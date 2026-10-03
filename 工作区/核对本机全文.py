"""只读核对本批本机题录、附件关联与已同步文件，不触发同步或改库。"""
import datetime as dt
import hashlib
import json
from pathlib import Path
import sys
import urllib.request
from urllib.parse import urlparse, unquote

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from lit.fulltext import verify_pdf, norm

def get(path, text=False):
    with urllib.request.urlopen('http://127.0.0.1:23119/api/users/0'+path,timeout=15) as r:
        raw=r.read().decode('utf-8')
    return raw.strip() if text else json.loads(raw)

downloads=json.loads((ROOT/'日志/fulltext-validation/official-downloads.json').read_text(encoding='utf-8'))
result={'at':dt.datetime.now(dt.timezone.utc).isoformat(),'mode':'local_read_only','items':[]}
for pmid,parent,key in [('42420446','WD9F8D8E','XT8K8X34'),('42816625','IU8CWQD2','JBKB7SJZ')]:
    item={'pmid':pmid,'parent':parent,'attachment':key};result['items'].append(item)
    try:
        source=next(d for d in downloads if d['pmid']==pmid)
        p=get('/items/'+parent);a=get('/items/'+key);children=get('/items/'+parent+'/children')
        if a['data']['parentItem']!=parent or a['data']['contentType']!='application/pdf':raise ValueError('附件身份错误')
        if a['data'].get('deleted') or p['data'].get('deleted'):raise ValueError('条目已删除')
        if p['data']['DOI'].lower()!=source['doi'].lower() or norm(p['data']['title'])!=norm(source['title']):raise ValueError('父项身份错误')
        if ('PMID: '+pmid) not in p['data'].get('extra','').splitlines():raise ValueError('父项PMID错误')
        if not any(c['key']==key for c in children):raise ValueError('子项列表缺附件')
        item.update(metadata_synced=True,parent_snapshot=p,attachment_snapshot=a)
        url=get('/items/'+key+'/file/view/url',text=True)
        parsed=urlparse(url)
        if parsed.scheme!='file' or parsed.netloc:raise ValueError('不是本机文件路径')
        path=Path(unquote(parsed.path).lstrip('/'))
        item.update(file=str(path),file_exists=path.is_file())
        blob=path.read_bytes();info=verify_pdf(blob,source)
        if info['sha256']!=source['sha256']:raise ValueError('本机文件哈希不同')
        item.update(status='local_verified',file=str(path),pdf=info,parent_snapshot=p,attachment_snapshot=a)
    except Exception as e:item.update(status='failed',reason=type(e).__name__+': '+str(e))
result['all_pass']=all(i['status']=='local_verified' for i in result['items'])
out=ROOT/'日志/fulltext-validation/desktop-verification.json'
out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'all_pass':result['all_pass'],'items':[{k:v for k,v in i.items() if k not in ('parent_snapshot','attachment_snapshot')} for i in result['items']]},ensure_ascii=True))
raise SystemExit(0 if result['all_pass'] else 1)
