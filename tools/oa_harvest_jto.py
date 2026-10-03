# oa_harvest_jto.py — JTO 新批 45 篇开放获取层补全文（层①，PI 2026-10-04 令）
# A 路：PMC OA 直连（复用 lit 官方域白名单 + 身份核 + sha256）
# B 路：EuropePMC fullTextUrlList 的 pdf 型开放链接（下载后过 verify_pdf 严验）
# 挂接：lit.fulltext.attach（查重→建壳→官方协议上传→读回核验）；一篇失败不拦全批
import sys, json, re, time, urllib.request, urllib.parse
from pathlib import Path

sys.path.insert(0, r'D:\trackeep-lit')
from lit.fulltext import attach, AttachmentLibrary, LIMIT
from lit.native_fulltext import official_fallback

LOCAL = 'http://127.0.0.1:23119/api/users/0'
ROOT = Path(r'D:\trackeep-lit')
UA = {'User-Agent': 'Mozilla/5.0 trackeep-lit-oa/1.0'}


def lget(p, timeout=30):
    return json.load(urllib.request.urlopen(urllib.request.Request(LOCAL + p), timeout=timeout))


# --- 1. 目标：JTO 新批无 PDF 条目 ---
items, s = [], 0
while True:
    pg = lget(f'/collections/2HID2MQK/items/top?itemType=-attachment&limit=100&start={s}')
    items += pg
    if len(pg) < 100:
        break
    s += 100
targets = []
for it in items:
    d = it['data']
    if d.get('itemType') != 'journalArticle' or (d.get('dateAdded') or '') < '2026-10-03T16:00:00Z':
        continue
    m = re.search(r'(?im)^PMID:\s*(\d+)', d.get('extra') or '')
    n = re.search(r'(?im)^NLM ID:\s*(\S+)', d.get('extra') or '')
    if not (m and n and d.get('DOI')):
        continue
    kids = lget(f"/items/{it['key']}/children")
    if any(k['data'].get('contentType') == 'application/pdf' for k in kids):
        continue
    targets.append({'key': it['key'], 'pmid': m.group(1), 'nlm_id': n.group(1),
                    'doi': d['DOI'], 'title': d['title']})
print(f'目标（新批无 PDF）: {len(targets)} 篇', flush=True)

lib = AttachmentLibrary()


# --- 2. B 路：EuropePMC 开放 pdf 链接 ---
def epmc_pdf_urls(doi_str):
    q = urllib.parse.quote(f'DOI:"{doi_str}"')
    u = f'https://www.ebi.ac.uk/europepmc/webservices/rest/search?query={q}&format=json&resultType=core'
    try:
        d = json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30))
    except Exception:
        return []
    hits = d.get('resultList', {}).get('result', [])
    if not hits:
        return []
    h = hits[0]
    oa = h.get('inEPMC') == 'Y' or h.get('isOpenAccess') == 'Y' or h.get('openAccessYn') == 'Y'
    if not oa:
        return []
    out = []
    for doc in (h.get('fullTextUrlList') or {}).get('fullTextUrl', []):
        if doc.get('documentStyle') == 'pdf' and (doc.get('availability') or '').lower().startswith('open'):
            out.append(doc['url'])
    return out


def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        blob = r.read(LIMIT + 1)
    if len(blob) > LIMIT or not blob.startswith(b'%PDF-'):
        return None
    return blob


# --- 3. 逐篇：A 路 → B 路 → 严验挂接 ---
stats = {}
rows = []
for t in targets:
    article = {'pmid': t['pmid'], 'doi': t['doi'], 'title': t['title'], 'nlm_id': t['nlm_id']}
    events = []
    got = None
    a_err = ''
    try:
        fb = official_fallback(article, ROOT, events)
        if fb:
            blob = Path(fb['path']).read_bytes()
            if blob.startswith(b'%PDF-'):
                got = ('PMC直连', fb['source'], blob)
    except Exception as e:
        a_err = str(e)[:70]
    if not got:
        try:
            for u in epmc_pdf_urls(t['doi'])[:3]:
                blob = fetch(u)
                if blob:
                    got = ('EuropePMC', u, blob)
                    break
        except Exception:
            pass
        time.sleep(0.3)
    if not got:
        st = '无开放版' + (f'（PMC:{a_err}）' if '冲突' in a_err else '')
    else:
        route, source, blob = got
        try:
            r = attach(lib, article, t['key'], blob, source, lambda e: events.append(e), apply=True)
            st = f"挂接成功[{route}] {r['status']}"
        except ValueError as e:
            st = f'严验未过，弃挂: {str(e)[:60]}'
        except Exception as e:
            st = f'挂接异常: {str(e)[:60]}'
    stats[st.split('（')[0].split('[')[0]] = stats.get(st.split('（')[0].split('[')[0], 0) + 1
    rows.append((t['pmid'], st, t['title'][:40]))
    print(f"  {t['pmid']}  {st}  | {t['title'][:36]}", flush=True)

print('\n===== 汇总 =====')
for k, v in sorted(stats.items(), key=lambda x: -x[1]):
    print(f'  {k}: {v}')
