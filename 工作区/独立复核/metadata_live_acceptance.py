"""对已保存的真实两篇试验回执独立复算；绝不访问服务。"""
import json,hashlib,re,datetime
from pathlib import Path
root=Path(r'D:/trackeep-lit');names=['日志/metadata-batches/20261003-145432-2b6d0965/report.json','日志/metadata-batches/20261003-145542-09f4f670/report.json','日志/metadata-reviews/review-1141862b.json']
paths=[root/n for n in names];first,retry,review=[json.loads(p.read_text(encoding='utf-8')) for p in paths]
expected={'42420446':'WD9F8D8E','42816625':'IU8CWQD2'}
assert first['status']==retry['status']=='metadata_verified'
assert first['counts']=={'created_verified':2} and retry['counts']=={'existing_verified':2}
assert first['receipt']['executed'] is True and first['receipt']['counts']['imported']==2 and first['receipt']['counts']['failed']==0
assert not any(k in retry for k in ['receipt','dry_run'])
assert first['collection']==retry['collection']=={'key':'V98QAD78','name':'Nature'}
assert review['status']=='review_complete' and review['counts']=={'keep':2,'exclude':0,'pending':0} and set(review['effective_pmids'])==set(expected)
assert review['zotero_mutations']==0 and all(x['fulltext_status']=='not_started' for x in [first,retry,review])
checks=[]
for pmid,key in expected.items():
 a=next(x for x in first['articles'] if x['pmid']==pmid)
 initial=next(x for x in first['items'] if x['pmid']==pmid)
 existing=next(x for x in retry['items'] if x['pmid']==pmid)
 final=next(x for x in review['items'] if x['pmid']==pmid)
 receipt=next(x for x in first['receipt']['items'] if x['pmid']==pmid)
 assert initial['created_key']==receipt['zoteroKey']==key and initial['keys']==existing['keys']==final['keys']==[key]
 before=initial['readback'];after=existing['before'][0];latest=final['readback']
 assert before['data']==after['data']==latest['data']
 d=latest['data'];assert d['title']==a['title'] and d['DOI']==a['doi'] and d['abstractNote']==a['abstract']
 assert re.findall(r'(?m)^PMID: (\d+)$',d['extra'])==[pmid] and re.findall(r'(?m)^NLM ID: (\S+)$',d['extra'])==['0410462']
 assert d['collections']==['V98QAD78'] and not d.get('deleted')
 assert final['children']==[] and latest['meta']['numChildren']==0
 for source in a['date_sources'].values():
  for xml in source['xml']:assert xml in d['extra']
 if pmid=='42816625':assert d['volume']==d['issue']==d['pages']=='' and a['publication_status']=='aheadofprint'
 assert not a['retracted'] and not a['retraction_notice']
 checks.append({'pmid':pmid,'key':key,'identity_title_doi_nlm_collection':'match','snapshot_data_unchanged':True,'tags':d['tags'],'children_count':0,'date_sources_preserved':True})
judgements=[{'pmid':'42420446','decision':'keep','basis':'独立读取保存的原摘要：研究造血干/祖细胞的KIT表位编辑及移植预处理，直接涉及造血细胞移植。','qualification':'仅题录/摘要相关性，不是全文质量或临床有效性判断。'}, {'pmid':'42816625','decision':'keep','basis':'独立读取保存的原摘要：临床研究人群明确为接受造血细胞移植的住院患者，分析饮食、抗菌药与菌群变化。既定范围含移植患者研究，所以标题未出现移植并非排除理由。','qualification':'符合当前较宽相关性范围；不将观察结果解释为治疗建议。'}]
report={'schema':'trackeep/metadata-live-independent-acceptance@1','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'verdict':'accepted_for_two_article_metadata_trial','counts':{'created':2,'retry_existing':2,'retry_created':0,'kept':2,'excluded':0,'pending':0,'fulltext_started':0},'item_checks':checks,'independent_relevance':judgements,'failure_history':'首轮预演失败仍保留blocked，根因未知；见independent-live-failure-review.json。本次成功不撤销该历史。','protection_evidence':'同一两条新建记录：首次读回、同批重跑before及复核readback的完整data相同，标签/目录/版本等未改；子项均为0。','limits':['本轮真实样本没有已有附件/笔记，因此不能宣称实测保护了含附件的旧条目；该场景证据仍来自离线合成测试与只读实现。','仅审保存的真实服务回执，未独立联网重查。','无实际排除条目；本轮有效候选清单保留2条，不能说完成了真实删除或清理。','第一页pages=262与引擎保存262-274分别来自StartPage与MedlinePgn；本审不把来源不同当身份冲突。','两个PMID及key证明本批重跑未新增，不外推全库任意并发幂等。','不涵盖全文获取、插件或全管道发布。'],'inputs':[{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths],'network_calls':0,'credential_reads':0}
out=root/'日志/metadata-validation/independent-live-acceptance.json';out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'verdict':report['verdict'],'counts':report['counts']},ensure_ascii=False))
