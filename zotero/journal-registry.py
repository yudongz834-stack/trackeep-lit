# journal-registry.py — 期刊×月份登记表（纯机器现算的派生视图，不另记账）
# 数据源：Zotero 库（本地 API 优先，云端兜底）+ PubMed eutils（近45天有无新货）
# 输出：D:\workbench\期刊登记表-<date>.md + 控制台摘要
import json, os, re, sys, time, urllib.request, urllib.parse
from collections import defaultdict
from datetime import date

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

TABLE = r'E:\Trackeep-Obsidian\00-系统\期刊来源表.md'
OUT = rf'D:\workbench\期刊登记表-{date.today():%Y%m%d}.md'
UA = {'User-Agent': 'Mozilla/5.0 trackeep-lit-registry'}

# ---------- 1. 期刊表 ----------
journals = []  # (来源分类, 全名, TA缩写, 目录名)
for line in open(TABLE, encoding='utf-8'):
    m = re.match(r'^\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|', line)
    if not m:
        continue
    grp, full, abbr, dn = (m.group(i).strip().strip('`') for i in range(1, 5))
    if grp in ('胸部肿瘤与胸外科', '流行病学与公共卫生', '临床医学综合', '医学AI与数字医学', '基础与转化医学'):
        journals.append((grp, full, abbr, dn))
print(f'期刊表：{len(journals)} 刊（家：E:\\Trackeep-Obsidian）')

# ---------- 2. Zotero 条目（本地优先，云端兜底） ----------
def get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or UA)
    return json.load(urllib.request.urlopen(req, timeout=30))

local, base, hdr_z = False, '', None
env = {}
for ln in open(os.path.join(os.environ['USERPROFILE'], r'.config\trackeep\secrets\zotero.env'), encoding='utf-8'):
    if '=' in ln and not ln.strip().startswith('#'):
        k, v = ln.strip().split('=', 1)
        env[k.strip()] = v.strip()
base_cloud = f"https://api.zotero.org/users/{env['ZOTERO_USER_ID']}"
hdr_cloud = {'Zotero-API-Key': env['ZOTERO_API_KEY'], **UA}

def zget(path):
    """本地优先，任何失败永久切云端"""
    global local, base
    if local or base == '':
        try:
            u = ('http://127.0.0.1:23119/api/users/0' if not base else base) + path
            r = get(u)
            local = True
            base = 'http://127.0.0.1:23119/api/users/0'
            return r
        except Exception:
            local = False
            base = base_cloud
    return get(base_cloud + path, hdr_cloud)

try:
    zget('/collections?limit=1')
    print('数据源：', '本地 API' if local else '云端 API')
except Exception as e:
    print('数据源全断：', e); sys.exit(1)

items, start = [], 0
while True:
    page = zget(f'/items?limit=100&start={start}&format=json')
    items += page
    if len(page) < 100:
        break
    start += 100
print(f'条目拉取：{len(items)} 条')

# 分区名→key（含年月子分区归属：条目挂在年月叶上，要算进期刊）
cols = zget('/collections?limit=100')
name2key, key2name, parent = {}, {}, {}
for c in cols:
    k, n = c['key'], c['data']['name']
    name2key[n] = k
    key2name[k] = n
    parent[k] = c['data'].get('parentCollection') or False

dn_set = {j[3] for j in journals}

def journal_of(key):
    """沿父链向上，落在第一个期刊名上就停（防止爬过头到五大类）"""
    seen = set()
    while key and key not in seen:
        seen.add(key)
        n = key2name.get(key)
        if n in dn_set:
            return n
        key = parent.get(key)
    return ''

MON = {m: i + 1 for i, m in enumerate(
    ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'])}

def parse_ym(s):
    if not s:
        return None
    s = str(s).strip()
    m = re.match(r'^(\d{4})[-/ ](\d{1,2})', s)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    m = re.match(r'^(\d{4})[-/ ]?([A-Za-z]{3})', s)
    if m and m.group(2).lower() in MON:
        return (int(m.group(1)), MON[m.group(2).lower()])
    m = re.match(r'^(\d{4})(\d{2})$', s)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    return None

jm = defaultdict(lambda: defaultdict(int))   # 目录名 -> (年,月) -> 数
no_date = defaultdict(int)
for it in items:
    d = it.get('data', {})
    if d.get('itemType') in ('attachment', 'note', 'annotation') or it.get('meta', {}).get('creatorSummary') is None and d.get('itemType') not in ('journalArticle', 'review'):
        pass
    if d.get('itemType') not in ('journalArticle', 'review'):
        continue
    names = {journal_of(k) for k in d.get('collections', []) if k in key2name} - {''}
    ym = parse_ym(d.get('date'))
    for n in names:
        if ym:
            jm[n][ym] += 1
        else:
            no_date[n] += 1


# ---------- 3. PubMed 近45天有无新货 ----------
today = date.today()
import datetime as _dt
_now = _dt.datetime.now()  # 报表/警报用带时分的时间戳（date.today() 无时间分量，审核 LOW-1）
def pubmed_recent(ta):
    q = urllib.parse.quote(f'"{ta}"[TA]')
    u = f'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&retmode=json&reldate=45&datetype=edat&term={q}&tool=trackeep-lit-registry'
    try:
        return int(get(u)['esearchresult'].get('count', 0))
    except Exception:
        return -1

rows = []
for grp, full, abbr, dn in journals:
    months = jm.get(dn, {})
    latest = max(months) if months else None
    total = sum(months.values())
    pm = pubmed_recent(abbr)
    time.sleep(0.35)
    lag = None
    if latest:
        lag = (today.year - latest[0]) * 12 + (today.month - latest[1])
    rows.append(dict(grp=grp, dn=dn, total=total, latest=latest, lag=lag, pm=pm,
                     no_date=no_date.get(dn, 0), months=months))

# ---------- 4. 输出 ----------
def fmt_ym(ym):
    return f'{ym[0]}-{ym[1]:02d}' if ym else '—'

have = sorted([r for r in rows if r['total']], key=lambda r: r['latest'], reverse=True)
empty = [r for r in rows if not r['total']]
behind = [r for r in have if r['pm'] > 0 and (r['lag'] or 0) >= 2]  # 有新货且库里最新月落后≥2月

L = [f'# 期刊×月份登记表（{_now:%Y-%m-%d %H:%M} 现算）', '',
     f'> 数据源＝Zotero 库（{len(items)} 条目）＋ PubMed 近45天计数。机器现算派生视图，永不失准；重跑＝python D:\\trackeep-lit\\zotero\\journal-registry.py', '',
     '## 摘要', '',
     f'- 在用期刊：**{len(have)} / {len(rows)}**（空架子 {len(empty)} 刊）',
     f'- PubMed 有新货而库里落后≥2个月：**{len(behind)} 刊**',
     f'  ' + '、'.join(f"{r['dn']}({fmt_ym(r['latest'])})" for r in sorted(behind, key=lambda r: -(r['lag'] or 0))) if behind else '  无', '',
     '## 逐刊明细（按最新月降序；仅列有货刊）', '',
     '| 期刊 | 最新月 | 落后(月) | 条目 | 无日期条 | PubMed近45天 | 月份分布 |',
     '|---|---|---|---|---|---|---|']
for r in have:
    dist = ' '.join(f'{fmt_ym(m)}×{n}' for m, n in sorted(r['months'].items(), reverse=True)[:8])
    more = '…' if len(r['months']) > 8 else ''
    L.append(f"| {r['dn']} | {fmt_ym(r['latest'])} | {r['lag']} | {r['total']} | {r['no_date']} | {r['pm']} | {dist}{more} |")
L += ['', f'## 空架子（{len(empty)} 刊，尚无任何条目）', '', '、'.join(r['dn'] for r in empty), '']
open(OUT, 'w', encoding='utf-8').write('\n'.join(L))
print('登记表已写:', OUT)

# 周闹钟警报面（每周计划任务跑；全跟齐也留时间戳证明活着）
# 审核整改：pm<0＝PubMed 拉取失败≠「跟齐」，单独报「结论不可信」防假安心
ALERT = r'D:\workbench\期刊雷达-警报.txt'
pm_failed = [r for r in rows if r['pm'] < 0]
if pm_failed:
    open(ALERT, 'w', encoding='utf-8').write(
        f'⚠ PubMed 拉取失败 {len(pm_failed)} 刊（{_now:%Y-%m-%d %H:%M} 扫）——本次「跟齐/落后」结论不可信，需重跑：\n' +
        '\n'.join(f"  {r['dn']}" for r in pm_failed) + '\n')
    print(f'⚠ PubMed 拉取失败 {len(pm_failed)} 刊，警报已写:', ALERT)
elif behind:
    open(ALERT, 'w', encoding='utf-8').write(
        f'⚠ 落后刊 {len(behind)} 本（{_now:%Y-%m-%d %H:%M} 扫）：\n' +
        '\n'.join(f"  {r['dn']} 最新{fmt_ym(r['latest'])} PubMed近45天{r['pm']}条" for r in sorted(behind, key=lambda r: -(r['lag'] or 0))) +
        '\n处置：对落后刊喊「lit 补货 <刊名>」\n')
    print('⚠ 警报已写:', ALERT)
else:
    open(ALERT, 'w', encoding='utf-8').write(f'✅ 全部跟齐（{_now:%Y-%m-%d %H:%M} 扫）\n')
    print('✅ 全部跟齐，警报文件已刷新:', ALERT)

print('\n===== 摘要 =====')
print(f'在用 {len(have)}/{len(rows)} 刊；空架子 {len(empty)} 刊')
for r in have:
    flag = ' ⚠落后' if r in behind else ''
    print(f"  {r['dn']:<28} 最新 {fmt_ym(r['latest'])}  共{r['total']:>3}条  PubMed45天 {r['pm']:>3}{flag}")
