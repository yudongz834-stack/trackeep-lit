"""全文候选独立离线探针；原件只读，所有服务及凭证禁止。"""
import sys,copy,json,hashlib,tempfile,datetime,urllib.error,io
from pathlib import Path
from unittest.mock import patch
sys.dont_write_bytecode=True;sys.path.insert(0,r'D:/trackeep-lit')
import fitz
from lit import fulltext as f,fulltext_batch as fb,zotero
root=Path(r'D:/trackeep-lit');out=root/'日志/fulltext-validation';out.mkdir(exist_ok=True)
batch=json.loads((root/'日志/metadata-batches/20261003-145432-2b6d0965/report.json').read_text(encoding='utf-8'))
A=copy.deepcopy(batch['articles'][0]);blob=(root/'全文/42420446.pdf').read_bytes();parent='WD9F8D8E'
parent_row=next(i['readback'] for i in batch['items'] if i['pmid']==A['pmid'])
results=[]
def deny(*a,**k):raise AssertionError('offline boundary')
def pdf(first):
 doc=fitz.open();p=doc.new_page();p.insert_text((40,40),first,fontsize=9)
 for n in range(4):
  p=doc.new_page();p.insert_text((40,30),'Methods and references\n'+('\n'.join('A detailed synthetic scientific paragraph with controls and results for checking.' for _ in range(65))),fontsize=8)
 return doc.tobytes()
with patch('urllib.request.urlopen',side_effect=deny),patch('urllib.request.OpenerDirector.open',side_effect=deny),patch.object(zotero,'_load_env',side_effect=deny):
 for a in batch['articles']:
  b=(root/'全文'/(a['pmid']+'.pdf')).read_bytes();results.append({'case':'official_'+a['pmid'],'verification':f.verify_pdf(b,a)})
 synth={'pmid':'101','title':'Synthetic transplantation article','doi':'10.1000/abc'}
 for name,data in [('html',b'<html>login</html>'),('fake_magic',b'%PDF-pretend'),('wrong_title',pdf('Other unrelated study\n10.1000/abc')),('doi_prefix_collision',pdf('Synthetic transplantation article\n10.1000/abc999')),('reference_on_first_page',pdf('Different research article\n10.5555/wrong\n\nReferences\nSynthetic transplantation article\n10.1000/abc')),('supplement',pdf('Supplementary Information\nSynthetic transplantation article\n10.1000/abc'))]:
  try:r=f.verify_pdf(data,synth);results.append({'case':name,'accepted':True,'check':r})
  except Exception as e:results.append({'case':name,'accepted':False,'error':str(e)})
 for mode in ['new','existing','unrelated','pending','user_pending','wrong_parent','create_bad_parent','auth_failure','upload_failure','register_failure','exists_wrong_file','wrong_hash','parent_changed','association_changed','type_changed','deleted_after','md5_changed']:
  calls=[];events=[];key='ATTACH01';child={'key':key,'data':{'itemType':'attachment','parentItem':parent,'contentType':'application/pdf','url':'https://www.nature.com/article.pdf','tags':[{'tag':'trackeep-fulltext'}]}}
  children=[]
  if mode in ['existing','unrelated','pending','user_pending']:
   children=[copy.deepcopy(child)]
   if mode in ['existing','unrelated']:children[0]['data']['md5']='hash'
   if mode=='user_pending':children[0]['data']['tags']=[]
  class Lib:
   def get(self,path):
    calls.append(('get',path))
    if path=='/items/'+parent:
     row=copy.deepcopy(parent_row)
     if mode=='wrong_parent':row['data']['title']='Wrong'
     if mode=='parent_changed' and sum(c==('get',path) for c in calls)>1:row['data']['tags']=[{'tag':'user-added'}]
     return row
    result=copy.deepcopy(child)
    if ('file',key) in calls:
     result['data']['md5']=hashlib.md5(blob).hexdigest()
     if mode=='association_changed':result['data']['parentItem']='OTHER001'
     if mode=='type_changed':result['data']['contentType']='text/html'
     if mode=='deleted_after':result['data']['deleted']=1
     if mode=='md5_changed':result['data']['md5']='incorrect'
    return result
   def all(self,path):calls.append(('all',path));return copy.deepcopy(children)
   def file(self,k):
    calls.append(('file',k));return b'wrong bytes' if mode in ['wrong_hash','exists_wrong_file','unrelated'] else blob
   def post(self,path,body,headers=None):
    calls.append(('post',path))
    if path=='/items':
     c=copy.deepcopy(child)
     if mode=='create_bad_parent':c['data']['parentItem']='OTHER001'
     return {'successful':{'0':c},'failed':{}}
    if isinstance(body,bytes) and body.startswith(b'upload='):
     if mode=='register_failure':raise RuntimeError('register failed')
     return None
    if mode=='auth_failure':raise RuntimeError('auth failed')
    return {'exists':mode=='exists_wrong_file','url':'https://s3.amazonaws.com/upload','prefix':'','suffix':'','contentType':'application/pdf','uploadKey':'synthetic'}
   def upload_bytes(self,auth,data):
    calls.append(('upload','storage'))
    if mode=='upload_failure':raise RuntimeError('upload failed')
  try:r=f.attach(Lib(),A,parent,blob,child['data']['url'],events.append,True);results.append({'case':'attach_'+mode,'result':r['status'],'calls':calls})
  except Exception as e:results.append({'case':'attach_'+mode,'result':'error','error':str(e),'calls':calls})
 # Eligibility keeps per-item decisions authoritative; no network or credential constructor.
 original_review=json.loads((root/'日志/metadata-reviews/review-1141862b.json').read_text(encoding='utf-8'))
 for decision in ['keep','exclude','pending']:
  review=copy.deepcopy(original_review);review['items'][0]['decision']=decision
  selected=fb.eligible(review,batch)
  results.append({'case':'eligibility_'+decision,'selected':[a['pmid'] for a,k in selected]})
report={'schema':'trackeep/fulltext-independent-results@1','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'results':results,'network':0,'credentials':0,'original_pdf_writes':0}
(out/'independent-candidate-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(results,ensure_ascii=False))
