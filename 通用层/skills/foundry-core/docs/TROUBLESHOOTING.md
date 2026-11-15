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
