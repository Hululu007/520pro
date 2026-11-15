#!/usr/bin/env python3
"""v0.8.66 · M12 经验门接电闸（批1-①：闸建了没接电的修复）。

背景（2026-11-15 实查）：chk_contentflow（断流/账实脱节/复发超限/效果指标四判据）
此前只在巡检 run（模型自愿发起）时跑——闸建了，没接电。台账断流 11 版、
01-方法论欠账长期无人发现，正是这个缺口。本薄壳把它接进 verify.sh 必经链路。

三态（M-R60）：
  ✓ 绿/黄 —— chk_contentflow 返回 green（或 yellow 提示级：断路夹/复发超限属账面提醒，
              verify 不因黄阻断，与巡检语义一致；黄必须显式可见，不静默）
  ✗ 红    —— 返回 red（账实脱节过期/无源内容/复发超限按 M12 阈值）
  · 无法判定 —— 数据源损坏（不折叠成绿）

正向：账实一致+无新账缺 ref → 绿；反向：临时造缺 event_ref 回执 → 红（--selftest 内置双向）。
# impl: B-15 S5
"""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, '通用层', 'skills', 'inspect-hub', 'scripts'))


def check():
    from chk_landing import chk_contentflow          # noqa: E402（延迟导入，失败显式报）
    from inspect_hub import worst                    # noqa: E402
    ctx = {'thresholds': {}, 'worst': worst}
    worst_st = 'green'

    # ① 先探测：HEAD 变了才真扫（未变则零写盘零扰动），保证新 commit 必被探到
    try:
        sys.path.insert(0, os.path.join(REPO, 'verify'))
        from delivery_probe import scan as probe_scan, summary as debt_summary   # noqa: E402
        if os.environ.get('WB_PROBE_NO_SCAN') != '1':        # selftest 隔离：不污染真账本
            probe_scan(quiet=True)
        ds = debt_summary()
        red_age = 3
        try:
            import json as _j
            red_age = _j.load(open(os.path.join(REPO, 'verify', 'delivery_debt.json'),
                                   encoding='utf-8')).get('thresholds', {}).get('red_age_commits', 3)
        except Exception:
            pass
        if ds['open'] == 0:
            print(f"  ✓ [落库欠账] 0 条（已还 {ds['closed']} / 豁免 {ds['waived']}）")
        else:
            lvl = 'red' if ds['max_age'] > red_age else 'yellow'
            mark = '✗' if lvl == 'red' else '⚠'
            print(f"  {mark} [落库欠账] {ds['open']} 条未还（最老 {ds['max_age']} commit，阈值 {red_age}）")
            for it in ds['items'][:6]:
                print(f"       {it['id']}  龄 {it['age']}  {it['folder'].split('/')[-1]}"
                      f"  ← {it['commit']}  应为「{it['expect'][:28]}」")
            if len(ds['items']) > 6:
                print(f"       …另 {len(ds['items']) - 6} 条（--list 看全）")
            if lvl == 'red':
                worst_st = 'red'
    except Exception as ex:
        print(f"  · [落库欠账] 无法判定：探测器不可用（{str(ex)[:60]}）")
        worst_st = 'unknown'

    # ② 内容流四判据
    r = chk_contentflow(REPO, {'repo': REPO}, ctx)
    for it in r.get('items', []):
        mark = {'green': '✓', 'yellow': '⚠', 'red': '✗'}.get(it.get('s'), '·')
        print(f"  {mark} [{it.get('t')}] {it.get('e', '')[:90]}")

    sts = [worst_st, r.get('status')]
    if 'red' in sts:
        return 'red'
    if 'unknown' in sts:
        return 'unknown'
    return 'yellow' if 'yellow' in sts else 'green'


def selftest():
    """正反向：红/黄/绿三态在真数据上现形；反向靠临时构造缺 ref 回执。"""
    import json
    import shutil
    import tempfile
    led = os.path.join(REPO, 'archive_ledger.json')
    bak = tempfile.mktemp()
    shutil.copy(led, bak)
    fails = []
    try:
        # 正向：真数据跑一遍，应可判定（green/yellow 都算通过，red 算违例——当前真数据应无 red）
        st = check()
        if st in ('red',):
            fails.append(f'正向：真数据出现 red（{st}）——先清真账再谈闸')
        # 反向：造一条 result=ok 且缺 event_ref、非 legacy round 的新账 → 应 red
        d = json.load(open(led, encoding='utf-8'))
        rows = d if isinstance(d, list) else d.get('entries', [])
        rows.append({'ts': '2026-11-15T99:99:99', 'round': 'selftest-bad', 'artifact': 'x',
                     'target': '🧬 520进化论/05-复盘与判例', 'result': 'ok', 'event_ref': '', 'note': 'selftest'})
        json.dump(d, open(led, 'w'), ensure_ascii=False, indent=1)
        st2 = check()
        if st2 != 'red':
            fails.append(f'反向：造缺 ref 新账后仍 {st2}——闸抓不住无源内容')
        print(f"  selftest: 正向={st} 反向={st2}")
    finally:
        shutil.copy(bak, led)
        os.remove(bak)
    if fails:
        for f in fails:
            print(f'  ✗ {f}')
        return 1
    print('  ✓ 正反向全通过（真数据绿/黄、造违例即红）')
    return 0


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        sys.exit(selftest())
    st = check()
    print(f"[experience-gate] M12 经验门状态: {st}")
    sys.exit(1 if st == 'red' else 0)
