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
                               QRadioButton, QScrollArea, QStackedWidget, QTreeWidget,
                               QTreeWidgetItem, QVBoxLayout, QWidget)

from lit import deepseek, engine, journals, ledger, overrides, strategy, zotero
from ui import style
from ui.pages.category_form import CategoryPolicyForm
from ui.workers import run_async

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
_EX_COLOR = "#6B5B95"                # AI 过滤：雾紫（暖底上的冷点缀，区别于去重灰 / 失败红）
_EX_BG = "#ECE9F5"

# status → (前景色, 底色, 药丸文字)。_item_row 与两个回执的分组清单共用。
_STATUS_STYLE = {
    "new":      (_NEW_COLOR,  _NEW_BG,  "新增"),
    "imported": (_IMP_COLOR,  _IMP_BG,  "已导入"),
    "dup":      (_DUP_COLOR,  _DUP_BG,  "去重"),
    "suspect":  (_SUS_COLOR,  _SUS_BG,  "疑似"),
    "failed":   (_FAIL_COLOR, _FAIL_BG, "失败"),
    "excluded": (_EX_COLOR,   _EX_BG,   "已过滤"),
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


def _engine_import(params: dict, exclude_pmids=None) -> dict:
    """按 params['mode'] 分流调 engine.run_import（-Execute 真写 Zotero + 台账）。

    exclude_pmids（6b-2）：AI 判滤且未捞回的 PMID，透传引擎 -ExcludePmids 跳过、不 POST。
    """
    return engine.run_import(params["journal"], exclude_pmids=exclude_pmids,
                             **_engine_kwargs(params))


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
        self._recovered = set()       # 6b-2 捞回集合：AI 判滤但 PI 手动捞回的 PMID（导入时不排除）
        self._action_btns = []        # 当前回执里的动作按钮（导入/重试/AI复筛/捞回），_running 时整体禁用

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

        # ---------- 左：分类/期刊树（分类节点也可选→配策略；期刊叶子→操作） ----------
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setRootIsDecorated(True)
        self.tree.setIndentation(14)
        self.tree.setUniformRowHeights(True)
        self.tree.setFixedWidth(248)
        self.tree.setSelectionMode(QTreeWidget.SingleSelection)
        self.tree.itemSelectionChanged.connect(self._on_tree_changed)
        self._cat_nodes = {}          # 分类名→顶层节点（「调整本类策略」跳转用）
        for cat in journals.CATEGORIES:
            names = self._journals.get(cat, [])
            if not names:                      # 兜底回退时其它分类空 → 不建空组
                continue
            node = QTreeWidgetItem([f"{cat}（{len(names)}）"])
            f = node.font(0)
            f.setBold(True)
            node.setFont(0, f)
            node.setForeground(0, QBrush(QColor(style.MUTED)))
            node.setData(0, Qt.UserRole, ("cat", cat))       # 分类节点可选 → 配策略
            for name in names:
                leaf = QTreeWidgetItem([name])
                leaf.setData(0, Qt.UserRole, ("journal", name))
                node.addChild(leaf)
            self.tree.addTopLevelItem(node)
            node.setExpanded(True)
            self._cat_nodes[cat] = node
        root.addWidget(self.tree)

        # ---------- 右：Stacked（选期刊→操作面板 / 选分类→分类策略表单） ----------
        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)
        self.journal_panel = self._build_journal_panel()
        self.category_form = CategoryPolicyForm()
        self.stack.addWidget(self.journal_panel)
        self.stack.addWidget(self.category_form)

        self._select_journal(journals.DEFAULT_JOURNAL)   # 触发 _on_tree_changed 载首刊
        self._update_search_btn()

    # ---------- 操作面板（选期刊时显示：策略摘要 + 本刊例外 + 操作 + 审计） ----------

    def _build_journal_panel(self) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        body = QWidget()
        scroll.setWidget(body)
        lay = QVBoxLayout(body)
        lay.setContentsMargins(26, 22, 30, 18)
        lay.setSpacing(12)

        self.journal_title = QLabel("📡  采集台")
        self.journal_title.setObjectName("pageTitle")
        lay.addWidget(self.journal_title)

        # _config_panel 容器：策略摘要 + 本刊例外 + 操作卡，运行时整体冻结（视觉锁定）
        self._config_panel = QWidget()
        cfg = QVBoxLayout(self._config_panel)
        cfg.setContentsMargins(0, 0, 0, 0)
        cfg.setSpacing(12)
        cfg.addWidget(self._build_summary_and_exception())
        cfg.addWidget(self._build_operation())
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
        return scroll

    def _build_summary_and_exception(self) -> QFrame:
        """生效策略摘要条（resolve 结果）+ 「调整本类策略」跳转 + 折叠的「本刊例外」区。"""
        panel, ply = self._card()
        ply.setContentsMargins(20, 14, 20, 16)

        def chip() -> QLabel:
            lb = QLabel("")
            lb.setStyleSheet("background:#fff; border:1px solid %s; border-radius:8px;"
                             "padding:4px 10px; font-size:9.5pt;" % style.BORDER)
            return lb
        srow = QHBoxLayout()
        srow.setSpacing(8)
        self.chip_cat = chip()
        self.chip_topic = chip()
        self.chip_ai = chip()
        srow.addWidget(self.chip_cat)
        srow.addWidget(self.chip_topic)
        srow.addWidget(self.chip_ai)
        srow.addStretch(1)
        self.btn_to_cat = QPushButton("调整本类策略 ▸")
        self.btn_to_cat.setCursor(Qt.PointingHandCursor)
        self.btn_to_cat.clicked.connect(self._goto_category)
        srow.addWidget(self.btn_to_cat)
        self.btn_exc = QPushButton("本刊例外 ▾")
        self.btn_exc.setCheckable(True)
        self.btn_exc.setCursor(Qt.PointingHandCursor)
        self.btn_exc.toggled.connect(self._toggle_exception)
        srow.addWidget(self.btn_exc)
        ply.addLayout(srow)

        # 本刊例外区（默认折叠）：Editorial/Letter + 主题覆写 → 写 journal-overrides.json
        self.exc_box = QFrame()
        self.exc_box.setVisible(False)
        exl = QVBoxLayout(self.exc_box)
        exl.setContentsMargins(0, 8, 0, 0)
        exl.setSpacing(8)
        exl.addWidget(self._muted(
            "覆写本刊的类型 / 主题（留空 = 随分类默认）。仅本刊生效，写 journal-overrides.json。"))
        erow = QHBoxLayout()
        erow.setSpacing(12)
        erow.addWidget(self._muted("类型例外："))
        self.cb_editorial = QCheckBox("Editorial")
        self.cb_editorial.toggled.connect(self._on_exception_changed)
        self.cb_letter = QCheckBox("Letter")
        self.cb_letter.toggled.connect(self._on_exception_changed)
        erow.addWidget(self.cb_editorial)
        erow.addWidget(self.cb_letter)
        erow.addStretch(1)
        exl.addLayout(erow)
        trow = QHBoxLayout()
        trow.addWidget(self._muted("主题覆写："))
        self.topic_edit = QLineEdit()
        self.topic_edit.setPlaceholderText("留空 = 随分类默认；填则本刊用此检索式")
        self.topic_edit.editingFinished.connect(self._on_exception_changed)
        trow.addWidget(self.topic_edit, 1)
        exl.addLayout(trow)
        ply.addWidget(self.exc_box)
        return panel

    def _build_operation(self) -> QFrame:
        """操作卡：模式（采集最新 / 回填）+ 窗口 + 检索按钮。"""
        panel, ply = self._card()
        ply.setContentsMargins(20, 14, 20, 16)

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
            "点一下 = 后台静默跑引擎 + 去重预览（约 30–60 秒，无弹窗，dry-run）"), 1)
        ply.addLayout(arow)

        self.rb_latest.setChecked(True)   # 放 search_btn 之后：触发 _on_mode_changed 需用它
        return panel

    # ---------- 树选择 / 路由 ----------

    def current_journal(self) -> str | None:
        it = self.tree.currentItem()
        if it is None:
            return None
        role = it.data(0, Qt.UserRole)
        return role[1] if role and role[0] == "journal" else None

    def _select_journal(self, name: str) -> None:
        for i in range(self.tree.topLevelItemCount()):
            cat = self.tree.topLevelItem(i)
            for j in range(cat.childCount()):
                leaf = cat.child(j)
                role = leaf.data(0, Qt.UserRole)
                if role and role[1] == name:
                    self.tree.setCurrentItem(leaf)
                    return

    def _on_tree_changed(self) -> None:
        """树选中变化：分类节点 → 切分类策略表单；期刊叶子 → 切操作面板 + 载该刊。"""
        it = self.tree.currentItem()
        if it is None:
            return
        role = it.data(0, Qt.UserRole)
        if not role:
            return
        if role[0] == "cat":
            self.category_form.load(role[1])
            self.stack.setCurrentWidget(self.category_form)
        else:
            self.stack.setCurrentWidget(self.journal_panel)
            self._load_journal(role[1])

    def _goto_category(self) -> None:
        """「调整本类策略 ▸」：选中本刊所属分类节点（→ 切策略表单）。"""
        journal = self.current_journal()
        if not journal:
            return
        node = self._cat_nodes.get(journals.category_of(journal))
        if node is not None:
            self.tree.setCurrentItem(node)

    def _toggle_exception(self, on: bool) -> None:
        self.exc_box.setVisible(on)

    # ---------- 期刊载入 / 本刊例外写回 ----------

    def _load_journal(self, journal: str) -> None:
        """选中期刊 → 载生效策略摘要（resolve）+ 本刊例外控件（overrides）+ 采集窗口。

        _loading 抑制期间的写回，避免切刊把旧刊例外写进新刊。
        """
        self.journal_title.setText("📡  " + journal)
        res = strategy.resolve(journal)
        cat = journals.category_of(journal) or "—"
        self.chip_cat.setText("本刊按【%s】采集" % cat)
        self.chip_topic.setText("主题过滤：" + ("开" if res["topic"] else "关"))
        self.chip_ai.setText("🤖 AI 复筛：" + ("开" if res["deepseek_enabled"] else "关"))
        cfg = overrides.get(journal)
        self._loading = True
        try:
            self.cb_editorial.setChecked(cfg["includeEditorial"])
            self.cb_letter.setChecked(cfg["includeLetter"])
            self.topic_edit.setText(cfg.get("topicFilter") or "")
        finally:
            self._loading = False
        self.btn_exc.setText("本刊例外 ▾" + ("（有）" if overrides.is_exception(journal) else ""))
        self._update_window_for_current()
        self._update_search_btn()

    def _on_exception_changed(self) -> None:
        """本刊例外（Editorial/Letter/主题覆写）变更 → 写 journal-overrides + 刷新摘要。"""
        if self._loading:
            return
        journal = self.current_journal()
        if not journal:
            return
        cfg = {
            "includeEditorial": self.cb_editorial.isChecked(),
            "includeLetter": self.cb_letter.isChecked(),
            "topicFilter": self.topic_edit.text().strip() or None,
        }
        try:
            overrides.save(journal, cfg)
        except OSError as e:
            self.run_status.setText("⚠ 本刊例外写回失败：%s" % e)
            self.run_status.setVisible(True)
        self.btn_exc.setText("本刊例外 ▾" + ("（有）" if overrides.is_exception(journal) else ""))
        res = strategy.resolve(journal)
        self.chip_topic.setText("主题过滤：" + ("开" if res["topic"] else "关"))

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
        if self._running or self.current_journal() is None:
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
        # 回填模式：护栏⑭ 校验（按钮已据此禁用，这里再挡一道）
        if self.rb_back.isChecked():
            ok, _ = self._backfill_validation()
            if not ok:
                return
        self._search_journal = journal
        self._running = True
        self._update_search_btn()
        self._clear_receipt()
        # 生效配置来自 resolve（分类默认 ⊕ 本刊例外），不再读 UI 勾选
        res = strategy.resolve(journal)
        inc_ed = res["editorial"]
        inc_lt = res["letter"]
        topic = res["topic"]

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
            self._recovered = set()             # 新检索清旧捞回（判决已失效，捞回不跨检索）
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

    def _render_counts_warn(self, box, counts, groups, keys) -> None:
        """BL-07①：counts 与 items 分组实数逐键对比，任一不等 → 橙字警示（以 counts 为准）。

        统计行 chips 仍按 counts 显示（既有行为不变），警示只是把不一致挑明、不再静默谎报。
        counts 值非 int（脏回执）→ 跳过该键不比、不警示（转不了 int 视为不可比，不让对比抛异常）。
        """
        parts = []
        for key in keys:
            try:
                cv = int(counts.get(key, 0))
            except (TypeError, ValueError):
                continue
            actual = len(groups.get(key, []))
            if cv != actual:
                parts.append("%s %d≠清单 %d" % (key, cv, actual))
        if parts:
            warn = QLabel("⚠ 回执自检：counts 与清单数不一致（%s），以 counts 为准"
                          % "，".join(parts))
            warn.setStyleSheet(style.WARN_TEXT)
            warn.setWordWrap(True)
            box.addWidget(warn)

    def _render_other_group(self, box, groups, known_keys) -> None:
        """BL-07②：已知分组渲染完后，剩余分组（未知 status / 缺 status 等）合并为一张
        「❔ 其他（未识别状态）」卡，表头带总条数，逐条 _item_row（带原始 status 药丸，
        _STATUS_STYLE.get 已有默认回退样式），不静默丢。"""
        remaining = [(k, rows) for k, rows in groups.items() if k not in known_keys]
        if not remaining:
            return
        total = sum(len(rows) for _, rows in remaining)
        card, clay = self._card()
        clay.setContentsMargins(0, 0, 0, 0)
        clay.setSpacing(0)
        hdr = QLabel("❔ 其他（未识别状态）（%d 篇）" % total)
        hdr.setStyleSheet("font-weight:bold; padding:10px 14px; color:%s;" % style.TEXT)
        clay.addWidget(hdr)
        for key, rows in remaining:
            for it in rows:
                clay.addWidget(self._item_row(it, key))
        box.addWidget(card)

    def _render_receipt(self, journal: str, r: dict, params: dict | None = None) -> None:
        self._clear_receipt()
        box = self.receipt_box
        # 脏回执兜底：r 非 dict（list/None/str 等）→ 渲染一条人话错误，不抛 AttributeError
        if not isinstance(r, dict):
            err = QLabel("⚠ 引擎回执格式异常，无法渲染（期望对象，收到 %s）。"
                         % type(r).__name__)
            err.setStyleSheet(style.DANGER_TEXT)
            err.setWordWrap(True)
            box.addWidget(err)
            return

        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        badge = QLabel(
            f"  ✓ 预览完成 · {_params_window_desc(params)} · {ts} · dry-run（未写 Zotero）  ")
        badge.setStyleSheet(
            "background:%s; color:white; padding:6px 14px; border-radius:9px;"
            "font-weight:bold; font-size:10pt;" % style.ACCENT)
        box.addWidget(badge)

        # 统计行：found / new / dup / suspect
        counts = r.get("counts", {}) or {}
        # counts/分组实数对比（BL-07①②）前置：警示与其他卡都依赖 groups，stats 仍只用 counts
        items = r.get("items", []) or []
        groups: dict[str, list] = {}
        for it in items:
            groups.setdefault((it.get("status") or "?"), []).append(it)
        stats = QHBoxLayout()
        stats.setSpacing(8)
        stats.addWidget(self._stat_chip("命中", r.get("found", 0), style.TEXT))
        stats.addWidget(self._stat_chip("新增", counts.get("new", 0), _NEW_COLOR))
        stats.addWidget(self._stat_chip("去重", counts.get("dup", 0), _DUP_COLOR))
        stats.addWidget(self._stat_chip("疑似", counts.get("suspect", 0), _SUS_COLOR))
        stats.addStretch(1)
        box.addLayout(stats)

        # BL-07①：counts 与清单实数逐键对比，不一致 → 橙字警示（chips 仍显 counts，不改为清单数）
        self._render_counts_warn(box, counts, groups, ("new", "dup", "suspect"))

        # 护栏⑫：found>=retmax 上限可能截断 → 橙字告警（建议改按月回填）
        # found 非 int（脏回执）安全降级：转不了就视为不触发告警，避免 TypeError；显示仍照原值
        try:
            _found_warn = int(r.get("found", 0))
        except (TypeError, ValueError):
            _found_warn = -1
        if _found_warn >= _RETMAX_WARN:
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

        # AI 复筛判决：6b-2 真门控（AI-enabled 刊 + 已有 verdicts → 判滤的默认不导入、可捞回）；
        # 6b-1 advisory（仅标注）已是历史。ai_on 决定是否出「复筛」按钮 + 是否门控。
        ai_on = strategy.resolve(journal)["deepseek_enabled"]
        verdicts = self._ai_verdicts or {}
        gating = ai_on and bool(verdicts)   # 门控生效条件（决定捞回 UI / 导入排除）

        # 分组清单（items/groups 已于上方 counts 处算出）
        order = [("new", "🆕 新增 · 将导入"), ("dup", "♻ 去重跳过 · 已在库"),
                 ("suspect", "❓ 疑似 · 待人工")]
        for key, title in order:
            rows = groups.get(key)
            if not rows:
                continue
            card, clay = self._card()
            clay.setContentsMargins(0, 0, 0, 0)
            clay.setSpacing(0)
            # new 组表头：门控时附「将导入 X / AI 建议留 Y / 滤 Z」+ 全部捞回；否则仅判决统计
            hdr_text = f"{title}（{len(rows)} 篇）"
            on_recover = None                  # 默认不给捞回按钮（非门控 / 非 new 组）
            if key == "new" and verdicts:
                kept = sum(1 for it in rows
                           if (verdicts.get(str(it.get("pmid"))) or {}).get("keep"))
                filtered = len(rows) - kept
                recovered = sum(1 for it in rows
                                if str(it.get("pmid") or "") in self._recovered)
                if gating and filtered > 0:
                    # 门控生效：表头亮「将导入」数（keep=True + 已捞回）+ 全部捞回入口
                    hdr_text = ("🆕 新增（%d 篇 · 将导入 %d · 🤖 AI 建议留 %d / 滤 %d）"
                                % (len(rows), kept + recovered, kept, filtered))
                    on_recover = self._toggle_recover
                else:
                    hdr_text = ("🆕 新增（%d 篇 · 🤖 AI 建议留 %d / 滤 %d）"
                                % (len(rows), kept, filtered))
            hdr = QLabel(hdr_text)
            hdr.setStyleSheet(
                "font-weight:bold; padding:10px 14px; color:%s;" % style.TEXT)
            clay.addWidget(hdr)
            # 门控 + 有滤项 → 表头下放「↩ 全部捞回」+ 说明（捞回操作都进 _action_btns 随单飞禁用）
            if key == "new" and on_recover is not None:
                rrow = QHBoxLayout()
                rrow.setContentsMargins(14, 0, 14, 6)
                rec_all = QPushButton("↩ 全部捞回（%d）" % filtered)
                rec_all.setCursor(Qt.PointingHandCursor)
                rec_all.setEnabled(not self._running)
                rec_all.clicked.connect(lambda checked=False: self._recover_all())
                rrow.addWidget(rec_all)
                rrow.addWidget(self._muted(
                    "AI 判滤的篇目默认不导入；可逐条 ↩ 捞回或全部捞回。"), 1)
                clay.addLayout(rrow)
                self._action_btns.append(rec_all)
            for it in rows:
                v = verdicts.get(str(it.get("pmid"))) if key == "new" else None
                clay.addWidget(self._item_row(it, key, verdict=v, on_recover=on_recover))
            box.addWidget(card)

        # BL-07②：剩余分组（未知 status / 缺 status 等）合并渲染「其他」卡，不静默丢
        self._render_other_group(box, groups, {"new", "dup", "suspect"})

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
            if gating:
                _will, _filt, _rec = self._gate_breakdown(r)
                hint = ("真实写库（仅导入 AI 判留 %d + 已捞回 %d，滤 %d · 可逆：可移回收站）。"
                        "点击后先确认。" % (_will - _rec, _rec, _filt))
            else:
                hint = "真实写库（新增 · 去重 · 可逆：可移回收站）。点击后先确认。"
            irow.addWidget(self._muted(hint), 1)
            box.addLayout(irow)
            self._action_btns.append(imp)

        # 🤖 DeepSeek 复筛：AI-enabled 刊且有 new 才出。未跑 → 复筛按钮；已跑 → 门控说明。
        if ai_on and new_count > 0:
            arow = QHBoxLayout()
            if not verdicts:
                aibtn = QPushButton("🤖  DeepSeek 复筛（预览判决）")
                aibtn.setCursor(Qt.PointingHandCursor)
                aibtn.setEnabled(not self._running)
                aibtn.clicked.connect(self._start_ai_filter)
                arow.addWidget(aibtn)
                arow.addWidget(self._muted(
                    "按分类判据逐篇判「主体是否相关」（约 10–30 秒）。"
                    "本刊已开 AI 复筛，须先跑完才能导入（判滤的默认不导入、可捞回）。"), 1)
                self._action_btns.append(aibtn)
            else:
                note = self._muted(
                    "🤖 AI 判滤的篇目默认不导入；可在上方逐条 ↩ 捞回或全部捞回。"
                    "导入按当前判决门控。判据准不准可点上方「调整本类策略」或选左树分类节点调整。")
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

        # 页脚：collection / journal / mode（collection 非 dict 时兜 {}，走「未知」路径）
        coll = r.get("collection")
        if not isinstance(coll, dict):
            coll = {}
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
        左树分类节点的策略表单里调，本处只照判据执行。
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
            self._recovered = set()             # 新判决清旧捞回（上一轮捞回基于旧判决，失效）
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
        """导入按钮：AI 门控校验 → 算排除集 → 确认框 → 受控建 collection → run_import 线程。

        用 _last_params（检索时锁定的 journal/days/配置），不用当前 UI 态——防检索后
        切了刊/改了配置却导入错对象。_running 时直接返回（护栏⑮ 单飞）。

        6b-2 真门控（decision②）：AI-enabled 刊若没跑复筛（_ai_verdicts is None）→ 弹提醒
        + 锁死导入（return）。AI-disabled 刊不受限、照旧全导。导入时算 exclude_pmids
        （decision①：keep=False 且未捞回的 PMID）透传引擎 -ExcludePmids 跳过。
        """
        if self._running:
            return
        p = self._last_params
        if not p:
            return
        journal = p["journal"]
        # decision②：AI-enabled 刊必须先跑完复筛才解锁导入
        if strategy.resolve(journal)["deepseek_enabled"] and self._ai_verdicts is None:
            QMessageBox.information(
                self, "请先完成 AI 复筛",
                "本刊已开启 AI 复筛，请先点『🤖 DeepSeek 复筛』完成分析，再导入。")
            return
        exclude_pmids = self._compute_exclude_pmids()
        will_import, filtered, recovered = self._gate_breakdown(r)
        # 确认框文案：门控时带将导入 / 过滤 / 捞回明细，否则原 6b-1 文案
        if filtered or recovered:
            confirm = ("确认真实导入 %d 篇到 Zotero「%s」collection？\n"
                       "窗口：%s\n（AI 过滤 %d · 已捞回 %d · 可逆：可移回收站）"
                       % (will_import, journal, _params_window_desc(p),
                          filtered, recovered))
        else:
            new_count = (r.get("counts") or {}).get("new", 0)
            confirm = ("确认真实导入 %d 篇新文献到 Zotero「%s」collection？\n"
                       "窗口：%s\n（新增 · 去重 · 可逆：可移回收站）"
                       % (new_count, journal, _params_window_desc(p)))
        ans = QMessageBox.question(self, "确认真实导入", confirm)
        if ans != QMessageBox.Yes:
            return
        # 受控建 collection（护栏⑯）：检索说 collection 不存在 → 先建再导入
        coll = r.get("collection") or {}
        if not coll.get("exists"):
            if not self._ensure_collection(journal):
                return          # 用户取消建 / 分类未找到 / 建失败 → 放弃导入
        self._begin_import(p, exclude_pmids)

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

    def _compute_exclude_pmids(self) -> set:
        """门控排除集（decision①）：AI-enabled 刊 + 有 verdicts → keep=False 且未捞回的 PMID。

        空（AI-disabled / 无 verdicts）= 全导（向后兼容 6b-1）。导入时透传引擎 -ExcludePmids。
        对缺 / 畸形 pmid 的 item 安全跳过（不抛）。
        """
        p, r = self._last_params, self._last_result
        if not p or not strategy.resolve(p["journal"])["deepseek_enabled"]:
            return set()
        verdicts = self._ai_verdicts
        if not isinstance(verdicts, dict) or not verdicts:
            return set()
        exclude = set()
        for it in (r.get("items") or []):
            if it.get("status") != "new":
                continue
            pmid = str(it.get("pmid") or "")
            if not pmid:
                continue
            v = verdicts.get(pmid) or {}
            if not v.get("keep") and pmid not in self._recovered:
                exclude.add(pmid)
        return exclude

    def _gate_breakdown(self, r: dict) -> tuple[int, int, int]:
        """门控计数 (will_import, filtered, recovered) 供文案 / 头标。

        非门控（AI-disabled / 无 verdicts）→ (new_count, 0, 0)。对脏 items 安全（不抛）。
        """
        new_count = (r.get("counts") or {}).get("new", 0)
        p = self._last_params
        if not p or not strategy.resolve(p["journal"])["deepseek_enabled"]:
            return new_count, 0, 0
        verdicts = self._ai_verdicts
        if not isinstance(verdicts, dict) or not verdicts:
            return new_count, 0, 0
        filtered = recovered = 0
        for it in (r.get("items") or []):
            if it.get("status") != "new":
                continue
            pmid = str(it.get("pmid") or "")
            if not (verdicts.get(pmid) or {}).get("keep"):
                if pmid in self._recovered:
                    recovered += 1
                else:
                    filtered += 1
        return new_count - filtered, filtered, recovered

    def _toggle_recover(self, pmid: str) -> None:
        """逐条捞回 / 取消捞回：翻转 pmid 在 _recovered 中的归属，重渲 new 组门控态。"""
        if pmid in self._recovered:
            self._recovered.discard(pmid)
        else:
            self._recovered.add(pmid)
        self._rerender_last()

    def _recover_all(self) -> None:
        """全部捞回：把当前 new 组里所有 keep=False 的 PMID 塞进 _recovered，重渲。"""
        r = self._last_result
        verdicts = self._ai_verdicts or {}
        for it in (r.get("items") or []):
            if it.get("status") == "new":
                pmid = str(it.get("pmid") or "")
                if pmid and not (verdicts.get(pmid) or {}).get("keep"):
                    self._recovered.add(pmid)
        self._rerender_last()

    def _rerender_last(self) -> None:
        """用 _last_result + _last_params 重渲检索回执（捞回操作后刷新门控 UI）。"""
        r, p = self._last_result, self._last_params
        if r and p:
            self._render_receipt(p["journal"], r, p)

    def _begin_import(self, params: dict, exclude_pmids=None) -> None:
        """发起导入：禁按钮 + 进度文案 + run_async 跑 run_import；done 渲导入回执。

        exclude_pmids（6b-2）：AI 判滤且未捞回的 PMID 集合，透传引擎 -ExcludePmids 跳过。
        重试失败时重算（_ai_verdicts / _recovered 仍在场），保证重跑与首次同口径排除。
        """
        self._running = True
        self._update_search_btn()                # 禁检索按钮
        self._set_action_btns_enabled(False)     # 禁导入/重试按钮
        self._begin_running_ui("导入", "真写 Zotero，约 1–3 分钟")

        def job():
            return _engine_import(params, exclude_pmids)

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
        # 脏回执兜底：r 非 dict（list/None/str 等）→ 渲染一条人话错误，不抛 AttributeError
        if not isinstance(r, dict):
            err = QLabel("⚠ 引擎回执格式异常，无法渲染（期望对象，收到 %s）。"
                         % type(r).__name__)
            err.setStyleSheet(style.DANGER_TEXT)
            err.setWordWrap(True)
            box.addWidget(err)
            return
        counts = r.get("counts") or {}
        imported = counts.get("imported", 0) or 0
        failed = counts.get("failed", 0) or 0
        dup = counts.get("dup", 0) or 0
        excluded = counts.get("excluded", 0) or 0   # 6b-2：AI 门控过滤（不 POST、不进台账）
        # counts/分组实数对比（BL-07①②）前置
        items = r.get("items", []) or []
        groups: dict[str, list] = {}
        for it in items:
            groups.setdefault((it.get("status") or "?"), []).append(it)

        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        badge_text = f"  ✓ 已导入 {imported} · 失败 {failed} · 去重 {dup}"
        if excluded:
            badge_text += f" · AI 过滤 {excluded}"
        badge = QLabel(badge_text + f"  · {ts}  ")
        badge.setStyleSheet(
            "background:%s; color:white; padding:6px 14px; border-radius:9px;"
            "font-weight:bold; font-size:10pt;" % style.ACCENT)
        box.addWidget(badge)

        stats = QHBoxLayout()
        stats.setSpacing(8)
        stats.addWidget(self._stat_chip("已导入", imported, _IMP_COLOR))
        stats.addWidget(self._stat_chip("失败", failed, _FAIL_COLOR))
        stats.addWidget(self._stat_chip("去重", dup, _DUP_COLOR))
        if excluded:
            stats.addWidget(self._stat_chip("AI 过滤", excluded, _EX_COLOR))
        stats.addStretch(1)
        box.addLayout(stats)

        # BL-07①：counts 与清单实数逐键对比，不一致 → 橙字警示
        self._render_counts_warn(box, counts, groups,
                                 ("imported", "failed", "dup", "excluded"))

        # 分组清单（imported/excluded/failed/dup/suspect；items/groups 已于上方 counts 处算出）
        order = [("imported", "✓ 已导入"), ("excluded", "🚫 AI 已过滤 · 未导入"),
                 ("failed", "✗ 失败 · 可重试"),
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

        # BL-07②：剩余分组（未知 status / 缺 status 等）合并渲染「其他」卡，不静默丢
        self._render_other_group(box, groups,
                                 {"imported", "excluded", "failed", "dup", "suspect"})

        # 失败 > 0 → 重试按钮（再跑一次 run_import，幂等）
        if failed > 0:
            rrow = QHBoxLayout()
            retry = QPushButton("🔁  重试失败（%d）" % failed)
            retry.setObjectName("primary")
            retry.setCursor(Qt.PointingHandCursor)
            retry.setEnabled(not self._running)
            retry.clicked.connect(lambda: self._begin_import(params, self._compute_exclude_pmids()))
            rrow.addWidget(retry)
            rrow.addWidget(self._muted(
                "引擎台账只记成功、去重跳过已导入，重试只补失败项（幂等）。"), 1)
            box.addLayout(rrow)
            self._action_btns.append(retry)

        coll = r.get("collection")
        if not isinstance(coll, dict):
            coll = {}
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

    def _item_row(self, it: dict, status: str, verdict: dict | None = None,
                  on_recover=None) -> QFrame:
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
        keep = None
        if verdict is not None:
            keep = verdict.get("keep")
            tip.append("AI: %s · %s" % ("建议留" if keep else "建议滤",
                                        verdict.get("reason") or "—"))
        # 6b-2 门控态：keep=False（AI 判滤）+ 已捞回标记（_recovered），写入 tooltip
        pmid = str(it.get("pmid") or "")
        is_recovered = bool(pmid) and pmid in self._recovered
        if keep is False and is_recovered:
            tip.append("捞回：是（PI 手动捞回，将导入）")
        row.setToolTip("\n".join(tip))

        rl.addWidget(pill)
        rl.addWidget(title, 1)
        # AI 复筛判决：右侧 AI 药丸 + ≤20字理由
        if verdict is not None:
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
        # 6b-2 门控捞回：on_recover 提供回调 + keep=False 的 new 项 → 给捞回 / 已捞回按钮；
        # 未捞回的弱化（标题删除线 + 灰字，表「被剔除、未导入」）。按钮进 _action_btns 随单飞禁用。
        if on_recover is not None and keep is False and pmid:
            if not is_recovered:
                f = title.font()
                f.setStrikeOut(True)
                title.setFont(f)
                title.setStyleSheet("color:%s;" % style.MUTED)
            rec_btn = QPushButton("已捞回" if is_recovered else "↩ 捞回")
            rec_btn.setCursor(Qt.PointingHandCursor)
            rec_btn.setEnabled(not self._running)
            rec_btn.clicked.connect(lambda checked=False, p=pmid: on_recover(p))
            self._action_btns.append(rec_btn)
            rl.addWidget(rec_btn)
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
