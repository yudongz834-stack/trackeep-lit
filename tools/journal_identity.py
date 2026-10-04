# journal_identity.py — 期刊身份注册表生成器（合并役 2026-10-04，PI「合并，按标准规范来」）
# 分域单源：收藏口径正本＝E:\Trackeep-Obsidian\00-系统\期刊来源表.md（人编）；官方身份＝NLM Catalog
#   逐条核验（机器取，缓存 .project/nlm-identity.json，每条附来源链接）。本工具拼合两域生成
#   .project/pubmed-journals.json（引擎消费；遗留七刊主刊条目保留、重叠刊别名并流）。
# 用法：
#   E:\Python\python.exe tools/journal_identity.py           # 生成（离线：表×缓存）
#   E:\Python\python.exe tools/journal_identity.py --check   # 漂移闸：重生比对磁盘，不一致退出 1
#   E:\Python\python.exe tools/journal_identity.py --fetch   # 联网刷新缓存（表刊缺身份/需重核时）
import io, json, re, sys, time, urllib.parse
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
ROOT = Path(__file__).resolve().parents[1]
TABLE = Path(r'E:\Trackeep-Obsidian\00-系统\期刊来源表.md')
CACHE = ROOT / '.project/nlm-identity.json'
TARGET = ROOT / '.project/pubmed-journals.json'
GROUPS = ('胸部肿瘤与胸外科', '流行病学与公共卫生', '临床医学综合', '医学AI与数字医学', '基础与转化医学')
LEGACY_MAINS = {'Nature', 'Science', 'Cell', 'Lancet'}  # 不在表内的遗留七刊主刊（NEJM/JAMA/BMJ 由表接管）


def load_table():
    rows = []
    for ln in io.open(TABLE, encoding='utf-8-sig'):
        m = re.match(r'^\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|', ln)
        if not m:
            continue
        grp, full, abbr, dn = (m.group(i).strip().strip('`') for i in range(1, 5))
        if grp in GROUPS:
            rows.append({'name': full, 'abbr': abbr, 'dir': dn})
    return rows


def fetch_missing(rows, cache):
    from lit.pubmed import request, BASE
    got = []
    for r in rows:
        if r['abbr'] in cache:
            continue
        q = urllib.parse.urlencode(dict(db='nlmcatalog', term=f'"{r["abbr"]}"[Title Abbreviation]', retmode='json', retmax=2))
        raw, _ = request(BASE + 'esearch.fcgi?' + q)
        res = json.loads(raw).get('esearchresult', {})
        if str(res.get('count')) != '1' or len(res.get('idlist', [])) != 1:
            print(f'  ⚠ 待核（命中 {res.get("count")} 条）: {r["abbr"]}')
            continue
        uid = res['idlist'][0]
        raw, _ = request(BASE + 'efetch.fcgi?' + urllib.parse.urlencode(dict(db='nlmcatalog', id=uid, retmode='xml')))
        rec = ET.fromstring(raw)
        nlm = rec.findtext('.//NlmUniqueID')
        if not nlm:
            print(f'  ⚠ 待核（无 NlmUniqueID）: {r["abbr"]}')
            continue
        cache[r['abbr']] = {'nlm_id': nlm, 'ta': rec.findtext('.//MedlineTA') or r['abbr'],
                            'source': 'https://www.ncbi.nlm.nih.gov/nlmcatalog/' + uid}
        got.append(r['abbr'])
        time.sleep(0.4)
    return got


def build():
    rows = load_table()
    cache = json.loads(CACHE.read_text(encoding='utf-8')) if CACHE.exists() else {}
    legacy = []
    if TARGET.exists():
        try:
            legacy = json.loads(TARGET.read_text(encoding='utf-8')).get('journals', [])
        except Exception:
            legacy = []
    records, missing = [], []
    for r in rows:
        c = cache.get(r['abbr'])
        if not c:
            missing.append(r['abbr'])
            continue
        aliases, seen = [], set()
        old = [x for x in legacy if x.get('ta') == c['ta']]
        for a in [r['name'], r['abbr'], r['dir']] + [a for x in old for a in x.get('aliases', [])]:
            k = a.casefold()
            if a and k not in seen:
                seen.add(k)
                aliases.append(a)
        rec = {'name': r['name'], 'ta': c['ta'], 'nlm_id': c['nlm_id'], 'aliases': aliases,
               'issn': next((x.get('issn', []) for x in old if x.get('issn')), []),
               'source': c['source']}
        records.append(rec)
    covered = {x['ta'] for x in records}
    for x in legacy:  # 遗留七刊主刊原样保留（表外的）
        if x.get('name') in LEGACY_MAINS and x.get('ta') not in covered:
            records.append(x)
    doc = {'verified_on': date.today().isoformat(),
           'generated_by': 'tools/journal_identity.py（收藏口径＝期刊来源表；身份＝NLM Catalog 缓存，勿手编本文件）',
           'journals': records}
    return doc, missing


def main():
    if '--fetch' in sys.argv:
        cache = json.loads(CACHE.read_text(encoding='utf-8')) if CACHE.exists() else {}
        got = fetch_missing(load_table(), cache)
        CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding='utf-8')
        print(f'联网刷新：新取 {len(got)} 条，缓存共 {len(cache)} 条')
    doc, missing = build()
    if missing:
        print('⚠ 表刊缺身份（先跑 --fetch）：', '、'.join(missing))
        sys.exit(2)
    text = json.dumps(doc, ensure_ascii=False, indent=1)
    if '--check' in sys.argv:
        disk = TARGET.read_text(encoding='utf-8') if TARGET.exists() else ''
        if disk.strip() == text.strip():
            print(f'--check PASS（{len(doc["journals"])} 条身份在册，与表一致）')
        else:
            print('--check FAIL：磁盘 json 与重生结果不一致（表或缓存已变），重跑生成')
            sys.exit(1)
    else:
        TARGET.write_text(text + '\n', encoding='utf-8')
        print(f'已生成 {TARGET}（{len(doc["journals"])} 条；含遗留七刊主刊 {sum(1 for x in doc["journals"] if x.get("name") in LEGACY_MAINS)} 条）')


if __name__ == '__main__':
    main()
