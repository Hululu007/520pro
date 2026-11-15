# 交接摘要（handoff_latest）

> **用途**：换模型 / 新会话 / 换设备接手时，**先读这三项再动手**（core-8 `B-07`）。
> **纪律**：三项缺一 = 交接不完整；本文件由**当前主线负责人**在每次阶段收尾时更新，不写历史流水账。
> **机检**：`verify/tests/test_handoff.py` 查三项齐全 + 版本号与 `VERSION` 一致（过期即红）+ 第 4 段账目三齐（B-14）+ **三通道接手条款在位**（core-8 / 薄壳 / 手机指令各有一句"先读本文件"的动作）。

## 1. 当前主线（一句话）

v0.8.76 熔铸司（foundry）W2 引擎上提与 26 工具全量接线已收口：**做法**：`JadxMCP` 从能力层 `shellcrack.py` 上提到通用层 `foundry-core/scripts/jadx_engine.py`（独立命名避开与 `tvbox-core/core.py` 撞名、importlib 按路径加载不塞 sys.path、能力层反向复用调用行零改动，病15 `S233①` 五种后接形态判据保留）；`tools_schema.json` 补 26 个 `inputSchema`（`tools/list` 一手实测）+ 26 条真调配方（3 个 S233① 已用 + 23 个 P1/FIX-6 补调），`verified 26/26`，首轮 6 个假失败作 `bad_args_examples` 保留不删；修正 `core.py` 病15 复发（`chain_ok` 改查参数值不查键名）、新增 `schema_ok`（识别范围=对象范围，反向覆盖五种后接形态 + 洗绿造错）；引擎 `call()` 收敛死进程为 `PROC_DEAD` 三态。**本轮真调复验**：两独立 java 进程 `tools/list` 均 26 个、`load_apk` LOADED（22432 类），资源专项用 jadx 解码名 `AndroidManifest.xml`/`resources.arsc` 真调通、zip 原始路径报 `link-not-file`（闭环证明参数链规则②）；进程 B 反编译某类崩子进程如实记 `PROC_DEAD 13`（6/20 通）不折叠。**四条施工纪律**（沿用）：①`Next:` 三段式 + handoff P0 锚点每阶段前移；②问题从机制解决不跳过；③正反向 selftest 通过才落地、阶段性推 git；④遵守原有施工纪律。**判据**：`core.py`/`jadx_engine.py`/`foundry.py`/`shellcrack.py` 正反向 selftest 全绿、契约 C1–C11 全✓、`bash verify.sh` 0✗/0⚠、handoff 机检三齐且 P0 至多 1 条。**遗留**：W3 63 目录全量迁入、W4 三处登记 + 端到端落库、W5 收口推送。

**v0.8.76 提交后补丁（本轮收口）**：① 病15 第 13 例横向复发修复 —— `delivery_probe._closed()` 的 `msg_version` 核销凭据由「message 里任一 x.y.z 版本号」收紧为 `msg_anchors=[本 commit 短 sha, 本次 VERSION bump 目标版本]`（旧判据拿 W2 正文里的 v0.8.75／v0.8.4／1.1.0 命中 artifact-store v1.1.0 的他人回执，把 `D-78d068c-F04` 静默销掉；并坐实旧实现 `if msg_vers: … elif sha:` 连合法 sha 回执都核销不了的第二类缺陷）；9 例正反向入 `--selftest` 全绿、quotepath 回归 59/137 中文路径可见，病15 台账 12→13 次 + 实例/落点登记，F04 `source_event`/`producer` 口径同步（M5）。② **W2 补充真调复验如实记「无法判定」**：`/tmp/w2_realcall_verify.json` 因 java 子进程在第 3 步 `get_methods_of_class` 返回 UNKNOWN 后 `BrokenPipeError` 中止，`resource_probe` 未跑到（steps=3／真调通 2），属已知不稳定通道的一次降级 —— 不洗绿、不推翻已收口的 `verified 26/26`（其对象范围是 inputSchema 实测登记 + 真调配方在册且有证据，非本轮重跑 26 次 java，提交正文已辨析）。③ `--audit 20` 修复后如实浮现 2 条未入账 F04 欠账（`D-d054c8d-F04` 历史／`D-78d068c-F04` W2 本轮），按「登记与补码转正分离」口径入账目，不伪造回执销账。

**下一步**：`git log -1 --format=%B | sed -n 's/^Next: //p'`（正文即细则）

> v0.8.40–52 已收口：`git show 1c5a2ae` / `f5973ae` / `c4d8bee` / `596c2d8` / `d7a92c2` / `ca47338` / `8176cff` / `1954613`。


## 2. 版本与位置

- 仓库根：当前 clone 目录（用 `pwd -P` 确认，不在本文件写死绝对路径）
- 版本：0.8.76
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
| P0 | 熔铸司 W3 63 目录全量迁入：W2 已收口（26 工具接线 verified 26/26，引擎已上提通用层）；63 目录能力面清单待 W3 迁入 | 我 | 先全量登记 63 目录能力面（登记与补码转正分离），逐目录补码后 `bash verify.sh` 全绿提交并阶段性推 git | W3 正反向 selftest 通过 + 阶段性 git 推送完成 |
| P2 | 重采链路批量跑（123 个存活仓库）**挂起**：熔铸司施工期间不并行，原 P0 未收敛不删除 | 我 | W5 收口后由用户决定是否恢复：先跑 10 仓质量复核通过再放全量，成品库留入库回执 | W5 收口后用户重新批准批量 |
| P2 | 云端收件箱 2 个测试库待删 | 用户 | 在资料库 App 内手动点删 | 用户确认删除即完 |
| P2 | 26 条内容流旧账已豁免至 2026-12-31（quotepath 盲区期漏账，见病15 第 11 例）；到期由探测器自动转 open | 我 | 到期前复核：能真补的经 `archive` 落库核销，仍不补的重新豁免并写明继续不补的具体原因（不许转成 closed 洗绿） | 2026-12-31 |
| P2 | 手机端硬轨：App 无指令入口（2.8.0/2.9.1 两版实测）→ 每次新会话首条粘贴（14 条正文/13 条对应 B 编号；云端 doc v9） | 用户 | 每个新会话开始时，资料库打开「手机指令粘贴区（复制即用）」→ 从第 2 行起全选复制 → 作为该会话**第一条消息**发出，然后再提需求 | 已形成习惯（连续 2 个新会话都先粘贴）即算完 |
| P2 | GitHub 账号双因子 | 用户 | 在账号安全设置里开启 2FA | 2026-12-08 前 |
| P2 | 内容流 F04/F06 欠账真补：`--audit 20` 浮现 `D-d054c8d-F04`（历史）／`D-78d068c-F04`（W2 演进说明）2 条未入账，本轮改台账提交后会命中 F06 diff_paths 再浮现 1 条复盘判例 | 我 | 云端资料库可用时经 `space-hub archive` 正门逐条真补（W2 演进说明／第13例复盘判例／d054c8d 历史说明），补完在 `archive_ledger.json` 记 `event_ref` 指回本 commit 的回执核销；不许改成 closed 洗绿 | 2026-12-31 与既有 waived 同批复检 |
