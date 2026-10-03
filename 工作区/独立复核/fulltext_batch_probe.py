"""批处理失败留证和锁竞争，网络/凭证全部硬拦。"""
import sys,json,tempfile,copy,hashlib,io,contextlib,msvcrt
from pathlib import Path
from unittest.mock import patch
sys.dont_write_bytecode=True;sys.path.insert(0,r'D:/trackeep-lit')
from lit import fulltext_batch as b,zotero
root=Path(r'D:/trackeep-lit');original=json.loads((root/'日志/metadata-reviews/review-1141862b.json').read_text(encoding='utf-8'));batch_raw=Path(original['batch_source']).read_bytes();results=[]
class Fake:
 pass
with patch('urllib.request.urlopen',side_effect=AssertionError('offline')),patch('urllib.request.OpenerDirector.open',side_effect=AssertionError('offline')),patch.object(zotero,'_load_env',side_effect=AssertionError('credentials forbidden')):
 for mode in ['excluded_all','pending_all','batch_tamper','download_identity_wrong','file_hash_wrong']:
  with tempfile.TemporaryDirectory() as td:
   t=Path(td);(t/'全文').mkdir();rev=copy.deepcopy(original);bp=t/'batch.json';bp.write_bytes(batch_raw);rev['batch_source']=str(bp)
   if mode in ['excluded_all','pending_all']:
    for i in rev['items']:i['decision']='exclude' if mode=='excluded_all' else 'pending'
   if mode=='batch_tamper':bp.write_bytes(batch_raw+b' ')
   rp=t/'review.json';rp.write_text(json.dumps(rev));dp=t/'downloads.json'
   ds=[]
   for i in json.loads(batch_raw)['articles']:
    blob=b'not a pdf';(t/'全文'/(i['pmid']+'.pdf')).write_bytes(blob)
    ds.append({'pmid':i['pmid'],'title':i['title'],'doi':'WRONG' if mode=='download_identity_wrong' else i['doi'],'source':'https://www.nature.com/synthetic.pdf','sha256':'wrong'})
   dp.write_text(json.dumps(ds))
   with patch.object(b,'ROOT',t),patch.object(b,'attach',side_effect=AssertionError('should not attach')) as attach:r=b.run(rp,dp,t,True,Fake())
   results.append({'case':mode,'status':r['status'],'attach_calls':attach.call_count,'persisted':(t/'report.json').exists(),'counts':r.get('counts')})
 with tempfile.TemporaryDirectory() as td:
  t=Path(td);folder=t/'日志/fulltext-batches';folder.mkdir(parents=True);lock=folder/'attachment.lock'
  lock.write_bytes(b'0')
  with lock.open('r+b') as f:
   msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
   try:
    with patch.object(b,'ROOT',t),patch.object(sys,'argv',['fulltext','--review','fake','--downloads','fake']),contextlib.redirect_stdout(io.StringIO()):
     try:outcome={'exit_code':b.main()}
     except BaseException as e:outcome=type(e).__name__+':'+str(e)
   finally:f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
  results.append({'case':'competing_process_lock','outcome':outcome,'reports':[json.loads(p.read_text(encoding='utf-8')) for p in folder.glob('*/report.json')]})
(root/'日志/fulltext-validation/independent-batch-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(results,ensure_ascii=False))

