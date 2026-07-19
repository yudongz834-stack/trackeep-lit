# -*- coding: utf-8 -*-
"""Trackeep Lit 配置常量（路径 / 版本 / 引擎入口）。"""
import sys
from pathlib import Path

APP_NAME = "Trackeep Lit"
VERSION = "0.4.0"  # v0.4 AI 复筛期刊级控制 + 默认全开（每刊三态覆写+自定义判据，resolve 单刊>分类>默认）

# 打包成品（PyInstaller frozen）= exe 所在文件夹；开发态 = 项目根（lit/ 的上两级）。
# 与 gui.py 的 ROOT 同源，使 ui.main_window.ICON_PATH 在两种态下都指向 app.ico。
if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).resolve().parent
else:
    ROOT = Path(__file__).resolve().parent.parent
ENGINE_PATH = Path(r"D:\BaiduSyncdisk\Mecha-Core\scripts\zotero-import.ps1")
MECHA_CORE = Path(r"D:\BaiduSyncdisk\Mecha-Core")
