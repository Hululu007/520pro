# S231 · 一键写PY引擎六层资产 + 壳矩阵翻案（WeiXin.zip 三轮深挖）

来源：WeiXin.zip 解包（`OK影视一键写py.py` 2587 行全文拆解 + 4 个 APK 内容物鉴定）。
原文快照：[`S231_物料_OK影视一键写py.py`](S231_物料_OK影视一键写py.py)（md5 `668aacfd13e153a7fa6ae0a63530c1e3`，**本文所有行号均指向该快照**）。
词典机器可读版：[`S231_url_wordlists.json`](S231_url_wordlists.json)。
先例：S224（base(5) 壳二轮深挖 8 项资产）同型续作。三轮累计 27 组有出处 / 1 条无出处（移植优先级建议）。

---

## ★ 一、六层资产总账（每层：出处 → 精华 → 探源司用法）

| 层 | 资产 | 快照行号 | 探源司去向 |
|---|---|---|---|
| 网络层 | TLS 指纹伪装 + 多域名轮换 + header 全套 | L104-195 | livecheck/测活网络段（待移植） |
| 词典 | NON_CONTENT / CONTENT_DIRS / 导航词 | L378-424 | S231_url_wordlists.json（已落） |
| 算法 | sniff 聚类打分 / _build_detail_re / _looks_dead / _migrate_target | L528-771 | repair recon/rewrite（S226 补充） |
| 接口 | JsonAPI 适配 / _probe_site 语义测活 / search 12 形态 | L291-399, L1045-1071, L1659-1683 | livecheck 死因分型补充 |
| 播放 | 6 层播放集兜底 + 广告排除 / 二次解析 | L972-1245 | shellcrack 金律补充（S196） |
| 通道 | 本地推送协议 / wsrv.nl 图代理 / 原子写 | L1603-1624, L1747-1773, L1900-1920 | 常备资产（本文承载） |

### 1. 网络层（★★★，可直接抄）

**TLS 指纹伪装**（L104-118）：`ssl.create_default_context()` + 关证书校验 + `set_ciphers` 浏览器
cipher 列表 + `set_alpn_protocols(["http/1.1"])`。原文注释：**「部分站点 WAF 会识别 Python 默认
指纹并拒绝」**。≈15 行。这是探源司「浏览器能开但脚本 403」类死案的现成解药——
**待办 B-14：owner=探源司 / next=把该段试挂进 livecheck 网络层并 A/B 实测 / due=移植完成判据为
同一 403 目标在挂段后三态改善，且 verify.sh 全绿**。

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
- **播放页二次解析三正则**（L1215-1244）：`player_xxx={...}` JSON → `"url":"...m3u8"` →
  `source:'...'`；全失败退 `parse:1` 交壳嗅探——与 S196 抠链金律同向，可作 shellcrack 的
  第 7 条金律候选（待实测再升判据）。

### 6. 通道（★★，常备资产）

- **FongMi 系本地推送协议**（L1747-1773）：`com.github.catvod.Proxy.getPort()` 拿本地端口 →
  POST `http://127.0.0.1:{port}/action?do=sync&mode=1&type=history`，body 为
  `config={"type":0,"url":...,"name":...}&force=false`（urlencoded）。**免手输接口地址、
  一键换源的正门**，Muse/Meta 系（FongMi）壳通用。
- **wsrv.nl 图代理**（L1900-1920）：封面防盗链/挂图的正解——把已生成源里 `IMG_PROXY` 行
  原地改写为 `https://wsrv.nl/?url=`，开关一键切换。
- **原子写**（L1603-1624）：tmp → `fsync` → `os.replace`；内容没变不重写。core/repair 写
  配置可对齐。

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

## 四、待办登记（B-14 三齐）

| owner | next | due |
|---|---|---|
| 探源司 | TLS 指纹段试挂 livecheck 网络层，A/B 实测「浏览器通脚本 403」目标 | 挂段后三态改善 + verify.sh 全绿 |
| 探源司 | `_probe_site` 语义测活判据并入 livecheck 死因分型前置探针 | 同上 |
| 探源司 | shellcrack 第 7 条金律候选（播放页二次解析三正则）实测评估 | 实测 ≥3 壳样本后再升判据 |
