#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""foundry-core · 熔铸司共享引擎内核（被 import，不注册、不路由）。

一手事实：jadx-headless-mcp 0.7.1 的 tools/list 实测 26 个工具
（/tmp/tools_list_实测.json，2026-11-15）。S233 §3.2 文档枚举 25 个，漏
get_main_application_classes_names —— 以实测为准，不以文档为准（B-06）。

参数链三条口径来自 23 个未用工具逐个 tools/call 的真调复盘：
  ① 方法名/类名取上一步真实返回（items[0]），拿 JSON key 当类名会报
     "see get_methods_of_class for the exact name"；
  ② 资源名用 jadx 解码后的名字，zip 原始路径一律报
     "resource is a link, not a file"；
  ③ 构造器写 <init> / <clinit>。
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA = os.path.join(HERE, 'tools_schema.json')
MANIFEST = os.path.join(os.path.dirname(HERE), 'manifest.json')

# 26 个工具名：tools/list 实测顺序（唯一真源，不复制文档枚举）
TOOLS_26 = [
    'status', 'load_apk', 'unload_apk', 'get_app_info', 'get_android_manifest',
    'get_main_activity_class', 'list_classes', 'get_main_application_classes_names',
    'get_class_source', 'get_class_summary', 'get_smali_of_class',
    'get_fields_of_class', 'get_inner_classes', 'resolve_class',
    'get_methods_of_class', 'get_method_by_name', 'get_method_body',
    'get_method_smali', 'search_method_by_name', 'search_classes_by_keyword',
    'get_xrefs_to_class', 'get_xrefs_to_method', 'get_xrefs_to_field',
    'get_strings', 'list_resource_files', 'get_resource_file',
]

# 参数链规则（真调实证，不是猜测）
CHAIN_RULES = {
    'from_previous_result': '参数一律取上一步真实返回；方法名用 items[0]',
    'class_name': '类名取 get_main_application_classes_names 的返回，不手敲',
    'method_name': '方法名取 get_methods_of_class 返回的首项（如 onCreate / $stable）',
    'resource_name': '资源名用 jadx 解码表（AndroidManifest.xml / resources.arsc），不用 zip 原始路径',
    'constructor': '构造器写 <init> / <clinit>',
}

# 反例：真调首轮 6 个假失败就是这些填法（/tmp/tools_call_实测.json）
BAD_ARGS = ('class_name', 'zip_entry_path', 'MainActivity.guess', 'raw_path')


def load_schema(path=None):
    """读 26 工具 schema。文件缺失/坏 JSON 抛异常，不折叠成空（B-02 三态）。"""
    with open(path or SCHEMA, encoding='utf-8') as f:
        d = json.load(f)
    if not isinstance(d, dict) or not isinstance(d.get('tools'), list):
        raise ValueError('tools_schema.json 结构失配：缺 tools 数组')
    return d


def skeleton_ok(root=None):
    """骨架齐全判定。返回 (ok, missing)。root 默认本 lib 目录。"""
    r = root or os.path.dirname(HERE)
    need = ['manifest.json', 'README.md', 'CHANGELOG.md',
            'scripts/core.py', 'scripts/tools_schema.json',
            'docs/TROUBLESHOOTING.md']
    missing = [f for f in need if not os.path.isfile(os.path.join(r, f))]
    return (not missing), missing


def names_ok(names):
    """名册判定：必须是 26 个、与实测集合完全相等、无重复。"""
    if not isinstance(names, list) or len(names) != 26:
        return False, f'工具数 {len(names) if isinstance(names, list) else "非 list"} ≠ 26'
    if len(set(names)) != 26:
        return False, '名册有重复'
    if set(names) != set(TOOLS_26):
        return False, '名册与 tools/list 实测集合不一致'
    return True, '26 个工具与实测一致'


def chain_ok(args):
    """参数链判定：出现已知坏填法即红。"""
    blob = json.dumps(args, ensure_ascii=False)
    for bad in BAD_ARGS:
        if bad in blob:
            return False, f'参数链含坏填法 {bad}（见 CHAIN_RULES）'
    return True, '参数链未命中已知坏填法'


def selftest():
    """正反向验证：正向真实状态绿；四类造错各自必须红。"""
    fails = []

    def ck(label, cond, detail=''):
        print(('  ✓ ' if cond else '  ✗ ') + label + ('' if cond else '  ← ' + str(detail)))
        if not cond:
            fails.append(label)

    print('── 正向（真实状态）──')
    ok, miss = skeleton_ok()
    ck('骨架齐全（6 件）', ok, miss)
    ok, msg = names_ok(TOOLS_26)
    ck('名册 26 个与实测一致', ok, msg)
    ok, msg = chain_ok({'method': 'onCreate', 'class': 'com.yunget.app.MainActivity'})
    ck('合法参数链通过', ok, msg)
    try:
        d = load_schema()
        names = [t['name'] for t in d['tools']]
        ok, msg = names_ok(names)
        ck('tools_schema.json 名册 26 个', ok, msg)
        n_ver = sum(1 for t in d['tools'] if t.get('verified'))
        print(f'  ℹ 已验 {n_ver}/26（W1 登记 / W2 补码转正，分离口径，不洗绿）')
    except Exception as e:
        ck('tools_schema.json 可读', False, f'{type(e).__name__}: {e}')

    print('── 反向（造错必红）──')
    ok, _ = skeleton_ok(root='/tmp/__foundry_no_such_dir__')
    ck('缺 manifest.json → 骨架判红', not ok)
    ok, _ = names_ok(TOOLS_26[:-1])
    ck('工具数 25 → 名册判红', not ok)
    ok, _ = names_ok(TOOLS_26 + ['get_xrefs_to_class'])
    ck('名册重复 → 判红', not ok)
    ok, _ = chain_ok({'class': 'class_name', 'res': 'zip_entry_path'})
    ck('JSON key / zip 路径 → 参数链判红', not ok)

    print(f'\n结果：{"全部通过" if not fails else str(len(fails)) + " 项失败"}')
    return 0 if not fails else 2


def main(argv):
    if '--selftest' in argv:
        return selftest()
    print(__doc__)
    print(f'工具名册 {len(TOOLS_26)} 个；schema 真源 {SCHEMA}')
    print('跑 --selftest 做正反向验证。')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as e:
        print(f'✗ 内核自身异常：{type(e).__name__}: {e}')
        sys.exit(1)
