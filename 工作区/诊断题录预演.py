"""只读预演故障归类；不打印或保存原始异常、请求头。"""
from pathlib import Path
import json
import re
import subprocess
root=Path(__file__).resolve().parents[1]
engine=Path(r'D:\dev\trackeep-scripts\zotero-import.ps1')
cmd=[r'C:\Program Files\PowerShell\7\pwsh.exe','-NoProfile','-File',str(engine),'-Journal','Nature',
     '-ArticlePmids','42420446,42816625','-CollectionKey','V98QAD78','-StateDir',str(root),
     '-ExpectedRecordsPath',str(root/'日志/metadata-batches/20261003-145208-a76b30d3/expected.json'),'-EmitJson']
r=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=600,creationflags=subprocess.CREATE_NO_WINDOW)
plain=re.sub(r'\x1b\[[0-9;]*m','',r.stderr)
known=re.findall(r"throw '([^']+)'",engine.read_text(encoding='utf-8-sig'))
report={'execute':False,'exit_code':r.returncode,'known_failures':[s for s in known if s in plain],
        'http_codes':re.findall(r'\b(?:400|401|403|404|409|412|429|500|502|503|504)\b',plain),
        'line_numbers':re.findall(r'Line\s*\|\s*(\d+)',plain),
        'timeout':bool(re.search(r'timed out|timeout|超时',plain,re.I)),
        'network':bool(re.search(r'connection|resolve|连接|网络|SSL|TLS',plain,re.I))}
(root/'日志/metadata-validation/live-dryrun-diagnosis.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False))
