"""现行 PMC 云及普通浏览器同源读取；不导出 Cookie、不修改浏览器设置。"""
import base64,hashlib,json,urllib.request
from pathlib import Path
root=Path(__file__).resolve().parents[1]; folder=root/'日志/fulltext-validation'
review=json.loads((root/'日志/metadata-reviews/review-1141862b.json').read_text(encoding='utf-8'))
if review['status']!='review_complete' or not all(next(i for i in review['items'] if i['pmid']==p)['decision']=='keep' for p in ('42420446','42816625')):
    raise ValueError('排除或待核条目禁止下载')
meta=json.loads((folder/'pmc-metadata.json').read_text(encoding='utf-8'))
url=meta['pdf_url'].replace('s3://pmc-oa-opendata/','https://pmc-oa-opendata.s3.amazonaws.com/')
blob=urllib.request.urlopen(url,timeout=90).read()
assert hashlib.md5(blob).hexdigest()==url.split('md5=')[1] and blob.startswith(b'%PDF-')
(root/'全文/42420446.pdf').write_bytes(blob)
evidence=[{'pmid':'42420446','doi':meta['doi'],'title':meta['title'],'source':url,'bytes':len(blob),'sha256':hashlib.sha256(blob).hexdigest(),'publisher_metadata':meta}]
js='''(async()=>{const get=n=>document.querySelector('meta[name="'+n+'"]')?.content;const url=get('citation_pdf_url');const r=await fetch(url);const b=new Uint8Array(await r.arrayBuffer());let s='';for(let i=0;i<b.length;i+=16384)s+=String.fromCharCode(...b.subarray(i,i+16384));return JSON.stringify({doi:get('citation_doi'),title:get('citation_title'),source:url,final_url:r.url,status:r.status,content_type:r.headers.get('content-type'),base64:btoa(s)});})()'''
req=urllib.request.Request('http://localhost:3456/eval?target=86B42D579908C1BB6B5B16C798F0F1EB',data=js.encode(),headers={'Content-Type':'text/plain'})
wrapper=json.load(urllib.request.urlopen(req,timeout=120))
result=json.loads(wrapper['value']);raw=base64.b64decode(result.pop('base64'))
result.update(pmid='42816625',bytes=len(raw),pdf_magic=raw.startswith(b'%PDF-'),sha256=hashlib.sha256(raw).hexdigest())
if raw.startswith(b'%PDF-'):(root/'全文/42816625.pdf').write_bytes(raw)
evidence.append(result)
(folder/'official-downloads.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps([{k:v for k,v in x.items() if k!='publisher_metadata'} for x in evidence]))
