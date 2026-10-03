"""仅本次已授权测试项：先只读验证并跳过重复附加，再逐项移回收站。"""
import json, sys, urllib.request, datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from lit.library import Library, NoRedirect
from lit.fulltext import verify_pdf
OUT=ROOT/'日志/native-zotero-validation'
scope={'QMZ3QGFM':['YAW2DYA9'],'K8ZWW5TD':['UICJITSE','WH83RRD9']}
def local(path):
 with urllib.request.urlopen('http://127.0.0.1:23119/api/users/0/items/'+path,timeout=20) as r:return json.load(r)
receipt=OUT/'cleanup.json'
if receipt.exists():raise SystemExit('已有清理记录，禁止盲重跑')
guard=[]
for parent,expected in scope.items():
 p=local(parent);children=local(parent+'/children')
 assert set(c['key'] for c in children)==set(expected)
 checks=[]
 for c in children:
  assert c['data']['parentItem']==parent
  url=c['links']['enclosure']['href'];assert url.startswith('file:///')
  path=Path(urllib.request.url2pathname(url[7:]));assert path.parent.name==c['key']
  checks.append(verify_pdf(path.read_bytes(),{'title':p['data']['title'],'doi':p['data']['DOI']}))
 guard.append({'parent':parent,'decision':'已有通过标题、DOI和文件解析验证的PDF，跳过附加','before':len(children),'after':len(local(parent+'/children')),'new_attachment':0,'verified_files':checks})
(OUT/'guarded-repeat.json').write_text(json.dumps(guard,ensure_ascii=False,indent=2),encoding='utf-8')
lib=Library();planned=[]
for parent,children in scope.items():
 p=lib.get('/items/'+parent)
 assert p['data']['collections']==['75X3U7JU'] and {'tag':'trackeep-native-test-20261003'} in p['data']['tags']
 actual=lib.all('/items/'+parent+'/children');assert set(c['key'] for c in actual)==set(children)
 for c in actual:
  assert c['data']['parentItem']==parent and c['data']['itemType']=='attachment'
  planned.append(c)
 planned.append(p)
record={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'action':'PATCH deleted=1；禁止永久删除','exact_keys':[i['key'] for i in planned],'results':[],'collection':'保留空测试目录75X3U7JU'}
def save():receipt.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
save()
for row in planned:
 key=row['key'];now=lib.get('/items/'+key)
 # 删除子项可能推进父版本，因此每项重新读取版本；对象范围已完整校验。
 assert now['data'].get('parentItem')==row['data'].get('parentItem')
 if not now['data'].get('deleted'):
  req=urllib.request.Request(lib.base+'/items/'+key,data=b'{"deleted":1}',headers={**lib.headers,'Content-Type':'application/json','If-Unmodified-Since-Version':str(now['version'])},method='PATCH')
  try:
   with urllib.request.build_opener(NoRedirect).open(req,timeout=90) as r:assert r.status==204
  except Exception:raise RuntimeError('清理请求状态待核，保留回执，不盲重发') from None
 after=lib.get('/items/'+key);assert after['data'].get('deleted')==1
 record['results'].append({'key':key,'deleted':1});save()
print(json.dumps({'guarded_new':0,'trashed':record['results']},ensure_ascii=False))
