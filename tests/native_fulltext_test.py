"""原生全文收口护栏：合成父项与附件，不接真实 Zotero。"""
import copy
import io
import json
import sys
import subprocess
import urllib.error
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lit import native_fulltext as n
from lit.mcp_server import Server, serve

A = {'pmid': '123', 'doi': '10.1000/test', 'title': 'A paper', 'nlm_id': '1234'}
P = {'key': 'ABCDEFGH', 'data': {'itemType': 'journalArticle', 'DOI': A['doi'], 'title': A['title'], 'extra': 'PMID: 123\nNLM ID: 1234'}}
C = {'key': 'IJKLMNOP', 'data': {'itemType': 'attachment', 'parentItem': P['key'], 'contentType': 'application/pdf'}}


class Local:
    def __init__(self):
        self.parent = copy.deepcopy(P)
        self.rows = []
    def get(self, path):
        return self.parent
    def children(self, key):
        return self.rows
    def file(self, child):
        return b'pdf'


class Native(unittest.TestCase):
    def test_empty_jobs_never_complete(self):
        with patch.object(n,'ensure') as ensure:
            result = n.execute_jobs([],apply=True)
        ensure.assert_not_called()
        self.assertEqual(result['status'],'no_kept_items')
        self.assertEqual(result['counts']['scope'],0)
    def setUp(self):
        self.local = Local()
        self.patcher = patch.object(n, 'verify_pdf', return_value={'sha256': 'hash', 'pages': 3})
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.network = patch.object(n, 'official_read', side_effect=AssertionError('离线测试禁止网络'))
        self.network.start()
        self.addCleanup(self.network.stop)
    def test_preview_no_native(self):
        self.assertEqual(n.ensure(A, P['key'], local=self.local)['status'], 'ready')
    def test_existing_avoids_write(self):
        self.local.rows = [C]
        self.assertEqual(n.ensure(A, P['key'], True, self.local, object())['status'], 'existing_verified')
    def test_find_then_repeat(self):
        local = self.local
        class Bridge:
            calls = 0
            def find_full_text(self, *args):
                self.calls += 1
                local.rows = [C]
        bridge = Bridge()
        self.assertEqual(n.ensure(A, P['key'], True, local, bridge, poll_seconds=0)['status'], 'created_verified')
        self.assertEqual(n.ensure(A, P['key'], True, local, bridge)['status'], 'existing_verified')
        self.assertEqual(bridge.calls, 1)
    def test_parent_conflict(self):
        self.local.parent['data']['extra'] = 'PMID: 999\nNLM ID: 1234'
        with self.assertRaises(ValueError):
            n.ensure(A, P['key'], True, self.local, object())
    def test_missing_existing_file_blocks_duplicate(self):
        self.local.rows = [C]
        with patch.object(self.local, 'file', side_effect=ValueError('missing')):
            self.assertEqual(n.ensure(A, P['key'], True, self.local, object())['status'], 'pending_attachment')
    def test_unreviewed_no_reads(self):
        result = n.execute_jobs([{'pmid': A['pmid'], 'parent_key': P['key'], 'article': A, 'review': 'pending'}], True, local=object())
        self.assertEqual(result['items'][0]['status'], 'pending_review')
    def test_wrong_parent_child(self):
        self.local.rows = [copy.deepcopy(C)]
        self.local.rows[0]['data']['parentItem'] = 'ZZZZZZZZ'
        with self.assertRaises(ValueError):
            n.ensure(A, P['key'], local=self.local)
    def test_pagination(self):
        local = n.LocalLibrary()
        rows = [{'key': str(i)} for i in range(101)]
        with patch.object(local, 'get', side_effect=[rows[:100], rows[100:]]) as get:
            self.assertEqual(len(local.children(P['key'])), 101)
            self.assertIn('start=100', get.call_args.args[0])
    def test_missing_native_then_official_stored_copy(self):
        local = self.local
        class Bridge:
            calls = []
            def find_full_text(self, *args):
                self.calls.append('find')
            def attach_file(self, *args):
                self.calls.append('attach')
                local.rows = [C]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'a.pdf'; path.write_bytes(b'pdf')
            fallback = {'path': str(path), 'source': 'https://www.nature.com/a.pdf', 'sha256': 'hash'}
            bridge = Bridge()
            result = n.ensure(A, P['key'], True, local, bridge, fallback, poll_seconds=0)
            self.assertEqual(result['route'], 'native_stored_copy')
            self.assertEqual(bridge.calls, ['find', 'attach'])
    def test_no_available_fulltext(self):
        class Bridge:
            def find_full_text(self, *args):
                pass
        with patch.object(n, 'official_fallback', return_value=None):
            self.assertEqual(n.ensure(A, P['key'], True, self.local, Bridge(), poll_seconds=0)['status'], 'missing_fulltext')
    def test_native_mutation_parent_blocks(self):
        local = self.local
        class Bridge:
            def find_full_text(self, *args):
                local.parent['data']['tags'] = [{'tag': 'changed'}]
        with self.assertRaisesRegex(ValueError, '父题录内容变化'):
            n.ensure(A, P['key'], True, local, Bridge(), poll_seconds=0)


class OfficialDiagnostics(unittest.TestCase):
    def test_http_forbidden_not_retried_or_body_exposed(self):
        events = []
        error = urllib.error.HTTPError('https://www.nature.com/secret', 403, 'secret detail', {}, None)
        with patch.object(n.urllib.request, 'build_opener') as build:
            build.return_value.open.side_effect = error
            with self.assertRaisesRegex(RuntimeError, '阶段=pdf.*HTTP=403') as caught:
                n.official_read('https://www.nature.com/a.pdf', stage='pdf', events=events)
        self.assertNotIn('secret', str(caught.exception))
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['outcome'], 'failed')

    def test_transient_http_retry_is_bounded(self):
        events = []
        error = urllib.error.HTTPError('https://www.nature.com/a', 503, 'unavailable', {}, None)
        with patch.object(n.urllib.request, 'build_opener') as build, patch.object(n.time, 'sleep'):
            build.return_value.open.side_effect = error
            with self.assertRaisesRegex(RuntimeError, 'HTTP=503'):
                n.official_read('https://www.nature.com/a', events=events)
        self.assertEqual([x['outcome'] for x in events], ['retry', 'failed'])

    def test_execute_failure_preserves_completed_stages(self):
        def fail(*args, events=None, **kwargs):
            events.extend([{'stage': 'native_find_triggered'}, {'stage': 'native_find_no_verified_file'}])
            raise RuntimeError('阶段=pmc_version_listing，HTTP=503')
        job = {'pmid': '123', 'parent_key': 'ABCDEFGH', 'review': 'keep', 'article': A}
        with patch.object(n, 'ensure', side_effect=fail):
            result = n.execute_jobs([job], apply=True)
        self.assertEqual(result['items'][0]['status'], 'failed')
        self.assertEqual(len(result['items'][0]['events']), 2)


class MCP(unittest.TestCase):
    def test_stdio_handshake_and_dispatch(self):
        class Flow:
            def dispatch(self, action, payload):
                return {'ok': True, 'action': action, 'data': payload}
        messages = [{'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-03-26'}},
                    {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
                    {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': 'literature_dispatch', 'arguments': {'action': 'status', 'payload': {'run_id': 'test'}}}}]
        output = io.StringIO()
        serve(Flow(), io.StringIO('\n'.join(json.dumps(x) for x in messages)), output)
        results = [json.loads(x) for x in output.getvalue().splitlines()]
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['result']['protocolVersion'], '2025-03-26')
        self.assertEqual(json.loads(results[1]['result']['content'][0]['text'])['data']['run_id'], 'test')
    def test_bad_params(self):
        server = Server(object())
        for params in ([], '', 5):
            self.assertEqual(server.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': params})['error']['code'], -32602)
    def test_write_requires_run(self):
        server = Server(object()); server.initialized = True
        value = server.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'literature_dispatch', 'arguments': {'action': 'fulltext', 'payload': {'apply': True}}}})
        self.assertEqual(value['error']['code'], -32602)
    def test_real_plugin_process_handshake(self):
        root = Path(__file__).resolve().parents[1]
        lines = [{'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-03-26'}},
                 {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
                 {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'}]
        process = subprocess.run([sys.executable, str(root / 'plugins/trackeep-literature/server.py')],
            input='\n'.join(map(json.dumps, lines)) + '\n', capture_output=True, text=True, encoding='utf-8', timeout=15)
        self.assertEqual(process.returncode, 0, process.stderr)
        result = [json.loads(line) for line in process.stdout.splitlines()]
        self.assertEqual([r['id'] for r in result], [1, 2])
        self.assertEqual(result[1]['result']['tools'][0]['name'], 'literature_dispatch')


if __name__ == '__main__':
    unittest.main()
