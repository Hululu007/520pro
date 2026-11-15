# 交接摘要（handoff_latest）

> **用途**：换模型 / 新会话 / 换设备接手时，**先读这三项再动手**（core-8 `B-07`）。
> **纪律**：三项缺一 = 交接不完整；本文件由**当前主线负责人**在每次阶段收尾时更新，不写历史流水账。
> **机检**：`verify/tests/test_handoff.py` 查三项齐全 + 版本号与 `VERSION` 一致（过期即红）+ 第 4 段账目三齐（B-14）+ **三通道接手条款在位**（core-8 / 薄壳 / 手机指令各有一句"先读本文件"的动作）。

## 1. 当前主线（一句话）

v0.8.72 S233 §六 收口（两件事全落地）：**①jadx 类名级壳侦察**——`能力层/tvbox/skills/probe-hub/scripts/shellcrack.py` 增 `JadxMCP`/`_kw_in_fqn`/`classify_shell_types`/`probe_shell_types`，`probe.py` 注册 `shellcrack apk-types <APK> [--jar]`，替代 `strings` 粗扫；LeeCat 真壳走通（7428 类 / 26 工具 / rc=0）给出类名级证据：`python`→`com.chaquo.python.*`、`quickjs`→`com.whl.quickjs.wrapper.*`、`catvod`/`spider`→`com.lee.catvod.app.spider.*` 判 supported；`php`/`drpy`/`pycryptodome` 在 assets 脚本层、类名 0 命中记「无法判定」**不判不支持**（病15 同型：识别范围仅 dex 类名 ≠ 对象范围含 assets 脚本）；词边界确认覆盖 5 种后接形态、8 形态正反向进 selftest，真壳抓到 2 处子串误命中（`IntrinsicConstEvaluation` / `bouncycastle.crypto.CipherParameters`）单列不删（B-18）。**②写源按壳分档**——`choose_aes_variant()` 三态（有 pycryptodome→`native`、无/未知→`fallback`，未知一律保守兜底不赌壳能力 B-02），判据落 `SKILL.md §3.12.3`、selftest 覆盖两分支+反向+dict 共 6 项；存证 `references/S234_jadx类名级壳侦察与写源分档.md`。**同期收口**：补 `43570e8` 两条落库欠账（F02 方法论 / F04 演进时间线，经 space-hub `archive` 正门核销，open 0）；SKILL.md 41.0→39.74KB 消 C7 WARN（12 处史料段按 M2 指针化，判据主干全留）；版本四处升 v0.8.72 / v1.28.9。**遗留**：M12 经验门病15×7 黄项按真源约定不手工消（见 §4 P0）；批5 三项原样；22 条豁免账 2026-12-31 到期复检。

**下一步**：`git log -1 --format=%B | sed -n 's/^Next: //p'`（正文即细则）

> v0.8.40–52 已收口：`git show 1c5a2ae` / `f5973ae` / `c4d8bee` / `596c2d8` / `d7a92c2` / `ca47338` / `8176cff` / `1954613`。


## 2. 版本与位置

- 仓库根：当前 clone 目录（用 `pwd -P` 确认，不在本文件写死绝对路径）
- 版本：0.8.72
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
| P0 | M12 经验门 yellow 的机制级闸化消解：病15×7 的「须升【阻】或闸化」提醒，本轮已闸化（词边界+8 形态 selftest+三态不折叠）但 `chk_contentflow` 判据不认，明细仍挂 ⚠（按真源约定不手工改计数） | 我 | `通用层/skills/inspect-hub/scripts/chk_landing.py` 的 `chk_contentflow` 加「已闸化登记」识别（病号有 `gate` 落点且落点脚本+selftest 存在→报 green，不再报 yellow），并在 `gate_experience.py --selftest` 补正反向（有 gate→green / gate 指向不存在文件→仍 yellow） | verify 明细不含「须升【阻】或闸化」且 0 ✗，推 git |
| P1 | 重采链路已通（IVTV2 一仓 50 条），**123 个存活仓库待批量跑**；成品库仍空 | 我 | 按存活清单批量 `harvest scan`（每仓 2-3 分钟，全量约 5 小时）→ filter 测活 → promote 写成品库；先跑 10 仓看质量再放全量 | 用户批准批量后 |
| P2 | 云端收件箱 2 个测试库待删 | 用户 | 在资料库 App 内手动点删 | 用户确认删除即完 |
| P2 | 26 条内容流旧账已豁免至 2026-12-31（quotepath 盲区期漏账，见病15 第 11 例）；到期由探测器自动转 open | 我 | 到期前复核：能真补的经 `archive` 落库核销，仍不补的重新豁免并写明继续不补的具体原因（不许转成 closed 洗绿） | 2026-12-31 |
| P2 | 手机端硬轨：App 无指令入口（2.8.0/2.9.1 两版实测）→ 每次新会话首条粘贴（14 条正文/13 条对应 B 编号；云端 doc v9） | 用户 | 每个新会话开始时，资料库打开「手机指令粘贴区（复制即用）」→ 从第 2 行起全选复制 → 作为该会话**第一条消息**发出，然后再提需求 | 已形成习惯（连续 2 个新会话都先粘贴）即算完 |
| P2 | GitHub 账号双因子 | 用户 | 在账号安全设置里开启 2FA | 2026-12-08 前 |
