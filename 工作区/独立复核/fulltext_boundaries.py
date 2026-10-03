"""认证头与下载资格边界补核，全部HTTP在内存替身中执行。"""
import sys,json,tempfile,io,urllib.error,hashlib,datetime
from pathlib import Path
from unittest.mock import patch
sys.dont_write_bytecode=True;sys.path.insert(0,r'D:/trackeep-lit')
from lit import fulltext as f
results=[]
class Resp:
 status=201
 def __enter__(self):return self
 def __exit__(self,*a):pass
 def read(self,*a):return b'%PDF-synthetic'
lib=object.__new__(f.AttachmentLibrary);lib.base='https://api.zotero.org/users/0';lib.headers={'Zotero-API-Key':'SYNTHETIC'}
for mode in ['allowed_redirect','wrong_domain','http_redirect']:
 calls=[]
 class Opener:
  def open(self,req,timeout):
   calls.append({'url':req.full_url,'headers':dict(req.header_items())})
   if len(calls)==1:
    url={'allowed_redirect':'https://bucket.s3.amazonaws.com/file','wrong_domain':'https://zotero.org.attacker.invalid/file','http_redirect':'http://bucket.s3.amazonaws.com/file'}[mode]
    raise urllib.error.HTTPError(req.full_url,302,'synthetic',{'Location':url},None)
   return Resp()
 with patch('urllib.request.build_opener',return_value=Opener()):
  try:lib.file('SYNTHKEY');out='accepted'
  except RuntimeError:out='rejected'
 assert len(calls)<2 or not any(k.lower()=='zotero-api-key' for k in calls[1]['headers'])
 results.append({'case':mode,'outcome':out,'request_count':len(calls),'storage_received_auth':False})
calls=[]
class Upload:
 def open(self,req,timeout):calls.append(dict(req.header_items()));return Resp()
with patch('urllib.request.build_opener',return_value=Upload()):lib.upload_bytes({'url':'https://bucket.s3.amazonaws.com/file','prefix':'','suffix':'','contentType':'application/pdf'},b'pdf')
assert not any(k.lower()=='zotero-api-key' for k in calls[0]);results.append({'case':'upload_auth_isolation','passed':True})
script=Path(r'D:/trackeep-lit/工作区/下载本批官方全文.py').read_text(encoding='utf-8-sig');prefix=script.split("assert hashlib.md5")[0]
for optimize in [0,2]:
 with tempfile.TemporaryDirectory() as td:
  root=Path(td);(root/'工作区').mkdir();(root/'日志/metadata-reviews').mkdir(parents=True);(root/'日志/fulltext-validation').mkdir(parents=True)
  (root/'日志/metadata-reviews/review-1141862b.json').write_text(json.dumps({'status':'review_complete','items':[{'pmid':'42420446','decision':'exclude'},{'pmid':'42816625','decision':'keep'}]}))
  (root/'日志/fulltext-validation/pmc-metadata.json').write_text(json.dumps({'pdf_url':'s3://pmc-oa-opendata/test.pdf'}))
  with patch('urllib.request.urlopen',side_effect=RuntimeError('OFFLINE STOP')) as req:
   try:exec(compile(prefix,'download-guard', 'exec',optimize=optimize),{'__file__':str(root/'工作区/download.py')});out='completed'
   except Exception as e:out=type(e).__name__
  results.append({'case':'excluded_download_optimize_'+str(optimize),'network_attempts':req.call_count,'outcome':out})
Path(r'D:/trackeep-lit/日志/fulltext-validation/independent-boundary-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(results))
