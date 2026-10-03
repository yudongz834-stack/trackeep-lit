"""只汇总离线独立证据；不访问网络或凭证。"""
import json, hashlib, datetime
from pathlib import Path
root=Path('D:/trackeep-lit')
out=root/'日志/fulltext-validation'
def read(name): return json.loads((out/name).read_text(encoding='utf-8-sig'))
c=read('independent-candidate-results.json')['results']; b=read('independent-batch-results.json'); x=read('independent-boundary-results.json')
cases={i['case']:i for i in c}
assert not cases['doi_prefix_collision']['accepted']
assert not cases['reference_on_first_page']['accepted']
assert cases['attach_new']['result']=='created_verified'
assert cases['attach_pending']['result']=='resumed_verified'
for mode in ['association_changed','type_changed','deleted_after','md5_changed']:
 assert cases['attach_'+mode]['result']=='error'
assert all(cases['official_'+p]['verification']['pages']==37 for p in ['42420446','42816625'])
lock=b[-1]
assert lock['outcome']['exit_code']==2 and len(lock['reports'])==1
assert lock['reports'][0]['status']=='blocked' and not lock['reports'][0]['items']
assert all(i.get('network_attempts',0)==0 and not i.get('storage_received_auth',False) for i in x)
files=['lit/fulltext.py','lit/fulltext_batch.py','lit/library.py','工作区/下载本批官方全文.py','.project/fulltext-task.md','tests/fulltext_test.py']
r={'schema':'trackeep-independent/fulltext-gate@1','created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'decision':'允许本批两篇受控附件上传；尚非真实上传验收或通用全文管道发布',
 'scope':{'42420446':'WD9F8D8E','42816625':'IU8CWQD2'},
 'candidate_sha256':{f:hashlib.sha256((root/f).read_bytes()).hexdigest() for f in files},
 'independent_probe_counts':{'candidate':len(c),'network_isolation_and_download_gate':len(x),'batch_and_lock':len(b),'existing_unit_tests':6},
 'closed_findings':[
  {'id':'FT-01','severity':'high','location':'lit/fulltext.py:29','reproduction':'doi_prefix_collision','before':'目标 DOI 为错误 DOI 前缀时被接受','after':'完整 token 比对拒绝；原反例复测'},
  {'id':'FT-02','severity':'high','location':'lit/fulltext.py:28','reproduction':'reference_on_first_page','before':'首页参考文献标题和 DOI 被误作主文身份','after':'剔除参考文献并限制标题前 800 字符；原反例拒绝'},
  {'id':'FT-03','severity':'medium','location':'lit/fulltext_batch.py:main','reproduction':'competing_process_lock','before':'锁竞争阻止执行但无失败回执','after':'退出 2，blocked 回执一份，items 为空'}],
 'remaining_blockers_for_named_trial':[],
 'evidence':['independent-candidate-before-fix.json','independent-candidate-results.json','independent-boundary-results.json','independent-batch-results.json'],
 'reproduce':['E:/Python/python.exe -B 工作区/独立复核/'+s for s in ['fulltext_candidate.py','fulltext_boundaries.py','fulltext_batch_probe.py','fulltext_close.py']],
 'limits':[
  '24 个首轮动态用例不等于前期 24 类风险矩阵全部覆盖；另有 12 个边界/批次探针。',
  '全程无真实网络、凭证读取或 Zotero 写入；服务端协议和响应只能待现场验证。',
  '合成附件 unrelated/user_pending 夹具重用键导致预期读回哈希失败，仅证明不覆盖旧项，不构成成功挂接实证。',
  '并发锁只覆盖本项目批处理入口；其他程序并发写 Zotero 不受此锁控制。',
  'PDF 身份/正文启发式不是任意出版物完整性证明；本门禁限两份已核 37 页、固定哈希原件。',
  '下载前云端查重来自本次主控现场记录，下载脚本本身不实现通用云端预查。',
  '真实上传后必须核父项/附件键/读回哈希及同批重跑无新增，方可最终验收。'],
 'original_pdf_verifications':{p:cases['official_'+p]['verification'] for p in ['42420446','42816625']}}
(out/'independent-review.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'decision':r['decision'],'report':str(out/'independent-review.json'),'counts':r['independent_probe_counts']},ensure_ascii=False))
