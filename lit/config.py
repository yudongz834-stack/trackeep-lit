# -*- coding: utf-8 -*-
"""Trackeep Lit 配置常量（路径 / 版本 / 引擎入口）。"""
import sys
from pathlib import Path

APP_NAME = "Trackeep Lit"
VERSION = "0.4.2"  # v0.4.2 结果页极简重排（存入 Zotero 按钮上移 + 🤖→✦ 火花 + 去重/检索式折叠；纯视觉，逻辑零改动）

# 打包成品（PyInstaller frozen）= exe 所在文件夹；开发态 = 项目根（lit/ 的上两级）。
# 与 gui.py 的 ROOT 同源，使 ui.main_window.ICON_PATH 在两种态下都指向 app.ico。
if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).resolve().parent
else:
    ROOT = Path(__file__).resolve().parent.parent
ENGINE_PATH = Path(r"D:\BaiduSyncdisk\Mecha-Core\scripts\zotero-import.ps1")
MECHA_CORE = Path(r"D:\BaiduSyncdisk\Mecha-Core")
