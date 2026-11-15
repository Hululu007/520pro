# 交接摘要（handoff_latest）

> **用途**：换模型 / 新会话 / 换设备接手时，**先读这三项再动手**（core-8 `B-07`）。
> **纪律**：三项缺一 = 交接不完整；本文件由**当前主线负责人**在每次阶段收尾时更新，不写历史流水账。
> **机检**：`verify/tests/test_handoff.py` 查三项齐全 + 版本号与 `VERSION` 一致（过期即红）+ 第 4 段账目三齐（B-14）+ **三通道接手条款在位**（core-8 / 薄壳 / 手机指令各有一句"先读本文件"的动作）。

## 1. 当前主线（一句话）

v0.8.74 闸化登记推广（B-15 同类排查）已收口：**背景**：v0.8.73 只给病15 补了结构化 `gate`，`verify/病号映射表.json` 里 `destination=闸化` 共 5 病号，其余 4 个（病1/病10/病11/病12）无——一旦某个 count 涨到 ≥3 且未 retired，判4 会重新挂「须升【阻】或闸化」⚠。**做法**：全仓 122 个 `.py` 用 `_gate_landed` 实扫（13 个可实证），逐个查 `docs/通病台账.md` 机制落点真源；结论 4 个**全部暂不登记**——闸本体 `gate_scan.py` 无 selftest 定义、`test_*.py` 由 `verify.sh` 直接执行未接电、`verify.sh` grep 段非 Python，均无「落点脚本+selftest」可实证。**三条不做的理由**（文首小节详载）：①不拿 `delivery_probe.selftest_quotepath` 同型脚本冒充（它测 `read_commits`，病10 闸是 `gate_scan --gate quotepath`，同根因不同对象 = 病15「识别范围≠对象范围」）；②不扩展 `_selftest_landed` 或给脚本硬加 `--selftest` 来迁就登记（改判据≠补登记）；③不改 `experience_recurrence.json`、4 个 `gate` 保持缺失（不洗绿、不造空 gate，将来 hot 如实报黄）。**判据**：`gate_experience.py --selftest` 补「多病号混合」用例（部分有/部分无/含 retired 非 hot），A/B/C yellow、D green + 原有五形态/六反例/端到端全过；`bash verify.sh` 0 ✗ 且判据明细无「须升【阻】或闸化」；`docs/通病台账.md` 文首集中登记 5 病号结论、各段留指针（M2）；`verify/病号映射表.json` doc 补契约。**遗留**：批5 三项原样；22 条豁免账 2026-12-31 到期复检；4 个闸化病号仍无 gate（机制状态，非待办）。

**下一步**：`git log -1 --format=%B | sed -n 's/^Next: //p'`（正文即细则）

> v0.8.40–52 已收口：`git show 1c5a2ae` / `f5973ae` / `c4d8bee` / `596c2d8` / `d7a92c2` / `ca47338` / `8176cff` / `1954613`。


## 2. 版本与位置

- 仓库根：当前 clone 目录（用 `pwd -P` 确认，不在本文件写死绝对路径）
- 版本：0.8.74
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
| P0 | 重采链路批量跑：IVTV2 一仓 50 条已通，**123 个存活仓库待批量跑**，成品库仍空 | 我 | 用户批准批量后先跑 10 仓看质量，再按存活清单全量 `harvest scan` → filter 测活 → promote 写成品库 | 用户批准批量后；10 仓质量复核通过再放全量 |
| P2 | 云端收件箱 2 个测试库待删 | 用户 | 在资料库 App 内手动点删 | 用户确认删除即完 |
| P2 | 26 条内容流旧账已豁免至 2026-12-31（quotepath 盲区期漏账，见病15 第 11 例）；到期由探测器自动转 open | 我 | 到期前复核：能真补的经 `archive` 落库核销，仍不补的重新豁免并写明继续不补的具体原因（不许转成 closed 洗绿） | 2026-12-31 |
| P2 | 手机端硬轨：App 无指令入口（2.8.0/2.9.1 两版实测）→ 每次新会话首条粘贴（14 条正文/13 条对应 B 编号；云端 doc v9） | 用户 | 每个新会话开始时，资料库打开「手机指令粘贴区（复制即用）」→ 从第 2 行起全选复制 → 作为该会话**第一条消息**发出，然后再提需求 | 已形成习惯（连续 2 个新会话都先粘贴）即算完 |
| P2 | GitHub 账号双因子 | 用户 | 在账号安全设置里开启 2FA | 2026-12-08 前 |
