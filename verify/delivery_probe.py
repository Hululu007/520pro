#!/usr/bin/env python3
"""v0.8.67 · 内容流触发源探测器（批3）：该产未产 → 欠账负账本。

背景（四轮漏检排查）：archive_ledger 只记「落了的」（正向账），漏落无影无踪——
01-方法论只有 1 件、版本台账断流 11 版，都是「触发源发生了、产出没发生、没人报红」。
本探测器把触发源机器可测化（git commit message / diff 路径 / VERSION），
与正向账对账，命中「该产未产」写欠账进 verify/delivery_debt.json；
ledger 出现对应回执即机器自动核销。

三态（B-02）：
  ✓ 绿  —— 全部触发源都有回执，或窗口内无触发源（无可判对象）
  ✗ 红  —— 存在该产未产欠账（或账本损坏，不折叠成绿）
  · 无法判定 —— content_sources / ledger 不可读，或 online 类流（离线不可判）

正向：造一条 Lesson 非空的 commit 无回执 → 出欠账；反向：Lesson=「无」/ 已有回执 → 零欠账。
（--selftest 用纯函数 probe_commit 造 4 个用例，不碰真实数据。）
"""
import json, os, re, subprocess, sys, datetime

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CS = os.path.join(REPO, 'verify', 'content_sources.json')
DEBT = os.path.join(REPO, 'verify', 'delivery_debt.json')
LEDGER = os.path.join(REPO, 'archive_ledger.json')


# ────────────────────────── 纯函数层（可单测，不碰磁盘） ──────────────────────────
def lesson_of(msg):
    """取 commit message 的 Lesson: 段（首个匹配行）。返回 (原文, 是否实质)。"""
    m = re.search(r'(?m)^Lesson:\s*(.*)$', msg or '')
    if not m:
        return '', False
    line = m.group(1).strip()
    if not line:
        return '', False
    if line.startswith('无'):
        return line, False          # 「无」或「无（…）」按 commit-msg 语义=没踩坑
    return line, True


def lesson_advisory(msg):
    """逃逸提示：Lesson 写「无」但括号里塞了实质内容（>15 字）→ 提示确认。
    机器只能提示不能断言（语义判断），故不计欠账。"""
    line, real = lesson_of(msg)
    if real or not line:
        return None
    m = re.match(r'无\s*[（(](.*)[）)]\s*$', line)
    if m and len(m.group(1).strip()) > 15:
        return f'Lesson 写「无」但括注 {len(m.group(1))} 字：「{m.group(1)[:50]}…」——确认是否应提炼方法论'
    return None


def _glob_hit(path, pattern):
    """极简 glob：支持 ** 与 *，用于 diff 路径匹配（不引第三方依赖）。"""
    rx = re.escape(pattern).replace(r'\*\*/', '(?:.*/)?').replace(r'\*', '[^/]*')
    return re.search('^' + rx + '$', path) is not None


def signal_hit(sig, commit):
    """单条 flow 的信号是否命中。返回 (hit, evidence)；不支持的 type 返回 (False, '')。"""
    t = sig.get('type')
    msg = commit.get('msg', '')
    paths = commit.get('paths') or []

    if t == 'lesson':
        line, real = lesson_of(msg)
        if sig.get('match') == 'nonempty':
            return (True, f'Lesson: {line[:80]}') if real else (False, '')
        if sig.get('match') == 'keyword':
            kws = sig.get('keywords') or []
            if real and any(k in line for k in kws):
                return True, f'Lesson 命中 {[k for k in kws if k in line]}: {line[:60]}'
            return False, ''
        return False, ''

    if t == 'message':
        for group in sig.get('all_of') or []:
            if not any(k in msg for k in group):
                return False, ''
        return True, 'message 命中 ' + str([g[0] for g in (sig.get('all_of') or [])])

    if t == 'diff_paths':
        pat = sig.get('glob', '')
        flt = sig.get('path_filter') or []
        hits = [p for p in paths
                if (_glob_hit(p, pat) or p.endswith(pat))
                and (not flt or any(x in p for x in flt))]
        return (True, f'改动文件: {hits[0]}' if hits else '') if hits else (False, '')

    if t == 'version_bump':
        v = commit.get('version')
        if v and v[0] != v[1]:
            return True, f'VERSION {v[0]} → {v[1]}'
        return False, ''

    return False, ''   # online / derived：离线不可判/派生，交给上层


def _closed(folder, flow, commit, ledger_rows):
    """核销判定：ledger 有 result=ok、target 前缀命中、ts>=commit 日期 的行，
    **且回执能指回这条 commit**——否则同夹里别人的回执会把账误销掉（实测踩到：
    d8b5b6a 的方法论欠账被 01 夹「自愈演示」旧回执误判为已还）。
      · F09 / close_match=version：回执须含目标版本号
      · close_match=msg_version：回执须含 message 中的任一 x.y.z 版本号（技能 bump）
      · 其余：回执须含 commit 短 sha（无源内容判据的口径：event_ref 必须指向 commit）
    """
    day = (commit.get('date') or '')[:10]
    fid = flow.get('id', '')
    cm = flow.get('close_match', '')
    sha = (commit.get('short') or '')[:7]
    want_ver = (commit.get('version') or (None, None))[1] if (fid == 'F09' or cm == 'version') else None
    msg_vers = re.findall(r'\d+\.\d+\.\d+', commit.get('msg', '')) if cm == 'msg_version' else []
    for e in ledger_rows:
        if e.get('result') != 'ok':
            continue
        tgt = (e.get('target') or '')
        if not tgt.startswith(folder):
            continue
        if day and (e.get('ts') or '')[:10] < day:
            continue
        blob = json.dumps(e, ensure_ascii=False)
        if want_ver:
            if want_ver not in blob:
                continue
        elif msg_vers:
            if not any(v in blob for v in msg_vers):
                continue
        elif sha:
            if sha not in blob:
                continue
        return e
    return None


def probe_commit(commit, flows, ledger_rows):
    """单 commit 探测。返回 (debts, advices)；debts 元素为待入账的欠账 dict。"""
    debts, advices = [], []
    for f in flows:
        if f.get('probe') not in ('debt', 'advisory'):
            continue
        hit, ev = signal_hit(f.get('signal') or {}, commit)
        if not hit:
            continue
        if f.get('probe') == 'advisory':
            advices.append({'flow': f['id'], 'commit': commit.get('short', ''),
                            'text': f'{f["folder"].split("/")[-1]}: {ev}'})
            continue
        closed = _closed(f['folder'], f, commit, ledger_rows)
        if closed:
            continue
        debts.append({
            'id': f'D-{commit.get("short", "")[:7]}-{f["id"]}',
            'flow': f['id'], 'folder': f['folder'],
            'commit': commit.get('short', ''), 'commit_date': commit.get('date', ''),
            'target_version': (commit.get('version') or (None, None))[1] if f['id'] == 'F09' else '',
            'title': (commit.get('msg', '').splitlines() or [''])[0][:80],
            'expect': f.get('action', ''), 'evidence': ev[:160],
            'status': 'open', 'age_commits': 0,
            'first_seen': datetime.date.today().isoformat(),
            'closed_by': '', 'waived_until': '', 'note': '',
        })
    adv = lesson_advisory(commit.get('msg', ''))
    if adv:
        advices.append({'flow': 'lesson-escape', 'commit': commit.get('short', ''), 'text': adv})
    return debts, advices


# ────────────────────────── 磁盘层 ──────────────────────────
def _git(*args):
    r = subprocess.run(['git', '-C', REPO] + list(args), capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ''


def load_json(path, default=None):
    try:
        return json.load(open(path, encoding='utf-8'))
    except Exception:
        return default


def save_json_atomic(path, data):
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def read_commits(limit=None, after_sha=None):
    """读 commit 列表（含 diff 路径与 VERSION 前后值）。after_sha 之后的所有 commit。"""
    fmt = '--format=%h%x1f%H%x1f%ad%x1f%B%x1e'
    rng = f'{after_sha}..HEAD' if after_sha else f'-{limit or 40}'
    raw = _git('log', '--date=short', fmt, rng)
    out = []
    for chunk in raw.split('\x1e'):
        chunk = chunk.strip('\n')
        if not chunk:
            continue
        parts = chunk.split('\x1f')
        if len(parts) < 4:
            continue
        short, full, date, msg = parts[0], parts[1], parts[2], parts[3]
        paths = [p for p in _git('show', '--name-only', '--format=', short).splitlines() if p.strip()]
        v_new = _git('show', f'{short}:VERSION').strip()
        v_old = _git('show', f'{short}^:VERSION').strip() or v_new
        out.append({'short': short, 'full': full, 'date': date, 'msg': msg,
                    'paths': paths, 'version': (v_old, v_new) if v_new else None})
    out.reverse()   # 时间正序
    return out


def scan(limit=None, quiet=False):
    cs = load_json(CS)
    led = load_json(LEDGER)
    debt = load_json(DEBT)
    if not cs or not led or not debt:
        print('  · [delivery-probe] 无法判定：content_sources / archive_ledger / delivery_debt 任一不可读')
        return 0
    flows = cs.get('flows', [])
    ledger_rows = led.get('entries', []) if isinstance(led, dict) else led
    state = debt.setdefault('scan_state', {})
    after = state.get('last_sha') or None
    commits = read_commits(limit=limit or cs.get('probe', {}).get('window_commits', 40), after_sha=after)

    existing = {d['id']: d for d in debt.get('debts', [])}
    pre_open = {d['id'] for d in debt.get('debts', []) if d.get('status') == 'open'}
    added, advices = [], []
    for c in commits:
        ds, adv = probe_commit(c, flows, ledger_rows)
        for d in ds:
            if existing.get(d['id']):    # 幂等：同 flow+commit 不重复入账；已还的不重开
                continue
            existing[d['id']] = d
            added.append(d)
        advices.extend(adv)

    # 核销重判：**每次 scan 都跑**（回执可能在不扫新 commit 时补上）——机器销账，无需人工改状态
    just_closed = []
    for d in existing.values():
        if d.get('status') != 'open':
            continue
        fl = next((x for x in flows if x.get('id') == d['flow']), None) \
            or {'id': d['flow'], 'folder': d['folder']}
        fake = {'short': d['commit'], 'date': d.get('commit_date', ''),
                'msg': d.get('evidence', ''),
                'version': (None, d.get('target_version') or None)}
        hit = _closed(d['folder'], fl, fake, ledger_rows)
        if hit:
            d['status'] = 'closed'
            d['closed_by'] = f'{hit.get("round", "?")} @ {hit.get("ts", "")[:10]}'
            d['note'] = (d.get('note', '') + '｜机器核销：ledger 回执已现').strip('｜')
            just_closed.append(d['id'])

    # 欠债不能躺着：扫描前就在的 open 账，按本轮新扫 commit 数增龄（新账从 0 起算）
    for did in pre_open:
        d = existing.get(did)
        if d and d.get('status') == 'open':
            d['age_commits'] = d.get('age_commits', 0) + len(commits)

    # 过期豁免自动转 open（防洗绿：豁免带期限，到期必须复检）
    today = datetime.date.today().isoformat()
    expired = []
    for d in existing.values():
        wu = d.get('waived_until') or ''
        if d.get('status') == 'waived' and wu and wu < today:
            d['status'] = 'open'
            d['note'] = (d.get('note', '') + f'｜豁免 {wu} 到期自动转 open').strip('｜')
            expired.append(d['id'])

    debt['debts'] = sorted(existing.values(), key=lambda x: (x.get('commit_date', ''), x['id']))
    if commits or just_closed or expired:   # 有变化才写盘（HEAD 未变时零扰动，不弄脏工作区）
        if commits:
            debt['scan_state']['last_sha'] = commits[-1]['full']
        debt['scan_state']['last_scan_ts'] = datetime.datetime.now().isoformat(timespec='seconds')
        debt['updated'] = today
        save_json_atomic(DEBT, debt)

    open_ds = [d for d in debt['debts'] if d.get('status') == 'open']
    if not quiet:
        if commits:
            print(f'  扫描 {len(commits)} 个新 commit（{commits[0]["short"]}..{commits[-1]["short"]}）')
        elif not just_closed:
            print(f'  ✓ [delivery-probe] 无新 commit（上次扫到 {after[:7] if after else "—"}），无可判对象（绿）')
        print(f'  新增欠账 {len(added)} 条；当前 open {len(open_ds)} 条')
        for d in added:
            print(f'    + {d["id"]}  {d["folder"].split("/")[-1]}  ← {d["commit"]} {d["title"][:40]}')
        for a in advices:
            print(f'    ! 提示 {a["commit"]} {a["text"][:90]}')
        if just_closed:
            print(f'  ✓ 机器核销 {len(just_closed)} 条（ledger 回执已现）：' + '，'.join(just_closed))
        if open_ds:
            print('  ✗ [delivery-probe] 存在该产未产欠账（红）：')
            for d in open_ds:
                print(f'      {d["id"]}  龄 {d["age_commits"]} commit  {d["folder"]}  应为「{d["expect"][:30]}」')
            print('     修法：把该轮交付物经 space-hub archive 正门落库并写回执 → 重跑本探测器自动核销')
            return 2
        print('  ✓ [delivery-probe] 全部触发源均有落库回执（绿）')
    return 2 if open_ds else 0


def summary():
    """给 next_anchor / gate_experience 用的摘要（--json）。"""
    debt = load_json(DEBT) or {}
    rows = debt.get('debts', [])
    op = [d for d in rows if d.get('status') == 'open']
    return {'open': len(op), 'closed': len([d for d in rows if d.get('status') == 'closed']),
            'waived': len([d for d in rows if d.get('status') == 'waived']),
            'max_age': max([d.get('age_commits', 0) for d in op], default=0),
            'items': [{'id': d['id'], 'folder': d['folder'], 'commit': d['commit'],
                       'expect': d['expect'], 'age': d.get('age_commits', 0),
                       'title': d.get('title', '')[:60]} for d in op]}


def selftest():
    """正反向四用例（纯函数，不碰真实数据）。"""
    flows = [
        {'id': 'F02', 'kind': 'folder', 'folder': '🧬 520进化论/01-方法论', 'probe': 'debt',
         'action': '方法论条目', 'signal': {'type': 'lesson', 'match': 'nonempty'}},
        {'id': 'F09', 'kind': 'ledger', 'folder': '🧬 520进化论/版本演化台账', 'probe': 'debt',
         'action': '版本台账记录', 'signal': {'type': 'version_bump'}},
        {'id': 'F06', 'kind': 'folder', 'folder': '🧬 520进化论/05-复盘与判例', 'probe': 'debt',
         'action': '判例', 'signal': {'type': 'diff_paths', 'glob': 'docs/通病台账.md'}},
    ]
    ok = True

    def case(name, commit, ledger, want_debts, want_adv=0):
        nonlocal ok
        ds, adv = probe_commit(commit, flows, ledger)
        got = len(ds)
        good = got == want_debts and len(adv) == want_adv
        ok = ok and good
        print(f'  {"✓" if good else "✗"} {name}：欠账 {got}（期望 {want_debts}）/ 提示 {len(adv)}（期望 {want_adv}）')
        for d in ds:
            print(f'      → {d["id"]} {d["folder"].split("/")[-1]}')

    print('── 正向①：Lesson 非空 + 无回执 → 必出欠账')
    case('踩坑文案无回执', {'short': 'aaa1111', 'date': '2026-11-15',
                          'msg': 'fix: x\n\nLesson: 病15(第8例) 判据识别范围过宽',
                          'paths': [], 'version': ('0.8.66', '0.8.66')}, [], 1)
    print('── 正向②：VERSION 变更 + 台账无该版本 → 必出欠账')
    case('版本bump无台账', {'short': 'bbb2222', 'date': '2026-11-15', 'msg': 'v0.8.67 升级',
                          'paths': ['VERSION'], 'version': ('0.8.66', '0.8.67')}, [], 1)
    print('── 反向①：Lesson 写「无」 → 零欠账')
    case('无踩坑', {'short': 'ccc3333', 'date': '2026-11-15', 'msg': 'chore: y\n\nLesson: 无',
                  'paths': [], 'version': ('0.8.66', '0.8.66')}, [], 0)
    print('── 反向②：有对应落库回执 → 核销为零欠账')
    case('有回执', {'short': 'ddd4444', 'date': '2026-11-15',
                  'msg': 'fix: z\n\nLesson: 病15(第9例) 某坑', 'paths': [],
                  'version': ('0.8.66', '0.8.66')},
         [{'result': 'ok', 'target': '🧬 520进化论/01-方法论', 'ts': '2026-11-15T10:00:00',
           'event_ref': 'commit ddd4444'}], 0)
    print('── 反向③：回执早于 commit（旧账不能核销新账）→ 仍欠账')
    case('回执过期', {'short': 'eee5555', 'date': '2026-11-15',
                    'msg': 'fix: w\n\nLesson: 病15(第10例) 某坑', 'paths': [],
                    'version': ('0.8.66', '0.8.66')},
         [{'result': 'ok', 'target': '🧬 520进化论/01-方法论', 'ts': '2026-11-10T10:00:00',
           'event_ref': 'commit eee5555'}], 1)
    print('── 反向④：同夹同日但有回执不指向本 commit（他人回执误销）→ 仍欠账')
    case('他人回执', {'short': 'hhh8888', 'date': '2026-11-15',
                   'msg': 'fix: q\n\nLesson: 病15(第11例) 某坑', 'paths': [],
                   'version': ('0.8.66', '0.8.66')},
         [{'result': 'ok', 'target': '🧬 520进化论/01-方法论', 'ts': '2026-11-15T09:00:00',
           'event_ref': '自愈演示（无关 commit）'}], 1)
    print('── 提示①：Lesson 写「无」但括注实质 → 1 条提示、0 欠账')
    case('逃逸提示', {'short': 'fff6666', 'date': '2026-11-15',
                    'msg': 'chore: v\n\nLesson: 无（假正门属体检发现非踩坑，已订正登记并补四处清单）',
                    'paths': [], 'version': ('0.8.66', '0.8.66')}, [], 0, 1)
    print('── 正向③：台账回执不含目标版本号 → 不算核销（版本流专项）')
    case('台账版本不符', {'short': 'ggg7777', 'date': '2026-11-15', 'msg': 'v0.8.67 升级',
                       'paths': ['VERSION'], 'version': ('0.8.66', '0.8.67')},
         [{'result': 'ok', 'target': '🧬 520进化论/版本演化台账', 'ts': '2026-11-15T10:00:00',
           'note': '记了 0.8.66'}], 1)

    print('✓ selftest 全通过（探测器活着，正反向皆如预期）' if ok
          else '✗ selftest 有失败——闸失灵，不许上线')
    return 0 if ok else 2


if __name__ == '__main__':
    a = sys.argv[1:]
    if '--selftest' in a:
        sys.exit(selftest())
    if '--json' in a:
        print(json.dumps(summary(), ensure_ascii=False))
        sys.exit(0)
    if '--list' in a:
        s = summary()
        print(f"open {s['open']} / closed {s['closed']} / waived {s['waived']}  max_age {s['max_age']}")
        for d in s['items']:
            print(f"  {d['id']}  龄{d['age']}  {d['folder']}  ← {d['commit']}  {d['title']}")
        sys.exit(0)
    lim = None
    if '--commits' in a:
        lim = int(a[a.index('--commits') + 1])
    sys.exit(scan(limit=lim))
