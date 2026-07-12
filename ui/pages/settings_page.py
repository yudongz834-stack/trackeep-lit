# -*- coding: utf-8 -*-
"""设置页（Slice 1 占位）。后续 slice 放：引擎路径、Zotero 连通自检、主题等。"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from lit import config


class SettingsPage(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 22, 28, 18)
        lay.setSpacing(10)

        title = QLabel("⚙️  设置")
        title.setObjectName("pageTitle")
        lay.addWidget(title)

        info = QLabel(
            f"版本：{config.APP_NAME} v{config.VERSION}（Slice 1 · 采集预览）\n"
            f"引擎：{config.ENGINE_PATH}\n"
            f"Mecha-Core：{config.MECHA_CORE}\n\n"
            "本页为占位。后续 slice 将放置：Zotero 连通自检、引擎路径配置、"
            "采集台账锚点查看、主题等。"
        )
        info.setObjectName("muted")
        info.setWordWrap(True)
        info.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(info)
        lay.addStretch(1)
