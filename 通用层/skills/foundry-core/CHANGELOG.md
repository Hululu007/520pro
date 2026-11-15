# foundry-core 变更记录

> 版本号四处对账：`manifest.json` / `CHANGELOG.md` 首条 / `verify/skill_contracts.json` / `MANIFEST.json` 通用层登记（C4，lib 类不走 SKILL.md）。

## v1.1.0 — 2026-11-15

- **W2 引擎上提**：新建 `scripts/jadx_engine.py`——把嵌在能力层 `shellcrack.py`、只硬编码 3 工具的 `JadxMCP` 泛化成 26 工具全量客户端（`call(name, args)` + 可注入 `FakeTransport`），上提到通用层。沿用 v0.8.4「收件方自持、调用行零改动」范式，能力层 importlib 按路径绑定反向复用。**独立命名、不塞 sys.path**：`probe.py` 注入的 `tvbox-core/core.py` 与内核同名，塞路径会劫持 `from core import http_get`（病15 对象范围坑）。
- **26 工具全量接线**：`tools_schema.json` 补 26 个 `inputSchema`（`tools/list` 一手实测）+ 26 条真调配方（`call_recipe.args/evidence/state`），`verified 26/26`（3 个 S233① 已用 + 23 个 P1/FIX-6 补调）。首轮 6 个假失败作 `bad_args_examples` 保留不删（B-18）。
- **修正病15 复发**：`chain_ok` 旧版用 `'class_name' in json.dumps(args)` 判坏，而 `class_name` 是 26 工具合法必填键名——会把真实配方全误判。改为查参数**值**（`_bad_value`：JSON key 字面量 / 占位符 / zip 原始路径前缀），六种合法形态 + 五种坏填法后接形态进 selftest。新增 `schema_ok`（识别范围=对象范围，不只看一个 `verified` 布尔；反向含洗绿造错 / inputSchema=null / 缺 required）。
- **引擎门面健壮性**：`call()` 把死进程的 `BrokenPipeError/OSError` 收敛成 `PROC_DEAD` 三态 dict，不抛、不假绿。
- **本轮真调复验**：两独立 java 进程 `tools/list` 均 26 个、`load_apk` LOADED（22432 类）；资源专项 `AndroidManifest.xml`/`resources.arsc` 用解码名真调通、zip 原始路径报 `link-not-file`（闭环证明参数链规则②）。进程 B 反编译某类崩子进程，如实记 `PROC_DEAD 13`（6/20 通）不折叠——属 jadx 服务端稳定性，非传输层缺陷。`w2_realcall` 佐证含 `honest_note`。
- **正反向自检**：`core.py --selftest` 与 `jadx_engine.py --selftest` 全绿；`shellcrack.py --selftest` 35 项（含病15 S233① 五种后接形态）改造后仍全绿。

## v1.0.0 — 2026-11-15

- **W1 建核**：通用层 lib 落地，26 个 jadx MCP 工具名册（一手 `tools/list` 实测 26 个，非文档枚举的 25 个——S233 §3.2 漏了 `get_main_application_classes_names`）。
- **参数链规则**：①参数取上一步真实返回，方法名用 `items[0]`，不手敲类名；②资源名用 jadx 解码表，不用 zip 原始路径；③构造器写 `<init>` / `<clinit>`。三条均来自 23 工具真调的假失败复盘。
- **状态如实**：`tools_schema.json` 26 条 W1 只登记名册（`verified:false`），W2 逐个补 inputSchema 与真调参数；登记与转正分离，不把「登记了」说成「调通了」。
- **正反向自检**：`core.py --selftest` 覆盖名册 / 缺件 / 参数链 / 资源名四类，造错必须翻红。
