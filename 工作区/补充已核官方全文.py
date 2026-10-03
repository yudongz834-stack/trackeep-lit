"""复用已成功核实的官方地址；新取原文件留证，不重打限流的身份转换接口。"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lit.native_fulltext import official_read, verify_pdf
from lit.fulltext import norm
from lit.library import doi

run_id = '20261003-163749-8a270bffc79e'
run = json.loads((ROOT / '日志/workflow-runs' / run_id / 'run.json').read_text(encoding='utf-8'))
article = run['metadata']['articles'][0]
assert article['pmid'] == '35357919' and article['pmc'] == 'PMC9186530'
previous = ROOT / '日志/unified-live-validation/20261003-170318-692440-fulltext.json'
response = json.loads(json.loads(previous.read_text(encoding='utf-8'))['responses'][-1]['result']['content'][0]['text'])
assert any(e.get('stage') == 'official_pdf_download' and e.get('http_status') == 200
    and e.get('path') == '/PMC9186530.1/PMC9186530.1.pdf' for e in response['data']['fulltext']['items'][0]['events'])
source = 'https://pmc-oa-opendata.s3.amazonaws.com/PMC9186530.1/PMC9186530.1.pdf?md5=c43483771ec5e878f500c7078a115d9e'
path = ROOT / '全文/原生补充/35357919-b2d13d10041d4873.pdf'
record_path = ROOT / '日志/unified-live-validation/science-official-file.json'
assert not path.exists() and not record_path.exists(), '已有文件时应复验缓存，禁止重新下载'
events = []
meta = json.loads(official_read(source.split('.pdf?')[0] + '.json', 1024*1024, 'known_pmc_metadata', events))
assert str(meta['pmid']) == article['pmid'] and doi(meta['doi']) == doi(article['doi'])
assert norm(meta['title']) == norm(article['title']) and not meta.get('is_retracted')
assert meta['pdf_url'].replace('s3://pmc-oa-opendata/', 'https://pmc-oa-opendata.s3.amazonaws.com/') == source
blob = official_read(source, stage='known_official_pdf_download', events=events)
check = verify_pdf(blob, article)
assert check['md5'] == 'c43483771ec5e878f500c7078a115d9e'
assert check['sha256'] == 'b2d13d10041d4873479388f69e577b266bf2b31c1daf807bef5dfde6937046ff'
path.parent.mkdir(parents=True, exist_ok=True)
with path.open('xb') as stream:
    stream.write(blob)
fallback = {'path': str(path), 'source': source, 'sha256': check['sha256'], 'publisher_metadata': meta}
record_path.write_text(json.dumps({'mode':'新下载已核地址；不是缓存复验', 'mapping_evidence': str(previous),
    'events':events, 'pdf':check, 'fallback':fallback}, ensure_ascii=False, indent=2), encoding='utf-8')
result = subprocess.run([sys.executable, '-B', str(ROOT / '工作区/验证统一MCP.py'), 'fulltext',
    json.dumps({'run_id':run_id,'apply':True,'fallbacks':{'35357919':fallback}})], cwd=ROOT)
raise SystemExit(result.returncode)
