#!/usr/bin/env python3
"""v0.8.64 · 520进化论「每轮交付必落库」闸（方案 v3 梯度④）。
判据：各技能 CHANGELOG 近 3 天内新增的版本条目，必须在 archive_ledger.json 有落库回执
（result=ok，ts ≥ 版本日期）。有 bump 无回执 = 假交付（宣称升级但成果没进资料库）。

三态（M-R60）：
  ✓ 绿  —— 近期 bump 全部有回执，或近 3 天无 bump（无可判对象）
  ✗ 红  —— 近期 bump 无回执；ledger 损坏（坏 JSON/结构失配）不折叠成绿
  · 无法判定 —— ledger 缺失（旧版本装机，warn 不阻断）

正向：有 bump 有回执 → 绿；反向：造一个无回执 bump → 红（--selftest 内置双向）。
"""
import json, os, re, sys, time, datetime

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(REPO, 'archive_ledger.json')
SKILLS = ['probe-hub', 'space-hub', 'inspect-hub', 'tvbox-pipeline', 'learn-hub',
          'artifact-store', 'machine-bootstrap']
SKILL_DIRS = {
    'probe-hub': os.path.join(REPO, '能力层/tvbox/skills/probe-hub'),
    'space-hub': os.path.join(REPO, '通用层/skills/space-hub'),
    'inspect-hub': os.path.join(REPO, '通用层/skills/inspect-hub'),
    'tvbox-pipeline': os.path.join(REPO, '能力层/tvbox/skills/tvbox-pipeline'),
}
for name in ['learn-hub', 'artifact-store', 'machine-bootstrap']:
    SKILL_DIRS[name] = os.path.join(REPO, f'通用层/skills/{name}')

WINDOW_DAYS = 3


def _recent_bumps(now=None):
    """各技能 CHANGELOG 近 WINDOW_DAYS 天内的版本条目 [(技能, 版本, 日期)]。"""
    now = now or datetime.date.today()
    out = []
    for name in SKILLS:
        cl = os.path.join(SKILL_DIRS[name], 'CHANGELOG.md')
        if not os.path.isfile(cl):
            continue
        try:
            head = open(cl, encoding='utf-8').read(4000)
        except Exception:
            continue
        for m in re.finditer(r'^## (v[\d.]+) — (\d{4}-\d{2}-\d{2})', head, re.M):
            try:
                d = datetime.date.fromisoformat(m.group(2))
            except ValueError:
                continue
            if (now - d).days <= WINDOW_DAYS:
                out.append((name, m.group(1), m.group(2)))
    return out


def _load_ledger():
    """三态读取：('ok', entries) / ('corrupt', 原因) / ('missing', None)。"""
    if not os.path.isfile(LEDGER):
        return 'missing', None
    try:
        d = json.load(open(LEDGER, encoding='utf-8'))
    except Exception as e:
        return 'corrupt', f'JSONDecodeError: {e}'
    if not isinstance(d, dict) or not isinstance(d.get('entries'), list):
        return 'corrupt', '结构失配：entries 非 list'
    return 'ok', d['entries']


def check(now=None):
    st, payload = _load_ledger()
    if st == 'missing':
        print('  · [archive-ledger] 无法判定：ledger 缺失（旧版本装机，不阻断）——'
              f'预期路径 {LEDGER}')
        return 0
    if st == 'corrupt':
        print(f'  ✗ [archive-ledger] ledger 损坏不折叠（{payload}）——数据基座塌陷（M-R58）')
        return 2
    bumps = _recent_bumps(now)
    if not bumps:
        print(f'  ✓ [archive-ledger] 近 {WINDOW_DAYS} 天无版本 bump，无可判对象（绿）')
        return 0
    ok_rows = [e for e in payload if e.get('result') == 'ok']
    missing = []
    for name, ver, day in bumps:
        hit = [e for e in ok_rows
               if (e.get('ts') or '')[:10] >= day and ver.replace('v', '') in json.dumps(e, ensure_ascii=False)]
        if not hit:
            missing.append((name, ver, day))
    if missing:
        print('  ✗ [archive-ledger] 近期版本 bump 无落库回执（假交付，方案 v3 梯度④）：')
        for name, ver, day in missing:
            print(f'       {name} {ver}（{day}）——交付未落资料库，回执缺失')
        print('     修法：把该轮交付物经 space-hub archive 正门落库，回执写入 archive_ledger.json')
        return 2
    print(f'  ✓ [archive-ledger] 近期 bump {len(bumps)} 条全部有落库回执（绿）')
    return 0


def selftest():
    """正反向：正向=当前真实状态；反向=用注入的未来 bump 造违例，闸必须红。"""
    print('── 正向（真实状态）──')
    rc1 = check()
    print('── 反向（造违例：把窗口推大到覆盖旧 bump → 无回执必红）──')
    # 造违例：临时把 WINDOW_DAYS 拉大，使历史 bump 进入窗口但它们没回执
    global WINDOW_DAYS
    old = WINDOW_DAYS
    WINDOW_DAYS = 400
    rc2 = check()
    WINDOW_DAYS = old
    if rc2 == 2:
        print('  ✓ 反向验证通过：无回执 bump 被判红（闸活着）')
        return 0 if rc1 == 0 else rc1
    print('  ✗ 反向验证失败：违例未被判红——闸失灵，不许上线')
    return 2


if __name__ == '__main__':
    sys.exit(selftest() if '--selftest' in sys.argv else check())
