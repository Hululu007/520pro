#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pack_skills.py — 技能发布闸（打包 + 包校验），治「包比仓库旧」

为什么要有它（真实事故，非假设）:
  2026-11-14 手工打了 7 个技能包给手机导入，2 小时后仓库又改了 space-hub(2.7.5→2.7.6)
  与 probe-hub(1.28.0→1.28.2)，但 zip 仍是旧的。用户差点把「移不到空间根」的旧版导进手机。
  根因不是手滑，是**打包没有闸**：没有任何判据能回答「这个 zip 跟当前仓库是不是同一份」。

判据（fail-closed，判不了就拒）:
  P1 前置：打包前跑 skill_contract_check.py，有 ✗ 即拒（B-10 拦截即停止）
  P2 结构：SKILL.md 必须在包根（平台要求），frontmatter 三键齐（name/version/description）
  P3 指纹：包内写 _PACK_META.json（git_head + 各文件 sha256 + packed_at），
           使「包 ↔ 仓库」的对应关系可事后机检，不靠人记
  P4 校验：--verify 逐文件比 sha，报 missing / extra / content-diff 三类，全零才 rc=0
  P5 版本：--verify 比对 META.version 与仓库当前版本；不一致即红（治「包比仓库旧」）
  P6 老包：无 _PACK_META.json 的包判「无法判定」，不算通过（三态不得折叠成通过）

纪律:
  · 打包内容只来自仓库工作区，不读 ~/.codebuddy 安装副本（那是产物，不是真源）
  · 排除运行时目录（snapshots / harvest_candidates）与 __pycache__，包只含「技能本体」
  · CHANGELOG 默认排除（手机侧用不上，probe-hub 的 CHANGELOG 有 200KB，
    挤占模型上下文毫无收益）；要带就 --with-changelog，并在 META 里记下
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import zipfile

REPO = os.path.dirname(os.path.abspath(__file__))
CONTRACTS = os.path.join(REPO, 'verify', 'skill_contracts.json')
META_NAME = '_PACK_META.json'
META_SCHEMA = 'pack_meta v1'

EXCLUDE_DIRS = {'.git', '__pycache__', 'node_modules', '.pytest_cache',
                'snapshots', 'harvest_candidates', '.mypy_cache'}
EXCLUDE_SUFFIX = ('.pyc', '.pyo', '.DS_Store', '.swp')
EXCLUDE_FILES = {'CHANGELOG.md'}


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 16), b''):
            h.update(chunk)
    return h.hexdigest()


def load_skills(repo):
    """技能清单唯一真源 = 契约登记表（M1），不自己扫目录。"""
    d = json.load(open(CONTRACTS, encoding='utf-8'))
    out = {}
    for name, spec in (d.get('skills') or {}).items():
        if spec.get('kind') != 'skill':
            continue  # lib 类无 SKILL.md，平台不注册，不打包
        rel = spec.get('path') or ''
        out[name] = os.path.join(repo, rel)
    return out


def git_head(repo):
    try:
        sha = subprocess.check_output(['git', '-C', repo, 'rev-parse', 'HEAD'],
                                      stderr=subprocess.DEVNULL, text=True).strip()
        dirty = bool(subprocess.check_output(
            ['git', '-C', repo, '--no-optional-locks', 'status', '--porcelain',
             '--', '.'], stderr=subprocess.DEVNULL, text=True).strip())
        return sha, dirty
    except Exception:
        return '', None


def read_skill_meta(base):
    """从 SKILL.md frontmatter 读 name / version / description。"""
    p = os.path.join(base, 'SKILL.md')
    txt = open(p, encoding='utf-8').read()
    m = re.match(r'^---\n(.*?)\n---', txt, re.S)
    if not m:
        return None
    fm = m.group(1)
    got = {}
    for key in ('name', 'version', 'description'):
        # ★ 不能写 `"?([^"\n]*)"?`：description 值内部可能含 ASCII 双引号
        #   （tvbox-pipeline 就有 4 个），字符类会在中间那个引号处截断、$ 不匹配，
        #   于是「明明有 description」被判成缺失（首跑即误拒了一次）。
        #   取整行再削掉首尾成对引号，才是稳的读法。
        mm = re.search(rf'^{key}:\s*(.+)$', fm, re.M)
        val = mm.group(1).strip() if mm else ''
        if len(val) >= 2 and val[0] == '"' and val[-1] == '"':
            val = val[1:-1]
        got[key] = val
    return got


def collect(base, with_changelog):
    """返回 [(相对路径, 绝对路径)]，路径统一用 / 分隔。"""
    files = []
    for root, dirs, names in os.walk(base):
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDE_DIRS)
        for n in sorted(names):
            if n.endswith(EXCLUDE_SUFFIX):
                continue
            if n in EXCLUDE_FILES and not with_changelog:
                continue
            ap = os.path.join(root, n)
            rel = os.path.relpath(ap, base).replace(os.sep, '/')
            files.append((rel, ap))
    return files


def precheck(repo, skip):
    """P1：契约机检不过，不许打包。"""
    if skip:
        print('  ⚠ 已用 --skip-precheck 绕行契约机检——请确认这是有意为之（审计留痕）')
        return True
    r = subprocess.run([sys.executable, os.path.join(repo, 'verify', 'skill_contract_check.py')],
                       capture_output=True, text=True, cwd=repo)
    out = (r.stdout or '') + (r.stderr or '')
    # ★ 只看「结果行」：机检明细形如 `  ✗ [C3] probe-hub: ...`。
    #   不能用 `'✗' in line`——汇总行本身就含「0 ✗」，判据会把自己算成违例
    #   （与病1「自指命中」同族，首次跑就在这里误拒了一次）。
    bad = [l for l in out.splitlines() if re.search(r'^\s*✗\s+\[', l)]
    if bad or r.returncode != 0:
        print(f'  ✗ 前置闸拒收：契约机检有 {len(bad)} 项红（rc={r.returncode}）')
        for l in bad[:5]:
            print('    ' + l.strip())
        print('    处置：先修红再打包；确需带伤出包用 --skip-precheck 并写明理由')
        return False
    print('  ✓ 前置闸：契约机检全绿')
    return True


def pack_one(name, base, outdir, with_changelog, head, dirty):
    meta = read_skill_meta(base)
    if not meta or not meta.get('name'):
        print(f'  ✗ {name}: SKILL.md 缺 frontmatter，拒打包')
        return None
    for k in ('version', 'description'):
        if not meta.get(k):
            print(f'  ✗ {name}: frontmatter 缺 {k}，拒打包')
            return None
    if meta['name'] != name:
        print(f"  ✗ {name}: frontmatter name={meta['name']} 与登记名不符，拒打包")
        return None

    files = collect(base, with_changelog)
    if not any(rel == 'SKILL.md' for rel, _ in files):
        print(f'  ✗ {name}: SKILL.md 不在包根，拒打包')
        return None

    hashes = {rel: sha256(ap) for rel, ap in files}
    pack_meta = {
        'schema': META_SCHEMA,
        'skill': name,
        'version': meta['version'],
        'git_head': head,
        'git_dirty': dirty,
        'packed_at': __import__('datetime').datetime.now().astimezone().isoformat(timespec='seconds'),
        'with_changelog': bool(with_changelog),
        'file_count': len(hashes),
        'files': hashes,
    }

    os.makedirs(outdir, exist_ok=True)
    zp = os.path.join(outdir, f'{name}.zip')
    with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as z:
        for rel, ap in files:
            z.write(ap, rel)
        z.writestr(META_NAME, json.dumps(pack_meta, ensure_ascii=False, indent=1))
    size = os.path.getsize(zp)
    print(f'  ✓ {name}  v{meta["version"]}  {len(hashes)} 件  {size / 1024:.0f}KB  → {zp}')
    return zp


def verify_zip(zp, skills, repo):
    """P4/P5/P6：逐文件比对 + 版本比对。返回 (ok, 说明)。"""
    name = os.path.basename(zp)[:-4]
    if name not in skills:
        return False, f'{name}: 契约表里没有这个技能（改名了？）'
    base = skills[name]

    try:
        z = zipfile.ZipFile(zp)
    except Exception as e:
        return False, f'{name}: 打不开（{e}）'

    names = set(z.namelist())
    if 'SKILL.md' not in names:
        return False, f'{name}: 包内无根级 SKILL.md（结构不合格）'

    if META_NAME not in names:
        # 老格式包：仍尽量给一条可判的线索——版本号能读出来就先比版本，
        # 版本都不同就是真旧包（真阳性）；版本相同也不能算通过（缺指纹，无法判定）。
        pkg_ver = ''
        try:
            fm = re.match(r'^---\n(.*?)\n---',
                          z.read('SKILL.md').decode('utf-8', 'replace'), re.S)
            mm = re.search(r'^version:\s*"?([^"\n]*)"?\s*$', fm.group(1), re.M) if fm else None
            pkg_ver = mm.group(1).strip() if mm else ''
        except Exception:
            pass
        ver_now = (read_skill_meta(base) or {}).get('version', '')
        if pkg_ver and ver_now and pkg_ver != ver_now:
            return False, (f'{name}: ✗ 旧包——包内 v{pkg_ver} ≠ 仓库 v{ver_now}'
                           f'（且无 {META_NAME}，无法逐文件判定差在哪）')
        return False, (f'{name}: 无 {META_NAME} —— 无法判定该包与仓库是否一致'
                       f'（包内 v{pkg_ver or "?"} 与仓库一致，但仍缺指纹；重新打包即可）')

    try:
        meta = json.loads(z.read(META_NAME).decode('utf-8'))
    except Exception as e:
        return False, f'{name}: {META_NAME} 损坏（{e}）'

    cur = collect(base, with_changelog=bool(meta.get('with_changelog')))
    cur_hash = {rel: sha256(ap) for rel, ap in cur}

    packed_files = set(meta.get('files') or {})
    pkg_files = names - {META_NAME}

    missing = sorted(packed_files - pkg_files)          # 包里丢了
    extra = sorted(pkg_files - packed_files)            # 包里多了
    diff = sorted(rel for rel in (packed_files & pkg_files)
                  if z.read(rel) != open(os.path.join(base, rel), 'rb').read()
                  if os.path.exists(os.path.join(base, rel)))

    vs_repo = sorted(set(cur_hash) - packed_files)      # 仓库新增、包里没有
    gone = sorted(packed_files - set(cur_hash))         # 包里有的，仓库已删

    ver_now = (read_skill_meta(base) or {}).get('version', '')
    ver_pkg = meta.get('version', '')

    problems = []
    if missing:
        problems.append(f'包内缺 {len(missing)} 件 {missing[:3]}')
    if extra:
        problems.append(f'包内多 {len(extra)} 件 {extra[:3]}')
    if diff:
        problems.append(f'{len(diff)} 件内容不同（仓库改过？）{diff[:3]}')
    if vs_repo:
        problems.append(f'仓库新增 {len(vs_repo)} 件未入包 {vs_repo[:3]}')
    if gone:
        problems.append(f'{len(gone)} 件仓库已无 {gone[:3]}')
    if ver_pkg != ver_now:
        problems.append(f'版本不符：包内 {ver_pkg} ≠ 仓库 {ver_now}')

    if problems:
        return False, f'{name}: ✗ ' + '；'.join(problems)

    head_now, _ = git_head(repo)
    tail = '' if meta.get('git_head') == head_now else f'（包出在 {str(meta.get("git_head"))[:8]}，当前 HEAD {head_now[:8]}，技能文件一致）'
    return True, f'{name}: ✓ v{ver_now} {len(packed_files)} 件逐 sha 一致{tail}'


def main():
    ap = argparse.ArgumentParser(description='技能发布闸：打包 + 包校验')
    ap.add_argument('--only', help='只处理这些技能（逗号分隔）')
    ap.add_argument('--out', default='out/skill_packs', help='输出目录（默认 out/skill_packs）')
    ap.add_argument('--with-changelog', action='store_true', help='把 CHANGELOG.md 打进包（默认排除）')
    ap.add_argument('--verify', nargs='+', metavar='ZIP', help='只校验已有包，不打包')
    ap.add_argument('--skip-precheck', action='store_true', help='跳过契约机检前置闸（须写明理由）')
    a = ap.parse_args()

    skills = load_skills(REPO)

    if a.verify:
        targets = []
        for t in a.verify:
            if os.path.isdir(t):
                targets += [os.path.join(t, f) for f in sorted(os.listdir(t)) if f.endswith('.zip')]
            else:
                targets.append(t)
        print(f'校验 {len(targets)} 个包 vs 仓库当前工作区\n')
        bad = 0
        for zp in targets:
            ok, msg = verify_zip(zp, skills, REPO)
            print(('  ' if ok else '  ') + msg)
            bad += 0 if ok else 1
        print(f'\n汇总：✓ {len(targets) - bad} ／ ✗ {bad}')
        return 0 if bad == 0 else 1

    print('① 前置闸')
    if not precheck(REPO, a.skip_precheck):
        return 1

    only = [s.strip() for s in a.only.split(',')] if a.only else sorted(skills)
    unknown = [s for s in only if s not in skills]
    if unknown:
        print(f'  ✗ 未登记技能：{unknown}（合法值见 verify/skill_contracts.json）')
        return 1

    head, dirty = git_head(REPO)
    if dirty:
        print('  ⚠ 工作区有未提交改动——包指纹的 git_head 会指向旧提交（内容仍按文件 sha 判定）')

    print(f'\n② 打包（{len(only)} 个技能 → {a.out}）')
    made = []
    for name in only:
        zp = pack_one(name, skills[name], os.path.join(REPO, a.out), a.with_changelog, head, dirty)
        if zp is None:
            return 1
        made.append(zp)

    print('\n③ 出包自校（打完立刻验一遍，防止「打包逻辑自己出错」）')
    bad = 0
    for zp in made:
        ok, msg = verify_zip(zp, skills, REPO)
        print('  ' + msg)
        bad += 0 if ok else 1
    if bad:
        print(f'\n✗ 出包自校失败 {bad} 个——包不可交付')
        return 1
    print(f'\n✓ 完成：{len(made)} 个包，全部与仓库逐 sha 一致')
    return 0


if __name__ == '__main__':
    sys.exit(main())
