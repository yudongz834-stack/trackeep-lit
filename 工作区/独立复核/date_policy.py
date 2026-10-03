"""具名日期政策独立离线复核；所有公共请求替换为合成回执。"""
import sys,json,copy,io,unittest,importlib.util,datetime,hashlib,ast
from pathlib import Path
from unittest.mock import patch
sys.dont_write_bytecode=True;sys.path.insert(0,r'D:/trackeep-lit')
from lit import pubmed as p
base={'kind':'journal','journal':'Science','date':{'start':'2024-06-01','end':'2024-06-30'},'selection_mode':'broad','screening_location':'undecided'}
search=(json.dumps({'esearchresult':{'count':'1','idlist':['1'],'querytranslation':'synthetic offline'}}).encode(),{})
def xml(electronic='',issue=''):
 return (f'<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>1</PMID><Article><ArticleTitle>合成日期样本</ArticleTitle>{electronic}<Journal><JournalIssue>{issue}</JournalIssue></Journal></Article><MedlineJournalInfo><NlmUniqueID>0404511</NlmUniqueID></MedlineJournalInfo></MedlineCitation></PubmedArticle></PubmedArticleSet>'.encode(),{})
checks=[]
def run(name,plan,expected,field=None,origin=None,meta=None):
 before=copy.deepcopy(plan)
 with patch.object(p,'request',side_effect=[search,meta or xml()]) as req:r=p.preview(plan)
 assert r['status']==expected,(name,r)
 assert plan==before and r['plan']==before,name
 if expected=='blocked':assert req.call_count==0,name
 else:
  assert r['date_policy']['field']==field and r['date_policy']['origin']==origin,name
  assert f'[{field}]' in r['searches'][0]['query'],name
  assert r['effective_plan']['screening_location']=='undecided',name
 checks.append({'name':name,'status':r['status'],'date_policy':r.get('date_policy'),'date_sources':r.get('articles',[{}])[0].get('date_sources') if r.get('articles') else None,'requests':req.call_count,'input_preserved':plan==before})
 return r
with patch('urllib.request.urlopen',side_effect=AssertionError('禁止联网')):
 r=run('journal_omitted_defaults_dp',copy.deepcopy(base),'retrieval_verified','dp','default')
 assert all(x['status']=='missing' and x['xml']==[] for x in r['articles'][0]['date_sources'].values())
 for field in ['dp','epdat','ppdat']:
  q=copy.deepcopy(base);q['date']['field']=field;run('explicit_'+field,q,'retrieval_verified',field,'explicit')
 for bad in [None,'','DP','typo',0]:
  q=copy.deepcopy(base);q['date']['field']=bad;run('bad_field_'+repr(bad),q,'blocked')
 q=copy.deepcopy(base);q['date'].pop('start');run('missing_start_not_guessed',q,'blocked')
 q=copy.deepcopy(base);q.update(kind='topic',query='cancer[tiab]',concepts=[{'name':'cancer'}]);q.pop('selection_mode');run('topic_field_still_required',q,'blocked')
 electronic='<ArticleDate DateType="Electronic"><Year>2024</Year><Month>3</Month><Day>2</Day></ArticleDate>'
 issue='<PubDate><Year>2024</Year><Season>Summer</Season></PubDate>'
 r=run('distinct_dates_preserved',copy.deepcopy(base),'retrieval_verified','dp','default',xml(electronic,issue));sources=r['articles'][0]['date_sources']
 assert 'Summer' in sources['issue']['xml'][0] and '<Day>' not in sources['issue']['xml'][0]
 assert '<Month>3</Month>' in sources['electronic']['xml'][0]
 r=run('issue_without_electronic',copy.deepcopy(base),'retrieval_verified','dp','default',xml('',issue));assert r['articles'][0]['date_sources']['electronic']=={'status':'missing','xml':[]}
 spec=importlib.util.spec_from_file_location('date_tests',r'D:/trackeep-lit/tests/pubmed_test.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);stream=io.StringIO();suite=unittest.TextTestRunner(stream=stream).run(unittest.defaultTestLoader.loadTestsFromModule(mod))
 assert suite.wasSuccessful()
assert not any(n in sys.modules for n in ['lit.zotero','lit.deepseek','lit.engine'])
report={'schema':'trackeep/date-policy-independent-review@1','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'verdict':'pass_for_named_read_only_date_policy','checks':checks,'existing_tests':{'run':suite.testsRun,'failures':len(suite.failures),'errors':len(suite.errors)},'document_review':{'scope':'规则/PubMed检索规范_v1.0_20261003.md及nature-month示例','contradictions':[],'conclusion':'按刊省略field默认dp、主题仍需显式字段、显式epdat/ppdat局限、筛选undecided、增量未实现均对应实现；第6节显式日期理解为范围要求，与前文默认字段不冲突。'},'boundaries':{'network_calls':0,'zotero_ai_engine_imported':False,'credentials_read':False,'real_library_writes':False},'limits':['合成日期仅验证保留与缺失标记；未联网重新验证检索口径、补录延迟或电子上线时效。','不覆盖增量回看/Zotero存量更新，非全管道发布批准。'],'files':{str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in [Path(r'D:/trackeep-lit/lit/pubmed.py'),Path(r'D:/trackeep-lit/规则/PubMed检索规范_v1.0_20261003.md')]},'reproduce':'D:/trackeep-lit/venv/Scripts/python.exe -B D:/trackeep-lit/工作区/独立复核/date_policy.py'}
Path(r'D:/trackeep-lit/日志/pubmed-validation/date-policy-review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'verdict':report['verdict'],'independent_cases':len(checks),'existing_tests':report['existing_tests']},ensure_ascii=False))
