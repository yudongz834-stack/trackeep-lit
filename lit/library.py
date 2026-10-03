"""批次复核用只读 Zotero 客户端；不提供建项或永久删除接口。"""
import json
import re
import urllib.error
import urllib.request
from lit import zotero


def doi(value):
    return re.sub(r'^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)', '', value.strip(), flags=re.I).lower()


def identity(row):
    data = row.get('data', row)
    pmids = re.findall(r'(?im)^PMID:\s*(\d+)\s*$', data.get('extra', ''))
    return doi(data.get('DOI', '')), set(pmids)


def matching(rows, article):
    return [r for r in rows if (article['pmid'] in identity(r)[1] or
            (article.get('doi') and doi(article['doi']) == identity(r)[0]))]


def exact(row, article):
    d, ps = identity(row)
    data = row['data']
    nlm = re.findall(r'(?im)^NLM ID:\s*(\S+)\s*$', data.get('extra', ''))
    return (data.get('itemType') == 'journalArticle' and ps == {article['pmid']}
            and d == doi(article.get('doi', '')) and data.get('title') == article['title']
            and nlm == [article['nlm_id']])


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Library:
    def __init__(self):
        uid, key = zotero._load_env()
        self.base = f'https://api.zotero.org/users/{uid}'
        self.headers = {'Zotero-API-Key': key, 'Zotero-API-Version': '3'}

    def get(self, path):
        try:
            req = urllib.request.Request(self.base + path, headers=self.headers)
            with urllib.request.build_opener(NoRedirect).open(req, timeout=90) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            raise RuntimeError(f'Zotero 读取失败 HTTP {e.code}') from None
        except Exception:
            raise RuntimeError('Zotero 读取失败，未取得有效回执') from None

    def all(self, path):
        rows = []
        while True:
            page = self.get(path + ('&' if '?' in path else '?') + f'limit=100&start={len(rows)}')
            if not isinstance(page, list):
                raise RuntimeError('Zotero 分页格式错误')
            rows.extend(page)
            if len(page) < 100:
                if len({x['key'] for x in rows}) != len(rows):
                    raise RuntimeError('Zotero 分页出现重复，须重查')
                return rows
