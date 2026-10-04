"""本机插件入口：调用现存项目，不复制业务。"""
from pathlib import Path
import sys
ROOT = Path('D:/trackeep-lit')
sys.path.insert(0, str(ROOT))
from lit.mcp_server import main
if __name__ == '__main__':
    main()
