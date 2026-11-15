# 交接摘要（handoff_latest）

> **用途**：换模型 / 新会话 / 换设备接手时，**先读这三项再动手**（core-8 `B-07`）。
> **纪律**：三项缺一 = 交接不完整；本文件由**当前主线负责人**在每次阶段收尾时更新，不写历史流水账。
> **机检**：`verify/tests/test_handoff.py` 查三项齐全 + 版本号与 `VERSION` 一致（过期即红）+ 第 4 段账目三齐（B-14）+ **三通道接手条款在位**（core-8 / 薄壳 / 手机指令各有一句"先读本文件"的动作）。

## 1. 当前主线（一句话）

v0.8.73 M12 经验门 yellow 机制级闸化消解（不改计数、靠机制消黄）：**背景**：`chk_contentflow` 判4 长期报「病15×7（须升【阻】或闸化）」⚠，而病15 其实早已闸化（S233① 词边界+8 形态 selftest）；`experience_recurrence.json` 是 hook 机器记账真源（doc 明写「AI 不手工记账」），改 count/status 消黄=洗绿，禁止。**正解**：判4 采信「已闸化登记」并实证落点——`verify/病号映射表.json` 病15 加结构化 `gate`（script/selftest/anchor/evidence/registered）；`通用层/skills/inspect-hub/scripts/chk_landing.py` 加 `_selftest_landed`/`_gate_landed`，用 **ast 结构化节点**认 selftest 函数定义+接电+判据锚点：注释与 docstring 造不出 FunctionDef/Call 故天然排除（本轮病15 同型坑「识别范围≠对象范围」：既防扫字样误收 docstring——镜像 `verify/gate_scan.py` 第6例，又防只认精确锚点漏判，五种后接写法全覆盖）。**三态不折叠**：登记+脚本存在+selftest 实证+锚点命中→green；无登记/脚本不存在/未接电/锚点不命中→仍 yellow；计数损坏→unknown。**判据**：`verify/gate_experience.py:_gate_selftest` 五形态全 True / 六反例全 False / 端到端（有 gate→green、gate 指向不存在文件→yellow、无登记→yellow）；真数据临时反向破坏（script 不存在/删 gate/锚点不匹配）三次均正确退回 yellow、还原回 green；`bash verify.sh` 明细不再含「须升【阻】或闸化」且 0 ✗。存证 `能力层/tvbox/skills/probe-hub/references/S235_M12经验门闸化登记消解.md`。**同期**：inspect-hub v1.4.3→1.4.4 四处对齐、`install.sh --user-skill` 重装消 C5、复发计数 count=7/active 原样未动。**遗留**：批5 三项原样；22 条豁免账 2026-12-31 到期复检；4 个 `destination=闸化` 病号（病1/病10/病11/病12）尚未登记 gate（当前非 hot、无现实黄项，见 §4 P0）。

**下一步**：`git log -1 --format=%B | sed -n 's/^Next: //p'`（正文即细则）

> v0.8.40–52 已收口：`git show 1c5a2ae` / `f5973ae` / `c4d8bee` / `596c2d8` / `d7a92c2` / `ca47338` / `8176cff` / `1954613`。


## 2. 版本与位置

- 仓库根：当前 clone 目录（用 `pwd -P` 确认，不在本文件写死绝对路径）
- 版本：0.8.73
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
| P0 | 闸化登记推广（B-15 同类排查）：`verify/病号映射表.json` 里 `destination=闸化` 共 5 个病号，本轮只有病15 登记了 `gate`，其余 4 个（病1/病10/病11/病12）仍无——一旦其中某个 count 涨到 ≥3 且未 retired，判4 会重新挂「须升【阻】或闸化」⚠。当前这 4 个 count=0 或已 retired、无现实黄项，但机制覆盖不全 | 我 | 逐个查其「机制落点」真源（`docs/通病台账.md` 对应行 / `verify/gate_scan.py` 的 `impl-reconcile` 等），能实证到「落点脚本+selftest」的补结构化 `gate`（复用 `_gate_landed`，不新建文件）；实证不到的在台账写明「暂不登记的具体原因」并保留为 yellow，不许造空 gate 骗绿。`gate_experience.py --selftest` 补一个「多病号混合」用例（部分有 gate/部分无→只对无 gate 的报 yellow） | 5 个闸化病号各有「已登记并实证」或「显式写明暂不登记原因」；`bash verify.sh` 明细 0 ✗ 且无「须升【阻】或闸化」；推 git |
| P1 | 重采链路已通（IVTV2 一仓 50 条），**123 个存活仓库待批量跑**；成品库仍空 | 我 | 按存活清单批量 `harvest scan`（每仓 2-3 分钟，全量约 5 小时）→ filter 测活 → promote 写成品库；先跑 10 仓看质量再放全量 | 用户批准批量后 |
| P2 | 云端收件箱 2 个测试库待删 | 用户 | 在资料库 App 内手动点删 | 用户确认删除即完 |
| P2 | 26 条内容流旧账已豁免至 2026-12-31（quotepath 盲区期漏账，见病15 第 11 例）；到期由探测器自动转 open | 我 | 到期前复核：能真补的经 `archive` 落库核销，仍不补的重新豁免并写明继续不补的具体原因（不许转成 closed 洗绿） | 2026-12-31 |
| P2 | 手机端硬轨：App 无指令入口（2.8.0/2.9.1 两版实测）→ 每次新会话首条粘贴（14 条正文/13 条对应 B 编号；云端 doc v9） | 用户 | 每个新会话开始时，资料库打开「手机指令粘贴区（复制即用）」→ 从第 2 行起全选复制 → 作为该会话**第一条消息**发出，然后再提需求 | 已形成习惯（连续 2 个新会话都先粘贴）即算完 |
| P2 | GitHub 账号双因子 | 用户 | 在账号安全设置里开启 2FA | 2026-12-08 前 |
