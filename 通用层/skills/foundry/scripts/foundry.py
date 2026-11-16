#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""foundry · 熔铸司正门（平台可路由 skill 的执行入口）。

四个子命令：status / tools / surface / selftest。
selftest 是施工纪律③「正反向验证通过才落地」的执行面：
  正向 = 真实骨架应绿（W2 起含 schema_ok 26/26 转正判定；W3 起含
  surface_ok 63/63 能力面登记判定）；
  反向 = 造多类违例（缺 SKILL.md / 缺 manifest.json / 名册非 26 /
  描述五组缺项 / 参数链五种后接形态坏填法 / W3 能力面多形态造错）必须各自翻红。
  造错用临时目录 + 内存深拷贝，不动真文件。
"""
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(SKILL_DIR))

# lib 内核：用户级优先，回退仓内相对路径（本仓结构与 install.sh 装法一致）
_CORE_CANDS = [
    os.path.expanduser('~/.codebuddy/skills/foundry-core/scripts'),
    os.path.join(os.path.dirname(SKILL_DIR), 'foundry-core', 'scripts'),
]


def _load_core():
    for p in _CORE_CANDS:
        if os.path.isfile(os.path.join(p, 'core.py')):
            sys.path.insert(0, p)
            import core
            return core
    raise RuntimeError('foundry-core 内核未找到（应先跑 install.sh --user-skill）')


SKILL_FILES = ['SKILL.md', 'CHANGELOG.md', 'artifacts.json',
               'scripts/foundry.py', 'references/trigger-samples.md',
               'docs/TROUBLESHOOTING.md']


def _skill_ok(root=None):
    """技能骨架 6 件齐全判定。"""
    r = root or SKILL_DIR
    missing = [f for f in SKILL_FILES if not os.path.isfile(os.path.join(r, f))]
    return (not missing), missing


def _fm_of_text(text):
    """从**文档文本**里取 front matter 正文（参数语义单一：只收文本，不收路径）。

    初版写成 _front_matter(path) 却在 selftest 里传了文本，OSError: File name too long
    —— 参数既能是路径又能是文本就是歧义源，这里从机制上收成一种。
    """
    if not text.startswith('---'):
        return ''
    end = text.find('\n---', 3)
    return text[3:end] if end > 0 else ''


def _desc_ok(path):
    """C3 描述五组的最小复跑（与 skill_contract_check.py 同口径）。"""
    import re
    fm = _fm_of_text(open(path, encoding='utf-8').read())
    m = re.search(r'^description:\s*"(.*?)"\s*$', fm, re.M | re.S) \
        or re.search(r'^description:\s*(.*?)(?=^[^\s]|\Z)', fm, re.M | re.S)
    desc = (m.group(1) if m else '').strip()
    need = [('D1 must_use', r'当用户|触发词|适用于'),
            ('D2 capability', r'①|能力：|能力:'),
            ('D5 negative_boundary', r'不要用于|不适用于|【边界】|边界：|别用于'),
            ('C9 触发前置', r'^当用户')]
    bad = [n for n, p in need if not re.search(p, desc, re.M)]
    tools = re.search(r'^allowed-tools:\s*(.+)$', fm, re.M)
    if not tools or 'Bash' not in tools.group(1):
        bad.append('C11 缺 Bash')
    if tools and 'Task' in tools.group(1):
        bad.append('C11 含禁用 Task')
    return (not bad), bad


def cmd_status():
    core = _load_core()
    ok, miss = _skill_ok()
    dok, dbad = _desc_ok(os.path.join(SKILL_DIR, 'SKILL.md'))
    try:
        schema = core.load_schema()
        names = [t['name'] for t in schema['tools']]
        nok, nmsg = core.names_ok(names)
        ver = sum(1 for t in schema['tools'] if t.get('verified'))
    except Exception as e:
        names, nok, nmsg, ver = [], False, f'{type(e).__name__}: {e}', 0
    print('【foundry · 熔铸司状态】')
    print(f'  技能骨架   : {"齐备 6 件" if ok else "缺件 " + ", ".join(miss)}')
    print(f'  描述契约   : {"五组齐备" if dok else "缺 " + ", ".join(dbad)}')
    print(f'  工具名册   : {len(names)} 个 / {"与实测一致" if nok else nmsg}')
    print(f'  已验工具   : {ver}/26（W2 全量接线：inputSchema 实测登记 + 真调配方在册）')
    try:
        sok, smsg = core.schema_ok(schema)
        print(f'  转正判定   : {"26/26 齐备（schema+配方+参数链，无洗绿）" if sok else "红 → " + smsg}')
    except Exception as e:
        sok = False
        print(f'  转正判定   : 无法判定（{type(e).__name__}: {e}）')
    # W3：63 目录能力面清单（登记与补码转正分离）
    try:
        surf = core.load_surface()
        uok, umsg = core.surface_ok(surf)
        t = surf['source']['totals']
        print(f'  能力面清单 : {t["directories"]}/63 目录 / {t["files"]} 文件 / '
              f'{t["refs"]} refs / {t["exe_scripts"]} 脚本（W3 全量登记）')
        print(f'  能力面判定 : {"63/63 登记齐全且机检可回读" if uok else "红 → " + umsg}')
        nport = sum(1 for x in surf['directories'] if x.get('ported'))
        print(f'  补码转正   : {nport}/63（port_ok 正向判据背书：资产落点+签名+sha+六维，中性摆出）')
        try:
            assets = core.load_assets()
            pok, pmsg = core.port_ok(surf, assets)
            print(f'  补码资产层 : 63 域一手真源落仓（{"绿" if pok else "红 → " + pmsg}）'
                  f'｜foundry.py cap [id] 可检索')
        except Exception as e:
            print(f'  补码资产层 : 无法判定（{type(e).__name__}: {e}）')
        # W7-B：正文落点（防 ghost-port 空架子）
        try:
            bok, bmsg = core.body_ok()
            print(f'  正文落点   : {"绿 · " + bmsg if bok else "红 → " + bmsg}')
        except Exception as e:
            print(f'  正文落点   : 无法判定（{type(e).__name__}: {e}）')
    except Exception as e:
        uok = False
        print(f'  能力面判定 : 无法判定（{type(e).__name__}: {e}）')
    print('  引擎真源   : 通用层 foundry-core/scripts/jadx_engine.py（能力层 shellcrack 反向复用）')
    print('  当前阶段   : W7-B 正文落库做实（63 域 349 正文解仓 + body_ok 逐条对账 + ghost-port 防线；W0→W7-B）')
    print('  产出落点   : 🧬 520进化论/03·04·05 + 📦 产物归档/清单（见 artifacts.json）')
    return 0 if (ok and dok and nok and sok and uok) else 2


def cmd_tools():
    core = _load_core()
    schema = core.load_schema()
    for i, t in enumerate(schema['tools'], 1):
        s = t.get('inputSchema')
        req = (s or {}).get('required') or []
        rc = (t.get('call_recipe') or {}).get('args') or {}
        print(f'  {i:2d}. {t["name"]:36s} '
              f'{"verified" if t.get("verified") else "待补":10s} '
              f'schema={"有" if s else "—"}  req={",".join(req) or "∅"}  '
              f'args={",".join(rc.keys()) or "{}"}')
    ok, msg = core.schema_ok(schema)
    print(f'\n  转正判定：{"26/26 齐备" if ok else msg}')
    return 0 if ok else 2


def cmd_surface():
    """W3 机检可回读：列出 63 目录能力面清单（中性结构化登记，不搬运正文）。"""
    core = _load_core()
    d = core.load_surface()
    ok, msg = core.surface_ok(d)
    print('【foundry · 63 目录能力面清单】')
    print(f'  机检判定   : {"63/63 登记齐全" if ok else "红 → " + msg}')
    print(f'  {msg}')
    print(f'  一手来源   : {d["source"]["evidence"]}')
    print(f'  分离口径   : {d["separation"]["note"]}')
    print()
    print(f'  {"#":>2}  {"目录":42s} files refs exe  sec mech tool  fm')
    for i, x in enumerate(d['directories'], 1):
        print(f'  {i:2d}. {x["id"]:42s} {x["n_files"]:5d} {x["n_refs"]:4d} '
              f'{x["n_exe"]:3d} {x["n_sections"]:4d} {x["n_mech"]:4d} '
              f'{x["n_tool_tokens"]:4d}  {"Y" if x["has_fm"] else "-"}')
    t = d['source']['totals']
    print(f'\n  合计: {t["directories"]} 目录 / {t["files"]} 文件 / {t["refs"]} refs / '
          f'{t["exe_scripts"]} 脚本 / {t["sections"]} 章节 / {t["mech"]} 机制点 / '
          f'{t["tool_tokens"]} 工具令牌')
    print(f'  补码转正: {sum(1 for x in d["directories"] if x.get("ported"))}/63')
    return 0 if ok else 2


def cmd_cap(argv=None):
    """W6 补码检索：按 id 回读某能力域的一手落点；无参列出可转正清单。"""
    argv = argv or sys.argv
    core = _load_core()
    assets = core.load_assets()
    surf = core.load_surface()
    smap = {x['id']: x for x in surf['directories']}
    by_id = {a['id']: a for a in assets['assets']}
    pok, pmsg = core.port_ok(surf, assets)
    want = argv[2] if len(argv) > 2 else None
    if want:
        # W8-A 第二工具集检索：REA 24 名册 / 65 外部工具 token 弱明细
        if want in ('rea', 'rea-tools', 'rea_tools'):
            d = core.load_rea()
            ok, msg = core.rea_ok(d)
            print(f'【REA 工具名册 · {d["count"]} 工具】({"绿" if ok else "红 → " + msg}）')
            print(f'  来源   : {d["origin"]}')
            print(f'  sha256 : {d["sha256_source"][:16]}…')
            for i, t in enumerate(d['tools'], 1):
                print(f'  {i:2d}. {t}')
            return 0 if ok else 2
        if want in ('tokens', 'tool-tokens', 'tool_tokens'):
            d = core.load_tokens()
            ok, msg = core.tokens_ok(d)
            print(f'【外部工具 token 弱明细 · {d["count"]} 个】({"绿" if ok else "红 → " + msg}）')
            print(f'  来源   : {d["origin"]}')
            print(f'  口径   : {d["note"]}')
            for x in d['tokens']:
                dom = ','.join(x['domains'][:4])
                print(f'  - {x["name"]:20s} 域={dom}')
            return 0 if ok else 2
        if want in ('runtimes', 'runtime-assets', 'runtime_assets'):
            d = core.load_runtimes()
            ok, msg = core.runtimes_ok(d)
            print(f'【运行时二进制实体 · {d["count"]} 文件 / {d["total_bytes"] // 1048576}MB】'
                  f'({"绿" if ok else "红 → " + msg}）')
            print(f'  来源   : {d["source"][:120]}')
            for x in d['files']:
                print(f'  - {x["path"]:52s} {x["bytes"]:>10d}B  sha={x["sha256"][:10]}')
            return 0 if ok else 2
        a = by_id.get(want)
        if not a:
            print(f'  未找到能力域 {want!r}（可用 foundry.py cap 列全清单）')
            return 1
        s = smap.get(want, {})
        print(f'【能力域 · {want}】')
        print(f'  补码状态   : {"ported（一手真源落仓 + 事实自洽转正）" if s.get("ported") else "registered（仅登记）"}')
        print(f'  定位       : {a.get("desc", "")[:180]}')
        print(f'  计数       : {a["n_files"]} 文件 / {a["n_refs"]} refs / {a["n_exe"]} 脚本 / '
              f'{a["n_sections"]} 章节 / {a["n_mech"]} 机制点')
        sigs = a.get('script_signatures') or []
        if sigs:
            print('  脚本签名   :（签名层登记）')
            for sg in sigs:
                defs = ','.join(sg.get('defs', [])) or '—'
                print(f'    - {sg.get("file", "?"):46s} {sg.get("bytes", 0):6d}B  defs={defs}')
        # W7-B：正文回读——签名对应的正文文件是否真实在册
        try:
            mf = json.load(open(core.V4_MANIFEST, encoding='utf-8'))
            hit = [r for r in mf['files'] if r['path'].startswith(want + '/')]
            if hit:
                print(f'  正文落点   : {len(hit)} 个文件在册（v4_skills/{want}/）')
                for r in hit[:8]:
                    tag = '正文' if r['path'].endswith(core._BODY_SCRIPT_EXT) else '文档'
                    print(f'    - {r["path"]:52s} {r["bytes"]:6d}B  {tag}  sha={r["sha256"][:10]}')
                if len(hit) > 8:
                    print(f'    … 另 {len(hit) - 8} 个（见 v4_skills_manifest.json）')
            else:
                print('  正文落点   : 该域无正文落点')
        except Exception as e:
            print(f'  正文落点   : 无法判定（{type(e).__name__}: {e}）')
        print(f'  一手真源   : {assets["origin"]}')
        return 0
    # 无参：清单
    print(f'【foundry · 补码资产清单（{len(assets["assets"])} 域）】')
    print(f'  补码判定   : {"绿 · " + pmsg if pok else "红 → " + pmsg}')
    print('  摆出口径   : 中性摆出，63 域一视同仁，不分级、不裁剪（边界由用户拍板）')
    nport = sum(1 for x in surf['directories'] if x.get('ported'))
    print(f'  已转正     : {nport}/63')
    print(f'  {"#":>2}  {"目录":34s} {"状态":9s} 文件 refs 脚本 签名')
    for i, a in enumerate(assets['assets'], 1):
        s = smap.get(a['id'], {})
        print(f'  {i:2d}. {a["id"]:34s} '
              f'{"ported" if s.get("ported") else "reg":9s} '
              f'{a["n_files"]:3d} {a["n_refs"]:4d} {a["n_exe"]:3d} {len(a.get("script_signatures",[])):3d}')
    print('\n  用法：foundry.py cap <id> 查看单域一手落点')
    return 0 if pok else 2


def cmd_selftest():
    """正反向验证。造错用临时目录 + 内存深拷贝，不碰真文件。"""
    core = _load_core()
    fails = []

    def ck(label, cond, detail=''):
        print(('  ✓ ' if cond else '  ✗ ') + label + ('' if cond else '  ← ' + str(detail)))
        if not cond:
            fails.append(label)

    print('── 正向（真实骨架应绿）──')
    ok, miss = _skill_ok()
    ck('技能骨架 6 件齐全', ok, miss)
    dok, dbad = _desc_ok(os.path.join(SKILL_DIR, 'SKILL.md'))
    ck('描述五组 + C9 + C11 齐备', dok, dbad)
    lok, lmiss = core.skeleton_ok()
    ck('lib 内核骨架（含 jadx_engine.py + capability_surface.json）齐全', lok, lmiss)
    nok, nmsg = core.names_ok(core.TOOLS_26)
    ck('名册 26 个与 tools/list 实测一致', nok, nmsg)
    # W2：真实配方含 class_name 键（病15 修正后必须判绿，W1 会误判）
    cok, cmsg = core.chain_ok({'class_name': 'com.yunget.app.MainActivity',
                               'method_name': 'onCreate'})
    ck('真实配方（含 class_name 键）参数链通过', cok, cmsg)
    try:
        d = core.load_schema()
        nok2, nmsg2 = core.names_ok([t['name'] for t in d['tools']])
        ck('tools_schema.json 26 条登记', nok2, nmsg2)
        sok, smsg = core.schema_ok(d)
        ck('W2 转正：26 工具 schema+配方+参数链齐备', sok, smsg)
    except Exception as e:
        ck('tools_schema.json 可读 / 转正', False, f'{type(e).__name__}: {e}')
    # W3：63 目录能力面清单转正判定（登记齐全 + 机检可回读）
    try:
        surf = core.load_surface()
        uok, umsg = core.surface_ok(surf)
        ck('W3 能力面清单 63/63 登记齐全且机检可回读', uok, umsg)
        ck('W3 名册 63 个与一手深读一致', len(core.CAPABILITY_63) == 63
           and set(core.CAPABILITY_63) == set(x['id'] for x in surf['directories']))
    except Exception as e:
        ck('capability_surface.json 可读 / 转正', False, f'{type(e).__name__}: {e}')
    # W6：补码资产层 + port_ok 正向判据（中性摆出，无价值分级）
    try:
        assets = core.load_assets()
        surf = core.load_surface()
        ck('W6 补码资产层 63 域齐备', len(assets['assets']) == 63)
        ck('W6 一手真源 sha 在册（脱离 /tmp 临时区）',
           len(assets.get('source_sha256', '')) == 64)
        ck('W6 中性摆出：无 content_tier/分级字段',
           all('content_tier' not in a and 'tier' not in a for a in assets['assets']))
        pok, pmsg = core.port_ok(surf, assets)
        ck('W6 port_ok 正向：63 域全量转正有资产落点背书', pok, pmsg)
        ck('W6 骨架含资产层两件', core.skeleton_ok()[0])
    except Exception as e:
        ck('补码资产层可读 / 转正', False, f'{type(e).__name__}: {e}')

    print('── 反向（多类造错必须各自翻红）──')
    tmp = tempfile.mkdtemp(prefix='foundry-selftest-')
    try:
        # ① 技能缺 SKILL.md
        d1 = os.path.join(tmp, 'skill')
        os.makedirs(d1)
        for f in SKILL_FILES[1:]:
            p = os.path.join(d1, f)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, 'w').write('x')
        ok1, _ = _skill_ok(root=d1)
        ck('缺 SKILL.md → 技能骨架判红', not ok1)

        # ② lib 缺 manifest.json
        d2 = os.path.join(tmp, 'lib')
        os.makedirs(os.path.join(d2, 'scripts'))
        open(os.path.join(d2, 'scripts', 'core.py'), 'w').write('x')
        open(os.path.join(d2, 'scripts', 'tools_schema.json'), 'w').write('{}')
        ok2, _ = core.skeleton_ok(root=d2)
        ck('缺 manifest.json → lib 骨架判红', not ok2)

        # ③ 名册非 26
        ok3, _ = core.names_ok(core.TOOLS_26[:-1])
        ck('工具数 25 → 名册判红', not ok3)

        # ④ 描述五组缺项：删光**全部**负边界词（只删一处仍留着别的「不要用于」= 造错不彻底）
        import re as _re
        s = _fm_of_text(open(os.path.join(SKILL_DIR, 'SKILL.md'), encoding='utf-8').read())
        bad_fm = _re.sub(r'不要用于：[^。]*。', '', s)
        ck('造错前提：负边界词已全部删净', '不要用于' not in bad_fm and '不适用于' not in bad_fm)
        p4 = os.path.join(tmp, 'bad.md')
        open(p4, 'w', encoding='utf-8').write('---\n' + bad_fm + '\n---\n')
        ok4, bad4 = _desc_ok(p4)
        ck('删负边界 → 描述契约判红', not ok4, bad4)

        # ⑤ 参数链坏填法：五种后接形态各自判红（病15「只认精确锚点会全漏」）
        bad_forms = [
            ('JSON key 当类名', {'class': 'class_name'}),
            ('JSON key 当方法名', {'class_name': 'com.yunget.app.MainActivity',
                                 'method_name': 'class_name'}),
            ('猜类名', {'class_name': 'MainActivity.guess'}),
            ('占位符当资源名', {'name': 'zip_entry_path'}),
            ('zip 原始路径', {'name': 'META-INF/com/android/build/gradle/app-metadata.properties'}),
        ]
        for nm, a in bad_forms:
            o, _ = core.chain_ok(a)
            ck(f'参数链判红·{nm}', not o)

        # ⑥ W2 转正判据造错：verified 无 evidence（洗绿）/ inputSchema=null 必须翻红
        try:
            import copy
            _d = copy.deepcopy(core.load_schema())
            _d['tools'][0]['call_recipe'].pop('evidence', None)
            ck('洗绿造错：verified 无 evidence → 转正判红', not core.schema_ok(_d)[0])
            _d2 = copy.deepcopy(core.load_schema())
            _d2['tools'][0]['inputSchema'] = None
            ck('W1 残留：inputSchema=null → 转正判红', not core.schema_ok(_d2)[0])
        except Exception as e:
            ck('schema 造错用例可读', False, f'{type(e).__name__}: {e}')

        # ⑦ W3 能力面多形态造错：只认单个 count 布尔会全漏，逐层判据各自翻红
        try:
            import copy
            smk = lambda: copy.deepcopy(core.load_surface())  # noqa: E731
            u1 = smk(); u1['directories'] = u1['directories'][:-1]
            ck('能力面判红·少一个目录', not core.surface_ok(u1)[0])
            # W6：63 域已全量真实转正，旧「翻 ported=true 即冒充」前提失效；
            # 改成名册外 id 翻正，防冒充语义在新态下仍成立。
            u2 = smk(); u2['directories'][7]['id'] = 'ghost-port'
            ck('能力面判红·名册外 id 冒充转正', not core.surface_ok(u2)[0])
            u3 = smk()
            u3['directories'][0]['n_files'] -= 1
            u3['source']['totals']['files'] -= 1
            ck('能力面判红·清单+totals 同步洗绿（独立硬锚）', not core.surface_ok(u3)[0])
            u4 = smk(); u4['directories'][0]['id'] = 'ghost-dir'
            ck('能力面判红·目录名不在名册', not core.surface_ok(u4)[0])
            u5 = smk(); u5['directories'][3]['n_files'] = '349'
            ck('能力面判红·计数类型错', not core.surface_ok(u5)[0])
            ck('能力面判红·整表非 dict', not core.surface_ok([1, 2, 3])[0])
        except Exception as e:
            ck('能力面造错用例可读', False, f'{type(e).__name__}: {e}')

        # ⑧ W6 补码判据反向（中性：只测事实自洽，不涉及分级/敏感判断）
        try:
            import copy
            assets = core.load_assets()
            surf = core.load_surface()
            na = copy.deepcopy(assets); na['assets'] = na['assets'][:-1]
            ck('补码判红·资产落点缺失', not core.port_ok(surf, na)[0])
            fs = copy.deepcopy(assets); fs['source_sha256'] = 'f' * 64
            ck('补码判红·真源 sha 失配', not core.port_ok(surf, fs)[0])
            ns = copy.deepcopy(assets)
            for a in ns['assets']:
                if a['n_exe'] > 0:
                    a['script_signatures'] = []
                    break
            ck('补码判红·脚本签名缺失', not core.port_ok(surf, ns)[0])
        except Exception as e:
            ck('补码判据造错用例可读', False, f'{type(e).__name__}: {e}')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print(f'\n结果：{"全部通过（正向绿 / 反向全红）" if not fails else str(len(fails)) + " 项失败"}')
    return 0 if not fails else 2


def main(argv):
    cmd = (argv[1] if len(argv) > 1 else 'status').lstrip('-')
    fn = {'status': cmd_status, 'tools': cmd_tools, 'surface': cmd_surface,
          'cap': cmd_cap, 'selftest': cmd_selftest, 'self-test': cmd_selftest}.get(cmd)
    if fn is None:
        print(__doc__)
        print('用法：foundry.py status | tools | surface | cap [id] | selftest')
        return 1
    return fn()


if __name__ == '__main__':
    try:
        sys.exit(main(sys.argv))
    except Exception as e:
        print(f'✗ 正门自身异常：{type(e).__name__}: {e}')
        sys.exit(1)
