"""精确键只读快照；本地 GET，无凭证、外网或修改。"""
import argparse,json,datetime,urllib.request,hashlib
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--stage',required=True);p.add_argument('--candidate',action='append',default=[]);args=p.parse_args()
assert args.stage.replace('-','').replace('_','').isalnum()
assert all(len(k)==8 and k.isalnum() for k in args.candidate)
class StopRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*a,**k):raise RuntimeError('redirect forbidden')
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),StopRedirect())
def get(suffix):
 with opener.open(urllib.request.Request('http://127.0.0.1:23119/api/users/16621589/items/'+suffix,headers={'Zotero-API-Version':'3'},method='GET'),timeout=20) as r:return json.load(r)
rows=[]
for key in ['WD9F8D8E','IU8CWQD2']+args.candidate:
 row={'key':key,'role':'protected' if key in ['WD9F8D8E','IU8CWQD2'] else 'test_copy'}
 try:
  row['parent']=get(key);row['children']=get(key+'/children');row['files']=[]
  for child in row['children']:
   enclosure=child.get('links',{}).get('enclosure',{}).get('href','')
   if enclosure.startswith('file:///'):
    path=Path(urllib.request.url2pathname(enclosure[7:]));assert path.parent.name==child['key']
    row['files'].append({'key':child['key'],'file':str(path),'exists':path.is_file(),'sha256':hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None})
 except Exception as e:row['error']=type(e).__name__+':'+str(e)
 rows.append(row)
out=Path('D:/trackeep-lit/日志/native-zotero-validation');out.mkdir(exist_ok=True)
dest=out/('independent-'+args.stage+'.json');assert not dest.exists(),'不覆盖已有证据'
dest.write_text(json.dumps({'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'mode':'local_get_only','items':rows},ensure_ascii=False,indent=2),encoding='utf-8')
print(str(dest))
