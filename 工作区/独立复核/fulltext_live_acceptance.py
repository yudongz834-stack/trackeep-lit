"""现场回执只读验收：无服务调用，无凭证读取。"""
import json,hashlib,re,datetime
from pathlib import Path
import fitz
root=Path('D:/trackeep-lit')
paths={'create':'日志/fulltext-batches/20261003-151747-7ee932e7/report.json','retry':'日志/fulltext-batches/20261003-152244-de96ea4a/report.json','downloads':'日志/fulltext-validation/official-downloads.json','metadata':'日志/metadata-batches/20261003-145432-2b6d0965/report.json','review':'日志/metadata-reviews/review-1141862b.json','gate':'日志/fulltext-validation/independent-review.json'}
data={k:json.loads((root/v).read_text(encoding='utf-8')) for k,v in paths.items()}
c,t,m,r=data['create'],data['retry'],data['metadata'],data['review']
assert c['status']==t['status']=='complete' and c['apply'] and t['apply']
assert c['counts']['created_verified']==2 and t['counts']['existing_verified']==2
assert t['counts']['created_verified']==0 and c['counts']['failed']==t['counts']['failed']==0
assert all(e['stage']=='before' for e in t['events'])
assert len(c['items'])==len(t['items'])==len(m['articles'])==2
assert all(x['decision']=='keep' for x in r['items'])
clean=lambda row:{k:v for k,v in row['data'].items() if k not in ('version','dateModified')}
norm=lambda s:''.join(x for x in s.casefold() if x.isalnum())
results=[]
for a in m['articles']:
 p=a['pmid'];ci=next(i for i in c['items'] if i['pmid']==p);ti=next(i for i in t['items'] if i['pmid']==p)
 assert ci['key']==ti['key'] and ci['parent']==ti['parent']
 old=next(i['readback'] for i in m['items'] if i['pmid']==p)
 before=next(e for e in c['events'] if e['stage']=='before' and e['parent']['key']==ci['parent'])
 after=next(e for e in c['events'] if e['stage']=='verified' and e['key']==ci['key'])
 again=next(e for e in t['events'] if e['parent']['key']==ci['parent'])
 assert clean(old)==clean(before['parent'])==clean(after['parent_after'])==clean(again['parent'])
 assert before['children']==[] and len(again['children'])==1
 att=after['attachment_after']; child=again['children'][0]
 assert att['key']==child['key']==ci['key'] and clean(att)==clean(child)
 assert att['data']['parentItem']==ci['parent'] and att['data']['contentType']=='application/pdf' and not att['data'].get('deleted')
 blob=(root/'全文'/(p+'.pdf')).read_bytes();sha=hashlib.sha256(blob).hexdigest();md5=hashlib.md5(blob).hexdigest()
 download=next(x for x in data['downloads'] if x['pmid']==p)
 assert download['sha256']==sha and download['doi']==a['doi'] and norm(download['title'])==norm(a['title'])
 assert ci['source']==ti['source']==download['source']
 assert att['data']['md5']==md5
 for pdf in [ci['pdf'],ti['pdf'],before['pdf'],after['pdf'],again['pdf']]:
  assert pdf['sha256']==sha and pdf['md5']==md5 and pdf['pages']==37 and pdf['bytes']==len(blob)
 with fitz.open(stream=blob,filetype='pdf') as doc:
  texts=[page.get_text() for page in doc]
  assert len(texts)==37 and norm(a['title']) in norm(texts[0][:800])
  assert a['doi'].lower() in {v.rstrip('.,;)') for v in re.findall(r'10\.\d{4,9}/[-._;()/:a-z0-9]+',texts[0].lower())}
  assert sum(map(len,texts))==ci['pdf']['text_characters']
 results.append({'pmid':p,'parent':ci['parent'],'attachment':ci['key'],'pages':37,'sha256':sha,'parent_all_data_unchanged_except_version_dateModified':True,'preexisting_children':0,'retry_children':1,'same_attachment_reused':True})
report={'schema':'trackeep-independent/fulltext-live-acceptance@1','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'verdict':'本批两篇全文附件实际试运行验收通过','items':results,'counts':{'metadata_created':2,'postreview_keep':2,'postreview_exclude':0,'postreview_pending':0,'official_pdf':2,'attachments_created':2,'retry_existing':2,'retry_created':0,'failures_in_successful_fulltext_runs':0},'evidence_sha256':{v:hashlib.sha256((root/v).read_bytes()).hexdigest() for v in paths.values()},'boundaries':['独立重新解析本地 PDF 并核对全部页面文本与身份；服务端文件读回依赖受离线门禁验证的执行器现场回执，本复核未再次访问网络。','现场父项前后 data 全字段一致，仅允许 version/dateModified 推进；两篇原有子项均为零，不能声称旧附件笔记保留已获实际样本验证。','排除/待核零下载、失败重试、错误身份和既有资料保护主要由此前离线合成反例覆盖。','重跑现场仅见两份 before 事件与 existing_verified，子项键及文件哈希相同，无新建事件。','未核本地 Zotero 同步状态；云端回执通过不等于桌面同步已完成。','不外推其他刊物、任意全文获取、插件发布或全库清理；早期题录 dry-run 不明失败仍保留在原阶段证据。'],'network_calls':0,'credential_reads':0,'implementation_writes':0}
(root/'日志/fulltext-validation/independent-live-acceptance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'verdict':report['verdict'],'counts':report['counts']},ensure_ascii=False))
