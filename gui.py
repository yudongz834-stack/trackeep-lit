# -*- coding: utf-8 -*-
"""Trackeep Lit —— 桌面程序入口。

启动方式（开发调试）：venv\\Scripts\\python.exe gui.py
打包成品（Slice-4）：双击 exe / VBS 启动器（无黑窗）。

骨架对齐 mecha-quant/gui.py：QApplication + setStyleSheet + AppUserModelID +
MainWindow。本项目无 quant 包、无 wheel_guard，不 import 它们。
"""
import ctypes
import os
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).resolve().parent   # 打包成品：exe 所在文件夹
else:
    ROOT = Path(__file__).resolve().parent
    sys.path.insert(0, str(ROOT))   # 让 `import lit` / `import ui` 在项目根可解析

from PySide6.QtGui import QIcon  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from lit import config  # noqa: E402
from ui import style  # noqa: E402
from ui.main_window import MainWindow  # noqa: E402


def main() -> int:
    # 让 Windows 任务栏把本程序当独立应用显示（图标不和 python 混在一起）
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("TrackeepLit.App")
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setApplicationName(config.APP_NAME)
    app.setApplicationVersion(config.VERSION)
    app.setStyleSheet(style.QSS)
    ico = ROOT / "app.ico"
    if ico.exists():
        app.setWindowIcon(QIcon(str(ico)))

    win = MainWindow()
    win.show()

    # 打包/起窗自检（构建与桥探针用）：环境变量 TRACKEEP_SELFTEST=1 时 3 秒后自动退出，
    # 退出码 0 = 整个界面能正常拉起。自检模式不弹任何模态引导。
    if os.environ.get("TRACKEEP_SELFTEST") == "1":
        from PySide6.QtCore import QTimer
        QTimer.singleShot(3000, app.quit)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
