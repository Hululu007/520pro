# foundry-core · 熔铸司共享引擎内核

> **这不是技能**：本目录故意**没有 `SKILL.md`**（`verify/skill_contracts.json` 里 `kind: lib`）。
> 平台只注册带 SKILL.md 的目录；本件被 `foundry` 与能力层 `probe-hub` import，
> 不参与 description 路由，也不该被装进平台技能清单（分层落地表 D 档反例）。

## 为什么独立成 lib

26 个 jadx MCP 工具、参数链口径、能力面登记结构，是**横向**能力，不属于 TVBox 任何业务域。
放在能力层会被 `probe-hub` 的找源流程绑死；放在通用层才能被多个板块复用。
依赖方向遵守 `MANIFEST.json` changelog_0_8_4 的定案：**通用层对能力层零依赖**，
反向（能力层 import 通用层）合法。

## 目录内容

| 文件 | 作用 |
|---|---|
| `manifest.json` | lib 版本号真源（C2/C4 对账用，替代 SKILL.md front matter）；W2 起含 `engine` 指针 |
| `scripts/core.py` | 纯判据层：26 工具名册 + 参数链规则（查值不查键）+ schema 装载 + `schema_ok` 转正判定 + `--selftest` 正反向 |
| `scripts/jadx_engine.py` | 纯传输层（W2 上提）：`JadxMCP.call(name,args)` 泛化 26 工具 + `FakeTransport` 离线注入 + `--selftest`。**独立命名**：绝不叫 `core.py`（会与 `tvbox-core/core.py` 撞名），调用方 importlib 按路径加载、不塞 sys.path |
| `scripts/tools_schema.json` | 26 个工具的 inputSchema + 真调配方（W2 全量转正，verified 26/26；`bad_args_examples` 保留首轮反例） |
| `CHANGELOG.md` | 变更凭证（C4 第三处） |
| `docs/TROUBLESHOOTING.md` | 按症状排的排障条目 |

> **引擎与内核分工（M2 单一事实源）**：`jadx_engine.py` 只管传输（initialize / tools/list / tools/call），
> `core.py` 只管判据（名册 / 参数链 / schema 装载）；两者**互不 import**，判据只在 core 定义一次。
> 能力层 `probe-hub/shellcrack.py` 反向复用引擎（v0.8.4「收件方自持、调用行零改动」范式）。

## 自检

```bash
python3 scripts/core.py --selftest         # 判据层正反向（含 schema_ok 26/26、五种后接形态）
python3 scripts/jadx_engine.py --selftest  # 传输层正反向（FakeTransport / PROC_DEAD 三态）
```

正反向：名册 26 / schema 转正齐备应绿；工具数非 26、缺 manifest.json、`inputSchema=null`、
verified 无 evidence（洗绿）、参数链五种坏填法（JSON key 当类名/方法名、猜类名、占位符、
zip 原始路径）各自必须翻红。

## 版本四处

`manifest.json` / `CHANGELOG.md` 首条 / `verify/skill_contracts.json` / `MANIFEST.json` 通用层登记 —— 四处一致才算过 C4（见上方「## 自检」）。
