import sys,json,copy,datetime,hashlib,unittest,importlib.util,io
from pathlib import Path
from unittest.mock import patch
sys.dont_write_bytecode=True
sys.path.insert(0,r'D:/trackeep-lit')
from lit import pubmed as p
base={'kind':'journal','journal':'Science','date':{'field':'dp','start':'2026-09-04','end':'2026-09-04'},'selection_mode':'broad','screening_location':'undecided'}
checks=[]
def run(name,plan,replies=None):
 try:
  with patch.object(p,'request',side_effect=replies or AssertionError('No network permitted')) as req:r=p.preview(plan)
  checks.append({'case':name,'status':r['status'],'failure':r.get('failure'),'requests':req.call_count})
 except Exception as e:checks.append({'case':name,'uncaught':type(e).__name__,'message':str(e)})
def es(**kw):
 d={'count':'1','idlist':['1'],'querytranslation':'Science[Journal]'};d.update(kw)
 return json.dumps({'esearchresult':d}).encode(),{}
xml=b'<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>1</PMID><Article><ArticleTitle>offline</ArticleTitle></Article><MedlineJournalInfo><NlmUniqueID>0404511</NlmUniqueID></MedlineJournalInfo></MedlineCitation></PubmedArticle></PubmedArticleSet>'
for field,value in [('date',['dp']),('journal',17),('filter_query',17),('date',None),('known_pmids',[1])]:
 plan=copy.deepcopy(base);plan[field]=value;run('malformed_'+field+'_'+str(value),plan)
for field,value in [('warninglist',[]),('warninglist','warning'),('errorlist',[]),('querytranslation',17),('count',True)]:
 run('response_'+field+'_'+str(value),base,[es(**{field:value}),(xml,{})])
plan=copy.deepcopy(base);plan['date']['start']='2026-02-29';run('invalid_leap_date',plan)
plan=copy.deepcopy(base);plan['date']['start']='2026-09-05';run('inverted_date',plan)
run('single_day_overflow',base,[es(count='10000',idlist=['1'])])
run('warning_propagates',base,[es(warninglist={'outputmessages':['x']}),(xml,{})])
run('wrong_identity',base,[es(),(xml.replace(b'<PMID>1',b'<PMID>2'),{})])
run('wrong_journal',base,[es(),(xml.replace(b'0404511',b'0410462'),{})])
# Existing suite under a network fence.
spec=importlib.util.spec_from_file_location('tested',r'D:/trackeep-lit/tests/pubmed_test.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
s=io.StringIO()
with patch('urllib.request.urlopen',side_effect=AssertionError('offline')):
 result=unittest.TextTestRunner(stream=s,verbosity=1).run(unittest.defaultTestLoader.loadTestsFromModule(mod))
report={'schema':'trackeep/pubmed-independent-review@1','reviewed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'D:/trackeep-lit current read-only PubMed entry','checks':checks,'existing_tests':{'run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'output':s.getvalue()},'files':{str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in [Path(r'D:/trackeep-lit/lit/pubmed.py'),Path(r'D:/trackeep-lit/规则/PubMed检索规范_v1.0_20261003.md')]}}
# One independently selected public sample; original URL opener, GET only, no authentication.
original=p.request
seen=[]
def public_only(url,**kw):
 from urllib.parse import urlparse
 u=urlparse(url)
 assert u.scheme=='https' and u.hostname=='eutils.ncbi.nlm.nih.gov' and not kw.get('data') and not kw.get('headers') and kw.get('method') in (None,'GET')
 seen.append(url);return original(url,**kw)
with patch.object(p,'request',side_effect=public_only):report['live_sample']=p.preview(base)
report['live_urls']=seen
out=Path(r'D:/trackeep-lit/日志/pubmed-validation/independent-review.json');out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'checks':checks,'existing_tests':report['existing_tests'],'live_status':report['live_sample']['status'],'live_counts':report['live_sample'].get('counts'),'live_failure':report['live_sample'].get('failure'),'report':str(out)},ensure_ascii=False))
