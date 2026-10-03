import json,hashlib,datetime
from pathlib import Path
root=Path(r'D:/trackeep-lit');files=[root/'日志/metadata-batches'/n/'report.json' for n in ['20261003-145208-a76b30d3','20261003-145307-7128c01c']]+[root/'日志/metadata-validation/live-dryrun-diagnosis.json']
a,b,c=[json.loads(f.read_text(encoding='utf-8')) for f in files]
assert a['status']=='blocked' and a.get('failure') and 'receipt' not in a and 'dry_run' not in a
assert all(x['metadata_status']=='new_candidate' and not x.get('created_key') for x in a['items'])
assert b['status']=='preview_only' and b['dry_run']['executed'] is False and b['dry_run']['counts']['imported']==0 and b['counts']=={'new_candidate':2}
assert c['execute'] is False and c['exit_code']==0
out={'schema':'trackeep/metadata-live-failure-review@1','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'verdict':'failure_visible_not_misreported_as_success','first_failure':{'status':a['status'],'failure':a['failure'],'intent_apply':a['apply'],'has_dry_run':False,'has_execute_receipt':False,'created_keys':[]},'subsequent_read_only':{'status':b['status'],'executed':b['dry_run']['executed'],'counts':b['dry_run']['counts']},'diagnosis':c,'reasoning':'结合稳定候选代码的顺序：dry_run调用正常返回并校验后才执行真写。首次报告保留blocked、无dry_run/receipt、两篇仍new_candidate，支持失败发生于预演阶段；apply=true仅是用户意图，不能当实际写成功。','cause':'unknown；后续只读成功不能反证前次失败或推定具体根因。','limits':['未调用服务/读取凭证；仅核本地报告及已审代码流程。','没有原始进程轨迹，不把报告缺字段单独当作服务器零写入证明。','第二次apply结果与真实幂等仍待成功或失败回执独立复核。'],'inputs':[{'path':str(f),'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for f in files]}
(root/'日志/metadata-validation/independent-live-failure-review.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(out['first_failure'],ensure_ascii=False))
