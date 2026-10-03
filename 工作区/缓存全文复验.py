"""只复验已留证的官方PDF并经真实MCP继续原生流程，不重新请求来源。"""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lit.native_fulltext import verify_pdf

run_id = '20261003-163749-8a270bffc79e'
run = json.loads((ROOT / '日志/workflow-runs' / run_id / 'run.json').read_text(encoding='utf-8'))
record = json.loads((ROOT / '日志/unified-live-validation/science-official-file.json').read_text(encoding='utf-8'))
fallback = record['fallback']
check = verify_pdf(Path(fallback['path']).read_bytes(), run['metadata']['articles'][0])
assert check['sha256'] == record['pdf']['sha256'] == fallback['sha256']
assert check['md5'] == record['pdf']['md5']
print('缓存复验：已留证PDF哈希及身份相同，不重新请求官方来源。', flush=True)
result = subprocess.run([sys.executable, '-B', str(ROOT / '工作区/验证统一MCP.py'), 'fulltext',
    json.dumps({'run_id':run_id,'apply':True,'fallbacks':{'35357919':fallback}})], cwd=ROOT)
raise SystemExit(result.returncode)
