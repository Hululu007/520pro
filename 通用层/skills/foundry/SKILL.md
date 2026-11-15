---
name: foundry
version: "1.1.0"
description: "当用户说「逆向工程」「扒 APK」「类源码」「能力迁移」「工具接线」时使用本技能。熔铸司·520 横向工具能力板块：把 jadx MCP 26 个工具、63 份技能目录的能力面完整承接进 520 生态，产出可落库。适用于 APK 逆向侦察、类级源码提取、工具能力盘点、跨项目技能迁移、能力面对照。触发词：逆向工程 / 扒 APK / 类源码 / jadx / 能力迁移 / 工具接线 / 能力面对照 / 横向采集 / 熔铸 / 工具盘点。能力：①jadx 26 工具真调（类/方法/字段/资源/xref 解码）；②63 目录能力面登记与分批补码；③产出经 archive_out 正门接 520进化论与资料库；④env-audit A/B/C 两级验证。不要用于：TVBox 找源/测活/写源（归 probe-hub）；不要用于学习资料整理（归 learn-hub）；不要用于云端建库/搬移（归 space-hub）。正门 scripts/foundry.py，先读 SKILL.md 判据再动手。"
allowed-tools: Read, Grep, Glob, Bash
---

# foundry · 熔铸司（520 横向工具能力板块）

> **第一动作（自省锚点）**：命中触发词后**先读本技能全文**再动手，不许看见脚本就直接跑——
> 判据在本文件与 `foundry.py --selftest`，不在记忆里。跳过判据动手，等于没有判据。

> 通用铁律由 `core-8.md` + 薄壳 + 手机指令三通道全局强制，本技能直接继承、不重复声明（M2）。

## 何时使用

- 触发词（唯一真源）：逆向工程 / 扒 APK / 类源码 / jadx / 能力迁移 / 工具接线 / 能力面对照 / 横向采集 / 熔铸 / 工具盘点
- 用户要把外部工具能力（APK 逆向、类级源码、工具链）**横向**接进 520 生态，而不是某个业务域的纵向深挖。

## 与现有板块的分工（不越界）

| 板块 | 领域 | 本板块关系 |
|---|---|---|
| probe-hub（探源司） | TVBox 上游侦察、找源、写源 | 纵向业务域；本板块只提供**通用工具引擎**，不接它的找源流程 |
| learn-hub（学习工坊） | 学习资料采集/精炼/入库 | 纵向业务域；产出落库走同一 `archive_out` 正门，但不复用其资料树 |
| space-hub（库务司） | 云端空间治理、归档、索引 | **本板块的产出承接方**，落库一律走它，不自造上传通道 |
| foundry-core | 无 SKILL.md 的共享库 | 本板块的引擎内核，被 import，不注册、不路由 |

## 正门（`scripts/foundry.py`）

| 命令 | 作用 |
|---|---|
| `python3 scripts/foundry.py status` | 打印板块状态：登记工具数、verified 26/26 转正判定、63/63 能力面登记判定、引擎真源、当前施工阶段、产出落点 |
| `python3 scripts/foundry.py tools` | 列出 26 个 jadx MCP 工具的 inputSchema / required / 真调参数配方（真源 `tools_schema.json`） |
| `python3 scripts/foundry.py surface` | 列出 63 目录能力面清单（W3 全量登记）：目录名 + 文件/refs/脚本/章节计数 + 机检回读判定；真源 `foundry-core/scripts/capability_surface.json` |
| `python3 scripts/foundry.py cap [id]` | W6 补码检索：无参列 63 域补码资产清单（落点/签名数/port 状态），带 id 回读某域一手落点（定位+计数+脚本签名）；真源 `foundry-core/assets/capability_63/` |
| `python3 scripts/foundry.py selftest` | 正反向验证：骨架+转正 26/26+能力面 63/63+补码 port_ok 应绿、缺件/坏填法/洗绿/能力面多形态/补码事实造假（落点缺失/sha 失配/签名缺失）应红 |

## 工作流

1. **先验**：`status` 确认骨架与 `schema_ok` 转正判定 26/26 绿、`surface_ok` 能力面 63/63 登记判定绿，不许凭印象说"接好了"。
2. **取工具面**：`tools` 读 26 个 inputSchema + 真调配方；调用走 `foundry-core/scripts/jadx_engine.py` 的 `call(name, args)`（W2 已上提泛化，能力层 shellcrack 反向复用）；参数一律取**上一步真实返回**（`items[0]`、解码资源名、构造器 `<init>/<clinit>`），不手敲类名。
3. **能力面**：`surface` 读 63 目录能力面清单（W3 已 63/63 全量登记，`capability_surface.json`）；清单是**中性结构化登记**，只摆目录名与计数、不搬运技能正文、不预设裁剪，边界由用户拍板。判据 `surface_ok` 逐目录验字段 + 六维求和对账 + 名册比对 + 独立硬锚，病15「识别范围 = 对象范围」。
3b. **补码（W6，用户拍板「全量转正·中性摆出」）**：一手真源从 `/tmp` 迁入 `foundry-core/assets/capability_63/`（63 域全量、脱离临时区），`cap [id]` 可回读。`ported=true` 由 `port_ok` 正向判据背书（资产落点 + 签名数 = n_exe + 真源 sha + 六维自洽），**不做任何价值分级/敏感判断/裁剪**——63 域一视同仁。注意：只迁结构化元数据（desc/positioning 摘要/脚本签名），不搬脚本正文与 mech/refs 全文；「补码落仓」指一手事实资产在册可检索，不等于 63 域脚本已在本地跑通。
4. **产出**：解码结果、能力对照、判例文档经 `space_hub.archive_out(path, source=..., note=..., target=...)` 落库，回执写 `archive_ledger.json`；失败记 `local_pending(待归档)`，由 `products --retry` 补投，绝不把"没落库"说成"已归档"。
5. **验证**：`selftest` 正反向通过才允许宣布该阶段完成；`bash verify.sh` 0✗/0⚠ 是阶段收口的硬判据。

## 三态与边界

- 工具调用只判 **真阳性 / 真阴性 / 无法判定**；报错、超时、被拦截一律记「无法判定」，不折叠成失败或成功。
- 解码资源名与 zip 原始路径是两回事；`get_resource_file` 必须用 jadx 解码后的资源名，拿原始 zip 路径调会一直报 `resource is a link, not a file`。
- 不替用户决定吸收范围与板块边界；全量素材中性摆出，边界由用户拍板。

## 施工阶段（真源在 `docs/handoff_latest.md` 的 P0 账目）

W0 锚点 → W1 骨架登记 → W2 引擎上提与 26 工具接线 → W3 63 目录全量迁入 → W4 产出接入 → W5 收口推送。
每阶段「正反向验证通过才落地，之后阶段性推 git」，`Next:` 三段式即进度锚点。
