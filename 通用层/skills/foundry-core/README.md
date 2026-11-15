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
| `manifest.json` | lib 版本号真源（C2/C4 对账用，替代 SKILL.md front matter） |
| `scripts/core.py` | 工具名册 + 参数链规则 + schema 装载 + `--selftest` 正反向 |
| `scripts/tools_schema.json` | 26 个工具的 inputSchema（W1 登记名册，W2 补码转正） |
| `CHANGELOG.md` | 变更凭证（C4 第三处） |
| `docs/TROUBLESHOOTING.md` | 按症状排的排障条目 |

## 版本四处

`manifest.json` / `CHANGELOG.md` 首条 / `verify/skill_contracts.json` / `MANIFEST.json` 通用层登记 —— 四处一致才算过 C4。

## 自检

```bash
python3 scripts/core.py --selftest
```

正反向：名册齐全应绿；工具数非 26、缺 manifest.json、参数链填了 JSON key、资源名用 zip 原始路径，四类造错必须各自翻红。
