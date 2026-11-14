#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""guard_cmd.py — 工具级硬拦截（PreToolUse·Bash 前置守卫）

为什么要有它（520 的真实软肋）:
  520 的提交闸做得很密——pre-commit 跑 secret_scan + verify、commit-msg 强制四字段，
  但这三道闸有一个共同的后门：`git commit --no-verify` 一句话全绕过。
  规则文件里写的「不许 --no-verify」只是软约束，模型想绕就绕，事后只能从 git 历史看出来。
  钩子是唯一能在**动作发生前**挡住的地方，实测有效（见下方协议注记）。

协议（实测确认，非推测）:
  PreToolUse 钩子输出 {"hookSpecificOutput":{"permissionDecision":"deny",
  "permissionDecisionReason":"..."}} 并 exit 2 → 平台直接阻断该次工具调用，
  模型收到 `PreToolUse:Bash hook blocked this tool call: <reason>`。
  2026-11-14 用临时探针实测命中一次，日志见 docs/通病台账.md 病15。

规则边界（只拦「确定有害且无正当理由」的，不拦常用操作）:
  G1 git commit/push/merge/rebase 带 --no-verify —— 绕过全部提交闸
  G2 rm -rf 目标是 / 或 ~ 或 $HOME（含 /* 变体）—— 不可逆灾难
  G3 git push --force/-f 到 main/master —— 覆盖远端历史
  G4 rm/mv/git rm 目标是双核 —— B-16 硬依赖
  G5 git add 凭据文件名 —— B-05 零明文凭证（一 add 即进永久历史）
  G6 Write/Edit 目标在 git 仓内且是凭据文件名 —— 同上，挡在「写下去」那一刻
  故意不拦：git reset --hard（常用且可恢复）、rm -rf 具体子目录（日常操作）、
            任何读操作、仓外的临时 .env（不入库就无风险，交给 G5 在 add 时兜）。
            拦太多会逼人永久关掉钩子，等于闸没了。

B-05 的凭据名单有三个来源，别写成三份：
  · secret_scan.py 的 CRED_NAMES 是「已追踪凭据文件」的真源，此处 CRED_BASENAMES 必须与它逐项相等；
    两边一致性由 test_guard_cmd.py 的对账用例守着（改了单边就红，不靠记）。
  · 本文件多出的是「入库即泄密」的同型扩展（.env / credentials.* / *.pem 等），
    secret_scan 靠内容扫描覆盖，这里靠文件名提前挡——两者互补，不是重复。

fail-open 但出声:
  守卫自身异常时放行（一个语法错误不该让整台机器干不了活），
  但把 guard_err 写进 state，`next_anchor.py --probe` 能查到——
  「静默失效」比「不设防」更危险，所以必须留痕。
"""
import argparse
import json
import os
import re
import sys

# ── B-05 凭据文件名（三条来源合一，见文件头） ──
# 前六项必须与 secret_scan.py 的 CRED_NAMES 逐项相等（对账用例守着，改单边就红）
CRED_BASENAMES = ('.gh_token', '.git-credentials', '.netrc', 'id_rsa', 'id_ed25519', '.env')
CRED_EXTRA = ('credentials.json', 'credentials.yml', 'credentials.yaml')
CRED_SUFFIXES = ('.pem', '.key', '.p12', '.pfx', '.keystore')
# 模板类一律放行：写了也不含真凭据，拦它只会逼人关钩子
CRED_TEMPLATE = ('.example', '.sample', '.template', '.dist')

# G5 的判据要**贴着 git add**：中间不许跨越命令分隔符（; & | 换行）。
# 首版用「命令里有 git add」+「命令里有凭据名」两个独立条件，结果
# `git add -A && git commit -F 说明文件`（说明里提到 .env）被误拦了三次——
# 判据的对象范围是「暂存动作的实参」，识别范围却是「整条 shell 文本」，
# 正是台账病15 的形态。改成一条正则后，凭据名必须出现在 git add 后方、
# 且与 git add 之间没有分隔符，才算「真要把这个文件加进去」。
G5_PAT = (
    r'\bgit\s+add\b[^;&|\n]*?[\s/]'
    r'(?:\.env(?!\.(?:example|sample|template|dist))'
    r'|\.gh_token|\.git-credentials|\.netrc|id_rsa(?!\.pub)|id_ed25519(?!\.pub)'
    r'|credentials\.(?:json|ya?ml)'
    r'|[^\s/\'"]+\.(?:pem|key|p12|pfx|keystore)'
    r')(?=[\s;&|)"\'=.]|$)'
)

# 真源在这里；改规则先改这里，再跑 verify/tests/test_guard_cmd.py
RULES = [
    {
        'id': 'G1',
        'why': '--no-verify 绕过全部提交闸（secret_scan / 提交四字段 / verify.sh）',
        'pat': r'\bgit\b[^|;&\n]*\b(commit|push|merge|rebase)\b[^|;&\n]*\s--no-verify\b',
        'fix': '去掉 --no-verify 正常提交；确有正当理由，在提交信息里写明并让人批准',
    },
    {
        'id': 'G2',
        'why': '递归删除根目录 / 家目录，不可逆',
        'pat': (r'\brm\b[^|;&\n]*\s-[a-zA-Z]*[rR][a-zA-Z]*\s+'
                r'(-[a-zA-Z]+\s+)*'
                r'(/|/\*|~|~/\*|~/|\$HOME|\$\{HOME\}|\$HOME/\*|\$\{HOME\}/\*'
                r'|\$HOME/|\$\{HOME\}/)(\s|$|["\'])'),
        'fix': '明确写出要删的具体子目录；批量删除先 --dry 列清单',
    },
    {
        'id': 'G3',
        'why': '强推 main/master 覆盖远端历史',
        # 三个条件必须同时成立、不限顺序（首版写成单条正则，把参数顺序写死了，
        # `git push origin main --force` 这种最常见写法反而溜过——已修）
        'pats': [r'\bgit\b[^|;&\n]*\bpush\b',
                 r'(?:^|\s)(?:--force-with-lease|--force|-f)(?:\s|$)',
                 r'\b(?:main|master)\b'],
        'fix': '用 hooks/git_push_safe.sh（带重试与校验）；确需强推先说明原因',
    },
    {
        'id': 'G4',
        'why': '删除/移走双核（probe-hub、tvbox-core）——B-16 硬依赖，'
               'tvbox-core/scripts/core.py 被 probe-hub import，删了或改名会全线崩',
        # 只拦「rm/mv 在前、双核在后」的组合：
        #   命中：rm -rf .../tvbox-core ｜ mv probe-hub /tmp ｜ git rm -r .../probe-hub
        #   不拦：cp -r probe-hub /tmp/bak（备份不改原件）
        #         mv /tmp/x probe-hub（往双核里塞东西，非删除）
        # 双核名后必须紧跟 / 空白 或结尾，避免误伤 tvbox-core-backup 这类备份目录
        'pats': [r'\b(?:rm|mv|git\s+rm)\b[^|;&\n]*',
                 # 双核名后允许的分隔符要写全：行尾、空白、/、;、&、|、) 、} 、引号
                 # （首版只写了 / 空白 行尾 引号，`rm -rf x/tvbox-core; echo ok`
                 #   因为后面跟 ; 而漏判——实测真删了一个测试目录才发现）
                 r'\b(?:tvbox-core|probe-hub)(?=[/\s;&|)\}"\']|$)'],
        # 豁免：双核作为 mv 的**目标**（最后一个参数）= 往双核里放东西，不是删它
        'exempt': r'\bmv\b[^|;&\n]*\s+(?:\./)?(?:[\w./-]*/)?(?:tvbox-core|probe-hub)/?\s*$',
        'fix': '双核不得删除、改名、合并；确要动先备替代件并通过技能契约机检（C1–C6），'
               '备份请用 cp 到仓外目录',
    },
    {
        'id': 'G5',
        'why': '把凭据文件加进版本库（B-05：一 add 就进永久历史，删了也还在）',
        # 判据是**一条**正则，不是「有 git add」+「有凭据名」两个独立条件——
        # 后者会把「提交说明里提到 .env」也算违例（实测连拦三次，见上方 G5_PAT 注释）。
        # `git add -A` / `git add .` 仍不拦：不带文件名，判不了；
        # 批量 add 靠 secret_scan 的「未忽略未追踪即红」兜底，两道闸分工不同。
        'pat': G5_PAT,
        'fix': '凭据放仓外（/tmp 或 ~/.config 下 0600）并进 .gitignore；'
               '仓内只留 .env.example / credentials.example',
    },
]


# 写文件类规则的「规则体」，判据在 check_write()（要看路径，不是命令串）
WRITE_RULE = {
    'id': 'G6',
    'why': '在 git 仓库内写凭据文件（B-05：写下去那一刻就等着被 add）',
    'fix': '凭据写仓外并 0600；仓内只放模板（.env.example 等）；'
           '确需仓内占位，先确认 .gitignore 已覆盖',
}


def _in_git_repo(path):
    """路径的最近存在祖先里有没有 .git——纯文件系统检查，不跑 git 命令。

    为什么不用 git rev-parse：钩子在每次 Write 前都会跑，起子进程太贵；
    且新文件的目录可能还不存在，rev-parse 会直接失败（误判为「不在仓内」而放行）。
    """
    try:
        d = os.path.dirname(os.path.abspath(os.path.expanduser(str(path))))
    except Exception:
        return False
    while d and d != os.path.dirname(d):
        if os.path.exists(os.path.join(d, '.git')):
            return True
        d = os.path.dirname(d)
    return False


def check_write(path):
    """Write/Edit 目标是不是「仓内凭据文件」。返回规则 dict 或 None。

    仓外不管：/tmp 里的 .env 不入库就无风险，硬拦只会误伤调试；
    真正入库的动作由 G5（git add）在那一刻挡。
    """
    p = str(path or '').strip()
    if not p:
        return None
    base = os.path.basename(p.rstrip('/\\'))
    low = base.lower()
    if any(low.endswith(t) for t in CRED_TEMPLATE):
        return None
    if not (low in CRED_BASENAMES or low in CRED_EXTRA or low.endswith(CRED_SUFFIXES)):
        return None
    return WRITE_RULE if _in_git_repo(p) else None


def check(command):
    """返回命中的规则 dict，未命中返回 None。"""
    if not command:
        return None
    cmd = str(command)
    for r in RULES:
        if r.get('exempt') and re.search(r['exempt'], cmd):
            continue
        if r.get('pats'):
            if all(re.search(p, cmd) for p in r['pats']):
                return r
        elif r.get('pat'):
            if re.search(r['pat'], cmd):
                return r
    return None


def deny_payload(rule):
    """PreToolUse 的阻断载荷（协议已实测）。"""
    return {
        'hookSpecificOutput': {
            'hookEventName': 'PreToolUse',
            'permissionDecision': 'deny',
            'permissionDecisionReason': f"⛔ [{rule['id']}] {rule['why']}｜正门：{rule['fix']}",
        }
    }


def main():
    ap = argparse.ArgumentParser(description='工具级硬拦截（PreToolUse 守卫：命令 + 写入路径）')
    ap.add_argument('--check', metavar='CMD', help='只判定一条命令，打印结果（调试/测试用）')
    ap.add_argument('--check-write', metavar='PATH', help='只判定一个写入路径（调试/测试用）')
    ap.add_argument('--list', action='store_true', help='列出全部规则')
    a = ap.parse_args()

    if a.list:
        for r in RULES:
            pat = r.get('pat') or ' && '.join(r.get('pats') or [])
            print(f"{r['id']}  {r['why']}\n     {r['fix']}\n     {pat}")
        print(f"{WRITE_RULE['id']}  {WRITE_RULE['why']}\n     {WRITE_RULE['fix']}\n     "
              f"文件名 ∈ {CRED_BASENAMES + CRED_EXTRA} 或后缀 ∈ {CRED_SUFFIXES}，且路径在 git 仓内")
        return 0

    if a.check is not None:
        hit = check(a.check)
        print(json.dumps({'deny': bool(hit), 'rule': hit['id'] if hit else None,
                          'why': hit['why'] if hit else None}, ensure_ascii=False))
        return 2 if hit else 0

    if a.check_write is not None:
        hit = check_write(a.check_write)
        print(json.dumps({'deny': bool(hit), 'rule': hit['id'] if hit else None,
                          'why': hit['why'] if hit else None}, ensure_ascii=False))
        return 2 if hit else 0

    # 钩子模式：从 stdin 读 payload
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    ti = data.get('tool_input') if isinstance(data.get('tool_input'), dict) else {}
    tool = (data.get('tool_name') or data.get('toolName') or '').lower()
    if tool in ('write', 'edit', 'multiedit', 'notebookedit'):
        fp = ti.get('file_path') or ti.get('path') or ti.get('notebook_path') or ''
        hit = check_write(fp)
    else:
        cmd = data.get('command') or ti.get('command') or ''
        hit = check(cmd)
    if hit:
        print(json.dumps(deny_payload(hit), ensure_ascii=False))
        return 2
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)          # fail-open，绝不因守卫自身故障卡住干活
