"""PubMed 只读检索预览。规则入口在项目 AGENTS.md；不加载 Zotero 或模型凭证。"""
import argparse
import copy
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
# 小于官方 10000 上限，避免服务端把 retmax=10000 调成 9999。
LIMIT = 9999


def request(url, *, data=None, headers=None, method=None, timeout=60):
    """仅公共 NCBI 请求；节流及有限重试，不返回原始异常请求信息。"""
    for attempt in range(3):
        time.sleep(.36)
        try:
            req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read(), dict(r.headers)
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise RuntimeError(f"NCBI HTTP {e.code}") from None
        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise RuntimeError("NCBI 连接失败或超时") from None
        time.sleep(1 + attempt * 2)


def journals():
    return json.loads((ROOT / '.project/pubmed-journals.json').read_text(encoding='utf-8'))['journals']


def resolve_journal(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 200 or any(c in value for c in '"[]\r\n'):
        raise ValueError('期刊名为空或含检索控制字符')
    hits = [j for j in journals() if value.casefold() in {a.casefold() for a in j['aliases'] + [j['ta']]}]
    if len(hits) == 1:
        return hits[0]
    result = {}
    for field in ('Title Abbreviation','ISSN','Title'):
        query = f'"{value}"[{field}]'
        raw, _ = request(BASE + 'esearch.fcgi?' + urllib.parse.urlencode(dict(db='nlmcatalog', term=query, retmode='json', retmax=2)))
        result = json.loads(raw).get('esearchresult', {})
        if str(result.get('count')) != '0':
            break
    if str(result.get('count')) != '1' or len(result.get('idlist', [])) != 1:
        raise ValueError('NLM 期刊目录未找到唯一身份，请提供准确刊名、缩写或 ISSN')
    uid = result['idlist'][0]
    raw, _ = request(BASE + 'efetch.fcgi?' + urllib.parse.urlencode(dict(db='nlmcatalog', id=uid, retmode='xml')))
    records = ET.fromstring(raw).findall('NLMCatalogRecord')
    if len(records) != 1 or not records[0].findtext('NlmUniqueID') or not records[0].findtext('MedlineTA'):
        raise ValueError('NLM 期刊目录缺少身份或标准缩写')
    node = records[0]
    return {'name': node.findtext('TitleMain/Title', ''), 'ta': node.findtext('MedlineTA'),
            'nlm_id': node.findtext('NlmUniqueID'), 'aliases': [value],
            'source': 'https://www.ncbi.nlm.nih.gov/nlmcatalog/' + uid}


def esearch(query, report):
    params = dict(db='pubmed', retmode='json', retmax=LIMIT, term=query, tool='trackeep-lit')
    event = {'query': query, 'requested_at': dt.datetime.now(dt.timezone.utc).isoformat(),
             'parameters': params}
    report['searches'].append(event)
    raw, _ = request(BASE + 'esearch.fcgi?' + urllib.parse.urlencode(params))
    event['sha256'] = hashlib.sha256(raw).hexdigest()
    try:
        data = json.loads(raw)
    except ValueError:
        event['unparsed_response'] = raw.decode('utf-8', errors='replace')
        raise RuntimeError('PubMed 回执不是有效 JSON') from None
    event['response'] = data
    if not isinstance(data, dict) or not isinstance(data.get('esearchresult'), dict):
        raise RuntimeError('PubMed 回执结构异常')
    d = data.get('esearchresult', {})
    for name in ('warninglist', 'errorlist'):
        values = d.get(name, {})
        if not isinstance(values, dict) or any(not isinstance(v, list) or any(not isinstance(s, str) for s in v) for v in values.values()):
            raise RuntimeError('PubMed 错误或警告字段结构异常')
    if data.get('error') or d.get('ERROR') or any(d.get('errorlist', {}).values()):
        raise RuntimeError('PubMed 报检索错误；完整回执已保存，须改式重查')
    if any(d.get('warninglist', {}).values()):
        report['review_reasons'].append('PubMed 检索警告，须核对本次回执')
    if not isinstance(d.get('querytranslation'), str) or not d['querytranslation'].strip():
        raise RuntimeError('PubMed 未返回检索解释，不能确认执行口径')
    value, ids = d.get('count'), d.get('idlist')
    if isinstance(value, bool) or not isinstance(value, (str, int)) or not re.fullmatch(r'[0-9]+', str(value)):
        raise RuntimeError('PubMed Count 格式异常')
    count = int(value)
    if not isinstance(ids, list) or any(not isinstance(p, str) or not re.fullmatch(r'[1-9][0-9]*', p) for p in ids):
        raise RuntimeError('PubMed 数量或 PMID 格式异常')
    if len(ids) != len(set(ids)) or (count <= LIMIT and len(ids) != count):
        raise RuntimeError('PubMed PMID 数量不齐或重复，拒绝截断结果')
    return count, ids


def prepare(plan):
    if not isinstance(plan, dict):
        raise ValueError('检索计划必须为 JSON 对象')
    allowed={'kind','journal','date','selection_mode','screening_location','known_pmids',
             'filter_query','filter_reason','query','concepts','all_time','pmids'}
    if set(plan)-allowed:
        raise ValueError('计划含不支持的字段，拒绝静默忽略：'+', '.join(sorted(set(plan)-allowed)))
    for name in ('journal', 'query', 'filter_query', 'filter_reason'):
        if name in plan and not isinstance(plan[name], str):
            raise ValueError(f'{name} 必须为字符串')
    if 'all_time' in plan and not isinstance(plan['all_time'], bool):
        raise ValueError('all_time 必须为布尔值')
    if plan.get('kind') not in ('journal', 'topic', 'articles'):
        raise ValueError('kind 必须为 journal、topic 或 articles')
    if plan.get('screening_location') not in ('undecided', 'before-import', 'after-import', 'split'):
        raise ValueError('必须明确筛选位置，尚未决定请填 undecided')
    if plan['kind'] == 'articles':
        ids = plan.get('pmids')
        if (not isinstance(ids, list) or not ids or len(ids) != len(set(ids)) or
                any(not isinstance(p, str) or not re.fullmatch(r'[1-9][0-9]*', p) for p in ids)):
            raise ValueError('指定文章须提供不重复的 PMID 列表')
        if any(plan.get(k) for k in ('journal','date','query','filter_query','selection_mode','all_time')):
            raise ValueError('指定文章不能暗带期刊、日期或过滤条件')
        return ' OR '.join(p + '[PMID]' for p in ids), None, None, None
    date = plan.get('date')
    if date is not None:
        if not isinstance(date, dict):
            raise ValueError('date 必须为日期对象')
        if set(date) != {'field','start','end'}:
            raise ValueError('date 必须且只能含 field/start/end')
        if date.get('field') not in ('dp', 'epdat', 'ppdat', 'crdt', 'edat'):
            raise ValueError('必须明确合法日期字段')
        lo, hi = dt.date.fromisoformat(date['start']), dt.date.fromisoformat(date['end'])
        if lo > hi or plan.get('all_time'):
            raise ValueError('日期区间倒置或与 all_time 冲突')
    else:
        if plan['kind'] == 'journal' or plan.get('all_time') is not True:
            raise ValueError('期刊采集必须给日期；主题无时间限制须显式 all_time=true')
        lo = hi = None
    journal = resolve_journal(plan['journal']) if plan.get('journal') else None
    if plan['kind'] == 'journal':
        if journal is None or plan.get('selection_mode') not in ('broad', 'query-filtered'):
            raise ValueError('必须明确期刊与 broad/query-filtered 模式；没有全局默认')
        clause = f'"{journal["ta"]}"[TA]'
        extra = plan.get('filter_query', '').strip()
        if plan['selection_mode'] == 'query-filtered':
            if not extra or not plan.get('filter_reason'):
                raise ValueError('前端过滤必须提供完整过滤式与理由')
            clause += f' AND ({extra})'
        elif extra:
            raise ValueError('broad 模式不能暗带过滤式')
        if plan.get('query'):
            raise ValueError('期刊模式用 filter_query，不能暗带 query')
    else:
        clause = plan.get('query', '').strip()
        concepts = plan.get('concepts')
        if not clause or not isinstance(concepts, list) or not concepts or any(not isinstance(c, dict) or not isinstance(c.get('name'), str) or not c['name'].strip() for c in concepts):
            raise ValueError('主题检索须给英文检索式及概念拆分记录')
        if plan.get('filter_query') or plan.get('selection_mode'):
            raise ValueError('主题过滤须完整写进 query，不能使用期刊模式字段')
        clause = f'({clause})'
        if journal:
            clause += f' AND "{journal["ta"]}"[TA]'
    known = plan.get('known_pmids', [])
    if not isinstance(known, list) or any(not isinstance(p, str) or not re.fullmatch(r'[1-9][0-9]*', p) for p in known):
        raise ValueError('known_pmids 必须是 PMID 字符串列表')
    return clause, lo, hi, journal


def collect(clause, lo, hi, field, report):
    query = clause if lo is None else f'({clause}) AND ("{lo:%Y/%m/%d}"[{field}] : "{hi:%Y/%m/%d}"[{field}])'
    count, ids = esearch(query, report)
    if count <= LIMIT:
        return set(ids)
    if lo is None or lo == hi:
        raise RuntimeError('结果超过单批上限且无法继续拆日期；须缩小范围，不报已取齐')
    mid = lo + (hi-lo)//2
    left = collect(clause, lo, mid, field, report)
    right = collect(clause, mid+dt.timedelta(days=1), hi, field, report)
    merged = left | right
    report['partitions'].append({'query': query, 'parent_count': count, 'left_count': len(left),
                                 'right_count': len(right), 'overlap': len(left & right), 'union_count': len(merged)})
    if len(merged) != count:
        raise RuntimeError('日期分片并集与父查询 Count 不同；可能索引变化或日期边界问题，须重查')
    return merged


def metadata(ids, report=None):
    out = {}
    for start in range(0, len(ids), 150):
        chunk = ids[start:start+150]
        raw, _ = request(BASE + 'efetch.fcgi?' + urllib.parse.urlencode(dict(db='pubmed', retmode='xml', id=','.join(chunk), tool='trackeep-lit')))
        root = ET.fromstring(raw)
        rows = []
        for a in root.findall('PubmedArticle'):
            def text(path):
                node = a.find(path)
                return ''.join(node.itertext()).strip() if node is not None else ''
            pmid = text('./MedlineCitation/PMID')
            types = [n.text or '' for n in a.findall('./MedlineCitation/Article/PublicationTypeList/PublicationType')]
            links = [{'type': n.get('RefType'), 'pmid': n.findtext('PMID', ''), 'source': n.findtext('RefSource', '')}
                     for n in a.findall('./MedlineCitation/CommentsCorrectionsList/CommentsCorrections')]
            dates = [ET.tostring(n, encoding='unicode') for path in ('./MedlineCitation/Article/Journal/JournalIssue/PubDate',
                     './MedlineCitation/Article/ArticleDate', './PubmedData/History/PubMedPubDate') for n in a.findall(path)]
            date_sources = {}
            for name, path in [('electronic', './MedlineCitation/Article/ArticleDate[@DateType="Electronic"]'),
                               ('issue', './MedlineCitation/Article/Journal/JournalIssue/PubDate')]:
                nodes = a.findall(path)
                values = [ET.tostring(n, encoding='unicode') for n in nodes]
                present = any(''.join(n.itertext()).strip() for n in nodes)
                date_sources[name] = {'status':'reported' if present else 'missing', 'xml':values}
            rows.append(pmid)
            if pmid in out:
                raise RuntimeError('EFetch 返回重复 PMID，拒绝覆盖')
            out[pmid] = {'pmid': pmid, 'title': text('./MedlineCitation/Article/ArticleTitle'),
              'abstract': '\n'.join(''.join(n.itertext()) for n in a.findall('./MedlineCitation/Article/Abstract/AbstractText')),
              'doi': text('./PubmedData/ArticleIdList/ArticleId[@IdType="doi"]').lower(),
              'pmc': text('./PubmedData/ArticleIdList/ArticleId[@IdType="pmc"]'),
              'journal': text('./MedlineCitation/Article/Journal/ISOAbbreviation'),
              'journal_title': text('./MedlineCitation/Article/Journal/Title'),
              'nlm_id': text('./MedlineCitation/MedlineJournalInfo/NlmUniqueID'),
              'types': types, 'dates': dates, 'date_sources': date_sources, 'retraction_links': links,
              'publication_status': text('./PubmedData/PublicationStatus'),
              'volume': text('./MedlineCitation/Article/Journal/JournalIssue/Volume'),
              'issue': text('./MedlineCitation/Article/Journal/JournalIssue/Issue'),
              'pages': text('./MedlineCitation/Article/Pagination/StartPage') or text('./MedlineCitation/Article/Pagination/MedlinePgn'),
              'retracted': 'Retracted Publication' in types or any(n['type']=='RetractionIn' for n in links),
              'retraction_notice': bool({'Retraction Notice', 'Retraction of Publication'} & set(types)) or any(n['type']=='RetractionOf' for n in links),
              'source': f'https://pubmed.ncbi.nlm.nih.gov/{pmid}/'}
        if report is not None:
            report['metadata_batches'].append({'requested': chunk, 'returned': rows, 'sha256': hashlib.sha256(raw).hexdigest()})
        if set(rows) != set(chunk) or len(rows) != len(chunk):
            raise RuntimeError('EFetch 请求与返回 PMID 不一致；不静默跳过书籍、缺篇或错误身份')
    return [out[p] for p in ids]


def preview(plan):
    report = {'schema': 'trackeep-literature/pubmed-preview@1', 'created_at': dt.datetime.now(dt.timezone.utc).isoformat(),
              'plan': plan, 'status': 'blocked', 'read_only': True, 'searches': [], 'partitions': [],
              'metadata_batches': [], 'articles': [], 'review_reasons': [], 'retrieval_complete': False,
              'relevance_validated': False}
    try:
        effective = copy.deepcopy(plan)
        if isinstance(effective, dict) and 'screening_location' not in effective:
            effective['screening_location'] = 'after-import'
        defaulted = (isinstance(effective,dict) and effective.get('kind')=='journal'
                     and isinstance(effective.get('date'),dict) and 'field' not in effective['date'])
        if defaulted:
            effective['date']['field']='dp'
        clause, lo, hi, journal = prepare(effective)
        field = (effective.get('date') or {}).get('field')
        report['effective_plan'] = effective
        report['date_policy'] = {'field':field, 'origin':'default' if defaulted else 'explicit',
          'limitation': '仅电子日期，缺电子日期的记录可能漏收' if field=='epdat' else
                        '仅印刷日期，尚未编期或缺印刷日期的记录可能漏收' if field=='ppdat' else
                        '发表日期候选集，不等于首次上线日期或持续增量追踪' if field=='dp' else
                        '按显式指定的时间范围检索'}
        ids = (sorted(effective['pmids'], key=int) if effective['kind'] == 'articles'
               else sorted(collect(clause, lo, hi, field, report), key=int))
        report['pmids'] = ids
        report['articles'] = metadata(ids, report)
        if journal:
            bad = [a['pmid'] for a in report['articles'] if a['nlm_id'] != journal['nlm_id']]
            report['journal_check'] = {'expected': journal, 'mismatched_pmids': bad}
            if bad:
                raise RuntimeError('题录期刊 NLM ID 与指定主刊不符或缺失')
        seeds = set(plan.get('known_pmids', []))
        report['known_item_check'] = {'expected': sorted(seeds), 'missing': sorted(seeds-set(ids))}
        if seeds-set(ids):
            report['review_reasons'].append('已知应命中文献未命中，需逐篇解释或修改检索式')
        if plan['kind'] == 'topic' and not seeds:
            report['review_reasons'].append('尚无已知文献召回验证；不能声称主题检索已验证')
        report['counts'] = {'unique_pmids': len(ids), 'metadata': len(report['articles']),
          'missing_abstract': sum(not a['abstract'] for a in report['articles']),
          'retracted': sum(a['retracted'] for a in report['articles']),
          'retraction_notice': sum(a['retraction_notice'] for a in report['articles'])}
        report['retrieval_complete'] = True
        report['status'] = 'review_required' if report['review_reasons'] else 'retrieval_verified'
    except (ValueError, KeyError, TypeError, RuntimeError, ET.ParseError) as e:
        report['failure'] = str(e)
    return report


def compare_previous(report, previous):
    """对账只读快照，不改当前来源计数，不写持久去重台账。"""
    if report['status'] == 'blocked':
        return
    if not previous:
        report['cross_batch'] = {'status':'not_evaluated', 'reason':'未提供历史报告，不宣称全局新增'}
        return
    try:
        versions = {}
        doi_pmids = {}
        snapshots = []
        current_time = dt.datetime.fromisoformat(report['created_at'])
        if current_time.tzinfo is None:
            raise ValueError('当前报告时间缺少时区')
        for old in previous:
            if not isinstance(old, dict) or old.get('schema') != report['schema'] or old.get('read_only') is not True or old.get('retrieval_complete') is not True or old.get('status') not in ('retrieval_verified','review_required'):
                raise ValueError('历史报告不是完整的本入口只读快照')
            stamp = dt.datetime.fromisoformat(old['created_at'])
            if stamp.tzinfo is None:
                raise ValueError('历史报告时间缺少时区')
            if stamp > current_time:
                raise ValueError('历史报告时间晚于当前报告，不能作为此前已见依据')
            rows = old['articles']
            if not isinstance(rows,list) or any(not isinstance(a,dict) or not isinstance(a.get('pmid'),str) or not re.fullmatch(r'[1-9][0-9]*',a['pmid']) or not isinstance(a.get('doi',''),str) for a in rows):
                raise ValueError('历史题录结构异常')
            prior_ids=old.get('pmids')
            if not isinstance(prior_ids,list) or any(not isinstance(x,str) for x in prior_ids) or len(prior_ids)!=len(rows) or len({a['pmid'] for a in rows}) != len(rows) or set(prior_ids) != {a['pmid'] for a in rows}:
                raise ValueError('历史报告 PMID 与题录不一致')
            counts=old.get('counts')
            if not isinstance(counts,dict) or any(type(counts.get(k)) is not int or counts[k]!=len(rows) for k in ('unique_pmids','metadata')):
                raise ValueError('历史报告数量与 PMID/题录集合不一致')
            snapshots.append((stamp,rows))
        def norm(value):
            return re.sub(r'^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)','',value.strip(),flags=re.I).lower()
        for _,rows in sorted(snapshots,key=lambda x:x[0]):
            for a in rows:
                versions.setdefault(a['pmid'],[]).append(a)
                if norm(a.get('doi','')):
                    doi_pmids.setdefault(norm(a['doi']),set()).add(a['pmid'])
        for a in report['articles']:
            if norm(a.get('doi','')):
                doi_pmids.setdefault(norm(a['doi']),set()).add(a['pmid'])
        seen, new, changed, conflicts = [], [], [], []
        for a in report['articles']:
            pmid=a['pmid']; past=versions.get(pmid,[])
            (seen if past else new).append(pmid)
            if past:
                fields=sorted(k for k in set(a)|set(past[-1]) if a.get(k)!=past[-1].get(k))
                if fields:
                    changed.append({'pmid':pmid,'fields':fields})
                known_dois={norm(x.get('doi','')) for x in past+[a]}-{''}
                if len(known_dois)>1:
                    conflicts.append({'pmid':pmid,'reason':'同 PMID 存在不同 DOI，须核对更新来源'})
            if norm(a.get('doi','')) and len(doi_pmids[norm(a['doi'])])>1:
                conflicts.append({'pmid':pmid,'reason':'同 DOI 对应不同 PMID，不自动合并',
                                  'related_pmids':sorted(doi_pmids[norm(a['doi'])])})
        report['cross_batch']={'status':'review_required' if conflicts else 'compared',
          'scope':'仅相对于明确传入的历史报告，不代表 Zotero 库', 'source_hits':len(report['pmids']),
          'seen_count':len(seen),'new_count':len(new),'seen_pmids':seen,'new_pmids':new,
          'metadata_changes':changed,'identity_conflicts':conflicts}
        if conflicts:
            report['status']='review_required'
            report['review_reasons'].append('跨批次标识冲突，保留各条题录待核，不按标题合并')
    except (ValueError,KeyError,TypeError) as e:
        report['status']='blocked'
        report['failure']='历史快照对账失败：'+str(e)


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description='PubMed 只读预览；规范见 AGENTS.md。不导入 Zotero、不调用 AI。')
    parser.add_argument('--plan', type=Path, required=True, help='已明确范围的 JSON 检索计划')
    parser.add_argument('--previous', type=Path, action='append', default=[], help='可重复指定本入口历史报告；只读跨批次对账')
    args = parser.parse_args()
    try:
        plan = json.loads(args.plan.read_text(encoding='utf-8-sig'))
        if not isinstance(plan, dict):
            raise ValueError('检索计划必须为 JSON 对象')
    except (OSError, ValueError):
        report = {'schema':'trackeep-literature/pubmed-preview@1', 'status':'blocked', 'read_only':True,
                  'created_at':dt.datetime.now(dt.timezone.utc).isoformat(), 'plan_file':str(args.plan),
                  'retrieval_complete':False, 'relevance_validated':False, 'review_reasons':[],
                  'failure':'无法读取有效检索计划 JSON', 'searches':[], 'metadata_batches':[], 'articles':[]}
    else:
        report = preview(plan)
        report['previous_reports']=[str(p) for p in args.previous]
        try:
            previous=[json.loads(p.read_text(encoding='utf-8-sig')) for p in args.previous]
        except (OSError,ValueError):
            report['status']='blocked'
            report['failure']='历史报告不可读或 JSON 无效，不跳过对账'
        else:
            compare_previous(report,previous)
    folder = ROOT / '日志/pubmed-preview'
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (dt.datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8]+'.json')
    # 独立文件排他写入，保留每次失败及成功证据，不覆盖既有记录。
    with path.open('x', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    print(json.dumps({'status': report['status'], 'counts': report.get('counts'), 'report': str(path),
                      'cross_batch': report.get('cross_batch'), 'failure': report.get('failure'), 'review_reasons': report['review_reasons']}, ensure_ascii=False))
    return {'retrieval_verified': 0, 'review_required': 2, 'blocked': 1}[report['status']]


if __name__ == '__main__':
    raise SystemExit(main())
