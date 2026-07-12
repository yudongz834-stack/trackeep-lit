# -*- coding: utf-8 -*-
"""主窗口：左侧导航 + 右侧页面堆叠，桌面软件的骨架（对齐 mecha-quant）。"""
from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QHBoxLayout, QListWidget, QListWidgetItem,
                               QMainWindow, QStackedWidget, QWidget)

from lit import config
from ui.pages.harvest_page import HarvestPage
from ui.pages.help_page import HelpPage
from ui.pages.settings_page import SettingsPage

ICON_PATH = config.ROOT / "app.ico"   # 开发=项目根；打包成品=exe 旁边

# 页面导航单一真相源：短名 → 导航标签（含图标）。增删页面 / 改顺序只动这里。
_PAGES = [
    ("采集台", "📡  采集台"),
    ("设置", "⚙️  设置"),
    ("使用说明", "📖  使用说明"),
]
PAGE_NAMES = [name for name, _ in _PAGES]


def page_index(name: str) -> int:
    return PAGE_NAMES.index(name)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{config.APP_NAME} v{config.VERSION}")
        if ICON_PATH.exists():
            self.setWindowIcon(QIcon(str(ICON_PATH)))
        self.resize(1280, 840)
        self.setMinimumSize(1040, 680)

        self._workers = []   # 主窗自身的后台线程引用（防回收）；各页也有自己的 _workers

        central = QWidget()
        lay = QHBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.setCentralWidget(central)

        # 左侧导航
        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        self.nav.setFixedWidth(168)
        self.nav.setIconSize(QSize(20, 20))
        for _, label in _PAGES:
            QListWidgetItem(label, self.nav)

        # 右侧页面（顺序与 _PAGES 一一对应）
        self.stack = QStackedWidget()
        self.pages = [
            HarvestPage(),
            SettingsPage(),
            HelpPage(),
        ]
        for p in self.pages:
            self.stack.addWidget(p)

        lay.addWidget(self.nav)
        lay.addWidget(self.stack, 1)

        self.nav.currentRowChanged.connect(self._switch)
        self.nav.setCurrentRow(page_index("采集台"))

    def _switch(self, row: int) -> None:
        self.stack.setCurrentIndex(row)

    def closeEvent(self, event) -> None:
        """关窗前给后台线程（检索）几秒收尾，避免退出报错。"""
        for w in list(getattr(self, "_workers", [])):
            w.wait(5000)
        for page in self.pages:
            for w in list(getattr(page, "_workers", [])):
                w.wait(5000)
        super().closeEvent(event)
