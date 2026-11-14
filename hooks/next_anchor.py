#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PreToolUse 锚点钩子：Bash 调用前，把当前仓库上一轮提交的 `Next:` 打出来。

为什么要有：会话中途最容易忘的是「下一步是什么」。`verify.sh` 只在提交时打印，
中途没有任何必经点；`docs/钩子来源判定.md` 已实证平台支持 PreToolUse——
这是唯一能在「每个动作」粒度上带出锚点的位置。

铁律（三条，缺一条就不该装）：
  ① **永不拦截**：任何异常 / 非 Bash / 非 git 仓 → exit 0 静默，绝不挡工具调用；
  ② **节流**：同一仓库 15 分钟只提示一次，避免刷屏把上下文塞满；
  ③ **只读**：除自己的状态文件外不写任何东西。

定位仓库根的三级回退（2026-11-14 实测：Bash 工具 cwd 恒为 /workspace，
不随命令里的 cd 持久化；只认 payload.cwd 会让钩子在多仓工作区永久静默）：
  ① payload.cwd 自身是 git 仓 → 用它；
  ② 从 command 里解析最后一个 `cd <绝对路径>` / `git -C <绝对路径>` → 用它；
  ③ 都不中 → 用 state 里记的 last_repo（仅当它仍是 git 仓）。

挂点与投递通道（2026-11-14 实测，别凭直觉改）：
  · **PreToolUse**：exit 0 时 stdout **不进模型上下文**——实测命中后 state 有记录、
    工具输出里却看不到 `⏭` 行。所以这个挂点只算「给用户看的 UI 提示」，不能当 AI 锚点。
  · **UserPromptSubmit**：官方文档明确 `hookSpecificOutput.additionalContext` 会注入模型
    上下文。模型侧的锚点必须走这里（每轮一次，不节流；Bash 太密才需要节流）。
  · 两者的仓库定位共用同一套三级回退，避免两套逻辑各错一半。

状态文件：~/.codebuddy/hooks/.next_anchor_state
  {"repos": {仓库根: 最后打印时间}, "last_repo": 路径, "probe": 最后一次调用快照}
  旧版扁平格式 {仓库根: 时间} 读取时自动迁移。

自检：`python3 next_anchor.py --probe` 打印最后一次调用的 event/tool/cwd/root/via/hit，
用来区分「平台没调用钩子」与「调用了但没匹配上」——没有它，生效与否永远无法判定。
"""
import json
import os
import re
import subprocess
import sys
import time

STATE = os.path.expanduser('~/.codebuddy/hooks/.next_anchor_state')
THROTTLE_SEC = 15 * 60
MAX_STATE_KEYS = 50          # 状态文件有界，防无限增长
CMD_HEAD = 80                # probe 里只留命令开头，避免存整条长命令

EMPTY = {'repos': {}, 'last_repo': '', 'probe': {}}


def _read_state():
    try:
        with open(STATE, encoding='utf-8') as f:
            d = json.load(f)
    except Exception:
        return dict(EMPTY)
    if not isinstance(d, dict):
        return dict(EMPTY)
    if 'repos' not in d:                                # 旧扁平格式迁移
        repos = {k: v for k, v in d.items() if isinstance(v, (int, float))}
        return {'repos': repos, 'last_repo': '', 'probe': {}}
    d.setdefault('repos', {})
    d.setdefault('last_repo', '')
    d.setdefault('probe', {})
    return d


def _write_state(d):
    try:
        repos = d.get('repos') or {}
        if len(repos) > MAX_STATE_KEYS:                 # 按时间留最近的
            keep = sorted(repos.items(), key=lambda kv: kv[1], reverse=True)[:MAX_STATE_KEYS]
            d['repos'] = dict(keep)
        tmp = STATE + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(d, f)
        os.replace(tmp, STATE)                          # 原子替换（同 save_state 的做法）
    except Exception:
        pass


def _payload():
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except Exception:
        return {}


def _repo_root(cwd):
    try:
        r = subprocess.run(['git', '-C', cwd, 'rev-parse', '--show-toplevel'],
                           capture_output=True, text=True, timeout=5)
        return r.stdout.strip() if r.returncode == 0 else ''
    except Exception:
        return ''


def _norm_abs(p):
    """只接受已存在的绝对路径（含 ~ 展开）。相对路径 / 命令替换 / 引号残留一律丢。"""
    p = (p or '').strip().strip('"').strip("'")
    if not p:
        return ''
    p = os.path.expanduser(p)
    if not os.path.isabs(p):
        return ''
    p = os.path.normpath(p)
    return p if os.path.isdir(p) else ''


def _cmd_candidates(command):
    """从命令文本里挖候选目录：cd 目标与 git -C 目标，取最后一次出现。"""
    if not command:
        return []
    out = []
    for pat in (r'(?<![\w.-])cd\s+([^\s;&|()]+)', r'\bgit\s+-C\s+([^\s;&|()]+)'):
        found = [_norm_abs(m) for m in re.findall(pat, command)]
        found = [p for p in found if p]
        if found:
            out.append(found[-1])
    return out


def _next_line(root):
    """取最近一条提交里以 Next: 开头的行（commit-msg 闸保证格式：做什么—起点—完成判据）。"""
    try:
        r = subprocess.run(['git', '-C', root, 'log', '-1', '--format=%B'],
                           capture_output=True, text=True, timeout=5)
        for line in r.stdout.splitlines():
            if line.startswith('Next: '):
                return line[6:].strip()
    except Exception:
        pass
    return ''


def _save(d, probe, hit=False):
    probe['hit'] = bool(hit)
    d['probe'] = probe
    _write_state(d)


def _resolve_root(d, cwd, command, probe):
    r = _repo_root(cwd)
    if r:
        probe['via'] = 'cwd'
        return r
    for cand in _cmd_candidates(command):
        r = _repo_root(cand)
        if r:
            probe['via'] = 'command'
            return r
    last = d.get('last_repo') or ''
    if last and os.path.isdir(last):
        r = _repo_root(last)
        if r:
            probe['via'] = 'last_repo'
            return r
    probe['via'] = 'none'
    return ''


def main():
    if '--probe' in sys.argv[1:]:
        p = _read_state().get('probe') or {}
        print(json.dumps(p, ensure_ascii=False, indent=2) if p else '（无调用记录）')
        return 0

    data = _payload()
    event = data.get('hook_event_name') or ''
    tool = data.get('tool_name') or data.get('toolName') or ''
    cwd = data.get('cwd') or data.get('workingDirectory') or os.getcwd()
    ti = data.get('tool_input') if isinstance(data.get('tool_input'), dict) else {}
    command = data.get('command') or ti.get('command') or ''

    d = _read_state()
    probe = {'ts': int(time.time()), 'event': event, 'tool': tool, 'cwd': cwd,
             'cmd': str(command)[:CMD_HEAD], 'root': '', 'via': 'none', 'hit': False}

    # ---- 模型侧锚点：UserPromptSubmit 注入 additionalContext（每轮一次，不节流）----
    if event == 'UserPromptSubmit':
        root = _resolve_root(d, cwd, command, probe)
        probe['root'] = root
        nxt = _next_line(root) if root else ''
        if not nxt:
            probe['via'] += '+no-next'
            _save(d, probe)
            return 0
        d['last_repo'] = root
        _save(d, probe, hit=True)
        msg = '⏭ 上一轮定的下一步（%s）：%s' % (os.path.basename(root), nxt[:400])
        # 经验闭环闸3：按 Next 任务类型注入同型病号（读映射表+复发计数，降级静默）
        try:
            import json as _jj, re as _re, os as _os2
            _mp = _jj.load(open(_os2.path.join(root, 'verify', '病号映射表.json'), encoding='utf-8'))
            _rec_path = _os2.path.join(root, 'experience_recurrence.json')
            _rec = _jj.load(open(_rec_path, encoding='utf-8')) if _os2.path.isfile(_rec_path) else {}
            _cnt = _rec.get('counters', {})
            _hits = []
            _nxt_low = nxt.lower()
            for _dz in _mp.get('diseases', []):
                if _dz.get('status') != 'active':
                    continue
                _tags = _dz.get('tags', [])
                if any(_tg in nxt or _tg in _nxt_low for _tg in _tags):
                    _n = _cnt.get(_dz['id'], {}).get('count', 0)
                    _hits.append((_n, _dz))
            if _hits:
                _hits.sort(key=lambda x: -x[0])
                _top = _hits[0][1]
                msg += '｜📚 本轮同型坑 %s·%s：%s' % (_top['id'], _top['name'], _top['fix'][:60])
        except Exception:
            pass  # 经验注入失败不影响主提醒
        # v0.8.64 方案v3 梯度③：交付落库提醒（520进化论·每轮必落库）——只提示不拦截，
        # 硬对账在 verify/gate_archive_ledger.py（梯度④），提醒与闸分层。
        import os as _os
        _led = _os.path.join(root, 'archive_ledger.json')
        if _os.path.isfile(_led):
            try:
                _d = json.load(open(_led, encoding='utf-8'))
                _last = (_d.get('entries') or [{}])[-1]
                _lt = (_last.get('ts') or '')[:10]
                if _lt != time.strftime('%Y-%m-%d'):
                    msg += '｜📦 提醒：archive_ledger 今日无落库回执——本轮交付完成后走 space-hub archive 正门落库'
            except Exception:
                pass
        print(json.dumps({'continue': True,
                          'hookSpecificOutput': {'hookEventName': 'UserPromptSubmit',
                                                 'additionalContext': msg}},
                         ensure_ascii=False))
        return 0

    # ---- 写文件类硬拦截：Write/Edit 目标在仓内且是凭据文件 → 挡在写下去那一刻 ----
    #   为什么挂这里：settings.json 里本脚本已有一条 matcher='Bash' 的注册，
    #   再加一条 matcher='Write|Edit' 即可复用同一份 deny 协议，不必让 guard_cmd
    #   同时当「库」和「注册钩子」（那会让 hook-probe 的依赖库豁免规则失效）。
    if tool and tool != 'Bash':
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import guard_cmd
            fp = ti.get('file_path') or ti.get('path') or ti.get('notebook_path') or ''
            _w = guard_cmd.check_write(fp)
            if _w:
                probe['via'] = 'write-guard:' + _w['id']
                _save(d, probe, hit=True)               # 命中守卫也算 hit（否则 probe 看着像没干活）
                print(json.dumps(guard_cmd.deny_payload(_w), ensure_ascii=False))
                return 2
        except Exception as _e:
            probe['guard_err'] = ('%s: %s' % (type(_e).__name__, _e))[:120]
        probe['via'] = 'skip-tool'                      # 锚点提示仍只挂 Bash（Edit/Write 太频繁）
        _save(d, probe)
        return 0

    # ---- 工具级硬拦截：危险命令在**执行前**挡住（逻辑真源 hooks/guard_cmd.py）----
    #   协议实测（2026-11-14）：deny JSON + exit 2 → 平台直接阻断该次调用，
    #   模型侧看到 `PreToolUse:Bash hook blocked this tool call: <reason>`。
    #   fail-open：守卫自身坏了放行，但把 guard_err 写进 state（--probe 可查），
    #   不许静默失效——静默失效比不设防更危险。
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import guard_cmd
        _hit = guard_cmd.check(command)
        if _hit:
            probe['via'] += '+guard:' + _hit['id']
            _save(d, probe, hit=True)                   # 同上：拦下来就是命中了
            print(json.dumps(guard_cmd.deny_payload(_hit), ensure_ascii=False))
            return 2
    except Exception as _e:
        probe['guard_err'] = ('%s: %s' % (type(_e).__name__, _e))[:120]

    if not os.path.isdir(cwd):
        probe['via'] = 'bad-cwd'
        _save(d, probe)
        return 0

    root = _resolve_root(d, cwd, command, probe)
    probe['root'] = root
    if not root:
        _save(d, probe)
        return 0

    nxt = _next_line(root)
    if not nxt:
        probe['via'] += '+no-next'
        _save(d, probe)
        return 0
    if time.time() - float(d['repos'].get(root, 0) or 0) < THROTTLE_SEC:
        probe['via'] += '+throttled'
        _save(d, probe)
        return 0

    d['repos'][root] = time.time()
    d['last_repo'] = root
    _save(d, probe, hit=True)
    print('⏭ 上一轮 Next（%s）: %s' % (os.path.basename(root), nxt))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception:                                   # 永不拦截：任何异常都放行
        sys.exit(0)
