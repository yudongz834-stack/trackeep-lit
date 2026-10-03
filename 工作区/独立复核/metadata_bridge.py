"""桥接离线独立反例；禁止网络、凭证读取、真实子进程。"""
import sys,json,copy,tempfile,hashlib,datetime,socket,subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.dont_write_bytecode=True;sys.path.insert(0,r'D:/trackeep-lit')
from lit import metadata_batch as m,zotero
A={'pmid':'101','doi':'10.1/a','title':'Title A','nlm_id':'0404511','abstract':'test','journal':'Science'}
def report():return {'schema':'trackeep-literature/pubmed-preview@1','status':'retrieval_verified','retrieval_complete':True,'read_only':True,'pmids':['101'],'articles':[copy.deepcopy(A)],'counts':{'unique_pmids':1,'metadata':1},'plan':{'journal':'Science','screening_location':'after-import'}}
def receipt(apply):return {'schema':'trackeep-lit/import-result@1','executed':apply,'collection':{'key':'COLL0001'},'items':[{'pmid':'101','doi':'10.1/a','title':'Title A','status':'imported' if apply else 'new','zoteroKey':'NEW00001' if apply else ''}]}
def row(**extra):
 d={'itemType':'journalArticle','extra':'PMID: 101\nNLM ID: 0404511','DOI':'10.1/a','title':'Title A','collections':['COLL0001'],'tags':[{'tag':'existing'}]};d.update(extra);return {'key':'OLD00001','data':d}
def blocked(*a,**k):raise AssertionError('offline boundary')
results=[]
with patch('urllib.request.urlopen',side_effect=blocked),patch('urllib.request.OpenerDirector.open',side_effect=blocked),patch('socket.socket.connect',side_effect=blocked),patch.object(zotero,'_load_env',side_effect=blocked),patch('subprocess.run',side_effect=blocked):
 for name in ['new','missing_collection','duplicate_collection','existing','existing_conflict','trashed','outside','readback_wrong','readback_wrong_nlm','engine_timeout','source_fresh_drift','existing_duplicate','post_partial']:
  with tempfile.TemporaryDirectory() as td:
   folder=Path(td);src=folder/'preview.json';src.write_text(json.dumps(report()),encoding='utf-8');live=[];calls=[]
   if name in ['existing','trashed','outside','existing_conflict','existing_duplicate']:
    live=[row()]
    if name=='trashed':live[0]['data']['deleted']=1
    if name=='outside':live[0]['data']['collections']=[]
    if name=='existing_conflict':live[0]['data']['DOI']='10.1/conflict'
    if name=='existing_duplicate':live.append(dict(row(),key='OLD00002'))
   before=copy.deepcopy(live)
   class FakeLibrary:
    def all(self,path):
     calls.append(('GET',path))
     if path!='/collections':return live
     if name=='missing_collection':return []
     cols=[{'key':'COLL0001','data':{'name':'Science'}}]
     return cols*2 if name=='duplicate_collection' else cols
    def get(self,path):
     calls.append(('GET',path));r=row();r['key']='NEW00001'
     if name=='readback_wrong':r['data']['title']='WRONG'
     if name=='readback_wrong_nlm':r['data']['extra']='PMID: 101\nNLM ID: WRONG'
     return r
   def fake_engine(articles,journal,collection,pin,apply):
    calls.append(('ENGINE',apply))
    if name=='engine_timeout' and apply:raise subprocess.TimeoutExpired('synthetic',1)
    r=receipt(apply)
    if name=='post_partial' and apply:r['items'][0]['status']='failed'
    return r
   fresh=copy.deepcopy(A)
   if name=='source_fresh_drift':fresh['doi']='10.1/changed'
   with patch.object(m,'Library',FakeLibrary),patch.object(m.pubmed,'metadata',return_value=[fresh]),patch.object(m,'engine_call',side_effect=fake_engine):out=m.run(SimpleNamespace(apply=True,preview=src,pmids='101'),folder)
   assert live==before
   results.append({'case':name,'status':out['status'],'items':[{k:i.get(k) for k in ['metadata_status','created_key']} for i in out['items']],'calls':calls,'existing_unchanged':live==before,'fulltext_status':out['fulltext_status']})
 # Test real engine_call parser with synthetic subprocess output.
 for name in ['wrong_schema','wrong_collection','duplicate_receipts','wrong_pmid','bad_key','valid']:
  r=receipt(True)
  if name=='wrong_schema':r['schema']='wrong'
  if name=='wrong_collection':r['collection']['key']='WRONG001'
  if name=='wrong_pmid':r['items'][0]['pmid']='999'
  if name=='bad_key':r['items'][0]['zoteroKey']='x'
  text='TRACKEEP_JSON '+json.dumps(r)+'\n';text=text*2 if name=='duplicate_receipts' else text
  with patch.object(m.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout=text)):
   try:m.engine_call([A],'Science','COLL0001',Path('synthetic'),True);outcome='accepted'
   except Exception as e:outcome=type(e).__name__
  results.append({'case':'parser_'+name,'outcome':outcome})
f=Path(r'D:/trackeep-lit/日志/metadata-validation/independent-bridge-results.json');f.write_text(json.dumps({'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'results':results,'network_calls':0,'credentials':False,'product_hash':hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest()},ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(results,ensure_ascii=False))
