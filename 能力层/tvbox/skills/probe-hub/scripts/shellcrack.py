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


# ═══════════════════════════════════════════════════════════════════
# 第 7 条金律：播放页二次解析（S231 L1215-1244 移植，bdb 46 源实测扩宽）
#
# 原文只给三条正则 + 一个 JSON 分支。拿 bdb 包 47 个真实 py 源做样本后发现不够用，
# 差异不是猜的，逐条有出处：
#
#   ① **JSON 字段名两种模板**：原文取 `d.get("url")`，但苹果CMS v10 标准模板
#      `player_aaaa` 的字段是 `link` / `link_next`（bdb 内 `player_aaaa=` 10 处，
#      歪比影视另用 `.url`）——只认 url 对标准模板**恒失败**，且失败得毫无声响。
#   ② **值可以是字符串不是 JSON**：`var player_aaaa='https://…m3u8'`（bdb 3 处），
#      原文的 `\{[\s\S]*?\}` 直接认不出。
#   ③ **裸赋值形态**：`const url = "…"` / `url: "…"`（6v.py `_find_media` 四条正则里占两条）。
#   ④ **iframe 套壳要下钻**：6v.py 的做法是「本页找不到 → 跟 iframe 再找一遍」，
#      原文只在一层页面里找，而播放页是 iframe 壳的站点极多。
#   ⑤ **网盘直链不该解析**：magnet:/夸克/百度/迅雷/阿里/123/189/139（6v.py 有现成识别）
#      是「本来就直接交给壳」的集，属于**前置分流**而不是解析失败。
#
# 判据顺序（前一层出结果即停）：NETDISK → L1 JSON → L2 字符串变量 → L3 JSON 字段
#   → L4 裸赋值 → L5 source:'' → L6 裸地址 → iframe 下钻 → parse:1 交壳嗅探
# ═══════════════════════════════════════════════════════════════════

_MEDIA = r'\.(?:m3u8|mp4|flv|mkv|ts)'
_NETDISK_HOSTS = ('pan.quark.cn', 'pan.baidu.com', 'xunlei.com', 'aliyundrive.com',
                  'alipan.com', 'cloud.189.cn', 'yun.139.com', '123pan.com')
_ENT = (('&amp;', '&'), ('&quot;', '"'), ('&#39;', "'"), ('&lt;', '<'), ('&gt;', '>'))


def _clean_url(u):
    """统一清洗：HTML 实体 → 反斜杠转义。三种真实世界都会出现，漏一种就整条失效。"""
    u = (u or '').strip()
    for a, b in _ENT:
        u = u.replace(a, b)
    return u.replace('\\/', '/').replace('\\u002F', '/').replace('\\u002f', '/')


def _is_netdisk(u):
    low = (u or '').lower()
    return low.startswith('magnet:') or any(h in low for h in _NETDISK_HOSTS)


def _resolve_once(html, page):
    """单页解析，返回 (层名, 绝对URL)；全不命中返回 ('', '')。纯函数、不联网。"""
    html = html or ''

    # 前置：网盘直链——这类集本来就直接交给壳，不是「解析不出来」
    m = re.search(r'magnet:\?[^\s"\'<>]+', html, re.I)
    if m:
        return 'NETDISK magnet', m.group(0)
    m = re.search(r'https?://[^\s"\'<>]*(?:%s)[^\s"\'<>]*'
                  % '|'.join(re.escape(h) for h in _NETDISK_HOSTS), html, re.I)
    if m:
        return 'NETDISK 网盘', _clean_url(m.group(0))

    # L1 `player_xxx = {...}` JSON：字段名 url / link / url_next / link_next / src 全认
    for pat in (r'player_[A-Za-z]*\s*=\s*(\{[\s\S]*?\})\s*;?\s*</script>',
                r'player_[A-Za-z]*\s*=\s*(\{[\s\S]{16,}?\})'):
        m = re.search(pat, html, re.I)
        if not m:
            continue
        try:
            d = json.loads(m.group(1))
        except Exception:
            continue                       # 括号截错/转义怪，退下一层，不抛
        if isinstance(d, dict):
            for k in ('url', 'link', 'url_next', 'link_next', 'src'):
                v = d.get(k)
                if isinstance(v, str) and re.search(_MEDIA, v, re.I):
                    return 'L1 player JSON(%s)' % k, _clean_url(v)

    # L2 `player_xxx = '…'`（值不是 JSON 而是字符串；原文认不出）
    m = re.search(r'player_[A-Za-z]*\s*=\s*[\'"]([^\'"]+%s[^\'"]*)[\'"]' % _MEDIA, html, re.I)
    if m:
        return 'L2 player 字符串', _clean_url(m.group(1))

    # L3~L6 依次尝试；同一套取值/清洗/补全逻辑走一张表，避免各层写法漂移
    for name, pat in (
            ('L3 JSON 字段', r'["\'](?:url|link|src)["\']\s*:\s*["\']([^"\']+%s[^"\']*)["\']' % _MEDIA),
            ('L4 裸赋值', r'(?:const\s+\w+\s*=\s*|url\s*[:=]\s*)["\']([^"\']+%s[^"\']*)["\']' % _MEDIA),
            ('L5 source', r'source\s*:\s*[\'"]([^\'"]+%s[^\'"]*)[\'"]' % _MEDIA),
            ('L6 裸地址', r'(https?:[^\s"\'<>\\]+%s[^\s"\'<>]*)' % _MEDIA),
    ):
        m = re.search(pat, html, re.I)
        if m:
            return name, _clean_url(m.group(1))
    return '', ''


def iframe_targets(html, page):
    """页面里的 iframe 地址（绝对化、去重、保持出现顺序）。"""
    out = []
    for src in re.findall(r'<iframe[^>]+src\s*=\s*["\']([^"\']+)["\']', html or '', re.I):
        u = urljoin(page, src)
        if u not in out:
            out.append(u)
    return out


def resolve_play_page(html, page, *, fetch=None, depth=1):
    """播放页 → 真实播放地址。返回 {'layer','url','parse','trace'}。

    parse=0 表示拿到了可直放地址；parse=1 表示交给壳嗅探（原文行为：**不硬凑**）。
    depth 控制 iframe 下钻层数（实测一层最有用；两层以上收益低且容易绕进广告页）。
    fetch 可注入，离线自检用假函数，避免「单测绕开真实链路」。
    """
    trace = []
    cur_html, cur_page = html, page
    for level in range(depth + 1):
        layer, u = _resolve_once(cur_html, cur_page)
        if u:
            if not u.startswith(('http://', 'https://', 'magnet:')):
                u = urljoin(cur_page, u)      # 相对地址播放器直接哑，必须补全
            trace.append(f'L{level} {layer}')
            return {'layer': layer, 'url': u, 'parse': 0, 'trace': trace}
        trace.append(f'L{level} 未命中')
        if level >= depth or fetch is None:
            break
        frames = iframe_targets(cur_html, cur_page)
        if not frames:
            break
        trace.append(f'L{level} 下钻 iframe（{len(frames)} 个候选）')
        nxt = None
        for fr in frames:
            try:
                h2 = fetch(fr)
            except Exception as e:
                trace.append(f'  取 {fr[:60]} 失败：{type(e).__name__}')
                continue
            lay2, u2 = _resolve_once(h2, fr)
            if u2:
                nxt = (h2, fr, lay2, u2)
                break
        if not nxt:
            trace.append('  下钻后仍未命中')
            break
        layer, u = nxt[2], nxt[3]
        if not u.startswith(('http://', 'https://', 'magnet:')):
            u = urljoin(nxt[1], u)
        trace.append(f'L{level + 1} {layer}（经 iframe）')
        return {'layer': layer + '（经 iframe）', 'url': u, 'parse': 0, 'trace': trace}
    return {'layer': '', 'url': page, 'parse': 1, 'trace': trace}


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
    if op == 'apk-types':
        # S233 §六①：借 jadx MCP 反编译判壳源类型（类名级证据），替代 strings 粗扫
        r = probe_shell_types(a.apk, jar=(a.jar or ''))
        if a.json:
            print(json.dumps(r, ensure_ascii=False, indent=1))
        else:
            print(f"[{r['status']}] {r['apk']}  类数={r['class_count']} 工具={r['tool_count']}")
            if r['reason']:
                print(f"  · 无法判定：{r['reason']}")
            print(f"  · 识别范围：{r['scope']}；{r['scope_warning']}")
            for st, v in r['types'].items():
                mark = '✓' if v['status'] == 'supported' else '·'
                ev = ', '.join(x['fqn'] for x in v['class_evidence'][:3]) or '（无类名证据）'
                print(f"  {mark} {st:14s} {v['status']:12s} raw={v['raw_hits']} "
                      f"确认={len(v['class_evidence'])} 误命中={len(v['substring_only'])}")
                print(f"      {ev}")
                if v['substring_only']:
                    print(f"      ⚠ 子串误命中（单列不删）："
                          f"{', '.join(x['fqn'] for x in v['substring_only'][:3])}")
        return 0 if r['status'] == 'ok' else 3   # 3 = 无法判定，不折叠
    print(f'未知子命令 {op}'); return 2


# ═══════════════════════════════════════════════════════════════════════════════
# S233 §六① · jadx MCP 反编译级壳能力侦察（替代 zipfile + strings 粗扫）
#
# 病15「判据识别范围 ≠ 对象范围」——本模块的判据边界必须写死在这里：
#   · 识别范围 = dex 里的 Java/Kotlin 类名（LeeCat 实测 7428 个）
#   · 对象范围 = 「这个壳支持哪些源类型」：其中 PHP WASM 运行时、drpy3、cat.js、
#     spider_compat.py、source_loader.py、pycryptodome 都在 assets/ 里，**不是类**
#   → 类名 0 命中一律记「无法判定（assets 层，判据不覆盖）」，**绝不判不支持**（B-02）。
#   → 三份账都报：raw_hits（原始）/ confirmed（词边界确认）/ substring_only（误命中），
#     误命中单列不静默删（B-18）。实测样本：搜 lua 唯一命中
#     kotlin.internal.IntrinsicConstEvaluation —— "Eva[lua]tion" 子串，非 Lua 类。
# ═══════════════════════════════════════════════════════════════════════════════

# 源类型 → (类名层关键词组, assets 层线索, 归属层)
# layer=class/asset/both：决定 0 命中时是「不支持」还是「无法判定」
SHELL_TYPE_SIGNALS = {
    'python': (('python', 'chaquopy', 'PyObject'), ('spider_compat.py', 'pycryptodome'), 'both'),
    'quickjs': (('quickjs',), ('drpy3', 'cat.js', 'cheerio'), 'both'),
    'catvod': (('catvod',), (), 'class'),
    'spider': (('spider',), (), 'class'),
    'php': (('php',), ('php-runtime/dispatcher.php', 'spider.php'), 'asset'),
    'lua': (('lua', 'luajava'), ('Kodi lua 插件集',), 'asset'),
    'drpy': (('drpy',), ('drpy3', 'cat.js'), 'asset'),
    'pycryptodome': (('pycryptodome', 'Crypto.Cipher'), ('pycryptodome-3.21.0',), 'asset'),
}

JADX_JAR_CANDIDATES = (
    '/tmp/milk/assets/mcp/jadx-headless-mcp-0.7.1-all.jar',
    os.path.expanduser('~/.local/share/jadx-headless-mcp-all.jar'),
)


def _seg_tokens(seg):
    """把一段类名切成 camelCase / 数字 / 非字母数字 边界的 token。"""
    return [t for t in re.split(r'(?<=[a-z0-9])(?=[A-Z])|[^A-Za-z0-9]+', seg) if t]


def _kw_in_fqn(kw, fqn):
    """词边界确认：kw 作为「段首」或「某个 camelCase token 精确相等」才算真命中。

    覆盖五种后接形态（本轮病15 同型坑：只认精确锚点会全漏）：
      ① 精确段      com.github.catvod.crawler.spider
      ② 前缀后接    SpiderService / SpiderNull / SpiderApi
      ③ camelCase   QuickJSContext（段小写以 quickjs 开头）
      ④ 包名段      com.lee.catvod.app.spider.DriveConfigActivity
      ⑤ 大小写变体  CatVod / catvod / QuickJSObject
    反例（必须排除）：IntrinsicConstEvaluation 里的 'lua' 只是子串，不是 token。
    返回 (confirmed, substring_only)。
    """
    k = (kw or '').lower()
    if not k:
        return False, False
    for seg in [s for s in re.split(r'[.$]', fqn or '') if s]:
        low = seg.lower()
        if low.startswith(k):            # 段首命中（含前缀后接 + camelCase 拼接）
            return True, False
        for t in _seg_tokens(seg):
            if t.lower() == k:           # 独立 token 精确相等（含大小写变体）
                return True, False
    if k in (fqn or '').lower():
        return False, True               # 子串误命中：单列，不静默删
    return False, False


def _resolve_jadx_jar(jar=''):
    """jar 不入 git（40MB，违反产物纪律）：三路解析，都取不到返回「无法判定」。"""
    import shutil
    for c in ((jar,) if jar else ()) + (os.environ.get('JADX_MCP_JAR', ''),) + JADX_JAR_CANDIDATES:
        if c and os.path.isfile(c):
            if not shutil.which('java'):
                return '', 'java 不在 PATH（无法判定）'
            return c, ''
    return '', 'jadx jar 未找到（--jar / JADX_MCP_JAR / 常见路径三路皆空），无法判定'


class JadxMCP:
    """jadx-headless-mcp 0.7.1 的 stdio JSON-RPC 最小客户端。

    工具名来自 tools/list 实测（S233 §3.3：rea-preset.json 的 24 个名字是上层封装，
    照抄必 Tool not found）——本客户端只用 load_apk / status / search_classes_by_keyword。
    transport 可注入（_FakeMCP），供离线 selftest 用，不启动 java。
    """
    def __init__(self, jar, timeout=300):
        self.jar = jar
        self.timeout = timeout
        self.proc = None
        self._id = 0
        self.tool_names = []

    def start(self):
        import subprocess
        self.proc = subprocess.Popen(
            ['java', '-jar', self.jar, '--transport', 'stdio'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, bufsize=0)
        init = self._call('initialize', {
            'protocolVersion': '2024-11-05', 'capabilities': {},
            'clientInfo': {'name': 'probe-hub-shellcrack', 'version': '1'}}, 120)
        if not init or 'result' not in init:
            raise RuntimeError('MCP initialize 无响应')
        self.proc.stdin.write((json.dumps({
            'jsonrpc': '2.0', 'method': 'notifications/initialized',
            'params': {}}) + '\n').encode())
        self.proc.stdin.flush()
        tl = self._call('tools/list', {}, 60)
        self.tool_names = [t.get('name') for t in
                           (((tl or {}).get('result') or {}).get('tools') or [])]
        return self

    def _call(self, method, params, timeout=None):
        self._id += 1
        i = self._id
        self.proc.stdin.write((json.dumps({
            'jsonrpc': '2.0', 'id': i, 'method': method,
            'params': params}) + '\n').encode())
        self.proc.stdin.flush()
        t0 = time.time()
        lim = timeout or self.timeout
        while time.time() - t0 < lim:
            line = self.proc.stdout.readline()
            if not line:
                return None
            s = line.decode('utf-8', 'ignore').strip()
            if not s.startswith('{'):
                continue
            try:
                d = json.loads(s)
            except Exception:
                continue
            if d.get('id') == i:
                return d
        return None

    def _text(self, r):
        if not r or 'error' in r:
            return ''
        return '\n'.join(c.get('text', '') for c in
                         ((r.get('result') or {}).get('content') or []))

    def load_apk(self, path):
        r = self._call('tools/call', {'name': 'load_apk',
                                      'arguments': {'path': path}}, 600)
        try:
            return json.loads(self._text(r))
        except Exception:
            return {'state': 'UNKNOWN'}

    def search(self, term, count=25):
        r = self._call('tools/call', {
            'name': 'search_classes_by_keyword',
            'arguments': {'search_term': term, 'search_in': 'class',
                          'count': count}}, 180)
        try:
            return json.loads(self._text(r))
        except Exception:
            return {'items': [], 'count': 0}

    def close(self):
        if self.proc:
            try:
                self.proc.terminate()
            except Exception:
                pass


def classify_shell_types(searches):
    """纯判据（可离线）：searches = {关键词: {'items':[{'fqn':...}], 'count':N}}。

    不碰 MCP、不碰文件系统 —— selftest 直接喂假响应即可覆盖全部形态。
    """
    out = {}
    for stype, (kws, asset_hints, layer) in SHELL_TYPE_SIGNALS.items():
        raw, confirmed, substr = [], [], []
        for kw in kws:
            data = searches.get(kw) or {}
            items = data.get('items') or []
            for it in items:
                fqn = it.get('fqn') or ''
                if not fqn:
                    continue
                raw.append({'kw': kw, 'fqn': fqn})
                ok, sub = _kw_in_fqn(kw, fqn)
                if ok:
                    confirmed.append({'kw': kw, 'fqn': fqn})
                elif sub:
                    substr.append({'kw': kw, 'fqn': fqn})
        # 三态：有确认证据 → supported；0 命中 → 一律 undetermined（不是「不支持」）
        status = 'supported' if confirmed else 'undetermined'
        if not confirmed:
            note = ('assets 层，类名判据不覆盖；0 命中≠不支持，不判不支持（B-02）'
                    if layer == 'asset' else
                    '本轮类名未命中；识别范围仅 dex 类，不判不支持（B-02）')
        else:
            note = '类名级证据（见 class_evidence）'
        out[stype] = {
            'status': status,
            'layer': layer,
            'raw_hits': len(raw),
            'class_evidence': confirmed[:20],
            'substring_only': substr,     # 误命中单列，不静默删（B-18）
            'asset_hints': list(asset_hints),
            'note': note,
        }
    return out


def probe_shell_types(apk, jar='', mcp=None):
    """S233 §六① 主入口：load_apk → search_classes_by_keyword → 类名级证据。

    返回三态 dict：status=ok（有 MCP 回执）/ undetermined（jar 或 java 或 APK 不可用）。
    """
    base = {
        'apk': apk, 'status': 'undetermined', 'reason': '',
        'scope': 'dex Java/Kotlin 类名',
        'scope_warning': 'PHP/drpy/pycryptodome 等 assets 脚本层不在本判据识别范围；'
                         '类名 0 命中一律记「无法判定」，不判「不支持」（病15）',
        'types': {}, 'class_count': 0, 'tool_count': 0,
    }
    # 离线注入 mcp 时 apk 只是标识，不做真实文件存在检查（否则 selftest 无法离线跑）——
    # 这本身也是「判据识别范围≠对象范围」：真实通道才需要校验落盘对象。
    if mcp is None and (not apk or not os.path.isfile(apk)):
        base['reason'] = 'APK 不存在，无法判定'
        return base
    if mcp is None:
        jpath, why = _resolve_jadx_jar(jar)
        if not jpath:
            base['reason'] = why
            return base
        try:
            mcp = JadxMCP(jpath).start()
        except Exception as e:
            base['reason'] = f'MCP 启动失败（{type(e).__name__}：{str(e)[:120]}），无法判定'
            return base
    own = mcp is not None and not isinstance(mcp, _FakeMCP)
    try:
        names = getattr(mcp, 'tool_names', []) or []
        if names and 'search_classes_by_keyword' not in names:
            base['reason'] = 'tools/list 无 search_classes_by_keyword，无法判定'
            return base
        base['tool_count'] = len(names) if names else 26
        loaded = mcp.load_apk(apk)
        base['class_count'] = loaded.get('class_count', 0)
        if loaded.get('state') != 'LOADED' and not isinstance(mcp, _FakeMCP):
            base['reason'] = 'load_apk 未 LOADED，无法判定'
            return base
        searches = {}
        for _stype, (kws, _hints, _layer) in SHELL_TYPE_SIGNALS.items():
            for kw in kws:
                if kw not in searches:
                    searches[kw] = mcp.search(kw, 25)
        base['types'] = classify_shell_types(searches)
        base['status'] = 'ok'
    finally:
        if own:
            mcp.close()
    return base


class _FakeMCP:
    """离线 selftest 注入用：不启动 java、不联网。"""
    def __init__(self, responses, tool_names=None):
        self.responses = responses
        self.tool_names = tool_names or ['load_apk', 'status',
                                         'search_classes_by_keyword']

    def load_apk(self, path):
        return {'state': 'LOADED', 'class_count': 7428}

    def search(self, term, count=25):
        return self.responses.get(term, {'items': [], 'count': 0})


# ── S233 §六② · 写源按壳分档（判据落 SKILL.md §3.12.3）──────────────────────
# LeeCat 自带 pycryptodome 3.21.0 → 原生 AES 足够；羊壳/未知壳 → 纯 Python 兜底。
# 三态：已知有 / 已知无 / 未知。未知一律走最保守的兜底，不赌壳能力（B-02）。
AES_VARIANT_NATIVE = 'native'      # from Crypto.Cipher import AES（原生）
AES_VARIANT_FALLBACK = 'fallback'  # _aes_fallback.py 纯 Python 兜底


def choose_aes_variant(capability):
    """按目标壳能力选 AES 实现分支。

    capability: 'has_pycryptodome' | 'no_pycryptodome' | 'unknown'（或壳能力档案 dict）
    返回 (variant, reason)。未知 → fallback（保守），绝不返回 native。
    """
    cap = capability if isinstance(capability, str) else \
        (capability or {}).get('pycryptodome', 'unknown')
    cap = (cap or 'unknown').lower()
    if cap in ('has_pycryptodome', 'has', 'native', 'true', 'yes'):
        return AES_VARIANT_NATIVE, '已知目标壳有 pycryptodome → 用原生 Crypto.Cipher.AES'
    if cap in ('no_pycryptodome', 'no', 'none', 'false'):
        return AES_VARIANT_FALLBACK, '已知目标壳无 pycryptodome → 用 _aes_fallback 纯 Python 兜底'
    return AES_VARIANT_FALLBACK, '壳能力未知（无法判定）→ 保守走 _aes_fallback，不赌壳能力'


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

    # ── 第 7 条金律：播放页二次解析（bdb 46 源实测形态）──
    # ⚠ 每条用例都断言**层名**，不能只看 url：低层兜底会把 url 补出来，
    #   于是「测 L1」实际测成了「测 L6」，反向摘掉 L1 也不红（本条自检第一版就栽在这）。
    # ① 苹果CMS 标准模板字段是 link/link_next，原文只取 url → 对标准模板恒失败
    h = ('<script>var player_aaaa={"flag":"play","encrypt":0,"trysee":0,"points":0,'
         '"link":"https:\\/\\/cdn.ex.com\\/a\\/index.m3u8","link_next":"",'
         '"server":"no","note":""}</script>')
    r7 = resolve_play_page(h, page)
    chk('金律①：L1 层认出苹果CMS link 字段（原文只认 url，此处必红）',
        r7['layer'].startswith('L1') and r7['url'] == 'https://cdn.ex.com/a/index.m3u8', str(r7))
    chk('金律①：\\/ 转义被还原', '\\' not in r7['url'], r7['url'])

    # ② 另一种模板用 url 字段
    r7 = resolve_play_page('<script>var player_aaaa={"url":"https://cdn.ex.com/b.m3u8"}'
                           '</script>', page)
    chk('金律②：L1 层认 url 字段模板',
        r7['layer'].startswith('L1') and r7['url'] == 'https://cdn.ex.com/b.m3u8', str(r7))

    # ③ 值不是 JSON 而是字符串（bdb 3 处 var player_aaaa='...'）
    r7 = resolve_play_page("<script>var player_aaaa='https://cdn.ex.com/c.m3u8'</script>", page)
    chk('金律③：L2 层认出字符串变量（原文的 \\{…\\} 认不出）',
        r7['layer'].startswith('L2') and r7['url'] == 'https://cdn.ex.com/c.m3u8', str(r7))

    # ④ 无 player_ 前缀的 JSON 字段 / 裸赋值 / source / 裸地址
    r7 = resolve_play_page('{"url":"https://cdn.ex.com/d.m3u8"}', page)
    chk('金律④：L3 层认 JSON 字段',
        r7['layer'].startswith('L3') and r7['url'] == 'https://cdn.ex.com/d.m3u8', str(r7))
    r7 = resolve_play_page('const url = "https://cdn.ex.com/e.m3u8"', page)
    chk('金律⑤：L4 层认 const url 裸赋值',
        r7['layer'].startswith('L4') and r7['url'] == 'https://cdn.ex.com/e.m3u8', str(r7))
    r7 = resolve_play_page("var c = {source:'https://cdn.ex.com/f.m3u8'}", page)
    chk('金律⑥：L5 层认 source:\'…\'',
        r7['layer'].startswith('L5') and r7['url'] == 'https://cdn.ex.com/f.m3u8', str(r7))
    r7 = resolve_play_page('点此播放 https://cdn.ex.com/g.m3u8 谢谢', page)
    chk('金律⑦：L6 层裸地址兜底',
        r7['layer'].startswith('L6') and r7['url'] == 'https://cdn.ex.com/g.m3u8', str(r7))

    # ⑤ 相对地址补全 + HTML 实体还原
    chk('金律⑧：相对地址补全为绝对',
        resolve_play_page('{"link":"/vod/h.m3u8"}', page)['url']
        == 'https://v.example.com/vod/h.m3u8')
    chk('金律⑨：&amp; 实体还原',
        resolve_play_page('{"url":"https://c.ex.com/i.m3u8?a=1&amp;b=2"}', page)['url']
        == 'https://c.ex.com/i.m3u8?a=1&b=2')

    # ⑥ 网盘直链是前置分流，不是解析失败
    r7 = resolve_play_page('<a href="magnet:?xt=urn:btih:ABC">下载</a>', page)
    chk('金律⑩：magnet 前置识别（parse=0 不硬凑）',
        r7['parse'] == 0 and r7['url'].startswith('magnet:'), str(r7))
    r7 = resolve_play_page('<a href="https://pan.quark.cn/s/abcd">夸克</a>', page)
    chk('金律⑪：网盘域名前置识别', 'NETDISK' in r7['layer'], str(r7))

    # ⑦ iframe 下钻（6v.py 的两次尝试；fetch 注入，不联网）
    r7 = resolve_play_page('<iframe src="/frame/1.html"></iframe>', page,
                           fetch=lambda u: '<script>var player_aaaa='
                                           '{"link":"https://cdn.ex.com/j.m3u8"}</script>', depth=1)
    chk('金律⑫：iframe 下钻命中', r7['parse'] == 0 and 'j.m3u8' in r7['url'], str(r7))
    chk('金律⑬：下钻过程写进 trace（不静默）',
        any('下钻' in t for t in r7['trace']), str(r7['trace']))
    r7 = resolve_play_page('<iframe src="/frame/2.html"></iframe>', page,
                           fetch=lambda u: '<p>页面里什么都没有</p>', depth=1)
    chk('金律⑭：下钻失败退 parse:1', r7['parse'] == 1, str(r7))

    # ⑧ 全失败：交壳嗅探，且 url 保持原页（不硬凑一个假地址）
    r7 = resolve_play_page('<p>本站暂无播放</p>', page)
    chk('金律⑮：全失败 parse:1 且 url 为原页',
        r7['parse'] == 1 and r7['url'] == page, str(r7))
    chk('金律⑯：失败也留 trace', bool(r7['trace']), str(r7['trace']))

    # ══ S233 §六① 词边界判据：五种后接形态 + 反向误命中 + 三态 ══
    # 本轮病15 同型坑：只认精确锚点会把 SpiderService / QuickJSContext / 包名段全漏掉。
    cases = [
        ('形态①精确段',   'spider', 'com.github.catvod.crawler.spider', True, False),
        ('形态②前缀后接', 'spider', 'com.github.catvod.crawler.SpiderService', True, False),
        ('形态③camelCase','quickjs','com.whl.quickjs.wrapper.QuickJSContext', True, False),
        ('形态④包名段',   'spider', 'com.lee.catvod.app.spider.DriveConfigActivity', True, False),
        ('形态⑤大小写',   'catvod', 'com.lee.catvod.app.CatVod', True, False),
        ('反向·子串误命中', 'lua', 'kotlin.internal.IntrinsicConstEvaluation', False, True),
        ('反向·完全无关', 'php', 'okhttp3.Dispatcher', False, False),
        ('反向·段中非词首','lua','org.foo.EvaluationHolder', False, True),
    ]
    for nm, kw, fqn, want_ok, want_sub in cases:
        got_ok, got_sub = _kw_in_fqn(kw, fqn)
        chk(f'S233①{nm}', got_ok == want_ok and got_sub == want_sub,
            f'{kw}@{fqn} → ok={got_ok} sub={got_sub} 期望 ok={want_ok} sub={want_sub}')

    # classify：真命中判 supported，0 命中判 undetermined（绝不判「不支持」）
    fake_searches = {
        'spider': {'items': [{'fqn': 'com.github.catvod.crawler.SpiderService'}]},
        'catvod': {'items': [{'fqn': 'com.lee.catvod.app.spider.SpiderService'}]},
        'python': {'items': [{'fqn': 'com.chaquo.python.PyObject'}]},
        'quickjs': {'items': [{'fqn': 'com.whl.quickjs.wrapper.QuickJSContext'}]},
        'lua': {'items': [{'fqn': 'kotlin.internal.IntrinsicConstEvaluation'}]},
    }
    cls = classify_shell_types(fake_searches)
    chk('S233①类名证据判 supported', cls['spider']['status'] == 'supported'
        and cls['spider']['class_evidence'], str(cls['spider']))
    chk('S233①0命中判 undetermined 不判不支持',
        cls['php']['status'] == 'undetermined'
        and '不判不支持' in cls['php']['note'], str(cls['php']))
    chk('S233①assets 层明确标注判据不覆盖',
        'assets 层' in cls['pycryptodome']['note'], str(cls['pycryptodome']))
    chk('S233①误命中单列不静默删（B-18）',
        cls['lua']['status'] == 'undetermined'
        and len(cls['lua']['substring_only']) == 1
        and cls['lua']['raw_hits'] == 1, str(cls['lua']))

    # 端到端（离线注入）：走通 load_apk→search→分类，不启动 java
    fake = _FakeMCP(fake_searches)
    e2e = probe_shell_types('/tmp/__fake_leecat__.apk', mcp=fake)
    chk('S233①离线端到端 status=ok', e2e['status'] == 'ok', str(e2e.get('reason')))
    chk('S233①端到端带类名级证据',
        e2e['types']['spider']['class_evidence'], str(e2e['types']['spider']))
    chk('S233①端到端三态范围声明在位',
        '0 命中' in e2e['scope_warning'], str(e2e['scope_warning']))
    # 反向：jar 三路皆空 → 无法判定，不折叠成通过/失败
    und = probe_shell_types('/tmp/__no_such_apk__.apk')
    chk('S233①APK/jar 不可用记无法判定（三态不折叠）',
        und['status'] == 'undetermined' and und['reason'], str(und))

    # ══ S233 §六② 写源按壳分档：两分支 + 未知保守 + 反向 ══
    v1, r1 = choose_aes_variant('has_pycryptodome')
    v2, r2 = choose_aes_variant('no_pycryptodome')
    v3, r3 = choose_aes_variant('unknown')
    v4, r4 = choose_aes_variant({'pycryptodome': 'has'})
    chk('S233②有 pycryptodome → 原生 AES', v1 == AES_VARIANT_NATIVE, r1)
    chk('S233②无 pycryptodome → 兜底', v2 == AES_VARIANT_FALLBACK, r2)
    chk('S233②未知 → 保守兜底不赌壳', v3 == AES_VARIANT_FALLBACK
        and '不赌壳能力' in r3, r3)
    chk('S233②档案 dict 形态同样命中', v4 == AES_VARIANT_NATIVE, r4)
    chk('S233②两分支互异（判据真有两路）', v1 != v2, f'{v1} vs {v2}')
    chk('S233②反向：未知绝不返回 native', v3 != AES_VARIANT_NATIVE, r3)

    print()
    if fails:
        print(f'✗ shellcrack 离线自检 {len(fails)} 项失败：{fails}')
        return 1
    print('✓ shellcrack 离线自检全部通过（S231 移植④ + S233 §六①②）')
    return 0


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        raise SystemExit(selftest())
    print(__doc__ or 'shellcrack：由 probe.py shellcrack 子命令调用；独立运行只支持 --selftest')
    raise SystemExit(2)
