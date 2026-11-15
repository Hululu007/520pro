# foundry-core 变更记录

> 版本号四处对账：`manifest.json` / `CHANGELOG.md` 首条 / `verify/skill_contracts.json` / `MANIFEST.json` 通用层登记（C4，lib 类不走 SKILL.md）。

## v1.0.0 — 2026-11-15

- **W1 建核**：通用层 lib 落地，26 个 jadx MCP 工具名册（一手 `tools/list` 实测 26 个，非文档枚举的 25 个——S233 §3.2 漏了 `get_main_application_classes_names`）。
- **参数链规则**：①参数取上一步真实返回，方法名用 `items[0]`，不手敲类名；②资源名用 jadx 解码表，不用 zip 原始路径；③构造器写 `<init>` / `<clinit>`。三条均来自 23 工具真调的假失败复盘。
- **状态如实**：`tools_schema.json` 26 条 W1 只登记名册（`verified:false`），W2 逐个补 inputSchema 与真调参数；登记与转正分离，不把「登记了」说成「调通了」。
- **正反向自检**：`core.py --selftest` 覆盖名册 / 缺件 / 参数链 / 资源名四类，造错必须翻红。
