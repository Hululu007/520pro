#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""foundry-core · jadx MCP 26 工具全量接线引擎（通用层 lib，被 import，不注册不路由）。

命名来由（病15 对象范围坑）：本模块刻意叫 jadx_engine 而非 core。
probe-hub 的 probe.py 会把 ~/.codebuddy/skills/tvbox-core/scripts 插进 sys.path，
shellcrack.py 里 `from core import http_get` 依赖那个 core；若本模块也叫 core 并被
加进 sys.path，会劫持该名字、让能力层静默拿到错模块。因此：
  · 引擎独立命名；
  · 调用方一律 importlib.util.spec_from_file_location 按**绝对路径**加载，
    全程不改 sys.path（本模块也不 import 同目录 core.py，保持零耦合）。

职责边界（与 core.py 分工，M2 单一事实源）：
  · 本模块 = 纯传输层：initialize / tools/list / tools/call，call(name, args) 泛化
    调 26 个工具，transport 可注入（FakeTransport）供离线 selftest，不启动 java。
  · core.py = 纯判据层：26 工具名册、参数链 CHAIN_RULES、tools_schema.json 装载。
  两者互不 import：判据只在 core 定义一次，引擎不重复。

兼容契约（v0.8.4「收件方自持、调用行零改动」）：
  shellcrack.py 原 JadxMCP(jar).start() / load_apk() / search() / close() 签名保持，
  故其 probe_shell_types 调用行无需改动；_FakeMCP 与 S233① 五种后接形态判据仍留能力层。
"""
import json
import os
import subprocess
import time

JADX_JAR_CANDIDATES = (
    '/tmp/milk/assets/mcp/jadx-headless-mcp-0.7.1-all.jar',
    os.path.expanduser('~/.local/share/jadx-headless-mcp-all.jar'),
)


def resolve_jadx_jar(jar=''):
    """jar 不入 git（40MB，违反产物纪律）：三路解析，都取不到返回「无法判定」。"""
    import shutil
    for c in ((jar,) if jar else ()) + (os.environ.get('JADX_MCP_JAR', ''),) + JADX_JAR_CANDIDATES:
        if c and os.path.isfile(c):
            if not shutil.which('java'):
                return '', 'java 不在 PATH（无法判定）'
            return c, ''
    return '', 'jadx jar 未找到（--jar / JADX_MCP_JAR / 常见路径三路皆空），无法判定'


class FakeTransport:
    """离线 selftest 注入用：不启动 java、不联网。

    request(method, params) 按 MCP JSON-RPC 形态返回响应；call_results 可覆盖特定
    工具的 tools/call 返回值（字符串=原文，dict=转 JSON），用来造正向/反向场景。
    """

    def __init__(self, tools=None, call_results=None, fail=False):
        self.tools = tools if tools is not None else [
            'status', 'load_apk', 'search_classes_by_keyword']
        self.call_results = call_results or {}
        self.fail = fail
        self.calls = []

    def request(self, method, params):
        self.calls.append((method, params))
        if self.fail:
            return {'error': {'code': -1, 'message': 'transport down'}}
        if method == 'initialize':
            return {'jsonrpc': '2.0', 'id': 1, 'result': {'protocolVersion': '2024-11-05'}}
        if method == 'tools/list':
            return {'jsonrpc': '2.0', 'id': 2,
                    'result': {'tools': [{'name': n} for n in self.tools]}}
        if method == 'tools/call':
            name = (params or {}).get('name')
            payload = self.call_results.get(name, {'ok': True, 'tool': name})
            text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
            return {'jsonrpc': '2.0', 'id': 3,
                    'result': {'content': [{'type': 'text', 'text': text}]}}
        return {'jsonrpc': '2.0', 'id': 0, 'result': {}}


class JadxMCP:
    """jadx-headless-mcp 0.7.1 的 26 工具泛化客户端。

    两种通道：
      · 真实：JadxMCP(jar).start() 起 java 子进程走 stdio JSON-RPC；
      · 离线：JadxMCP(transport=FakeTransport(...)).start()，供 selftest / 无 java 环境。
    call(name, arguments) 是全量接线的通用入口；load_apk/search/close 保留兼容签名。
    """

    def __init__(self, jar=None, timeout=300, transport=None):
        self.jar = jar
        self.timeout = timeout
        self.proc = None
        self.transport = transport
        self._id = 0
        self.tool_names = []

    def start(self):
        if self.transport is None:
            self.proc = subprocess.Popen(
                ['java', '-jar', self.jar, '--transport', 'stdio'],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, bufsize=0)
        init = self._call('initialize', {
            'protocolVersion': '2024-11-05', 'capabilities': {},
            'clientInfo': {'name': 'foundry-core-jadx-engine', 'version': '1'}}, 120)
        if not init or 'result' not in init:
            raise RuntimeError('MCP initialize 无响应')
        if self.transport is None:
            # notifications/initialized 是通知（无 id、无响应）——离线通道不写盘
            self.proc.stdin.write((json.dumps({
                'jsonrpc': '2.0', 'method': 'notifications/initialized',
                'params': {}}) + '\n').encode())
            self.proc.stdin.flush()
        tl = self._call('tools/list', {}, 60)
        self.tool_names = [t.get('name') for t in
                           (((tl or {}).get('result') or {}).get('tools') or [])]
        return self

    def _call(self, method, params, timeout=None):
        if self.transport is not None:
            return self.transport.request(method, params)
        self._id += 1
        i = self._id
        self.proc.stdin.write((json.dumps({
            'jsonrpc': '2.0', 'id': i, 'method': method,
            'params': params}) + '\n').encode())
        self.proc.stdin.flush()
        t0 = time.time()
        lim = timeout or self.timeout
        while time.time() - t0 < lim:
            line = self.proc.stdout.readline()
            if not line:
                return None
            s = line.decode('utf-8', 'ignore').strip()
            if not s.startswith('{'):
                continue
            try:
                d = json.loads(s)
            except Exception:
                continue
            if d.get('id') == i:
                return d
        return None

    @staticmethod
    def _text(r):
        if not r or 'error' in r:
            return ''
        return '\n'.join(c.get('text', '') for c in
                         ((r.get('result') or {}).get('content') or []))

    def call(self, name, arguments=None, timeout=None, as_json=True):
        """W2 全量接线通用入口：按工具名调 26 个工具中的任意一个。

        arguments 由调用方按 core.CHAIN_RULES 构造（参数取上一步真实返回）；
        引擎只管传输，不重复判据（M2）。as_json=True 时尽量解析文本为对象，
        解析不了返回 {'_raw':..., 'state':'UNKNOWN'}，不折叠成空（B-02 三态）。

        W2 真调复验暴露：jadx 服务端反编译某类时可能崩子进程，写 stdin 会抛
        BrokenPipeError/OSError。门面统一收敛成 {'state':'PROC_DEAD'} 三态 dict，
        调用方不必各自兜、也绝不假装成功（三态不折叠）。这是门面健壮性，不改判据。
        """
        try:
            r = self._call('tools/call',
                           {'name': name, 'arguments': arguments or {}}, timeout)
        except (BrokenPipeError, OSError) as e:
            dead = {'state': 'PROC_DEAD', 'error': f'{type(e).__name__}: {e}'}
            return dead if as_json else ''
        txt = self._text(r)
        if not as_json:
            return txt
        try:
            return json.loads(txt)
        except Exception:
            return {'_raw': txt, 'state': 'UNKNOWN'}

    # ── 兼容 shellcrack 的 3 个方法（调用行零改动）──
    def load_apk(self, path):
        r = self.call('load_apk', {'path': path}, 600)
        return r if isinstance(r, dict) else {'state': 'UNKNOWN'}

    def search(self, term, count=25):
        r = self.call('search_classes_by_keyword',
                      {'search_term': term, 'search_in': 'class', 'count': count}, 180)
        return r if isinstance(r, dict) else {'items': [], 'count': 0}

    def close(self):
        if self.proc:
            try:
                self.proc.terminate()
            except Exception:
                pass


def selftest():
    """正反向：正向 FakeTransport 驱动全部 26 工具名；反向造错三态不折叠。

    判据范围说明（病15）：tools/list 拿回的名册由 core.names_ok 判 26 个；
    本引擎只验证「call 能泛化驱动任意工具名」，不越界替 core 做名册判定。
    """
    fails = []

    def ck(label, cond, detail=''):
        print(('  ✓ ' if cond else '  ✗ ') + label + ('' if cond else '  ← ' + str(detail)))
        if not cond:
            fails.append(label)

    here = os.path.dirname(os.path.abspath(__file__))
    schema = json.load(open(os.path.join(here, 'tools_schema.json'), encoding='utf-8'))
    names = [t['name'] for t in schema['tools']]

    print('── 正向（离线 FakeTransport）──')
    ft = FakeTransport(tools=names)
    m = JadxMCP(transport=ft).start()
    ck('tools/list 拿回 26 个工具名', len(m.tool_names) == 26, len(m.tool_names))
    ok_all = True
    for n in names:
        r = m.call(n, {})
        ok_all = ok_all and isinstance(r, dict) and r.get('ok') is True
    ck('call() 泛化驱动 26 工具全部走通', ok_all)
    ck('load_apk 兼容方法返回 dict', isinstance(m.load_apk('/tmp/x.apk'), dict))
    ck('search 兼容方法返回 dict', isinstance(m.search('spider'), dict))
    ck('call 记录进 transport.calls（真调链可溯源）',
       any(c[0] == 'tools/call' for c in ft.calls))

    print('── 反向（造错必红 / 三态不折叠）──')
    bad = JadxMCP(transport=FakeTransport(fail=True))
    started = True
    try:
        bad.start()
    except RuntimeError:
        started = False
    ck('transport 报错 → initialize 无响应判红', not started)
    ck('transport 全错时 call 返回 UNKNOWN 不崩',
       bad.call('status', {}).get('state') == 'UNKNOWN')
    ft2 = FakeTransport(tools=names,
                        call_results={'get_resource_file': '<xml>not json</xml>'})
    m2 = JadxMCP(transport=ft2).start()
    r = m2.call('get_resource_file', {'name': 'AndroidManifest.xml'})
    ck('非 JSON 文本三态不折叠（_raw + UNKNOWN）',
       r.get('state') == 'UNKNOWN' and '_raw' in r, r)
    ck('未知名不伪造 success（引擎只做传输）',
       isinstance(m.call('no_such_tool', {}), dict))

    # W2 真调复验暴露的进程崩溃形态：写通道抛 BrokenPipeError → 门面收敛 PROC_DEAD
    class _DeadPipe(FakeTransport):
        def request(self, method, params):
            if method == 'tools/call':
                raise BrokenPipeError(32, 'Broken pipe')
            return super().request(method, params)
    dead_m = JadxMCP(transport=_DeadPipe(tools=names)).start()
    dr = dead_m.call('get_class_source', {'class_name': 'X'})
    ck('死进程写通道 → 门面返回 PROC_DEAD 三态（不抛/不假绿）',
       isinstance(dr, dict) and dr.get('state') == 'PROC_DEAD', dr)
    ck('死进程 as_json=False → 空文本不折叠',
       dead_m.call('get_resource_file', {'name': 'x'}, as_json=False) == '')

    print(f'\n结果：{"全部通过（正向绿 / 反向红）" if not fails else str(len(fails)) + " 项失败"}')
    return 0 if not fails else 2


def main(argv):
    if '--selftest' in argv:
        return selftest()
    print(__doc__)
    print('通用入口：JadxMCP(transport=FakeTransport()).start() 后 call(name, args)。')
    return 0


if __name__ == '__main__':
    import sys
    raise SystemExit(main(sys.argv))
