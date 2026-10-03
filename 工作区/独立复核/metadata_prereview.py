"""原型只读审阅与独立验收矩阵；不加载引擎、不读取凭证、不发网络请求。"""
import json,hashlib,datetime
from pathlib import Path
engine=Path(r'C:/Users/yudon/AppData/Local/Temp/trackeep-literature-engine/zotero-import.ps1')
source=engine.read_text(encoding='utf-8-sig');lines=source.splitlines()
def line(term):return next(i for i,s in enumerate(lines,1) if term in s)
rows=[
('identity_single','指定一篇PMID，EFetch恰一篇且与已核验DOI/title/NLM一致','只允许该身份进入POST；单条回执仍为数组'),
('identity_multi_reordered','指定两篇，EFetch逆序返回','按身份匹配；不得按返回位置把字段接错'),
('identity_wrong_missing_duplicate','错误、遗漏、重复PMID分别注入','任何写请求前拒绝；不得只比较数量'),
('identity_doi_drift','PMID相同，EFetch DOI与核验报告不一致','写前阻断或显式待核，零POST'),
('identity_title_drift','PMID/DOI相同但题名换成另一研究','写前阻断或显式待核，零POST'),
('identity_nlm_drift','PMID相同但NLM ID换刊或缺失','写前阻断，不能仅接受Journal参数名称'),
('identity_unicode_markup','合法题名含XML内联标记、Unicode与引号','按声明规范化保留正确身份，不损坏POST题名'),
('collection_missing_wrong','目标key不存在、存在但对应另一目录分别注入','零题录POST；不静默落全库或错目录'),
('collection_duplicate_names','同名目录两条，未提供锁定key','待核/阻断，不猜目录'),
('existing_same_identity','既有匹配PMID/DOI且有附件、引用和标签','不新增、不PATCH、不移回收站，完整既有对象保持原样'),
('existing_trashed','回收站中已存在相同身份','不静默复活，不新增副本，回执说明'),
('existing_conflict','同DOI异PMID、同PMID异DOI分别注入','冲突待核，不能当确定重复或写新副本'),
('existing_doi_normalization','既有DOI使用HTTPS DOI URL、大小写和空白变化','不因表现形式不同重复导入'),
('title_only_similarity','不同PMID/DOI但标题相同；仅无DOI的标题疑似','不得按标题自动合并或清理；疑似须可追踪'),
('response_key_mismatch','POST回执index正确但返回数据PMID/DOI或key不匹配','不得报告该预期条目已确认；不能进入清理白名单'),
('response_partial_malformed','一成功一失败、successful缺失、越界index、重复key分别注入','失败/未知可追踪；只确认核对过的新建key；不记假成功台账'),
('retry_ambiguous_timeout','POST服务端已成功但客户端超时，下次读库已有条目','重试不产生重复；身份和可清理归属不猜'),
('receipt_cleanup_scope','把既有key混入新建列表或提供额外待清理key','禁止清理既有项；仅本批明确新建且审查决定排除的key可逆处理'),
('cleanup_race','新建条目在复核后已被用户编辑或加附件','不覆盖并发资产；失败须可查，不永久删除'),
('stage_order','导入→题录审查→可逆清理全程','本阶段不发全文请求、不创建附件、不触插件；未知相关性保留待核')]
findings=[
 {'id':'META-PRE-01','severity':'B1','line':line('if ($cands.Count -ne $expectedPmids.Count'),'evidence':'写前只比较PMID集合，参数块无已核验DOI/title/NLM快照约束；候选未采NLM ID。','consequence':'相同PMID下返回错误/漂移题录仍可进入写口。'},
 {'id':'META-PRE-02','severity':'B1','line':line("$cm = @($cols"),'evidence':'显式CollectionKey分支仅查key存在，不核对目录名称/目标身份。','consequence':'存在但错误目录key可被接受。'},
 {'id':'META-PRE-03','severity':'B1','line':line('function Cand-Items'),'evidence':'items回执只含pmid/doi/title/type/status等，无Zotero新建key；confirmed按successful属性名索引slice，不核返回对象身份。','consequence':'不能单凭回执建立新建项可逆清理边界。'},
 {'id':'META-PRE-04','severity':'B1','line':line('$inLib ='),'evidence':'DOI命中或PMID命中即dup；没有双标识冲突分支。','consequence':'不同论文的标识冲突会被隐藏成确定重复。'}]
report={'schema':'trackeep/metadata-independent-prereview@1','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'verdict':'prototype_not_approved_pending_candidate_validation','engine':str(engine),'sha256':hashlib.sha256(engine.read_bytes()).hexdigest(),'mode':'static_read_only_and_test_design','contract':'D:/trackeep-lit/PROJECT-CONTRACT.md；R2独立复核/对抗/失败可追踪，PI本次特定阶段授权限制优先','findings':findings,'offline_oracles':[{'id':name,'input':inp,'expected':out,'execution':'pending_candidate'} for name,inp,out in rows],'safety':{'engine_executed':False,'credential_access':False,'network':False,'real_library_writes':False,'product_modified':False},'limits':['静态缺陷不是动态事故证据；候选版本到达后才用拦截全部服务/凭证的合成环境逐项运行。','本阶段只核少量精确题录导入/入库后审查/可逆清理，不批准全文、插件或全库清理。']}
folder=Path(r'D:/trackeep-lit/日志/metadata-validation');folder.mkdir(parents=True,exist_ok=True);dest=folder/'independent-prereview.json';dest.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'report':str(dest),'findings':len(findings),'pending_oracles':len(rows)},ensure_ascii=False))
