# fulltext_sweep_inbox.py v2 — 全文收件箱扫箱归档（SOP 第4步第6分步执行体）
# v2 修三病（首跑实测）：①bytes 先读再开 fitz（不再锁文件挪不动）②DOI 用正则集合精确匹配
#   （归一化包含会把 DOI 前缀相近的认错人）③可注入验证器＝DOI 主尺＋辅助证据版
# （Elsevier 版式：社论天生 2 页/8000 字够不着研究文标准；PubMed 题名与纸质排版有措辞差）
import hashlib, json, re, sys, urllib.request
from pathlib import Path

sys.path.insert(0, r'D:\trackeep-lit')
import fitz
from lit.fulltext import attach, AttachmentLibrary, LIMIT
from lit.library import doi as doi_norm

INBOX = Path(r'E:\全文收件箱')
ARCHIVE = INBOX / '已归档'
LOCAL = 'http://127.0.0.1:23119/api/users/0'
COLLECTION = '2HID2MQK'  # J Thorac Oncol
SINCE = '2026-10-03T16:00:00Z'
REPORT = Path(r'D:\workbench\全文归档对账-20261004.md')
DOI_RE = re.compile(r'10\.\d{4,9}/[-._;()/:a-z0-9]+')


def lget(p):
    return json.load(urllib.request.urlopen(urllib.request.Request(LOCAL + p), timeout=30))


def norm(s):
    return re.sub(r'[^\w]', '', s.lower(), flags=re.UNICODE)


def verify_elsevier(blob, article):
    """DOI 主尺验证器：身份证（DOI）必须原文印在 PDF 前两页；标题降为辅助。
    保留：PDF 魔数/大小/加密/补充材料拒收；社论短文放行（≥2 页或 ≥1000 字符）。"""
    if not blob.startswith(b'%PDF-') or len(blob) > LIMIT:
        raise ValueError('文件不是 PDF 或超过大小限制')
    doc = fitz.open(stream=blob, filetype='pdf')
    try:
        if doc.is_encrypted or len(doc) < 1:
            raise ValueError('PDF 加密或无页面')
        texts = [p.get_text() for p in doc]
        front2 = ''.join(texts[:2])
        if re.search(r'supplementary\s+(information|material|appendix)|supporting\s+information', front2[:600], re.I):
            raise ValueError('补充材料不能作主文')
        ids = {x.rstrip('.,;)') for x in DOI_RE.findall(front2.lower())}
        if doi_norm(article['doi']) not in ids:
            raise ValueError('DOI 未印在 PDF 前两页（身份不成立）')
        if sum(map(len, texts)) < 1000 or len(doc) < 2:
            raise ValueError('内容量不足（<2 页或 <1000 字符），疑非全文')
        return {'pages': len(doc), 'text_characters': sum(map(len, texts)),
                'sha256': hashlib.sha256(blob).hexdigest(), 'md5': hashlib.md5(blob).hexdigest(),
                'bytes': len(blob), 'identity': 'doi_printed_in_first_two_pages'}
    finally:
        doc.close()


# --- 1. 目标清单（全部 45 篇：含已挂好的——它们的收件箱原件直接归档）---
items, s = [], 0
while True:
    pg = lget(f'/collections/{COLLECTION}/items/top?itemType=-attachment&limit=100&start={s}')
    items += pg
    if len(pg) < 100:
        break
    s += 100
by_doi, by_key = {}, {}
for it in items:
    d = it['data']
    if d.get('itemType') != 'journalArticle' or (d.get('dateAdded') or '') < SINCE:
        continue
    pmid = re.search(r'(?im)^PMID:\s*(\d+)', d.get('extra') or '')
    nlm = re.search(r'(?im)^NLM ID:\s*(\S+)', d.get('extra') or '')
    if not (pmid and nlm):
        continue
    kids = lget(f"/items/{it['key']}/children")
    has_pdf = any(k['data'].get('contentType') == 'application/pdf' for k in kids)
    cr = (d.get('creators') or [{}])[0]
    author = cr.get('lastName') or cr.get('name') or 'Unknown'
    year = (d.get('date') or '20xx')[:4]
    short = re.sub(r'[\\/:*?"<>|\r\n]+', ' ', d['title'])
    short = re.sub(r'\s+', ' ', short).strip()[:60].rstrip(' .,;:-')
    t = {'key': it['key'], 'pmid': pmid.group(1), 'nlm_id': nlm.group(1),
         'doi': doi_norm(d.get('DOI')), 'title': d['title'], 'has_pdf': has_pdf,
         'fname': f"{author}-{year}-{short}.pdf", 'n20': norm(d['title'])[:20]}
    if t['doi']:
        by_doi[t['doi']] = t
    by_key[it['key']] = t
print(f'目标: {len(by_key)} 篇（含已挂 {sum(t["has_pdf"] for t in by_key.values())}）', flush=True)

lib = AttachmentLibrary()
files = sorted(INBOX.glob('*.pdf'))
print(f'收件箱 PDF: {len(files)} 份', flush=True)


def to_archive(f):
    """单份制（PI 2026-10-04 定）：正本在 Zotero＋云端，原件验后即删；逐名留痕防对不上。"""
    f.unlink()
    deleted_log.append(f.name)


deleted_log = []


filed, already, bad, moved_fail = 0, 0, [], []
unrecognized, attached_keys = [], set()

for f in files:
    blob = f.read_bytes()
    try:
        doc = fitz.open(stream=blob, filetype='pdf')
        front2 = ''.join(p.get_text() for p in doc[:2]).lower()
        doc.close()
    except Exception as e:
        unrecognized.append((f.name, f'PDF 解析失败: {str(e)[:40]}'))
        continue
    ids = {x.rstrip('.,;)') for x in DOI_RE.findall(front2)}
    hit = None
    for d in ids:
        if d in by_doi:
            hit = by_doi[d]
            break
    if not hit:  # 标题兜底：题名前 20 归一字出现
        n2 = norm(front2)
        for t in by_key.values():
            if t['n20'] and t['n20'] in n2:
                hit = t
                break
    if not hit:
        unrecognized.append((f.name, '前两页无本批 DOI/题名'))
        continue
    if hit['has_pdf'] or hit['key'] in attached_keys:
        to_archive(f)
        already += 1
        print(f"  [已挂过·归档] {f.name[:46]}", flush=True)
        continue
    article = {'pmid': hit['pmid'], 'doi': hit['doi'], 'title': hit['title'], 'nlm_id': hit['nlm_id']}
    try:
        r = attach(lib, article, hit['key'], blob, f.name, lambda e: None, apply=True,
                   filename=hit['fname'], verify=verify_elsevier)
        attached_keys.add(hit['key'])
        filed += 1
        print(f"  [{r['status']}] {hit['fname'][:56]}", flush=True)
        to_archive(f)
    except ValueError as e:
        unrecognized.append((f.name, f'验不过: {str(e)[:50]}'))
        print(f"  [验不过·留原地] {f.name[:46]} — {str(e)[:40]}", flush=True)
    except Exception as e:
        bad.append((f.name, str(e)[:60]))
        print(f"  [挂接异常·留原地] {f.name[:46]} — {str(e)[:50]}", flush=True)

missing = [t for t in by_key.values() if not t['has_pdf'] and t['key'] not in attached_keys]
L = [f'# 全文归档对账 v3（扫描 {len(files)} 份·单份制）', '',
     f'- 本轮挂接成功：**{filed}** 份（原件已删，正本在 Zotero＋云端）',
     f'- 已在前轮挂好、原件即删：**{already}** 份',
     f'- 验不过（留原地）：**{len(unrecognized)}** 份', f'- 挂接异常（留原地待复核）：**{len(bad)}** 份',
     f'- 45 篇清单仍缺：**{len(missing)}** 篇', '',
     '## 本轮删除原件清单（逐名）'] + [f'- `{n}`' for n in deleted_log] + \
    ['', '## 验不过/认不出'] + [f'- `{n}` — {r}' for n, r in unrecognized] + ['', '## 挂接异常'] + \
    [f'- `{n}` — {r}' for n, r in bad] + ['', '## 仍缺清单（重挂用 DOI）'] + \
    [f'- {t["doi"]} — {t["title"][:60]}' for t in missing]
REPORT.write_text('\n'.join(L), encoding='utf-8')
print(f'\n对账已写: {REPORT}')
print(f'汇总: 挂接 {filed} / 前轮已挂归档 {already} / 验不过 {len(unrecognized)} / 异常 {len(bad)} / 仍缺 {len(missing)}')
