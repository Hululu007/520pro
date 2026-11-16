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

W2（v0.8.76）：26 工具 inputSchema 与真调配方全部落盘，verified 26/26。
本轮修正一处病15 复发：chain_ok 旧版用 `'class_name' in json.dumps(args)` 判坏，
而 class_name 是 26 工具合法必填键名 —— 判据识别范围（键名字符串）≠ 对象范围
（参数值），会把所有真实配方误判。改为查参数**值**，并补五种后接形态单测。

W3（v0.8.76 增量）：63 目录能力面清单 capability_surface.json 全量登记
（349 文件 / 196 refs / 38 脚本 / 1458 章节，MilkCode / breakerKit 一手深读）。
中性结构化登记：只登记目录 id + 聚合计数 + 脚本名，不搬运技能正文、不裁剪、
不做价值判断。登记与补码转正分离（registered / ported 两态）。新增 surface_ok
判据：病15「识别范围 = 对象范围」——不看单个 count 布尔，逐目录验字段 +
六维求和对账 + 名册比对 + 分离态 + 独立硬锚防「清单与 totals 一起改」的洗绿。
"""
import json
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA = os.path.join(HERE, 'tools_schema.json')
SURFACE = os.path.join(HERE, 'capability_surface.json')
MANIFEST = os.path.join(os.path.dirname(HERE), 'manifest.json')
# W6 补码资产层：一手真源从 /tmp 迁入仓内，脱离临时区
ASSETS_DIR = os.path.join(os.path.dirname(HERE), 'assets', 'capability_63')
ASSET_FILE = os.path.join(ASSETS_DIR, 'capability_assets.json')
DEEP_FILE = os.path.join(ASSETS_DIR, 'source_deep.json')
# W7 阶段B：63 域脚本正文落点（从本机 MilkCode APK 的 assets/breaker/v4-skills
# 全量解出）。manifest 记录每条正文的 bytes/sha256，判据据此对账磁盘真实文件，
# 堵住「ported=true 但正文文件不在册」的 ghost-port 空架子盲区。
V4_SKILLS_DIR = os.path.join(ASSETS_DIR, 'v4_skills')
V4_MANIFEST = os.path.join(ASSETS_DIR, 'v4_skills_manifest.json')
BODY_ANCHORS = {'domains': 63, 'files': 349, 'scripts': 38}
_BODY_SCRIPT_EXT = ('.py', '.ps1', '.sh', '.js')
# W8-A：REA 24 工具名册（第二工具集）+ 65 外部工具 token 弱明细
REA_FILE = os.path.join(ASSETS_DIR, 'rea_tools.json')
TOKENS_FILE = os.path.join(ASSETS_DIR, 'tool_tokens.json')
REA_COUNT = 24          # rea-preset.json 实测工具数（唯一真源）
TOKENS_COUNT = 65       # source_deep.json 63 域 tool_tokens 去重实测数
# W8-D：frida-server + linux-tools arm64 上游只读二进制实体（保真归档，非本仓运行时）
RUNTIME_DIR = os.path.join(ASSETS_DIR, 'runtime_assets')
RUNTIME_MANIFEST = os.path.join(ASSETS_DIR, 'runtime_assets_manifest.json')
RUNTIME_COUNT = 8       # 同一 APK 解出的实体文件数（唯一真源，manifest 自洽校验）

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

# 63 目录名册：/tmp/milk63_deep.json 一手深读顺序（唯一真源，不复制别处枚举）
# 中性技术资产标识，仅作能力面核对锚，不含也不搬运任何技能正文内容。
CAPABILITY_63 = (
    'adult-fiction', 'anti-cheat', 'api-security', 'apk-reverse', 'attack-chain', 'binary-analysis',
    'binary-diff', 'border-crossing', 'crack-keygen', 'dma-attack', 'dotnet-reverse', 'dsl-vm-reverse',
    'dynamic-instrumentation', 'edr-bypass-re', 'finance-movement', 'firmware-pentest', 'full-crack', 'full-pentest',
    'game-cheat', 'game-engine', 'game-hacking', 'graphics-api', 'ida-reverse', 'identity-docs',
    'js-reverse', 'l-gameassist', 'l-license', 'l-reverse', 'l-webrecon', 'mobile-competitive-game-security',
    'mobile-reverse', 'mobile-security', 'network-pentest', 'patch-diff-exploit', 'pentest-tools', 'phishing-kit',
    'pipeline-renderer', 'politics-history', 'protocol-reverse-engineering', 'protocol-reversing', 'pwn-chain', 'radare2',
    'rei-fallback', 'research-rigor', 'reverse-engineering', 'reverse-engineering-api', 'seagull-anticheat', 'seagull-auto-ops',
    'seagull-evasion', 'seagull-exploit', 'seagull-game-hack', 'seagull-game-redteam', 'seagull-game-security', 'seagull-lab',
    'seagull-license-security', 'seagull-malware', 'seagull-mature-content', 'seagull-memory', 'seagull-pentest', 'seagull-reverse',
    'seagull-social-eng', 'seagull-unlimited', 'windows-kernel',
)

# 能力面独立硬锚（Next 锚点验收口径 63/349/196/38）：
# 与清单 source.totals 分离固化，防「清单逐条求和 + totals 同步改小」的洗绿。
SURFACE_ANCHORS = {'directories': 63, 'files': 349, 'refs': 196, 'exe_scripts': 38}

# 参数链规则（真调实证，不是猜测）
CHAIN_RULES = {
    'from_previous_result': '参数一律取上一步真实返回；方法名用 items[0]',
    'class_name': '类名取 get_main_application_classes_names 的返回，不手敲',
    'method_name': '方法名取 get_methods_of_class 返回的首项（如 onCreate / $stable）',
    'resource_name': '资源名用 jadx 解码表（AndroidManifest.xml / resources.arsc），不用 zip 原始路径',
    'constructor': '构造器写 <init> / <clinit>',
}

# 坏填法：真调首轮 6 个假失败就是把这些**字面量 / 路径**填进了参数「值」
# （/tmp/tools_call_实测.json / 补调）。注意这是「值」的黑名单，不是「键名」——
# class_name / method_name / field_name / name 都是 inputSchema 的合法参数名。
BAD_VALUE_LITERALS = (
    'class_name', 'method_name', 'field_name', 'search_term',  # JSON key 当值
    'zip_entry_path', 'raw_path', 'MainActivity.guess',        # 占位符 / 猜类名
)
# zip 归档原始路径（非 jadx 解码资源名）：get_resource_file 用这类值一律
# "resource is a link, not a file"。解码名是 AndroidManifest.xml / resources.arsc / res/*。
ZIP_RAW_PREFIXES = ('META-INF/', 'classes.dex', 'classes2.dex', 'lib/',
                    'assets/', 'DebugProbesKt.bin')


def load_schema(path=None):
    """读 26 工具 schema。文件缺失/坏 JSON 抛异常，不折叠成空（B-02 三态）。"""
    with open(path or SCHEMA, encoding='utf-8') as f:
        d = json.load(f)
    if not isinstance(d, dict) or not isinstance(d.get('tools'), list):
        raise ValueError('tools_schema.json 结构失配：缺 tools 数组')
    return d


def load_surface(path=None):
    """读 63 目录能力面清单。文件缺失/坏 JSON 抛异常，不折叠成空（B-02 三态）。"""
    with open(path or SURFACE, encoding='utf-8') as f:
        d = json.load(f)
    if not isinstance(d, dict) or not isinstance(d.get('directories'), list):
        raise ValueError('capability_surface.json 结构失配：缺 directories 数组')
    return d


def load_assets(path=None):
    """读 W6 补码资产层清单。缺失/坏结构抛异常，不折叠成空（B-02）。"""
    with open(path or ASSET_FILE, encoding='utf-8') as f:
        d = json.load(f)
    if not isinstance(d, dict) or not isinstance(d.get('assets'), list):
        raise ValueError('capability_assets.json 结构失配：缺 assets 数组')
    return d


def load_rea(path=None):
    """读 W8-A REA 工具名册。缺失/坏结构抛异常，不折叠成空（B-02）。"""
    with open(path or REA_FILE, encoding='utf-8') as f:
        d = json.load(f)
    if not isinstance(d, dict) or not isinstance(d.get('tools'), list):
        raise ValueError('rea_tools.json 结构失配：缺 tools 数组')
    return d


def load_tokens(path=None):
    """读 W8-A 外部工具 token 弱明细。缺失/坏结构抛异常（B-02）。"""
    with open(path or TOKENS_FILE, encoding='utf-8') as f:
        d = json.load(f)
    if not isinstance(d, dict) or not isinstance(d.get('tokens'), list):
        raise ValueError('tool_tokens.json 结构失配：缺 tokens 数组')
    return d


def load_runtimes(path=None):
    """读 W8-D 运行时二进制实体清单。缺失/坏结构抛异常（B-02）。"""
    with open(path or RUNTIME_MANIFEST, encoding='utf-8') as f:
        d = json.load(f)
    if not isinstance(d, dict) or not isinstance(d.get('files'), list):
        raise ValueError('runtime_assets_manifest.json 结构失配：缺 files 数组')
    return d


def rea_ok(d=None):
    """REA 24 工具名册判据：count 自洽 + 24 个无重复 + 与 26 工具集非同一套。
    返回 (ok, msg)。病15：识别范围=对象范围——只验名册自洽，不虚构版本/用途。"""
    d = d if d is not None else load_rea()
    tools = d.get('tools')
    if not isinstance(tools, list):
        return False, 'tools 非数组'
    if d.get('count') != len(tools):
        return False, f'count {d.get("count")} ≠ tools 实际 {len(tools)}'
    if len(tools) != REA_COUNT:
        return False, f'工具数 {len(tools)} ≠ 实测 {REA_COUNT}'
    if len(set(tools)) != len(tools):
        return False, '名册有重复'
    if set(tools) == set(TOOLS_26):
        return False, 'REA 名册与 26 工具集相同（应为不同工具集）'
    if not d.get('sha256_source'):
        return False, '缺来源 sha256（无法证明原样解出）'
    return True, f'{len(tools)} 个 REA 工具自洽（与 26 工具集不同）'


def tokens_ok(d=None):
    """外部工具 token 弱明细判据：count 自洽 + 65 个 + 五项目标工具命中。
    只验弱明细（name/domains/evidence），不虚构版本号。返回 (ok, msg)。"""
    d = d if d is not None else load_tokens()
    toks = d.get('tokens')
    if not isinstance(toks, list):
        return False, 'tokens 非数组'
    if d.get('count') != len(toks):
        return False, f'count {d.get("count")} ≠ tokens 实际 {len(toks)}'
    if len(toks) != TOKENS_COUNT:
        return False, f'token 数 {len(toks)} ≠ 实测 {TOKENS_COUNT}'
    names = {t.get('name') for t in toks if isinstance(t, dict)}
    if len(names) != len(toks):
        return False, 'token 有重复'
    for target in ('idalib-mcp', 'nmap', 'nuclei', 'burpsuite', 'frida-ps'):
        if target not in names:
            return False, f'缺目标工具 {target}'
    return True, f'{len(toks)} 个 token 自洽（五项目标工具命中）'


def runtimes_ok(d=None, assets_dir=None):
    """W8-D 运行时实体判据（病15：识别范围=对象范围）——验磁盘实体本身，非只看清单。
      ① manifest 结构完整（count == len(files) == 8 硬锚）
      ② count/total_bytes 与 files 自洽
      ③ 每条 path 无越界（不含 .. / 绝对路径），实体真实存在、非空
      ④ 逐条 bytes/sha256 与 manifest 记录一致（篡改/掉包即红）
      ⑤ 来源标注在册（证明同源 APK 原样解出，非凭空生成）
    返回 (ok, msg)。不执行任何二进制（arm64 实体在本机 amd64 仅保真归档）。
    """
    d = d if d is not None else load_runtimes()
    root = assets_dir or RUNTIME_DIR
    files = d.get('files')
    if not isinstance(files, list):
        return False, 'files 非数组'
    if d.get('count') != len(files):
        return False, f'count {d.get("count")} ≠ files 实际 {len(files)}'
    if len(files) != RUNTIME_COUNT:
        return False, f'实体数 {len(files)} ≠ 实测 {RUNTIME_COUNT}'
    total = 0
    for rec in files:
        if not isinstance(rec, dict) or 'path' not in rec:
            return False, '实体条目缺 path'
        rel = rec['path']
        if os.path.isabs(rel) or '..' in rel.split('/'):
            return False, f'实体 path 越界：{rel}'
        p = os.path.join(root, *rel.split('/'))
        if not os.path.isfile(p):
            return False, f'实体文件缺失：{rel}'
        raw = open(p, 'rb').read()
        if not raw:
            return False, f'实体文件空：{rel}'
        if len(raw) != rec.get('bytes'):
            return False, f'实体 bytes 失配：{rel}（{len(raw)}≠{rec.get("bytes")}）'
        if hashlib.sha256(raw).hexdigest() != rec.get('sha256'):
            return False, f'实体 sha256 失配：{rel}（可能篡改/掉包）'
        if not rec.get('source'):
            return False, f'实体缺来源标注：{rel}'
        total += len(raw)
    if d.get('total_bytes') != total:
        return False, f'total_bytes {d.get("total_bytes")} ≠ 逐条求和 {total}'
    return True, (f'{len(files)}/{RUNTIME_COUNT} 运行时实体落点在册（bytes/sha256 逐条对账一致，'
                  f'{total / 1048576:.1f}MB，未加载执行）')


def port_ok(surface_d, assets=None, deep_path=None):
    """W6 补码转正正向判据（病15：识别范围 = 对象范围）。

    中性摆出、不预设价值判断：63 目录一视同仁，判据只看事实自洽，
    不看任何「分级 / 敏感 / 该不该激活」的人为判断。ported=true 逐条须满足：
      ① 资产层有同 id 条目（一手落点在册）
      ② 脚本签名数 == n_exe（有脚本签名齐备六字段；无脚本则为空——纯事实）
      ③ 一手真源 sha256 与资产清单记录一致（防真源被篡改/掉包）
      ④ 资产六维计数与 capability_surface 逐条自洽（防两账脱钩）
    返回 (ok, msg)。不基于「有 ported 就红」的反向旧判据。
    """
    if not isinstance(surface_d, dict) or not isinstance(surface_d.get('directories'), list):
        return False, '能力面结构失配'
    try:
        a = assets if assets is not None else load_assets()
    except Exception as e:
        return False, f'资产层不可读：{type(e).__name__}: {e}'
    amap = {x['id']: x for x in a['assets'] if isinstance(x, dict) and 'id' in x}
    smap = {x['id']: x for x in surface_d['directories'] if isinstance(x, dict) and 'id' in x}
    ported_ids = [x['id'] for x in surface_d['directories']
                  if isinstance(x, dict) and x.get('ported')]
    if not ported_ids:
        return True, '0/63 转正（全登记态，无冒充）'
    # ③ 真源 sha 校验（只算一次，命中才做）
    try:
        with open(deep_path or DEEP_FILE, 'rb') as f:
            real_sha = hashlib.sha256(f.read()).hexdigest()
    except Exception as e:
        return False, f'一手真源不可读：{type(e).__name__}: {e}'
    if real_sha != a.get('source_sha256'):
        return False, f'真源 sha 失配（实际 {real_sha[:12]}）'
    need = ('file', 'bytes', 'defs', 'imports', 'args', 'doc')
    for cid in ported_ids:
        rec = amap.get(cid)
        if not rec:
            return False, f'{cid}: ported=true 但资产层无落点'
        sigs = rec.get('script_signatures')
        if not isinstance(sigs, list) or any(
                not isinstance(s, dict) or any(k not in s for k in need) for s in sigs):
            return False, f'{cid}: 脚本签名不完整（file/bytes/defs/imports/args/doc）'
        surf = smap.get(cid)
        if not surf:
            return False, f'{cid}: 资产有落点但能力面缺条目'
        # ② 签名数 == n_exe（事实自洽，不涉及价值判断）
        if len(sigs) != surf.get('n_exe'):
            return False, f'{cid}: 签名数 {len(sigs)} ≠ n_exe {surf.get("n_exe")}'
        # ④ 六维自洽
        for k in ('n_files', 'n_refs', 'n_exe', 'n_sections', 'n_mech', 'n_tool_tokens', 'has_fm'):
            if rec.get(k) != surf.get(k):
                return False, f'{cid}: 六维计数与能力面失配（{k}）'
    return True, f'{len(ported_ids)}/63 转正：资产落点齐 + 签名数与脚本数自洽 + 真源 sha 一致 + 六维自洽（中性摆出）'


def body_ok(manifest_obj=None, skills_dir=None):
    """W7 阶段B 正文落点判据（病15：识别范围 = 对象范围）。

    port_ok 只验脚本**签名元数据**，ported=true 仍可能是「正文没落盘」的空架子。
    本判据把对象范围对准「磁盘上的正文文件本身」，逐条对账：
      ① manifest 结构完整（count == len(files) == 349 独立硬锚）
      ② 63 域目录齐全且与一手名册一致，每域 SKILL.md 在册
      ③ 每个落点文件真实存在、非空，bytes/sha256 与 manifest 记录一致
      ④ 脚本正文数 == 38 独立硬锚（.py/.ps1/.sh/.js）
      ⑤ manifest 自身 count 与 files 长度自洽
    造错用内存深拷贝 + 真目录，不碰真文件。返回 (ok, msg)。
    """
    sd = skills_dir or V4_SKILLS_DIR
    if manifest_obj is None:
        try:
            with open(V4_MANIFEST, encoding='utf-8') as f:
                mf = json.load(f)
        except Exception as e:
            return False, f'正文 manifest 不可读：{type(e).__name__}: {e}'
    else:
        mf = manifest_obj
    if not isinstance(mf, dict) or not isinstance(mf.get('files'), list):
        return False, '正文 manifest 结构失配：缺 files 数组'
    files = mf['files']
    if len(files) != BODY_ANCHORS['files']:
        return False, f'正文条目数 {len(files)} ≠ 硬锚 {BODY_ANCHORS["files"]}'
    if mf.get('count') != len(files):
        return False, f'manifest count {mf.get("count")} ≠ files 长度 {len(files)}'
    # ② 63 域目录 + SKILL.md
    dirs = os.listdir(sd) if os.path.isdir(sd) else []
    doms = set(dirs)
    if doms != set(CAPABILITY_63):
        return False, f'正文域目录 {len(doms)} 与一手名册不符（缺 {sorted(set(CAPABILITY_63) - doms)[:3]}，多 {sorted(doms - set(CAPABILITY_63))[:3]}）'
    for did in CAPABILITY_63:
        if not os.path.isfile(os.path.join(sd, did, 'SKILL.md')):
            return False, f'{did}: SKILL.md 未在册'
    # ③ 逐条对账磁盘真实文件 bytes/sha256
    n_script = 0
    for rec in files:
        if not isinstance(rec, dict) or 'path' not in rec:
            return False, '正文条目缺 path'
        p = os.path.join(sd, rec['path'])
        if not os.path.isfile(p):
            return False, f'正文文件缺失：{rec["path"]}'
        raw = open(p, 'rb').read()
        if not raw:
            return False, f'正文文件空：{rec["path"]}'
        if len(raw) != rec.get('bytes'):
            return False, f'正文 bytes 失配：{rec["path"]}（{len(raw)}≠{rec.get("bytes")}）'
        if hashlib.sha256(raw).hexdigest() != rec.get('sha256'):
            return False, f'正文 sha256 失配：{rec["path"]}'
        if rec['path'].endswith(_BODY_SCRIPT_EXT):
            n_script += 1
    # ④ 脚本正文数硬锚
    if n_script != BODY_ANCHORS['scripts']:
        return False, f'脚本正文数 {n_script} ≠ 硬锚 {BODY_ANCHORS["scripts"]}'
    return True, (f'{len(files)}/{BODY_ANCHORS["files"]} 正文落点在册（63 域 SKILL.md 齐 + '
                  f'{n_script} 脚本 bytes/sha256 逐条对账一致，中性摆出）')


def skeleton_ok(root=None):
    """骨架齐全判定。返回 (ok, missing)。root 默认本 lib 目录。"""
    r = root or os.path.dirname(HERE)
    need = ['manifest.json', 'README.md', 'CHANGELOG.md',
            'scripts/core.py', 'scripts/tools_schema.json',
            'scripts/capability_surface.json',
            'scripts/jadx_engine.py', 'docs/TROUBLESHOOTING.md',
            'assets/capability_63/capability_assets.json',
            'assets/capability_63/source_deep.json',
            'assets/capability_63/v4_skills_manifest.json',
            'assets/capability_63/v4_skills',
            'assets/capability_63/rea_tools.json',
            'assets/capability_63/tool_tokens.json']
    missing = [f for f in need if not os.path.isfile(os.path.join(r, f))
               and not os.path.isdir(os.path.join(r, f))]
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


def _bad_value(v):
    """判定单个参数「值」是否为已知坏填法。返回说明字符串或 None。

    病15：判据识别范围必须等于对象范围。旧版扫 json.dumps(args) 的字符串，
    会把合法键名 class_name 当成违例；这里只看值，键名任意都合法。
    """
    if not isinstance(v, str):
        return None
    if v in BAD_VALUE_LITERALS:
        return f'JSON key / 占位符字面量 {v!r} 当参数值'
    for p in ZIP_RAW_PREFIXES:
        if v.startswith(p):
            return f'zip 原始路径 {v!r}（应用 jadx 解码名）'
    return None


def chain_ok(args):
    """参数链判定：查参数**值**是否命中已知坏填法（查值不查键，病15 修正）。"""
    if not isinstance(args, dict):
        return False, '参数链非 dict'
    hits = []
    for k, v in args.items():
        b = _bad_value(v)
        if b:
            hits.append(f'{k}: {b}')
    if hits:
        return False, '；'.join(hits) + '（见 CHAIN_RULES）'
    return True, '参数链未命中已知坏填法'


def schema_ok(d):
    """W2 转正判定（病15：识别范围 = 对象范围，不只看一个 verified 布尔）。

    逐工具验：26 名册一致 / inputSchema 非空且 object / required 自洽 /
    call_recipe.args 齐备 / 参数链无坏填法 / verified 有 evidence 防洗绿。
    """
    tools = d.get('tools') if isinstance(d, dict) else None
    if not isinstance(tools, list):
        return False, '缺 tools 数组'
    if len(tools) != 26:
        return False, f'工具数 {len(tools)}≠26'
    names = [t.get('name') for t in tools]
    ok, msg = names_ok(names)
    if not ok:
        return False, msg
    for t in tools:
        n = t.get('name')
        s = t.get('inputSchema')
        if not isinstance(s, dict) or s.get('type') != 'object':
            return False, f'{n} inputSchema 缺失/非 object（W1 残留）'
        recipe = t.get('call_recipe')
        if not isinstance(recipe, dict) or not isinstance(recipe.get('args'), dict):
            return False, f'{n} 缺 call_recipe.args 真调配方'
        args = recipe['args']
        for r in (s.get('required') or []):
            if r not in args:
                return False, f'{n} required {r} 未出现在 call_recipe.args'
        cok, cmsg = chain_ok(args)
        if not cok:
            return False, f'{n} 参数链坏填法：{cmsg}'
        if t.get('verified') and not recipe.get('evidence'):
            return False, f'{n} verified=true 但无 evidence（洗绿）'
    nv = sum(1 for t in tools if t.get('verified'))
    if nv != 26:
        return False, f'verified {nv}/26 未全转正'
    return True, '26 工具 inputSchema + 真调配方齐备，参数链合法，verified 26/26'


# 能力面逐条必填字段 / 计数字段 / 布尔字段（surface_ok 的对象范围）
_SURFACE_FIELDS = ('id', 'n_files', 'n_refs', 'n_exe', 'n_sections', 'n_mech',
                   'n_tool_tokens', 'has_fm', 'registered', 'ported', 'scripts')
_SURFACE_CNT = ('n_files', 'n_refs', 'n_exe', 'n_sections', 'n_mech', 'n_tool_tokens')
_SURFACE_BOOL = ('has_fm', 'registered', 'ported')
# 计数字段 → source.totals 键（六维求和对账）
_SURFACE_PAIR = {'n_files': 'files', 'n_refs': 'refs', 'n_exe': 'exe_scripts',
                 'n_sections': 'sections', 'n_mech': 'mech', 'n_tool_tokens': 'tool_tokens'}


def surface_ok(d):
    """W3 63 目录能力面「登记齐全 + 机检可回读」判定。

    病15：识别范围 = 对象范围。不看单个 count 布尔，六道逐层验：
      ① 名册与数量（逐个比对 CAPABILITY_63、查重，不只 len）
      ② 逐目录字段/类型/自洽（n_exe==len(scripts)）
      ③ 登记/转正分离（registered 全真、ported 全假，防冒充）
      ④ 逐条求和 ↔ source.totals 六维对账（防清单内部自相矛盾）
      ⑤ 独立硬锚 63/349/196/38（防「清单 + totals 同步改小」的洗绿）
      ⑥ separation 分离声明在位（M2 纪律）
    """
    if not isinstance(d, dict):
        return False, '清单非 dict'
    dirs = d.get('directories')
    if not isinstance(dirs, list):
        return False, 'directories 非 list'
    # ① 名册与数量
    if len(dirs) != SURFACE_ANCHORS['directories']:
        return False, f'目录数 {len(dirs)}≠63'
    ids = [x.get('id') for x in dirs if isinstance(x, dict)]
    if len(ids) != 63 or len(set(ids)) != 63:
        return False, 'id 缺失或重复'
    if set(ids) != set(CAPABILITY_63):
        return False, '目录名与一手深读名册 CAPABILITY_63 不一致'
    # ② 逐目录字段 / 类型 / 自洽
    for x in dirs:
        if not isinstance(x, dict):
            return False, '目录条目非 dict'
        miss = [k for k in _SURFACE_FIELDS if k not in x]
        if miss:
            return False, f"{x.get('id', '?')} 缺字段 {miss}"
        if not isinstance(x['id'], str) or not x['id']:
            return False, 'id 非非空 str'
        for k in _SURFACE_CNT:
            v = x[k]
            if not isinstance(v, int) or isinstance(v, bool) or v < 0:
                return False, f"{x['id']} {k} 非非负 int"
        for k in _SURFACE_BOOL:
            if not isinstance(x[k], bool):
                return False, f"{x['id']} {k} 非 bool"
        if not isinstance(x['scripts'], list) or not all(isinstance(s, str) for s in x['scripts']):
            return False, f"{x['id']} scripts 非 list[str]"
        if x['n_exe'] != len(x['scripts']):
            return False, f"{x['id']} n_exe≠len(scripts)"
    # ③ 登记/转正分离（W6：ported=true 须由 port_ok 资产落点判据背书，非旧「全假才绿」）
    if not all(x['registered'] for x in dirs):
        return False, '存在 registered=false（登记未全）'
    pok, pmsg = port_ok(d)
    if not pok:
        return False, f'补码转正判据红：{pmsg}'
    # ③-b W7 阶段B：正文落点判据——ported 全量大面积转正时，正文必须真实在册。
    #   只在该清单确有大面积转正（>0）时校验，防「仅登记态」新仓缺正文被误判红。
    n_port = sum(1 for x in dirs if x.get('ported'))
    if n_port > 0:
        bok, bmsg = body_ok()
        if not bok:
            return False, f'正文落点判据红（ghost-port 空架子）：{bmsg}'
    # ④ 逐条求和 ↔ source.totals 六维对账
    src = d.get('source')
    if not isinstance(src, dict) or not isinstance(src.get('totals'), dict):
        return False, '缺 source.totals'
    tot = src['totals']
    for ck, tk in _SURFACE_PAIR.items():
        s = sum(x[ck] for x in dirs)
        if s != tot.get(tk):
            return False, f'求和 {ck}={s} 与 source.totals.{tk}={tot.get(tk)} 不符'
    if tot.get('directories') != SURFACE_ANCHORS['directories']:
        return False, 'source.totals.directories≠63'
    # ⑤ 独立硬锚（与清单 totals 分离，防同步洗绿）
    for ck, tk in (('n_files', 'files'), ('n_refs', 'refs'), ('n_exe', 'exe_scripts')):
        if sum(x[ck] for x in dirs) != SURFACE_ANCHORS[tk]:
            return False, f'硬锚失配：{tk} 逐条求和≠{SURFACE_ANCHORS[tk]}'
    # ⑥ separation 分离声明
    sep = d.get('separation')
    if not isinstance(sep, dict) or not all(k in sep for k in ('registered', 'ported', 'note')):
        return False, '缺 separation 分离声明'
    n_port = sum(1 for x in dirs if x['ported'])
    return (True, '63/63 能力面登记齐全（349 文件/196 refs/38 脚本），六维对账一致，'
                  f'补码转正 {n_port}/63（登记≠转正）')


def selftest():
    """正反向：正向真实状态绿；多类造错各自必须红。

    病15 单测覆盖多种后接形态：坏填法不只一种精确锚点；能力面 likewise
    十二类造错（删目录/重复 id/缺字段/类型错/登记未全/冒充转正/脚本失配/
    求和污染/清单+totals 同步洗绿/名册不符/缺分离/整表非 dict）各自判红。
    """
    fails = []

    def ck(label, cond, detail=''):
        print(('  ✓ ' if cond else '  ✗ ') + label + ('' if cond else '  ← ' + str(detail)))
        if not cond:
            fails.append(label)

    print('── 正向（真实状态）──')
    ok, miss = skeleton_ok()
    ck('骨架齐全（含 jadx_engine.py + capability_surface.json）', ok, miss)
    ok, msg = names_ok(TOOLS_26)
    ck('名册 26 个与实测一致', ok, msg)
    legal = [
        ('真实类/方法名', {'class_name': 'com.yunget.app.MainActivity', 'method_name': 'onCreate'}),
        ('required 键名本身合法', {'class_name': 'com.yunget.app.MainActivity'}),
        ('构造器', {'class_name': 'dev.turbodl.core.X', 'method_name': '<init>'}),
        ('字段', {'class_name': 'com.yunget.app.MainActivity', 'field_name': '$stable'}),
        ('jadx 解码资源名', {'name': 'AndroidManifest.xml'}),
        ('无参', {}),
    ]
    for nm, a in legal:
        o, m = chain_ok(a)
        ck(f'合法参数链：{nm}', o, m)
    try:
        d = load_schema()
        ok, msg = names_ok([t['name'] for t in d['tools']])
        ck('tools_schema.json 名册 26 个', ok, msg)
        ok, msg = schema_ok(d)
        ck('W2 转正：26 工具 schema+配方齐备 verified 26/26', ok, msg)
        n_ver = sum(1 for t in d['tools'] if t.get('verified'))
        print(f'  ℹ 已验 {n_ver}/26（W2 全量接线完成）')
    except Exception as e:
        ck('tools_schema.json 可读', False, f'{type(e).__name__}: {e}')
    try:
        sd = load_surface()
        ok, msg = surface_ok(sd)
        ck('W3 能力面清单 63/63 登记齐全且机检可回读', ok, msg)
        print(f'  ℹ {msg}')
    except Exception as e:
        ck('capability_surface.json 可读', False, f'{type(e).__name__}: {e}')

    print('── 反向（造错必红）──')
    ok, _ = skeleton_ok(root='/tmp/__foundry_no_such_dir__')
    ck('缺 manifest.json → 骨架判红', not ok)
    ok, _ = names_ok(TOOLS_26[:-1])
    ck('工具数 25 → 名册判红', not ok)
    ok, _ = names_ok(TOOLS_26 + ['get_xrefs_to_class'])
    ck('名册重复 → 判红', not ok)
    bad_forms = [
        ('JSON key 当类名', {'class': 'class_name'}),
        ('JSON key 当方法名', {'class_name': 'com.yunget.app.MainActivity',
                             'method_name': 'class_name'}),
        ('猜类名', {'class_name': 'MainActivity.guess'}),
        ('占位符当资源名', {'name': 'zip_entry_path'}),
        ('zip 原始路径', {'name': 'META-INF/com/android/build/gradle/app-metadata.properties'}),
    ]
    for nm, a in bad_forms:
        o, _ = chain_ok(a)
        ck(f'坏填法判红：{nm}', not o)
    try:
        import copy
        d = load_schema()
        mk = lambda: copy.deepcopy(d)  # noqa: E731
        d1 = mk(); d1['tools'] = d1['tools'][:-1]
        ck('schema 少一个工具 → 判红', not schema_ok(d1)[0])
        d2 = mk(); d2['tools'][0]['inputSchema'] = None
        ck('inputSchema=null（W1 残留）→ 判红', not schema_ok(d2)[0])
        d3 = mk(); d3['tools'][0]['call_recipe'].pop('evidence', None)
        ck('verified 无 evidence（洗绿）→ 判红', not schema_ok(d3)[0])
        d4 = mk()
        for t in d4['tools']:
            if 'method_name' in (t['inputSchema'].get('required') or []):
                t['call_recipe']['args']['method_name'] = 'class_name'
                break
        ck('参数链含坏填法 → 判红', not schema_ok(d4)[0])
        d5 = mk()
        for t in d5['tools']:
            if t['inputSchema'].get('required'):
                r = t['inputSchema']['required'][0]
                t['call_recipe']['args'].pop(r, None)
                break
        ck('缺 required 必填 → 判红', not schema_ok(d5)[0])
    except Exception as e:
        ck('schema 造错用例可读', False, f'{type(e).__name__}: {e}')

    # W3 能力面：十二类造错各自必红（病15：识别范围 = 对象范围）
    try:
        import copy
        smk = lambda: copy.deepcopy(load_surface())  # noqa: E731
        s1 = smk(); s1['directories'] = s1['directories'][:-1]
        ck('能力面·少一个目录 → 判红', not surface_ok(s1)[0])
        s2 = smk(); s2['directories'][1]['id'] = s2['directories'][0]['id']
        ck('能力面·重复 id → 判红', not surface_ok(s2)[0])
        s3 = smk(); s3['directories'][0].pop('n_refs', None)
        ck('能力面·单条缺字段 → 判红', not surface_ok(s3)[0])
        s4 = smk(); s4['directories'][0]['n_files'] = '349'
        ck('能力面·计数类型错（str）→ 判红', not surface_ok(s4)[0])
        s5 = smk(); s5['directories'][5]['registered'] = False
        ck('能力面·registered=false（登记未全）→ 判红', not surface_ok(s5)[0])
        # W6：63 域已全量真实转正，旧「任一 ported=true 即冒充」用例前提失效。
        # 改成「翻正一个名册外 id」仍须判红——防冒充的语义在新态下依然成立。
        s6 = smk(); s6['directories'][7]['id'] = 'ghost-port'
        ck('能力面·翻正名册外 id（冒充转正）→ 判红', not surface_ok(s6)[0])
        s7 = smk(); s7['directories'][3]['scripts'].append('ghost.py')
        ck('能力面·n_exe≠len(scripts) → 判红', not surface_ok(s7)[0])
        s8 = smk(); s8['directories'][0]['n_files'] += 1
        ck('能力面·逐条求和与 totals 失配 → 判红', not surface_ok(s8)[0])
        s9 = smk()
        s9['directories'][0]['n_files'] -= 1
        s9['source']['totals']['files'] -= 1
        ck('能力面·清单+totals 同步改小（洗绿）→ 独立硬锚判红', not surface_ok(s9)[0])
        s10 = smk(); s10['directories'][0]['id'] = 'ghost-dir'
        ck('能力面·目录名不在名册 → 判红', not surface_ok(s10)[0])
        s11 = smk(); s11.pop('separation', None)
        ck('能力面·缺 separation 分离声明 → 判红', not surface_ok(s11)[0])
        ck('能力面·整表非 dict → 判红', not surface_ok([1, 2, 3])[0])
    except Exception as e:
        ck('能力面·造错用例可读', False, f'{type(e).__name__}: {e}')

    # W6 补码转正判据：正向真实态绿；四类事实造假各自判红（病15：对象范围=能否真转正）
    # 中性摆出：不测「分级/敏感/该不该激活」，只测事实自洽（落点/签名/sha/六维）
    try:
        import copy
        assets = load_assets()
        surf = load_surface()
        pok, pmsg = port_ok(surf, assets)
        ck(f'补码正向判据：真实态（{sum(1 for x in surf["directories"] if x.get("ported"))}/63 转正）', pok, pmsg)
        ck('补码中性：资产层无 value 分级字段',
           all('content_tier' not in a and 'tier' not in a for a in assets['assets']))
        base = copy.deepcopy(surf)
        for x in base['directories']:
            x['ported'] = True
        ck('补码正向：全量 63 域落点+事实自洽 → 判绿', port_ok(base, assets)[0])
        # 反向 1：资产落点缺失（删一条）→ 红
        noasset = copy.deepcopy(assets)
        noasset['assets'] = noasset['assets'][:-1]
        ck('补码反向·资产落点缺失 → 判红', not port_ok(base, noasset)[0])
        # 反向 2：真源 sha 篡改 → 红
        fake_sha = copy.deepcopy(assets); fake_sha['source_sha256'] = '0' * 64
        ck('补码反向·真源 sha 失配 → 判红', not port_ok(base, fake_sha)[0])
        # 反向 3：脚本签名被掏空（有脚本域）→ 红
        nosig = copy.deepcopy(assets)
        for a in nosig['assets']:
            if a['n_exe'] > 0:
                a['script_signatures'] = []
                break
        ck('补码反向·脚本签名缺失 → 判红', not port_ok(base, nosig)[0])
        # 反向 4：六维计数失配 → 红
        badcnt = copy.deepcopy(assets)
        badcnt['assets'][0]['n_files'] += 1
        ck('补码反向·六维计数失配 → 判红', not port_ok(base, badcnt)[0])
    except Exception as e:
        ck('补码判据·造错用例可读', False, f'{type(e).__name__}: {e}')

    # W7 阶段B 正文落点判据：正向真目录绿；四类事实造假各自判红（病15：对象范围=磁盘正文）
    # 中性摆出：不测分级，只测正文文件是否真实在册、bytes/sha256 逐条对账。
    try:
        import copy
        mf = json.load(open(V4_MANIFEST, encoding='utf-8'))
        bok, bmsg = body_ok(mf)
        ck(f'正文正向判据：真实态（{mf["count"]} 条目在册）', bok, bmsg)
        # 反向 1：正文文件被抹掉（ghost-port：manifest 有条目、磁盘无文件）→ 红
        ghost = copy.deepcopy(mf)
        ghost['files'][0]['path'] = ghost['files'][0]['path'] + '.ghost'
        ck('正文反向·落点文件缺失（ghost-port 空架子）→ 判红', not body_ok(ghost)[0])
        # 反向 2：正文 bytes 篡改 → 红
        badb = copy.deepcopy(mf)
        badb['files'][0]['bytes'] = badb['files'][0]['bytes'] + 1
        ck('正文反向·bytes 篡改 → 判红', not body_ok(badb)[0])
        # 反向 3：正文 sha256 篡改 → 红
        bads = copy.deepcopy(mf)
        bads['files'][0]['sha256'] = '0' * 64
        ck('正文反向·sha256 篡改 → 判红', not body_ok(bads)[0])
        # 反向 4：count 与 files 脱钩 → 红
        badc = copy.deepcopy(mf)
        badc['count'] = badc['count'] - 1
        ck('正文反向·count 脱钩 → 判红', not body_ok(badc)[0])
    except Exception as e:
        ck('正文判据·造错用例可读', False, f'{type(e).__name__}: {e}')

    # W8-A REA 24 工具 + 65 token 弱明细判据：正向绿，造错判红（病15：对象范围=名册自洽）
    try:
        import copy
        rea = load_rea(); tok = load_tokens()
        rok, rmsg = rea_ok(rea); tokok, tomsg = tokens_ok(tok)
        ck(f'REA 正向判据：真实态（{rea["count"]} 工具）', rok, rmsg)
        ck(f'token 正向判据：真实态（{tok["count"]} token）', tokok, tomsg)
        # 反面 1：REA count 脱钩 → 红
        badr = copy.deepcopy(rea); badr['count'] += 1
        ck('REA 反向·count 脱钩 → 判红', not rea_ok(badr)[0])
        # 反面 2：REA 与 26 工具集雷同（识别范围≠对象范围）→ 红
        samer = copy.deepcopy(rea); samer['tools'] = list(TOOLS_26)
        ck('REA 反向·与26工具集雷同 → 判红', not rea_ok(samer)[0])
        # 反面 3：REA 缺来源 sha（无法证明原样解出）→ 红
        nosha = copy.deepcopy(rea); nosha.pop('sha256_source', None)
        ck('REA 反向·缺来源 sha → 判红', not rea_ok(nosha)[0])
        # 反面 4：token 缺目标工具 → 红
        badt = copy.deepcopy(tok)
        badt['tokens'] = [x for x in badt['tokens'] if x['name'] != 'nmap']
        badt['count'] = len(badt['tokens'])
        ck('token 反向·缺目标工具 nmap → 判红', not tokens_ok(badt)[0])
        # 反面 5：token 有重复 → 红
        dup = copy.deepcopy(tok); dup['tokens'].append(dup['tokens'][0]); dup['count'] += 1
        ck('token 反向·重复 → 判红', not tokens_ok(dup)[0])
    except Exception as e:
        ck('W8-A 判据·造错用例可读', False, f'{type(e).__name__}: {e}')

    # W8-D 运行时实体判据：正向绿（真磁盘实体逐条对账），造错判红（病15：对象范围=磁盘实体）
    try:
        import copy
        rt = load_runtimes()
        rok, rmsg = runtimes_ok(rt)
        ck(f'runtime 正向判据：真实态（{rt["count"]} 实体/{rt["total_bytes"] // 1048576}MB）', rok, rmsg)
        # 反面 1：篡改某实体 sha → 红（掉包/篡改必抓）
        badsha = copy.deepcopy(rt); badsha['files'][0]['sha256'] = '0' * 64
        ck('runtime 反向·实体 sha 篡改 → 判红', not runtimes_ok(badsha)[0])
        # 反面 2：实体 bytes 与清单脱钩 → 红
        badbytes = copy.deepcopy(rt); badbytes['files'][0]['bytes'] += 1
        ck('runtime 反向·实体 bytes 脱钩 → 判红', not runtimes_ok(badbytes)[0])
        # 反面 3：count 脱钩 → 红
        badcount = copy.deepcopy(rt); badcount['count'] += 1
        ck('runtime 反向·count 脱钩 → 判红', not runtimes_ok(badcount)[0])
        # 反面 4：path 越界（../） → 红
        badpath = copy.deepcopy(rt); badpath['files'][0]['path'] = '../evil.bin'
        ck('runtime 反向·path 越界 → 判红', not runtimes_ok(badpath)[0])
        # 反面 5：缺来源标注 → 红（无法证明同源解出）
        nosrc = copy.deepcopy(rt); nosrc['files'][0].pop('source', None)
        ck('runtime 反向·缺来源标注 → 判红', not runtimes_ok(nosrc)[0])
        # 反面 6：total_bytes 脱钩 → 红
        badtotal = copy.deepcopy(rt); badtotal['total_bytes'] += 1
        ck('runtime 反向·total_bytes 脱钩 → 判红', not runtimes_ok(badtotal)[0])
    except Exception as e:
        ck('W8-D 判据·造错用例可读', False, f'{type(e).__name__}: {e}')

    print(f'\n结果：{"全部通过" if not fails else str(len(fails)) + " 项失败"}')
    return 0 if not fails else 2


def main(argv):
    if '--selftest' in argv:
        return selftest()
    print(__doc__)
    print(f'工具名册 {len(TOOLS_26)} 个；schema 真源 {SCHEMA}')
    print(f'能力面清单 {len(CAPABILITY_63)} 目录；surface 真源 {SURFACE}')
    print('跑 --selftest 做正反向验证。')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as e:
        print(f'✗ 内核自身异常：{type(e).__name__}: {e}')
        sys.exit(1)
