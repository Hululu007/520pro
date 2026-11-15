# 交接摘要（handoff_latest）

> **用途**：换模型 / 新会话 / 换设备接手时，**先读这三项再动手**（core-8 `B-07`）。
> **纪律**：三项缺一 = 交接不完整；本文件由**当前主线负责人**在每次阶段收尾时更新，不写历史流水账。
> **机检**：`verify/tests/test_handoff.py` 查三项齐全 + 版本号与 `VERSION` 一致（过期即红）+ 第 4 段账目三齐（B-14）+ **三通道接手条款在位**（core-8 / 薄壳 / 手机指令各有一句"先读本文件"的动作）。

## 1. 当前主线（一句话）

v0.8.71 第二立项 **四壳逐个深入**（LeeCat→云取→MilkCode→Muse，产物 `references/S233_四壳深入_*.md`）：**LeeCat（294MB）**实测四种源语言——除 py/js 外新发现 **PHP 8.4 WASM 26MB**（`php-runtime/dispatcher.php` 常驻循环，协议与 py 完全同构，连 `pdfh/pdfa/pd` 都同名）与 `libfjs.so` 8.2MB；两条对我们直接有用的：①`spider_compat.py` 的 `Spider` + `source_loader.py` 的 `dialect='catvod'|'drpy'` → **`forge` 生成的源可直接跑**；②自带 `pycryptodome 3.21.0` → AES 兜底在此壳不必要，写源应按壳分档。**云取（32MB）纠正 S231**：不是壳，是 QuickJS 插件化**下载器**——`catvod`/`tvbox`/`spider`/`drpy` **全 0 命中**，`turbodl` 190 处、aria2 39 处；原判「仅支持 js/drpy 类源」不成立，移到「下载器参考」。**MilkCode（302MB）**：42MB jadx jar **抽出并实测可用**（MCP 握手 ✓，26 个 jadx 级工具，`load_apk` 云取 22432 类 / 14.8s），结论**可用但不入 git**；踩坑：`rea-preset.json` 那 24 个工具名是上层封装，照抄必 `Tool not found`。**Muse（42MB）**：除名确认，dex 字节计数 43588/765/19（订正 S231 的 grep 行数口径），`catvod`/`tvbox`/`spider` 全 0。**同期收口第一立项**（v0.8.70）：通道三件代码化 + 第 7 条金律升判据（46 源实测 5 处缺口）+ bdb 立项 S232 （第二种写源范式 DSL，但铁律③不做 DSL 实现故只做侦察）+ 订正 S231 过期标注 + 修三真缺陷（金律用例假绿 / imgproxy 三态折叠 / install.sh 引号丢搜索候选）。**遗留**：S233 §六 待办 3 条；批5 三项原样；22 条豁免账 2026-12-31 到期复检。

**下一步**：`git log -1 --format=%B | sed -n 's/^Next: //p'`（正文即细则）

> v0.8.40–52 已收口：`git show 1c5a2ae` / `f5973ae` / `c4d8bee` / `596c2d8` / `d7a92c2` / `ca47338` / `8176cff` / `1954613`。


## 2. 版本与位置

- 仓库根：当前 clone 目录（用 `pwd -P` 确认，不在本文件写死绝对路径）
- 版本：0.8.71
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
| P0 | S233 落地的两件事：①jadx MCP 接入 `probe shellcrack`（`load_apk`→`search_classes_by_keyword` 判源类型，替代现在 `strings` 粗扫）②写源按壳分档（有 pycryptodome 用原生 AES，未知用 `_aes_fallback`） | 我 | 先做①：对 LeeCat 真壳走通并给出「支持哪些源类型」的类名级证据；再做②：分档判据落 SKILL.md 且 selftest 覆盖两分支 | 两件各有落点证据 + verify 全绿 |
| P1 | 重采链路已通（IVTV2 一仓 50 条），**123 个存活仓库待批量跑**；成品库仍空 | 我 | 按存活清单批量 `harvest scan`（每仓 2-3 分钟，全量约 5 小时）→ filter 测活 → promote 写成品库；先跑 10 仓看质量再放全量 | 用户批准批量后 |
| P2 | 云端收件箱 2 个测试库待删 | 用户 | 在资料库 App 内手动点删 | 用户确认删除即完 |
| P2 | 26 条内容流旧账已豁免至 2026-12-31（quotepath 盲区期漏账，见病15 第 11 例）；到期由探测器自动转 open | 我 | 到期前复核：能真补的经 `archive` 落库核销，仍不补的重新豁免并写明继续不补的具体原因（不许转成 closed 洗绿） | 2026-12-31 |
| P2 | 手机端硬轨：App 无指令入口（2.8.0/2.9.1 两版实测）→ 每次新会话首条粘贴（14 条正文/13 条对应 B 编号；云端 doc v9） | 用户 | 每个新会话开始时，资料库打开「手机指令粘贴区（复制即用）」→ 从第 2 行起全选复制 → 作为该会话**第一条消息**发出，然后再提需求 | 已形成习惯（连续 2 个新会话都先粘贴）即算完 |
| P2 | GitHub 账号双因子 | 用户 | 在账号安全设置里开启 2FA | 2026-12-08 前 |
