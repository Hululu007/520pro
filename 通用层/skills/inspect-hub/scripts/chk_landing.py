#!/usr/bin/env python3
"""v0.8.64 方案v3：落地监测三面（M9 总览 / M10 薄弱 / M11 项目追踪）。
契约与既有 chk_* 一致：chk(target, cfg, ctx) -> {'status', 'items'}。
三态铁律：取不到/失败 → 白（无法判定），绝不装绿；数据源全部离线为主，census 一项可失败降级。
"""
import datetime, glob, json, os, re, subprocess

TH = lambda ctx, k, dflt: (ctx.get('thresholds') or {}).get(k, dflt)


def _worst(ctx, sts):
    """聚合器：优先复用引擎 worst（单一真源），异常时本地降级实现（三态顺序一致）。"""
    f = ctx.get('worst')
    if f:
        return f(sts)
    order = ['green', 'yellow', 'red', 'unknown', 'pending']
    for k in ('red', 'unknown', 'yellow', 'pending', 'green'):
        if k in sts:
            return k
    return 'unknown'


def _repo(target, cfg):
    return cfg.get('repo') or target


def _ledger(repo):
    return os.path.join(repo, 'archive_ledger.json')


def _load_ledger_safe(repo):
    p = _ledger(repo)
    if not os.path.isfile(p):
        return 'missing', None, p
    try:
        d = json.load(open(p, encoding='utf-8'))
        if not isinstance(d, dict) or not isinstance(d.get('entries'), list):
            return 'corrupt', None, p
        return 'ok', d['entries'], p
    except Exception as e:
        return 'corrupt', repr(e), p


def chk_overview(target, cfg, ctx):
    """M9 总览面：520 整体情况（版本/技能/分片/落库回执/云端缝率）。"""
    items, sts = [], []
    repo = _repo(target, cfg)
    # 1) 版本
    vp = os.path.join(repo, 'VERSION')
    try:
        ver = open(vp, encoding='utf-8').read().strip()
        items.append({'t': f'【绿】520pro 版本 {ver}', 'e': 'VERSION 文件', 'c': '无需处置'})
        sts.append('green')
    except Exception as e:
        items.append({'t': '【白】VERSION 读取失败，无法判定', 'e': repr(e), 'c': '核对仓库完整性'})
        sts.append('unknown')
    # 2) 技能与分片
    skills = os.path.expanduser(cfg.get('install_root', '~/.codebuddy/skills'))
    n_skill = len([d for d in glob.glob(os.path.join(skills, '*',)) if os.path.isdir(d)])
    n_shard = 0
    for p in glob.glob(os.path.join(skills, '*', 'artifacts.json')):
        try:
            if isinstance(json.load(open(p, encoding='utf-8')).get('blueprint'), dict):
                n_shard += 1
        except Exception:
            pass
    if n_shard:
        items.append({'t': f'【绿】技能 {n_skill} 个 / 蓝图分片 {n_shard} 个（产出自动跟随）',
                      'e': skills, 'c': '无需处置'})
        sts.append('green')
    else:
        items.append({'t': '【黄】零蓝图分片——产出将落「未归类」', 'e': skills, 'c': '核对 artifacts.json 安装完整性'})
        sts.append('yellow')
    # 3) 落库回执（今日）
    st, entries, p = _load_ledger_safe(repo)
    today = datetime.date.today().isoformat()
    if st == 'ok':
        n_today = sum(1 for e in entries if (e.get('ts') or '')[:10] == today and e.get('result') == 'ok')
        items.append({'t': f'【绿】archive_ledger 今日落库回执 {n_today} 条', 'e': p, 'c': '无需处置'})
        sts.append('green')
    elif st == 'missing':
        items.append({'t': '【白】archive_ledger 缺失，落库对账无法判定', 'e': p, 'c': '跑方案 v3 步骤补建'})
        sts.append('unknown')
    else:
        items.append({'t': '【红】archive_ledger 损坏（数据基座塌陷 M-R58）', 'e': str(entries)[:120], 'c': '从 Git 恢复或修复 JSON'})
        sts.append('red')
    # 4) 云端缝率（census，可失败降级为无法判定）
    try:
        sh = cfg.get('space_hub', os.path.expanduser('~/.codebuddy/skills/space-hub/scripts/space_hub.py'))
        r = subprocess.run(['python3', sh, 'census'], capture_output=True, text=True, timeout=25)
        m = re.search(r'缝（无主）(\d+)（(\d+)%\）', r.stdout)
        if m:
            pct = int(m.group(2))
            if pct <= 20:
                items.append({'t': f'【绿】云端缝率 {pct}%（{m.group(1)} 个）', 'e': 'space-hub census', 'c': '无需处置'})
                sts.append('green')
            else:
                items.append({'t': f'【黄】云端缝率 {pct}%——归属治理欠账', 'e': 'space-hub census', 'c': '补 space_hub_zones.json 登记'})
                sts.append('yellow')
        else:
            items.append({'t': '【白】census 输出无缝率行，无法判定', 'e': r.stdout[-120:], 'c': '手跑 census 核查'})
            sts.append('unknown')
    except Exception as e:
        items.append({'t': '【白】census 调用失败（云端不可达/超时），无法判定', 'e': repr(e)[:120], 'c': '网络恢复后复跑'})
        sts.append('unknown')
    return {'status': _worst(ctx, sts), 'items': items}


def chk_weakness(target, cfg, ctx):
    """M10 薄弱面：遗留登记待办/超期、ledger pending、近期 bump 密度。"""
    items, sts = [], []
    repo = _repo(target, cfg)
    today = datetime.date.today()
    # 1) 遗留登记
    lp = os.path.join(repo, 'docs', '遗留登记.md')
    try:
        txt = open(lp, encoding='utf-8').read()
        n_open = txt.count('【待】')
        overdue = []
        for m in re.finditer(r'期限：(\d{4}-\d{2}-\d{2})', txt):
            try:
                if datetime.date.fromisoformat(m.group(1)) < today:
                    overdue.append(m.group(1))
            except ValueError:
                pass
        if overdue:
            items.append({'t': f'【红】遗留登记超期 {len(overdue)} 条 / 待办 {n_open} 条', 'e': '期限<' + today.isoformat() + ': ' + ', '.join(overdue[:4]), 'c': '逐条闭环或改期（B-14）'})
            sts.append('red')
        else:
            items.append({'t': f'【绿】遗留登记 {n_open} 条待办，0 超期', 'e': 'docs/遗留登记.md', 'c': '无需处置'})
            sts.append('green')
    except FileNotFoundError:
        items.append({'t': '【白】遗留登记文件缺失，无法判定', 'e': lp, 'c': '巡检司 M6 面数据源核对'})
        sts.append('unknown')
    # 2) ledger pending
    st, entries, p = _load_ledger_safe(repo)
    if st == 'ok':
        n_pend = sum(1 for e in entries if e.get('result') == 'pending')
        if n_pend > 10:
            items.append({'t': f'【黄】ledger pending {n_pend} 条——待归档欠账偏多', 'e': p, 'c': 'products --retry 补投或人工处置后销账'})
            sts.append('yellow')
        else:
            items.append({'t': f'【绿】ledger pending {n_pend} 条（含说明性欠账）', 'e': p, 'c': '无需处置'})
            sts.append('green')
    else:
        items.append({'t': '【白】ledger 不可读，pending 无法判定', 'e': str(entries)[:100], 'c': 'M9 已报，此处不重复'})
        sts.append('unknown')
    # 3) 近 3 天 bump 密度（改动活跃度提示）
    n_bump = 0
    for cl in glob.glob(os.path.join(repo, '**', 'CHANGELOG.md'), recursive=True):
        try:
            head = open(cl, encoding='utf-8').read(3000)
        except Exception:
            continue
        for m in re.finditer(r'^## v[\d.]+ — (\d{4}-\d{2}-\d{2})', head, re.M):
            try:
                if (today - datetime.date.fromisoformat(m.group(1))).days <= 3:
                    n_bump += 1
                    break
            except ValueError:
                pass
    items.append({'t': f'【绿】近 3 天 {n_bump} 个技能有版本 bump（活跃度事实行）', 'e': 'CHANGELOG 扫描', 'c': '活跃≠风险，供总览参考'})
    sts.append('green')
    return {'status': _worst(ctx, sts), 'items': items}


def chk_projects(target, cfg, ctx):
    """M11 项目面：逐技能版本/最近变更/最近落库回执——具体项目落地追踪。"""
    items, sts = [], []
    repo = _repo(target, cfg)
    st, entries, _p = _load_ledger_safe(repo)
    yd = TH(ctx, 'stale_yellow_days', 14)
    rd = TH(ctx, 'stale_red_days', 30)
    today = datetime.date.today()
    proj = cfg.get('projects') or [
        ('探源司', '能力层/tvbox/skills/probe-hub'),
        ('整包坊', '能力层/tvbox/skills/tvbox-pipeline'),
        ('库务司', '通用层/skills/space-hub'),
        ('巡检司', '通用层/skills/inspect-hub'),
        ('学习工坊', '通用层/skills/learn-hub'),
    ]
    for name, rel in proj:
        base = os.path.join(repo, rel)
        sk = os.path.join(base, 'SKILL.md')
        cl = os.path.join(base, 'CHANGELOG.md')
        ver, last, last_day = '', '', None
        try:
            m = re.search(r'^version:\s*"?([^"\n]+)"?', open(sk, encoding='utf-8').read(6000), re.M)
            ver = (m.group(1) if m else '?').strip()
        except Exception:
            pass
        try:
            m = re.search(r'^## (v[\d.]+) — (\d{4}-\d{2}-\d{2})', open(cl, encoding='utf-8').read(4000), re.M)
            if m:
                last, last_day = m.group(1), datetime.date.fromisoformat(m.group(2))
        except Exception:
            pass
        if not last_day:
            items.append({'t': f'【白】{name}：版本 {ver or "取不到"}，最近变更无法判定', 'e': rel, 'c': '核对 CHANGELOG'})
            sts.append('unknown')
            continue
        days = (today - last_day).days
        # ledger 里该技能最近回执
        last_ok = ''
        if st == 'ok':
            for e in reversed(entries):
                if e.get('result') == 'ok' and name in json.dumps(e, ensure_ascii=False):
                    last_ok = (e.get('ts') or '')[:10]
                    break
        if days >= rd:
            items.append({'t': f'【红】{name} v{ver}：最近变更 {last}（{days} 天前）≥ {rd} 天停更', 'e': rel, 'c': '确认是否需要保鲜或宣布冻结'})
            sts.append('red')
        elif days >= yd:
            items.append({'t': f'【黄】{name} v{ver}：最近变更 {last}（{days} 天前）', 'e': rel, 'c': '观察新鲜度'})
            sts.append('yellow')
        else:
            items.append({'t': f'【绿】{name} v{ver}：最近变更 {last}（{days} 天前）｜最近落库回执 {last_ok or "无"}',
                          'e': rel, 'c': '无需处置'})
            sts.append('green')
    return {'status': _worst(ctx, sts), 'items': items}
