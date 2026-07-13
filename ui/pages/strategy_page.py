# -*- coding: utf-8 -*-
"""采集策略页 —— 按分类的采集策略总控（Slice 6a）。

左列 5 分类（journals.CATEGORIES），右表单随选中分类载入 / 写回该分类策略
（strategy.json）：Editorial/Letter pubtype 开关、PubMed 主题检索式（topicFilter）、
DeepSeek 语义复筛判据（deepseek；本片只存判据字符串、不执行，执行属 6b）。

- Article/Review 是引擎查询恒含基底（不可去），表单里作只读展示（勾选+禁用）。
- 切分类用 _loading 抑制写回（仿 harvest_page）；任一控件变更去抖存盘（原子写、
  保留 version 与其它分类）。写失败显提示不崩。
- 本页只写 strategy.json，绝不碰 journal-overrides.json（单刊例外仍在采集台配）。

配色只用 ui/style.py 既有常量；小部件工厂（_muted/_label/_card）对齐 harvest_page。
"""
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (QCheckBox, QFrame, QHBoxLayout, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QPlainTextEdit,
                               QScrollArea, QVBoxLayout, QWidget)

from lit import journals, strategy
from ui import style

_SAVE_DEBOUNCE_MS = 400      # 文本框 textChanged 频繁触发，聚一次再原子写


class StrategyPage(QWidget):
    def __init__(self):
        super().__init__()
        self._workers = []          # 主窗关闭时 wait（本页无后台线程，留空占位对齐其它页）
        self._loading = False        # 程序化载策略时抑制写回（切分类 setChecked/setText 不落盘）
        self._current_cat = None     # 当前选中分类（_save 用）

        self._journals = journals.load()          # {分类: [刊名,...]}，算各分类刊数

        # 去抖存盘定时器（连续编辑只聚一次写）
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(_SAVE_DEBOUNCE_MS)
        self._save_timer.timeout.connect(self._flush_save)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---------- 左：分类列表（5 分类） ----------
        self.cat_list = QListWidget()
        self.cat_list.setObjectName("catList")
        self.cat_list.setFixedWidth(248)
        for cat in journals.CATEGORIES:
            n = len(self._journals.get(cat, []))
            QListWidgetItem("%s（%d）" % (cat, n), self.cat_list)
        self.cat_list.setCurrentRow(0)
        root.addWidget(self.cat_list)

        # ---------- 右：滚动表单 ----------
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        root.addWidget(scroll, 1)
        body = QWidget()
        scroll.setWidget(body)
        lay = QVBoxLayout(body)
        lay.setContentsMargins(26, 22, 30, 18)
        lay.setSpacing(12)

        title = QLabel("🎛️  采集策略")
        title.setObjectName("pageTitle")
        lay.addWidget(title)
        lay.addWidget(self._muted(
            "按 5 大分类分别配采集策略（文献类型 / PubMed 主题过滤 / DeepSeek 语义筛判据），"
            "改动自动存 strategy.json。单刊例外仍在采集台配，此处不碰。"))

        lay.addWidget(self._build_form())
        lay.addStretch(1)

        # 首次载入：连信号 + 载第 0 分类策略
        self.cat_list.currentRowChanged.connect(self._on_cat_changed)
        self._on_cat_changed(self.cat_list.currentRow())

    # ---------- 表单 ----------

    def _build_form(self) -> QFrame:
        panel, ply = self._card()
        ply.setContentsMargins(20, 16, 20, 18)

        self.cat_title = QLabel("")
        self.cat_title.setObjectName("sectionTitle")
        ply.addWidget(self.cat_title)
        ply.addWidget(self._muted(
            "Article / Review 是引擎查询恒含的基底（不可去），此处只读展示。"
            "Editorial / Letter、主题过滤、DeepSeek 判据按分类配置。"))

        # 文献类型行：Article/Review（只读基底）+ Editorial/Letter（可改）
        pt = QHBoxLayout()
        pt.setSpacing(12)
        for base in ("Article", "Review"):
            cb = QCheckBox(base)
            cb.setChecked(True)
            cb.setEnabled(False)          # 引擎恒含基底，展示用不可改
            pt.addWidget(cb)
        sep = QFrame()
        sep.setFixedWidth(1)
        sep.setFixedHeight(20)
        sep.setStyleSheet("background:%s;" % style.BORDER)
        pt.addSpacing(2)
        pt.addWidget(sep)
        pt.addSpacing(2)
        self.cb_editorial = QCheckBox("Editorial")
        self.cb_editorial.toggled.connect(self._on_field_changed)
        self.cb_letter = QCheckBox("Letter")
        self.cb_letter.toggled.connect(self._on_field_changed)
        pt.addWidget(self.cb_editorial)
        pt.addWidget(self.cb_letter)
        pt.addStretch(1)
        ply.addLayout(pt)

        # PubMed 主题过滤行
        ply.addWidget(self._label("PubMed 主题过滤", "sectionTitle"))
        self.cb_topic = QCheckBox("启用主题过滤（PubMed 检索式层）")
        self.cb_topic.toggled.connect(self._on_topic_toggled)
        ply.addWidget(self.cb_topic)
        self.edit_topic = QLineEdit()
        self.edit_topic.setPlaceholderText("lung[tiab] OR esophag*[tiab] …")
        self.edit_topic.editingFinished.connect(self._on_field_changed)
        ply.addWidget(self.edit_topic)

        # DeepSeek 语义筛行
        ply.addWidget(self._label("DeepSeek 语义复筛", "sectionTitle"))
        self.cb_deepseek = QCheckBox("启用 DeepSeek V4 Flash 语义复筛（按标题+摘要逐篇判留/滤）")
        self.cb_deepseek.toggled.connect(self._on_deepseek_toggled)
        ply.addWidget(self.cb_deepseek)
        self.edit_deepseek = QPlainTextEdit()
        self.edit_deepseek.setFixedHeight(64)     # 2–3 行高
        self.edit_deepseek.setPlaceholderText("研究主体真正聚焦肺癌/胸部肿瘤，而非泛癌顺带提及")
        self.edit_deepseek.textChanged.connect(self._on_field_changed)
        ply.addWidget(self.edit_deepseek)

        # 小结行
        self.summary = self._muted("")
        ply.addWidget(self.summary)
        return panel

    # ---------- 分类切换 / 载入 ----------

    def _on_cat_changed(self, row: int) -> None:
        if row < 0 or row >= len(journals.CATEGORIES):
            return
        # 切分类前先把待写的旧分类落盘，防丢（控件的值还是旧分类、_current_cat 未变）
        if self._save_timer.isActive():
            self._save_timer.stop()
            self._flush_save()
        cat = journals.CATEGORIES[row]
        self._current_cat = cat
        self.cat_title.setText("%s（%d 刊）" % (cat, len(self._journals.get(cat, []))))
        self._load(cat)

    def _load(self, cat: str) -> None:
        """选中分类变化 → 读 strategy，把策略反映到控件（_loading 抑制写回）。"""
        p = strategy.get_category(cat)
        self._loading = True
        try:
            self.cb_editorial.setChecked(p["editorial"])
            self.cb_letter.setChecked(p["letter"])
            self.cb_topic.setChecked(p["topicFilter"]["enabled"])
            self.edit_topic.setText(p["topicFilter"]["terms"])
            self.edit_topic.setEnabled(p["topicFilter"]["enabled"])
            self.cb_deepseek.setChecked(p["deepseek"]["enabled"])
            self.edit_deepseek.setPlainText(p["deepseek"]["criteria"])
            self.edit_deepseek.setEnabled(p["deepseek"]["enabled"])
        finally:
            self._loading = False
        self._refresh_summary(p)

    # ---------- 写回 ----------

    def _on_topic_toggled(self, on: bool) -> None:
        self.edit_topic.setEnabled(on)
        self._on_field_changed()

    def _on_deepseek_toggled(self, on: bool) -> None:
        self.edit_deepseek.setEnabled(on)
        self._on_field_changed()

    def _on_field_changed(self) -> None:
        """任一控件变更 → 去抖存盘（_loading 期间不触发）。"""
        if self._loading:
            return
        self._save_timer.start()       # 重启计时器：连续编辑只聚一次

    def _flush_save(self) -> None:
        cat = self._current_cat
        if not cat:
            return
        policy = {
            "editorial": self.cb_editorial.isChecked(),
            "letter": self.cb_letter.isChecked(),
            "topicFilter": {
                "enabled": self.cb_topic.isChecked(),
                "terms": self.edit_topic.text(),
            },
            "deepseek": {
                "enabled": self.cb_deepseek.isChecked(),
                "criteria": self.edit_deepseek.toPlainText(),
            },
        }
        try:
            strategy.save_category(cat, policy)
        except OSError as e:
            self.summary.setText("⚠ 策略写回失败：%s" % e)
            self.summary.setStyleSheet(style.DANGER_TEXT)
            return
        self._refresh_summary(policy)

    def _refresh_summary(self, p: dict) -> None:
        ai = p["deepseek"]["enabled"]
        topic = p["topicFilter"]["enabled"] and bool(p["topicFilter"]["terms"].strip())
        if ai:
            mode = "主题过滤 + DeepSeek 复筛"
        elif topic:
            mode = "PubMed 主题过滤"
        else:
            mode = "全收（Article/Review 基底 + Editorial/Letter 开关）"
        ed = []
        if p["editorial"]:
            ed.append("Editorial")
        if p["letter"]:
            ed.append("Letter")
        extra = ("（含 " + " / ".join(ed) + "）") if ed else ""
        self.summary.setText("当前分类策略：%s%s" % (mode, extra))
        self.summary.setStyleSheet("")    # 清掉可能的错误红字样式

    # ---------- 小部件工厂（对齐 harvest_page） ----------

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
