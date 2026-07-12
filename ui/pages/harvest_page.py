# -*- coding: utf-8 -*-
"""采集台 —— 核心页（Slice 2）。

Slice 1 落的：分类期刊树 + chips + dry-run 检索 + 审计渲染 + 三条护栏（线程不卡 UI /
运行中禁按钮 / pubtype 至少一个）。Slice 2 在其上加四件：
  1. 载全 74 刊（lit.journals 解析期刊来源表，5 分类分组；解析失败回退静态 10）
  2. 检索配置写回例外表 journal-overrides.json（lit.overrides；只存与默认不同的字段，
     原子写、保留其它刊条目）；与默认不同的刊配置区显示「例外」小标
  3. 采集窗口从台账算（lit.ledger；有历史 → (今天-上次)+30 夹 [7,400]，首次 → 60），
     替代 Slice 1 硬编码 60
  4. UI 护栏两条：④ Article/Review 都没勾时灰掉「仅要有摘要」；
     ⑧ found==0 按 taMismatch 分流（错配红字 / 无新文献提示）

仍禁 -Execute / 任何真实 Zotero 写入（真导入属 Slice 3）。配色只用 ui/style.py 既有常量。
"""
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (QCheckBox, QFrame, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QRadioButton,
                               QScrollArea, QTreeWidget, QTreeWidgetItem,
                               QVBoxLayout, QWidget)

from lit import engine, journals, ledger, overrides
from ui import style
from ui.workers import run_async

# 文献类型 chips。Article/Review 是引擎默认基底（query 恒含
# "journal article OR review AND hasabstract"），不可在 UI 关掉对查询的影响；这里作
# UI 状态 + 护栏④的联动开关。Editorial/Letter 才真透传引擎 -Include*。
_PUBTYPES = ["Article", "Review", "Editorial", "Letter"]
_PILL_TEXT = {"new": "新增", "dup": "去重", "suspect": "疑似"}

# 内联语义色（lit 专用，不上 style.py：避免改 style 引入跨页漂移）
_NEW_COLOR = style.ACCENT            # 新文献：主色珊瑚
_NEW_BG = style.ACCENT_SOFT          # 新文献底
_DUP_COLOR = "#8A8578"               # 重复：暖深灰
_DUP_BG = "#ECE9DE"
_SUS_COLOR = "#E8590C"               # 疑似：警示橙
_SUS_BG = "#FFF1E6"


class HarvestPage(QWidget):
    def __init__(self):
        super().__init__()
        self._workers = []          # 后台检索线程引用（防回收），主窗关闭时 wait
        self._running = False
        self._search_journal = None   # 发起检索时锁定的刊名（防切刊后回执错位）
        self._loading = False          # 程序化载配置时抑制写回（切刊 setText/toggled 不落盘）
        self._window_days = ledger.DEFAULT_DAYS   # 当前刊算出的采集窗口（检索时用）

        self._journals = journals.load()          # {分类: [刊名,...]}，失败回退静态 10

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---------- 左：期刊树（5 分类） ----------
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setRootIsDecorated(True)
        self.tree.setIndentation(14)
        self.tree.setUniformRowHeights(True)
        self.tree.setFixedWidth(248)
        self.tree.setSelectionMode(QTreeWidget.SingleSelection)
        self.tree.itemSelectionChanged.connect(self._on_journal_changed)
        for cat in journals.CATEGORIES:
            names = self._journals.get(cat, [])
            if not names:                      # 兜底回退时其它分类空 → 不建空组
                continue
            node = QTreeWidgetItem([f"{cat}（{len(names)}）"])
            f = node.font(0)
            f.setBold(True)
            node.setFont(0, f)
            node.setForeground(0, QBrush(QColor(style.MUTED)))
            node.setFlags(node.flags() & ~Qt.ItemIsSelectable)   # 分类节点不可选
            for name in names:
                leaf = QTreeWidgetItem([name])
                leaf.setData(0, Qt.UserRole, name)
                node.addChild(leaf)
            self.tree.addTopLevelItem(node)
            node.setExpanded(True)
        root.addWidget(self.tree)

        # ---------- 右：滚动主区 ----------
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        root.addWidget(scroll, 1)
        body = QWidget()
        scroll.setWidget(body)
        lay = QVBoxLayout(body)
        lay.setContentsMargins(26, 22, 30, 18)
        lay.setSpacing(12)

        title = QLabel("📡  采集台")
        title.setObjectName("pageTitle")
        lay.addWidget(title)
        lay.addWidget(self._muted(
            "选一本刊 → 勾文献类型 / 主题过滤 → 点「检索」dry-run 预览（PubMed edat + "
            "Zotero 全库去重）。Slice 2 不写 Zotero、不动台账。"))

        lay.addWidget(self._build_config())
        self.run_status = self._muted("")
        self.run_status.setWordWrap(True)
        self.run_status.setVisible(False)
        lay.addWidget(self.run_status)

        self.receipt_box = QVBoxLayout()
        self.receipt_box.setSpacing(10)
        lay.addLayout(self.receipt_box)
        lay.addStretch(1)

        self._select_journal(journals.DEFAULT_JOURNAL)   # 触发 _on_journal_changed 载首刊配置
        self._update_search_btn()

    # ---------- 配置面板 ----------

    def _build_config(self) -> QFrame:
        panel, ply = self._card()
        ply.setContentsMargins(20, 16, 20, 18)

        # 标题行：检索配置 · 该刊  +  「例外」小标（该刊与默认不同时显示）
        hdr = QHBoxLayout()
        hdr.setSpacing(8)
        hdr.addWidget(self._label("检索配置 · 该刊", "sectionTitle"))
        self.exception_badge = QLabel("例外")
        self.exception_badge.setStyleSheet(
            "color:white; background:%s; padding:1px 8px; border-radius:7px;"
            "font-size:9pt; font-weight:bold;" % style.ACCENT)
        self.exception_badge.setVisible(False)
        hdr.addWidget(self.exception_badge)
        hdr.addStretch(1)
        ply.addLayout(hdr)

        # chips 行：Article/Review/Editorial/Letter | 仅要有摘要
        chips = QHBoxLayout()
        chips.setSpacing(8)
        self.pubtype_cbs: dict[str, QCheckBox] = {}
        for pt in _PUBTYPES:
            cb = QCheckBox(pt)
            cb.setChecked(pt in ("Article", "Review"))   # 基底默认开；Editorial/Letter 由切刊载入
            cb.toggled.connect(self._on_pubtype_toggled)
            chips.addWidget(cb)
            self.pubtype_cbs[pt] = cb
        sep = QFrame()
        sep.setFixedWidth(1)
        sep.setFixedHeight(20)
        sep.setStyleSheet("background:%s;" % style.BORDER)
        chips.addSpacing(4)
        chips.addWidget(sep)
        chips.addSpacing(4)
        self.cb_abstract = QCheckBox("仅要有摘要（Article/Review）")
        self.cb_abstract.setChecked(True)
        chips.addWidget(self.cb_abstract)
        chips.addStretch(1)
        ply.addLayout(chips)

        # 主题过滤行（topicFilter → 引擎 -TopicFilter；空 = 删该字段）
        trow = QHBoxLayout()
        trow.addWidget(self._muted("主题过滤："))
        self.topic_edit = QLineEdit()
        self.topic_edit.setPlaceholderText("lung[tiab] OR esophag*[tiab] …")
        self.topic_edit.editingFinished.connect(self._on_topic_edited)
        trow.addWidget(self.topic_edit, 1)
        ply.addLayout(trow)

        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet("background:%s;" % style.BORDER)
        ply.addWidget(div)

        # 模式 + 采集窗口（窗口天数从台账算）
        mrow = QHBoxLayout()
        self.rb_latest = QRadioButton("采集最新（edat）")
        self.rb_back = QRadioButton("回填历史（Slice 3）")
        self.rb_back.setEnabled(False)
        self.rb_back.setToolTip("Slice 3 接入：按日期范围回填历史文献。")
        self.rb_latest.setChecked(True)
        mrow.addWidget(self._muted("模式："))
        mrow.addWidget(self.rb_latest)
        mrow.addWidget(self.rb_back)
        mrow.addStretch(1)
        ply.addLayout(mrow)

        self.window_info = self._muted("")
        ply.addWidget(self.window_info)

        arow = QHBoxLayout()
        self.search_btn = QPushButton("🔍  检索")
        self.search_btn.setObjectName("primary")
        self.search_btn.setCursor(Qt.PointingHandCursor)
        self.search_btn.clicked.connect(self._start_search)
        arow.addWidget(self.search_btn)
        arow.addWidget(self._muted(
            "点一下 = spawn 引擎 + 去重预览（约 30–60 秒，dry-run，不写 Zotero）"), 1)
        ply.addLayout(arow)
        return panel

    # ---------- 期刊树 ----------

    def current_journal(self) -> str | None:
        it = self.tree.currentItem()
        if it is None:
            return None
        return it.data(0, Qt.UserRole)   # 叶子有 UserRole，分类节点为 None

    def _select_journal(self, name: str) -> None:
        for i in range(self.tree.topLevelItemCount()):
            cat = self.tree.topLevelItem(i)
            for j in range(cat.childCount()):
                leaf = cat.child(j)
                if leaf.data(0, Qt.UserRole) == name:
                    self.tree.setCurrentItem(leaf)
                    return

    def _on_journal_changed(self) -> None:
        # 分类节点不可选（flags 去掉 Selectable），这里只处理叶子选中
        if self.current_journal() is None:
            return
        self._load_config_for_current()
        self._update_window_for_current()
        self._update_search_btn()

    # ---------- 配置载入 / 写回 ----------

    def _load_config_for_current(self) -> None:
        """选中刊变化 → 读例外表，把 Editorial/Letter/topic 反映到 UI（Article/Review/摘要恒默认开）。

        _loading 抑制期间的 toggled / editingFinished 写回，避免切刊把旧刊状态写进新刊。
        """
        journal = self.current_journal()
        if journal is None:
            return
        cfg = overrides.get(journal)
        self._loading = True
        try:
            self.pubtype_cbs["Article"].setChecked(True)
            self.pubtype_cbs["Review"].setChecked(True)
            self.pubtype_cbs["Editorial"].setChecked(cfg["includeEditorial"])
            self.pubtype_cbs["Letter"].setChecked(cfg["includeLetter"])
            self.cb_abstract.setChecked(True)
            self.topic_edit.setText(cfg.get("topicFilter") or "")
        finally:
            self._loading = False
        self.exception_badge.setVisible(overrides.is_exception(journal))
        self._update_abstract_enabled()

    def _update_window_for_current(self) -> None:
        """选中刊 → 从台账算采集窗口，刷新 window_info + _window_days。"""
        journal = self.current_journal()
        if journal is None:
            return
        days, last = ledger.reldate_for(journal)
        self._window_days = days
        if last is None:
            self.window_info.setText("首次采集 · 近 %d 天" % days)
        else:
            self.window_info.setText(
                "采集最新：上次 %s · +30天缓冲 · 近 %d 天"
                % (last.isoformat(), days))

    def _on_pubtype_toggled(self) -> None:
        self._update_abstract_enabled()
        self._update_search_btn()
        if self._loading:
            return
        journal = self.current_journal()
        if journal:
            self._persist_current(journal)

    def _on_topic_edited(self) -> None:
        if self._loading:
            return
        journal = self.current_journal()
        if journal:
            self._persist_current(journal)

    def _persist_current(self, journal: str) -> None:
        """把当前 Editorial/Letter/topic 写回例外表（与默认相同则删该刊条目）。"""
        cfg = {
            "includeEditorial": self.pubtype_cbs["Editorial"].isChecked(),
            "includeLetter": self.pubtype_cbs["Letter"].isChecked(),
            "topicFilter": self.topic_edit.text().strip() or None,
        }
        try:
            overrides.save(journal, cfg)
        except OSError as e:
            self.run_status.setText("⚠ 配置写回失败：%s" % e)
            self.run_status.setVisible(True)
        self.exception_badge.setVisible(overrides.is_exception(journal))

    def _update_abstract_enabled(self) -> None:
        # 护栏④：「仅要有摘要」只对 Article/Review 有意义 —— 两者都没勾 → 灰掉
        art = self.pubtype_cbs["Article"].isChecked()
        rev = self.pubtype_cbs["Review"].isChecked()
        self.cb_abstract.setEnabled(art or rev)

    # ---------- 检索 ----------

    def _update_search_btn(self) -> None:
        any_pub = any(cb.isChecked() for cb in self.pubtype_cbs.values())
        self.search_btn.setEnabled(any_pub and not self._running)

    def _start_search(self) -> None:
        if self._running:
            return
        journal = self.current_journal()
        if not journal:
            return
        if not any(cb.isChecked() for cb in self.pubtype_cbs.values()):
            return
        self._search_journal = journal
        self._running = True
        self._update_search_btn()
        self._clear_receipt()
        days = self._window_days
        inc_ed = self.pubtype_cbs["Editorial"].isChecked()
        inc_lt = self.pubtype_cbs["Letter"].isChecked()
        topic = self.topic_edit.text().strip() or None
        self.run_status.setText(
            "⏳ 检索中… spawn zotero-import.ps1 -Journal \"%s\" -ReldateDays %d "
            "-EmitJson（约 30–60 秒，后台线程，请勿关闭）"
            % (journal, days))
        self.run_status.setVisible(True)

        def job():
            return engine.run_search(
                journal, reldate_days=days,
                include_editorial=inc_ed, include_letter=inc_lt,
                topic_filter=topic)

        def done(r):
            self._running = False
            self._update_search_btn()
            self.run_status.setVisible(False)
            self._render_receipt(self._search_journal, r)

        def failed(err):
            self._running = False
            self._update_search_btn()
            self.run_status.setText("❌ 检索失败：" + err)
            self.run_status.setVisible(True)

        run_async(self, job, done=done, failed=failed)

    # ---------- 审计渲染 ----------

    def _clear_receipt(self) -> None:
        while self.receipt_box.count():
            it = self.receipt_box.takeAt(0)
            w = it.widget()
            if w is not None:
                w.deleteLater()

    def _render_receipt(self, journal: str, r: dict) -> None:
        self._clear_receipt()
        box = self.receipt_box

        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        badge = QLabel(f"  ✓ 预览完成 · {ts} · dry-run（未写 Zotero）  ")
        badge.setStyleSheet(
            "background:%s; color:white; padding:6px 14px; border-radius:9px;"
            "font-weight:bold; font-size:10pt;" % style.ACCENT)
        box.addWidget(badge)

        # 统计行：found / new / dup / suspect
        counts = r.get("counts", {}) or {}
        stats = QHBoxLayout()
        stats.setSpacing(8)
        stats.addWidget(self._stat_chip("命中", r.get("found", 0), style.TEXT))
        stats.addWidget(self._stat_chip("新增", counts.get("new", 0), _NEW_COLOR))
        stats.addWidget(self._stat_chip("去重", counts.get("dup", 0), _DUP_COLOR))
        stats.addWidget(self._stat_chip("疑似", counts.get("suspect", 0), _SUS_COLOR))
        stats.addStretch(1)
        box.addLayout(stats)

        # query 行
        qline = QLabel(r.get("query", "—") or "—")
        qline.setStyleSheet("font-family: Consolas, monospace; color:%s;" % style.MUTED)
        qline.setWordWrap(True)
        qline.setTextInteractionFlags(Qt.TextSelectableByMouse)
        box.addWidget(qline)

        # 分组清单
        items = r.get("items", []) or []
        groups: dict[str, list] = {}
        for it in items:
            groups.setdefault((it.get("status") or "?"), []).append(it)
        order = [("new", "🆕 新增 · 将导入"), ("dup", "♻ 去重跳过 · 已在库"),
                 ("suspect", "❓ 疑似 · 待人工")]
        for key, title in order:
            rows = groups.get(key)
            if not rows:
                continue
            card, clay = self._card()
            clay.setContentsMargins(0, 0, 0, 0)
            clay.setSpacing(0)
            hdr = QLabel(f"{title}（{len(rows)} 篇）")
            hdr.setStyleSheet(
                "font-weight:bold; padding:10px 14px; color:%s;" % style.TEXT)
            clay.addWidget(hdr)
            for it in rows:
                clay.addWidget(self._item_row(it, key))
            box.addWidget(card)

        # 护栏⑧：found==0 按 taMismatch 分流
        if r.get("found", 0) == 0:
            card, clay = self._card()
            if r.get("taMismatch"):
                warn = QLabel("⚠ 刊名可能与 PubMed [TA] 错配，核对缩写")
                warn.setStyleSheet(style.DANGER_TEXT)
                warn.setWordWrap(True)
                clay.addWidget(warn)
            else:
                broad = r.get("broadCount")
                broad_str = str(broad) if broad is not None else "—"
                clay.addWidget(self._muted(
                    "本期无新文献（该刊 [TA] 宽检索共 %s 篇存在）" % broad_str))
            box.addWidget(card)
        elif not items:
            card, clay = self._card()
            clay.addWidget(self._muted("（未命中文献）"))
            box.addWidget(card)

        # 页脚：collection / journal / mode
        coll = r.get("collection", {}) or {}
        foot = self._muted(
            "collection key=%s（%s）· journal=%s · mode=%s · dry-run 预览：未写 Zotero、"
            "未动台账。真实导入属 Slice 3。"
            % (coll.get("key", "—"), "已存在" if coll.get("exists") else "未建",
               r.get("journal", "—"), r.get("mode", "—")))
        foot.setTextInteractionFlags(Qt.TextSelectableByMouse)
        box.addWidget(foot)

    def _stat_chip(self, label: str, num, color: str) -> QFrame:
        f = QFrame()
        f.setObjectName("card")
        l = QVBoxLayout(f)
        l.setContentsMargins(12, 6, 12, 6)
        l.setSpacing(0)
        lb1 = QLabel(label)
        lb1.setStyleSheet("color:%s; font-size:9pt;" % style.MUTED)
        lb2 = QLabel(str(num))
        lb2.setStyleSheet("font-size:16pt; font-weight:bold; color:%s;" % color)
        l.addWidget(lb1)
        l.addWidget(lb2)
        return f

    def _item_row(self, it: dict, status: str) -> QFrame:
        row = QFrame()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(14, 8, 14, 8)
        rl.setSpacing(10)

        if status == "new":
            fg, bg = _NEW_COLOR, _NEW_BG
        elif status == "dup":
            fg, bg = _DUP_COLOR, _DUP_BG
        else:
            fg, bg = _SUS_COLOR, _SUS_BG
        pill = QLabel(_PILL_TEXT.get(status, status))
        pill.setFixedWidth(54)
        pill.setAlignment(Qt.AlignCenter)
        pill.setStyleSheet(
            "color:%s; background:%s; border-radius:6px; padding:3px 0;"
            "font-weight:bold; font-size:9pt;" % (fg, bg))

        title = QLabel(it.get("title") or "（无标题）")
        title.setWordWrap(True)
        title.setTextInteractionFlags(Qt.TextSelectableByMouse)

        # tooltip：完整明细
        tip = [f"类型: {it.get('type', '—')}",
               f"有摘要: {'是' if it.get('hasAbstract') else '否'}"]
        if it.get("pmid"):
            tip.append(f"PMID: {it['pmid']}")
        if it.get("doi"):
            tip.append(f"DOI: {it['doi']}")
        if it.get("dedupBy"):
            tip.append(f"判重依据: {it['dedupBy']}")
        if it.get("dupSrc"):
            tip.append(f"重复来源: {it['dupSrc']}")
        tip.append(f"状态: {status}")
        row.setToolTip("\n".join(tip))

        rl.addWidget(pill)
        rl.addWidget(title, 1)
        return row

    # ---------- 小部件工厂 ----------

    @staticmethod
    def _muted(text: str) -> QLabel:
        lb = QLabel(text)
        lb.setObjectName("muted")
        lb.setWordWrap(True)
        return lb

    @staticmethod
    def _label(text: str, obj: str) -> QLabel:
        lb = QLabel(text)
        if obj:
            lb.setObjectName(obj)
        return lb

    @staticmethod
    def _card() -> tuple[QFrame, QVBoxLayout]:
        f = QFrame()
        f.setObjectName("card")
        lay = QVBoxLayout(f)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(6)
        return f, lay
