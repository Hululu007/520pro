#!/usr/bin/env bash
# 工程E T4 反向测试：四种破坏各自必须翻红，恢复后必须全绿
# 用法：bash verify/tests/test_rule_map_reverse.sh
set -u
R="$(cd "$(dirname "$0")/../.." && pwd)"
RM=$R/verify/rule_map.json
C8=$R/通用层/rules/core-8.md
cp "$RM" /tmp/rm.bak; cp "$C8" /tmp/c8.bak
run(){ python3 "$R/verify/terminology_check.py" --repo "$R" >/tmp/t4.out 2>&1; echo "rc=$? | $(grep '\[T4\]' /tmp/t4.out)"; }
restore(){ cp /tmp/rm.bak "$RM"; cp /tmp/c8.bak "$C8"; }

echo "【0】基线（应 rc=0 且 T4 ✓）"; run

echo "【1】删掉 B-05 映射（应红：规则无映射）"
python3 - <<'EOF'
import json;p='/workspace/520pro/verify/rule_map.json'
d=json.load(open(p,encoding='utf-8')); del d['rules']['B-05']
json.dump(d,open(p,'w',encoding='utf-8'),ensure_ascii=False,indent=2)
EOF
run; restore

echo "【2】锚点漂移 PATTERNS → PATTERNS_XX（应红）"
python3 - <<'EOF'
import json;p='/workspace/520pro/verify/rule_map.json'
d=json.load(open(p,encoding='utf-8')); d['rules']['B-05']['anchor']='PATTERNS_XX'
json.dump(d,open(p,'w',encoding='utf-8'),ensure_ascii=False,indent=2)
EOF
run; restore

echo "【3】core-8 删掉 B-07 尾注（应红：缺尾注 + 尾注不等）"
python3 - <<'EOF'
p='/workspace/520pro/通用层/rules/core-8.md'
t=open(p,encoding='utf-8').read().replace('｜验证 V-MANUAL-07','',1)
open(p,'w',encoding='utf-8').write(t)
EOF
run; restore

echo "【4】kind 写错（应红）"
python3 - <<'EOF'
import json;p='/workspace/520pro/verify/rule_map.json'
d=json.load(open(p,encoding='utf-8')); d['rules']['B-01']['kind']='auto'
json.dump(d,open(p,'w',encoding='utf-8'),ensure_ascii=False,indent=2)
EOF
run; restore

echo "【5】恢复后（应 rc=0 且 T4 ✓）"; run

echo "【6】规则预算：core-8 加到 21 条（应红：超过预算 20）"
python3 - <<'EOF'
import json, os, shutil, tempfile
t = tempfile.mkdtemp()
os.makedirs(os.path.join(t, '通用层', 'rules')); os.makedirs(os.path.join(t, 'verify'))
shutil.copy('/workspace/520pro/通用层/rules/core-8.md', os.path.join(t, '通用层', 'rules'))
shutil.copy('/workspace/520pro/verify/rule_map.json', os.path.join(t, 'verify'))
c8 = os.path.join(t, '通用层', 'rules', 'core-8.md')
lines = open(c8, encoding='utf-8').read().split('\n')
i = max(k for k, l in enumerate(lines) if l.startswith('18. **B-18'))
add = ['%d. **B-%d** 预算测试占位｜验证 V-MANUAL-%d' % (n, n, n) for n in (19, 20, 21)]
lines[i + 1:i + 1] = add
open(c8, 'w', encoding='utf-8').write('\n'.join(lines))
p = os.path.join(t, 'verify', 'rule_map.json')
d = json.load(open(p, encoding='utf-8'))
for n in (19, 20, 21):
    d['rules']['B-%d' % n] = {'verify_id': 'V-MANUAL-%d' % n, 'kind': 'manual',
                              'how': '占位', 'strength': {}, 'impl': [],
                              'proven_by': {'cmd': '', 'expect': '', 'got': ''},
                              'retire_if': ''}
json.dump(d, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
open('/tmp/budget_repo', 'w').write(t)
EOF
python3 "$R/verify/terminology_check.py" --repo "$(cat /tmp/budget_repo)" 2>&1 | grep -o "超过预算 20 条" | head -1
rm -rf "$(cat /tmp/budget_repo)" /tmp/budget_repo
