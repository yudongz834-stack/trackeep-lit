# -*- coding: utf-8 -*-
"""Trackeep Lit 配置常量（路径 / 版本 / 引擎入口）。"""
import sys
from pathlib import Path

APP_NAME = "Trackeep Lit"
VERSION = "0.5.0"  # 双入口共用流程的本地候选版本；不代表已正式发布。

# 打包成品（PyInstaller frozen）= exe 所在文件夹；开发态 = 项目根（lit/ 的上两级）。
# 与 gui.py 的 ROOT 同源，使 ui.main_window.ICON_PATH 在两种态下都指向 app.ico。
if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).resolve().parent
else:
    ROOT = Path(__file__).resolve().parent.parent
ENGINE_PATH = Path(r"D:\trackeep-lit\zotero\import.ps1")
# 历史别名（原名 MECHA_CORE，2026-10-03 批B 除名改名）；指向仓库根，.trackeep 三 json 的落点。
LEGACY_ROOT = ROOT
STATE_DIR = ROOT / ".trackeep"
