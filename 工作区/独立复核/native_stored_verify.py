import json,hashlib
from pathlib import Path
import fitz
root=Path('D:/trackeep-lit');out=root/'日志/native-zotero-validation'
d=json.loads((out/'independent-stored-first.json').read_text(encoding='utf-8'))
before=json.loads((out/'independent-copies-before.json').read_text(encoding='utf-8'))
i=next(i for i in d['items'] if i['key']=='K8ZWW5TD');old=next(i for i in before['items'] if i['key']=='K8ZWW5TD')
assert len(i['children'])==len(i['files'])==1
c=i['children'][0];f=i['files'][0]
assert c['data']['parentItem']==i['key'] and c['data']['linkMode']=='imported_file'
clean=lambda x:{k:v for k,v in x['parent']['data'].items() if k not in ('version','dateModified')}
assert clean(i)==clean(old)
blob=Path(f['file']).read_bytes();sha=hashlib.sha256(blob).hexdigest()
assert sha==hashlib.sha256((root/'全文/42816625.pdf').read_bytes()).hexdigest()=='a346ec1af676aafcb59867d0e3673b8036bbeaee911206020babcab98ef88d9f'
with fitz.open(stream=blob,filetype='pdf') as doc:
 texts=[p.get_text() for p in doc];assert len(texts)==37
norm=lambda s:''.join(c for c in s.casefold() if c.isalnum())
assert norm(i['parent']['data']['title']) in norm(texts[0][:800])
r={'status':'verified','parent':i['key'],'attachment':c['key'],'linkMode':c['data']['linkMode'],'pages':len(texts),'sha256':sha,'source_unchanged':True,'parent_unchanged':True,'children':1}
(out/'independent-stored-first-verification.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(r))
