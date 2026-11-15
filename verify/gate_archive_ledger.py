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
          'artifact-store', 'machine-bootstrap', 'foundry']
SKILL_DIRS = {
    'probe-hub': os.path.join(REPO, '能力层/tvbox/skills/probe-hub'),
    'space-hub': os.path.join(REPO, '通用层/skills/space-hub'),
    'inspect-hub': os.path.join(REPO, '通用层/skills/inspect-hub'),
    'tvbox-pipeline': os.path.join(REPO, '能力层/tvbox/skills/tvbox-pipeline'),
}
for name in ['learn-hub', 'artifact-store', 'machine-bootstrap', 'foundry']:
    SKILL_DIRS[name] = os.path.join(REPO, f'通用层/skills/{name}')

WINDOW_DAYS = 3


def _ver_token_in(blob, ver):
    """版本完整 token 命中：防 1.1.0 子串误命中 1.1.01（病15 识别范围=对象范围）。"""
    v = ver.replace('v', '')
    return re.search(r'(?<!\d)' + re.escape(v) + r'(?!\d)', blob) is not None


def _owned_hit(e, name, ver):
    """归属判据（病15 第15例，2026-11-15 W4）：一条 ok 回执能否核销「本技能的本次 bump」。
    原实现只判 `ver in json.dumps(e)`：foundry v1.1.0 会命中 artifact-store v1.1.0 的
    他人回执，把没落库的 bump 假绿销掉（同病15 第13例的 message 全量版本号）。
    正解=排他：版本 token 命中 **且 未署名其他技能**。两头都不伤——
      · 强制「本技能署名」会误伤 space-hub v2.7.9 那种只在 note 写版本、无署名的补登回执；
      · 只认版本会假绿。排他法以「有没有署名别人」划线，对象范围=「回执归属本 bump」。
    """
    if e.get('result') != 'ok':
        return False
    blob = json.dumps(e, ensure_ascii=False)
    if not _ver_token_in(blob, ver):
        return False
    others = [s for s in SKILLS if s != name]
    return not any(o in blob for o in others)


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


def _load_debt():
    """欠账账本（v0.8.67）：三态 None=文件缺失（退回窗口快检）/ [] = 无欠账 / [rows] = 有欠账。"""
    fp = os.path.join(REPO, 'verify', 'delivery_debt.json')
    if not os.path.isfile(fp):
        return None
    try:
        d = json.load(open(fp, encoding='utf-8'))
        return [x for x in (d.get('debts') or []) if x.get('status') == 'open']
    except Exception:
        return None


def check(now=None):
    st, payload = _load_ledger()
    if st == 'missing':
        print('  · [archive-ledger] 无法判定：ledger 缺失（旧版本装机，不阻断）——'
              f'预期路径 {LEDGER}')
        return 0
    if st == 'corrupt':
        print(f'  ✗ [archive-ledger] ledger 损坏不折叠（{payload}）——数据基座塌陷（M-R58）')
        return 2

    # ① 主判据：欠账账本（v0.8.67 起并入）。欠账不随 3 天窗口消失——
    #    旧判据只看"近 3 天 bump"，超窗即洗白，历史断流（版本台账 36 版）因此长期不可见。
    op = _load_debt()
    if op is not None and os.environ.get('WB_PROBE_NO_SCAN') != '1':
        try:                      # 先探一遍，保证账本是"现在"的（HEAD 未变时零写盘）
            sys.path.insert(0, os.path.join(REPO, 'verify'))
            from delivery_probe import scan as _probe_scan
            _probe_scan(quiet=True)
            op = _load_debt()
        except Exception as ex:
            print(f'  · [archive-ledger] 探测器不可用（{str(ex)[:50]}），按账本现状判')
    if op:
        print(f'  ✗ [archive-ledger] 落库欠账 {len(op)} 条未还（账本制，不随窗口消失）：')
        for d in op[:8]:
            print(f'       {d.get("id")}  {d.get("folder", "").split("/")[-1]}'
                  f'  ← {d.get("commit")}  龄 {d.get("age_commits", 0)}  应为「{(d.get("expect") or "")[:26]}」')
        if len(op) > 8:
            print(f'       …另 {len(op) - 8} 条（python3 verify/delivery_probe.py --list）')
        print('     修法：把该轮交付经 space-hub archive / evolve-log 正门落库 → 探测器自动核销')
        return 2

    # ② 兜底快检：账本缺失时的窗口判据（保留，防账本未生成时彻底失守）
    bumps = _recent_bumps(now)
    if not bumps:
        print(f'  ✓ [archive-ledger] 近 {WINDOW_DAYS} 天无版本 bump，无可判对象（绿）')
        return 0
    ok_rows = [e for e in payload if e.get('result') == 'ok']
    missing = []
    for name, ver, day in bumps:
        hit = [e for e in ok_rows
               if (e.get('ts') or '')[:10] >= day and _owned_hit(e, name, ver)]
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
    """正反向：正向=真实状态；反向=往欠账账本塞一条假账，闸必须红。

    （v0.8.67 起反向改法：原「把窗口拉大到覆盖历史 bump」造不出违例了——历史债
    已全量清偿，旧 bump 现在都有回执。反向必须对准**新主判据**（账本制）。）
    """
    import shutil, tempfile
    # 归属判据正反（病15 第15例）：纯函数喂样本，不碰真文件。
    print('── 归属判据 _owned_hit 正反（版本 token + 排他，防假绿/防误伤）──')
    import copy
    base = {'result': 'ok', 'ts': '2026-11-15T06:00:00',
            'artifact': 'foundry_v1.1.0_产出.md', 'round': 'v1.1.0',
            'event_ref': 'foundry v1.1.0 W4 落库', 'note': 'foundry 自己落库'}
    cases = [
        # (说明, 回执, 技能, 版本, 期望)
        ('本技能署名+版本命中→核销', base, 'foundry', 'v1.1.0', True),
        ('他人署名 artifact-store v1.1.0 不得核销 foundry（假绿反向）',
         {'result': 'ok', 'ts': '2026-11-15T05:46:08', 'artifact': '瘦身司v1.1.0经验热冷分层.md',
          'event_ref': 'artifact-store v1.1.0 bump（本提交）'}, 'foundry', 'v1.1.0', False),
        ('无署名补登回执只写版本→仍核销（防误伤 space-hub v2.7.9 型）',
         {'result': 'ok', 'ts': '2026-11-15T10:05:00', 'artifact': '版本演化台账记录 0.8.66',
          'event_ref': 'VERSION=0.8.66 · batch3', 'note': '补回执（v2.7.9）'}, 'space-hub', 'v2.7.9', True),
        ('版本 token 边界：1.1.0 不命中 1.1.01',
         {'result': 'ok', 'ts': '2026-11-15T06:00:00', 'artifact': 'foundry_1.1.01.md',
          'event_ref': 'foundry v1.1.01'}, 'foundry', 'v1.1.0', False),
        ('result 非 ok 不核销', {**base, 'result': 'pending'}, 'foundry', 'v1.1.0', False),
    ]
    oh_pass = True
    for label, e, nm, ver, want in cases:
        got = _owned_hit(e, nm, ver)
        if got != want:
            oh_pass = False
            print(f'  ✗ {label}: want={want} got={got}')
    if not oh_pass:
        print('  ✗ 归属判据正反失败，不许上线')
        return 2
    print(f'  ✓ 归属判据 {len(cases)} 例正反全过（含假绿反向 + 防误伤 + token 边界）')
    print('── 正向（真实状态）──')
    rc1 = check()
    print('── 反向（造违例：账本里塞一条 open 欠账 → 必红）──')
    fp = os.path.join(REPO, 'verify', 'delivery_debt.json')
    bak = tempfile.mktemp()
    have = os.path.isfile(fp)
    if have:
        shutil.copy(fp, bak)
    rc2 = None
    try:
        d = json.load(open(fp, encoding='utf-8')) if have else {'debts': []}
        d.setdefault('debts', []).append({
            'id': 'D-selftest-F02', 'flow': 'F02', 'folder': '🧬 520进化论/01-方法论',
            'commit': 'selftest', 'commit_date': '2026-11-15', 'target_version': '',
            'title': 'selftest 假账', 'expect': '方法论条目', 'evidence': 'selftest',
            'status': 'open', 'age_commits': 0, 'first_seen': '2026-11-15',
            'closed_by': '', 'waived_until': '', 'note': 'selftest'})
        json.dump(d, open(fp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        rc2 = check()
    finally:
        if have:
            shutil.copy(bak, fp)
            os.remove(bak)
        elif os.path.isfile(fp):
            os.remove(fp)
    if rc2 == 2:
        print('  ✓ 反向验证通过：账本欠账被判红（闸活着）')
        return 0 if rc1 == 0 else rc1
    print(f'  ✗ 反向验证失败：造欠账后返回 {rc2}——闸失灵，不许上线')
    return 2


if __name__ == '__main__':
    sys.exit(selftest() if '--selftest' in sys.argv else check())
