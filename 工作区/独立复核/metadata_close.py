"""独立结果断言、现有离线测试与本次2篇门禁结论。"""
import json,sys,io,unittest,importlib.util,hashlib,datetime
from pathlib import Path
from unittest.mock import patch
sys.dont_write_bytecode=True;sys.path.insert(0,r'D:/trackeep-lit')
folder=Path(r'D:/trackeep-lit/日志/metadata-validation')
def read(n):return json.loads((folder/n).read_text(encoding='utf-8-sig'))
e=read('independent-engine-results.json');eng={r['case']:r for r in e['results']}
for n in ['wrong_pmid','missing_fetch','duplicate_fetch','wrong_doi','wrong_title','wrong_nlm','wrong_collection','conflict']:assert eng[n]['error'] and eng[n]['post_count']==0,n
for n in ['single','multi','multi_reordered','unicode','same_title']:assert not eng[n]['error'] and eng[n]['receipt']['counts']['imported']>=1,n
for n in ['existing','trashed','normalized_doi']:assert eng[n]['post_count']==0 and eng[n]['receipt']['counts']['imported']==0,n
for n in ['wrong_response_identity','duplicate_key','missing_response']:assert eng[n]['error'] and eng[n]['receipt'] is None,n
assert eng['partial']['receipt']['counts']['failed']==1 and eng['partial']['receipt']['counts']['imported']==1
b=read('independent-bridge-results.json');bridge={r['case']:r for r in b['results']}
for n in ['source_fresh_drift','missing_collection','duplicate_collection']:assert bridge[n]['status']=='blocked' and not any(c[0]=='ENGINE' for c in bridge[n]['calls']),n
assert bridge['readback_wrong_nlm']['items'][0]['metadata_status']=='readback_failed'
assert bridge['engine_timeout']['status']=='blocked'
for r in b['results']:
 if 'existing_unchanged' in r:assert r['existing_unchanged'] and r['fulltext_status']=='not_started'
 if r['case'].startswith('parser_'):assert r['outcome']==('accepted' if r['case']=='parser_valid' else 'RuntimeError')
p=read('independent-postreview-results.json');post={r['case']:r for r in p}
for n in ['keep','exclude','pending','no_abstract','retracted','notice','changed','duplicate','outside']:assert post[n]['mutations']==0 and post[n]['fulltext']=='not_started'
assert post['keep']['effective']==['101'] and post['exclude']['effective']==[]
for n in ['pending','no_abstract','changed','duplicate','outside']:assert post[n]['status']=='review_pending'
assert post['cli_failed_review_evidence']=={'case':'cli_failed_review_evidence','uncaught':None,'exit_code':2,'review_files':1}
from lit import zotero
spec=importlib.util.spec_from_file_location('metadata_tests',r'D:/trackeep-lit/tests/metadata_test.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);stream=io.StringIO()
with patch('urllib.request.urlopen',side_effect=AssertionError('offline')),patch('urllib.request.OpenerDirector.open',side_effect=AssertionError('offline')),patch('subprocess.run',side_effect=AssertionError('no real process')),patch.object(zotero,'_load_env',side_effect=AssertionError('no credentials')):
 result=unittest.TextTestRunner(stream=stream).run(unittest.defaultTestLoader.loadTestsFromModule(mod))
assert result.wasSuccessful(),stream.getvalue()
files=[Path(r'D:/dev/trackeep-scripts/zotero-import.ps1')]+[Path(r'D:/trackeep-lit/lit')/x for x in ['metadata_batch.py','library.py','batch_review.py','zotero.py','pubmed.py']]
report={'schema':'trackeep/metadata-independent-review@1','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'verdict':'pass_offline_gate_for_authorized_two_article_trial','execution_counts':{'engine_synthetic':len(eng),'bridge_synthetic':len(bridge),'postreview_synthetic':len(post),'existing_tests':result.testsRun},'findings':[{'id':'META-01','description':'成功回执错身份仍确认并记台账','status':'closed','before':'independent-engine-results-before-fix.json wrong_response_identity','after':'independent-engine-results.json wrong_response_identity拒绝'}, {'id':'META-02','description':'两篇同key被记两次成功','status':'closed','before':'independent-engine-results-before-fix.json duplicate_key','after':'independent-engine-results.json duplicate_key拒绝'}, {'id':'META-03','description':'读回NLM错误仍标created_verified','status':'closed','before':'independent-bridge-results-before-fix.json readback_wrong_nlm','after':'independent-bridge-results.json readback_wrong_nlm待核'}, {'id':'META-04','description':'复核CLI失败无报告','status':'closed','before':'independent-postreview-results-before-fix.json cli_failed_review_evidence','after':'independent-postreview-results.json exit2且一份失败回执'}],'candidate_hashes':{str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in files},'scope_reconciliation':'原20类验收中清理/trash已由PI本轮缩减为有效候选清单；按新边界验证零库变更和原附件/子项保留，不声称真实trash/merge通过。错误/缺少/重复PMID、乱序、Unicode、目录、已有/回收站、DOI规范化、标识冲突、回执失败、桥接超时、复核状态均有原始用例。','limits':['离线桩不证明真实Zotero服务契约或实库幂等；仅允许既定2篇试验继续，之后仍须按回执key核对PMID/DOI/title/NLM和目录，并同批重跑验证不新增。','模拟超时已证明失败可见；其后已有身份分支不新增已独立验证，但没有声称完成真实服务断网恢复演练。','本阶段不提供永久删除、自动merge/trash、全库清理、全文或插件能力。','任何新增候选或修改被审文件须重新判断适用验证；本报告不是全管道发布批准。'],'safety':{'real_network':0,'credential_reads':0,'real_execute':0,'mock_execute_only':True,'real_zotero_writes':0,'product_modifications':0},'reproduce':['C:/Program Files/PowerShell/7/pwsh.exe -NoProfile -File D:/trackeep-lit/工作区/独立复核/metadata_engine.ps1','D:/trackeep-lit/venv/Scripts/python.exe -B D:/trackeep-lit/工作区/独立复核/metadata_bridge.py','D:/trackeep-lit/venv/Scripts/python.exe -B D:/trackeep-lit/工作区/独立复核/metadata_postreview.py','D:/trackeep-lit/venv/Scripts/python.exe -B D:/trackeep-lit/工作区/独立复核/metadata_close.py']}
(folder/'independent-review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'verdict':report['verdict'],'counts':report['execution_counts']},ensure_ascii=False))
