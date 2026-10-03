import json,re,hashlib
from pathlib import Path
import fitz
out=Path('D:/trackeep-lit/日志/native-zotero-validation')
d=json.loads((out/'independent-find-first.json').read_text(encoding='utf-8'))
i=next(i for i in d['items'] if i['key']=='QMZ3QGFM');assert len(i['children'])==len(i['files'])==1
c=i['children'][0];f=i['files'][0];assert c['data']['parentItem']==i['key']
assert c['data']['url']=='https://www.nature.com/articles/s41586-026-10737-8.pdf'
blob=Path(f['file']).read_bytes()
with fitz.open(stream=blob,filetype='pdf') as doc:texts=[p.get_text() for p in doc]
norm=lambda s:''.join(c for c in s.casefold() if c.isalnum())
assert norm(i['parent']['data']['title']) in norm(texts[0][:800])
assert i['parent']['data']['DOI'].lower() in re.findall(r'10\.\d{4,9}/[-._;()/:a-z0-9]+',texts[0].lower())
assert len(texts)==37 and sum(map(len,texts))>8000
assert next(x for x in d['items'] if x['key']=='K8ZWW5TD')['children']==[]
r={'status':'verified','parent':i['key'],'attachment':c['key'],'source':c['data']['url'],'linkMode':c['data']['linkMode'],'pages':len(texts),'characters':sum(map(len,texts)),'sha256':hashlib.sha256(blob).hexdigest(),'title_doi_identity':True,'other_copy_children':0}
(out/'independent-find-first-verification.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(r))
