import json
from pathlib import Path
out=Path('D:/trackeep-lit/日志/native-zotero-validation')
read=lambda name:json.loads((out/name).read_text(encoding='utf-8'))
b=read('independent-protected-baseline.json');d=read('independent-stored-repeat.json')
for old in b['items']:
 now=next(i for i in d['items'] if i['key']==old['key'])
 assert now['parent']['data']==old['parent']['data']
 assert [c['key'] for c in now['children']]==[c['key'] for c in old['children']]
 assert now['files']==old['files']
scope={}
for key in ['QMZ3QGFM','K8ZWW5TD']:
 row=next(i for i in d['items'] if i['key']==key)
 assert row['parent']['data']['collections']==['75X3U7JU']
 assert {'tag':'trackeep-native-test-20261003'} in row['parent']['data']['tags']
 assert all(c['data']['parentItem']==key for c in row['children'])
 scope[key]=[c['key'] for c in row['children']]
assert set(scope['K8ZWW5TD'])=={'WH83RRD9','UICJITSE'}
row=next(i for i in d['items'] if i['key']=='K8ZWW5TD')
assert len(set(f['sha256'] for f in row['files']))==1
r={'status':'允许仅下列测试项移回收站，禁止永久删除','cleanup_scope':scope,'isolated_collection':'75X3U7JU','protected_unchanged':True,'stored_repeat_result':'原生附加文件未去重：附件由1增至2，不同key、相同SHA256','protected':{'WD9F8D8E':['XT8K8X34'],'IU8CWQD2':['JBKB7SJZ']},'limits':['清理后须独立核deleted或回收站证据，不能仅凭404判断可恢复。','Find Full Text现有附件后入口消失依据主控UI记录；未执行第二次查找，不宣称实测重跑去重。']}
(out/'independent-cleanup-scope.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(r))
