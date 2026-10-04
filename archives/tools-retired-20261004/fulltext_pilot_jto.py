# JTO 全文补全——试点 3 篇（apply 真跑：驱动 Zotero 原生「查找全文」+ 读回验证）
import json, re, sys, urllib.request

sys.path.insert(0, r'D:\trackeep-lit')
from lit.native_fulltext import execute_jobs

LOCAL = 'http://127.0.0.1:23119/api/users/0'

def get(path):
    return json.load(urllib.request.urlopen(urllib.request.Request(LOCAL + path), timeout=30))

# 1) 今天的 JTO 新条目（top、期刊文章）
items, s = [], 0
while True:
    pg = get(f'/collections/2HID2MQK/items/top?itemType=-attachment&limit=100&start={s}')
    items += pg
    if len(pg) < 100: break
    s += 100
new = [it for it in items if (it['data'].get('dateAdded') or '') >= '2026-10-03T16:00:00Z'
       and it['data'].get('itemType') == 'journalArticle']
print(f'今日新增 JTO 条目: {len(new)}')

# 2) 每篇查子附件，筛出无 PDF 的
no_pdf = []
for it in new:
    kids = get(f"/items/{it['key']}/children")
    has = any(k['data'].get('contentType') == 'application/pdf' for k in kids)
    pmid = ''
    m = re.search(r'(?im)^PMID:\s*(\d+)', it['data'].get('extra') or '')
    if m: pmid = m.group(1)
    if not has and pmid:
        no_pdf.append(it)
print(f'其中无 PDF 且有 PMID: {len(no_pdf)}')

# 3) 组任务（试点取 3；article 必须带 nlm_id——extra 栏里有，exact() 逐字段验身份）
pilot = no_pdf[:3]
def build_job(it):
    d = it['data']
    pmid = re.search(r'(?im)^PMID:\s*(\d+)', d['extra']).group(1)
    nlm = re.search(r'(?im)^NLM ID:\s*(\S+)', d['extra']).group(1)
    return {'pmid': pmid, 'parent_key': it['key'],
            'article': {'pmid': pmid, 'doi': d.get('DOI') or '', 'title': d['title'],
                        'nlm_id': nlm, 'retracted': False, 'retraction_notice': False},
            'review': {'decision': 'keep'}}
jobs = [build_job(it) for it in pilot]
for j in jobs:
    print('  试点:', j['pmid'], j['article']['title'][:50])

# 4) 执行（apply=True 真跑）
result = execute_jobs(jobs, apply=True, root=__import__('pathlib').Path(r'D:\trackeep-lit'))
print(json.dumps({'status': result['status'], 'counts': result['counts']}, ensure_ascii=False))
for x in result['items']:
    print(f"  {x['status']:<18} {x.get('pmid')} {x.get('reason','')[:60]}")
