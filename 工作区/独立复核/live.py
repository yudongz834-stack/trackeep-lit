import sys,json
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlparse
sys.dont_write_bytecode=True;sys.path.insert(0,r'D:/trackeep-lit')
from lit import pubmed as p
f=Path(r'D:/trackeep-lit/日志/pubmed-validation/independent-review.json');r=json.loads(f.read_text(encoding='utf-8'))
plan={'kind':'journal','journal':'Science','date':{'field':'dp','start':'2024-06-07','end':'2024-06-07'},'selection_mode':'broad','screening_location':'undecided'}
orig=p.request
urls=[]
def guard(url,**kw):
 assert urlparse(url).hostname=='eutils.ncbi.nlm.nih.gov' and not kw.get('headers') and not kw.get('data')
 urls.append(url);return orig(url,**kw)
with patch.object(p,'request',side_effect=guard):sample=p.preview(plan)
r['historical_live_sample']=sample;r['historical_live_urls']=urls
f.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'status':sample['status'],'counts':sample.get('counts'),'failure':sample.get('failure'),'journal_check':sample.get('journal_check')},ensure_ascii=False))
