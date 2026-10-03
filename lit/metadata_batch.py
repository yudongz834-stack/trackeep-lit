"""核验报告到原 PowerShell 引擎的有界桥接；入库后复核，全文另行启动。"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid
from lit import pubmed
from lit.library import Library, exact, matching

ROOT = Path(__file__).resolve().parents[1]
ENGINE = Path(r'D:\dev\trackeep-scripts\zotero-import.ps1')
PWSH = Path(r'C:\Program Files\PowerShell\7\pwsh.exe')


def save(path, data):
    tmp = path.with_suffix('.tmp')
    with tmp.open('w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def load_scope(path, pmids):
    raw = path.read_bytes()
    report = json.loads(raw.decode('utf-8-sig'))
    if (report.get('schema') != 'trackeep-literature/pubmed-preview@1' or
            report.get('status') != 'retrieval_verified' or report.get('retrieval_complete') is not True or
            report.get('read_only') is not True):
        raise ValueError('只接收完整、无待核警告的核验报告')
    if not 1 <= len(pmids) <= 3 or len(set(pmids)) != len(pmids) or any(not re.fullmatch(r'[1-9]\d*', p) for p in pmids):
        raise ValueError('本阶段须显式指定 1 至 3 个不同 PMID')
    rows = report['articles']
    ids = report['pmids']
    if len(rows) != len(ids) or len(set(ids)) != len(ids) or set(ids) != {a['pmid'] for a in rows}:
        raise ValueError('源报告集合不一致')
    if any(type(report['counts'].get(k)) is not int or report['counts'][k] != len(rows) for k in ('unique_pmids', 'metadata')):
        raise ValueError('源报告计数不一致')
    selected = [a for a in rows if a['pmid'] in pmids]
    if len(selected) != len(pmids):
        raise ValueError('指定 PMID 不全在已核报告中')
    plan = report.get('effective_plan', report['plan'])
    if plan.get('screening_location') != 'after-import':
        raise ValueError('源计划未采用本阶段入库后复核顺序，须更新计划并重做预览')
    journal = plan.get('journal')
    if not journal or any(not a.get('nlm_id') or not a.get('title') for a in selected):
        raise ValueError('本阶段需要已核期刊身份')
    verified_journal = pubmed.resolve_journal(journal)
    if any(a['nlm_id'] != verified_journal['nlm_id'] for a in selected):
        raise ValueError('源报告题录期刊与计划不一致')
    return selected, verified_journal['ta'], hashlib.sha256(raw).hexdigest(), plan


def engine_call(articles, journal, collection, pin, apply):
    cmd = [str(PWSH), '-NoProfile', '-File', str(ENGINE), '-Journal', journal,
           '-ArticlePmids', ','.join(a['pmid'] for a in articles), '-CollectionKey', collection,
           '-StateDir', str(ROOT), '-ExpectedRecordsPath', str(pin), '-EmitJson']
    if apply:
        cmd.append('-Execute')
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace',
                            timeout=600, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    # 不把引擎原始输出/错误写日志，避免依赖异常中夹带请求头。
    if result.returncode:
        raise RuntimeError('原引擎未正常完成；须读库核对写入状态')
    lines = [s[len('TRACKEEP_JSON '):] for s in result.stdout.splitlines() if s.startswith('TRACKEEP_JSON ')]
    if len(lines) != 1:
        raise RuntimeError('原引擎缺唯一机器回执；须读库核对')
    receipt = json.loads(lines[0])
    items = receipt.get('items')
    if (receipt.get('schema') != 'trackeep-lit/import-result@1' or receipt.get('executed') is not apply or
            receipt.get('collection', {}).get('key') != collection or not isinstance(items, list) or
            len(items) != len(articles) or {i['pmid'] for i in items} != {a['pmid'] for a in articles}):
        raise RuntimeError('原引擎回执与指定范围不符')
    for a in articles:
        item = next(i for i in items if i['pmid'] == a['pmid'])
        if item.get('title') != a['title'] or item.get('doi', '').lower() != a.get('doi', '').lower():
            raise RuntimeError('原引擎回执身份不符')
        if item['status'] == 'imported' and not re.fullmatch(r'[A-Z0-9]{8}', item.get('zoteroKey', '')):
            raise RuntimeError('新建项缺少唯一 Zotero 编号')
    return receipt


def run(args, folder):
    out = {'schema': 'trackeep-literature/metadata-batch@1', 'created_at': dt.datetime.now(dt.timezone.utc).isoformat(),
           'status': 'started', 'apply': args.apply, 'review_status': 'not_started', 'fulltext_status': 'not_started',
           'source': str(args.preview.resolve()), 'items': []}
    path = folder / 'report.json'
    save(path, out)
    try:
        articles, journal, digest, plan = load_scope(args.preview, args.pmids.split(','))
        out.update(source_sha256=digest, plan=plan, screening_location='after-import', selected_pmids=[a['pmid'] for a in articles])
        # 写前重新取公共题录，逐一比较关键身份；元数据变化要求重做预览。
        probe = {'metadata_batches': []}
        fresh = pubmed.metadata([a['pmid'] for a in articles], probe)
        by_id = {a['pmid']: a for a in fresh}
        if any(any(a.get(k) != by_id[a['pmid']].get(k) for k in ('pmid','doi','title','nlm_id')) for a in articles):
            raise ValueError('题录身份较预览已变化，须重新核验')
        articles = [by_id[a['pmid']] for a in articles]
        out['articles'] = articles
        out['metadata_batches'] = probe['metadata_batches']
        lib = Library()
        cols = [c for c in lib.all('/collections') if c['data']['name'] == journal]
        if len(cols) != 1:
            raise ValueError('目标期刊目录不存在或重名；本阶段不新建目录')
        collection = cols[0]['key']
        out['collection'] = {'key': collection, 'name': journal}
        rows = lib.all('/items?includeTrashed=1')
        pending = []
        for a in articles:
            hits = matching(rows, a)
            item = {'pmid': a['pmid'], 'doi': a['doi'], 'title': a['title'], 'review': 'pending'}
            if hits:
                item['keys'] = [r['key'] for r in hits]
                if len(hits) != 1 or not exact(hits[0], a):
                    item['metadata_status'] = 'identity_or_duplicate_pending'
                elif hits[0]['data'].get('deleted'):
                    item['metadata_status'] = 'already_trashed'
                elif collection not in hits[0]['data'].get('collections', []):
                    item['metadata_status'] = 'existing_outside_target'
                else:
                    item['metadata_status'] = 'existing_verified'
                # 不改已有条目；仅保存当前批次匹配项的快照。
                item['before'] = hits
            else:
                item['metadata_status'] = 'new_candidate'
                pending.append(a)
            out['items'].append(item)
        save(path, out)
        if pending:
            pin = folder / 'expected.json'
            save(pin, pending)
            out['dry_run'] = engine_call(pending, journal, collection, pin, False)
            save(path, out)
            if any(i['status'] != 'new' for i in out['dry_run']['items']):
                raise ValueError('引擎与库查重结论不一致，停止写入')
            if args.apply:
                out['receipt'] = engine_call(pending, journal, collection, pin, True)
                save(path, out)
                # 按引擎确认为本批创建的编号读回，不以“先前没见过”认领条目。
                for a in pending:
                    ri = next(i for i in out['receipt']['items'] if i['pmid'] == a['pmid'])
                    item = next(i for i in out['items'] if i['pmid'] == a['pmid'])
                    if ri['status'] != 'imported':
                        item['metadata_status'] = 'not_created_pending'
                        continue
                    row = lib.get('/items/' + ri['zoteroKey'])
                    item.update(keys=[ri['zoteroKey']], created_key=ri['zoteroKey'], readback=row)
                    item['metadata_status'] = ('created_verified' if exact(row, a) and not row['data'].get('deleted') and
                                               collection in row['data'].get('collections', []) else 'readback_failed')
                    save(path, out)
        good = {'created_verified','existing_verified'}
        out['counts'] = {s: sum(i['metadata_status'] == s for i in out['items']) for s in sorted({i['metadata_status'] for i in out['items']})}
        out['status'] = ('metadata_verified' if all(i['metadata_status'] in good for i in out['items']) else
                         'preview_only' if not args.apply else 'review_required')
    except Exception as e:
        out['status'] = 'blocked'
        # 仅本模块有界错误可回显；外部异常不转录凭证/请求。
        out['failure'] = str(e) if isinstance(e, (ValueError, RuntimeError)) else '执行异常，须检查范围及读回状态'
    save(path, out)
    return out


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preview', type=Path, required=True)
    parser.add_argument('--pmids', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    folder = ROOT / '日志/metadata-batches' / (dt.datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8])
    folder.mkdir(parents=True)
    report = run(args, folder)
    print(json.dumps({'status': report['status'], 'counts': report.get('counts'), 'failure': report.get('failure'),
                      'report': str(folder / 'report.json')}, ensure_ascii=False))
    return 0 if report['status'] in ('metadata_verified','preview_only') else 2


if __name__ == '__main__':
    raise SystemExit(main())
