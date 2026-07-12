# -*- coding: utf-8 -*-
"""使用说明页（Slice 1）。"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class HelpPage(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 22, 28, 18)
        lay.setSpacing(12)

        title = QLabel("📖  使用说明")
        title.setObjectName("pageTitle")
        lay.addWidget(title)

        body = QLabel(
            "采集台 · 四步\n"
            "① 左侧期刊树选一本刊（Slice 1 仅胸部肿瘤与胸外科 10 本）\n"
            "② 检索配置：勾选文献类型（Article/Review/Editorial/Letter）+「仅要有摘要」"
            "——至少勾一个类型才能检索\n"
            "③ 点「检索」（采集最新 · 近 60 天 · PubMed edat）\n"
            "④ 审计页看命中/新增/去重/疑似，逐条标题与判重依据\n\n"
            "说明\n"
            "· Slice 1 是 dry-run 预览：spawn zotero-import.ps1 -EmitJson，"
            "拉 PubMed + 遍历 Zotero 全库去重，不写 Zotero、不动台账。\n"
            "· 一次检索约 30–60 秒，在后台线程跑、不卡界面；运行中按钮禁用。\n"
            "· 判重顺序：DOI › PMID › 归一标题（命中库 + 台账）。\n"
            "· 真实导入（-Execute）、回填历史、全 74 刊载入、配置写回 journal-overrides.json"
            " 属后续 slice。"
        )
        body.setObjectName("muted")
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(body)
        lay.addStretch(1)
