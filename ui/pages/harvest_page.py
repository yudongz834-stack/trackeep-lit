# -*- coding: utf-8 -*-
"""采集台 —— 核心页（Slice 1）。

照 prototype-reference.html 的流程翻成 Qt 控件。Slice 1 范围：
- 左：分类期刊树（静态胸外 10 本，J Thorac Oncol 默认选中）
- 检索配置 chips：Article/Review/Editorial/Letter + 仅要有摘要（Slice 1 只存 UI 状态，
  不写回 journal-overrides.json；Editorial/Letter 才真透传引擎 -Include*）
- 采集最新（-ReldateDays 60，PubMed edat）；回填历史留占位禁用
- 「检索」→ run_async 跑 lit.engine.run_search（dry-run）→ 渲染审计页 / 报错原文

护栏（SPEC §7 基础三条）：①检索走 workers 线程不卡 UI ②运行中禁检索按钮 + 进度文案
③pubtype 至少勾一个才启用检索。**Slice 1 绝不 -Execute / 任何真实 Zotero 写入。**

配色只用 ui/style.py 已确认存在的常量（ACCENT/MUTED/BORDER/TEXT/CARD_BG/ACCENT_SOFT），
不引入新 style 常量（避免与 style.py 漂移致崩）。
"""
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (QCheckBox, QFrame, QHBoxLayout, QLabel,
                               QPushButton, QRadioButton, QScrollArea,
                               QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from lit import engine
from ui import style
from ui.workers import run_async

# Slice 1 静态刊：胸部肿瘤与胸外科 10 本（来源 prototype-reference.html §树）。
# 后续 slice 从 Mecha-Core 期刊来源表载全 74 本。
_JOURNALS = [
    "J Thorac Oncol",
    "Ann Thorac Surg",
    "Eur J Cardiothorac Surg",
    "J Thorac Cardiovasc Surg",
    "Lung Cancer",
    "Chest",
    "Thorax",
    "Lancet Respir Med",
    "Eur Respir J",
    "Clin Lung Cancer",
]
DEFAULT_JOURNAL = "J Thorac Oncol"
RELDATE_DAYS = 60   # 采集最新：近 60 天（PubMed edat）

# 文献类型 chips → 引擎开关。Article/Review 是引擎默认基底（query 恒含
# "journal article OR review AND hasabstract"，无法在 Slice 1 关掉），这里作 UI 状态；
# Editorial/Letter 才真透传引擎 -IncludeEditorial / -IncludeLetter。
_PUBTYPES = ["Article", "Review", "Editorial", "Letter"]
_DEFAULT_CHECKED = {"Article", "Review", "Editorial"}
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

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---------- 左：期刊树 ----------
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setRootIsDecorated(True)
        self.tree.setIndentation(14)
        self.tree.setUniformRowHeights(True)
        self.tree.setFixedWidth(248)
        self.tree.setSelectionMode(QTreeWidget.SingleSelection)
        self.tree.itemSelectionChanged.connect(self._on_journal_changed)
        cat = QTreeWidgetItem(["胸部肿瘤与胸外科（10）"])
        f = cat.font(0)
        f.setBold(True)
        cat.setFont(0, f)
        cat.setForeground(0, QBrush(QColor(style.MUTED)))
        cat.setFlags(cat.flags() & ~Qt.ItemIsSelectable)   # 分类节点不可选，只叶子驱动
        for name in _JOURNALS:
            leaf = QTreeWidgetItem([name])
            leaf.setData(0, Qt.UserRole, name)
            cat.addChild(leaf)
        self.tree.addTopLevelItem(cat)
        cat.setExpanded(True)
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
            "选一本刊 → 勾文献类型 → 点「检索」dry-run 预览（PubMed edat 近 %d 天 + "
            "Zotero 全库去重）。Slice 1 不写 Zotero、不动台账。" % RELDATE_DAYS))

        lay.addWidget(self._build_config())
        self.run_status = self._muted("")
        self.run_status.setWordWrap(True)
        self.run_status.setVisible(False)
        lay.addWidget(self.run_status)

        self.receipt_box = QVBoxLayout()
        self.receipt_box.setSpacing(10)
        lay.addLayout(self.receipt_box)
        lay.addStretch(1)

        self._select_journal(DEFAULT_JOURNAL)
        self._update_search_btn()

    # ---------- 配置面板 ----------

    def _build_config(self) -> QFrame:
        panel, ply = self._card()
        ply.setContentsMargins(20, 16, 20, 18)
        ply.addWidget(self._label("检索配置 · 该刊", "sectionTitle"))

        chips = QHBoxLayout()
        chips.setSpacing(8)
        self.pubtype_cbs: dict[str, QCheckBox] = {}
        for pt in _PUBTYPES:
            cb = QCheckBox(pt)
            cb.setChecked(pt in _DEFAULT_CHECKED)
            cb.toggled.connect(self._update_search_btn)
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

        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet("background:%s;" % style.BORDER)
        ply.addWidget(div)

        mrow = QHBoxLayout()
        self.rb_latest = QRadioButton("采集最新（近 %d 天 · edat）" % RELDATE_DAYS)
        self.rb_back = QRadioButton("回填历史（Slice 2）")
        self.rb_back.setEnabled(False)
        self.rb_back.setToolTip("Slice 2 接入：按日期范围回填历史文献。")
        self.rb_latest.setChecked(True)
        mrow.addWidget(self._muted("模式："))
        mrow.addWidget(self.rb_latest)
        mrow.addWidget(self.rb_back)
        mrow.addStretch(1)
        ply.addLayout(mrow)

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
        # 选中刊物变化不影响已发起的检索（回执按 _search_journal 渲染）
        self._update_search_btn()

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
        self.run_status.setText(
            "⏳ 检索中… spawn zotero-import.ps1 -Journal \"%s\" -ReldateDays %d "
            "-EmitJson（约 30–60 秒，后台线程，请勿关闭）"
            % (journal, RELDATE_DAYS))
        self.run_status.setVisible(True)

        inc_ed = self.pubtype_cbs["Editorial"].isChecked()
        inc_lt = self.pubtype_cbs["Letter"].isChecked()

        def job():
            return engine.run_search(
                journal, reldate_days=RELDATE_DAYS,
                include_editorial=inc_ed, include_letter=inc_lt)

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
        if not items:
            empty = self._muted(
                "（未命中文献：可能确无新文，或刊名错配——核对 [TA] 拼写）")
            card, clay = self._card()
            clay.addWidget(empty)
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
