"""仅建立本次授权的两份可追溯题录测试副本，附件操作交给Zotero原生UI。"""
import json,sys,datetime as dt,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from lit.fulltext import AttachmentLibrary
folder=ROOT/'日志/native-zotero-validation';folder.mkdir(exist_ok=True)
path=folder/'fixture.json'
if path.exists():raise SystemExit('准备记录已存在，禁止重复建测试副本')
tag='trackeep-native-test-20261003'
r={'at':dt.datetime.now(dt.timezone.utc).isoformat(),'marker':tag,'status':'started','items':[],
   'authorization':'PI指令实测原生查找全文和存储副本导入；仅两份受控副本及其附件可移回收站，禁止永久删除',
   '轨道位置':'原生能力验证','R级':'R2','判级理由':'真实文献库内受控可恢复测试副本','签发':'PI经协调会话明确要求验两条原生路径'}
def save():path.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
save();lib=AttachmentLibrary()
col=lib.post('/collections',[{'name':'临时验证-原生全文-20261003','parentCollection':False}])
r['collection_receipt']=col;save()
if set(col.get('successful',{}))!={'0'}:raise SystemExit('测试目录创建失败，保留回执')
r['collection']=col['successful']['0']['key'];save()
for source,pmid,route in [('WD9F8D8E','42420446','find-full-text'),('IU8CWQD2','42816625','stored-copy')]:
 with urllib.request.urlopen('http://127.0.0.1:23119/api/users/0/items/'+source) as resp:original=json.load(resp)
 data={k:v for k,v in original['data'].items() if k not in ('key','version','dateAdded','dateModified')}
 data['collections']=[r['collection']];data['tags']=[{'tag':tag},{'tag':'临时测试副本-'+route}];data['relations']={}
 data['extra']+='\n受控临时测试副本：'+tag+' / '+route+'；原父项 '+source+'；验收后仅此副本及子项移回收站'
 entry={'pmid':pmid,'original':source,'route':route,'input':data};r['items'].append(entry);save()
 result=lib.post('/items',[data]);entry['receipt']=result;save()
 if set(result.get('successful',{}))!={'0'}:raise SystemExit('副本创建失败，保留回执，禁止盲重试')
 entry['key']=result['successful']['0']['key'];save()
r['status']='created';save()
print(json.dumps({'collection':r['collection'],'items':[{k:i[k] for k in ('pmid','route','key')} for i in r['items']]},ensure_ascii=True))
