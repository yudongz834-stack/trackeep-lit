"""最后的本地回归与交付清单；不调用真实写库路径。"""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess

root=Path(__file__).resolve().parents[1]
python=root/'venv/Scripts/python.exe'
folder=root/'日志/fulltext-validation'
env={**os.environ,'TRACKEEP_CI':'1','TRACKEEP_SELFTEST':'1','QT_QPA_PLATFORM':'offscreen','PYTHONIOENCODING':'utf-8'}
checks=[]
for name, cmd in [('fulltext',[str(python),'tests/fulltext_test.py']),('metadata',[str(python),'tests/metadata_test.py']),('pubmed',[str(python),'tests/pubmed_test.py']),
                  ('smoke',[str(python),'tests/smoke_test.py']),('gui',[str(python),'tests/gui_test.py']),
                  ('adversarial',[str(python),'tests/adversarial_test.py']),('map',[str(python),'tools/check_map.py','--check'])]:
    result=subprocess.run(cmd,cwd=root,env=env,capture_output=True)
    path=folder/('final-'+name+'.log')
    path.write_bytes(result.stdout+result.stderr)
    checks.append({'name':name,'exit_code':result.returncode,'log':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
result={'at':dt.datetime.now(dt.timezone.utc).isoformat(),'all_pass':all(c['exit_code']==0 for c in checks),'checks':checks,
        'remote_ci':'not_run','fulltext':'created_verified_2_existing_verified_2'}
(folder/'final-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))

