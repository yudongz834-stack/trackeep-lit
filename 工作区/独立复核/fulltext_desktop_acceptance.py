"""只读本地 Zotero API 与其明确返回的 PDF；不读取配置或凭证。"""
import json,hashlib,datetime,urllib.request,urllib.parse,re
from pathlib import Path
import fitz
root=Path('D:/trackeep-lit');out=root/'日志/fulltext-validation'
before=json.loads((out/'desktop-before-relink.json').read_text(encoding='utf-8'))
live=json.loads((out/'independent-live-acceptance.json').read_text(encoding='utf-8'))
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*a,**k):raise RuntimeError('禁止重定向')
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
calls=[]
def get(path):
 assert path.startswith('/api/users/16621589/items/')
 calls.append(path)
 with opener.open(urllib.request.Request('http://127.0.0.1:23119'+path,headers={'Zotero-API-Version':'3'},method='GET'),timeout=20) as r:
  raw=r.read()
 try:return json.loads(raw)
 except ValueError:return raw.decode().strip()
rows=[]
for old in before['items']:
 pmid=old['pmid'];parent=old['parent'];key=old['attachment'];base='/api/users/16621589/items/'
 p=get(base+parent);children=get(base+parent+'/children');a=get(base+key);url=get(base+key+'/file/view/url')
 assert p['data']==old['parent_snapshot']['data']
 assert len(children)==1 and children[0]['key']==key
 assert a['key']==key and a['data']['parentItem']==parent and a['data']['contentType']=='application/pdf'
 assert not a['data'].get('deleted') and a['data']['itemType']=='attachment'
 attachment_changes={k:{'before':old['attachment_snapshot']['data'].get(k),'after':a['data'].get(k)} for k in set(a['data'])|set(old['attachment_snapshot']['data']) if a['data'].get(k)!=old['attachment_snapshot']['data'].get(k)}
 print(json.dumps({'attachment_changes':attachment_changes},ensure_ascii=False))
 assert set(attachment_changes)<= {'lastRead','version'}
 if isinstance(url,dict):raise AssertionError('unexpected file URL shape')
 u=urllib.parse.urlparse(url);assert u.scheme=='file' and not u.netloc
 path=Path(urllib.request.url2pathname(u.path))
 assert path.parent.name==key and path.suffix.lower()=='.pdf'
 blob=path.read_bytes();sha=hashlib.sha256(blob).hexdigest()
 official=root/'全文'/(pmid+'.pdf');assert sha==hashlib.sha256(official.read_bytes()).hexdigest()
 prior=next(i for i in live['items'] if i['pmid']==pmid);assert sha==prior['sha256']
 with fitz.open(stream=blob,filetype='pdf') as doc:
  text=[page.get_text() for page in doc];assert len(text)==37
 norm=lambda s:''.join(c for c in s.casefold() if c.isalnum())
 assert norm(p['data']['title']) in norm(text[0][:800])
 assert p['data']['DOI'].lower() in set(re.findall(r'10\.\d{4,9}/[-._;()/:a-z0-9]+',text[0].lower()))
 rows.append({'pmid':pmid,'parent':parent,'attachment':key,'parent_all_data_equal':True,'attachment_changes':attachment_changes,'children':len(children),'file':str(path),'sha256':sha,'pages':len(text),'bytes':len(blob),'previous_file_existed':old.get('file_exists'),'status':'verified'})
report={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'verdict':'桌面本批两篇交付通过','items':rows,'new_attachment_count':0,'original_attachment_keys_preserved':True,'read_only_local_api_calls':calls,'credential_reads':0,'writes_to_zotero':0,'limits':['父项全部data未变；附件允许并逐项记录lastRead和version变化，其他data全部一致。','仅验证本机原附件键内文件可读、与官方原件哈希一致。WebDAV远端文件上传与其他设备同步未验证。','API调用只允许127.0.0.1、GET、指定两父项及两附件，禁止代理和重定向。']}
(out/'independent-desktop-acceptance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'verdict':report['verdict'],'items':rows},ensure_ascii=False))
