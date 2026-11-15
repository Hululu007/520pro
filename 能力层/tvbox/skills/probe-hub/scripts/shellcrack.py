# -*- coding: utf-8 -*-
import os  # fix_paths.py 注入（路径跨机器适配）
"""probe-hub · 模块 G：壳源侦察与抠链（shellcrack，S196 固化）。

来历：S196 跨站实验（LunaTV 清单 10 站）验证了「播放页壳」抠链流程可复制：
  候选站 ac=detail 形态分诊 → 壳页三模板正则 → urljoin 转绝对 → 真拉分片验活 → 入播放页壳库。
正本判据（全部来自实测，不许改口）：
  ① 三模板金律正则（顺序不可换）：
     const url=…m3u8…（相对）→ const vid='…' → const vid="…" → var main=…m3u8… → 任意裸 m3u8
     ★ const url 必须排在 vid 之前——否则 vid 双引号正则先命中 hex id（无 .m3u8）抢匹配。
  ② urljoin 金律：壳内相对路径、master 子清单行、分片行都可能 '/' 开头绝对路径——
     一律 urljoin（对 http 绝对行也安全）；base+ 拼接会双路径 404（茅台站实测）。
  ③ 「已抠」必须真拉分片 >1KB——与 livecheck 同构，HTTP 200 不算数（S097 判据一）。
  ④ 三态：已抠 / 壳死 / 抠出但链死 / 待抠（页面通但正则未命中，如实报「非CMS模板」不硬凑）。
  ⑤ 形态分诊（ac=detail 第一段播放地址）：
     .m3u8/.mp4 → 直链站（交 livecheck/harvest 链，不归本模块）；
     页面路径   → 壳（本模块抠）；
     from 变体接口返回壳（如新浪 xlyun）→「接口给壳」混合形态，可抠但产物是每片 hash，
     进不了 type=1 直链 json，须 spider 嗅探——如实登记，不硬进包。
入库：探源司·总库下的「播放页壳库」DB_SHELL=hPF6AUmWmOQa26tOg8Wjb5。
"""
import json, re, sys, time, urllib.request, urllib.error
from urllib.parse import urljoin

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
DB_SHELL = 'hPF6AUmWmOQa26tOg8Wjb5'
LIB = os.path.expanduser('~/.codebuddy/skills/library')

def _first_json(text):
    """摘第一个可解析 JSON 对象（正本输出是 `KS_XXX_OK\t{json}`，JSON 不在行首）。"""
    for i, ch in enumerate(text or ''):
        if ch != '{':
            continue
        try:
            # ★ 必须 raw_decode：正本输出是「KS_OK\t{json}\nKS_USER_REPLY\t…」多行，
            #   json.loads(text[i:]) 会把尾随行算进去 → 整体失败 → 静默返回 {}。
            #   实测 db_edit set-records：add_count/record_ids 全丢，只剩一个'成功'标签。
            obj, _ = json.JSONDecoder().raw_decode(text[i:])
        except Exception:
            continue
        if isinstance(obj, dict):
            return obj
    return {}


# ── 本地壳库（2026-11-12 立为权威）──────────────────────────────────────────
# 为什么改：原实现读回要 `eco-ledger/core_ledger`、入库要 `library/database/*.py`，
# 而这两个技能在新生态里都没装 —— 于是「入库必须 readback」这条硬规则整条落空，
# 探源司 self-check 的壳库项一直红着。实测：造一个只提供 rows_of 的假账房司，
# readback 逻辑一次就正确，说明**缺的是数据源，不是逻辑**。
# 现在本地 JSON 为权威，云端有就双写、没有就只写本地，任何一边失败都不阻断另一条路。
SHELL_LIB = os.path.expanduser('~/.codebuddy/tvbox/shell_library.json')


# ── 基础 ──
def fetch(url, timeout=12):
    """收敛到共享核心 core.http_get（T5 / M-R38 单一事实源）。

    保留原 UA + Referer:baidu 透传；异常行为与原 urllib 一致（失败抛 URLError 类异常）。
    """
    from core import http_get
    st, payload, reason = http_get(
        url, timeout=timeout, ua=UA,
        headers={'Referer': 'https://www.baidu.com/'}, as_text=False)
    if st != 'ok':
        raise urllib.error.URLError('http_get %s: %s' % (st, reason))
    return payload

# ── 金律正则（顺序即契约）──
PATTERNS = [
    ('const_url', r'''const\s+url\s*=\s*["']([^"'\s]*?\.m3u8[^"'\s]*)["']'''),
    ("vid_sq",    r"const\s+vid\s*=\s*'([^'\s]+)'"),
    ('vid_dq',    r'const\s+vid\s*=\s*"([^"\s]+)"'),
    ('var_main',  r'''var\s+main\s*=\s*["']([^"'\s]*?\.m3u8[^"'\s]*)["']'''),
    ('bare',      r'''["']?(https?://[^\s"']+?\.m3u8[^\s"']*)["']?'''),
]
TEMPLATES = {
    'const_url': 'Artplayer(相对url或绝对直链)',
    'vid_sq': 'DPlayer+hls.js(const vid)',
    'vid_dq': 'DPlayer+hls.js(const vid)',
    'var_main': 'DPlayer+ckplayer双挂(var main+playlist)',
    'bare': '裸m3u8(页面内直出)',
}


def crack(name, page):
    """抠一个播放页壳。返回 dict：status/note/m3u8/template。判据见文件头①②③④。"""
    host = page.split('/')[2]
    try:
        body = fetch(page)
    except Exception as e:
        return {'name': name, 'page': page, 'status': '壳死',
                'note': f'{type(e).__name__}:{str(e)[:40]}'}
    txt = body.decode('utf-8', 'ignore')
    hit = None
    for key, pat in PATTERNS:
        m = re.search(pat, txt)
        if m and ('.m3u8' in m.group(1) or key in ('vid_sq', 'vid_dq')):
            hit = (key, m.group(1))
            break
    if not hit:
        return {'name': name, 'page': page, 'status': '待抠',
                'note': f'页面{len(body)}B未命中正则（非CMS模板）'}
    key, raw = hit
    m3u8 = urljoin(page, re.sub(r'\s+', '', raw))   # ★ urljoin 金律 + 去所有空白
    try:
        lst = fetch(m3u8).decode('utf-8', 'ignore')
        cur = m3u8
        if '#EXT-X-STREAM-INF' in lst:
            lines = [l.strip() for l in lst.splitlines() if l.strip() and not l.startswith('#')]
            sub = urljoin(cur, lines[0])            # ★ '/' 开头行 urljoin 回根
            lst = fetch(sub).decode('utf-8', 'ignore')
            cur = sub
        segs = [l.strip() for l in lst.splitlines() if l.strip() and not l.startswith('#')]
        if not segs:
            return {'name': name, 'page': page, 'status': '抠出但链死', 'm3u8': m3u8,
                    'template': TEMPLATES[key], 'note': '清单无分片'}
        s1 = urljoin(cur, segs[0])                  # ★ 分片行同理
        t0 = time.time()
        b2 = fetch(s1)
        dt = max(time.time() - t0, 0.001)
        if len(b2) < 1024:
            return {'name': name, 'page': page, 'status': '抠出但链死', 'm3u8': m3u8,
                    'template': TEMPLATES[key], 'note': f'分片仅{len(b2)}B'}
        note = (f'{lst.count("#EXTINF")}段 首片{len(b2)//1024}KB '
                f'{len(b2)/1024/dt/1024:.2f}MB/s 正则命中={key}')
        return {'name': name, 'page': page, 'status': '已抠', 'm3u8': m3u8,
                'template': TEMPLATES[key], 'note': note}
    except Exception as e:
        return {'name': name, 'page': page, 'status': '抠出但链死', 'm3u8': m3u8,
                'template': TEMPLATES.get(key, ''), 'note': f'{type(e).__name__}:{str(e)[:40]}'}


# ═══════════ S231 移植④：6 层播放集兜底 + 跨域广告排除 ═══════════
# 出处：references/S231_物料_OK影视一键写py.py L972-1019（`_shows` 六层兜底）+ L999-1002（跨域广告排除）。
# 为什么补：`crack()` 解的是**播放页**（壳页里已经拿到 m3u8）；而**详情页**上的选集
#   结构（几线路/几集/链接怎么拼）此前没有实现——于是「站点能进、播放页也能开，
#   但选不出集」这类站在探源司眼里只剩一个"待抠"，看不出到底缺哪一层。
#   六层是从实站归纳的**兜底顺序**（先精确模板、后宽泛扫描），不是六个独立方案：
#   前一层出结果就停——顺序颠倒会把推荐位/广告卡片当成选集（S196 同族坑）。
_AD_WORDS = ('教程', '帮助', '下载', '注册', '登录', '充值', '公告', 'APP', '求片')


def _txt(s):
    """去标签取纯文本（六层里每层都要用，收敛到一处）。"""
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', s or '')).strip()


def _is_ad(text, href, bases):
    """跨域广告/推广判定（S231 L999-1002 的分型，逐条给理由）。

    三类：①绝对地址且不在站点域名内 → 站外推广；②文案含推广/年份评分 → 推荐卡片；
    ③文案过长（>20 字）→ 不是集名（集名极少超过 20 字）。
    """
    if href.startswith('http') and bases and not any(
            href.rstrip('/').startswith(b.rstrip('/')) for b in bases):
        return True
    if re.search(r'\d\.\d\s*分|\b(19|20)\d{2}\b', text or ''):
        return True
    if any(w in (text or '') for w in _AD_WORDS):
        return True
    return len(text or '') > 20


def play_sets(html, page, bases=None):
    """详情页 → 播放集结构。返回 {'layer': 层级名, 'groups': {sid: [[集名, 绝对URL], ...]}}。

    六层顺序（**不可换**，前一层出结果即停）：
      A0 通用苹果CMS 三数字模板 `ID-SID-EID.html`（`/vodplay/` 与 `/play/` 都收）
      A  同一模板的 `data-line`/`data-episode` 锚点（字母 ID 站常见）
      A2 `vodplay` 相对地址重写（页面只给相对地址、没给完整路径）
      B  带数字的 play 链接（`/play?xx=1&ep=2` 这类，排除站外/推广）
      C  iframe / JSON 里的直链（`"url":"...m3u8"`，最后一层：拿到的是播放器地址）
    跨域广告在 B/C 层按 `_is_ad` 剔除，**并统计剔除条数**——静默丢弃是另一种骗人。
    """
    bases = [b.rstrip('/') for b in (bases or []) if b]
    if not bases:
        m = re.match(r'^(https?://[^/]+)', page or '')
        bases = [m.group(1)] if m else []
    html = html or ''

    def _abs(u):
        return urljoin(page, u)

    # ── A0/A：三数字模板（苹果CMS 重写 / play 路径）──
    groups = {}
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, re.S | re.I):
        href, inner = m.group(1), m.group(2)
        mm = re.search(r'/(?:vodplay|play)/?(\d+)[-_/](\d+)[-_/](\d+)', href)
        if not mm:
            continue
        t = _txt(inner)
        if _is_ad(t, _abs(href) if not href.startswith('http') else href, bases):
            continue
        pid, sid, eid = mm.group(1), mm.group(2), mm.group(3)
        u = _abs(href.split('?')[0])
        groups.setdefault(sid, {})
        groups[sid].setdefault(u, [t or f'第{eid}集', u, int(eid)])
    if groups:
        return {'layer': 'A0 三数字模板', 'groups': _finish(groups)}

    # ── A：data-line / data-episode 锚点（按线路分组）──
    for chunk in re.split(r'<a\s', html):
        tag = chunk.split('>')[0]
        m1 = re.search(r'href="([^"]*?/play/[A-Za-z0-9]{5,}[^"]*)"', tag)
        m2 = re.search(r'data-line="(\d+)"', tag)
        m3 = re.search(r'data-episode="(\d+)"', tag)
        if m1 and m2 and m3:
            sid, ep = m2.group(1), m3.group(1)
            u = _abs(m1.group(1))
            groups.setdefault(sid, {})
            groups[sid].setdefault(u, [f'第{ep}集', u, int(ep)])
    if groups:
        return {'layer': 'A data-line 锚点', 'groups': _finish(groups)}

    # ── B：带数字的 play 链接（最后一道选集兜底；跨域广告在此剔除并计数）──
    #   原文分层只有 A0/A/A2锚点/B/C 四段；「A2 vodplay 重写」已在 A0 一并覆盖，
    #   不再单列一层——单列会把本层用例提前吃掉，让「广告剔除计数」永远不触发。
    dropped = 0
    for href, inner in re.findall(
            r'<a[^>]+href="([^"]*(?:play|vodplay)[^"]*)"[^>]*>(.*?)</a>', html, re.S | re.I):
        if not re.search(r'\d', href):
            continue
        t = _txt(inner)
        if _is_ad(t, _abs(href) if not href.startswith('http') else href, bases):
            dropped += 1
            continue
        u = _abs(href)
        groups.setdefault('1', {})
        groups['1'].setdefault(u, [t or '播放', u, len(groups['1'])])
    if groups:
        return {'layer': f'B play 链接（广告剔除 {dropped}）', 'groups': _finish(groups)}

    # ── C：iframe / JSON 直链 ──
    for src in re.findall(r'(?:iframe[^>]+src\s*=\s*|"url"\s*:\s*)"([^"]*(?:m3u8|player|play)[^"]*)"',
                          html, re.I):
        u = _abs(src)
        groups.setdefault('1', {})
        groups['1'].setdefault(u, [_txt(src)[:12] or '线路', u, len(groups['1'])])
    if groups:
        return {'layer': 'C iframe/JSON 直链', 'groups': _finish(groups)}
    return {'layer': '', 'groups': {}}


def _finish(groups):
    """组内按集号排序、丢集号，补全为绝对地址前的收尾（与原文结构一致）。"""
    out = {}
    for sid, eps in groups.items():
        out[sid] = [[n, u] for n, u, _i in sorted(eps.values(), key=lambda x: x[2])]
    return out


def play_sets_shows(ps):
    """把 play_sets 结果转成 TVBox shows/urls 结构（层名也带上，便于复核走的哪一层）。"""
    keys = sorted(ps['groups'], key=lambda x: (len(x), x))
    shows = [f'线路{i + 1}' for i in range(len(keys))]
    urls = [ps['groups'][k] for k in keys]
    return shows, urls


def triage(name, api):
    """形态分诊：ac=detail 取中间一片，判 直链站 / 壳 / API死。返回 (形态, 详情dict)。"""
    try:
        d = json.loads(fetch(api + '?ac=detail&pg=1&h=72').decode('utf-8', 'ignore'))
        lst = d.get('list') or []
        if not lst:
            return 'api空', {'name': name, 'api': api, 'note': '返回0条'}
        v = lst[len(lst) // 2]
        d2 = json.loads(fetch(f'{api}?ac=detail&ids={v.get("vod_id")}').decode('utf-8', 'ignore'))
        v2 = (d2.get('list') or [{}])[0]
        first = (v2.get('vod_play_url') or '').split('#')[0]
        url = first.split('$')[-1] if '$' in first else first
        frm = v2.get('vod_play_from') or ''
        if re.search(r'\.(m3u8|mp4)', url):
            return '直链', {'name': name, 'api': api, 'from': frm, 'sample': url,
                            'note': '直链站——交 livecheck/harvest 链，不归本模块'}
        page = url if url.startswith('http') else urljoin(api.split('/api')[0] + '/', url)
        return '壳', {'name': name, 'api': api, 'from': frm, 'page': page,
                      'note': f'播放页壳（from={frm}）'}
    except Exception as e:
        return 'api死', {'name': name, 'api': api,
                         'note': f'{type(e).__name__}:{str(e)[:50]}——无法判定≠死，勿拉黑(M-R60)'}


# ── 本地库读写（原子写 + 三态：读失败 ≠ 空库）──
def _lib_load():
    """读本地壳库。返回 (records, ok, err)。ok=False 是「读失败」，不是「空库」。"""
    try:
        if not os.path.isfile(SHELL_LIB):
            return [], True, ''
        with open(SHELL_LIB, encoding='utf-8') as f:
            d = json.load(f)
        rows = d.get('records')
        if not isinstance(rows, list):
            return [], False, '文件结构异常（records 不是列表）——不敢当成空库'
        return rows, True, ''
    except Exception as e:
        return [], False, f'{type(e).__name__}: {str(e)[:80]}'


def _lib_save(rows):
    """原子写（tmp → rename），防止写一半断电留下半个库。返回 (ok, err)。"""
    try:
        os.makedirs(os.path.dirname(SHELL_LIB), exist_ok=True)
        tmp = SHELL_LIB + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump({'updated': time.strftime('%Y-%m-%dT%H:%M:%S'),
                       'note': f'播放页壳库（本地权威）。云端 DB_SHELL={DB_SHELL} 仍在双写。',
                       'records': rows}, f, ensure_ascii=False, indent=1)
        os.replace(tmp, SHELL_LIB)
        return True, ''
    except Exception as e:
        return False, f'{type(e).__name__}: {str(e)[:80]}'


def _cloud_rows():
    """读云端壳库。返回 (rows, ok, why)。依赖未装时 ok=False 并给出原因，不假装空库。"""
    d = os.path.expanduser('~/.codebuddy/skills/eco-ledger/scripts')
    if not os.path.isdir(d):
        return [], False, '账房司未装（~/.codebuddy/skills/eco-ledger）'
    try:
        if d not in sys.path:
            sys.path.insert(0, d)
        import core_ledger as L
        rows, good = L.rows_of(DB_SHELL)
        return (rows or []), bool(good), ('' if good else '云端读取失败')
    except Exception as e:
        return [], False, f'{type(e).__name__}: {str(e)[:80]}'


def to_local(x):
    """扁平记录（本地库用）。人可读、可 diff，不套多维表那层 {'text':...} 壳。"""
    return {
        'name': x.get('name', ''),
        'host': (x.get('page') or '').split('/')[2] if x.get('page') else '',
        'page': x.get('page', ''),
        'template': x.get('template') or '',
        'regex': x.get('regex_note') or '',
        'status': x.get('status', ''),
        'note': (x.get('note') or '')[:480],
        'm3u8': x.get('m3u8') or '',
        'saved_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
    }


# ── 入库：本地权威 + 云端可选（S144 判真判据保留：回执≠真相，必须 readback）──
def save(recs):
    """recs 是 crack/triage 产出的**原始扁平 dict 列表**（不是 to_record 的云端格式）。"""
    rows, ok, err = _lib_load()
    if not ok:
        print(f'❌ 本地壳库读取失败：{err}（不敢覆盖，先修文件再入库）'); return 0

    idx = {r.get('page'): i for i, r in enumerate(rows) if r.get('page')}
    new_n = upd_n = 0
    for x in recs:
        flat = to_local(x)
        p = flat.get('page')
        if p and p in idx:
            rows[idx[p]] = flat; upd_n += 1
        else:
            rows.append(flat); new_n += 1

    ok2, err2 = _lib_save(rows)
    if not ok2:
        print(f'❌ 本地入库失败：{err2}'); return 0
    print(f'✅ 本地壳库：新增 {new_n} · 覆盖 {upd_n} · 现有 {len(rows)} 条 → {SHELL_LIB}')

    # 云端双写：有就写、没有就明说、失败不阻断本地
    if not os.path.isdir(f'{LIB}/database'):
        print('   · 云端未装（library/database 不存在），本次仅存本地')
        n_ok = len(recs)
    else:
        payload = json.dumps({'records': [to_record(x) for x in recs]}, ensure_ascii=False)
        import subprocess
        # v0.8.33：正本 batch_add_database_records.py 已并入 db_edit.py --op set-records
        # （写入 + 逐条回读一次完成）。回执从 {"results":[{success}]} 变成
        # `KS_DB_EDIT_OK\t{add_count,failed_add_indices,verified_count}`，
        # 旧的前缀解析（找 '{' 开头行）会整段漏掉 → n_ok 恒为 0，看起来"云端全失败"。
        r = subprocess.run([sys.executable, f'{LIB}/database/db_edit.py',
                            '--database-id', DB_SHELL, '--op', 'set-records', '--stdin'],
                           input=payload, capture_output=True, text=True)
        text = (r.stdout or '') + (r.stderr or '')
        tag = next((ln.strip().split('\t')[0] for ln in text.splitlines()
                    if ln.strip().startswith('KS_')), '')
        d = _first_json(text)
        if tag == 'KS_DB_EDIT_OK':
            n_ok = len(recs)
        else:
            failed = d.get('failed_add_indices') or []
            n_ok = max(len(recs) - len(failed), 0) if isinstance(failed, list) else 0
        print(f'   云端双写：{n_ok}/{len(recs)} 成功（失败不影响本地）'
              + ('' if tag == 'KS_DB_EDIT_OK' else f'｜{tag or "无状态行"}'))

    print('   回执≠真相，请用 `shellcrack status` readback 复核')
    return n_ok


def to_record(x):
    rec = {
        '名称': {'text': x.get('name', '')[:100]},
        'host': {'text': x.get('page', '').split('/')[2] if x.get('page') else ''},
        '壳地址': {'url': {'text': (x.get('page') or '').split('/')[2], 'link': x.get('page')}},
        '模板指纹': {'text': x.get('template') or '未识别'},
        '抠链正则': {'text': x.get('regex_note') or '见 SKILL §3.16 金律'},
        '状态': {'select': x['status']},
        '备注': {'text': (x.get('note') or '')[:480]},
    }
    if x.get('m3u8'):
        rec['抠出直链'] = {'url': {'text': 'm3u8', 'link': x['m3u8']}}
    return rec


def status():
    """readback：本地优先、云端兜底。两边都读不到才报「无法判定」，不假装空库。"""
    rows, ok, err = _lib_load()
    src = '本地'
    if not ok:
        print(f'⚠️ 本地壳库读取失败：{err}')
    if ok and not rows:
        crows, cok, cwhy = _cloud_rows()
        if cok and crows:
            rows, src = crows, '云端'
        elif not cok:
            print(f'   · 本地为空；云端不可用（{cwhy}）→ 无法判定是否有历史记录')
            return 0

    from collections import Counter
    c = Counter((r.get('status') or r.get('状态')) for r in rows)
    print(f'播放页壳库（{src}）共 {len(rows)} 条：{dict(c)}')
    for r in rows[-8:]:
        if 'status' in r:                       # 本地扁平格式
            name, st, note = r.get('name'), r.get('status'), r.get('note')
            link = r.get('m3u8') or ''
        else:                                   # 云端多维表格式
            name = (r.get('名称') or {}).get('text') if isinstance(r.get('名称'), dict) else r.get('名称')
            st = r.get('状态')
            note = (r.get('备注') or {}).get('text') if isinstance(r.get('备注'), dict) else r.get('备注')
            lk = r.get('抠出直链') or {}
            link = ((lk.get('url') or {}).get('link') if isinstance(lk, dict) else '') or ''
        print(f'  [{st}] {name} {(note or "")[:50]}')
        if link:
            print(f'      {link[:90]}')
    return 0


# ── 命令入口（probe.py 薄封装调用）──
def cmd_shellcrack(a):
    op = a.cmd   # probe.py 注册 dest='cmd'（与全模块一致，S197 修 dest 名不一致：原此处读 a.op 靠兼容行兜底）
    if op == 'crack':
        r = crack(a.name or (a.page.split('/')[2]), a.page)
        print(f"[{r['status']}] {r['note']}")
        if r.get('m3u8'):
            print(f"  模板: {r.get('template')}")
            print(f"  直链: {r['m3u8']}")
        if a.save:
            save([r])
        return 0 if r['status'] == '已抠' else 1
    if op == 'probe':
        form, info = triage(a.name, a.api)
        print(f'[{a.name}] 形态={form}')
        for k, v in info.items():
            print(f'  {k}: {str(v)[:100]}')
        if form == '壳':
            r = crack(info['name'], info['page'])
            print(f'  → 抠链: [{r["status"]}] {r["note"]}')
            if r.get('m3u8'):
                print(f'    {r["m3u8"][:100]}')
            info.update(r)
            if a.save:
                save([info])
        return 0
    if op == 'scan':
        cands = []
        if a.infile:
            cands = json.load(open(a.infile))
        else:
            # 候选册是本机运行时数据（v0.8.12 起不随分发包携带）：新机器上本来就没有，
            # 这不是故障。缺件报"请用 --in"，绝不抛 FileNotFoundError 把命令崩掉。
            _cf = __file__.replace('shellcrack.py', 'shellcrack_cands.json')
            if not os.path.exists(_cf):
                print(f'ℹ️ 候选册不存在：{os.path.basename(_cf)}'
                      f'（本机运行时数据，新机器为空是正常状态）')
                print('   用法：shellcrack scan --in <清单.json>，清单格式 [[名称, 接口URL], ...]')
                return 0
            try:
                cands = json.load(open(_cf, encoding='utf-8'))
            except Exception as e:
                print(f'❌ 候选册损坏（{type(e).__name__}）：{_cf}——请人工修复或换 --in')
                return 2
        if not cands:
            print('ℹ️ 候选册为空——用 --in <清单.json> 提供待判定的壳站点')
            return 0
        results = []
        for name, api in cands:
            form, info = triage(name, api)
            print(f'[{name}] 形态={form} {info.get("note", "")[:60]}')
            if form == '壳':
                r = crack(name, info['page'])
                info.update(r)
                print(f'  → [{r["status"]}] {r["note"][:60]}')
                if r.get('m3u8'):
                    print(f'    {r["m3u8"][:90]}')
            results.append((form, info))
        if a.save:
            shells = [info for form, info in results if form == '壳']
            if shells:
                save(shells)
        n_shell = sum(1 for f, _ in results if f == '壳')
        n_ok = sum(1 for f, i in results if i.get('status') == '已抠')
        print(f'\n=== 扫描小结 === 分诊 {len(results)} 站：壳 {n_shell}（抠出 {n_ok}）'
              f' 直链 {sum(1 for f, _ in results if f == "直链")}'
              f' 死/空 {sum(1 for f, _ in results if f in ("api死", "api空"))}')
        return 0
    if op == 'status':
        return status()
    print(f'未知子命令 {op}'); return 2


def selftest():
    """离线自检（S231 移植④）：六层播放集兜底 + 跨域广告排除，全部离线。

    每层一个正向用例（造该层特征的最小 HTML）+ 每条排除规则一个反向用例。
    """
    fails = []

    def chk(name, cond, detail=''):
        print(f'[{"OK " if cond else "FAIL"}] {name}' + ('' if cond else f'  {detail}'))
        if not cond:
            fails.append(name)

    page = 'https://v.example.com/v/9.html'
    B = ['https://v.example.com']

    # A0：三数字模板 + 同集去重（同一 URL 出现两次只能算一集）
    html = ('<a href="/vodplay/9-1-1.html">第1集</a>'
            '<a href="/vodplay/9-2-1.html">第1集</a>'
            '<a href="/vodplay/9-1-1.html">第1集</a>')
    r = play_sets(html, page, B)
    chk('A0 命中三数字模板', 'A0' in r['layer'], r['layer'])
    chk('A0 按 sid 分两组', len(r['groups']) == 2, str(r['groups']))
    chk('A0 同集去重（1 集不重复）', len(r['groups'].get('1', [])) == 1, str(r['groups'].get('1')))

    # A：data-line/data-episode 锚点
    html = ('<a href="/play/abcDEF123" data-line="2" data-episode="3">x</a>'
            '<a href="/play/abcDEF124" data-line="2" data-episode="1">y</a>')
    r = play_sets(html, page, B)
    chk('A 命中 data-line 锚点', 'data-line' in r['layer'], r['layer'])
    chk('A 按集号排序（1 在 3 前）', [e[0] for e in r['groups']['2']] == ['第1集', '第3集'],
        str(r['groups']))

    # B：非三数字、非 data-line 的普通 play 链接（原文 A2/B 合并后的第一道兜底）
    r = play_sets('<a href="/play/someLongId9">第5集</a>', page, B)
    chk('B 命中普通 play 链接', r['groups'] and '第5集' in str(r['groups']), r['layer'])

    # B：跨域广告必须剔除，且被计入剔除数（不许静默丢）
    html = ('<a href="https://ad.example.net/play/123">推广影片 9.9分</a>'
            '<a href="/play/1?ep=2">第2集</a>')
    r = play_sets(html, page, B)
    chk('B 跨域广告被剔除', '推广' not in str(r['groups']), str(r['groups']))
    chk('B 同域选集保留', '第2集' in str(r['groups']), str(r['groups']))
    chk('B 剔除数写进层名（可见不静默）', '广告剔除' in r['layer'], r['layer'])

    # B 反向：广告词/年份评分/长文案三种都要挡
    chk('广告词被挡', _is_ad('注册送会员', '/play/1', B))
    chk('年份评分被挡', _is_ad('某片 2024 8.9分', '/play/1', B))
    chk('超长文案被挡', _is_ad('这是一个非常长的推荐位文案超过了二十个字符限制', '/play/1', B))
    chk('正常集名不挡', not _is_ad('第12集', '/play/12', B))
    chk('同域绝对地址不挡', not _is_ad('第3集', 'https://v.example.com/play/3', B))

    # C：iframe/JSON 直链
    r = play_sets('<iframe src="https://cdn.example.com/x.m3u8"></iframe>', page, B)
    chk('C 命中 iframe 直链', 'C ' in r['layer'] and 'x.m3u8' in str(r['groups']), r['layer'])
    r = play_sets('<script>var c={"url":"https://cdn.ex.com/y.m3u8"}</script>', page, B)
    chk('C 命中 JSON 直链', 'C ' in r['layer'] and 'y.m3u8' in str(r['groups']), r['layer'])

    # 反向：六层全不命中 → layer 为空、groups 为空（不硬凑）
    r = play_sets('<p>本站没有播放按钮</p>', page, B)
    chk('全不命中返回空（不硬凑）', r['layer'] == '' and r['groups'] == {}, str(r))

    # 相对地址必须补全成绝对（播放器拿相对地址直接哑）
    r = play_sets('<a href="/vodplay/9-1-1.html">第1集</a>', page, B)
    u = r['groups']['1'][0][1]
    chk('地址补全为绝对', u.startswith('https://v.example.com/'), u)

    # shows/urls 转换对齐 TVBox 结构
    shows, urls = play_sets_shows(r)
    chk('playsets→shows/urls 结构', shows == ['线路1'] and len(urls) == 1, f'{shows} {urls}')

    print()
    if fails:
        print(f'✗ shellcrack 离线自检 {len(fails)} 项失败：{fails}')
        return 1
    print('✓ shellcrack 离线自检全部通过（S231 移植④）')
    return 0


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        raise SystemExit(selftest())
    print(__doc__ or 'shellcrack：由 probe.py shellcrack 子命令调用；独立运行只支持 --selftest')
    raise SystemExit(2)
