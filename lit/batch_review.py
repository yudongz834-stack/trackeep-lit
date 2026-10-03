"""仅复核显式批次；清理以可逆的有效候选清单表达，不改已有 Zotero 资料。"""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import sys
import uuid
from lit.library import Library, exact, matching
from lit.metadata_batch import ROOT, save


def review(batch, decisions, lib):
    if batch.get('schema') != 'trackeep-literature/metadata-batch@1' or batch.get('status') != 'metadata_verified':
        raise ValueError('只复核已读回验证的题录批次')
    articles = batch['articles']
    if (not isinstance(decisions, list) or len(decisions) != len(articles) or
            {d.get('pmid') for d in decisions} != {a['pmid'] for a in articles}):
        raise ValueError('每个批次 PMID 必须有且仅有一条复核决定')
    all_rows = lib.all('/items?includeTrashed=1')
    result = {'schema':'trackeep-literature/batch-review@1', 'created_at':dt.datetime.now(dt.timezone.utc).isoformat(),
              'rule_version':'PubMed检索规范 v1.0 / 2026-10-03 入库后复核', 'location':'after-import',
              'cleanup_method':'effective_candidate_list', 'zotero_mutations':0, 'fulltext_status':'not_started', 'items':[]}
    for a in articles:
        decision = next(d for d in decisions if d['pmid'] == a['pmid'])
        if decision.get('decision') not in ('keep','exclude','pending') or not isinstance(decision.get('reason'),str) or not decision['reason'].strip():
            raise ValueError('决定必须为保留/排除/待核并附理由')
        imported = next(i for i in batch['items'] if i['pmid'] == a['pmid'])
        hits = matching(all_rows,a)
        item = {'pmid':a['pmid'],'doi':a['doi'],'title':a['title'],'source':a['source'],
                'retraction_links':a.get('retraction_links',a.get('links',[])), 'requested_decision':decision,
                'decision':decision['decision'],'reason':decision['reason'], 'keys':[r['key'] for r in hits]}
        if (len(hits) != 1 or not exact(hits[0],a) or hits[0]['key'] not in imported.get('keys',[]) or
                batch['collection']['key'] not in hits[0]['data'].get('collections',[]) or hits[0]['data'].get('deleted')):
            item.update(decision='pending',reason='读回身份、目录或重复状态变化，保护原资料待核')
        elif a.get('retracted') or a.get('retraction_notice'):
            item.update(decision='exclude',reason='撤稿原文或通知：保留来源，从有效研究候选中排除')
        elif not a.get('abstract') and decision['decision'] == 'exclude':
            item.update(decision='pending',reason='缺摘要条目不自动排除，需补充可核证据')
        if len(hits) == 1:
            row = hits[0]
            item['readback'] = row
            # 子项只读保存本批相关信息；保护附件与笔记，不合并或删除。
            item['children'] = lib.all('/items/'+row['key']+'/children')
        result['items'].append(item)
    result['counts'] = {k:sum(i['decision']==k for i in result['items']) for k in ('keep','exclude','pending')}
    result['effective_pmids'] = [i['pmid'] for i in result['items'] if i['decision']=='keep']
    result['status'] = 'review_complete' if not result['counts']['pending'] else 'review_pending'
    return result


def main():
    if hasattr(sys.stdout,'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--batch',type=Path,required=True)
    p.add_argument('--decisions',type=Path,required=True)
    args=p.parse_args()
    folder=ROOT/'日志/metadata-reviews'
    folder.mkdir(parents=True,exist_ok=True)
    path=folder / ('review-'+uuid.uuid4().hex[:8]+'.json')
    result={'schema':'trackeep-literature/batch-review@1','status':'started','batch_source':str(args.batch.resolve()),
            'counts':{},'fulltext_status':'not_started','zotero_mutations':0}
    save(path,result)
    try:
        raw=args.batch.read_bytes()
        batch=json.loads(raw.decode('utf-8-sig'))
        decisions=json.loads(args.decisions.read_text(encoding='utf-8-sig'))
        result=review(batch,decisions,Library())
        result.update(batch_source=str(args.batch.resolve()),batch_sha256=hashlib.sha256(raw).hexdigest())
    except Exception as e:
        result.update(status='blocked',failure=str(e) if isinstance(e,(ValueError,RuntimeError)) else '复核输入或读取失败')
    save(path,result)
    print(json.dumps({'status':result['status'],'counts':result['counts'],'report':str(path)},ensure_ascii=False))
    return 0 if result['status']=='review_complete' else 2


if __name__=='__main__': raise SystemExit(main())
