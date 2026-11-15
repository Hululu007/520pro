#!/usr/bin/env python3
"""wsrv.nl 图代理开关：把 py 源里的 IMG_PROXY 行原地改写（S231 L1866-1898 移植）。

解决的是「源写出来了、接口也活，但壳里封面全是破图」这一类问题：站点图片有防盗链，
TVBox 直连拿不到。正解不是去改壳，而是让源在拼接封面时套一层图片代理——
`https://wsrv.nl/?url=` 后面接原图地址，代理侧带 Referer 取图并回源缓存。

原文做法（`_apply_img_proxy`）：
  ① 开关状态存一个 `.imgproxy` 小文件；
  ② 遍历已生成目录下所有 `.py`，`re.sub(r'IMG_PROXY = ".*?"', ..., count=1)` 改第一处；
  ③ 改完重新推送，壳下拉刷新即生效。

本件的三处**有意差异**（都为了「不静默」）：

  · **默认 dry-run**：不 `--apply` 只打印将改哪些文件。原文点一下按钮就落盘，
    而这是批量改文件——批量不可逆动作要先给眼睛看（B-09）。
  · **统计分三类**：改了 N / 本来就对 M / 没这行 K。原文只报「已应用到 N 个 py」，
    看不出「是 3 个里改了 1 个」还是「30 个全改了」。
  · **写走 atomicio**：内容没变不碰文件（inode 不变），批量跑不改 mtime。

保留 `count=1`：文件里通常只有一处真赋值，注释里的示例不该被改；真有多处赋值说明
源本身有问题，改第一处后 `--check` 会把它报出来，比一次全改更安全。
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from atomicio import write_atomic           # noqa: E402  同技能内相对导入（自包含）

__all__ = ['PROXY_ON', 'scan', 'apply_proxy', 'state_path', 'read_state']

PROXY_ON = 'https://wsrv.nl/?url='
STATE_NAME = '.imgproxy'
# 原文是 `IMG_PROXY = ".*?"`（等号两边各一个空格）；这里放宽空白，避免生成器
# 写成 `IMG_PROXY=""` 时整批漏改——**漏改会静默**，比误改危险。
LINE_RE = re.compile(r'^([ \t]*IMG_PROXY[ \t]*=[ \t]*)"([^"]*)"', re.M)


def state_path(root):
    return os.path.join(root, STATE_NAME)


def read_state(root):
    """当前开关值；文件不存在返回 ''（= 关闭），与原文 _img_proxy 一致。"""
    try:
        with open(state_path(root), 'r', encoding='utf-8') as f:
            return f.read().strip()
    except OSError:
        return ''


def scan(root):
    """列出目录下所有 py 源：`[(path, value|None, kind)]`，kind ∈ ok / no_line / unreadable。

    **三态不许折叠**（B-02）：`no_line`（老源本来就没这行）与 `unreadable`（编码坏 /
    权限不足）对处置的含义相反——前者跳过即可，后者要报给人看。折叠成一个 None
    会让「这批文件全都读不了」表现为「这批文件全都没有 IMG_PROXY」，安静地假装成功。
    """
    out = []
    if not os.path.isdir(root):
        return out
    for fn in sorted(os.listdir(root)):
        if not fn.endswith('.py'):
            continue
        path = os.path.join(root, fn)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                code = f.read()
        except (OSError, UnicodeDecodeError):
            out.append((path, None, 'unreadable'))
            continue
        m = LINE_RE.search(code)
        out.append((path, m.group(2) if m else None, 'ok' if m else 'no_line'))
    return out


def apply_proxy(root, proxy=PROXY_ON, *, dry_run=True):
    """批量改写。返回统计 dict：changed / same / no_line / unreadable / details。

    proxy='' 表示关闭代理（写回空串，源就直连封面）。
    """
    proxy = (proxy or '').strip()
    st = {'changed': 0, 'same': 0, 'no_line': 0, 'unreadable': 0,
          'dry_run': bool(dry_run), 'details': []}
    files = scan(root)
    writes = []
    for path, cur, kind in files:
        if kind == 'unreadable':
            st['unreadable'] += 1
            st['details'].append(('unreadable', os.path.basename(path), '读不出（编码或权限）'))
            continue
        if kind == 'no_line':
            st['no_line'] += 1
            continue
        if cur == proxy:
            st['same'] += 1
            st['details'].append(('same', os.path.basename(path), cur))
            continue
        writes.append((path, cur))

    for path, cur in writes:
        name = os.path.basename(path)
        if dry_run:
            st['changed'] += 1
            st['details'].append(('would-change', name, f'{cur or "(空)"} → {proxy or "(空)"}'))
            continue
        try:
            with open(path, 'r', encoding='utf-8') as f:
                code = f.read()
            repl = proxy.replace('\\', '\\\\')      # 与原文一致：值里的反斜杠要转义
            new = LINE_RE.sub(lambda m: '%s"%s"' % (m.group(1), repl), code, count=1)
            if new == code:                       # 正则没命中（缩进/引号形态特殊）
                st['no_line'] += 1
                st['details'].append(('regex-miss', name, '扫到了值但替换未生效'))
                continue
            r = write_atomic(path, new)
            st['changed' if r == 'written' else 'same'] += 1
            st['details'].append((r, name, f'{cur or "(空)"} → {proxy or "(空)"}'))
        except Exception as e:                     # 单个文件失败不拖垮整批，但必须计数
            st['unreadable'] += 1
            st['details'].append(('error', name, f'{type(e).__name__}: {e}'))

    if not dry_run:
        try:
            state = 'same' if read_state(root) == proxy else write_atomic(state_path(root), proxy)
            st['state'] = state
        except Exception as e:
            st['state'] = f'error: {type(e).__name__}: {e}'
    return st


def _fmt(st, proxy=PROXY_ON):
    tag = '（dry-run，未落盘）' if st['dry_run'] else ''
    lines = [f'图代理 → {"关闭" if not proxy else proxy}{tag}',
             f'  改了 {st["changed"]} / 本来就对 {st["same"]} / 无该行 {st["no_line"]}'
             f' / 不可读 {st["unreadable"]}']
    for kind, name, note in st['details'][:20]:
        lines.append(f'    [{kind}] {name}  {note}')
    if len(st['details']) > 20:
        lines.append(f'    …还有 {len(st["details"]) - 20} 条')
    return '\n'.join(lines)


def _selftest():
    import shutil
    import tempfile

    fails = []

    def chk(name, cond, detail=''):
        print(f'[{"OK " if cond else "FAIL"}] {name}' + ('' if cond else f'  {detail}'))
        if not cond:
            fails.append(name)

    base = tempfile.mkdtemp(prefix='imgproxy_')
    try:
        os.makedirs(os.path.join(base, 'src'))
        d = os.path.join(base, 'src')
        pa = os.path.join(d, 'a.py')       # 待改
        pb = os.path.join(d, 'b.py')       # 已正确
        pc = os.path.join(d, 'c.py')       # 无该行
        pd = os.path.join(d, 'd.py')       # 注释里也有，只能改第一处
        open(pa, 'w', encoding='utf-8').write('IMG_PROXY = ""\nNAME="a"\n')
        open(pb, 'w', encoding='utf-8').write(f'IMG_PROXY = "{PROXY_ON}"\n')
        open(pc, 'w', encoding='utf-8').write('NAME="c"\n')
        open(pd, 'w', encoding='utf-8').write(
            'IMG_PROXY = ""\n# 示例：IMG_PROXY = "https://old.example/"\n')

        sc = scan(d)
        chk('scan 三态齐全（ok/ok/no_line/ok）',
            [k for _, _, k in sc] == ['ok', 'ok', 'no_line', 'ok'], str(sc))
        chk('scan 读出当前值', [v for _, v, _ in sc] == ['', PROXY_ON, None, ''], str(sc))

        # dry-run 一个字节都不碰
        ino = os.stat(pa).st_ino
        st = apply_proxy(d, PROXY_ON, dry_run=True)
        chk('dry-run 统计待改 2 个（a 与 d 首处都是空值）', st['changed'] == 2, str(st['changed']))
        chk('dry-run 不改文件（inode 不变）', os.stat(pa).st_ino == ino)
        chk('dry-run 不写状态文件', not os.path.exists(state_path(d)))

        # 真改
        st = apply_proxy(d, PROXY_ON, dry_run=False)
        chk('apply 改了 2 个', st['changed'] == 2, str(st))
        chk('apply 本来就对的计 same', st['same'] == 1, str(st))
        chk('apply 无该行的计 no_line', st['no_line'] == 1, str(st))
        chk('a.py 值已改对', f'IMG_PROXY = "{PROXY_ON}"' in open(pa, encoding='utf-8').read())
        chk('c.py 未被误改', 'IMG_PROXY' not in open(pc, encoding='utf-8').read())
        txt_d = open(pd, encoding='utf-8').read()
        chk('d.py 只改第一处（注释里的示例保留）',
            txt_d.count(f'IMG_PROXY = "{PROXY_ON}"') == 1 and 'old.example' in txt_d, txt_d)
        chk('状态文件写入开关值', read_state(d) == PROXY_ON, read_state(d))

        # 幂等：再跑一次全部 same
        st2 = apply_proxy(d, PROXY_ON, dry_run=False)
        chk('重跑幂等（changed=0 / same=3）',
            st2['changed'] == 0 and st2['same'] == 3, str(st2))
        chk('重跑状态文件返回 same', st2.get('state') == 'same', str(st2.get('state')))

        # 关闭
        st3 = apply_proxy(d, '', dry_run=False)
        chk('关闭后 a.py 为空值', 'IMG_PROXY = ""' in open(pa, encoding='utf-8').read())
        chk('关闭后状态文件为空', read_state(d) == '')

        # 反：目录不存在 → 空统计不炸
        st4 = apply_proxy(os.path.join(base, 'nope'), PROXY_ON, dry_run=True)
        chk('目录不存在返回空统计', st4['changed'] == 0 and st4['no_line'] == 0, str(st4))

        # 反：非 utf-8 文件计入不可读，而不是抛异常中断整批
        pbad = os.path.join(d, 'bad.py')
        open(pbad, 'wb').write(b'IMG_PROXY = "\xff\xfe"\n')
        st5 = apply_proxy(d, PROXY_ON, dry_run=True)
        chk('乱码文件计入不可读（不中断整批）', st5['unreadable'] == 1, str(st5['unreadable']))
    finally:
        import shutil as _s
        _s.rmtree(base, ignore_errors=True)

    print()
    if fails:
        print(f'✗ imgproxy 自检 {len(fails)} 项失败：{fails}')
        return 1
    print('✓ imgproxy 自检全部通过（S231 L1866-1898 通道层：wsrv.nl 图代理开关）')
    return 0


def main(argv):
    if '--selftest' in argv:
        return _selftest()
    a = {'dir': '', 'proxy': PROXY_ON, 'apply': '--apply' in argv}
    if '--dir' in argv:
        a['dir'] = argv[argv.index('--dir') + 1]
    if '--off' in argv:
        a['proxy'] = ''
    elif '--proxy' in argv:
        a['proxy'] = argv[argv.index('--proxy') + 1]
    if not a['dir'] or not os.path.isdir(a['dir']):
        print(__doc__)
        print('✗ 需要 --dir 指向已生成 py 源的目录', file=sys.stderr)
        return 2
    st = apply_proxy(a['dir'], a['proxy'], dry_run=not a['apply'])
    print(_fmt(st))
    if not a['apply']:
        print('  （加 --apply 才落盘）')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
