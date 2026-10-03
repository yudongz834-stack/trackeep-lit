"""本机原生全文编排：只读 API 核验，写操作仅由原生界面桥执行。"""
import json
import copy
import hashlib
import re
import subprocess
import time
import urllib.parse
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from pathlib import Path

from lit.fulltext import LIMIT, verify_pdf as _verify_pdf
from lit.library import NoRedirect, exact, doi
from lit.fulltext import norm

ROOT = Path(__file__).resolve().parents[1]


def official_read(url, limit=LIMIT, stage='official_read', events=None):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname not in ('pmc.ncbi.nlm.nih.gov', 'pmc-oa-opendata.s3.amazonaws.com', 'www.nature.com') or parsed.username or parsed.password:
        raise ValueError('全文来源不在已核官方域中')
    opener = urllib.request.build_opener(NoRedirect)
    for attempt in range(1, 3):
        event = {'stage': stage, 'host': parsed.hostname, 'path': parsed.path, 'attempt': attempt}
        try:
            with opener.open(urllib.request.Request(url, headers={'User-Agent': 'trackeep-lit/1.0'}), timeout=45) as response:
                blob = response.read(limit + 1)
                event.update(http_status=response.status, outcome='read')
            if len(blob) > limit:
                raise ValueError('官方响应超过大小限制')
            if events is not None:
                events.append(event)
            return blob
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            status = error.code if isinstance(error, urllib.error.HTTPError) else None
            retry = attempt < 2 and (status is None or status in (429, 502, 503, 504))
            event.update(http_status=status, outcome='retry' if retry else 'failed')
            if events is not None:
                events.append(event)
            if retry:
                time.sleep(1)
                continue
            raise RuntimeError('官方来源读取失败：阶段=' + stage + '，HTTP=' + str(status or 'network') + '；不绕过访问限制') from None


def official_fallback(article, root, events=None):
    """现行 PMC Cloud API；只请求单篇的官方元数据与主文 PDF。"""
    try:
        records = json.loads(official_read('https://pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/?' + urllib.parse.urlencode(
            {'ids': article['pmid'], 'idtype': 'pmid', 'format': 'json', 'tool': 'trackeep-lit'}), 1024 * 1024, 'pmc_id_conversion', events)).get('records', [])
    except RuntimeError:
        if not doi(article['doi']).startswith('10.1038/'):
            raise
        records = []
    records = [r for r in records if str(r.get('pmid')) == article['pmid'] and doi(r.get('doi', '')) == doi(article['doi'])]
    sources = []
    if len(records) == 1 and re.fullmatch(r'PMC\d+', records[0].get('pmcid', '')):
        pmcid = records[0]['pmcid']
        base = 'https://pmc-oa-opendata.s3.amazonaws.com/'
        listing = ET.fromstring(official_read(base + '?' + urllib.parse.urlencode({'list-type': '2', 'prefix': pmcid + '.', 'delimiter': '/'}), 1024 * 1024, 'pmc_version_listing', events))
        if listing.findtext('{*}IsTruncated') == 'true':
            raise ValueError('PMC 版本列表未取齐')
        prefixes = [n.text for n in listing.findall('{*}CommonPrefixes/{*}Prefix')]
        for prefix in prefixes:
            if not re.fullmatch(re.escape(pmcid) + r'\.\d+/', prefix or ''):
                raise ValueError('PMC 版本路径异常')
            meta = json.loads(official_read(base + prefix + prefix.rstrip('/') + '.json', 1024 * 1024, 'pmc_article_metadata', events))
            if (str(meta.get('pmid')) != article['pmid'] or doi(meta.get('doi', '')) != doi(article['doi']) or
                    norm(meta.get('title', '')) != norm(article['title']) or meta.get('is_retracted')):
                raise ValueError('PMC 元数据身份或撤稿状态冲突')
            source = meta.get('pdf_url') or ''
            if source.startswith('s3://pmc-oa-opendata/'):
                sources.append((bool(meta.get('is_manuscript')), source.replace('s3://pmc-oa-opendata/', base), meta))
    # 现有 Nature 官方文章 PDF 路由；其他出版社由 Zotero 原生解析器处理。
    if doi(article['doi']).startswith('10.1038/'):
        sources.append((True, 'https://www.nature.com/articles/' + urllib.parse.quote(doi(article['doi']).split('/', 1)[1], safe='') + '.pdf', {}))
    last_failure = None
    for _, source, meta in sorted(sources, key=lambda x: x[0]):
        try:
            blob = official_read(source, stage='official_pdf_download', events=events)
            expected_md5 = urllib.parse.parse_qs(urllib.parse.urlsplit(source).query).get('md5', [])
            if expected_md5 and expected_md5 != [hashlib.md5(blob).hexdigest()]:
                raise ValueError('PMC 文件哈希不符')
            check = verify_pdf(blob, article)
            folder = Path(root) / '全文' / '原生补充'
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / (article['pmid'] + '-' + check['sha256'][:16] + '.pdf')
            if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() != check['sha256']:
                raise ValueError('既有补充文件发生变化，禁止覆盖')
            if not path.exists():
                with path.open('xb') as stream:
                    stream.write(blob)
            return {'path': str(path), 'source': source, 'sha256': check['sha256'], 'publisher_metadata': meta}
        except RuntimeError as error:
            last_failure = error
            continue
    if last_failure:
        raise last_failure
    return None


def verify_pdf(blob, article):
    try:
        return _verify_pdf(blob, article)
    except ModuleNotFoundError:
        result = subprocess.run([r'E:\Python\python.exe', str(ROOT / 'lit/native_pdf.py'), json.dumps(article)],
            input=blob, capture_output=True, timeout=60, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if result.returncode:
            raise ValueError('PDF 解析或身份校验未通过')
        return json.loads(result.stdout.decode('utf-8'))


class LocalLibrary:
    def get(self, suffix):
        if not re.fullmatch(r'/items/[A-Z0-9]{8}(?:/children(?:\?limit=100&start=\d+)?)?', suffix):
            raise ValueError('本地读取范围无效')
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect)
        try:
            with opener.open('http://127.0.0.1:23119/api/users/0' + suffix, timeout=20) as response:
                return json.load(response)
        except Exception:
            raise RuntimeError('本机 Zotero 未就绪或本地读取失败') from None

    def children(self, key):
        rows = []
        while True:
            page = self.get('/items/' + key + '/children?limit=100&start=' + str(len(rows)))
            if not isinstance(page, list):
                raise ValueError('附件列表格式异常')
            rows.extend(page)
            if len({x['key'] for x in rows}) != len(rows):
                raise ValueError('附件分页重复，不能确认读取完整')
            if len(page) < 100:
                return rows

    def file(self, child):
        uri = child.get('links', {}).get('enclosure', {}).get('href', '')
        parsed = urllib.parse.urlsplit(uri)
        if parsed.scheme != 'file' or parsed.netloc not in ('', 'localhost'):
            raise ValueError('附件尚无本机文件')
        path = Path(urllib.request.url2pathname(parsed.path))
        if child['data'].get('linkMode') != 'linked_file' and (path.parent.name != child['key'] or path.parent.parent.name != 'storage'):
            raise ValueError('附件不是 Zotero 管理的存储副本')
        if not path.is_file() or path.stat().st_size > LIMIT:
            raise ValueError('本机附件不存在或超过限制')
        return path.read_bytes()


class NativeBridge:
    """固定项目桥，不把内部 Zotero 函数冒充外部接口。"""
    def call(self, action, parent, article, path=None):
        payload = {'action': action, 'parent_key': parent, 'title': article['title'], 'doi': article['doi'], 'pmid': article['pmid'], 'path': str(path) if path else None}
        result = subprocess.run([r'E:\Python\python.exe', str(ROOT / 'lit/native_ui.py')],
            input=json.dumps(payload), text=True, encoding='utf-8', capture_output=True,
            timeout=100, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        try:
            value = json.loads(result.stdout)
        except Exception:
            raise RuntimeError('原生界面桥未返回有效结果') from None
        if result.returncode or not value.get('ok'):
            raise RuntimeError(value.get('reason', '原生界面动作未完成'))
        return value

    def find_full_text(self, parent, article):
        return self.call('find', parent, article)

    def attach_file(self, parent, article, path):
        return self.call('attach', parent, article, path)


def inspect(local, article, parent):
    row = local.get('/items/' + parent)
    if row.get('key') != parent or row['data'].get('deleted') or not exact(row, article):
        raise ValueError('本机父题录身份冲突或尚未同步，保留待核')
    children = local.children(parent)
    checked, invalid = [], []
    for child in children:
        data = child['data']
        if data.get('deleted') or data.get('itemType') != 'attachment':
            continue
        if data.get('parentItem') != parent:
            raise ValueError('附件父项异常')
        if data.get('contentType') != 'application/pdf':
            continue
        try:
            checked.append({'key': child['key'], 'pdf': verify_pdf(local.file(child), article)})
        except (ValueError, OSError):
            invalid.append(child['key'])
    return row, children, checked, invalid


def ensure(article, parent, apply=False, local=None, bridge=None, fallback=None, poll_seconds=45, root=None, events=None):
    if not re.fullmatch(r'[A-Z0-9]{8}', parent):
        raise ValueError('父项键无效')
    local, bridge = local or LocalLibrary(), bridge or NativeBridge()
    before, children, verified, invalid = inspect(local, article, parent)
    before, children = copy.deepcopy(before), copy.deepcopy(children)
    events = events if events is not None else []
    events.append({'stage': 'before', 'children': [c['key'] for c in children], 'unverified': invalid})
    if verified:
        return {'status': 'existing_verified', **verified[0], 'verified_count': len(verified), 'events': events}
    if invalid:
        return {'status': 'pending_attachment', 'reason': '已有未核附件，先修复或复核，禁止再添重复副本', 'events': events}
    if not apply:
        return {'status': 'ready', 'events': events}
    bridge.find_full_text(parent, article)
    events.append({'stage': 'native_find_triggered'})
    deadline = time.monotonic() + poll_seconds
    while True:
        after, current, verified, invalid = inspect(local, article, parent)
        clean = lambda r: {k: v for k, v in r['data'].items() if k not in ('version', 'dateModified')}
        if clean(before) != clean(after):
            raise ValueError('原生动作后父题录内容变化，停止待核')
        if verified:
            return {'status': 'created_verified', **verified[0], 'route': 'native_find', 'events': events}
        if time.monotonic() >= deadline:
            break
        time.sleep(1)
    if current != children:
        return {'status': 'pending_attachment', 'reason': '原生操作已产生附件但文件未通过验证，不再追加', 'events': events}
    events.append({'stage': 'native_find_no_verified_file', 'wait_seconds': poll_seconds, 'children': [c['key'] for c in current]})
    if not fallback:
        fallback = official_fallback(article, root or ROOT, events)
    if not fallback:
        return {'status': 'missing_fulltext', 'reason': '原生查找未取得可核全文，尚无已核官方本地文件', 'events': events}
    path = Path(fallback['path']).resolve()
    source = urllib.parse.urlsplit(fallback['source'])
    if source.scheme != 'https' or source.hostname not in ('pmc-oa-opendata.s3.amazonaws.com', 'www.nature.com') or not fallback.get('sha256'):
        raise ValueError('补充文件缺少 HTTPS 官方来源与校验记录')
    if not path.is_file() or path.stat().st_size > LIMIT:
        raise ValueError('补充文件不存在或超过限制')
    check = verify_pdf(path.read_bytes(), article)
    if check['sha256'] != fallback['sha256']:
        raise ValueError('补充文件哈希已变化')
    events.append({'stage': 'official_file_verified', 'source': fallback['source'], 'sha256': check['sha256'],
                   'publisher_metadata': fallback.get('publisher_metadata', {})})
    # 再次读取消除下载等待期间其他入口已完成的情况。
    _, current, verified, invalid = inspect(local, article, parent)
    if verified:
        return {'status': 'existing_verified', **verified[0], 'events': events}
    if current != children or invalid:
        raise ValueError('附件集合变化，停止追加')
    bridge.attach_file(parent, article, path)
    events.append({'stage': 'native_stored_copy_triggered', 'sha256': check['sha256']})
    deadline = time.monotonic() + poll_seconds
    while True:
        after, _, verified, _ = inspect(local, article, parent)
        if clean(before) != clean(after):
            raise ValueError('附件导入后父题录内容变化')
        matching = [v for v in verified if v['pdf']['sha256'] == check['sha256']]
        if matching:
            return {'status': 'created_verified', **matching[0], 'route': 'native_stored_copy', 'source': fallback['source'], 'events': events}
        if time.monotonic() >= deadline:
            return {'status': 'pending_attachment', 'reason': '原生导入已触发，文件尚未验证，不盲目重发', 'events': events}
        time.sleep(1)


def execute_jobs(jobs, apply=False, root=None, progress=None, bridge=None, local=None):
    if not jobs:
        return {'status':'no_kept_items','items':[], 'counts':{'scope':0}, 'reason':'没有保留项，未执行全文操作'}
    items = []
    for job in jobs:
        item = {'pmid': job['pmid'], 'parent_key': job['parent_key'], 'events': []}
        review = job.get('review', {})
        decision = review.get('decision') if isinstance(review, dict) else review
        try:
            if decision != 'keep' or job['article'].get('retracted') or job['article'].get('retraction_notice'):
                item.update(status='pending_review', reason='仅已复核保留项可获取全文')
            else:
                item.update(ensure(job['article'], job['parent_key'], apply, local, bridge, job.get('fallback'), root=root, events=item['events']))
        except Exception as error:
            item.update(status='failed', reason=str(error) if isinstance(error, (ValueError, RuntimeError)) else '本机全文操作异常，保留待核')
        items.append(item)
        if progress:
            progress(item)
    counts = {state: sum(x['status'] == state for x in items) for state in sorted({x['status'] for x in items})}
    good = {'existing_verified', 'created_verified'} | ({'ready'} if not apply else set())
    return {'status': ('complete' if apply else 'preview_only') if all(x['status'] in good for x in items) else 'partial_failure', 'items': items, 'counts': counts}
