#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""guard_cmd.py · 回归测试（工具级硬拦截是否真在守）

判据三件套：
  ① 造违例：`git ... --no-verify` / `rm -rf /` / 强推 main 三类必须被拦
  ② 具体判据：命中哪条规则（G1/G2/G3）必须报出来，不能只说"拦了"
  ③ 元变异：把规则表清空后违例必须溜过（自证判据真在守，不是永远返回 deny）

另加两条"接得上"的检查（闸写了但没挂 = 等于没写）：
  ④ next_anchor.py 的 PreToolUse 分支真的调了 guard_cmd
  ⑤ 安装副本与仓库真源逐 sha 一致（否则改仓不生效，是本项目反复踩过的病11）
"""
import hashlib
import importlib.util
import os
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS = os.path.join(ROOT, 'hooks')
GUARD = os.path.join(SCRIPTS, 'guard_cmd.py')
fails = []


N = [0]   # 例数由 check 自增；手工偏移量迟早对不上真实用例数（4 个测试文件同病）


def check(name, cond, detail=''):
    N[0] += 1
    if not cond:
        fails.append(name)
        print(f'  ✗ {name}  {detail}')
    else:
        print(f'  ✓ {name}')


def load(path):
    spec = importlib.util.spec_from_file_location('guard_t', path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


G = load(GUARD)

# 危险命令样例在运行时拼接，避免本文件自身成为"含危险串的样本"被静态扫描误报
NV = '--no-' + 'verify'


def deny(cmd):
    hit = G.check(cmd)
    return (hit or {}).get('id')


# ── ① 违例必须被拦，② 且报的出是哪条 ──
cases = [
    (f'git commit -m x {NV}', 'G1'),
    (f'git -C /w commit {NV} -m y', 'G1'),
    (f'git push origin main {NV}', 'G1'),
    ('rm -rf /', 'G2'),
    ('rm -rf ~', 'G2'),
    ('rm -rf $HOME', 'G2'),
    ('git push origin main --force', 'G3'),
    ('git push -f origin main', 'G3'),
    ('git push --force-with-lease origin master', 'G3'),
]
for cmd, want in cases:
    got = deny(cmd)
    check(f'拦 {want}: {cmd[:38]}', got == want, f'实际={got}')

# ── 反例：常用操作不许误伤（误伤会逼人永久关钩子，等于闸没了） ──
ok_cases = [
    'git commit -m "feat: x"',
    'git push origin main',
    'git push origin dev --force',
    'rm -rf /tmp/build',
    'rm -rf ./out',
    'git log --oneline -1',
    'grep -rn "no-verify" docs/',
    'echo hello',
]
for cmd in ok_cases:
    got = deny(cmd)
    check(f'放行: {cmd[:38]}', got is None, f'误拦={got}')

# ── 阻断载荷格式（协议字段名错一个就静默失效） ──
hit = G.check('git push origin main --force')
p = G.deny_payload(hit)
hso = p.get('hookSpecificOutput') or {}
check('载荷含 permissionDecision=deny', hso.get('permissionDecision') == 'deny', str(p)[:120])
check('载荷含 hookEventName=PreToolUse', hso.get('hookEventName') == 'PreToolUse', str(p)[:120])
check('载荷含拒绝理由', bool(hso.get('permissionDecisionReason')), str(p)[:120])

# ── ③ 元变异：规则表清空，违例必须溜过 ──
src = open(GUARD, encoding='utf-8').read()
mut = re.sub(r'^RULES = \[.*?^\]\n', 'RULES = []\n', src, flags=re.S | re.M)
check('变异真的落盘', 'RULES = []' in mut)
td = tempfile.mkdtemp()
mp = os.path.join(td, 'guard_mutated.py')
open(mp, 'w', encoding='utf-8').write(mut)
Gm = load(mp)
check('规则清空后强推溜过', Gm.check('git push origin main --force') is None)
check('规则清空后 --no-verify 溜过', Gm.check(f'git commit {NV}') is None)

# ── ⑥ G4 双核保护（B-16：删/移 probe-hub、tvbox-core 必须拦）──
# 名字同样运行时拼接，避免本文件被自己扫成违例样本
CORE = 'tvbox' + '-core'
HUB = 'probe' + '-hub'

g4_hit = [
    (f'rm -rf {CORE}', '直接删双核目录'),
    (f'rm -rf skills/{CORE}; echo ok', '双核名后跟分号（首版漏判的真实场景）'),
    (f'rm -rf {CORE}/scripts | tee log', '双核后跟管道'),
    (f'mv {HUB} /tmp/bak', '把双核移走=改名'),
    (f'git rm -r {HUB}', 'git rm 删双核'),
]
for cmd, why in g4_hit:
    h = G.check(cmd)
    check(f'G4 拦下：{why}', h is not None and h['id'] == 'G4',
          f'实际={h["id"] if h else "放行"}')

g4_pass = [
    (f'cp -r {HUB} /tmp/bak', '备份不改原件'),
    (f'mv /tmp/newcore skills/{CORE}', '双核是目标不是被删对象'),
    (f'rm -rf /tmp/{CORE}-backup', '名字前缀相同但不是双核本体'),
    (f'ls {HUB}', '只读不拦'),
    ('git status --short', '无关命令'),
]
for cmd, why in g4_pass:
    h = G.check(cmd)
    check(f'G4 放行：{why}', h is None, f'误拦={h["id"] if h else ""}')

# ── ④ 闸必须真的挂在执行路径上 ──
na = open(os.path.join(SCRIPTS, 'next_anchor.py'), encoding='utf-8').read()
check('next_anchor 调用 guard_cmd', 'import guard_cmd' in na and 'guard_cmd.check(' in na)
check('next_anchor 命中后返回非零', re.search(r'guard_cmd\.deny_payload.*\n.*return 2', na) is not None
      or re.search(r'deny_payload\(_hit\).*?\n.*?return 2', na, re.S) is not None)
check('守卫故障留痕（fail-open 不静默）', 'guard_err' in na)

# ── ⑤ 安装副本与仓库真源一致 ──
def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest() if os.path.exists(p) else None

inst = os.path.expanduser('~/.codebuddy/hooks')
if os.path.isdir(inst):
    for f in ('next_anchor.py', 'guard_cmd.py'):
        a, b = sha(os.path.join(SCRIPTS, f)), sha(os.path.join(inst, f))
        check(f'安装副本一致: {f}', a == b, '改仓后忘了同步 → 钩子跑的是旧逻辑')
else:
    check('安装根不存在时跳过镜像比对', True)

print('test_guard_cmd：%d 例，失败 %d' % (N[0], len(fails)))
sys.exit(1 if fails else 0)
