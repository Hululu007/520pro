#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""stop_guard.py · 回归测试（B-13 完成态凭落点，Stop 拽回）

判据三件套：
  ① 造违例：宣称完成且零落点证据 → 必须拽回（stdout 出 JSON decision:block）
  ② 具体判据：判定理由要写清是「无证据」还是「否定语境豁免」
  ③ 元变异：清空断言词表后，同样的违例必须溜过（自证判据真在守）

另加三条"接得上"的检查：
  ④ stop_hook_active 为真必须放行（平台重入，防死循环）
  ⑤ 同 session 连续拽回达上限后放行并留痕（判据写坏也不能卡死会话）
  ⑥ settings.json 真的注册了 stop_guard.py（写了没挂 = 等于没写）
"""
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HOOKS = os.path.join(ROOT, 'hooks')
GUARD = os.path.join(HOOKS, 'stop_guard.py')
fails = []


N = [0]   # 例数由 check 自增；手工偏移量迟早对不上真实用例数（4 个测试文件同病）


def check(name, cond, detail=''):
    N[0] += 1
    if not cond:
        fails.append(name)
        print(f'  ✗ {name}  {detail}')
    else:
        print(f'  ✓ {name}')


def load(path, modname='sg'):
    spec = importlib.util.spec_from_file_location(modname, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


S = load(GUARD)

# 违例样例在运行时拼接，避免本文件被其它闸静态扫成违例样本
DONE = '已' + '完成'
ALLPASS = '全部' + '通过'

# ── ① 造违例：断言 + 零证据 → 必须拽回 ──
bad = [
    (f'{DONE}修复。', '最短断言'),
    (f'{ALLPASS}，可以收工了。', '全部通过'),
    ('搞定了，你看下。', '口语断言'),
    (f'{DONE}，三处都改好了，放心。', '断言 + 空口保证'),
]
for text, why in bad:
    d, reason = S.judge(text)
    check(f'拽回：{why}', d is True, f'实际={d}（{reason}）')

# ── ② 放行：有落点证据 / 否定语境 / 过程描述 ──
good = [
    (f'{DONE}，提交 6ed5df1', '有 sha'),
    (f'{DONE}，bash verify.sh → 0 ✗ / 2 ·（rc=0）', '有判据输出'),
    (f'已修复，改的是 hooks/stop_guard.py:118', '有文件:行号'),
    ('未完成，因为没有权限。', '否定语境'),
    ('无法验证，环境不可达。', '否定词开场'),
    ('这个函数完成了数据加载功能。', '过程描述不是任务断言'),
    ('39 例 0 失败', '只有判据无断言'),
    ('', '空消息'),
]
for text, why in good:
    d, reason = S.judge(text)
    check(f'放行：{why}', d is False, f'实际拽回（{reason}）')

# ── ③ 元变异：清空断言词表后，违例必须溜过 ──
src = open(GUARD, encoding='utf-8').read()
mut = re.sub(r'^ASSERT_PATS = \[.*?^\]', 'ASSERT_PATS = []', src, flags=re.S | re.M)
check('变异真的落盘', 'ASSERT_PATS = []' in mut)
td = tempfile.mkdtemp()
mp = os.path.join(td, 'stop_guard_mut.py')
open(mp, 'w', encoding='utf-8').write(mut)
Sm = load(mp, 'sg_mut')
d, _ = Sm.judge(f'{DONE}修复。')
check('断言表清空后违例溜过（判据不是恒真）', d is False, f'实际={d}')

# ── ④ stop_hook_active 放行（防死循环）──
r = subprocess.run(['python3', GUARD], input=json.dumps(
    {'session_id': 't-active', 'stop_hook_active': True,
     'last_assistant_message': f'{DONE}修复。'}), capture_output=True, text=True)
check('stop_hook_active=true 时放行', r.returncode == 0, f'rc={r.returncode}')

# ── ⑤ 连续拽回达上限后放行并留痕 ──
sid = 't-max-retry'
# 先清历史计数：判据把状态写在 ~/.codebuddy/hooks/.stop_guard_state，
# 不清就会「第二次跑测试必红」——pre-commit 每次跑，等于每次都在给自己挖坑
_st = S._read_state()
_st.pop(sid, None)
S._write_state(_st)
payload = json.dumps({'session_id': sid, 'stop_hook_active': False,
                      'last_assistant_message': f'{DONE}修复。'})
res = []
for _ in range(S.MAX_RETRY + 2):
    p = subprocess.run(['python3', GUARD], input=payload,
                       capture_output=True, text=True)
    try:
        blk = json.loads(p.stdout.strip() or '{}').get('decision') == 'block'
    except Exception:
        blk = False
    res.append((p.returncode, blk, p.stderr.strip()[:40]))
check('前 MAX_RETRY 次拽回', all(rc == 0 and b for rc, b, _ in res[:S.MAX_RETRY]),
      f'实际={res[:S.MAX_RETRY]}')
check('达上限后放行', all(rc == 0 and not b for rc, b, _ in res[S.MAX_RETRY:]),
      f'实际={res[S.MAX_RETRY:]}')
# 协议：实测 exit 2 + stderr 拽不回，只有 JSON decision:block 能拽回。
# 这条防的是「以后有人好心把输出改回 exit 2」——那样钩子还在跑，但语义降级成事后可见。
check('拽回走 JSON decision:block（非 exit 2）',
      res[0][0] == 0 and res[0][1] and not res[0][2], f'实际={res[0]}')
st = json.load(open(S.STATE, encoding='utf-8'))
check('放行痕迹已登记', st.get(sid, {}).get('gave_up') is True, f'实际={st.get(sid)}')

# ── ⑥ 闸必须真的挂在执行路径上 ──
sp = os.path.expanduser('~/.codebuddy/settings.json')
regd = False
if os.path.exists(sp):
    try:
        d = json.load(open(sp, encoding='utf-8'))
        blob = json.dumps(d.get('hooks', {}).get('Stop', []), ensure_ascii=False)
        regd = 'stop_guard.py' in blob
    except Exception:
        regd = False
check('settings.json 注册了 stop_guard.py', regd, '写了没挂 = 等于没写')

print('test_stop_guard：%d 例，失败 %d' % (N[0], len(fails)))
sys.exit(1 if fails else 0)
