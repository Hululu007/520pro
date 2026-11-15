# S233 · 四壳深入（LeeCat / 云取 / MilkCode / Muse）

来源：`/root/.codebuddy/artifact/.../weixin_x/`（原 `WeiXin.zip` 四件 APK + 一个 py 工具）。
先档：S231（壳矩阵一轮鉴定）。本档做的是**逐个深入**：每壳四栏（出厂自带证据 / 对探源司意义 /
可吸收项 / 明确不吸收项），**两条纠正**写在对应节里，不改历史档只加订正说明。

方法：`zipfile` 列结构与体积 → 读关键文件原文（php/py/js 源码可直接读）→
`jadx-headless-mcp` 实测反编译（§3）→ 字节计数核 dex（§4）。

---

## §1 LeeCat 294MB · Flutter 全本地引擎壳

### 1.1 出厂自带（实测，非转述）

| 资产 | 体积 | 证据路径 |
|---|---|---|
| Node.js 运行时 | 47.2 MB | `lib/arm64-v8a/libnode.so` |
| VLC 播放引擎 | 43.8 MB | `lib/arm64-v8a/libvlc.so` |
| **PHP 8.4 WASM 运行时** | **26.0 MB** | `assets/flutter_assets/assets/php-runtime/php_8_4-YDXAVFKU.wasm` + `dispatcher.php` + `spider.php` + `worker.js`(967 KB) |
| mpv / ffmpeg | 11.8 / 7.9 MB | `lib/arm64-v8a/libmpv.so`、`libffmpeg.so` |
| ONNX 运行时 | 21.2 MB | `lib/arm64-v8a/libonnxruntime.so` |
| **libfjs.so** | **8.2 MB** | `lib/arm64-v8a/libfjs.so`（S231 未记） |
| 迅雷 SDK | 5.3 MB | `lib/arm64-v8a/libxl_thunder_sdk.so` |
| Python 3.10 + 22 包 | 12.0 MB | `assets/chaquopy/`（见下表） |
| drpy3 + CatVod 双 js 引擎 | ~1.0 MB | `assets/flutter_assets/assets/js-runtime/`：`drpy3-host.js`(1190 KB)、`drpy3-engine.js`(200 KB)、`host.js`(649 KB)、`lib/cat.js`(475 KB)、`cheerio.min.js`、`crypto-js.js`、`gbk.js`、`drpy2.js` |
| Kodi lua 插件集 | 0.1 MB | `assets/lua/` 33 个（twitch / soundcloud / vimeo / dailymotion / bbc_co_uk…） |
| PDF 渲染 | 6.1 MB | `lib/arm64-v8a/libpdfium.so` |

**Python 包清单（22 个，`requirements-common.imy` 内 dist-info 实读）**：
`beautifulsoup4 4.15.0`、`soupsieve`、`cssselect`、`lxml 5.3.0`、`pyquery 2.1.0`、
`requests 2.34.2`、`urllib3 2.7.0`、`certifi`、`charset_normalizer`、`idna`、
**`pycryptodome 3.21.0`**、`ujson 5.11.0`、`jsonpath 0.82.2`、`jinja2 3.1.6`、`markupsafe`、
`json5 0.12.1`、`cachetools 7.1.8`、`chaquopy_libxml2 / libxslt`。

### 1.2 两条对我们直接有用的

**① py 源协议 = 标准 CatVod + drpy 双方言，我们是兼容的。**
`assets/chaquopy/app.imy → spider_compat.py` 定义了 `Spider` 基类
（`init/getName/getDependence/homeContent/homeVideoContent/categoryContent/detailContent/
searchContent/playerContent/localProxy/liveContent/action/isVideoFormat/manualVideoCheck/destroy`），
`assets/chaquopy/app.imy → source_loader.py` 里 `SourcePackage(dialect='catvod'|'drpy')`
按方言挑 `BaseSpider` 还是 `Spider`。
→ **`probe forge` 生成的源可直接跑**，不需要壳适配层。

**② 自带 `pycryptodome 3.21.0`，"AES 兜底"在 LeeCat 上不必要。**
本仓 `scripts/_aes_fallback.py` 是为「羊壳无 pycryptodome」准备的。在 LeeCat 上
`from Crypto.Cipher import AES` 直接可用。**结论不是删兜底**（别的壳没有），
而是**写源时按目标壳分档**：已知有 pycryptodome → 用原生；未知 → 用兜底。

### 1.3 ★ 新发现：PHP 源，第三种源语言

`dispatcher.php` 是一个常驻循环：`bridge('next')` 取请求 → 按 method 分派 → `bridge('result')` 回结果。
源从 `/sources/{entry}` 加载，必须「返回实例」或「声明恰好一个 `BaseSpider` 子类」。

接口与 py 完全同构：

| PHP 方法 | 对应 py |
|---|---|
| `homeContent($filter)` / `homeVideoContent()` | `homeContent` / `homeVideoContent` |
| `categoryContent($tid,$pg,$filter,$extend)` | 同名 |
| `detailContent([$ids])` / `searchContent($wd,$quick,$pg)` / `playerContent($flag,$id,$flags)` | 同名 |
| `localProxy` / `action` / `liveContent` | 同名 |
| **`pdfh` / `pdfa` / `pd`** | **drpy 的 HTML 选择器三件套，同名同语义** |
| `pageResult($list,$page,$pagecount,$limit,$total)` | 分页结构 |

辅助：`request/fetch/fetchJson`（走 `leecat_bridge('request')` 回宿主发请求）、
`getProxyUrl`、`localGet/localSet/localDelete`、`init($extend)`。
返回值上限 24 MB；`ob_start(fn=>'')` 吃掉源的 echo 防撑爆内存。

`spider.php` 顶部注释很关键：
> `// LeeCat SDK fallback. Source-owned lib/spider.php is used unchanged.`
以及 `dispatcher.php` 顶部：
> `// LeeCat's explicit Spider protocol. This is not DsPlayer's missing SDK.`

→ **LeeCat 在明确撇清与 DsPlayer 的关系**：DsPlayer 那套 py/php 源协议缺 SDK（S195 记过），
LeeCat 自己重写了一份显式协议。这条对「为什么某些源在 A 壳能跑 B 壳不能」有解释力。

### 1.4 四栏结论

- **对探源司意义**：① 生成源的兼容目标可明确写「CatVod 契约 + drpy dialect」；
  ② 壳能力差异（有无 pycryptodome / lxml）应进入「写源分档」，而不是一律用最保守写法。
- **可吸收**：`pdfh/pdfa/pd` 三件套跨语言同名这一事实——**选择器语法可跨语言复用**，
  是 S232 DSL 设计的有力旁证；`getDependence()` 声明依赖的机制（按需装包而非全量塞）。
- **不吸收**：播放五引擎（mpv/VLC/ffmpeg/fvp）、ONNX 本地 AI、迅雷 SDK（版权风险且与源无关）、
  Kodi lua 插件集（音乐/国外站，与国内影视源无交集）、PHP 源类型本身
  （**只有 LeeCat 一家支持，为单一壳新开一种源语言，生态收益远小于维护成本**）。

---

## §2 云取 2.7.12 · 32MB —— **纠正 S231：它不是壳**

### 2.1 实测

`load_apk` 反编译：包名 `com.yunget.app`，versionName `2.7.12`(60)，minSdk 23 / targetSdk 34，
22432 个类。权限含 `MANAGE_EXTERNAL_STORAGE`、`REQUEST_INSTALL_PACKAGES`、
`FOREGROUND_SERVICE_DATA_SYNC`——**下载器特征**。

关键字字节计数：`turbodl` **190**、`quickjs` 97、`aria2` 39、`pan.quark` 3、`pan.baidu` 1；
**`catvod` 0 / `tvbox` 0 / `spider` 0 / `drpy` 0**。

结构：`lib/arm64-v8a/libaria2c.so` 16.7 MB + `libquickjs.so` × 4 架构 +
`dev/turbodl/**` 一整套类：

| 包 | 类（列举） |
|---|---|
| `core` | `AdaptiveConcurrencyController`（含 `Decision`/`Direction`/`Phase`）、`BackendResolver`、`BuiltinHttpBackend`、`BackendContext`、`BackendResult`、`ApiVersion` |
| `plugin/runtime` | `Plugin`、`CapabilityId`（含 `Parsed`/`Result`） |
| `plugin/js` | `JsCapability`、`JsHostCrypto`、`JsValueCodec`、`JsScriptValidator`（含 `Report`）、`JsSealReport` |
| `plugin/hls` | `HlsBackend`、`HlsUnsupportedException` |
| `plugin/bootstrap` | `HttpBackendPlugin` |
| `plugin/native` | `NativePluginSourceKt` |

### 2.2 纠正

S231 壳矩阵里写「云取 = 网盘下载特化壳，**仅支持 js/drpy 类源**」——**后半句不成立**。
它没有任何 TVBox 源协议代码；`js` 指的是**下载器插件用的 QuickJS 脚本**，与 drpy 源是两回事。

### 2.3 四栏结论

- **对探源司意义**：**从「壳兼容矩阵」移到「下载器参考」**。它不能跑我们的源，
  但它的两套机制对我们有参考价值。
- **可吸收**：① `AdaptiveConcurrencyController`（按网络状况自适应调并发，
  我们 `livecheck --batch` 的固定并发可参考其 Decision/Phase 模型）；
  ② `CapabilityId` 能力声明 + `JsCapability` 按能力取用——与「技能契约声明能力」同构；
  ③ `JsHostCrypto`：JS 侧不自己实现 AES，调宿主能力——对应我们 `_aes_fallback` 的另一种解法。
- **不吸收**：aria2 下载引擎、turbodl 插件体系、网盘转存（属用户账号操作）。

---

## §3 MilkCode 1.0.4 · 302MB —— jadx MCP **实测可用**

### 3.1 出厂自带

| 资产 | 体积 | 证据 |
|---|---|---|
| Frida server 17.23.3 (arm64) | 56.4 MB | `assets/frida/frida-server-17.23.3-android-arm64` |
| proot 工具链 | 169.1 MB | `assets/linux-tools/arm64-v8a/`：`python-gnu.bin` 49.9 / `python-musl.bin` 48.0 / `node-musl.bin` 31.0 / `node-gnu.bin` 28.8 / `curl` 9.5 |
| **jadx-headless-mcp 0.7.1** | **40.6 MB** | `assets/mcp/jadx-headless-mcp-0.7.1-all.jar` |
| 红队技能库 | 5.1 MB | `assets/breaker/v4-skills/`（`ida-reverse` / `js-reverse` / `pentest-tools` / `src-hunter`…） |
| 壁纸（无关） | 39.0 MB | `assets/wallpapers/*.mp4` |

### 3.2 实测（这是本节的重点，不是「抽出来了」）

环境：`java 20`（Zulu 20.28+85-CA）可用。主类 `com.atxx.jhmcp.MainKt`。

```
java -jar jadx-headless-mcp-0.7.1-all.jar --transport stdio
→ initialize ✓  serverInfo {name: jadx-headless-mcp, version: 0.7.1}  protocolVersion 2024-11-05
→ tools/list  →  26 个工具
→ tools/call load_apk(云取.apk)  →  {"state":"LOADED","class_count":22432,
     "resource_count":1069,"load_duration_ms":14759,"threads":4}
→ tools/call get_app_info  →  {"package":"com.yunget.app","version_code":"60",…}
```

26 个工具分四组（全实测列出）：
- **装载**：`load_apk`（APK/DEX/JAR 通吃，替换当前文件）、`unload_apk`、`status`
- **元信息**：`get_app_info`、`get_android_manifest`（可按 section 取）、`get_main_activity_class`、
  `list_resource_files`、`get_resource_file`、`get_strings`
- **类/方法**：`list_classes`（分页 + 前缀）、`get_class_source`（反编译 Java，带 anti-decompile 兜底）、
  `get_class_summary`、`get_smali_of_class`、`get_methods_of_class`、`get_method_by_name`、
  `get_method_body`（Java 失败自动退 smali）、`get_method_smali`、`get_fields_of_class`、
  `get_inner_classes`、`resolve_class`、`search_classes_by_keyword`（可按 class/method 多作用域）、
  `search_method_by_name`
- **引用**：`get_xrefs_to_class` / `get_xrefs_to_method` / `get_xrefs_to_field`

### 3.3 ★ 一个必须记下的坑

`assets/mcp/rea-preset.json` 里列了 24 个工具名（`inspect_android_package` / `search_android_classes` /
`trace_android_references` / `inspect_pe_resources` / `analyze_javascript_application`…），
**照这个名字去调会得到 `Tool inspect_android_package not found`。**

实测第一遍就撞上了。原因是 `rea-preset.json` 是 MilkCode **上层 agent 的封装命名**，
不是这个 jar 的原生工具表；两者之间有一层映射（或另一个 server）。

> **教训**：配置文件里的「能力清单」不等于「实际接口」。**判断一个工具能不能用，只有跑一次**——
> 这次跑之前我以为只要 jar 在、java 有，抄 preset 就行；实际工具名完全不同。

### 3.4 四栏结论

- **对探源司意义**：**这是四件里唯一有直接生产价值的**。S196「壳源侦察」目前靠
  `zipfile` 列目录 + `strings` 扫（粗），这个 jar 给的是**反编译级**能力：
  `get_class_source` / `get_smali_of_class` / `get_xrefs_to_*` / `search_classes_by_keyword`。
  实测可用于回答「这个壳支持哪些源类型」——搜 `spider`/`catvod` 类名比扫字符串可靠得多
  （§2 纠正云取判定用的就是这条路）。
- **可吸收**：`load_apk` + 26 工具的能力面；`get_method_body`（Java 失败退 smali）这个降级设计。
- **部署方式（明确）**：**不入 git**。40.6 MB fat jar 进仓违反产物纪律且拖慢分发。
  需要时三选一：① 从 APK 现抽（`unzip -p` 一行）；② MCP 配置指向本机路径；
  ③ 官方渠道单独获取。**不写进 `install.sh`**，避免每次部署多拷 40 MB。
- **不吸收**：Frida server、proot 工具链、`breaker/` 红队技能库（含钓鱼、身份伪造类，**不建议安装**，
  本档只记结构不抄内容）、壁纸。

---

## §4 Muse_from_Meta 42MB —— 确认除名（并纠正 S231 的数字口径）

### 4.1 实测

6 个 dex 共 45.4 MB，字节计数：

| 命名空间 | 出现次数 |
|---|---|
| `com/facebook/` | **43,588** |
| `com/meta/` | 765 |
| `com/instagram/` | 19 |
| `catvod` / `tvbox` / `spider` | **0 / 0 / 0** |

### 4.2 纠正

S231 记的是 `com/facebook/`×7648 / `com/meta/`×82 / `com/instagram/`×17。
方向完全正确（就是 Meta 官方 App），但**数字口径不一致**——本轮用字节 `count()` 得 43588/765/19，
S231 那组数字更接近 `grep -c` 的行数统计（对二进制无意义）。**结论不变，数字以本档为准。**

### 4.3 四栏结论

- **对探源司意义**：**零**。它是 Meta（Facebook/Instagram）官方客户端，与 TVBox 生态无任何关系。
- **可吸收**：无。
- **不吸收**：全部。从壳矩阵除名（S231 已除名，本档补数字证据）。
- **为什么会在包里**：`WeiXin.zip` 是用户手机里若干 APK 的打包，Muse 属误放。
  这解释了为什么文件名带 `_APKPure`（应用商店下载版）。

---

## §五 汇总：四件怎么处置

| APK | 判定 | 处置 |
|---|---|---|
| **LeeCat** | Flutter 全本地引擎壳，py/js/**php**/lua 四语言源 | 保留为「生成源兼容目标」；写源按「有无 pycryptodome」分档；PHP 源不实现 |
| **云取** | **不是壳**，是 QuickJS 插件化下载器 | 从壳矩阵移到「下载器参考」；吸收自适应并发与能力声明两个机制 |
| **MilkCode** | 手机 AI Agent + 红队库 | **只取 jadx jar**（实测可用、不入 git）；其余不装不抄 |
| **Muse** | Meta 官方 App | 除名，无后续 |

## §六 待办（B-14 三齐）

| owner | next | due |
|---|---|---|
| 探源司 | `probe shellcrack`（S196 壳源侦察）增加「借 jadx MCP 反编译」的路径：`load_apk` → `search_classes_by_keyword` 判源类型，替代现在的 `strings` 粗扫 | 至少 1 个真壳（LeeCat）走通并给出「支持哪些源类型」的类名级证据 |
| 探源司 | 写源分档：`forge` 生成 AES 相关代码时按目标壳能力分支（有 pycryptodome → 原生；未知 → `_aes_fallback`） | 分档判据落入 SKILL.md 且 selftest 覆盖两条分支 |
| 探源司 | S231 壳矩阵表按本档订正（云取判定 + Muse 数字口径 + LeeCat 补 php/fjs/pycryptodome） | 表中每行都能指回本档小节 |
| 我 | `rea-preset.json` 与 jar 原生 26 工具的映射关系若后续要用，需单独查清（当前结论：**不可照抄**） | 下次真要接 MCP 时先跑 `tools/list` |
