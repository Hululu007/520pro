# foundry · 熔铸司 变更记录

> 版本号四处对账：`SKILL.md` front matter / `CHANGELOG.md` 首条 / `verify/skill_contracts.json` / `MANIFEST.json` 通用层登记（C4）。

## v1.0.0 — 2026-11-15

- **W1 骨架登记**：通用层落 `foundry`（skill，平台可路由）+ `foundry-core`（lib，被 import 不注册）双件；契约表加两行、MANIFEST 通用层登记两件、registry 登记新真源类别。
- **横向能力面**：26 个 jadx MCP 工具名单（一手实测 `/tmp/tools_list_实测.json`）、63 目录能力面清单先登记、补码分批转正——登记与转正分离，不把「登记了」说成「迁移完了」。
- **产出声明**：`artifacts.json` 声明能力面对照 / 解码资产 / 板块演进 / 判例四类落点，接 `🧬 520进化论` 与 `📦 产物归档`；出口一律 `space_hub.archive_out` 正门。
- **正反向自检**：`foundry.py selftest` 覆盖「骨架齐全应绿 / 缺 SKILL.md、缺 manifest.json、工具数非 26 应红」四个形态；`foundry-core` 的 `core.py selftest` 覆盖参数链规则正反向。
- **阶段锚点**：提交信息 `Next:` 三段式 + `docs/handoff_latest.md` P0 账目，W0→W5 每阶段收口后 `Next:` 前移一格。
