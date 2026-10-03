"""本批两篇的只读接口、现有附件和官方 PDF 探测。"""
import json, sys, urllib.request, urllib.error, hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lit.library import Library
ROOT=Path(__file__).resolve().parents[1]
folder=ROOT/'日志/fulltext-validation'; folder.mkdir(parents=True,exist_ok=True)
files=ROOT/'全文'; files.mkdir(exist_ok=True)
out={'sources':[],'local':{},'parents':[]}
for path in ('/api/','/api/users/0/items/WD9F8D8E','/api/users/0/items/IU8CWQD2'):
    try:
        with urllib.request.urlopen('http://127.0.0.1:23119'+path,timeout=10) as r:
            raw=r.read(); out['local'][path]={'status':r.status,'version':r.headers.get('Zotero-Version'),'body':json.loads(raw)}
    except Exception as e: out['local'][path]={'error':type(e).__name__}
lib=Library()
for pmid,key,doi in [('42420446','WD9F8D8E','10.1038/s41586-026-10737-8'),('42816625','IU8CWQD2','10.1038/s41586-026-11077-3')]:
    parent=lib.get('/items/'+key); children=lib.all('/items/'+key+'/children')
    out['parents'].append({'pmid':pmid,'parent':parent,'children':children})
    url='https://www.nature.com/articles/'+doi.split('/')[1]+'.pdf'
    entry={'pmid':pmid,'url':url};out['sources'].append(entry)
    try:
        with urllib.request.urlopen(url,timeout=90) as r:
            blob=r.read(50*1024*1024); entry.update(http=r.status,content_type=r.headers.get('Content-Type'),final_url=r.url,bytes=len(blob),pdf_magic=blob.startswith(b'%PDF-'))
        if blob.startswith(b'%PDF-'):
            p=files/(pmid+'.pdf');p.write_bytes(blob);entry.update(path=str(p),sha256=hashlib.sha256(blob).hexdigest())
    except urllib.error.HTTPError as e: entry['http']=e.code
    except Exception as e:entry['error']=type(e).__name__
    (folder/'source-probe.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'sources':out['sources'],'children':[len(x['children']) for x in out['parents']]},ensure_ascii=False))
