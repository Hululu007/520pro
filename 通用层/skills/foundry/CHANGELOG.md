# foundry · 熔铸司 变更记录

> 版本号四处对账：`SKILL.md` front matter / `CHANGELOG.md` 首条 / `verify/skill_contracts.json` / `MANIFEST.json` 通用层登记（C4）。

## v1.1.0 — 2026-11-15

- **W2 引擎上提与 26 工具全量接线**：引擎真源 `foundry-core/scripts/jadx_engine.py` 落地（26 工具泛化）；`status` 增 `schema_ok` 转正判定 26/26、引擎真源与产出落点，`tools` 展示每个工具的 `inputSchema`/`required`/真调配方。
- **病15 单测覆盖五种后接形态**：`selftest` 正向加「真实配方含 `class_name` 键判绿」「转正 26/26 判绿」，反向加五种坏填法（JSON key 当类名/方法名、猜类名、占位符、zip 原始路径）+ 洗绿造错（verified 无 evidence、inputSchema=null）各自判红。造错用临时目录 + 内存深拷贝，不动真文件。
- **依赖方向归位**：通用层对能力层零依赖；能力层 `probe-hub/shellcrack.py` 反向 import 通用层引擎（收件方自持，调用行零改动，病15 闸化锚点 `S233①` 保留）。
- **判据**：`foundry.py selftest` 正向绿 / 反向全红、`core.py`/`jadx_engine.py`/`shellcrack.py` selftest 全绿、`bash verify.sh` 0✗/0⚠。版本四处对齐 0.8.76。

## v1.0.0 — 2026-11-15

- **W1 骨架登记**：通用层落 `foundry`（skill，平台可路由）+ `foundry-core`（lib，被 import 不注册）双件；契约表加两行、MANIFEST 通用层登记两件、registry 登记新真源类别。
- **横向能力面**：26 个 jadx MCP 工具名单（一手实测 `/tmp/tools_list_实测.json`）、63 目录能力面清单先登记、补码分批转正——登记与转正分离，不把「登记了」说成「迁移完了」。
- **产出声明**：`artifacts.json` 声明能力面对照 / 解码资产 / 板块演进 / 判例四类落点，接 `🧬 520进化论` 与 `📦 产物归档`；出口一律 `space_hub.archive_out` 正门。
- **正反向自检**：`foundry.py selftest` 覆盖「骨架齐全应绿 / 缺 SKILL.md、缺 manifest.json、工具数非 26 应红」四个形态；`foundry-core` 的 `core.py selftest` 覆盖参数链规则正反向。
- **阶段锚点**：提交信息 `Next:` 三段式 + `docs/handoff_latest.md` P0 账目，W0→W5 每阶段收口后 `Next:` 前移一格。
