# 从 tests/native_fulltext_test.py 拆出的 MCP 段（随 GUI/MCP 退役归档 2026-10-04；依赖已归档的 lit.mcp_server 与 plugins server）
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
