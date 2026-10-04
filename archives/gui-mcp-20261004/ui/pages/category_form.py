# -*- coding: utf-8 -*-
"""分类采集策略表单（可复用件）——按分类配 pubtype / PubMed 主题过滤 / DeepSeek 判据。

原 strategy_page.py 的表单部分提取成独立 widget：**不含左侧分类列表**（分类选择由
采集台左树驱动，外部调 `load(cat)` 切分类）。改动去抖自动存 strategy.json（原子写、
保留 version 与其它分类）。写 strategy.json、不碰 journal-overrides.json（单刊例外在
采集台「本刊例外」区）。

配色只用 ui/style.py 常量；小部件工厂对齐 harvest_page。
"""
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (QCheckBox, QFrame, QHBoxLayout, QLabel, QLineEdit,
                               QPlainTextEdit, QVBoxLayout, QWidget)

from lit import journals, strategy
from ui import style

_SAVE_DEBOUNCE_MS = 400      # 文本框频繁触发，聚一次再原子写


class CategoryPolicyForm(QWidget):
    """单分类策略表单。外部 `load(cat)` 切分类；改动去抖自动存。"""

    def __init__(self):
        super().__init__()
        self._loading = False        # 程序化载入时抑制写回
        self._current_cat = None
        self._journals = journals.load()      # 算各分类刊数（标题用）

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(_SAVE_DEBOUNCE_MS)
        self._save_timer.timeout.connect(self._flush_save)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        self.title = QLabel("")
        self.title.setObjectName("pageTitle")
        lay.addWidget(self.title)
        lay.addWidget(self._muted(
            "按分类配采集策略，改动自动存。Article / Review 是引擎恒含基底（只读展示）；"
            "单刊例外在采集台选中期刊后的「本刊例外」里配。"))
        lay.addWidget(self._build_form())
        lay.addStretch(1)

    # ---------- 表单 ----------

    def _build_form(self) -> QFrame:
        panel, ply = self._card()
        ply.setContentsMargins(20, 16, 20, 18)

        # 文献类型：Article/Review 只读基底 + Editorial/Letter 可改
        pt = QHBoxLayout()
        pt.setSpacing(12)
        pt.addWidget(self._label("文献类型", "sectionTitle"))
        for base in ("Article", "Review"):
            cb = QCheckBox(base)
            cb.setChecked(True)
            cb.setEnabled(False)
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

        div1 = QFrame(); div1.setFixedHeight(1); div1.setStyleSheet("background:%s;" % style.BORDER)
        ply.addWidget(div1)

        ply.addWidget(self._label("PubMed 主题过滤", "sectionTitle"))
        self.cb_topic = QCheckBox("启用主题过滤（PubMed 检索式层）")
        self.cb_topic.toggled.connect(self._on_topic_toggled)
        ply.addWidget(self.cb_topic)
        self.edit_topic = QLineEdit()
        self.edit_topic.setPlaceholderText("lung[tiab] OR esophag*[tiab] …")
        self.edit_topic.editingFinished.connect(self._on_field_changed)
        ply.addWidget(self.edit_topic)

        div2 = QFrame(); div2.setFixedHeight(1); div2.setStyleSheet("background:%s;" % style.BORDER)
        ply.addWidget(div2)

        ply.addWidget(self._label("DeepSeek 语义复筛", "sectionTitle"))
        self.cb_deepseek = QCheckBox("启用 DeepSeek V4 Flash 语义复筛（按标题+摘要逐篇判留/滤）")
        self.cb_deepseek.toggled.connect(self._on_deepseek_toggled)
        ply.addWidget(self.cb_deepseek)
        self.edit_deepseek = QPlainTextEdit()
        self.edit_deepseek.setFixedHeight(64)
        self.edit_deepseek.setPlaceholderText("研究主体真正聚焦肺癌/胸部肿瘤，而非泛癌顺带提及")
        self.edit_deepseek.textChanged.connect(self._on_field_changed)
        ply.addWidget(self.edit_deepseek)

        self.summary = self._muted("")
        ply.addWidget(self.summary)
        return panel

    # ---------- 载入 / 写回 ----------

    def load(self, cat: str) -> None:
        """外部（采集台左树选中分类）调：切到该分类，把策略反映到控件。"""
        if self._save_timer.isActive():       # 切走前先落盘上一分类的待写
            self._save_timer.stop()
            self._flush_save()
        self._current_cat = cat
        n = len(self._journals.get(cat, []))
        self.title.setText("🎛  %s（%d 刊）策略" % (cat, n))
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

    def flush_pending(self) -> None:
        """外部切走本表单前调，确保待写落盘（防丢）。"""
        if self._save_timer.isActive():
            self._save_timer.stop()
            self._flush_save()

    def _on_topic_toggled(self, on: bool) -> None:
        self.edit_topic.setEnabled(on)
        self._on_field_changed()

    def _on_deepseek_toggled(self, on: bool) -> None:
        self.edit_deepseek.setEnabled(on)
        self._on_field_changed()

    def _on_field_changed(self) -> None:
        if self._loading:
            return
        self._save_timer.start()

    def _flush_save(self) -> None:
        cat = self._current_cat
        if not cat:
            return
        policy = {
            "editorial": self.cb_editorial.isChecked(),
            "letter": self.cb_letter.isChecked(),
            "topicFilter": {"enabled": self.cb_topic.isChecked(),
                            "terms": self.edit_topic.text()},
            "deepseek": {"enabled": self.cb_deepseek.isChecked(),
                         "criteria": self.edit_deepseek.toPlainText()},
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
        self.summary.setText("当前分类策略：%s%s · 改动自动存 strategy.json" % (mode, extra))
        self.summary.setStyleSheet("")

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
