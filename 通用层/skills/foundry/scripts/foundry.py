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
        print(f'  补码转正   : {nport}/63（登记≠转正，逐目录补码由用户拍板）')
    except Exception as e:
        uok = False
        print(f'  能力面判定 : 无法判定（{type(e).__name__}: {e}）')
    print('  引擎真源   : 通用层 foundry-core/scripts/jadx_engine.py（能力层 shellcrack 反向复用）')
    print('  当前阶段   : W3 63 目录能力面全量迁入完成（W0→W1→W2→W3 → W4 产出接入 → W5 收口）')
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
            u2 = smk(); u2['directories'][7]['ported'] = True
            ck('能力面判红·冒充补码转正', not core.surface_ok(u2)[0])
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
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print(f'\n结果：{"全部通过（正向绿 / 反向全红）" if not fails else str(len(fails)) + " 项失败"}')
    return 0 if not fails else 2


def main(argv):
    cmd = (argv[1] if len(argv) > 1 else 'status').lstrip('-')
    fn = {'status': cmd_status, 'tools': cmd_tools, 'surface': cmd_surface,
          'selftest': cmd_selftest, 'self-test': cmd_selftest}.get(cmd)
    if fn is None:
        print(__doc__)
        print('用法：foundry.py status | tools | surface | selftest')
        return 1
    return fn()


if __name__ == '__main__':
    try:
        sys.exit(main(sys.argv))
    except Exception as e:
        print(f'✗ 正门自身异常：{type(e).__name__}: {e}')
        sys.exit(1)
