"""无窗启动已有桌面程序，等待并透传退出码。"""
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parent
sys.exit(subprocess.run([str(root / 'venv/Scripts/pythonw.exe'), str(root / 'gui.py')],
                       cwd=root, creationflags=subprocess.CREATE_NO_WINDOW).returncode)
