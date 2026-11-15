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


def _gate_selftest():
    """v0.8.73 闸化登记分支：五种后接形态 + 反例 + 端到端 green/yellow。

    隔离：独立临时 repo（造最小账本/计数/落点脚本），全程只读真仓、不写任何受管文件；
    gate_registry 经 ctx 注入判4（不碰 verify/病号映射表.json）。
    本轮病15 同型坑防御：识别 selftest 靠 ast 结构化节点，注释/docstring 造不出
    FunctionDef/Call → 天然排除；五种真实后接写法全覆盖，防止「只认精确锚点」漏判。
    """
    import json
    import shutil
    import tempfile
    from chk_landing import chk_contentflow, _selftest_landed   # noqa: E402（sys.path 模块顶已插）
    from inspect_hub import worst                                # noqa: E402
    fails = []
    ANCH = 'S233①'
    # ── A. 五种后接形态（应全 True）──
    forms = {
        '①def+SystemExit': "def selftest():\n    chk('S233①x', 1)\nif __name__=='__main__':\n    if '--selftest' in sys.argv:\n        raise SystemExit(selftest())\n",
        '②async+sys.exit': "import sys\nasync def selftest():\n    chk('S233①x', 1)\nif '--selftest' in sys.argv:\n    sys.exit(selftest())\n",
        '③方法/test_前缀': "class T:\n    def test_selftest(self):\n        chk('S233①x', 1)\nif '--selftest' in sys.argv:\n    T().test_selftest()\n",
        '④argparse开关': "import argparse\ndef selftest():\n    chk('S233①x', 1)\np=argparse.ArgumentParser(); p.add_argument('--selftest', action='store_true')\nselftest()\n",
        '⑤裸调用无argv': "def selftest():\n    chk('S233①x', 1)\nselftest()\n",
    }
    for k, v in forms.items():
        ok, why = _selftest_landed(v, ANCH)
        if not ok:
            fails.append(f'闸化·形态{k} 应 True：{why}')
    # ── B. 反例（应全 False；注释/docstring/空壳/未接电/锚点只在注释）──
    negs = {
        '纯注释def': "# def selftest():\n#     if '--selftest' in sys.argv: selftest()\n",
        'docstring字样': '"""def selftest(): --selftest S233①"""\nx=1\n',
        '无函数只有开关': "if '--selftest' in sys.argv:\n    print('S233①')\n",
        '空壳selftest': "def selftest():\n    pass\nif '--selftest' in sys.argv: selftest()\n",
        '有def无接电': "def selftest():\n    chk('S233①x', 1)\n",
        '锚点只在注释': "def selftest():\n    # S233①\n    chk('x', 1)\nif '--selftest' in sys.argv: selftest()\n",
    }
    for k, v in negs.items():
        ok, why = _selftest_landed(v, ANCH)
        if ok:
            fails.append(f'闸化·反例{k} 应 False（注释/docstring 不算落点）：{why}')
    # ── C. 端到端：有 gate→green / gate 指向不存在文件→仍 yellow / 无 gate→yellow ──
    tmp = tempfile.mkdtemp(prefix='exp_gate_')
    try:
        os.makedirs(os.path.join(tmp, 'verify'))
        json.dump({'entries': []}, open(os.path.join(tmp, 'archive_ledger.json'), 'w'))
        json.dump({'counters': {'病15': {'count': 7, 'status': 'active'}}, 'direction_cases': []},
                  open(os.path.join(tmp, 'experience_recurrence.json'), 'w'))
        json.dump({'flows': []}, open(os.path.join(tmp, 'verify', 'content_sources.json'), 'w'))
        open(os.path.join(tmp, '_gate_probe.py'), 'w', encoding='utf-8').write(forms['①def+SystemExit'])
        base = {'thresholds': {}, 'worst': worst}

        def item4(reg):
            r = chk_contentflow(tmp, {'repo': tmp}, dict(base, gate_registry=reg))
            return next((i for i in r['items'] if '经验复发' in i.get('t', '')), None)

        it = item4({'病15': {'script': '_gate_probe.py', 'anchor': ANCH}})
        if not it or it['s'] != 'green':
            fails.append(f'闸化·端到端 有 gate 应 green：{it}')
        it2 = item4({'病15': {'script': '__不存在__.py', 'anchor': ANCH}})
        if not it2 or it2['s'] != 'yellow':
            fails.append(f'闸化·端到端 gate 指向不存在文件应仍 yellow：{it2}')
        it3 = item4({})
        if not it3 or it3['s'] != 'yellow':
            fails.append(f'闸化·端到端 无 gate 登记应 yellow：{it3}')
        print(f"  selftest[闸化]: 形态{len(forms)}/反例{len(negs)} "
              f"端到端 green={it['s'] if it else 'None'} "
              f"不存在文件={it2['s'] if it2 else 'None'} 无登记={it3['s'] if it3 else 'None'}")
        # ── D. 多病号混合（v0.8.74 B-15 同类排查）：部分有 gate/部分无 → 只对无 gate 的 hot 报 yellow ──
        #   含 retired 非 hot 病号，断言不被误伤；正反向：补一个 gate / 撤一个 gate，计数恰变。
        mixed = {
            '病15': {'count': 7, 'status': 'active'},     # 有 gate（应 gated）
            '病10': {'count': 5, 'status': 'active'},     # 无 gate（应 ungated）
            '病1':  {'count': 4, 'status': 'active'},     # 无 gate（应 ungated）
            '病11': {'count': 3, 'status': 'retired'},    # 非 hot（不应出现在明细）
        }
        json.dump({'counters': mixed, 'direction_cases': []},
                  open(os.path.join(tmp, 'experience_recurrence.json'), 'w'))
        g_ok = {'script': '_gate_probe.py', 'anchor': ANCH}   # 合成环境复用同一落点，仅验判4 分流逻辑
        itA = item4({'病15': g_ok})
        if not itA or itA['s'] != 'yellow' or '2 病号' not in itA['t'] \
                or '病10×' not in itA['e'] or '病1×' not in itA['e'] \
                or '病15' in itA['e'] or '病11' in itA['e']:
            fails.append(f'闸化·混合A 应仅对病10/病1 报 yellow：{itA}')
        itB = item4({'病15': g_ok, '病10': g_ok})            # 补一个 gate → 只剩病1
        if not itB or itB['s'] != 'yellow' or '1 病号' not in itB['t'] \
                or '病10×' in itB['e'] or '病1×' not in itB['e']:
            fails.append(f'闸化·混合B 补 gate 后应只剩病1：{itB}')
        itC = item4({'病15': {'script': '__不存在__.py', 'anchor': ANCH}, '病10': g_ok})
        if not itC or itC['s'] != 'yellow' or '2 病号' not in itC['t'] or '病15×' not in itC['e']:
            fails.append(f'闸化·混合C 登记未落地应回到 ungated：{itC}')
        itD = item4({'病15': g_ok, '病10': g_ok, '病1': g_ok})   # 全有 → green
        if not itD or itD['s'] != 'green':
            fails.append(f'闸化·混合D 全登记应 green：{itD}')
        print(f"  selftest[闸化·混合]: A={itA['s'] if itA else 'None'} "
              f"B={itB['s'] if itB else 'None'} C={itC['s'] if itC else 'None'} "
              f"D={itD['s'] if itD else 'None'}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return fails


def selftest():
    """正反向：红/黄/绿三态在真数据上现形；反向靠临时构造缺 ref 回执。
    v0.8.73 追加闸化登记分支（_gate_selftest）：五种形态/反例/端到端 green-yellow。"""
    import json
    import shutil
    import tempfile
    led = os.path.join(REPO, 'archive_ledger.json')
    bak = tempfile.mktemp()
    shutil.copy(led, bak)
    fails = []
    try:
        # 闸化登记分支（独立临时 repo，不碰真账本，放在造违例之前）
        fails += _gate_selftest()
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
    print('  ✓ 正反向全通过（闸化五形态+反例+端到端 green/yellow；真数据绿/黄、造违例即红）')
    return 0


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        sys.exit(selftest())
    st = check()
    print(f"[experience-gate] M12 经验门状态: {st}")
    sys.exit(1 if st == 'red' else 0)
