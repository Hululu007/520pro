# S234 · jadx 类名级壳侦察 与 写源按壳分档（S233 §六 两件事落地）

> 来源：v0.8.72 / probe-hub v1.28.9，承接 `S233_四壳深入_LeeCat云取MilkCodeMuse.md` §六 待办 2 条。
> 完成判据：①给出「LeeCat 支持哪些源类型」的**类名级证据**；②分档判据落 SKILL.md 且 selftest 覆盖两分支。
> 纪律：本文每条事实指回原文位置（文件 + 行号 / 命令输出原文），无出处项单列（B-18）。

## §1 真壳取证口径（可复跑）

```
java -jar jadx-headless-mcp-0.7.1-all.jar --transport stdio   # java 20，jar 不入 git
→ initialize ✓  serverInfo {name: jadx-headless-mcp, version: 0.7.1}  protocolVersion 2024-11-05
→ tools/list  → 26 个工具（真实工具名，非 rea-preset.json 里那 24 个封装名，见 S233 §3.3）
→ tools/call load_apk(LeeCatVodSimplify…-release.apk.1.1)
   {"state":"LOADED","class_count":7428,"raw_class_count":7428,
    "resource_count":1097,"load_duration_ms":9034,"threads":4}
→ tools/call search_classes_by_keyword(search_term, search_in='class', count=25)
```

封装正门：`tvbox probe shellcrack apk-types <APK> [--jar <path>] [--json]`，
实现 `scripts/shellcrack.py` 的 `JadxMCP` / `classify_shell_types()` / `probe_shell_types()`；
cli 注册 `scripts/probe.py` 的 `shellcrack apk-types` 子命令。jar 三路解析（`--jar` > `JADX_MCP_JAR` > 常见路径），
三路皆空记**无法判定**（返回码 3，不折叠成通过/失败，B-02）。

## §2 类名级证据（完成判据①）

LeeCat 真壳端到端输出（`python3 probe.py shellcrack apk-types <LeeCat.apk> --jar <jar>`，rc=0）：

| 源类型 | 判定 | raw | 词边界确认 | 子串误命中 | 类名级证据（FQN，前 3 条） |
|---|---|---|---|---|---|
| `python` | **supported** | 28 | 20 | 0 | `com.chaquo.python.internal.Common` / `com.chaquo.python.android.PyApplication` / `com.chaquo.python.android.AndroidPlatform` |
| `quickjs` | **supported** | 25 | 20 | 0 | `com.whl.quickjs.wrapper.QuickJSObject` / `QuickJSFunction` / `QuickJSContext` |
| `catvod` | **supported** | 25 | 20 | 0 | `com.lee.catvod.app.spider.SpiderService` / `SpiderActionActivity` / `DriveConfigActivity` |
| `spider` | **supported** | 10 | 10 | 0 | `com.lee.catvod.app.spider.SpiderService` / `com.github.catvod.crawler.SpiderNull` / `SpiderApi` |
| `php` | **undetermined** | 0 | 0 | 0 | 无类名证据 |
| `lua` | **undetermined** | 1 | 0 | **1** | `kotlin.internal.IntrinsicConstEvaluation`（`Eva[lua]tion` 子串，非 Lua 类） |
| `drpy` | **undetermined** | 0 | 0 | 0 | 无类名证据 |
| `pycryptodome` | **undetermined** | 1 | 0 | **1** | `org.bouncycastle.crypto.CipherParameters`（BouncyCastle，被关键词 `Crypto.Cipher` 子串命中） |

**结论（LeeCat 支持哪些源类型）**：类名级证据可实证 **py（chaquopy）/ js（QuickJS）/ CatVod-Spider 契约** 三条 Java 侧运行时；
与 S233 §1 的 assets 取证合并，LeeCat 完整支持 **py / js / php / lua 四种源语言 + `catvod` / `drpy` 双方言**。
`php`、`drpy`、`pycryptodome` 的类名 0 命中**不是「不支持」**——它们是 `assets/` 里的脚本/包，不在 dex 类里（见 §3）。

## §3 ★ 病15 同型坑：判据识别范围 ≠ 对象范围

| 层 | 事实 | 出处 |
|---|---|---|
| 识别范围 | `search_classes_by_keyword(search_in='class')` 只扫 **dex 的 7428 个 Java/Kotlin 类名** | 本文 §1 `class_count` |
| 对象范围 | 「壳支持哪些源类型」包含 `php-runtime/dispatcher.php`、`drpy3`、`cat.js`、`spider_compat.py`、`source_loader.py`、`pycryptodome 3.21.0` —— 全是 **assets 脚本/包**，不是类 | S233 §1.2 / §1.3；CHANGELOG v1.28.8 |
| 错误推法 | 「搜 `php` 0 命中 → LeeCat 不支持 PHP」 | 与 S232 包鉴定误判同型（病15 第 12 例） |
| 正确口径 | 0 命中一律 `undetermined`，note 写「assets 层，类名判据不覆盖；0 命中≠不支持，不判不支持」 | `shellcrack.py` `classify_shell_types()` |

**子串误命中不静默删（B-18）**：`lua` 与 `pycryptodome` 各有 1 条 raw 命中被词边界判据判为误命中，
输出仍保留在 `substring_only` 并打印 ⚠ 行。`raw_hits` / `class_evidence` / `substring_only` **三份账并列**，
删掉任一份都是另一种骗人。

**五种后接形态（本轮同型坑的具体形态，`_kw_in_fqn()` 覆盖，selftest 逐条断言）**：

| 形态 | 样例 FQN | 关键词 | 期望 |
|---|---|---|---|
| ① 精确段 | `com.github.catvod.crawler.spider` | spider | 确认 |
| ② 前缀后接 | `com.github.catvod.crawler.SpiderService` | spider | 确认 |
| ③ camelCase 拼接 | `com.whl.quickjs.wrapper.QuickJSContext` | quickjs | 确认（段小写以 quickjs 开头） |
| ④ 包名段 | `com.lee.catvod.app.spider.DriveConfigActivity` | spider | 确认 |
| ⑤ 大小写变体 | `com.lee.catvod.app.CatVod` | catvod | 确认 |
| 反向·子串误命中 | `kotlin.internal.IntrinsicConstEvaluation` | lua | **不确认**，单列 |
| 反向·无关类 | `okhttp3.Dispatcher` | php | 不确认、不计误命中 |
| 反向·段中非词首 | `org.foo.EvaluationHolder` | lua | 不确认，单列 |

> 只认「整行精确锚点」会把形态②③④⑤全漏掉——这正是病15 在本轮的具体复现。

## §4 写源按壳分档（完成判据②）

`scripts/shellcrack.py` 的 `choose_aes_variant(capability)`，三态：

| 壳能力 | 分支 | 理由 |
|---|---|---|
| 已知**有** pycryptodome（LeeCat 自带 3.21.0） | `native` → `from Crypto.Cipher import AES` | 原生最快，兜底在此壳不必要 |
| 已知**无**（羊壳） | `fallback` → `_aes_fallback.py` | 顶层 import Crypto 会让整个源在 import 阶段挂掉 |
| **未知 / 无法判定** | `fallback`（保守） | **不赌壳能力**（B-02），绝不返回 native |

判据落 `SKILL.md` §3.12.3；selftest 覆盖两分支 + 反向（未知绝不返回 native）+ 档案 dict 形态，
共 6 项。不删除既有兜底：别的壳没有 pycryptodome，兜底仍是唯一路径。

## §5 落点证据（B-13）

| 项 | 落点 | 结果 |
|---|---|---|
| 判据实现 | `能力层/tvbox/skills/probe-hub/scripts/shellcrack.py` | `JadxMCP` / `_kw_in_fqn` / `classify_shell_types` / `probe_shell_types` / `choose_aes_variant` |
| CLI 注册 | `scripts/probe.py` | `shellcrack apk-types` 子命令 + dispatch 条目 |
| 离线自检 | `python3 shellcrack.py --selftest` | 全绿（含 S233① 8 形态正反向 + ② 两分支） |
| 真壳端到端 | `python3 probe.py shellcrack apk-types <LeeCat.apk> --jar <jar>` | rc=0，7428 类 / 26 工具，输出见 §2 |
| 判据入册 | `SKILL.md` §3.16⑧ / §3.12.3 分档段 | 见本轮 commit |
| 版本 | `VERSION` / `MANIFEST.json` / `SKILL.md` / `CHANGELOG.md` / `verify/skill_contracts.json` | v0.8.72 / v1.28.9 四处一致 |

> 有出处 **N 条**（§1 命令原文 / §2 真壳输出 / §3 S233 §1.2-1.3 与 CHANGELOG v1.28.8 / §4 SKILL.md §3.12.3 / §5 各文件）；
> **0 条无出处推测**。未做的：`rea-preset.json` 24 名与 jar 26 工具的映射关系（S233 §六 第 4 条，本轮不需要，仍标「不可照抄」）。
