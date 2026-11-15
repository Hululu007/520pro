#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""foundry · 熔铸司正门（平台可路由 skill 的执行入口）。

三个子命令：status / tools / selftest。
selftest 是施工纪律③「正反向验证通过才落地」的执行面：
  正向 = 真实骨架应绿；反向 = 造四类违例（缺 SKILL.md / 缺 manifest.json /
  名册非 26 / 描述五组缺项）必须各自翻红。造错用临时目录，不动真文件。
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
    print(f'  已验工具   : {ver}/26（W1 登记 / W2 补码转正，分离口径）')
    print('  当前阶段   : W1 骨架登记（W0 锚点 → W1 → W2 引擎上提 → W3 全量迁入 → W4 产出接入 → W5 收口）')
    print('  产出落点   : 🧬 520进化论/03·04·05 + 📦 产物归档/清单（见 artifacts.json）')
    return 0 if (ok and dok and nok) else 2


def cmd_tools():
    core = _load_core()
    schema = core.load_schema()
    for i, t in enumerate(schema['tools'], 1):
        s = t.get('inputSchema')
        print(f'  {i:2d}. {t["name"]:36s} '
              f'{"verified" if t.get("verified") else "W2 待补":10s} '
              f'schema={"有" if s else "—"}')
    return 0


def cmd_selftest():
    """正反向验证。造错用临时目录，不碰真文件。"""
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
    ck('lib 内核骨架 6 件齐全', lok, lmiss)
    nok, nmsg = core.names_ok(core.TOOLS_26)
    ck('名册 26 个与 tools/list 实测一致', nok, nmsg)
    try:
        d = core.load_schema()
        nok2, nmsg2 = core.names_ok([t['name'] for t in d['tools']])
        ck('tools_schema.json 26 条登记', nok2, nmsg2)
    except Exception as e:
        ck('tools_schema.json 可读', False, f'{type(e).__name__}: {e}')

    print('── 反向（四类造错必须各自翻红）──')
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

        # ⑤ 参数链坏填法
        ok5, _ = core.chain_ok({'class': 'class_name'})
        ck('JSON key 当类名 → 参数链判红', not ok5)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print(f'\n结果：{"全部通过（正向绿 / 反向全红）" if not fails else str(len(fails)) + " 项失败"}')
    return 0 if not fails else 2


def main(argv):
    cmd = (argv[1] if len(argv) > 1 else 'status').lstrip('-')
    fn = {'status': cmd_status, 'tools': cmd_tools,
          'selftest': cmd_selftest, 'self-test': cmd_selftest}.get(cmd)
    if fn is None:
        print(__doc__)
        print('用法：foundry.py status | tools | selftest')
        return 1
    return fn()


if __name__ == '__main__':
    try:
        sys.exit(main(sys.argv))
    except Exception as e:
        print(f'✗ 正门自身异常：{type(e).__name__}: {e}')
        sys.exit(1)
