"""限定本地只读终验；云端依据执行回执，不读取凭证。"""
import json,urllib.request,hashlib,datetime
from pathlib import Path
root=Path('D:/trackeep-lit');out=root/'日志/native-zotero-validation'
read=lambda f:json.loads((out/f).read_text(encoding='utf-8'))
scope={'YAW2DYA9','QMZ3QGFM','UICJITSE','WH83RRD9','K8ZWW5TD'}
cleanup=read('cleanup.json');assert set(cleanup['exact_keys'])==scope
assert len(cleanup['results'])==5 and {x['key'] for x in cleanup['results']}==scope and all(x['deleted']==1 for x in cleanup['results'])
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*a,**kw):raise RuntimeError('redirect forbidden')
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
def get(s):
 with opener.open(urllib.request.Request('http://127.0.0.1:23119/api/users/16621589/'+s,headers={'Zotero-API-Version':'3'},method='GET'),timeout=20) as r:return json.load(r)
rows=[]
for key in sorted(scope):
 a=get('items/'+key+'?includeTrashed=1');assert a['key']==key and a['data'].get('deleted')==1
 rows.append({'key':key,'deleted':1,'parentItem':a['data'].get('parentItem')})
collection=get('collections/75X3U7JU');remaining=get('collections/75X3U7JU/items')
assert collection['key']=='75X3U7JU' and remaining==[]
b=read('independent-protected-baseline.json');a=read('independent-after-cleanup.json')
for old in b['items']:
 now=next(i for i in a['items'] if i['key']==old['key'])
 assert now['parent']['data']==old['parent']['data'] and now['files']==old['files']
 assert [c['key'] for c in now['children']]==[c['key'] for c in old['children']]
guard=read('guarded-repeat.json');assert len(guard)==2 and all(i['before']==i['after'] and i['new_attachment']==0 for i in guard)
report={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'verdict':'本次原生验证与限定可逆清理通过','counts':{'test_parents':2,'native_find_attachments':1,'stored_copy_first':1,'stored_copy_repeat_new':1,'guarded_repeat_new':0,'trashed_test_objects':5,'protected_objects_changed':0},'local_trash':rows,'empty_collection_retained':'75X3U7JU','cloud_trash_evidence':'cleanup.json逐项GET读回deleted=1；独立复核未访问云端','script_review':{'scope_exact':True,'method':'PATCH deleted=1','permanent_delete':False,'version_precondition':True,'credential_read_by_reviewer':False,'limits':'一次性限定脚本使用assert，不能视为可在python -O下运行的通用产品入口；此次正常执行且本地结果独立核验。'},'find_repeat_limit':'已附PDF后菜单入口消失是主控GUI观察；未实际第二次下载，不等同查找全文算法去重证明。','stored_repeat_conclusion':'原生附加文件无此次场景去重；不同附件键、相同文件哈希。先查已有附件的脚本跳过操作是另一个结果。','limits':['未永久删除；五项本地deleted=1且云端执行回执一致。','WebDAV远端文件同步未验证。','原两篇父项资料、附件键和文件哈希与基线相同。'],'evidence_sha256':{f:hashlib.sha256((out/f).read_bytes()).hexdigest() for f in ['cleanup.json','guarded-repeat.json','independent-after-cleanup.json','independent-stored-repeat.json']}}
(out/'independent-final-acceptance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'verdict':report['verdict'],'counts':report['counts']}))
