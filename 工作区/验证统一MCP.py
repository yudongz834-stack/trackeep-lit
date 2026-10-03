"""通过真实 stdio MCP 子进程验证一次业务动作，保留协议回执。"""
import argparse
import datetime as dt
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action')
    parser.add_argument('payload', help='由 Agent 形成的 JSON 参数')
    args = parser.parse_args()
    payload = json.loads(args.payload)
    messages = [
        {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {
            'protocolVersion': '2025-06-18', 'capabilities': {},
            'clientInfo': {'name': 'trackeep-live-verifier', 'version': '1.0'}}},
        {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
        {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'},
        {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {
            'name': 'literature_dispatch', 'arguments': {'action': args.action, 'payload': payload}}},
    ]
    result = subprocess.run([sys.executable, '-B', str(ROOT / 'plugins/trackeep-literature/server.py')],
        input=''.join(json.dumps(m, ensure_ascii=False) + '\n' for m in messages),
        capture_output=True, text=True, encoding='utf-8', cwd=ROOT, timeout=900)
    responses = [json.loads(line) for line in result.stdout.splitlines()]
    assert result.returncode == 0 and [r['id'] for r in responses] == [1, 2, 3]
    assert responses[1]['result']['tools'][0]['name'] == 'literature_dispatch'
    response = json.loads(responses[2]['result']['content'][0]['text'])
    folder = ROOT / '日志/unified-live-validation'
    folder.mkdir(parents=True, exist_ok=True)
    destination = folder / (dt.datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '-' + args.action + '.json')
    destination.write_text(json.dumps({'request': messages, 'responses': responses}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: response.get(k) for k in ('ok', 'action', 'run_id', 'state', 'counts', 'errors')}, ensure_ascii=False))
    print(str(destination))
    return 0 if response.get('ok') else 2


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
