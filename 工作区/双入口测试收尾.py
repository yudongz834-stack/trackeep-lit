"""仅处置本轮两篇隔离测试题录；先核范围，默认预览，应用时可逆入回收站。"""
import datetime
import json
from pathlib import Path
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lit.library import Library, NoRedirect, exact
from lit.native_fulltext import LocalLibrary

OUT = ROOT / '日志/unified-live-validation'
SCOPE = {
    '20261003-163402-0e7e9b51c2c0': ('34265844', 'C6WXAFZ4'),
    '20261003-163749-8a270bffc79e': ('35357919', '5ATM3SFJ'),
}
PROTECTED = {'WD9F8D8E', 'XT8K8X34', 'IU8CWQD2', 'JBKB7SJZ'}


def main():
    apply = sys.argv[1:] == ['--apply']
    assert not sys.argv[1:] or apply, '只支持预览或 --apply'
    receipt = OUT / 'cleanup.json'
    assert not receipt.exists(), '已有处置记录，须读回核查，禁止盲重跑'
    evidence = json.loads((OUT / 'local-delivery.json').read_text(encoding='utf-8'))
    assert all(x['unchanged_file'] for x in evidence['protected'])
    local, cloud = LocalLibrary(), Library()
    planned = []
    for run_id, (pmid, parent_key) in SCOPE.items():
        run = json.loads((ROOT / '日志/workflow-runs' / run_id / 'run.json').read_text(encoding='utf-8'))
        assert run['target_collection'] == '75X3U7JU'
        article = next(a for a in run['metadata']['articles'] if a['pmid'] == pmid)
        item = next(i for i in run['metadata']['items'] if i['pmid'] == pmid)
        assert item['keys'] == [parent_key] and item['created_key'] == parent_key
        proof = next(x for x in evidence['runs'] if x['run_id'] == run_id and x['parent_key'] == parent_key)
        assert not proof['invalid'] and len(proof['verified']) == 1
        expected = set(proof['children'])
        assert expected == {x['key'] for x in proof['verified']} and len(expected) == 1
        for source in (local, cloud):
            p = source.get('/items/' + parent_key)
            assert exact(p, article) and p['data']['collections'] == ['75X3U7JU']
            assert not p['data'].get('deleted')
            children = source.get('/items/' + parent_key + '/children')
            assert {c['key'] for c in children} == expected
            assert all(c['data']['parentItem'] == parent_key and c['data']['itemType'] == 'attachment' for c in children)
        planned.extend(children)
        planned.append(p)
    keys = [x['key'] for x in planned]
    assert len(keys) == len(set(keys)) == 4 and not PROTECTED.intersection(keys)
    record = {'at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'action': 'PATCH deleted=1；仅可恢复入回收站', 'exact_keys': keys,
        'collection': '75X3U7JU，保留空集合', 'results': []}
    if not apply:
        print(json.dumps(record, ensure_ascii=False))
        return
    def save():
        receipt.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    save()
    for row in planned:
        current = cloud.get('/items/' + row['key'])
        stable = lambda d: {k:v for k,v in d.items() if k not in ('version', 'dateModified')}
        assert stable(current['data']) == stable(row['data']), '验证后对象改变，停止处置'
        request = urllib.request.Request(cloud.base + '/items/' + row['key'],
            data=b'{"deleted":1}', method='PATCH', headers={**cloud.headers,
            'Content-Type': 'application/json', 'If-Unmodified-Since-Version': str(current['version'])})
        try:
            with urllib.request.build_opener(NoRedirect).open(request, timeout=90) as response:
                assert response.status == 204
        except Exception:
            raise RuntimeError('清理回执待核；保留记录，禁止盲重发') from None
        assert cloud.get('/items/' + row['key'])['data'].get('deleted') == 1
        record['results'].append({'key': row['key'], 'deleted': 1})
        save()
    print(json.dumps(record, ensure_ascii=False))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
