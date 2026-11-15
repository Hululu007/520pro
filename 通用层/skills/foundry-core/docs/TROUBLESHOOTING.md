# foundry-core 故障排查（按症状排）

## 1. import foundry_core 报 ModuleNotFoundError

症状：`foundry.py` 或 `shellcrack.py` 找不到内核。
处置：本 lib 装在 `~/.codebuddy/skills/foundry-core/`（用户级），`sys.path` 要指向其 `scripts/`。
不要把 core.py 复制进能力层——那会造出第二份真源，改一处漏一处（M1/M2）。

## 2. 工具数报 25 而不是 26

症状：`names_ok` 红，或有人按 S233 §3.2 的文档表补名册。
处置：文档枚举漏了 `get_main_application_classes_names`；以 `tools/list` 实测
（`/tmp/tools_list_实测.json`，26 个）为准。仓库是真源，文档不是（B-06）。

## 3. tools/call 报 `see get_methods_of_class for the exact name`

症状：方法名填了 JSON key `class_name`，或手敲了一个不存在的类名。
处置：方法名取 `get_methods_of_class` 返回首项（`items[0]`，如 `onCreate` / `$stable`），
类名取 `get_main_application_classes_names` 的返回。真调首轮 6 个假失败全是这个根因。

## 4. get_resource_file 报 `resource is a link, not a file`

症状：40 个 zip 原始路径候选全失败。
处置：zip 原始路径 ≠ jadx 解码资源名。先 `list_resource_files`，用解码后的
`AndroidManifest.xml` / `resources.arsc` 调；实证见 `/tmp/resource_file_实测.json`。

## 5. C4 报版本四处不一致

症状：契约机检 C4 红，lib 的 `manifest.json` 版本与别处对不上。
处置：四处是 `manifest.json` / `CHANGELOG.md` 首条 / `skill_contracts.json` /
`MANIFEST.json` 通用层登记；lib 类**没有** SKILL.md，不要去那儿找版本（C2 已按 kind 分支）。

## 6. 有人给本目录加了 SKILL.md

症状：平台把 foundry-core 注册成技能，`verify.sh` 报「核心库混入 SKILL.md」。
处置：删掉它。lib 不注册是分层落地表的硬口径，注册了会与 foundry 抢触发词。

## 7. `from core import http_get` 拿到错的模块（撞名劫持）

症状：能力层 `shellcrack.py` 的 `fetch()` 报 `http_get` 不存在，或 `JadxMCP` 变成判据模块。
处置：`probe.py` 把 `~/.codebuddy/skills/tvbox-core/scripts` 插进 sys.path，那里的 `core.py`
提供 `http_get`；本 lib 的 `scripts/core.py` 与之同名。若把 `foundry-core/scripts` 也塞进
sys.path 或用 `import core` 加载引擎，`from core import ...` 会被劫持。W2 引擎刻意独立命名
`jadx_engine.py`，且 shellcrack 用 `importlib.util.spec_from_file_location` 按**绝对路径**
加载、全程不碰 sys.path。别把引擎改名回 `core.py`，也别改回 `import core`。

## 8. 改了仓内 core.py 但 foundry.py 报 `has no attribute 'schema_ok'`

症状：`core.py --selftest`（直跑仓内）全绿，`foundry.py status/selftest` 却报
`AttributeError: module 'core' has no attribute 'schema_ok'`、`KeyError: 'call_recipe'`、
或「已验 0/26」「转正判定：无法判定」。
处置：`foundry.py` 的 `_load_core()` **用户级安装副本优先**，`~/.codebuddy/skills/foundry-core/`
还是上一阶段的旧件。这不是代码 bug，是 C5 镜像未同步。走 `bash install.sh --user-skill`
正门重装（不手工 cp 单文件），装完用户级副本与仓内一致即自愈；重跑前先确认
`grep -c 'def schema_ok' ~/.codebuddy/skills/foundry-core/scripts/core.py` ≥ 1。

## 9. tools/call 返回 `PROC_DEAD` 而不是抛异常

症状：jadx 服务端反编译某类时子进程崩溃，后续调用全 `PROC_DEAD`（本轮真调复验进程 B
6/20 通、13 PROC_DEAD）。
处置：`jadx_engine.py` 的 `call()` 把死进程的 `BrokenPipeError/OSError` 收敛成
`{'state':'PROC_DEAD'}` 三态 dict——如实记「无法判定」，不折叠成通过、也不假装成功。
这是 jadx 服务端稳定性、不是传输层缺陷：起独立 java 进程分批跑、或换稳定类名
（`get_main_activity_class` 的返回，别用 Kotlin 合成类 `...$MainActivityKt`）即可。
不要为了「凑绿」把 `PROC_DEAD` 判成 success（病15 / B-02）。
