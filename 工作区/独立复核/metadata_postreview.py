"""入库后复核独立桩：只读合成库，不允许任何服务或凭证。"""
import json,copy,sys,tempfile,io,contextlib
from pathlib import Path
from unittest.mock import patch
sys.dont_write_bytecode=True;sys.path.insert(0,r'D:/trackeep-lit')
from lit import batch_review as b,zotero
A={'pmid':'101','doi':'10.1/a','title':'Title A','nlm_id':'0404511','abstract':'evidence','source':'https://pubmed.ncbi.nlm.nih.gov/101/','retracted':False,'retraction_notice':False}
base={'schema':'trackeep-literature/metadata-batch@1','status':'metadata_verified','articles':[A],'items':[{'pmid':'101','keys':['OLD00001'],'metadata_status':'existing_verified'}],'collection':{'key':'COLL0001'}}
rows=[{'key':'OLD00001','data':{'itemType':'journalArticle','title':'Title A','DOI':'10.1/a','extra':'PMID: 101\nNLM ID: 0404511','collections':['COLL0001']}}]
children=[{'key':'CHILD001','data':{'itemType':'attachment','parentItem':'OLD00001','title':'Existing attachment'}}]
results=[]
class Lib:
 def all(self,path):return copy.deepcopy(children if path.endswith('/children') else rows)
with patch('urllib.request.urlopen',side_effect=AssertionError('offline')),patch('urllib.request.OpenerDirector.open',side_effect=AssertionError('offline')),patch.object(zotero,'_load_env',side_effect=AssertionError('no credentials')):
 for mode in ['keep','exclude','pending','no_abstract','retracted','notice','changed','duplicate','outside']:
  bat=copy.deepcopy(base);decision='exclude' if mode in ['exclude','no_abstract'] else 'pending' if mode=='pending' else 'keep'
  current=copy.deepcopy(rows)
  if mode=='no_abstract':bat['articles'][0]['abstract']=''
  if mode=='retracted':bat['articles'][0]['retracted']=True
  if mode=='notice':bat['articles'][0]['retraction_notice']=True
  if mode=='changed':current[0]['data']['title']='Changed'
  if mode=='duplicate':current.append(dict(copy.deepcopy(current[0]),key='OTHER001'))
  if mode=='outside':current[0]['data']['collections']=[]
  class Fake:
   def all(self,path):return copy.deepcopy(children if path.endswith('/children') else current)
  before=copy.deepcopy(current);r=b.review(bat,[{'pmid':'101','decision':decision,'reason':'synthetic judgement'}],Fake());assert current==before
  results.append({'case':mode,'status':r['status'],'effective':r['effective_pmids'],'decision':r['items'][0]['decision'],'mutations':r['zotero_mutations'],'children_preserved':r['items'][0].get('children')==children if len(current)==1 else None,'fulltext':r['fulltext_status']})
 # Failed independent review must still be auditable; exercise actual CLI with malformed decisions.
 with tempfile.TemporaryDirectory() as td:
  p=Path(td);(p/'batch.json').write_text(json.dumps(base));(p/'decisions.json').write_text('[]')
  with patch.object(b,'ROOT',p),patch.object(b,'Library',Lib),patch.object(sys,'argv',['review','--batch',str(p/'batch.json'),'--decisions',str(p/'decisions.json')]),contextlib.redirect_stdout(io.StringIO()):
   try:exit_code=b.main();error=None
   except Exception as e:error=type(e).__name__
  results.append({'case':'cli_failed_review_evidence','uncaught':error,'exit_code':exit_code,'review_files':len(list(p.glob('日志/metadata-reviews/review-*.json')))})
out=Path(r'D:/trackeep-lit/日志/metadata-validation/independent-postreview-results.json');out.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(results,ensure_ascii=False))
