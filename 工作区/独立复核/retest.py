from pathlib import Path
source=Path(__file__).with_name('review.py').read_text(encoding='utf-8-sig').split('# One independently selected public sample')[0]
exec(compile(source,'original-held-out','exec'))
import tempfile,contextlib
original_path=Path(r'D:/trackeep-lit/日志/pubmed-validation/independent-review.json')
prior=json.loads(original_path.read_text(encoding='utf-8'))
retest={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'checks':checks,'existing_tests':report['existing_tests'],'files':report['files']}
assert all(x.get('status')=='blocked' for x in checks if x['case']!='warning_propagates')
assert next(x for x in checks if x['case']=='warning_propagates')['status']=='review_required'
# Exercise the real CLI's malformed JSON path while output stays in TEMP.
with tempfile.TemporaryDirectory() as td:
 t=Path(td);bad=t/'bad.json';bad.write_text('{bad',encoding='utf-8');sink=io.StringIO()
 with patch.object(p,'ROOT',t),patch.object(sys,'argv',['pubmed','--plan',str(bad)]),patch('urllib.request.urlopen',side_effect=AssertionError('offline')),contextlib.redirect_stdout(sink):code=p.main()
 reports=list(t.glob('日志/pubmed-preview/*.json'));assert code==1 and len(reports)==1
 retest['invalid_file_cli']={'exit':code,'report_count':len(reports),'status':json.loads(reports[0].read_text(encoding='utf-8'))['status']}
# Map check uses the real renderer and source tree, only MAP points into TEMP.
spec=importlib.util.spec_from_file_location('mapcheck',r'D:/trackeep-lit/tools/check_map.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
text=m.MAP.read_text(encoding='utf-8');map_results=[]
with tempfile.TemporaryDirectory() as td:
 mp=Path(td)/'map.md'
 for name,body,expected in [('current-observed-drift',text,1),('regenerated-in-temp',m.update(text),0),('stale',text.replace('| `lit/pubmed.py` |','| `lit/WRONG.py` |'),1),('missing-marker',text.replace(m.END,''),1)]:
  mp.write_text(body,encoding='utf-8');s=io.StringIO()
  with patch.object(m,'MAP',mp),patch.object(sys,'argv',['check_map','--check']),contextlib.redirect_stdout(s):code=m.main()
  map_results.append({'case':name,'exit':code,'expected':expected,'output':s.getvalue().strip()});assert code==expected
retest['map_checks']=map_results
prior.setdefault('retests',[]).append(retest)
for f in prior['findings']:f['status']='closed';f['closure']='原held-out用例独立复测阻断正确，CLI坏文件回执独立落盘验证；见retests。'
prior['verdict']='pending_map_regeneration'
prior['document_review']['five_checks']['内容最新']='修复复核通过：原IR-01/02关闭，CLI坏文件失败留证已实测。'
prior['document_review']['five_checks']['完整']='本阶段通过；语义/相关性人工判断、跨阶段写入未实现边界保持明确。'
prior['map_review']={'basis':'仅先读规则/架构.md回答定位，再独立执行生成器核验；未修改产品或地图。','wrong_journal_location':'.project/pubmed-journals.json核身份；lit/pubmed.py metadata提取NLM ID，preview做指定期刊对账；先看日志/pubmed-preview回执，不放松断言。','new_date_location':'lit/pubmed.py prepare日期允许字段；tests/pubmed_test.py加反例；同步PubMed检索规范；生成块用tools/check_map.py --write。','four_questions':{'系统是什么':'通过：新只读预览与现役旧GUI明确区分。','故障去哪查':'通过：回执→prepare/esearch/collect/metadata/preview职责定位明确。','新功能加在哪':'通过：期刊表、日期允许字段、计划概念与写入后续阶段分别有落点。','各块怎样协调':'通过：Agent→计划→CLI→NCBI→本地回执，身份表/规则/记录归属清楚。'},'guard_limits':'生成器校验源码体量和本仓import语法，不证明手写架构语义完整或生产运行正确；CI仅确认配置接线，未声称云端已运行。'}
prior['delivery_conclusion']='代码缺陷复核关闭；待重新生成漂移地图后可交付本阶段只读PubMed规范、预览入口及机器护栏。不是全管道发布批准；Zotero导入、AI筛选、全文、插件仍不在复核范围。'
original_path.write_text(json.dumps(prior,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(retest,ensure_ascii=False))

