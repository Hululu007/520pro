#!/usr/bin/env python3
"""FongMi 系壳的本地推送协议（S231 L1747-1773 通道层移植）。

原文在 Android 端用 `from java import jclass` 取 `com.github.catvod.Proxy.getPort()`，
拿到壳自己开的本地 HTTP 端口，再 POST 一条 sync 指令把接口地址推进壳里——用户不用
在电视上拿遥控器一个字一个字敲 URL。这是「一键换源」的真正正门。

端侧能力在服务器/沙箱里不存在，所以端口来源做成**三态**（B-02 不许折叠）：

    --port 显式  >  环境变量 FONGMIPORT  >  java 桥（仅 Android 在壳内可用）
    三者都取不到  →  返回码 3 =「无法判定」（不是失败：这台机器上根本没有这条通道）

配合 adb：`adb forward tcp:9978 tcp:9978` 之后 `--port 9978` 即可从电脑推。

两个必须原样保留的坑（原文都踩过，去掉任意一个都会变成「推不动且报错看不懂」）：

  ⚠ `ProxyHandler({})` 置空代理：环境里只要存在 http_proxy/https_proxy，urllib 会把
    `127.0.0.1:9978` 的请求也丢给代理 → 报「连接被拒」，而壳明明开着。这是最典型的
    「本地回环被系统代理劫持」，排查时几乎没人先怀疑代理。
  ⚠ `Connection: close`：壳的本地服务是单线程 NanoHTTPD，keep-alive 连接不回话会把它
    整个挂住，后续所有请求超时。

安全边界：只往 127.0.0.1 推，不接外部地址（--port 之外没有 host 参数，写死回环）。
"""

import json
import os
import socket
import sys
import urllib.parse
import urllib.request

__all__ = ['port_from', 'probe_port', 'push', 'build_body', 'ACTION_PATH']

ACTION_PATH = '/action?do=sync&mode=1&type=history'
ENV_KEY = 'FONGMIPORT'
PROXY_DEFAULT = ''          # 默认不加图代理；壳侧按需改


def port_from(explicit=None, env=None):
    """端口来源三态。返回 (port, source)；取不到返回 (0, '')。

    source 取值：'arg' / 'env' / 'java' / ''——判据要看**来源**，只看端口号分不清
    「用户给的」和「碰巧 9978 有东西在听」。
    """
    if explicit:
        try:
            p = int(explicit)
            if 0 < p < 65536:
                return p, 'arg'
        except (TypeError, ValueError):
            pass
    v = os.environ.get(ENV_KEY) if env is None else env
    if v:
        try:
            p = int(v)
            if 0 < p < 65536:
                return p, 'env'
        except (TypeError, ValueError):
            pass
    try:                                    # 仅 Android 壳内可用；import 失败是正常的
        from java import jclass             # noqa: F401
        p = int(jclass('com.github.catvod.Proxy').getPort())
        if p > 0:
            return p, 'java'
    except Exception:
        pass
    return 0, ''


def probe_port(port, timeout=1.0):
    """回环端口有没有人听。True/False 都是**真结论**，不含「无法判定」。"""
    try:
        with socket.create_connection(('127.0.0.1', int(port)), timeout=timeout):
            return True
    except OSError:
        return False


def build_body(url, name='推送接口'):
    """原文字段：config 是 JSON 串，targets 空数组，force=false，整体 urlencode。"""
    config = json.dumps({'type': 0, 'url': url, 'name': name},
                        ensure_ascii=False, separators=(',', ':'))
    return urllib.parse.urlencode({'config': config, 'targets': '[]', 'force': 'false'})


def push(url, name='推送接口', *, port, dry_run=False, timeout=5):
    """推一条 sync。返回 (ok, msg)：ok=True 成功 / False 失败 / None 无法判定。

    None 的两种情形（都不是失败）：端口没人听（本机没开壳、没做 adb forward）、
    端口取不到。把它们报成 False 会让人去查协议对不对，方向就错了。
    """
    if not url or not str(url).strip():
        return False, 'url 为空'
    port = int(port or 0)
    if port <= 0:
        return None, (f'取不到本地端口（--port / {ENV_KEY} / java 桥三路皆空）——'
                      '无法判定，请确认壳是否在本机运行，或先 adb forward')
    if not probe_port(port):
        return None, (f'127.0.0.1:{port} 无监听——无法判定：端口没开（壳未运行或未做 '
                      'adb forward tcp:N tcp:N）')

    body = build_body(url, name).encode('utf-8')
    ep = 'http://127.0.0.1:%d%s' % (port, ACTION_PATH)
    if dry_run:
        return True, f'[dry-run] 将 POST {ep}\n  body: {body.decode("utf-8")}'

    req = urllib.request.Request(ep, data=body, headers={
        'Content-Type': 'application/x-www-form-urlencoded; charset=utf-8',
        'Connection': 'close',          # 见 module docstring：keep-alive 会挂死 NANOHTTPD
    })
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # ⚠ 置空代理
    try:
        with opener.open(req, timeout=timeout) as r:
            code = r.getcode()
            txt = r.read(200).decode('utf-8', 'ignore')
    except Exception as e:
        return False, f'推送失败：{type(e).__name__}: {e}'
    if 200 <= code < 300:
        return True, f'已推送：{url} → 127.0.0.1:{port} (HTTP {code}){(" " + txt) if txt.strip() else ""}'
    return False, f'壳返回 HTTP {code}：{txt[:120]}'


# ─────────────────────────── CLI ───────────────────────────

def _selftest():
    """离线自检：起一个本地假 Proxy，断言路径/字段/代理绕过/三态，全离线。"""
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    fails = []

    def chk(name, cond, detail=''):
        print(f'[{"OK " if cond else "FAIL"}] {name}' + ('' if cond else f'  {detail}'))
        if not cond:
            fails.append(name)

    got = {'n': 0, 'path': '', 'body': '', 'ctype': ''}

    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            n = int(self.headers.get('Content-Length') or 0)
            got['n'] += 1
            got['path'] = self.path
            got['body'] = self.rfile.read(n).decode('utf-8', 'ignore')
            got['ctype'] = self.headers.get('Content-Type') or ''
            self.send_response(200)
            self.send_header('Content-Length', '2')
            self.end_headers()
            self.wfile.write(b'ok')

        def log_message(self, *a):
            pass

    srv = HTTPServer(('127.0.0.1', 0), H)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        # 正：真推一条，断言服务端收到了什么
        ok, msg = push('http://x.test/api.php/provide/vod/', '全部PY源', port=port)
        chk('推送成功返回 True', ok is True, msg)
        chk('路径与原文一致', got['path'] == ACTION_PATH, got['path'])
        chk('Content-Type 为表单', 'x-www-form-urlencoded' in got['ctype'], got['ctype'])
        q = urllib.parse.parse_qs(got['body'])
        chk('body 含 config/targets/force 三字段',
            set(q) == {'config', 'targets', 'force'}, str(list(q)))
        cfg = json.loads(q['config'][0])
        chk('config.type=0', cfg.get('type') == 0, str(cfg))
        chk('config.url 原样', cfg.get('url') == 'http://x.test/api.php/provide/vod/', str(cfg))
        chk('config.name 原样', cfg.get('name') == '全部PY源', str(cfg))
        chk('targets 为空数组', q['targets'][0] == '[]', q['targets'][0])
        chk('force=false 是字符串', q['force'][0] == 'false', q['force'][0])

        # 反：系统代理存在时**仍须能推**（ProxyHandler({}) 的判据）
        old = {k: os.environ.get(k) for k in ('http_proxy', 'HTTP_PROXY', 'no_proxy', 'NO_PROXY')}
        try:
            os.environ['http_proxy'] = 'http://127.0.0.1:1'   # 一个必定连不上的代理
            os.environ.pop('no_proxy', None)
            os.environ.pop('NO_PROXY', None)
            n0 = got['n']
            ok2, msg2 = push('http://x.test/api.php', port=port)
            chk('环境有 http_proxy 时仍能推通（未被劫持）', ok2 is True and got['n'] == n0 + 1, msg2)
        finally:
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

        # 正：dry-run 不发请求，但给出将要发的 body
        n1 = got['n']
        ok3, msg3 = push('http://x.test/api.php', port=port, dry_run=True)
        chk('dry-run 不发真请求', got['n'] == n1, str(got['n']))
        chk('dry-run 打印 body', 'config=' in msg3, msg3[:80])

        # 三态：端口没人听 → None（无法判定），不是 False
        import socket as _s
        s = _s.socket()
        s.bind(('127.0.0.1', 0))
        dead = s.getsockname()[1]
        s.close()                                   # 拿到一个刚释放、确定没监听的端口
        ok4, msg4 = push('http://x.test/api.php', port=dead)
        chk('端口无监听 → 无法判定（None 而非 False）', ok4 is None, f'{ok4} {msg4}')
        ok5, msg5 = push('http://x.test/api.php', port=0)
        chk('端口取不到 → 无法判定（None）', ok5 is None, f'{ok5} {msg5}')
        # 反：url 为空才是真失败
        ok6, _ = push('', port=port)
        chk('url 空 → 真失败（False）', ok6 is False, str(ok6))
    finally:
        srv.shutdown()

    # 端口来源优先级
    chk('--port 优先于 env', port_from(1234, env='5678') == (1234, 'arg'), str(port_from(1234, env='5678')))
    chk('无参取 env', port_from(None, env='5678') == (5678, 'env'), str(port_from(None, env='5678')))
    chk('越界端口被拒（70000）', port_from(70000, env='') == (0, ''), str(port_from(70000, env='')))
    chk('非数字端口被拒', port_from('abc', env='') == (0, ''), str(port_from('abc', env='')))
    chk('env 为空时回落 java 桥（本机无 → 0）', port_from(None, env='')[0] == 0)

    print()
    if fails:
        print(f'✗ pushconfig 自检 {len(fails)} 项失败：{fails}')
        return 1
    print('✓ pushconfig 自检全部通过（S231 L1747-1773 通道层：FongMi 本地推送）')
    return 0


def main(argv):
    if '--selftest' in argv:
        return _selftest()
    a = {'url': '', 'name': '推送接口', 'port': 0, 'dry': '--dry-run' in argv}
    for k in ('--url', '--name', '--port'):
        if k in argv:
            i = argv.index(k)
            v = argv[i + 1] if i + 1 < len(argv) else ''
            if k == '--url':
                a['url'] = v
            elif k == '--name':
                a['name'] = v
            else:
                a['port'] = v
    if not a['url']:
        print(__doc__)
        return 2
    port, src = port_from(a['port'])
    if not src:
        print('✗ 无法判定：端口三路皆空（--port / FONGMIPORT / java 桥）', file=sys.stderr)
        return 3
    ok, msg = push(a['url'], a['name'], port=port, dry_run=a['dry'])
    print(('✓ ' if ok else ('? ' if ok is None else '✗ ')) + msg)
    print(f'  端口来源：{src}')
    return 0 if ok else (3 if ok is None else 1)


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
