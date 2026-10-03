"""对已复核的本批保留项挂接已核官方 PDF；每步落盘，失败不冒充完成。"""
import argparse,datetime as dt,hashlib,json,os,sys,uuid
from pathlib import Path
from lit.metadata_batch import ROOT,save
from lit.fulltext import AttachmentLibrary,attach,norm


def eligible(review,batch):
    if review.get('schema')!='trackeep-literature/batch-review@1' or review.get('status') not in ('review_complete','review_pending'):
        raise ValueError('未取得有效复核报告')
    if batch.get('status')!='metadata_verified':raise ValueError('题录批次未验证')
    items=review['items']
    if len({x['pmid'] for x in items})!=len(items) or {x['pmid'] for x in items}!={a['pmid'] for a in batch['articles']}:
        raise ValueError('复核集合不一致')
    selected=[]
    for item in items:
        if item['decision']!='keep':continue
        a=next(a for a in batch['articles'] if a['pmid']==item['pmid'])
        original=next(i for i in batch['items'] if i['pmid']==a['pmid'])
        if item['keys']!=original['keys'] or len(item['keys'])!=1 or a.get('retracted') or a.get('retraction_notice'):
            raise ValueError('保留项身份或撤稿状态不允许下载')
        selected.append((a,item['keys'][0]))
    if len(selected)>3:raise ValueError('超过本阶段小批量范围')
    return selected


def run(review_path,downloads_path,folder,apply=False,lib=None):
    report={'schema':'trackeep-literature/fulltext-batch@1','created_at':dt.datetime.now(dt.timezone.utc).isoformat(),
            'status':'started','apply':apply,'review_source':str(review_path),'items':[],'events':[]}
    path=folder/'report.json';save(path,report)
    def journal(event):report['events'].append(event);save(path,report)
    try:
        review=json.loads(review_path.read_text(encoding='utf-8-sig'))
        batch_raw=Path(review['batch_source']).read_bytes()
        if hashlib.sha256(batch_raw).hexdigest()!=review['batch_sha256']:raise ValueError('原批次已变化')
        batch=json.loads(batch_raw.decode('utf-8-sig'))
        selected=eligible(review,batch)
        downloads=json.loads(downloads_path.read_text(encoding='utf-8-sig'))
        report['counts']={'scope':len(review['items']),'eligible':len(selected),'excluded_or_pending':len(review['items'])-len(selected)}
        lib=lib or AttachmentLibrary()
        for a,key in selected:
            item={'pmid':a['pmid'],'parent':key};report['items'].append(item)
            try:
                candidates=[d for d in downloads if d['pmid']==a['pmid']]
                if len(candidates)!=1:raise ValueError('缺少唯一官方下载证据')
                d=candidates[0]
                if d['doi']!=a['doi'] or norm(d['title'])!=norm(a['title']):raise ValueError('下载来源身份不符')
                blob=(ROOT/'全文'/(a['pmid']+'.pdf')).read_bytes()
                if hashlib.sha256(blob).hexdigest()!=d['sha256']:raise ValueError('下载文件与留证哈希不同')
                item.update(source=d['source'],**attach(lib,a,key,blob,d['source'],journal,apply))
            except Exception as e:
                item.update(status='failed',reason=str(e) if isinstance(e,(ValueError,RuntimeError)) else '文件或接口读取失败')
            save(path,report)
        report['counts'].update({s:sum(i['status']==s for i in report['items']) for s in ('created_verified','resumed_verified','existing_verified','ready','failed')})
        report['status']='partial_failure' if report['counts']['failed'] else 'complete' if apply else 'preview_only'
    except Exception as e:
        report.update(status='blocked',reason=str(e) if isinstance(e,(ValueError,RuntimeError)) else '输入或接口异常')
    save(path,report);return report


def main():
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--review',type=Path,required=True);p.add_argument('--downloads',type=Path,required=True);p.add_argument('--apply',action='store_true')
    args=p.parse_args()
    folder=ROOT/'日志/fulltext-batches'/(dt.datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8]);folder.mkdir(parents=True)
    # 操作系统文件锁覆盖查重到读回；进程退出自动释放，不清理别人的锁文件。
    lock=ROOT/'日志/fulltext-batches/attachment.lock'
    with lock.open('a+b') as f:
        import msvcrt
        if f.seek(0,2)==0:f.write(b'0');f.flush()
        f.seek(0)
        try:msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:
            r={'schema':'trackeep-literature/fulltext-batch@1','status':'blocked','apply':args.apply,
               'created_at':dt.datetime.now(dt.timezone.utc).isoformat(),'reason':'另一个附件任务正在运行',
               'review_source':str(args.review),'items':[],'events':[]}
            save(folder/'report.json',r)
        else:
            try:r=run(args.review,args.downloads,folder,args.apply)
            finally:f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
    print(json.dumps({'status':r['status'],'counts':r.get('counts'),'report':str(folder/'report.json')},ensure_ascii=False))
    return 0 if r['status'] in ('complete','preview_only') else 2


if __name__=='__main__':raise SystemExit(main())
