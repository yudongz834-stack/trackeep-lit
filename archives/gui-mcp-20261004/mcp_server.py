"""MCP stdio 适配：JSON-RPC 行协议，业务完全委托共享 Workflow。"""
import argparse
import contextlib
import json
from pathlib import Path
import sys

ACTIONS = ['plan', 'plan_natural', 'search', 'import', 'review', 'review_ai', 'status', 'list_runs', 'collections', 'fulltext_jobs', 'fulltext']


class Server:
    def __init__(self, workflow):
        self.workflow = workflow
        self.initialized = False

    def handle(self, request):
        ident = request.get('id')
        method = request.get('method')
        if ident is None:
            return None
        def result(value):
            return {'jsonrpc': '2.0', 'id': ident, 'result': value}
        def error(code, message):
            return {'jsonrpc': '2.0', 'id': ident, 'error': {'code': code, 'message': message}}
        if request.get('jsonrpc') != '2.0':
            return error(-32600, '无效 JSON-RPC 请求')
        if not isinstance(request.get('params', {}), dict):
            return error(-32602, 'params 必须为对象')
        if method == 'initialize':
            self.initialized = True
            version = request.get('params', {}).get('protocolVersion')
            supported = ['2024-11-05', '2025-03-26', '2025-06-18']
            return result({'protocolVersion': version if version in supported else supported[-1],
                'capabilities': {'tools': {}}, 'serverInfo': {'name': 'trackeep-literature', 'version': '1.0.0'}})
        if method == 'ping':
            return result({})
        if not self.initialized:
            return error(-32002, '须先初始化')
        if method == 'tools/list':
            return result({'tools': [{'name': 'literature_dispatch', 'description': '操作 Trackeep Literature 共享流程：计划、检索、题录导入、复核和本机全文。写入须有明确范围与 apply=true。',
                'inputSchema': {'type': 'object', 'properties': {'action': {'type': 'string', 'enum': ACTIONS}, 'payload': {'type': 'object'}},
                    'required': ['action', 'payload'], 'additionalProperties': False},
                'annotations': {'readOnlyHint': False, 'destructiveHint': True, 'idempotentHint': False, 'openWorldHint': True}}]})
        if method == 'tools/call':
            params = request.get('params', {})
            arguments = params.get('arguments', {})
            if params.get('name') != 'literature_dispatch' or not isinstance(arguments, dict):
                return error(-32602, '工具名称或参数无效')
            action, payload = arguments.get('action'), arguments.get('payload')
            if action not in ACTIONS or not isinstance(payload, dict):
                return error(-32602, '动作或载荷无效')
            if 'apply' in payload and not isinstance(payload['apply'], bool):
                return error(-32602, 'apply 必须为布尔值')
            if 'apply_cleanup' in payload and not isinstance(payload['apply_cleanup'], bool):
                return error(-32602, 'apply_cleanup 必须为布尔值')
            if action in ('import', 'fulltext') and payload.get('apply') and not payload.get('run_id'):
                return error(-32602, '写入必须绑定已验证批次')
            try:
                with contextlib.redirect_stdout(sys.stderr):
                    response = self.workflow.dispatch(action, payload)
                return result({'content': [{'type': 'text', 'text': json.dumps(response, ensure_ascii=False)}], 'isError': not response.get('ok', False)})
            except Exception:
                return result({'content': [{'type': 'text', 'text': '共享流程调用失败，请查看批次回执；未将异常细节外发。'}], 'isError': True})
        return error(-32601, '不支持的方法')


def serve(workflow, incoming, outgoing):
    server = Server(workflow)
    for line in incoming:
        try:
            request = json.loads(line)
            if not isinstance(request, dict):
                raise ValueError()
            response = server.handle(request)
        except (ValueError, TypeError):
            response = {'jsonrpc': '2.0', 'id': None, 'error': {'code': -32700, 'message': 'JSON 请求格式无效'}}
        if response is not None:
            outgoing.write(json.dumps(response, ensure_ascii=False) + '\n')
            outgoing.flush()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path)
    args = parser.parse_args()
    from lit.workflow import Workflow
    if hasattr(sys.stdin, 'reconfigure'):
        sys.stdin.reconfigure(encoding='utf-8')
        sys.stdout.reconfigure(encoding='utf-8')
    serve(Workflow(root=args.root), sys.stdin, sys.stdout)


if __name__ == '__main__':
    main()
