"""供既有 GUI 环境调用公共工具棚的 PDF 解析器，不另装依赖。"""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lit.fulltext import LIMIT, verify_pdf

if __name__ == '__main__':
    try:
        result = verify_pdf(sys.stdin.buffer.read(LIMIT + 1), json.loads(sys.argv[1]))
        sys.stdout.buffer.write(json.dumps(result).encode('utf-8'))
    except Exception:
        raise SystemExit(2)
