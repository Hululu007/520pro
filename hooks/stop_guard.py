#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""stop_guard.py — 回合末拽回（Stop 事件 · B-13 完成态凭落点）

为什么要有它（520 的高频毛病）:
  「完成 / 已修复 / 全部通过」是本项目最常被滥用的一句话。规则文件里写了
  B-13「说完成必须同时给落点」，但那是**软约束**——模型想省就省，用户只能事后发现。
  Stop 是唯一能在「这条消息即将成为最终答复」这个时刻介入的地方。

协议（实测确认，2026-11-14）:
  Stop payload 含 `last_assistant_message`（本轮最后一条回复全文）+ `transcript_path`
  + `stop_hook_active`。exit 2 且 stderr 有内容时，平台把该内容作为
  `stopHookFeedback` 注入回模型（CLI 侧以 <system-reminder data-role="hook"> 呈现），
  模型被拉回来继续——**这不是硬阻断，是拽回**：说错了要重说，但话说出口了。

判据（保守优先，误报会让人关掉钩子 = 全域失防）:
  同时满足三条才拽回：
    ① 最后一条消息里出现「任务完成」类断言词
    ② 该断言词不在否定语境里（「未完成 / 没通过 / 无法验证」不算）
    ③ 全文找不到任何一个落点证据（rc= / 退出码 / commit sha / 文件:行号 / 0 ✗ / ✓ N）
  任一证据存在即放行——宁可放过，不可误伤。

防死循环:
  `stop_hook_active` 为真时一律放行（平台已因上一次拽回重入）。
  另加本机计数：同一 session 连续拽回上限 MAX_RETRY 次，超过即放行并留痕，
  避免判据写坏导致会话卡死。
"""
import argparse
import json
import os
import re
import sys

STATE = os.path.join(os.path.expanduser('~'), '.codebuddy', 'hooks', '.stop_guard_state')
MAX_RETRY = 2

# 断言词：只收「宣称一件事已经办完」的说法，不收「完成了 X 功能」这类过程描述
ASSERT_PATS = [
    r'已完成', r'已修复', r'已落地', r'已通过', r'全部通过', r'验证通过',
    r'已上线', r'已部署', r'已提交并推送', r'修复完成', r'改完了', r'做完了',
    r'已闭环', r'搞定了',
]

# 否定语境：断言词前 4 字内出现这些，视为「没做完」的正常表述，不拽回
NEG_RE = re.compile(r'(?:未|没|没有|无法|不能|不算|尚未|并不|不会|还没|未完全)'
                    r'[\u4e00-\u9fa5]{0,4}$')

# 落点证据：任一条命中即认为给了凭据（宽松，宁放过不误伤）
EVIDENCE_PATS = [
    r'\brc\s*=\s*\d+',                      # rc=0
    r'退出码\s*[:：]?\s*\d*',                # 退出码 0
    r'(?:commit|提交|sha)\s*[:：=]?\s*`?[0-9a-f]{7,40}',   # commit 6ed5df1
    r'(?=[0-9a-f]*[a-f])[0-9a-f]{7,40}',     # 裸 sha（必含 a-f，避免把纯数字当 sha）
    r'[\w./-]+\.(?:py|md|sh|json|js|ts|tsx|yml|yaml|html|css|toml):\s*\d+',  # 文件:行号
    r'0\s*✗',                                # 0 ✗
    r'✓\s*\d+',                              # ✓ 66
    r'\d+\s*例.{0,6}(?:通过|0\s*失败)',        # 39 例 0 失败
    r'第\s*\d+\s*行',                         # 第 120 行
]


def _read_state():
    try:
        return json.load(open(STATE, encoding='utf-8'))
    except Exception:
        return {}


def _write_state(d):
    try:
        os.makedirs(os.path.dirname(STATE), exist_ok=True)
        json.dump(d, open(STATE, 'w', encoding='utf-8'))
    except Exception:
        pass


def has_assert(text):
    """有没有「宣称完成」，且不在否定语境。"""
    for p in ASSERT_PATS:
        for m in re.finditer(p, text):
            if NEG_RE.search(text[max(0, m.start() - 6):m.start()]):
                continue
            return True
    return False


def has_evidence(text):
    for p in EVIDENCE_PATS:
        if re.search(p, text):
            return True
    return False


def judge(text):
    """返回 (是否拽回, 原因)。"""
    if not text or not text.strip():
        return False, '空消息'
    if not has_assert(text):
        return False, '无完成断言'
    if has_evidence(text):
        return False, '有落点证据'
    return True, '宣称完成但全文无任何落点证据'


MSG = ('⛔ B-13 完成态凭落点：上一条回复宣称「完成 / 通过」，但全文找不到任何落点证据。\n'
       '落点证据指：改动的文件与行号、跑过的命令与退出码（rc=0）、commit sha，'
       '或判据输出原文。\n'
       '请二选一：①补上上述证据后重发结论；②把结论改写成「未验证 / 无法判定」。\n'
       '这条拦的是「我看了一下，应该没问题」——它不算完成。')


def main():
    ap = argparse.ArgumentParser(description='回合末拽回（Stop · B-13）')
    ap.add_argument('--check', metavar='TEXT', help='只判定一段文本，打印结论（调试/测试用）')
    ap.add_argument('--list', action='store_true', help='列出判据')
    ap.add_argument('--probe', action='store_true', help='查看拽回观测（hit/via：判定走过哪条分支）')
    a = ap.parse_args()

    if a.probe:
        st = _read_state()
        if not st:
            print('（无拽回记录：判据从未命中，或钩子未被调用——病13 三态要分清）')
            return 0
        out = {'event': 'Stop', 'hit': False, 'via': 'pass', 'sessions': {}}
        for sid, v in st.items():
            n = int(v.get('n', 0))
            out['sessions'][sid] = {
                'retries': n,
                'gave_up': bool(v.get('gave_up')),
                'last_why': v.get('last_why', ''),
            }
            if n > 0:
                out['hit'] = True
                out['via'] = 'deny'
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    if a.list:
        print('断言词：', ' / '.join(ASSERT_PATS))
        print('否定豁免：', NEG_RE.pattern)
        print('落点证据（任一即放行）：')
        for p in EVIDENCE_PATS:
            print('  ', p)
        return 0

    if a.check is not None:
        d, why = judge(a.check)
        print(json.dumps({'deny': d, 'why': why}, ensure_ascii=False))
        return 2 if d else 0

    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0

    # 平台已因上次拽回重入 → 必须放行，否则死循环
    if data.get('stop_hook_active'):
        return 0

    sid = str(data.get('session_id') or '')
    st = _read_state()
    n = int((st.get(sid) or {}).get('n', 0))
    if n >= MAX_RETRY:
        st.setdefault(sid, {})['n'] = n
        st[sid]['gave_up'] = True
        _write_state(st)
        return 0

    text = str(data.get('last_assistant_message') or '')
    deny, why = judge(text)
    if not deny:
        return 0

    st.setdefault(sid, {})['n'] = n + 1
    st[sid]['last_why'] = why
    _write_state(st)
    sys.stderr.write(MSG + '\n')
    return 2


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)          # fail-open：判据坏了不该卡死会话
