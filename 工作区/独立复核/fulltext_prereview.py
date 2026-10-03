"""两篇保留项全文独立验收准备；仅读取本地批次复核证据，不下载、不读凭证。"""
import json,hashlib,datetime
from pathlib import Path
root=Path(r'D:/trackeep-lit')
review=root/'日志/metadata-reviews/review-1141862b.json';r=json.loads(review.read_text(encoding='utf-8'))
expected={'42420446':'WD9F8D8E','42816625':'IU8CWQD2'}
assert r['status']=='review_complete' and set(r['effective_pmids'])==set(expected)
for a in r['items']:assert a['decision']=='keep' and a['keys']==[expected[a['pmid']]]
cases=[
('scope_keep_only','混入exclude/pending/未知PMID、被篡改effective_pmids或未完成review','文件下载和附件写入均为0；不得只信有效PMID列表而不核逐项决定'),
('scope_parent_pinned','PMID正确而父key换成另一个真实/合成存在key；父项身份漂移','下载/上传前阻断；只接受本次两个已核父项及PMID/DOI/title/NLM'),
('scope_no_new_parent','API桩捕获建journalArticle、PATCH父项、DELETE或批量库请求','无题录创建、父项修改或删除；范围仍限两篇'),
('precheck_before_download','目标父项已有可用正文PDF','先查附件并核身份；足够复用时不重复下载或建附件'),
('preexisting_unrelated','已有补充材料、不同DOI PDF、笔记或linked_url','不将它们当正文；保持每个已有子项不变'),
('source_official_redirect','官方落地页跳转CDN；HTTPS降级、非准许主机、登录页','按明确来源策略判定，未核来源不上传；不把任意重定向当官方正文'),
('source_no_credentials_leak','NCBI/出版社/对象存储请求检查全部headers与日志','不得夹带Zotero认证头、签名URL或token；服务错误文本不原样落盘'),
('format_html_as_pdf','200 OK text/html登录页、XML、伪造%PDF前缀、截断PDF','不得标PDF或上传；HTML/XML不能替代PDF通过'),
('pdf_parse_and_body','可解析的单页封面/广告、仅摘要、损坏xref、空正文','不能仅凭MIME/扩展名/魔数/能打开判定全文；不够证据保留待核'),
('pdf_first_page_identity','首页标题相同DOI不同；DOI相同标题为另篇；仅参考文献含目标DOI','拒绝错误身份；不从参考文献/补充材料提取目标后冒认'),
('pdf_unicode_layout','首页标题断行、连字符/连字/Unicode；DOI换行','合法排版变化按可追溯规范化判断；无法确认则pending，不扩大误匹配'),
('pdf_supplement','同文补充PDF有相同DOI或标题但无主文','不当主文；单PDF也不默认主文'),
('resource_limit','超大Content-Length、无长度流、压缩炸弹、读取超时','有界读取/解析，失败留证，无无穷等待或半件误成功'),
('upload_three_phases','合法PDF，建附件→授权→上传→注册→读回','每步结果可追踪；只有远端实际文件读回并核哈希后成功'),
('upload_wrong_parent','建项响应parentItem、key或文件metadata错配','不得认作目标附件；不得覆盖另一父项文件'),
('upload_partial_failure','建项成功后授权/传输/注册任一步失败','报告失败及pending key，不能标全文已完成；保留可重试状态'),
('upload_ambiguous_timeout','注册或上传成功但客户端超时，重跑发现已存在','先重查远端可用内容再决定，不额外新建重复附件'),
('upload_existing_authorization','授权返回exists=true但实际读回为空/错文件','exists不是成功证据；错哈希不通过'),
('retry_empty_child','上次留下空附件，与来源吻合但尚无文件','只能在可证明本次创建的pending附件上恢复；不能劫持用户空附件'),
('retry_same_content_new_url','相同正文hash但源URL变化、同篇两种官方URL','重跑不重复附件；哈希/身份/父项共同比较，不只按URL'),
('concurrency','两个运行均先查到0附件；用户同步新增附件或改父项','不能在竞态中重复建项或覆盖用户数据；失去身份/版本条件则停'),
('readback_integrity','远端文件长度正确但字节不同，或读回403/404','失败/待核，不报告下载上传成功；失败必须有回执'),
('relevance_change','review从keep变pending或源摘要/身份变化','不能沿用旧可下载资格；当前候选依赖需可核'),
('final_assets','成功/失败/重跑前后父项和原有children快照','父项data与原附件/笔记/标签不改；最多新增本次明确成功的主文附件')]
report={'schema':'trackeep/fulltext-independent-test-plan@1','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'awaiting_candidate_not_approved','scope':expected,'required_pdf_identity':'真实可解析正文；首页DOI与标题对应保留文献。文件类型检查与正文身份检查分开。','review_source':{'path':str(review),'sha256':hashlib.sha256(review.read_bytes()).hexdigest()},'oracles':[{'id':n,'case':c,'expected':e,'execution':'pending_candidate'} for n,c,e in cases],'safety':{'network_calls':0,'credential_reads':0,'zotero_mutations':0,'candidate_implementation_participation':False},'limits':['本文件只制定独立验收，没有审核尚未提交的源码，也未证明两篇官方PDF实际可得。','离线验证后仍须限定两父项的小样真实上传及重跑证据；无全文获取途径时允许明确unavailable，不得HTML/XML冒充PDF。','不批准插件、全库附件清理、新题录或父项改写。']}
out=root/'日志/fulltext-validation';out.mkdir(parents=True,exist_ok=True);f=out/'independent-test-plan.json';f.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'status':report['status'],'cases':len(cases),'report':str(f)},ensure_ascii=False))
