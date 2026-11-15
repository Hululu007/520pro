# foundry 故障排查（按症状排）

> 每条都是真形态，不写占位。先跑 `python3 scripts/foundry.py selftest` 看是哪一层红。

## 1. status 报「骨架缺件」

症状：`status` 列出 SKILL.md / CHANGELOG.md / artifacts.json / trigger-samples.md 中某件缺失，
或 `verify/skill_contracts.json` 里 `foundry` 的 `required_files` 与磁盘不一致。
处置：不要改判据去迁就文件（改判据≠补齐登记），按 C1 契约把文件补回；补完重跑
`python3 verify/skill_contract_check.py --require-mirror` 确认 C1/C2 绿。

## 2. C4 版本四处对不上

症状：契约机检 C4 报 `版本不一致`，或 MANIFEST 通用层登记的版本 ≠ SKILL.md front matter。
处置：四处真源是 `skill_contracts.json` / `SKILL.md` / `CHANGELOG.md` 首条 / `MANIFEST.json`，
只改过期那一处，不在第五处写死副本；`foundry-core`（lib）的第四处同样要对齐 `manifest.json`。

## 3. 惊门报触发词撞车

症状：`inspect_hub.py run` 惊门红，提示某词被两个技能同时声明。
处置：字面同词才判红（本门只查字面）；把本板块的词改得更具体，不要删掉触发词清单
——删光会让 covered < total 反而判黄。语义相近但字面不同留给 N 组「应归谁」人工核。

## 4. tools/call 报 `see get_methods_of_class for the exact name`

症状：方法名/字段名参数填了 JSON key（如 `class_name`）或手敲类名，工具回错。
处置：参数一律取上一步**真实返回**——方法名用 `items[0]`（如 `onCreate` / `$stable`），
类名用 `get_main_application_classes_names` 的返回，构造器写 `<init>` / `<clinit>`。
这是 W2 参数链的核心口径，不要靠猜。

## 5. get_resource_file 报 `resource is a link, not a file`

症状：把 APK 里 zip 的原始路径（40 个候选全试过）传给 `get_resource_file` 一律失败。
处置：zip 原始路径 ≠ jadx 解码资源名。先 `list_resource_files` 拿解码后的名字，
用 `AndroidManifest.xml` / `resources.arsc` 这类名字调；实证见 `/tmp/resource_file_实测.json`。

## 6. 产出落库失败但被说成「已归档」

症状：`archive_out` 返回 False，或 `archive_ledger.json` 没有对应 `result=ok` 回执，
`gate_archive_ledger.py` 判「假交付」红。
处置：失败时本地文件保留并记 `local_pending(kind=待归档)`，用 `space_hub.py products --retry`
补投；回执由 archive 正门自动写仓级账，不要手工塞一行 ledger 洗绿。

## 7. C5 镜像报「安装副本不存在 / 内容不同」

症状：契约机检 C5 在 `--require-mirror` 下红。
处置：走 `bash install.sh --user-skill` 正门重装通用层，不要手工 cp 单个文件
（漏一件下次还是红）；运行时态文件在 `runtime_files` 豁免清单里，不要把它算成漂移。
