# 交接摘要（handoff_latest）

> **用途**：换模型 / 新会话 / 换设备接手时，**先读这三项再动手**（core-8 `B-07`）。
> **纪律**：三项缺一 = 交接不完整；本文件由**当前主线负责人**在每次阶段收尾时更新，不写历史流水账。
> **机检**：`verify/tests/test_handoff.py` 查三项齐全 + 版本号与 `VERSION` 一致（过期即红）+ 第 4 段账目三齐（B-14）+ **三通道接手条款在位**（core-8 / 薄壳 / 手机指令各有一句"先读本文件"的动作）。

## 1. 当前主线（一句话）

v0.8.60 B-05 零明文凭证从「内容扫描」硬化到「动作前阻断」：`guard_cmd` 增 **G5**（`git add` 后跟凭据名即拦：`.env` / `.env.local` / `credentials.*` / `id_rsa` / `*.pem`，`.env.example` 与 `id_rsa.pub` 放行）与 **G6**（Write/Edit 目标在 git 仓内且是凭据名即拦，仓外放行）；`next_anchor` 加第二条 `matcher=Write|Edit` 注册（不动旧 Bash 那条，免迁移），install.sh 幂等补插。**两条都实测被平台阻断**：`git add .env` → probe `via=none+guard:G5, hit=true`；Write 到 `520pro/.env` → `via=write-guard:G6`。**顺带修真缺口**：`.gitignore` 原无 `.env`、`secret_scan.CRED_NAMES` 也不含它，批量 add（不带文件名，G5 判不了）可整包带走——已补 `.gitignore` 与 CRED_NAMES，让「未忽略未追踪即红」接住。回归 test_guard_cmd 58 例（含与 secret_scan 名单逐项对账）。**误报当场修掉（首版连拦三次）**：G5 初版用「命令里有 add」+「命令里有凭据名」两个独立条件，结果「批量暂存 + 提交说明里提到 `.env`」被判违例，第三次直接挡住了正常提交。已改为一条正则——凭据名必须紧跟 add、且与 add 之间无命令分隔符（`;` `&` `|` 换行）；13 条正反例全对，测试里补 3 条放行例。残余限制：把命令写进文本的场景（heredoc/字符串）仍会被拦，钩子只能看文本。**遗留：全量 123 个存活仓库批量重采仍未跑；B-07/B-09 两条可硬化项未做。**

**下一步**：`git log -1 --format=%B | sed -n 's/^Next: //p'`（正文即细则）

> v0.8.40–52 已收口：`git show 1c5a2ae` / `f5973ae` / `c4d8bee` / `596c2d8` / `d7a92c2` / `ca47338` / `8176cff` / `1954613`。


## 2. 版本与位置

- 仓库根：当前 clone 目录（用 `pwd -P` 确认，不在本文件写死绝对路径）
- 版本：0.8.60
- 远端：核对口径是 `git rev-parse HEAD` 与 `gh api repos/tvbox342078879/520pro/commits/main --jq .sha` **两值相等**——本文件不写死 sha，因为任何一次收尾提交都会让写死值过期（写方法不过期）；`ls-remote` 常因网络抖动超时，超时记「无法判定」不算通过
- 推送一律走 `hooks/git_push_safe.sh`，不裸 push
- 当前主线自检口径：`bash verify.sh` 应 **0 ✗ / 0 ⚠**；`python3 verify/skill_contract_check.py --require-mirror` 应无 ✗（体积项允许 ⚠）

## 3. 习惯快照指针（只指，不抄）

| 习惯 | 真源 |
|---|---|
| 十八条通用铁律 + 七条元规则 | `通用层/rules/core-8.md`（B-01…B-18 / M1–M7） |
| 规则↔验证器映射（哪条怎么查） | `verify/rule_map.json` |
| 台账四律判据（状态/指纹/幂等/退出码） | `verify/ledger_laws.py` + `verify/tests/test_ledger_laws.py` |
| 手机指令云端副本（nodeId/sha/条数） | `docs/手机指令云端副本.json`；写它的是 `sync_phone_directive.py`，判它的是 `verify.sh` |
| 旧生态规则去向（193 条） | `docs/规则迁移映射_193条.md` |
| 通病病历（反复犯的错） | `docs/通病台账.md`（与 `docs/遗留登记.md` 分工：病历 vs 待办） |
| 技能契约（版本四处对账 / 描述五组 / 样本 / 体积） | `verify/skill_contracts.json` |
| 施工纪律（中文 / 正反向才提交 / 顺手修 / 每章出报告） | 会话约定 + `docs/模板_阶段完工交付报告.md` |

> 不要在本文件里复制条文全文——抄一份就多一个会腐烂的副本（M2）。

## 4. 待办账目（三齐）

**级别**：`P0` 主线推进（**全表至多 1 条**，超了就是主次不分，`test_handoff.py` 直接红）；`P1` 有 due 且会阻断功能；`P2` 杂务/习惯，不阻断。`Next:` 必须对应那条 P0。

| 级别 | 事项 | owner | next | due |
|---|---|---|---|---|
| P1 | 重采链路已通（IVTV2 一仓 50 条），**123 个存活仓库待批量跑**；成品库仍空 | 我 | 按存活清单批量 `harvest scan`（每仓 2-3 分钟，全量约 5 小时）→ filter 测活 → promote 写成品库；先跑 10 仓看质量再放全量 | 用户批准批量后 |
| P2 | 云端收件箱 2 个测试库待删 | 用户 | 在资料库 App 内手动点删 | 用户确认删除即完 |
| P2 | 手机端硬轨：App 无指令入口（2.8.0/2.9.1 两版实测）→ 每次新会话首条粘贴（14 条正文/13 条对应 B 编号；云端 doc v9） | 用户 | 每个新会话开始时，资料库打开「手机指令粘贴区（复制即用）」→ 从第 2 行起全选复制 → 作为该会话**第一条消息**发出，然后再提需求 | 已形成习惯（连续 2 个新会话都先粘贴）即算完 |
| P2 | GitHub 账号双因子 | 用户 | 在账号安全设置里开启 2FA | 2026-12-08 前 |
