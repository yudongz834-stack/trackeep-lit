"""只读核验本轮两个批次及受保护原文，输出最小本机证据。"""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lit.native_fulltext import LocalLibrary, inspect


def main():
    local = LocalLibrary()
    runs = ['20261003-163402-0e7e9b51c2c0', '20261003-163749-8a270bffc79e']
    evidence = {'runs': [], 'protected': []}
    for run_id in runs:
        run = json.loads((ROOT / '日志/workflow-runs' / run_id / 'run.json').read_text(encoding='utf-8'))
        for item in run.get('metadata', {}).get('items', []):
            if len(item.get('keys', [])) != 1:
                continue
            article = next(a for a in run['metadata']['articles'] if a['pmid'] == item['pmid'])
            parent, children, verified, invalid = inspect(local, article, item['keys'][0])
            evidence['runs'].append({'run_id': run_id, 'pmid': article['pmid'], 'parent_key': parent['key'],
                'collections': parent['data']['collections'], 'children': [c['key'] for c in children],
                'verified': verified, 'invalid': invalid})
    for pmid, parent_key, child_key, digest in [
        ('42420446','WD9F8D8E','XT8K8X34','c0c10e691579ee9cdc47fb61dc0ff52bca58a96a91b797aa2b4fb0b3f4121266'),
        ('42816625','IU8CWQD2','JBKB7SJZ','a346ec1af676aafcb59867d0e3673b8036bbeaee911206020babcab98ef88d9f')]:
        parent = local.get('/items/' + parent_key)
        article = {'pmid': pmid, 'doi':parent['data']['DOI'], 'title':parent['data']['title'], 'nlm_id':'0410462'}
        _, _, verified, invalid = inspect(local, article, parent_key)
        match = [x for x in verified if x['key'] == child_key and x['pdf']['sha256'] == digest]
        evidence['protected'].append({'pmid':pmid,'parent_key':parent_key,'attachment_key':child_key,
            'unchanged_file':len(match)==1, 'invalid':invalid})
        assert len(match) == 1
    folder = ROOT / '日志/unified-live-validation'
    folder.mkdir(exist_ok=True)
    (folder / 'local-delivery.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(evidence,ensure_ascii=False))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
