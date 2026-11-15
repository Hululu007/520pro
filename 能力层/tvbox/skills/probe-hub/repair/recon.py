# -*- coding: utf-8 -*-
"""recon.py —— 整站重写的「重新侦察」档（batch 4）。

## 为什么 rewrite 必须先侦察

小补（patch）只需要知道「哪一行错了」；**整站重写需要知道「这站到底怎么出数据」**。
如果直接把「重写一遍」扔给 LLM，它一定会凭记忆套一个 maccms 模板 —— 这就是
S224/r147 记下的那个坑：`host` 写成站点主域的 `.html`，播放器拉不到任何东西。

所以 rewrite 的前置不是「写代码」，而是先回答三个问题：
  ① 数据从哪来（内联首屏 / XHR 接口 / 标准 CMS / 静态 HTML）
  ② 分页与筛选走哪套参数（路径尾页码 / query / 单选）
  ③ 详情页 → 播放地址是直链还是需要解析（parse:1）

## 三态纪律（M-R60）

抓不到 ≠ 没有。`recon()` 任何一步失败都把该字段置 None 并记 `undetermined`，
**绝不填默认值冒充侦察结果**。上游（engine/drafts）见到 None 必须如实转述。
"""
import json
import os
import re
import subprocess
import sys
from urllib.parse import urljoin

HERE = os.path.dirname(os.path.abspath(__file__))
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36')

# 侦察用的特征表：**只收「能改变生成策略」的特征**，不做大而全的指纹库。
# 每条都必须能对应到一个生成决策，否则就是噪音（43 项全塞进去 LLM 会挑花眼）。
FEATURES = {
    # —— 数据来源（决定 homeContent/categoryContent 怎么取）——
    'src_inline_nuxt': (r'__NUXT__|__NUXT_DATA__', '内联首屏：__NUXT__，走 _inline_items'),
    'src_inline_next': (r'__NEXT_DATA__|self\.__next_f', '内联首屏：__NEXT_DATA__，走 _inline_items'),
    'src_inline_app': (r'window\.APP_DATA|__INITIAL_STATE__|__PRELOADED_STATE__',
                       '内联首屏：APP_DATA 系，走 _inline_items'),
    'src_spa_shell': (r'<div id=["\'](?:app|root)["\']\s*>\s*</div>',
                      '空壳 SPA：首屏无数据，必须找 XHR 接口'),
    'src_cms_maccms': (r'/api\.php/provide/vod|/index\.php/vod/|macCms|苹果CMS', '标准采集接口'),
    'src_static_html': (r'<li[^>]*>\s*<a[^>]+href="[^"]*detail', '静态 HTML 列表'),
    # —— 分页形态（决定 categoryContent 的 URL 拼法）——
    'page_path_tail': (r'href="/[a-z]+/\d+/\d+"', '路径尾页码：/type/2/3'),
    'page_query': (r'[?&](?:page|p|pg)=\d+', 'query 页码：?page=2'),
    'page_ajax': (r'loadMore|infinite|滚动加载|nextPage', '滚动/异步加载，需找接口'),
    # —— 选集形态（r148）——
    'play_three_num': (r'/bofang/\d+-\d+-\d+\.html', '三数字模板：/bofang/{id}-{sid}-{nid}.html'),
    'play_query_id': (r'[?&](?:vid|id|sid)=\d+', 'query 传 id'),
    'play_m3u8_inline': (r'\.m3u8', 'HTML 里直接出现 m3u8'),
    # —— 防御（决定要不要 POOL / localProxy）——
    'def_cf': (r'cf-ray|__cf_bm|challenge-platform', 'Cloudflare'),
    'def_referer': (r'防盗链|hotlink', 'Referer 校验'),
    'def_encrypt_aes': (r'AES|CryptoJS', 'AES 加密载荷'),
    'def_sign': (r'\bsign=|_sign=|X-Sign', '请求签名'),
    # —— 站点身份（决定 categories 从哪取）——
    'nav_categories': (r'<a[^>]+href="[^"]*(?:type|vod|list)/\d+"[^>]*>([^<]{2,12})</a>',
                       '导航里已有分类链接'),
    # —— 跳转壳（命中则首页 HTML 毫无侦察价值，必须跟随）——
    'shell_redirect': (r'Redirecting\.\.\.|window\.location(?:\.href)?\s*=|'
                       r'<meta[^>]+http-equiv=["\']?refresh',
                       '跳转壳：首页只返回跳转页，真实内容在跳转后'),
}


def _meta_refresh(html):
    m = re.search(r'<meta[^>]+http-equiv=["\']?refresh["\']?[^>]*'
                  r'content=["\']?\s*\d+\s*;\s*url=([^"\' >]+)', html, re.I)
    return m.group(1).strip() if m else ''


def _js_redirect(html):
    m = re.search(r'(?:window\.)?location(?:\.href)?\s*=\s*["\']([^"\']+)["\']', html)
    if m:
        return m.group(1).strip()
    # location.replace(x) / location.assign(x)：x 是变量时取不到，返回空由上层判「需人工」
    m = re.search(r'(?:window\.)?location\.(?:replace|assign)\(\s*["\']([^"\']+)["\']', html)
    return m.group(1).strip() if m else ''


def _needs_cookie(html):
    """JS 挑战型跳转：`document.cookie = "名=值;max-age=…"` 后才放行。"""
    return bool(re.search(r'document\.cookie\s*=\s*[`"\']', html))


def _cookie_from_js(html):
    """从挑战脚本里取「写死形态」的 cookie：`document.cookie = "k=v;max-age=…"`。

    ★ 只处理**字面量**形态。真实挑战站常写成
      `document.cookie=`k=${btoa(resp)};max-age=5`` —— 值依赖接口返回，
      静态取不到。这种情况**必须如实返回空**，由上层判「需人工/需带状态抓」，
      不许猜一个 cookie 塞进去（猜错了请求全是 403，排查成本更高）。
    """
    m = re.search(r'document\.cookie\s*=\s*[`"\']([A-Za-z0-9_\-]{2,40}=[^;`"\']{2,80})[;`"\']',
                  html)
    return m.group(1) if m else ''


def _curl(url, timeout=15, referer='', insecure=False, extra_headers=None):
    """→ (body_text, http_code, err)。err 非空＝无法判定。

    `insecure`：加 `-k` 跳过证书校验。照 livecheck S169 的做法——证书过期
    **不是站点死了**（实测 ryzy.tv / lz.118318.xyz 证书过期但接口照常返数据）。
    侦察阶段先正常抓，失败再带 -k 重试一次；两次都失败才判「无法判定」。
    """
    cmd = ['curl', '-s', '-L', '--compressed', '--connect-timeout', '8',
           '--max-time', str(timeout), '-A', UA,
           '-w', '\n__CODE__%{http_code}']
    if insecure:
        cmd.insert(1, '-k')
    if referer:
        cmd += ['-H', f'Referer: {referer}']
    for k, v in (extra_headers or {}).items():
        cmd += ['-H', f'{k}: {v}']
    cmd.append(url)
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout + 10)
    except subprocess.TimeoutExpired:
        return '', 0, '超时'
    out = r.stdout.decode('utf-8', 'replace')
    m = re.search(r'\n__CODE__(\d+)$', out)
    code = int(m.group(1)) if m else 0
    body = out[:m.start()] if m else out
    if code == 0:
        return body, 0, f'curl 退出码 {r.returncode}'
    if code >= 400:
        return body, code, f'HTTP {code}'
    return body, code, ''


def _get(url, timeout=15, referer='', extra_headers=None):
    """先正常抓，证书类错误自动带 -k 重试一次。→ (body, code, err, note)"""
    body, code, err = _curl(url, timeout, referer, extra_headers=extra_headers)
    if not err:
        return body, code, '', ''
    if 'certificate' in err.lower() or 'SSL' in err or '退出码 60' in err:
        b2, c2, e2 = _curl(url, timeout, referer, insecure=True,
                           extra_headers=extra_headers)
        if not e2:
            return b2, c2, '', '证书校验失败，已用 -k 重试成功（证书类问题，非站点死）'
        return b2, c2, e2, ''
    return body, code, err, ''


def _abs(base, href):
    if not href:
        return ''
    if href.startswith('//'):
        return 'https:' + href
    return urljoin(base, href)


# ═══════════ S231 移植③：sniff 聚类打分 + 五层详情正则生成 ═══════════
# 出处：references/S231_物料_OK影视一键写py.py（聚类 L590-687 / 五层决策 L717-771）。
# 为什么补这条路：`_parse_list` 用的是**固定正则** `(detail|/info/|/vod/detail|/v/)`——
#   站点形态一变（`/post/3KBddy`、`/mhkh/slug/`、`/movie/9x2`）就一条都取不到，
#   侦察报告于是写「列表样例为空」，下游只能凭记忆套模板（r147 那个坑的同族）。
#   聚类打分不假设路径词：按「路径模式键」把全页链接分组，用**唯一 ID 数与 ID 长度**
#   判断哪一组像详情页，再选该组最长 URL 反推正则 → 任意形态自适应。
# 三态纪律不变：聚类不出来就返回空（`undetermined` 记原因），**绝不猜一个模板顶上**。
_S231_WORDS = {}


def _s231_words():
    """惰性读 S231_url_wordlists.json（词表是踩坑沉淀，不在这里复制一份——M2）。"""
    global _S231_WORDS
    if not _S231_WORDS:
        p = os.path.join(os.path.dirname(HERE), 'references', 'S231_url_wordlists.json')
        try:
            _S231_WORDS = json.load(open(p, encoding='utf-8'))
        except Exception:
            _S231_WORDS = {'CONTENT_DIRS': {'words': []}, 'SNIFF_SCORE': {}}
    return _S231_WORDS


def _content_dirs():
    return tuple((_s231_words().get('CONTENT_DIRS') or {}).get('words') or ())


def _path_key(u):
    """URL → 路径模式键（把 ID 段归一成 #）。判不出模式返回 ''。

    `/vodplay/123-1-1.html` → `/vodplay/#-#-#.html`；
    `/post/3KBddy`          → `/post/#`；
    `/detail-217011.html`   → `/#.html` 之外保留前缀字面量（单段形态按字母前缀归一）。
    """
    p = (u or '').split('?')[0].split('#')[0]
    p = re.sub(r'^https?://[^/]+', '', p)
    if not p or p == '/':
        return ''
    segs = [s for s in p.split('/') if s]
    if not segs:
        return ''
    last = segs[-1]
    ext = ''
    m = re.search(r'(\.html?|\.php|\.aspx?)$', last, re.I)
    if m:
        ext, last = m.group(1), last[:m.start()]
    if len(segs) == 1:
        # 单段形态：只把数字/长 ID 段归一，前缀字面量保留（否则全站塌成一个键）
        stem = re.sub(r'\d{2,}', '#', last)
        stem = re.sub(r'[A-Za-z0-9_-]{4,}', '#', stem) if '#' not in stem else stem
        return '/' + stem + ext
    parent = '/'.join(segs[:-1]).lower()
    if last.isdigit():
        key_last = '#'
    elif re.fullmatch(r'\d+-\d+-\d+', last):
        key_last = '#-#-#'
    elif re.fullmatch(r'\d+-\d+', last):
        key_last = '#-#'
    else:
        key_last = '#'
    return '/' + parent + '/' + key_last + ext


def _id_of(u):
    """URL → 候选 ID 段（用于判断这组链接是否真是"同一个详情模板"）。

    ★ 末段直接整段返回（不要求 ≥2 字符）：实测 `/detail/id/1.html` 这种单位数 ID
      若被 `{2,}` 过滤掉，就会回退到父段 `id`——**全站 URL 的"ID"都变成同一个词 `id`**，
      唯一 ID 数恒为 1，聚类永远不参选（本轮自检就是被这条挡下的）。
    """
    p = (u or '').split('?')[0].split('#')[0]
    p = re.sub(r'^https?://[^/]+', '', p)
    segs = [s for s in p.split('/') if s]
    if not segs:
        return ''
    last = re.sub(r'\.(html?|php|aspx?)$', '', segs[-1], flags=re.I)
    if re.fullmatch(r'[A-Za-z0-9_-]+', last or ''):
        return last
    for cand in segs[-2::-1]:
        m = re.search(r'[A-Za-z0-9]{2,}', cand)
        if m:
            return m.group(0)
    return ''


def sniff_detail_re(html, base, min_uniq=3, top=80):
    """全页链接聚类打分 → 最像详情页的样本 URL。判不出返回 ''。

    打分（S231 SNIFF_SCORE，公式原文照抄不改良）：
      score = 唯一ID数×10 + ID均长×3 + min(链接数,200)×0.2
    门槛：该组唯一 ID 数 ≥ min_uniq 才参选（两三条链接凑不出"模板"）。
    """
    hrefs = [m.group(1) for m in re.finditer(r'href=["\']([^"\']+)["\']', html or '', re.I)]
    groups = {}
    for h in hrefs:
        u = _abs(base, h) if not h.startswith('http') else h
        k = _path_key(u)
        if not k or k in ('/', '/#', '/#.html'):
            continue
        groups.setdefault(k, []).append(u)
    best = None
    for _k, urls in groups.items():
        uniq = {i for i in (_id_of(u) for u in urls[:top]) if i}
        if len(uniq) < min_uniq:
            continue
        avg = sum(len(x) for x in uniq) / float(len(uniq))
        score = len(uniq) * 10 + avg * 3 + min(len(urls), 200) * 0.2
        if best is None or score > best[0]:
            best = (score, max(urls[:top], key=len), len(uniq))
    return best[1] if best else ''


def build_detail_re(sample):
    """由样本 URL 反推详情正则（S231 五层决策 L717-771，顺序不可换）。

    五层：①剥扩展名 → ②单段前缀（`/detail-217011`）→ ③MacCMS 占位词
    （`/index.php/vod/detail/id/123.html`，倒数第二段是占位词）→ ④`/v/1489032/229`
    短参数（ID 在倒数第二段）→ ⑤slug 整段；兜底只替换**最后一段数字**（避免吃到域名里的数字）。
    生成的正则用 `[a-zA-Z0-9_-]` 类捕获组，与探源司其余正则口径一致（不写死数字）。
    """
    s = (sample or '').split('?')[0]
    if not s:
        return ''
    # ★必须连 host 一起剥：只剥 `https:` 时 host（如 site2024.com）会留在 segs 里，
    #   生成的正则变成 `/site2024\.com/abc/(...)` —— 域名一换整条正则就废，
    #   而且域名里的数字会被兜底层当 ID 吃掉（原始注释专门警告过这一点）。
    m_host = re.match(r'^https?://[^/]+', s, re.I)
    if m_host:
        s = s[m_host.end():] or '/'
    segs = [x for x in s.split('/') if x]
    if not segs:
        return ''
    last = segs[-1]
    ext = ''
    m = re.search(r'(\.html?|\.php|\.aspx?)$', last, re.I)
    if m:
        ext, last = m.group(1), last[:m.start()]
    parent = '/'.join(segs[:-1])
    head = '/' + parent + '/' if parent else '/'
    if not parent:
        # ② 单段形态：`/detail-217011` → 前缀字面量 + 数字捕获
        m2 = re.fullmatch(r'([A-Za-z_-]{3,12}?)(\d{2,12})', last)
        if m2:
            return '/' + re.escape(m2.group(1)) + r'(\d{2,12})' + re.escape(ext)
        return '/' + re.escape(last) + re.escape(ext)
    # ③ MacCMS 重写：倒数第二段是占位词，最后一节才是 ID
    if len(segs) >= 3 and segs[-2].lower() in (
            'id', 'ids', 'vid', 'vodid', 'key', 'code', 'name', 'title'):
        return re.escape('/' + '/'.join(segs[:-1]) + '/') + r'([A-Za-z0-9_-]{1,60})' + re.escape(ext)
    # ④ ID 在倒数第二段、末段是短参数（`/v/1489032/229`）
    if last.isdigit() and len(last) <= 6 and len(segs) >= 3:
        pp = segs[-3].lower()
        if pp in ('v', 'd', 'ep', 'eps', 'video', 'watch', 'detail', 'play', 'vod'):
            return (re.escape('/' + '/'.join(segs[:-2]) + '/')
                    + r'([A-Za-z0-9_-]{2,60})/' + re.escape(last) + re.escape(ext))
    # ⑤ 纯 slug / 字母数字混合（含数字，或长度 ≥4）→ 整段替换
    if re.fullmatch(r'[A-Za-z0-9_-]{3,}', last) and (re.search(r'\d', last) or len(last) >= 4):
        return re.escape(head) + r'([A-Za-z0-9_-]{2,60})' + re.escape(ext)
    # 兜底：只替换最后一段数字（注释原文：「避免吃到域名里的数字」）
    esc = re.escape('/' + '/'.join(segs))
    found = list(re.finditer(r'\d{3,}', esc))
    if not found:
        return esc
    lastm = found[-1]
    return esc[:lastm.start()] + r'(\d+)' + esc[lastm.end():]


def _parse_list_sniff(html, base, limit=6):
    """聚类路线的列表解析（S231 移植③）。返回 (items, detail_re)。

    与 `_parse_list` 的区别：**不假设路径词**。先聚类选出最像详情页的模式，
    再由样本反推正则，然后用这个正则回头抓页面上的条目。
    聚类不出来 → 返回 ([], '')，由调用方记 undetermined（不猜模板）。
    """
    sample = sniff_detail_re(html, base)
    if not sample:
        return [], ''
    dre = build_detail_re(sample)
    if not dre:
        return [], ''
    items, seen = [], set()
    for m in re.finditer(dre, html, re.I):
        href = m.group(0)
        u = _abs(base, href) if not href.startswith('http') else href
        if u in seen:
            continue
        # 标题取链接后 200 字内的 title 属性或可见文本
        tail = html[m.end():m.end() + 200]
        t = re.search(r'title="([^"]{2,60})"', tail)
        txt = re.sub(r'<[^>]+>', ' ', tail)
        title = (t.group(1) if t else txt).strip()
        title = re.sub(r'\s+', ' ', title)[:60]
        if len(title) < 2:
            continue
        seen.add(u)
        items.append({'title': title, 'url': u, 'pic': ''})
        if len(items) >= limit:
            break
    return items, dre


def recon(url, *, depth=1, timeout=15):
    """侦察一个站点 → dict（可直接进 evidence 包）。

    `depth`：1 = 只抓首页；2 = 再加一个分类页 + 一个详情页（推荐，rewrite 必需）。
    """
    out = {
        'target': url,
        'home_ok': None,          # True / False / None(无法判定)
        'http_code': 0,
        'undetermined': [],        # 无法判定的项，逐条写清楚
        'hits': {},                # 命中的特征 → 生成含义
        'nav_categories': [],      # [{'name','url'}] 首页导航里的分类
        'list_sample': [],         # 分类页前 6 条 [{'title','url','pic'}]
        'page_url_pattern': '',    # 由列表页推出的分页形态
        'detail_sample': None,     # 详情页：{'url','play_links':[],'episode_shape':''}
        'api_candidates': [],      # HTML 里出现过的接口路径
        'title': '',
    }
    base = url if url.startswith('http') else 'https://' + url
    html, code, err, note = _get(base, timeout)
    if note:
        out['undetermined_note'] = note
    out['http_code'] = code
    if err:
        out['home_ok'] = None
        out['undetermined'].append(f'首页抓取失败（{err}）——无法判定，不是「站点无特征」')
        return out
    out['home_ok'] = True

    m = re.search(r'<title[^>]*>(.*?)</title>', html, re.S | re.I)
    out['title'] = re.sub(r'\s+', ' ', m.group(1)).strip()[:80] if m else ''

    # ── 跳转壳跟随（最多 2 跳，防止环）──
    # 实测 mtosz.com：首页只返回 5556 字节的 "Redirecting..." 壳，
    # 拿这份 HTML 做侦察会得出「无特征、无分类、无列表」的错误结论 ——
    # **抓到了内容 ≠ 抓到了站点**。这是本次落地新发现的坑，记在 FEATURES 里。
    hops = []
    for _ in range(2):
        nxt = _meta_refresh(html) or _js_redirect(html)
        if not nxt:
            if _needs_cookie(html):
                ck = _cookie_from_js(html)
                if ck:
                    body, c3, e3, _n3 = _get(base, timeout, referer=base,
                                             extra_headers={'Cookie': ck})
                    if not e3 and body != html:
                        html, out['http_code'] = body, c3
                        out.setdefault('notes', []).append(
                            f'JS 挑战：已用脚本里的 cookie（{ck.split("=")[0]}=…）取到真实内容')
                        m = re.search(r'<title[^>]*>(.*?)</title>', html, re.S | re.I)
                        out['title'] = re.sub(r'\s+', ' ', m.group(1)).strip()[:80] if m else ''
                        continue
                out['undetermined'].append(
                    'JS 挑战型防爬（cookie 值依赖接口返回，静态取不到）——'
                    '真实内容未取到，生成时不得凭空写 categories/列表结构')
            break
        nxt = _abs(base, nxt)
        if nxt in hops:
            out['undetermined'].append(f'跳转环：{nxt}（已跳 {len(hops)} 次）')
            break
        hops.append(nxt)
        h2, c2, e2, n2 = _get(nxt, timeout, referer=base)
        if e2:
            out['undetermined'].append(f'跟跳转失败（{e2}）：{nxt}——真实站点内容未取到')
            break
        html, base, out['http_code'] = h2, nxt, c2
        out['redirected_to'] = nxt
        m = re.search(r'<title[^>]*>(.*?)</title>', html, re.S | re.I)
        out['title'] = re.sub(r'\s+', ' ', m.group(1)).strip()[:80] if m else ''
    if hops:
        out['hits']['followed_redirect'] = f'首页是跳转壳，已跟到 {hops[-1]}'

    for name, (pat, meaning) in FEATURES.items():
        if re.search(pat, html, re.I):
            out['hits'][name] = meaning

    # 导航分类（取 6~12 字的中文链接，排除「首页/更多」这类）
    skip = {'首页', '更多', '全部', '登录', '注册', '排行', '专题', 'APP', '下载'}
    seen = set()
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>([^<]{2,12})</a>', html):
        href, name = m.group(1), m.group(2).strip()
        if not name or name in skip or 'type/' not in href and 'vod/' not in href \
                and 'list/' not in href:
            continue
        u = _abs(base, href)
        if u in seen:
            continue
        seen.add(u)
        out['nav_categories'].append({'name': name, 'url': u})
        if len(out['nav_categories']) >= 12:
            break

    # HTML 里冒出来的接口路径（给 LLM 一个「去哪找 XHR」的线索，不当结论）
    for m in re.finditer(r'["\'](/(?:api|ajax|index\.php)[^"\']{0,60})["\']', html):
        p = m.group(1)
        if p not in out['api_candidates']:
            out['api_candidates'].append(p)
        if len(out['api_candidates']) >= 8:
            break

    if depth < 2:
        return out

    # ── 抓一个分类页 ──
    list_url = ''
    if out['nav_categories']:
        list_url = out['nav_categories'][0]['url']
    else:
        # 没有导航就试常见形态（只试一次，不猜到底）
        for cand in ('/index.php/vod/type/id/1.html', '/type/1.html', '/vodtype/1.html'):
            u = _abs(base, cand)
            body, c, e, _n = _get(u, timeout, referer=base)
            if not e and len(body) > 800:
                list_url = u
                break
    if not list_url:
        out['undetermined'].append('找不到分类页（导航无分类链接，常见形态也未命中）——'
                                   'categories 必须由人工确认，不许凭空写')
    else:
        body, c, e, _n = _get(list_url, timeout, referer=base)
        if e:
            out['undetermined'].append(f'分类页抓取失败（{e}）：{list_url}')
        else:
            out['list_url'] = list_url
            out['list_sample'] = _parse_list(body, list_url)
            # ★S231 移植③：固定正则取不到时走聚类路线（任意站点形态自适应）。
            #   只在固定路口空时才触发——两条路线都跑会重复抓取，且正则会互相污染。
            if not out['list_sample']:
                items2, dre = _parse_list_sniff(body, list_url)
                if items2:
                    out['list_sample'] = items2
                    out['detail_re'] = dre
                    out['hits']['list_via'] = f'sniff 聚类（固定正则空→反推 {dre[:60]}）'
                else:
                    out['undetermined'].append(
                        '列表样例为空：固定正则与 sniff 聚类均未认出详情页形态——'
                        '下游必须人工确认列表结构，不许凭记忆套模板')
            out['page_url_pattern'] = _page_pattern(body, list_url)
            out['hits'].setdefault('list_ok', f'分类页可抓，样例 {len(out["list_sample"])} 条')
            # ── 抓详情页 ──
            if out['list_sample']:
                durl = out['list_sample'][0]['url']
                dbody, dc, de, _n = _get(durl, timeout, referer=list_url)
                if de:
                    out['undetermined'].append(f'详情页抓取失败（{de}）：{durl}')
                else:
                    out['detail_sample'] = _parse_detail(dbody, durl)
    return out


def _parse_list(html, base):
    """从分类页取前 6 条（标题+链接+封面）。

    ★ 匹配集合必须**排除 /type/ 与 /list/**：那两条是分类目录，不是作品。
      第一版把 `type|vod|info` 全收，结果 6 条样例全是「动作片/喜剧片…」分类链接 —
      侦察报告于是把导航当成了片单样例，下游 LLM 会照着生成一个「片单=分类」的源。
      实测 lziapi：真实详情页路径是 `/index.php/vod/detail/id/N.html`。
    """
    items, seen = [], set()
    for m in re.finditer(
            r'<a[^>]+href="([^"]*(?:detail|/info/|/vod/detail|/v/)[^"]*)"[^>]*>(.*?)</a>',
            html, re.S | re.I):
        href, inner = m.group(1), m.group(2)
        low = href.lower()
        if '/type/' in low or '/list/' in low or '/show/' in low:
            continue          # 分类目录，不是作品
        u = _abs(base, href)
        if u in seen:
            continue
        t = re.search(r'title="([^"]{2,60})"', m.group(0))
        txt = re.sub(r'<[^>]+>', ' ', inner)
        title = (t.group(1) if t else txt).strip()
        title = re.sub(r'\s+', ' ', title)[:60]
        if len(title) < 2:
            continue
        pic = ''
        pm = re.search(r'(?:data-src|data-original|src)="([^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"',
                       inner, re.I)
        if pm:
            pic = _abs(base, pm.group(1))
        seen.add(u)
        items.append({'title': title, 'url': u, 'pic': pic})
        if len(items) >= 6:
            break
    return items


def _page_pattern(html, list_url):
    """从列表页的翻页链接推出分页形态。判不出来就返回 ''（不猜）。"""
    # 路径尾：/type/2/3  —— 注意第二段是分类 id，第三段才是页码
    for m in re.finditer(r'href="([^"]*?/(\d+)/(\d+)\.html)"', html):
        return f'路径尾页码：{m.group(1)}（倒数第一段是页码）'
    for m in re.finditer(r'href="([^"]*[?&](?:page|p|pg)=(\d+)[^"]*)"', html):
        return f'query 页码：{m.group(1)}'
    if re.search(r'loadMore|infinite|滚动加载', html):
        return '滚动/异步加载：需找接口，URL 拼法不适用'
    return ''


def _parse_detail(html, url):
    d = {'url': url, 'play_links': [], 'episode_shape': '', 'm3u8': [], 'iframes': []}
    for m in re.finditer(r'href="([^"]*(?:/bofang/|/play/|player)[^"]*)"', html):
        u = _abs(url, m.group(1))
        if u not in d['play_links']:
            d['play_links'].append(u)
    for m in re.finditer(r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', html):
        if m.group(1) not in d['m3u8']:
            d['m3u8'].append(m.group(1))
    for m in re.finditer(r'<iframe[^>]+src="([^"]+)"', html):
        d['iframes'].append(_abs(url, m.group(1)))
    # 三数字模板判据（r148）：第三个数全同、第二个数不同 = sid/nid 顺序
    tri = [re.search(r'/(\d+)-(\d+)-(\d+)\.html', u) for u in d['play_links']]
    tri = [x for x in tri if x]
    if tri:
        n1 = {x.group(2) for x in tri}
        n2 = {x.group(3) for x in tri}
        if len(n2) <= 1 and len(n1) > 1:
            d['episode_shape'] = ('三数字：第三个数全同、第二个数不同 → 第二个是 sid（线路），'
                                  '第三个是 nid（集）；单集多线路，集名统一「正片」')
        elif len(n1) <= 1 and len(n2) > 1:
            d['episode_shape'] = '三数字：第二个数全同、第三个数不同 → 第二个 sid，第三个 nid（多集）'
        else:
            d['episode_shape'] = f'三数字：sid {len(n1)} 种、nid {len(n2)} 种，分布不典型，需人工看'
    return d


def as_evidence_text(r):
    """把侦察结果转成给 LLM 的文本（外部内容一律由调用方包 untrusted）。"""
    L = [f'# 站点侦察：{r["target"]}',
         f'标题：{r.get("title") or "（空）"}',
         f'首页：{"可抓" if r["home_ok"] else "抓取失败/无法判定"}（HTTP {r["http_code"]}）']
    if r['hits']:
        L.append('命中的特征（→ 生成含义）：')
        for k, v in r['hits'].items():
            L.append(f'  · {k}：{v}')
    else:
        L.append('命中的特征：无（不代表简单，可能只是没踩到表里的形态）')
    if r['nav_categories']:
        L.append('导航分类（可直接作为 categories 种子，须再核对一遍）：')
        for c in r['nav_categories'][:10]:
            L.append(f'  · {c["name"]}  {c["url"]}')
    if r.get('page_url_pattern'):
        L.append(f'分页形态：{r["page_url_pattern"]}')
    if r['list_sample']:
        L.append('分类页样例：')
        for it in r['list_sample']:
            L.append(f'  · {it["title"]}  {it["url"]}')
    if r.get('detail_sample'):
        d = r['detail_sample']
        L.append(f'详情页样例：{d["url"]}')
        if d['episode_shape']:
            L.append(f'  选集形态：{d["episode_shape"]}')
        for u in d['play_links'][:6]:
            L.append(f'  播放链接：{u}')
        for u in d['m3u8'][:3]:
            L.append(f'  HTML 内 m3u8：{u}')
        for u in d['iframes'][:3]:
            L.append(f'  iframe：{u}')
    if r['api_candidates']:
        L.append('HTML 中出现过的接口路径（线索，未验证）：')
        for p in r['api_candidates']:
            L.append(f'  · {p}')
    if r['undetermined']:
        L.append('★ 无法判定项（必须在生成时如实标注，不许编）：')
        for u in r['undetermined']:
            L.append(f'  · {u}')
    return '\n'.join(L)


def selftest():
    """离线自检：只测**纯解析逻辑**，不联网。

    为什么不上网：沙箱出口时好时坏，联网测试会变成「今天绿明天红」，
    最后没人看。联网部分由 CLI 手动跑（`recon.py <url>`），
    这里只保证「给定 HTML → 结论」这段是确定的。
    """
    fails = []

    def chk(name, cond, detail=''):
        print(f'[{"OK " if cond else "FAIL"}] {name}' + ('' if cond else f'  {detail}'))
        if not cond:
            fails.append(name)

    # ① 列表解析必须排除 /type/ 与 /list/（第一版把分类目录当片单样例的坑）
    html = ('<a href="/index.php/vod/type/id/6.html">动作片</a>'
            '<a href="/index.php/vod/detail/id/1.html" title="某电影">某电影</a>'
            '<a href="/index.php/vod/detail/id/2.html"><img data-src="/u/2.jpg">某剧</a>')
    items = _parse_list(html, 'https://x.com/')
    chk('列表排除分类目录', len(items) == 2 and all('/detail/' in i['url'] for i in items),
        str(items))
    chk('列表取到 title 属性', items[0]['title'] == '某电影', items[0]['title'])
    chk('列表封面补全', items[1]['pic'] == 'https://x.com/u/2.jpg', items[1]['pic'])

    # ② 三数字模板判据（r148）：第三个数全同、第二个数不同 = sid/nid
    d = _parse_detail(
        '<a href="/bofang/9-1-1.html">a</a><a href="/bofang/9-2-1.html">b</a>'
        '<a href="/bofang/9-3-1.html">c</a>', 'https://x.com/v/9.html')
    chk('三数字：单集多线路 → 第二个是 sid',
        '第二个是 sid' in d['episode_shape'], d['episode_shape'])

    d2 = _parse_detail(
        '<a href="/bofang/9-1-1.html">a</a><a href="/bofang/9-1-2.html">b</a>'
        '<a href="/bofang/9-1-3.html">c</a>', 'https://x.com/v/9.html')
    chk('三数字：多集 → 第三个是 nid',
        '第三个 nid' in d2['episode_shape'], d2['episode_shape'])

    # ③ 分页形态三态
    chk('分页：路径尾', '路径尾' in _page_pattern(
        '<a href="/type/2/3.html">3</a>', 'https://x.com/type/2'))
    chk('分页：query', 'query' in _page_pattern(
        '<a href="/list?page=3">3</a>', 'https://x.com/list'))
    chk('分页：判不出返回空', _page_pattern('<p>无翻页</p>', 'https://x.com/') == '')

    # ④ 跳转壳识别
    chk('meta refresh 识别', _meta_refresh(
        '<meta http-equiv="refresh" content="0;url=/home">') == '/home')
    chk('location.replace 识别', _js_redirect(
        '<script>window.location.replace("/h")</script>') == '/h')
    chk('字面量 cookie 提取', _cookie_from_js(
        '<script>document.cookie=`abc=123;max-age=5`</script>') == 'abc=123',
        _cookie_from_js('<script>document.cookie=`abc=123;max-age=5`</script>'))
    chk('模板串 cookie 不瞎猜', _cookie_from_js(
        '<script>document.cookie=`k=${btoa(e)};max-age=5`</script>') == '')

    # ⑤ 抓不到时 home_ok=None，且 undetermined 有话说（M-R60）
    r = recon('http://127.0.0.1:1/', timeout=3)
    chk('不可达 → home_ok=None', r['home_ok'] is None, str(r['home_ok']))
    chk('不可达 → 有 undetermined 说明', bool(r['undetermined']), str(r['undetermined']))

    # ⑥ ★S231 移植③：五层详情正则生成（**五层各一个用例**，缺一层就会在某种站点形态上瞎套）
    cases = [
        ('①单段前缀', 'https://a.com/detail-217011.html', 'https://a.com/detail-217012.html', True),
        ('③MacCMS占位词', 'https://a.com/index.php/vod/detail/id/12345.html',
         'https://a.com/index.php/vod/detail/id/999.html', True),
        ('④短参数(/v/ID/ep)', 'https://a.com/v/1489032/229', 'https://a.com/v/777/229', True),
        ('⑤slug整段', 'https://a.com/mhkh/slug-name', 'https://a.com/mhkh/other-slug', True),
        ('⑤数字段整段替换', 'https://a.com/abc/12345.html', 'https://a.com/abc/67890.html', True),
        ('兜底只换末段数字', 'https://a.com/abc/12.34.5678', 'https://a.com/abc/12.34.9999', True),
    ]
    for label, s1, s2, want in cases:
        dre = build_detail_re(s1)
        got = bool(re.search(dre, s2)) if dre else False
        chk(f'五层正则 {label}：能匹配同模板另一条', got == want, f'dre={dre!r}')
    # 反向①：正则**不得**吃掉域名里的数字（兜底层注释的原始动机）
    dre = build_detail_re('https://site2024.com/abc/12345.html')
    chk('五层正则 反向：不含域名数字', '2024' not in dre, dre)
    chk('五层正则 反向：不含 host（换域正则仍可用）',
        'site2024' not in dre and 'com' not in dre.replace('\\', ''), dre)
    # 反向②：不同模板不得互匹配（否则聚类会把分类目录和详情页混成一组）
    dre_a = build_detail_re('https://a.com/index.php/vod/detail/id/12345.html')
    chk('五层正则 反向：不跨模板误匹配',
        not re.search(dre_a, 'https://a.com/v/1489032/229'), dre_a)

    # ⑦ sniff 聚类打分：分类目录（唯一 ID 少）不得胜过详情页
    html = ''.join(f'<a href="/index.php/vod/detail/id/{i}.html">片{i}</a>' for i in range(1, 9))
    html += ''.join(f'<a href="/index.php/vod/type/id/{i}.html">类{i}</a>' for i in range(1, 3))
    sample = sniff_detail_re(html, 'https://a.com/')
    chk('sniff 聚类：选中详情页而非分类目录', '/detail/id/' in sample, sample)
    _dre = build_detail_re(sample) if sample else ''
    chk('sniff 聚类：反推正则非空且覆盖同组全部条目',
        bool(_dre) and len(re.findall(_dre, html)) >= 6, repr(_dre))
    # 反向：全站只有 2 个 ID（唯一 ID < 3）→ 不参选，返回空（宁可不说，不瞎猜）
    chk('sniff 聚类 反向：唯一ID不足返回空',
        sniff_detail_re('<a href="/v/1.html">a</a><a href="/v/2.html">b</a>',
                        'https://a.com/') == '')
    # 反向：纯导航页（无 ID 段）返回空
    chk('sniff 聚类 反向：无ID页返回空',
        sniff_detail_re('<a href="/about">关于</a><a href="/contact">联系</a>',
                        'https://a.com/') == '')

    print()
    if fails:
        print(f'✗ {len(fails)} 项失败：{fails}')
        return 1
    print('✓ recon 离线自检全部通过')
    return 0


def main(argv=None):
    argv = list(argv if argv is not None else sys.argv[1:])
    if not argv or argv[0] in ('-h', '--help'):
        print('用法：recon.py <url> [--depth 1|2] [--json]')
        print('      recon.py --selftest     # 离线自检（不联网）')
        return 0
    if argv[0] == '--selftest':
        return selftest()
    url = argv[0]
    depth = 2
    if '--depth' in argv:
        depth = int(argv[argv.index('--depth') + 1])
    r = recon(url, depth=depth)
    if '--json' in argv:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    else:
        print(as_evidence_text(r))
    return 0 if r['home_ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
