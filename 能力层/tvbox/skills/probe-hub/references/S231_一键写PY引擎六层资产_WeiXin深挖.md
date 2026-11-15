# S231 · 一键写PY引擎六层资产 + 壳矩阵翻案（WeiXin.zip 三轮深挖）

来源：WeiXin.zip 解包（`OK影视一键写py.py` 2587 行全文拆解 + 4 个 APK 内容物鉴定）。
原文快照：[`S231_物料_OK影视一键写py.py`](S231_物料_OK影视一键写py.py)（md5 `668aacfd13e153a7fa6ae0a63530c1e3`，**本文所有行号均指向该快照**）。
词典机器可读版：[`S231_url_wordlists.json`](S231_url_wordlists.json)。
先例：S224（base(5) 壳二轮深挖 8 项资产）同型续作。三轮累计 27 组有出处 / 1 条无出处（移植优先级建议）。

**状态（2026-11-15 第四轮·收口）：六层全部代码化，本文从"资产清单"转为"落点索引"。**
第四轮做的是把通道层三件补成可执行正门、用 46 个真实源把第 7 条金律的样本凑齐（§四），
以及订正本文自己那些「待移植」的过期标注（照旧读会让人重做一遍）。
后续对照见 [`S232_bdb库六类资产与写源DSL.md`](S232_bdb库六类资产与写源DSL.md)——那份材料
给的是**第二种写源范式**（JSON 模板 DSL），与本文的 Python 代码生成路线并行，不是替代。

---

## ★ 一、六层资产总账（每层：出处 → 精华 → **落地状态**）

> **2026-11-15 订正**：本表原先全部标「待移植／去向」，而代码早在 v1.28.6 就已落地，
> 照旧表读会让人重做一遍（病15 同族：**文档状态 ≠ 代码事实**）。现按落点逐行改写，
> 每行给文件名，可直接 grep 复核。

| 层 | 资产 | 快照行号 | 落点（已落地，给文件名） |
|---|---|---|---|
| 网络层 | TLS 指纹伪装 + 多域名轮换 + header 全套 | L104-195 | `scripts/livecheck.py`：`TLS_FP_CIPHERS`/`TLS13_CIPHERS`/`_build_cmd()`/指纹失败自动回退（`_FP_RETRY_KINDS`） |
| 词典 | NON_CONTENT / CONTENT_DIRS / 导航词 | L378-424 | `references/S231_url_wordlists.json` → `repair/recon.py: _s231_words()` 惰性消费 |
| 算法 | sniff 聚类打分 / _build_detail_re / _looks_dead / _migrate_target | L528-771 | `repair/recon.py`：`sniff_detail_re()`（聚类打分）/ `build_detail_re()`（五层决策） |
| 接口 | JsonAPI 适配 / _probe_site 语义测活 / search 12 形态 | L291-399, L1045-1071, L1659-1683 | `scripts/livecheck.py`：`SITE_API_PATHS`/`_list_count()`（-1 解析不了 ≠ 0 列表空）/ `probe_site()`；`death_cause` 增「内容层／接口层」两型 |
| 播放 | 6 层播放集兜底 + 广告排除 / **第 7 条金律** | L972-1245 | `scripts/shellcrack.py`：`play_sets()` 六层 + `resolve_play_page()` 第 7 条金律（见 §四） |
| 通道 | 本地推送协议 / wsrv.nl 图代理 / 原子写 | L1603-1624, L1747-1773, L1900-1920 | `scripts/atomicio.py`（原子写+内容不变不重写）/ `scripts/pushconfig.py`（FongMi 推送）/ `scripts/imgproxy.py`（wsrv.nl 开关） |

### 1. 网络层（★★★，可直接抄）

**TLS 指纹伪装**（L104-118）：`ssl.create_default_context()` + 关证书校验 + `set_ciphers` 浏览器
cipher 列表 + `set_alpn_protocols(["http/1.1"])`。原文注释：**「部分站点 WAF 会识别 Python 默认
指纹并拒绝」**。≈15 行。这是探源司「浏览器能开但脚本 403」类死案的现成解药——
**已落地** `livecheck.py`（`TLS_FP_CIPHERS` + `_build_cmd()`），并加了一处原文没有的保险：
收紧 cipher 会弄死只支持老套件的站，故 tls/cert 类失败时**去指纹重试一次**，
`_tls_fp_used` 如实反映本次是否套了指纹。关闭开关 `LIVECHECK_TLS_FP=0`。

**多域名轮换**（L140-195）：BASES 多域名逐个重试；URL 属备用域名自动换当前域名；外部 CDN 不轮换；
`https://host/www.host/path` 畸形拼接自动纠回（L122-139）；Sec-Fetch-* 全套 header；gzip 解压；
gbk→gb18030。

### 2. 词典（★★★，已落 JSON）

`NON_CONTENT` 60 词（L378-382）+ `CONTENT_DIRS` 40 词（L422-424）+ 中文导航词 15（L385-387）+
广告文案排除两组（L986-988, L1001-1004）+ search 12 形态（L1047-1059）+ probe API 4 路径
（L1662-1667）。**算法会迭代，词典是踩坑沉淀**——全部已内联进 `S231_url_wordlists.json`，
repair/recon/forge 可直接 import。

### 3. 算法（★★，配合 S226 整站重写档）

- **sniff 聚类打分**（L590-687）：全页链接按 `_path_key` 归一成 `/vodplay/#.html` 模式键聚类；
  打分 `唯一ID数×10 + ID均长×3 + min(链接数,200)×0.2`，≥3 个唯一 ID 才参选；选最优组最长 URL
  作正则模板。**不靠固定正则，任意站点形态自适应**——比 S226 现行侦察多一条统计路线。
- **首页全死自动换源**：`_migrate_target` 跟新站成功后**新域名插 BASES[0]、旧域名降备用**（L596-609）
  ——换源记忆机制，repair 换域路由可借鉴。
- **`_build_detail_re` 五层决策**（L717-771）：剥扩展名 → 单段前缀 → MacCMS 占位词 → `/v/ID/ep`
  短参数 → slug 整段；兜底只替换最后一段数字（注释：「避免吃到域名里的数字」）。
- `_looks_dead` 14 关键词判死（L528-553）、`_migrate_target` 公告页→JS 跳转→同品牌域名三层
  防钓鱼（L554-589）——与 S221 失效分型互补。

### 4. 接口（★★★，语义测活判据）

- **`_probe_site` 语义测活**（L1659-1683）：4 条 MacCMS 路径 + `ac=list`，**必须解析出
  `data.list` 非空才算接口活**——把「域名活着」和「接口能出片」分开判。现行 `_alive` 只看
  HTTP 码（SKILL.md §7 测活口径），此判据是「内容层死因」的零成本前置探针。
- **JsonAPI 适配**（L291-399）：`ac=detail` 失败退 `ac=videolist`；播放地址三级分隔
  （`$$$` 线路 / `#` 集 / `$` 名链）；`pagecount`/`total_page` 双字段兜底。
- **search 12 形态穷举**（L1045-1071），`parse_items` 有货即停。

### 5. 播放（★★，shellcrack 补充）

- **6 层播放集兜底**（L972-1019）：A0 通用苹果CMS `ID-SID-EID.html` → A `vodplay` 重写 →
  A2 `data-line`/`data-episode` 锚点 → B play 链接 → C iframe/JSON 直链。同一集跨推荐位重复
  出现按链接去重（L988-995）。
- **跨域广告排除**：播放链接为绝对地址且不在 BASES 内 → 判广告丢弃（L999-1002）。
- **播放页二次解析**（L1215-1244）：`player_xxx={...}` JSON → `"url":"...m3u8"` →
  `source:'...'`；全失败退 `parse:1` 交壳嗅探。**已升为 shellcrack 第 7 条金律**
  （`resolve_play_page()`）；但实测发现原文三层不够用，已扩到 7 层 + 网盘前置 + iframe 下钻，
  详见 §四。

### 6. 通道（★★，已全部代码化）

- **FongMi 系本地推送协议**（L1747-1773）：`com.github.catvod.Proxy.getPort()` 拿本地端口 →
  POST `http://127.0.0.1:{port}/action?do=sync&mode=1&type=history`，body 为
  `config={"type":0,"url":...,"name":...}&force=false`（urlencoded）。**免手输接口地址、
  一键换源的正门**，Muse/Meta 系（FongMi）壳通用。
  → 落点 `scripts/pushconfig.py`。端侧 `java` 桥在服务器上不存在，故端口来源做成三态
  （`--port` > `FONGMIPORT` > java 桥），三路皆空报**无法判定**而非失败。原样保留两个坑：
  `ProxyHandler({})`（系统代理会把 127.0.0.1 的请求也劫走，报错伪装成「连接被拒」）、
  `Connection: close`（壳侧 NanoHTTPD 单线程，keep-alive 会把它挂死）。
- **wsrv.nl 图代理**（L1900-1920）：封面防盗链/挂图的正解——把已生成源里 `IMG_PROXY` 行
  原地改写为 `https://wsrv.nl/?url=`，开关一键切换。
  → 落点 `scripts/imgproxy.py`。默认 **dry-run**（批量改文件不可逆，先给眼睛看），统计分
  「改了／本来就对／没这行／不可读」四类——原文只报「已应用到 N 个 py」，看不出基数。
- **原子写**（L1603-1624）：tmp → `fsync` → `os.replace`；**内容没变不重写**。core/repair 写
  配置可对齐。
  → 落点 `scripts/atomicio.py`。第 ② 条（内容不变不重写）此前全仓没有：space-hub 只实现了
  原子那一半，批量写完 mtime 全变，下游会误判「有新版本」，git 也会平白脏一格。

---

## ★ 二、壳矩阵翻案（APK 鉴定，四轮累计）

> 上一版「Muse/Meta=FongMi 系」判定**作废**。证据：Muse dex 包名统计 `com/facebook/`×7648、
> `com/meta/`×82、`com/instagram/`×17——**Meta（Facebook）官方 App，与 TVBox 零关系**，
> 混入 WeiXin.zip 属误放。

| 壳 | 鉴定 | 出厂自带（APK 内证据路径） | 对探源司的意义 |
|---|---|---|---|
| **LeeCat**（294MB） | Flutter 全本地引擎壳，**唯一不需远程 jar** | `libnode.so` 49MB（Node.js）；`assets/chaquopy/` Python 3.10 全运行时 + `build.json` `"extract_packages":["lxml"]`；`flutter_assets/assets/js-runtime/drpy3-engine.js` 205KB；播放五引擎 mpv/VLC(45MB)/mdk/ffmpeg/fvp；`libxl_thunder_sdk.so`（迅雷）；`libonnxruntime.so`+`libsherpa-onnx`（本地 AI） | py 源优先适配此壳；py 源里 **lxml 可用**；js/drpy3 亦本地支持 |
| **云取** 2.7.12 | 网盘下载特化壳 | `libquickjs.so`×4 架构；`libaria2c.so` 17MB；`dev/turbodl/plugin/js/abi.js` | 仅支持 js/drpy 类源；下载走 aria2 |
| **MilkCode** 1.0.4（302MB） | **手机越狱 AI Agent**，非 TVBox 协议壳 | `assets/builtin_skills/manifest.json`：69 技能/62 breakerKit（渗透/逆向/破解，含 phishing-kit、identity-docs 高危项）；`assets/mcp/jadx-headless-mcp-0.7.1-all.jar` 42MB；proot + DexKit | 架构与探源司同构（self-improving-agent / env-audit / skill-installer）；**⚠️ 内置红队技能库，不建议安装**，仅作技术观察 |
| Muse_from_Meta | **Meta 官方 App，非壳** | dex 包名统计（见上） | 从壳兼容矩阵除名 |

**jadx-headless-mcp** 现成工具提示：MilkCode 内的 42MB jadx MCP jar 可抽出部署，探源司验
jar/dex 的备选逆向工具（本次未抽，行号证据：`assets/mcp/jadx-headless-mcp-0.7.1-all.jar`）。

---

## 三、孤例留痕（B-15）

- S229 编号缺号（references 序列 S228 → S230，全库 grep 无 S229 登记）：孤例，本条留痕，
  不判模式；编号真源治理归 S230 规则册体系，不在本战线展开。

## 四、第 7 条金律实测：五处原文没有的缺口

原待办写的是「实测 ≥3 壳样本后再升判据」——样本一直没凑齐，所以这条挂了两轮。
2026-11-15 用 S232 那个 bdb 包的 `py/` 目录补齐：**46 个真实源全部实现 `playerContent`**，
逐个抽播放页解析实现后，发现原文那三条正则缺得比想象的多，而且**每一处缺口都有出处**：

| # | 缺口 | 原文写法 | 真实世界（出处） |
|---|---|---|---|
| 1 | **JSON 字段名** | 只取 `d.get("url")` | 苹果CMS v10 标准模板 `player_aaaa` 的字段是 **`link` / `link_next`**（bdb 内 `player_aaaa=` 10 处；另有源用 `.url`，如「歪比影视」）→ **原文对标准模板恒失败，且失败无声** |
| 2 | **值不是 JSON** | `\{[\s\S]*?\}` | `var player_aaaa='https://…m3u8'` 字符串形态（3 处），原文正则认不出 |
| 3 | **裸赋值形态** | 无 | `const url = "…"` / `url: "…"`——`6v.py` 的 `_find_media()` 四条正则里占两条 |
| 4 | **iframe 套壳** | 只在一层页面找 | `6v.py` 的做法是「本页没有 → 跟 iframe 再找一遍」；播放页是 iframe 壳的站点极多 |
| 5 | **网盘直链** | 无 | `6v.py` 有现成识别：magnet / quark / baidu / xunlei / aliyun / 123pan / 189 / 139。这类集**本来就不该二次解析**，属前置分流而非解析失败 |

**落地形态** `scripts/shellcrack.py::resolve_play_page()`，判据顺序：

```
NETDISK（magnet/网盘域名） → L1 player JSON（url/link/url_next/link_next/src）
  → L2 player 字符串 → L3 JSON 字段 → L4 裸赋值 → L5 source:'' → L6 裸地址
  → iframe 下钻（depth=1，fetch 可注入） → parse:1 交壳嗅探
```
统一清洗：HTML 实体 → `\/` 与 `\u002F` 反转义 → 相对地址补全。全过程写 `trace`，失败也留痕。

自检 16 例，正反向实测：
- 正向 35 项全绿（六层 19 + 金律 16）。
- 反向 A：L1 字段名改回原文的 `('url',)` → 「金律①」**单条红**，且返回的 url 完全相同、
  **只有层名从 `L1` 变成 `L3`** —— 第一版用例只断言 url，反向摘掉 L1 也不红（假绿）。
  修法：每条金律用例都断言**层名**，不只断言结果。这条已写进注释，防止后人改回去。
- 反向 B：摘掉 L2 字符串层 → 「金律③」单条红，层名 `L2`→`L6`。

> **这一节真正的方法论产出**：判据的样本要从**真实世界的多样性**里取，不是从原文的
> 实现里取。原文自己就是「一个站跑通了」的产物，把它当样本只会验证它自己。
> 46 个源里 5 处缺口，没有一处是推理出来的。

## 五、待办登记（B-14 三齐）

| owner | next | due | 状态 |
|---|---|---|---|
| 探源司 | TLS 指纹段试挂 livecheck 网络层 | 三态改善 + verify.sh 全绿 | ✅ 已完成（v1.28.6，`TLS_FP_CIPHERS`/`_build_cmd`/失败回退） |
| 探源司 | `_probe_site` 语义测活并入死因分型前置探针 | 同上 | ✅ 已完成（`_list_count`/`probe_site`/`death_cause` 两型） |
| 探源司 | shellcrack 第 7 条金律实测评估 | ≥3 壳样本 | ✅ 已完成（46 源实测 → 扩到 7 层，见 §四） |
| 探源司 | 通道层三件代码化 | 三件各有 selftest 正反向 | ✅ 已完成（`atomicio.py` 17 项 / `pushconfig.py` 20 项 / `imgproxy.py` 18 项） |
| 我 | 抽出 MilkCode 内 42MB `jadx-headless-mcp-0.7.1-all.jar` 并评估能否替代现逆向工具 | 给出「可用／不可用／需改」结论 | ⏳ 转入第二立项（4 个 APK 深入） |
