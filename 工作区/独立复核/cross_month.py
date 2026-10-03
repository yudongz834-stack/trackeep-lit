import sys,json,copy,datetime,hashlib,io,unittest,importlib.util
from pathlib import Path
from unittest.mock import patch
sys.dont_write_bytecode=True;sys.path.insert(0,r'D:/trackeep-lit')
from lit import pubmed as p
base={'schema':'trackeep-literature/pubmed-preview@1','created_at':'2026-10-03T12:00:00+00:00','status':'retrieval_verified','read_only':True,'retrieval_complete':True,'relevance_validated':False,'pmids':['101'],'counts':{'unique_pmids':1,'metadata':1},'review_reasons':[],'articles':[{'pmid':'101','doi':'10.1/test','title':'Same paper','publication_status':'ppublish','volume':'50','issue':'1','types':['Journal Article'],'retraction_notice':False,'retraction_links':[]}]}
old=copy.deepcopy(base);old['created_at']='2026-07-03T12:00:00+00:00';old['articles'][0].update(publication_status='aheadofprint',volume='',issue='')
results=[]
def case(name,previous,current=None):
 r=copy.deepcopy(current or base);before=copy.deepcopy(r['counts']);source=list(r['pmids'])
 try:p.compare_previous(r,previous);results.append({'case':name,'status':r['status'],'cross_batch':r.get('cross_batch'),'failure':r.get('failure'),'counts_preserved':before==r['counts'],'pmids_preserved':source==r['pmids']})
 except Exception as e:results.append({'case':name,'uncaught':type(e).__name__,'message':str(e)})
case('same_pmid_changed',[old]);case('no_history',[])
later=copy.deepcopy(old);later['created_at']='2026-09-03T12:00:00+00:00';later['articles']=copy.deepcopy(base['articles']);case('unsorted_histories',[later,old])
future=copy.deepcopy(old);future['created_at']='2099-01-01T00:00:00+00:00';case('future_history',[future])
for name,mut in [('bad_timezone',lambda x:x.update(created_at='2026-07-03T12:00:00')),('bad_doi',lambda x:x['articles'][0].update(doi=[])),('duplicate_rows',lambda x:x['articles'].append(copy.deepcopy(x['articles'][0]))),('bad_count',lambda x:x['counts'].update(unique_pmids=999))]:
 bad=copy.deepcopy(old);mut(bad);case(name,[bad])
for typ in ['Retraction Notice','Preprint']:
 current=copy.deepcopy(base);current['pmids']=['202'];current['articles'][0].update(pmid='202',doi='10.1/other',types=[typ],retraction_notice=typ=='Retraction Notice',retraction_links=[{'type':'RetractionOf','pmid':'101'}] if typ=='Retraction Notice' else [])
 case('different_pmid_'+typ,[old],current)
current=copy.deepcopy(base);current['pmids']=['202'];current['articles'][0]['pmid']='202';case('same_doi_different_pmid',[old],current)
paths=[Path(r'D:/trackeep-lit/日志/pubmed-preview')/n for n in ['20261003-141319-e595ab19.json','20261003-141439-fbf29861.json']]
a,b=[json.loads(f.read_text(encoding='utf-8')) for f in paths];case('saved_live_pair',[a],b)
spec=importlib.util.spec_from_file_location('tests',r'D:/trackeep-lit/tests/pubmed_test.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);stream=io.StringIO()
with patch('urllib.request.urlopen',side_effect=AssertionError('no network')):suite=unittest.TextTestRunner(stream=stream).run(unittest.defaultTestLoader.loadTestsFromModule(mod))
report={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'results':results,'tests':{'run':suite.testsRun,'failures':len(suite.failures),'errors':len(suite.errors)},'live_inputs':[{'path':str(f),'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for f in paths],'network_calls':0}
f=Path(r'D:/trackeep-lit/日志/pubmed-validation/independent-review.json');r=json.loads(f.read_text(encoding='utf-8'));r.setdefault('cross_month_reviews',[]).append(report);f.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=False))
