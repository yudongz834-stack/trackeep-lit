import json,hashlib,datetime
from pathlib import Path
f=Path(r'D:/trackeep-lit/日志/pubmed-validation/independent-review.json');r=json.loads(f.read_text(encoding='utf-8'));last=r['cross_month_reviews'][-1];rows={x['case']:x for x in last['results']}
for n in ['future_history','bad_count','bad_timezone','bad_doi','duplicate_rows']:assert rows[n]['status']=='blocked',n
for n in ['same_pmid_changed','unsorted_histories','saved_live_pair']:
 c=rows[n]['cross_batch'];assert c['seen_count']==1 and c['new_count']==0,n
for n in ['different_pmid_Retraction Notice','different_pmid_Preprint']:
 assert rows[n]['cross_batch']['new_count']==1 and rows[n]['cross_batch']['seen_count']==0,n
assert rows['same_doi_different_pmid']['status']=='review_required'
assert rows['no_history']['cross_batch']['status']=='not_evaluated'
assert all(x['counts_preserved'] and x['pmids_preserved'] for x in rows.values())
assert last['tests']=={'run':34,'failures':0,'errors':0}
for x in r['cross_month_findings']:x['status']='closed';x['closure']='原独立反例复跑均blocked；cross_month_reviews保留修复前后原始结果。'
r['verdict']='pass_for_read_only_pubmed_with_cross_month_comparison'
r['delivery_conclusion']='本阶段只读检索与跨月快照对账可交付，IR-01至IR-04均独立复核关闭。相同PMID跨月算已见/元数据变化，源命中数不改；不同PMID对象不自动合并。不代表完整文献管道发布，不批准Zotero/AI/全文/插件。'
r['oracle_artifacts']=[{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'role':{'review.py':'首次独立对抗+当次公开样本取证原脚本（含网络段）','live.py':'历史Science单日公开样本取证原脚本（含网络）','retest.py':'首次schema和地图修复时的复核快照脚本，内有当时地图漂移预期','cross_month.py':'当前跨月12例与现役测试复算，无网络','close_cross_month.py':'核对最终跨月结果并关闭发现'}[p.name]} for p in Path(r'D:/trackeep-lit/工作区/独立复核').glob('*.py') if p.name in ['review.py','live.py','retest.py','cross_month.py','close_cross_month.py']]
r['cross_month_final_check']={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'oracle_cases':12,'all_expected':True,'tests':34,'map_check_exit':0,'network_calls':0}
f.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8');print(r['verdict'])
