# 交接摘要（handoff_latest）

> **用途**：换模型 / 新会话 / 换设备接手时，**先读这三项再动手**（core-8 `B-07`）。
> **纪律**：三项缺一 = 交接不完整；本文件由**当前主线负责人**在每次阶段收尾时更新，不写历史流水账。
> **机检**：`verify/tests/test_handoff.py` 查三项齐全 + 版本号与 `VERSION` 一致（过期即红）+ 第 4 段账目三齐（B-14）+ **三通道接手条款在位**（core-8 / 薄壳 / 手机指令各有一句"先读本文件"的动作）。

## 1. 当前主线（一句话）

**v0.8.76 熔铸司（foundry）W3 63 目录能力面全量迁入已收口**（0.8.76 主线内增量：不 bump 版本、不改技能 CHANGELOG、不动线上，与 W2 补丁同型、零新增欠账）：`capability_surface.json` 落 63 目录 / 349 文件 / 196 refs / 38 脚本 / 1458 章节的中性结构化登记（只摆目录名 + 计数 + 脚本名，不搬运技能正文、全量 63 目录不裁剪、不预设价值判断、边界由用户拍板），`registered=true / ported=false` **登记与补码转正分离**；`core.py` 加 `load_surface()`/`surface_ok()` 判据（病15「识别范围 = 对象范围」：逐目录验字段/类型/自洽 + 六维求和 ↔ totals 对账 + `CAPABILITY_63` 名册比对 + 分离态 + `SURFACE_ANCHORS` 独立硬锚防「清单 + totals 同步洗绿」），`--selftest` 正向真实态绿、反向 12 类能力面造错各自判红；`foundry.py` 加 `surface` 子命令（63 目录机检可回读）+ status 能力面行 + selftest 正反向。**机制修复（判据挂空病）**：W2 三套 selftest 一直只手工跑、从未进 `verify.sh` 执行路径，W3 把 `core.py`/`jadx_engine.py`/`foundry.py` 接电进仓库级段（`$TARGET` 真源，`--repo-only` 干净检出也在电，正向 ✓ / 缺失或失败 ✗ 不折叠成 opt）。**四条施工纪律**（沿用）：①`Next:` 三段式 + handoff P0 锚点每阶段前移；②问题从机制解决不跳过；③正反向 selftest 通过才落地、阶段性推 git；④遵守原有施工纪律。**判据**：四套 selftest 全绿、`foundry.py surface` 63/63 回读、契约 88✓/0✗/0⚠、口径 5✓、handoff 16✓、`bash verify.sh` 0✗/0⚠。**遗留**：W4 产出接入（`artifacts.json` 五类产出端到端落库 + `gate_archive_ledger.py` 的 `SKILLS` 硬编码 7 技能未含 foundry 的机制盲区）、W5 收口推送。

**W4 前置·防阻塞/效率/思考闸门三件闭环（本轮收口，用户临时插入的 P0 前置项，先于 W4 落地）**：根因是 B-11（后台与落盘）、B-04（并行）两条规则全是 `kind=manual / strength={} / impl=[]`（`verify/rule_map.json`），钩子只有 `next_anchor.py`/`stop_guard.py`，无执行层拦截——两次前台阻塞取输出让用户插不进话，正是 M-R121「写进册子≠改掉行为」的重演。按 B-08 走现成正门：不新建脚本、不改 install.sh，三件全接到 `guard_cmd.py`（硬拦截真源）+ `next_anchor.py`（UserPromptSubmit 注入真源）：① **bg_guard**——G7 前台 sleep≥30s（执行事实判定，命令起始位锚定，非文本词匹配）+ G8 60s 内 >50 条 Bash 工具洪水计数，复用现成 deny 协议；② **思考闸门**——UserPromptSubmit 每轮注入三问（定性：方案还是施工／探查：丢子代理不刷主会话／收尾：落点即停禁轮询禁前台 sleep），落点在数据流必经点（M-R107）；③ **纪律真源**——core-8 B-11 + rule_map `strength:{S1:hooks/guard_cmd.py}` 双向对账。`block=true` 取输出属 TaskOutput 工具、非 Bash matcher，本会话无法实证硬拦，按 B-02 记「无法判定」交纪律层，不假装拦到。**机制化修的 2 个真问题（没跳过）**：G7 首版误拦 `echo sleep 240`（病15 识别范围≠对象范围复发，改命令起始位锚定 + 反例固化）；`# impl: B-11 S1` 实物自报后 gate_scan 判漏登（补 strength 登记双向对齐）。**按纪律未做**：改手机指令粘贴区触发云端副本 STALE，写云端需用户拍板，已回退该处（思考闸门走钩子每轮注入，手机端同样生效、不丢能力）。**判据**：`test_guard_cmd` 78 例全绿（含 3 类正反 + 元变异 + 安装副本 sha 一致）、impl-reconcile 全绿、云端副本 FRESH、`bash verify.sh` rc=0 / 0✗/0⚠（2 个「无法判定」非警告）。

**经验闭环 v2 四环（①淬炼→④呈现→②复用→③进化，用户 2026-11-15 拍板「按1423做」，先于 W4 落地）**：诊断——用户给的旧生态经验池/技能进化机制（35 条池、`skill-evolution` 执行器）在 520 **一个不在盘**（v0.8.41 已退役），但 520 有半套散落钩子里的活机制（复发记账 + 同型坑注入 + 经验门闸），缺的是「进料口（坑/解法→经验）」和「状态出口（看不见）」。按 B-08 不新建经验池文件：在 `experience_recurrence.json` 加派生键 `exp_entries`（真源仍是台账 + git Lesson/Reuse trailers，可重建）。① **淬炼** `verify/exp_distill.py`：从近 60 条 commit 的 `Lesson:`/`Reuse:` + 台账派生 67 条经验，`_has_landing` 反稀释（M-R148：记病须台账核得到 / Reuse 须有路径，无落点不派生）、按 evidence 幂等、`--apply/--status/--hit/--selftest`。**踩的坑**：首版用 `trailers:valueonly` 解析丢键名致 0 命中（病15 同型——识别范围=值、对象范围=键值配对），改完整 `%B` 正则提键名。④ **呈现** `next_anchor.py` UserPromptSubmit 注入段升级：从只注入同型坑名 → 带出 `exp_entries` 里具体经验条目（💡经验 标记 + evidence，最多 2 条防洪水）。② **复用** `--hit <evidence>` 显式正门（注入≠复用，不自动计命中，防 67 条全假绿），保留态重派生不洗掉。③ **进化** `solidified` 由映射表 `destination=闸化` 派生（可核实落点）。**可观测** `verify/exp_probe.py`：一条命令回读四环「写✓ 读✓ 进化✓ 呈现✓」，死库存/假经验/未淬炼/缺呈现四类反向如实报、不折叠；实测 `写67/读1/进化3/呈现在`（本轮真实采用 1 条经验留痕，非刷分）。两脚本接电 `verify.sh`（M12 经验门段后，判据不在执行路径=挂空，同 W3 教训）。**判据**：`exp_distill`/`exp_probe` 双 `--selftest` 全绿（反稀释/幂等/抗洗绿/死库存/缺呈现），`bash verify.sh` 0✗/0⚠。**遗留**：W4 产出接入（foundry SKILLS 盲区 + 五类产出端到端落库）、W5 收口推送。

> W2 引擎上提与 26 工具接线（前置，详见 `78d068c`）：**做法**：`JadxMCP` 从能力层 `shellcrack.py` 上提到通用层 `foundry-core/scripts/jadx_engine.py`（独立命名避开与 `tvbox-core/core.py` 撞名、importlib 按路径加载不塞 sys.path、能力层反向复用调用行零改动，病15 `S233①` 五种后接形态判据保留）；`tools_schema.json` 补 26 个 `inputSchema`（`tools/list` 一手实测）+ 26 条真调配方（3 个 S233① 已用 + 23 个 P1/FIX-6 补调），`verified 26/26`，首轮 6 个假失败作 `bad_args_examples` 保留不删；修正 `core.py` 病15 复发（`chain_ok` 改查参数值不查键名）、新增 `schema_ok`（识别范围=对象范围，反向覆盖五种后接形态 + 洗绿造错）；引擎 `call()` 收敛死进程为 `PROC_DEAD` 三态。**本轮真调复验**：两独立 java 进程 `tools/list` 均 26 个、`load_apk` LOADED（22432 类），资源专项用 jadx 解码名 `AndroidManifest.xml`/`resources.arsc` 真调通、zip 原始路径报 `link-not-file`（闭环证明参数链规则②）；进程 B 反编译某类崩子进程如实记 `PROC_DEAD 13`（6/20 通）不折叠。**四条施工纪律**（沿用）：①`Next:` 三段式 + handoff P0 锚点每阶段前移；②问题从机制解决不跳过；③正反向 selftest 通过才落地、阶段性推 git；④遵守原有施工纪律。**判据**：`core.py`/`jadx_engine.py`/`foundry.py`/`shellcrack.py` 正反向 selftest 全绿、契约 C1–C11 全✓、`bash verify.sh` 0✗/0⚠、handoff 机检三齐且 P0 至多 1 条。**遗留**：W3 63 目录全量迁入、W4 三处登记 + 端到端落库、W5 收口推送。

**v0.8.76 提交后补丁（本轮收口）**：① 病15 第 13 例横向复发修复 —— `delivery_probe._closed()` 的 `msg_version` 核销凭据由「message 里任一 x.y.z 版本号」收紧为 `msg_anchors=[本 commit 短 sha, 本次 VERSION bump 目标版本]`（旧判据拿 W2 正文里的 v0.8.75／v0.8.4／1.1.0 命中 artifact-store v1.1.0 的他人回执，把 `D-78d068c-F04` 静默销掉；并坐实旧实现 `if msg_vers: … elif sha:` 连合法 sha 回执都核销不了的第二类缺陷）；9 例正反向入 `--selftest` 全绿、quotepath 回归 59/137 中文路径可见，病15 台账 12→13 次 + 实例/落点登记，F04 `source_event`/`producer` 口径同步（M5）。② **W2 补充真调复验如实记「无法判定」**：`/tmp/w2_realcall_verify.json` 因 java 子进程在第 3 步 `get_methods_of_class` 返回 UNKNOWN 后 `BrokenPipeError` 中止，`resource_probe` 未跑到（steps=3／真调通 2），属已知不稳定通道的一次降级 —— 不洗绿、不推翻已收口的 `verified 26/26`（其对象范围是 inputSchema 实测登记 + 真调配方在册且有证据，非本轮重跑 26 次 java，提交正文已辨析）。③ `--audit 20` 提交后实况 4 条内容流欠账（`D-d054c8d-F04` 历史／`D-78d068c-F04` W2 本轮／`D-13ea480-F02` 第13例方法论〔Lesson 型信号触发〕／`D-13ea480-F06` 第13例复盘判例〔改台账触发〕），比提交前账目多 1 条 F02，按 B-14「账目与落点冲突时以落点为准」补正列名。其中 13ea480 两条由 `verify.sh` 必经链路 `gate_archive_ledger` 的 `scan()` 如实入账为 open 并判红（B-10 拦截即停止：读真源确认 `--audit` 只读、写账本的是闸的 scan，非误操作非判据 bug）；真补落云端库属 W4（需 space-hub MCP，B-12 本轮不开新战线），故经探测器 `--waive` 正门显式豁免至 2026-12-31（三条件校验 + note 留痕 + 到期自动转 open，不改成 closed、不删账、不改判据）。另 2 条 F04 仍未入账，按「登记与补码转正分离」留 P2 账目，不伪造回执销账。复验 `bash verify.sh` rc=0 / 0✗、基线 open 0 / closed 68 / waived 24。④ W2 提交正文欠的阶段性推 git 已兑现：`78d068c` 与 `13ea480` 经 `hooks/git_push_safe.sh` 正门推送，远端确认 `main = 13ea480`（第 3 次重试，网络瞬时错误按指数退避处理）；`--list` 基线仍保持 open 0 / closed 68 / waived 22。

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
| P0 | 熔铸司 W4 产出接入：W3 已收口（63 目录能力面 63/63 登记 + 三套 selftest 接电 verify.sh）；`artifacts.json` 五类产出端到端落库、`gate_archive_ledger.py` 的 `SKILLS` 硬编码 7 技能未含 foundry 的机制盲区待修 | 我 | 先把 foundry 纳入 gate_archive_ledger 的 SKILLS 监测（消机制盲区），再将 artifacts.json 五类产出经 space-hub archive 正门端到端落库，正反向验证 + `bash verify.sh` 全绿后提交并阶段性推 git | W4 落库回执可回读 + 阶段性 git 推送完成 |
| P2 | 重采链路批量跑（123 个存活仓库）**挂起**：熔铸司施工期间不并行，原 P0 未收敛不删除 | 我 | W5 收口后由用户决定是否恢复：先跑 10 仓质量复核通过再放全量，成品库留入库回执 | W5 收口后用户重新批准批量 |
| P2 | 云端收件箱 2 个测试库待删 | 用户 | 在资料库 App 内手动点删 | 用户确认删除即完 |
| P2 | 26 条内容流旧账已豁免至 2026-12-31（quotepath 盲区期漏账，见病15 第 11 例）；到期由探测器自动转 open | 我 | 到期前复核：能真补的经 `archive` 落库核销，仍不补的重新豁免并写明继续不补的具体原因（不许转成 closed 洗绿） | 2026-12-31 |
| P2 | 手机端硬轨：App 无指令入口（2.8.0/2.9.1 两版实测）→ 每次新会话首条粘贴（14 条正文/13 条对应 B 编号；云端 doc v9） | 用户 | 每个新会话开始时，资料库打开「手机指令粘贴区（复制即用）」→ 从第 2 行起全选复制 → 作为该会话**第一条消息**发出，然后再提需求 | 已形成习惯（连续 2 个新会话都先粘贴）即算完 |
| P2 | GitHub 账号双因子 | 用户 | 在账号安全设置里开启 2FA | 2026-12-08 前 |
| P2 | 内容流欠账真补：`D-d054c8d-F04`（历史演进说明）／`D-78d068c-F04`（W2 演进说明）2 条仍未入账待真补；`D-13ea480-F02`（第13例方法论）／`D-13ea480-F06`（第13例复盘判例）2 条已如实入账并经 `--waive` 正门显式豁免至 2026-12-31（留痕、不假称已还） | 我 | 云端资料库可用时经 `space-hub archive` 正门逐条真补（W2 演进说明／第13例方法论与复盘判例／d054c8d 历史说明），补完在 `archive_ledger.json` 记 `event_ref` 指回本 commit 的回执核销；不许改成 closed 洗绿 | 2026-12-31 与既有 waived 同批复检 |
