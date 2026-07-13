# -*- coding: utf-8 -*-
"""采集台 —— 核心页（Slice 3）。

Slice 1 落的：分类期刊树 + chips + dry-run 检索 + 审计渲染 + 三条护栏（线程不卡 UI /
运行中禁按钮 / pubtype 至少一个）。Slice 2 在其上加四件：
  1. 载全 74 刊（lit.journals 解析期刊来源表，5 分类分组；解析失败回退静态 10）
  2. 检索配置写回例外表 journal-overrides.json（lit.overrides；只存与默认不同的字段，
     原子写、保留其它刊条目）；与默认不同的刊配置区显示「例外」小标
  3. 采集窗口从台账算（lit.ledger；有历史 → (今天-上次)+30 夹 [7,400]，首次 → 60），
     替代 Slice 1 硬编码 60
  4. UI 护栏两条：④ Article/Review 都没勾时灰掉「仅要有摘要」；
     ⑧ found==0 按 taMismatch 分流（错配红字 / 无新文献提示）

Slice 3 在其上加真实导入路径（护栏⑨⑪⑮⑯）：
  5. 审计页加「导入」按钮（仅 new>0 显示）→ 确认框 → 受控建 collection（不存在时）
     → run_import（-Execute 真写）线程；导入用检索时锁定的 _last_params（防切刊/改配置
     导入错对象）；运行中禁检索+导入按钮（护栏②⑮ 单飞）
  6. 导入回执：✓ 已导入 X · 失败 Y · 去重 Z + 按 status 分组清单；failed>0 显「重试失败」
     （再跑一次 run_import，幂等）；导入后重读台账刷新采集窗口（护栏⑪ 锚点前移）
  7. 受控建 collection（lit.zotero）：collection.exists==false 且点导入 → 受控建框
     → PI 确认才 POST 创建子 collection（护栏⑯，现实极少触发）

Slice 4 在其上加回填历史（复用检索/导入流程，只换窗口参数）：
  8. 启用「回填历史」模式：选回填 → 显示年/月 QComboBox（近 8 年 + 全年/01…12）。
     检索/导入构 params 按模式分流：latest→reldate_days；back 全年→year；
     back 具体月→month="YYYY-MM"。_last_params 带 mode，检索 job / 导入 job 按
     mode 分流调引擎桥（run_search/run_import 都已支持 year/month）。
  9. 护栏⑭ 输入校验：年份不超今年（构造时已限）、当年月份非未来；违规 → 禁检索 +
     window_info 红字（style.DANGER_TEXT）。
 10. 护栏⑫ retmax 警示：found>=1000 → 审计页显橙字（style.WARN_TEXT）「命中达上限
     1000，可能截断，建议改按月回填」（本片只告警，不做自动分月循环）。

配色只用 ui/style.py 既有常量（新色为 lit 内联语义常量，沿用 Slice 2 约定）。
"""
from datetime import date, datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel,
                               QLineEdit, QMessageBox, QProgressBar, QPushButton,
                               QRadioButton, QScrollArea, QTreeWidget,
                               QTreeWidgetItem, QVBoxLayout, QWidget)

from lit import deepseek, engine, journals, ledger, overrides, strategy, zotero
from ui import style
from ui.workers import run_async

# 文献类型 chips。Article/Review 是引擎默认基底（query 恒含
# "journal article OR review AND hasabstract"），不可在 UI 关掉对查询的影响；这里作
# UI 状态 + 护栏④的联动开关。Editorial/Letter 才真透传引擎 -Include*。
_PUBTYPES = ["Article", "Review", "Editorial", "Letter"]

# 内联语义色（lit 专用，不上 style.py：避免改 style 引入跨页漂移）
_NEW_COLOR = style.ACCENT            # 新文献：主色珊瑚
_NEW_BG = style.ACCENT_SOFT          # 新文献底
_DUP_COLOR = "#8A8578"               # 重复：暖深灰
_DUP_BG = "#ECE9DE"
_SUS_COLOR = "#E8590C"               # 疑似：警示橙
_SUS_BG = "#FFF1E6"
_IMP_COLOR = style.ACCENT            # 已导入：同新增（imported = 已入库的 new）
_IMP_BG = style.ACCENT_SOFT
_FAIL_COLOR = "#C92A2A"              # 失败：危险红
_FAIL_BG = "#FFF0F0"

# status → (前景色, 底色, 药丸文字)。_item_row 与两个回执的分组清单共用。
_STATUS_STYLE = {
    "new":      (_NEW_COLOR,  _NEW_BG,  "新增"),
    "imported": (_IMP_COLOR,  _IMP_BG,  "已导入"),
    "dup":      (_DUP_COLOR,  _DUP_BG,  "去重"),
    "suspect":  (_SUS_COLOR,  _SUS_BG,  "疑似"),
    "failed":   (_FAIL_COLOR, _FAIL_BG, "失败"),
}

# 回填命中上限（PubMed esearch retmax）：达此值可能截断 → 审计页告警（护栏⑫）
_RETMAX_WARN = 1000


def _backfill_years() -> list[int]:
    """回填可选年份：近 8 年（当前年往前 7 年）。如 2026 → [2019..2026]。"""
    cy = date.today().year
    return list(range(cy - 7, cy + 1))


def _params_window_desc(params: dict | None) -> str:
    """从 _last_params 生成窗口描述文案（检索/导入文案 + 确认框共用）。"""
    if not params:
        return "—"
    mode = params.get("mode")
    if mode == "latest":
        return "近 %d 天（edat）" % params.get("reldate_days", "?")
    if mode == "back_year":
        return "%d 全年" % params.get("year", "?")
    if mode == "back_month":
        return params.get("month", "—")
    return "—"


def _engine_kwargs(params: dict) -> dict:
    """从 _last_params 取引擎调用关键字参数（窗口三选一 + 公共过滤项）。

    run_search / run_import 同构，本函数返回的 kwargs 两者都可直接 ** 展开传。
    """
    common = dict(include_editorial=params["inc_ed"],
                  include_letter=params["inc_lt"], topic_filter=params["topic"])
    mode = params["mode"]
    if mode == "latest":
        common["reldate_days"] = params["reldate_days"]
    elif mode == "back_year":
        common["year"] = params["year"]
    else:                                   # back_month
        common["month"] = params["month"]
    return common


def _engine_search(params: dict) -> dict:
    """按 params['mode'] 分流调 engine.run_search（dry-run，不写 Zotero）。"""
    return engine.run_search(params["journal"], **_engine_kwargs(params))


def _engine_import(params: dict) -> dict:
    """按 params['mode'] 分流调 engine.run_import（-Execute 真写 Zotero + 台账）。"""
    return engine.run_import(params["journal"], **_engine_kwargs(params))


class HarvestPage(QWidget):
    def __init__(self):
        super().__init__()
        self._workers = []          # 后台检索线程引用（防回收），主窗关闭时 wait
        self._running = False
        self._search_journal = None   # 发起检索时锁定的刊名（防切刊后回执错位）
        self._loading = False          # 程序化载配置时抑制写回（切刊 setText/toggled 不落盘）
        self._window_days = ledger.DEFAULT_DAYS   # 当前刊算出的采集窗口（latest 模式检索时用）
        self._latest_last = None      # 当前刊上次采集日期（latest 模式 window_info 文案用）
        self._last_params = None      # 检索成功时锁定的参数（journal/mode/窗口/inc_ed/inc_lt/topic）—— 导入用它，不用当前 UI 态
        self._last_result = None      # 检索成功时的引擎结果 r（AI 复筛/重渲用，不重新检索）
        self._ai_verdicts = None      # DeepSeek 复筛判决 {pmid: {keep,reason}}；None=未筛（6b-1 advisory）
        self._action_btns = []        # 当前回执里的动作按钮（导入/重试/AI复筛），_running 时整体禁用

        # 运行态 UI（醒目横幅 + 走马灯进度条 + 秒数跳动，证明后台没卡死）
        self._elapsed = 0             # 当前运行已用秒数（_elapsed_timer 每秒 +1）
        self._run_verb = "检索"       # 运行动作名（检索/导入），横幅文案用
        self._run_detail = ""         # 运行副文案（窗口描述），秒表跳动时保留
        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.setInterval(1000)
        self._elapsed_timer.timeout.connect(self._tick_elapsed)

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

        self._config_panel = self._build_config()   # 存引用：运行时整体冻结（视觉锁定）
        lay.addWidget(self._config_panel)
        self.run_status = self._muted("")
        self.run_status.setWordWrap(True)
        self.run_status.setVisible(False)
        lay.addWidget(self.run_status)
        # 走马灯进度条（不定长 range(0,0)）：运行时显示 = 明确「正在跑」信号
        self.run_progress = QProgressBar()
        self.run_progress.setRange(0, 0)
        self.run_progress.setTextVisible(False)
        self.run_progress.setFixedHeight(6)
        self.run_progress.setVisible(False)
        lay.addWidget(self.run_progress)

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

        # 模式 + 窗口（采集最新 / 回填历史）
        mrow = QHBoxLayout()
        mrow.setSpacing(8)
        self.rb_latest = QRadioButton("采集最新（edat）")
        self.rb_back = QRadioButton("回填历史")
        self.rb_latest.toggled.connect(self._on_mode_changed)
        mrow.addWidget(self._muted("模式："))
        mrow.addWidget(self.rb_latest)
        mrow.addWidget(self.rb_back)
        # 回填年/月选择（默认隐藏，选回填历史才显示）
        lb_year = self._muted("年：")
        self.cb_year = QComboBox()
        for y in _backfill_years():
            self.cb_year.addItem(str(y), y)
        self.cb_year.setCurrentIndex(self.cb_year.count() - 1)   # 默认当年
        lb_month = self._muted("月：")
        self.cb_month = QComboBox()
        self.cb_month.addItem("全年", None)
        for m in range(1, 13):
            self.cb_month.addItem("%02d" % m, "%02d" % m)
        self.cb_year.currentIndexChanged.connect(self._on_backfill_period_changed)
        self.cb_month.currentIndexChanged.connect(self._on_backfill_period_changed)
        mrow.addWidget(lb_year)
        mrow.addWidget(self.cb_year)
        mrow.addWidget(lb_month)
        mrow.addWidget(self.cb_month)
        mrow.addStretch(1)
        ply.addLayout(mrow)
        self._backfill_widgets = [lb_year, self.cb_year, lb_month, self.cb_month]

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

        self.rb_latest.setChecked(True)   # 放 search_btn 之后：触发 _on_mode_changed 需用它
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
        """选中刊 / 导入后 → 重算 latest 窗口天数（latest 模式检索用）+ 刷新文案。"""
        journal = self.current_journal()
        if journal is None:
            return
        days, last = ledger.reldate_for(journal)
        self._window_days = days
        self._latest_last = last
        self._refresh_window_info()

    # ---------- 模式 / 回填窗口 ----------

    def _on_mode_changed(self) -> None:
        """采集最新 ↔ 回填历史 切换：显示/隐藏回填年月控件 + 刷新文案 + 重算检索按钮。"""
        is_back = self.rb_back.isChecked()
        for w in self._backfill_widgets:
            w.setVisible(is_back)
        self._refresh_window_info()
        self._update_search_btn()

    def _on_backfill_period_changed(self) -> None:
        """回填年/月选择变更 → 刷新文案（校验提示）+ 重算检索按钮。"""
        self._refresh_window_info()
        self._update_search_btn()

    def _refresh_window_info(self) -> None:
        """按当前模式刷新 window_info：latest 用已算的 _window_days/_latest_last；back 用年/月。"""
        if self.rb_latest.isChecked():
            last = self._latest_last
            if last is None:
                self.window_info.setText("采集最新 · 首次采集 · 近 %d 天" % self._window_days)
            else:
                self.window_info.setText(
                    "采集最新：上次 %s · +30天缓冲 · 近 %d 天"
                    % (last.isoformat(), self._window_days))
            self.window_info.setStyleSheet("")
            return
        # 回填历史：先校验（当年月份非未来），通过显窗口、违规显红字
        ok, msg = self._backfill_validation()
        if ok:
            self.window_info.setText("回填历史 · %s" % self._backfill_desc())
            self.window_info.setStyleSheet("")
        else:
            self.window_info.setText("⚠ " + msg)
            self.window_info.setStyleSheet(style.DANGER_TEXT)

    def _backfill_validation(self) -> tuple[bool, str]:
        """护栏⑭：年份不超今年（构造时已限 [近8年]）、当年月份非未来。返回 (ok, msg)。"""
        year = self.cb_year.currentData()
        month = self.cb_month.currentData()      # None = 全年（恒合法）
        today = date.today()
        if year == today.year and month is not None and int(month) > today.month:
            return False, "%d 年 %s 月尚未到来，请改选更早的月份" % (year, month)
        return True, ""

    def _backfill_desc(self) -> str:
        """回填窗口的人读描述（window_info / 检索文案 / 确认框共用）。"""
        year = self.cb_year.currentData()
        month = self.cb_month.currentData()
        if month is None:
            return "%d 全年" % year
        return "%d-%s" % (year, month)

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

    # ---------- 运行态 UI（横幅 + 进度条 + 秒表 + 冻结） ----------

    def _begin_running_ui(self, verb: str, detail: str) -> None:
        """进入运行态：醒目珊瑚横幅 + 走马灯进度条 + 秒数跳动 + 冻结期刊树/配置区。

        verb=检索/导入；detail=窗口描述（如「近 30 天（edat），约 30–60 秒」）。
        灭弹窗后，这块是唯一「正在跑」信号 —— 三重可视化证明后台没卡死。
        """
        self._run_verb = verb
        self._run_detail = detail
        self._elapsed = 0
        self.run_status.setStyleSheet(
            "background:%s; color:white; padding:8px 14px; border-radius:9px;"
            "font-weight:bold;" % style.ACCENT)
        self.run_status.setText("⏳ 正在%s… 已用 0s · %s · 请勿关闭窗口" % (verb, detail))
        self.run_status.setVisible(True)
        self.run_progress.setVisible(True)
        self.tree.setEnabled(False)          # 冻结期刊树（运行中锁定目标）
        self._config_panel.setEnabled(False)  # 冻结配置区（防运行中误改）
        self._elapsed_timer.start()

    def _end_running_ui(self) -> None:
        """退出运行态：停秒表 + 收进度条 + 解冻树/配置。done 与 failed 都必须调。

        run_status 文案/样式由调用方善后（成功→隐藏；失败→红字）。"""
        self._elapsed_timer.stop()
        self.run_progress.setVisible(False)
        self.tree.setEnabled(True)
        self._config_panel.setEnabled(True)

    def _tick_elapsed(self) -> None:
        """每秒刷新横幅秒数（保留动作名 + 副文案），让 PI 看到进度在动、没冻死。"""
        self._elapsed += 1
        self.run_status.setText(
            "⏳ 正在%s… 已用 %ds · %s · 请勿关闭窗口"
            % (self._run_verb, self._elapsed, self._run_detail))

    # ---------- 检索 ----------

    def _update_search_btn(self) -> None:
        any_pub = any(cb.isChecked() for cb in self.pubtype_cbs.values())
        if not (any_pub and not self._running):
            self.search_btn.setEnabled(False)
            return
        # 回填模式：校验通过才能检索（护栏⑭）
        if self.rb_back.isChecked():
            ok, _ = self._backfill_validation()
            self.search_btn.setEnabled(ok)
        else:
            self.search_btn.setEnabled(True)

    def _start_search(self) -> None:
        if self._running:
            return
        journal = self.current_journal()
        if not journal:
            return
        if not any(cb.isChecked() for cb in self.pubtype_cbs.values()):
            return
        # 回填模式：护栏⑭ 校验（按钮已据此禁用，这里再挡一道）
        if self.rb_back.isChecked():
            ok, _ = self._backfill_validation()
            if not ok:
                return
        self._search_journal = journal
        self._running = True
        self._update_search_btn()
        self._clear_receipt()
        inc_ed = self.pubtype_cbs["Editorial"].isChecked()
        inc_lt = self.pubtype_cbs["Letter"].isChecked()
        topic = self.topic_edit.text().strip() or None

        # 按模式构窗口参数 + argv/窗口描述（_last_params 带 mode，导入按 mode 分流）
        if self.rb_latest.isChecked():
            params = {"journal": journal, "mode": "latest",
                      "reldate_days": self._window_days,
                      "inc_ed": inc_ed, "inc_lt": inc_lt, "topic": topic}
            argv_desc = "-ReldateDays %d" % self._window_days
            window_desc = "近 %d 天（edat）" % self._window_days
        else:
            year = self.cb_year.currentData()
            month = self.cb_month.currentData()
            if month is None:
                params = {"journal": journal, "mode": "back_year", "year": year,
                          "inc_ed": inc_ed, "inc_lt": inc_lt, "topic": topic}
                argv_desc = "-Year %d" % year
            else:
                mon_str = "%d-%s" % (year, month)
                params = {"journal": journal, "mode": "back_month",
                          "year": year, "month": mon_str,
                          "inc_ed": inc_ed, "inc_lt": inc_lt, "topic": topic}
                argv_desc = "-Month %s" % mon_str
            window_desc = self._backfill_desc()
        self._last_params = None          # 清旧的，检索成功才重新锁定（防导入用上一次的窗口）

        self._begin_running_ui("检索", "%s，约 30–60 秒" % window_desc)

        def job():
            return _engine_search(params)

        def done(r):
            self._running = False
            self._end_running_ui()
            self._update_search_btn()
            self.run_status.setVisible(False)
            self._last_params = params          # 检索成功才锁定导入目标（失败不覆盖）
            self._last_result = r               # 锁定结果供 AI 复筛/重渲复用（不重检索）
            self._ai_verdicts = None            # 新检索清旧 AI 判决
            self._render_receipt(self._search_journal, r, params)

        def failed(err):
            self._running = False
            self._end_running_ui()
            self._update_search_btn()
            self.run_status.setStyleSheet(style.DANGER_TEXT)
            self.run_status.setText("❌ 检索失败：" + err)
            self.run_status.setVisible(True)

        run_async(self, job, done=done, failed=failed)

    # ---------- 审计渲染 ----------

    def _clear_receipt(self) -> None:
        self._action_btns = []           # 旧回执的动作按钮随 widget 一并销毁，清引用
        self._clear_layout(self.receipt_box)

    @staticmethod
    def _clear_layout(layout) -> None:
        """递归清空布局：直属 widget 销毁，嵌套布局（stats/irow/arow 等）内的 widget
        也一并递归销毁——否则嵌套布局里的按钮/药丸只被 takeAt 摘下、仍挂 body 累积泄漏
        （新卡片不透明重绘遮住了它，视觉masked但控件在涨）。"""
        while layout.count():
            it = layout.takeAt(0)
            w = it.widget()
            if w is not None:
                w.deleteLater()
            else:
                sub = it.layout()
                if sub is not None:
                    HarvestPage._clear_layout(sub)
                    sub.deleteLater()

    def _render_receipt(self, journal: str, r: dict, params: dict | None = None) -> None:
        self._clear_receipt()
        box = self.receipt_box

        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        badge = QLabel(
            f"  ✓ 预览完成 · {_params_window_desc(params)} · {ts} · dry-run（未写 Zotero）  ")
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

        # 护栏⑫：found>=retmax 上限可能截断 → 橙字告警（建议改按月回填）
        if r.get("found", 0) >= _RETMAX_WARN:
            trunc = QLabel("⚠ 命中达上限 %d，可能截断，建议改按月回填" % _RETMAX_WARN)
            trunc.setStyleSheet(style.WARN_TEXT)
            trunc.setWordWrap(True)
            box.addWidget(trunc)

        # query 行
        qline = QLabel(r.get("query", "—") or "—")
        qline.setStyleSheet("font-family: Consolas, monospace; color:%s;" % style.MUTED)
        qline.setWordWrap(True)
        qline.setTextInteractionFlags(Qt.TextSelectableByMouse)
        box.addWidget(qline)

        # AI 复筛判决（6b-1 advisory）：仅标注、不拦截导入；ai_on 决定是否出「复筛」按钮
        ai_on = strategy.resolve(journal)["deepseek_enabled"]
        verdicts = self._ai_verdicts or {}

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
            # new 组 + 已有 AI 判决 → 表头附「🤖 AI 建议留 X / 滤 Y」
            hdr_text = f"{title}（{len(rows)} 篇）"
            if key == "new" and verdicts:
                kept = sum(1 for it in rows
                           if (verdicts.get(str(it.get("pmid"))) or {}).get("keep"))
                hdr_text = ("🆕 新增（%d 篇 · 🤖 AI 建议留 %d / 滤 %d）"
                            % (len(rows), kept, len(rows) - kept))
            hdr = QLabel(hdr_text)
            hdr.setStyleSheet(
                "font-weight:bold; padding:10px 14px; color:%s;" % style.TEXT)
            clay.addWidget(hdr)
            for it in rows:
                v = verdicts.get(str(it.get("pmid"))) if key == "new" else None
                clay.addWidget(self._item_row(it, key, verdict=v))
            box.addWidget(card)

        # 导入按钮（仅 new>0 显示）：确认框 → 受控建 collection（不存在时）→ run_import
        new_count = counts.get("new", 0)
        if new_count > 0:
            irow = QHBoxLayout()
            imp = QPushButton("📥  导入到 Zotero")
            imp.setObjectName("primary")
            imp.setCursor(Qt.PointingHandCursor)
            imp.setEnabled(not self._running)
            imp.clicked.connect(lambda: self._on_import_clicked(r))
            irow.addWidget(imp)
            irow.addWidget(self._muted(
                "真实写库（新增 · 去重 · 可逆：可移回收站）。点击后先确认。"), 1)
            box.addLayout(irow)
            self._action_btns.append(imp)

        # 🤖 DeepSeek 复筛（6b-1 advisory）：仅该刊分类开了 DeepSeek 且有 new 才出
        if ai_on and new_count > 0:
            arow = QHBoxLayout()
            if not verdicts:
                aibtn = QPushButton("🤖  DeepSeek 复筛（预览判决）")
                aibtn.setCursor(Qt.PointingHandCursor)
                aibtn.setEnabled(not self._running)
                aibtn.clicked.connect(self._start_ai_filter)
                arow.addWidget(aibtn)
                arow.addWidget(self._muted(
                    "按分类判据逐篇判「主体是否相关」（约 10–30 秒）。仅供参考，本版不拦截导入。"), 1)
                self._action_btns.append(aibtn)
            else:
                note = self._muted(
                    "🤖 AI 判决仅供参考 —— 本版**不拦截导入**（导入仍导入全部新增）。"
                    "判据准不准可在「采集策略」页按分类调整。")
                arow.addWidget(note, 1)
            box.addLayout(arow)

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

    # ---------- 导入（Slice 3）----------

    def _set_action_btns_enabled(self, on: bool) -> None:
        """批量切当前回执里的动作按钮（导入/重试/AI复筛）可用态——_running 时整体禁用。"""
        for b in self._action_btns:
            b.setEnabled(on)

    def _start_ai_filter(self) -> None:
        """🤖 DeepSeek 复筛（6b-1 advisory）：对检索结果的 new 候选按分类判据判 keep/drop。

        结果只标注在审计页、**不拦截导入**。用检索时锁定的 _last_params['journal'] +
        _last_result（不重新检索）；_running 时直接返回（单飞）。判据准不准由 PI 在
        「采集策略」页调，本处只照判据执行。
        """
        if self._running:
            return
        r, p = self._last_result, self._last_params
        if not r or not p:
            return
        journal = p["journal"]
        new_items = [it for it in (r.get("items") or []) if it.get("status") == "new"]
        if not new_items:
            return
        criteria = strategy.resolve(journal)["deepseek_criteria"]
        self._running = True
        self._update_search_btn()
        self._set_action_btns_enabled(False)
        self._begin_running_ui("AI 复筛", "DeepSeek V4 Flash 逐篇判，约 10–30 秒")

        def job():
            return deepseek.classify(new_items, criteria)

        def done(verdicts):
            self._running = False
            self._end_running_ui()
            self._update_search_btn()
            self.run_status.setVisible(False)
            self._ai_verdicts = verdicts
            self._render_receipt(journal, r, p)     # 重渲：new 组带上 AI 留/滤标注

        def failed(err):
            self._running = False
            self._end_running_ui()
            self._update_search_btn()
            self._set_action_btns_enabled(True)
            self.run_status.setStyleSheet(style.DANGER_TEXT)
            self.run_status.setText("❌ AI 复筛失败：" + err)
            self.run_status.setVisible(True)

        run_async(self, job, done=done, failed=failed)

    def _on_import_clicked(self, r: dict) -> None:
        """导入按钮：确认框 → 受控建 collection（不存在时）→ run_import 线程。

        用 _last_params（检索时锁定的 journal/days/配置），不用当前 UI 态——防检索后
        切了刊/改了配置却导入错对象。_running 时直接返回（护栏⑮ 单飞）。
        """
        if self._running:
            return
        p = self._last_params
        if not p:
            return
        journal = p["journal"]
        new_count = (r.get("counts") or {}).get("new", 0)
        ans = QMessageBox.question(
            self, "确认真实导入",
            "确认真实导入 %d 篇新文献到 Zotero「%s」collection？\n"
            "窗口：%s\n（新增 · 去重 · 可逆：可移回收站）"
            % (new_count, journal, _params_window_desc(p)))
        if ans != QMessageBox.Yes:
            return
        # 受控建 collection（护栏⑯）：检索说 collection 不存在 → 先建再导入
        coll = r.get("collection") or {}
        if not coll.get("exists"):
            if not self._ensure_collection(journal):
                return          # 用户取消建 / 分类未找到 / 建失败 → 放弃导入
        self._begin_import(p)

    def _ensure_collection(self, journal: str) -> bool:
        """collection 不存在时弹受控建框；Yes → POST 真建；No / 分类未找到 / 失败 → False。

        parent = 该刊分类的顶层 collection（zotero.find_top_key 按分类名匹配）。
        现实 74 刊 collection 都已存在，此路极少触发。
        """
        category = journals.category_of(journal)
        if not category:
            QMessageBox.warning(
                self, "无法创建 collection",
                "期刊「%s」不在任何分类下，无法确定父 collection。" % journal)
            return False
        ans = QMessageBox.question(
            self, "该刊 collection 不存在",
            "该刊 collection 不存在。拟在分类「%s」下创建 collection「%s」"
            "（[TA]=%s）。\n确认创建？" % (category, journal, journal))
        if ans != QMessageBox.Yes:
            return False
        try:
            parent_key = zotero.find_top_key(category)
            if not parent_key:
                QMessageBox.warning(
                    self, "无法创建 collection",
                    "Zotero 中未找到分类「%s」的顶层 collection，\n"
                    "请先手动建好该分类 collection 再导入。" % category)
                return False
            zotero.create_collection(journal, parent_key)
        except Exception as e:
            QMessageBox.warning(self, "创建 collection 失败", str(e))
            return False
        return True

    def _begin_import(self, params: dict) -> None:
        """发起导入：禁按钮 + 进度文案 + run_async 跑 run_import；done 渲导入回执。"""
        self._running = True
        self._update_search_btn()                # 禁检索按钮
        self._set_action_btns_enabled(False)     # 禁导入/重试按钮
        self._begin_running_ui("导入", "真写 Zotero，约 1–3 分钟")

        def job():
            return _engine_import(params)

        def done(ri):
            self._running = False
            self._end_running_ui()
            self._update_search_btn()
            self.run_status.setVisible(False)
            # 护栏⑪：导入成功 → 台账已被引擎更新 → 重读刷新采集窗口（仅当还停在该刊）
            if self.current_journal() == params["journal"]:
                self._update_window_for_current()
            self._render_import_receipt(params, ri)

        def failed(err):
            self._running = False
            self._end_running_ui()
            self._update_search_btn()
            self._set_action_btns_enabled(True)
            self.run_status.setStyleSheet(style.DANGER_TEXT)
            self.run_status.setText("❌ 导入失败：" + err)
            self.run_status.setVisible(True)

        run_async(self, job, done=done, failed=failed)

    def _render_import_receipt(self, params: dict, r: dict) -> None:
        """导入回执：✓ 已导入 X · 失败 Y · 去重 Z + 按 status 分组清单 + 失败重试。"""
        self._clear_receipt()
        box = self.receipt_box
        counts = r.get("counts") or {}
        imported = counts.get("imported", 0) or 0
        failed = counts.get("failed", 0) or 0
        dup = counts.get("dup", 0) or 0

        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        badge = QLabel(f"  ✓ 已导入 {imported} · 失败 {failed} · 去重 {dup} · {ts}  ")
        badge.setStyleSheet(
            "background:%s; color:white; padding:6px 14px; border-radius:9px;"
            "font-weight:bold; font-size:10pt;" % style.ACCENT)
        box.addWidget(badge)

        stats = QHBoxLayout()
        stats.setSpacing(8)
        stats.addWidget(self._stat_chip("已导入", imported, _IMP_COLOR))
        stats.addWidget(self._stat_chip("失败", failed, _FAIL_COLOR))
        stats.addWidget(self._stat_chip("去重", dup, _DUP_COLOR))
        stats.addStretch(1)
        box.addLayout(stats)

        # 分组清单（imported/failed/dup/suspect）
        items = r.get("items", []) or []
        groups: dict[str, list] = {}
        for it in items:
            groups.setdefault((it.get("status") or "?"), []).append(it)
        order = [("imported", "✓ 已导入"), ("failed", "✗ 失败 · 可重试"),
                 ("dup", "♻ 去重跳过"), ("suspect", "❓ 疑似 · 待人工")]
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

        # 失败 > 0 → 重试按钮（再跑一次 run_import，幂等）
        if failed > 0:
            rrow = QHBoxLayout()
            retry = QPushButton("🔁  重试失败（%d）" % failed)
            retry.setObjectName("primary")
            retry.setCursor(Qt.PointingHandCursor)
            retry.setEnabled(not self._running)
            retry.clicked.connect(lambda: self._begin_import(params))
            rrow.addWidget(retry)
            rrow.addWidget(self._muted(
                "引擎台账只记成功、去重跳过已导入，重试只补失败项（幂等）。"), 1)
            box.addLayout(rrow)
            self._action_btns.append(retry)

        coll = r.get("collection") or {}
        foot = self._muted(
            "真实导入完成 · 窗口 %s · collection key=%s · journal=%s · 已写 Zotero + 台账。"
            % (_params_window_desc(params), coll.get("key", "—"),
               r.get("journal", params.get("journal", "—"))))
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

    def _item_row(self, it: dict, status: str, verdict: dict | None = None) -> QFrame:
        row = QFrame()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(14, 8, 14, 8)
        rl.setSpacing(10)

        fg, bg, pill_text = _STATUS_STYLE.get(status, (style.TEXT, style.CARD_BG, status))
        pill = QLabel(pill_text)
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
        if verdict is not None:
            tip.append("AI: %s · %s" % ("建议留" if verdict.get("keep") else "建议滤",
                                        verdict.get("reason") or "—"))
        row.setToolTip("\n".join(tip))

        rl.addWidget(pill)
        rl.addWidget(title, 1)
        # AI 复筛判决（6b-1 advisory）：右侧 AI 药丸 + ≤20字理由，仅标注不拦截
        if verdict is not None:
            keep = verdict.get("keep")
            reason = QLabel(verdict.get("reason") or "")
            reason.setStyleSheet("color:%s; font-size:9pt;" % style.MUTED)
            reason.setWordWrap(True)
            reason.setMaximumWidth(180)
            ai_fg, ai_bg = (_NEW_COLOR, _NEW_BG) if keep else (_FAIL_COLOR, _FAIL_BG)
            ai_pill = QLabel("🤖留" if keep else "🤖滤")
            ai_pill.setFixedWidth(48)
            ai_pill.setAlignment(Qt.AlignCenter)
            ai_pill.setStyleSheet(
                "color:%s; background:%s; border-radius:6px; padding:3px 0;"
                "font-weight:bold; font-size:9pt;" % (ai_fg, ai_bg))
            rl.addWidget(reason)
            rl.addWidget(ai_pill)
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
