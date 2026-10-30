# Maibot × DSH 桥

把 [MaiBot（麦麦）](https://github.com/Mai-with-u/MaiBot) 和 [DeepSeek Harness（DSH）](https://github.com/deepseek-ai) 接起来：

**麦麦负责「像人」，DSH 负责「干活」，人格和记忆两边共用一份。**

> MaiBot 的设计原则是「最像，而不是最好」——她不该长成一个什么都能干的机器人。
> 所以这个项目不给她加功能，只在她需要动手的时候，把活递给 DSH，干完再以她自己的口吻说出来。

---

## ⚠️ 这是我自用的插件，不是通用产品

写清楚免得你踩坑：

- **只在我自己那台机器上跑通过**：Windows + MaiBot 1.3.19 一键包 + DSH 桌面版。Linux、Docker、macOS 全没试过。
- **路径是硬编码的**：配置默认指向我本机的目录结构，你得自己改 `settings.json`。
- **依赖几个第三方东西**：Playwright + 本机 Edge、一个能用的 B 站登录态、MaiBot 的 `plugin_runtime`（1.3.x）。少一样就有一段功能是灰色的。
- **接口是跟着 MaiBot 源码走的**：`@Command`、`ctx.maisaka.*` 这些没有稳定承诺，MaiBot 升级可能直接打断。
- **没有测试、没有 CI**：所有「能跑」都是我在群里手点出来的。

如果你要的是一个能长期维护的项目，这里大概率不是。但如果你也在折腾「让 bot 有点自主性」这件事，里面的踩坑记录应该能省你几天。

**状态**：能自用，但不保证稳定性。Issue 欢迎，能不能修看缘分。

---

## 它能做什么

| 能力 | 方向 | 说明 |
|---|---|---|
| **人格现读** | MaiBot → DSH | DSH 的「麦麦」模式不内联人设，每次开工现读 `bot_config.toml` 的 `[personality]`，你改麦麦的人设，DSH 这边跟着变 |
| **记忆只读** | MaiBot → DSH | DSH 里能检索麦麦的 A-Memorix 长期记忆（`/api/webui/memory/records/search`） |
| **记忆写入** | DSH → MaiBot | 把「DSH 这边发生的事」写进麦麦的长期记忆（`/api/webui/memory/import/paste`） |
| **任务互派** | MaiBot ↔ DSH | 麦麦的工具 `dsh_task` 会把任务交给 `dsh --profile headless` 执行，结果回到麦麦手里，由她决定怎么说 |
| **自动同步** | 定时 | 每天固定时间把 DSH 的项目记忆压缩成一段「最近发生的事」写进麦麦的记忆 |
| **自己出去看** | MaiBot → 网络 | `/看 <平台> <关键词>` 或 `look_around`，无头 Edge 真打开网页，把结果抽成结构化条目 |
| **真的看视频** | MaiBot → B站 | `/看视频 <BV号>` 读字幕、简介、弹幕抽样、热评，让她能聊视频内容而不是标题 |
| **喜欢就动手** | MaiBot → B站 | 看完真喜欢的，自己点赞 / 收藏，有日额度、冷却、必须说理由 |

三条命令消息的节奏是刻意设计的：**收到 → 结果 → 观感**。回执是因为抓取要几秒到十几秒，中间没动静会让人以为命令没生效；观感是因为「给一堆条目」不等于「她看过了」。

## 组成

```
.
├── maimai.py             # CLI：读人格 / 检索记忆 / 写入记忆
├── emit_preset.py        # 生成 DSH 侧「麦麦」模式的 bundle
├── persona_sync.py       # 只生成人格文本（emit_preset 的简化版）
├── sync_to_maimai.py     # 把 meow-memory 的项目记忆同步进麦麦
├── sync_daily.ps1        # 计划任务入口（Windows）
├── bili_login.py         # 扫码登录 B站，把 SESSDATA 落到两个地方
├── maibot-plugin/        # 麦麦侧插件（MaiBot plugin，id: lirick.maimai-bridge）
├── dsh-settings/         # DSH 侧设置界面（Cordis bundle，设置 → Maibot互联DSH）
└── dsh-preset/           # 由 emit_preset.py 生成，不进版本库
```

四个包各自独立安装，可以只用其中一两个。

## 安装

### 0. 需要什么

- MaiBot（1.3.19 以上）跑起来，WebUI 能在 `http://127.0.0.1:8001` 打开
- DSH（带 `webServer` 服务的版本）
- Python 3.10+（跑桥接脚本）
- 想用「出去看看 / 看视频」：`pip install playwright` + 本机装了 Edge（用 `channel="msedge"`，不用下载 Chromium）

### 1. 麦麦侧插件

把 `maibot-plugin/` 整个目录复制到 MaiBot 的 `plugins/` 下，改名 `maimai_bridge`：

```
<MaiBot>/plugins/maimai_bridge/
├── plugin.py
├── _manifest.json
├── config.toml
├── README.md
├── CHANGELOG.md
└── bili_video/           # 看视频与点赞收藏的内置子包
```

重启 MaiBot，日志里应该出现：

```
[plugin.lirick.maimai-bridge] [maimai_bridge] 桥插件已加载
```

### 2. DSH 侧设置界面

```
# 在 DSH 里
plugin_manager install_bundle(target: "<本仓库绝对路径>/dsh-settings")
```

装完重启 DSH，设置里会多一页「Maibot互联DSH」：连通状态、MaiBot 侧插件参数、路径、人格现读 / 重新生成 preset、长期记忆读写、平台登录、点赞收藏开关。

路径第一次要手填（写到 `~/.dsh/maimai-bridge/settings.json`）：

- **MaiBot 目录**：`<MaiBot>`（含 `config/bot_config.toml` 的那个）
- **Python 解释器**：能 import `tomllib` 的 Python
- **桥接脚本目录**：本仓库根目录
- **preset 输出目录**：`<本仓库>/dsh-preset`

### 3. DSH 的「麦麦」模式（可选）

设置页点「重新生成 preset」，或直接：

```bash
python emit_preset.py --home <MaiBot> --python <python> --out ./dsh-preset
```

生成的 `dsh-preset/` 是一个 Cordis bundle，按 DSH 的 bundle 方式装进 profile 即可。这个模式的人格是**现读**的——每次会话先跑 `maimai.py --home <MaiBot> persona`，所以你改 MaiBot 的人设就生效，不用重新生成。

### 4. 自动同步（可选，Windows）

```powershell
schtasks /create /tn "MaiBot-Sync-AM" /tr "powershell -NoProfile -ExecutionPolicy Bypass -File <本仓库>\sync_daily.ps1" /sc daily /st 09:00 /f
schtasks /create /tn "MaiBot-Sync-PM" /tr "powershell -NoProfile -ExecutionPolicy Bypass -File <本仓库>\sync_daily.ps1" /sc daily /st 21:00 /f
```

同步什么：只同步 DSH 记忆库里 **topic 全量 + project 的 `overview` / `decisions` / `quotes` / `todo`**——「发生了什么、拍板了什么、原话怎么说的」。

**不同步** `fact` / `lesson` / `rules` / `soul` / `user`——那些是操作知识和太私人的东西，搬进麦麦的记忆只会稀释她，让她变得不像群里那个人。

每条压到 120 字、整批 1500 字，一次最多 8 条。`sync-state.json` 记已写过的 id，不会重复写。

## 命令与工具

### 命令（你在群里打）

| 命令 | 干什么 |
|---|---|
| `/看 <平台> <关键词>` | 去那个平台搜，结果贴回来 |
| `/看 <关键词>` | 用必应搜 |
| `/看 <网址>` | 直接打开 |
| `/看` | 给用法 |
| `/看视频 <BV号 / 链接 / 关键词>` | 打开视频读字幕 + 弹幕 + 热评 |

`/看` 和 `/看视频` 都不占「她自主出去逛」的额度——人手触发的不该被冷却挡。

### 工具（她自己决定用）

| 工具 | 干什么 |
|---|---|
| `maimai_persona` | 读当前人格 |
| `maimai_recall` | 查麦麦的长期记忆 |
| `maimai_remember` | 把值得留的写进记忆 |
| `maimai_speak` | 用她的口吻生成一段（只返回不发） |
| `dsh_task` | 把活交给 DSH headless 执行 |
| `look_around` | 出去看一个平台（带每小时额度与冷却） |
| `watch_video` | 真看一个 B站视频 |
| `bili_react` | 自己点赞 / 收藏 |
| `bili_taste_status` | 查今天动手几次、上限多少 |

## 各平台现在到底能看什么

无头浏览器不是万能的。下表是实测结果（每站真开浏览器真抓）：

| 平台 | 能看吗 | 看的是什么 |
|---|---|---|
| **B站** | ✅ | 搜索结果：标题 / 作者 / 播放 / 时长 / 日期 / 链接 |
| **Steam** | ✅ | 搜索结果：标题 / 发售 / 价格 / 链接 |
| **GitHub** | ✅ | 整段文本（配方较粗，够判断是哪个项目） |
| **微博** | ✅ | 手机版首页信息流：正文 / 发布者 |
| **豆瓣** | ✅ | 首页热门话题：话题名 / 热度 |
| **小黑盒** | ✅ | bbs 首页信息流：标题 / 正文摘要 |
| **贴吧** | ❌ | 直接甩「百度安全验证」滑块 |
| **知乎** | ❌ | 「安全验证」，未登录只给一句提示 |
| **小红书** | ❌ | 登录墙 |

后三个不是配方没写对，是**无头浏览器进不去**——它们认设备指纹，不给内容。想硬看的唯一办法是有头模式（`browse.headless = false`），代价是屏幕上真会闪出一个浏览器窗口，服务器上没桌面则不可用。

微博 / 豆瓣 / 小黑盒的**搜索页**同样是死路，所以给了关键词时不会硬撞搜索页，直接看首页流，并在返回的「来源」里写明「只能看首页流」。

## 配置

配置在 `<MaiBot>/plugins/maimai_bridge/config.toml`（也可以在 DSH 设置页里改，两边读同一份文件）。

### `[plugin]`

| 键 | 默认 | 说明 |
|---|---|---|
| `enabled` | `true` | 总开关 |
| `recall_limit` | `5` | `maimai_recall` 不传条数时用这个，最后夹在 1–20 |
| `allow_memory_write` | `true` | 关掉后 `maimai_remember` 直接拒绝 |
| `dsh_command` | `dsh` | DSH 可执行文件 |
| `dsh_profile` | `headless` | 用哪个 profile 跑（headless 没有 GUI 工具） |
| `dsh_timeout_seconds` | `240` | 单次任务超时 |
| `dsh_cwd` | 空 | 给 DSH 的工作目录，空 = 继承 MaiBot 的 |
| `dsh_extra_args` | 空 | 追加参数；填 `--session-id <id>` 可以让多次调用共用一段会话 |
| `speak_model` | 空 | `maimai_speak` 用哪个模型，空 = 默认 |

### `[browse]`（出去看看）

`enabled` / `browser_channel`（默认 `msedge`）/ `headless` / `timeout_seconds` / `max_chars` / `wait_after_load_ms` / `cooldown_seconds` / `max_per_hour`。

### `[video]`（看视频）

`enabled` / `desc_max_chars` / `danmaku_limit` / `comment_limit` / `related_limit` / `keyword_take_first` / `credential_file`。

`credential_file` 默认指向 `plugins/maibot.bilibili-browser/bili_credential.json`——和另一个刷 B 站的插件共用同一份登录态。**路径必须相对 MaiBot 的 data 目录**，绝对路径会被静默忽略。

### `[taste]`（喜欢就自己动手）

`enabled` / `auto_like` / `auto_fav` / `fav_folder` / `daily_limit` / `cooldown_seconds` / `require_reason` / `dry_run`。

## 登录 B站

字幕这条链路必须登录。两种方式：

1. **扫码**：在 DSH 设置页「平台登录 → B站」点「扫码登录」，弹出一个浏览器窗口，扫完自动落盘（`bili_login.py`）。
2. **手工**：浏览器 F12 → Application → Cookies → bilibili.com → 复制 `SESSDATA`，粘进设置页。

登录态会写到两个地方：`plugins/maimai_bridge/logins.json`（给 `/看` 用）和 `data/plugins/maibot.bilibili-browser/bili_credential.json`（给看视频用）。

**凭证不进版本库**：`.gitignore` 已经排掉 `logins.json`、`bili_credential.json`、`browser-profile/`。

## 设计取舍

- **发租约，而不是发权限。** 让麦麦「出去看看」这类事，应该是「申请 → 你授权 → 限时活动 → 回来汇报」，不是给她一张永久通行证。
- **代发的话必须过审。** DSH 不直接持有发言权，它只能在 stdout 里用 `[[speak]]…[[/speak]]` 声明想说的话，由插件校验后发出——DSH 只是一张写好台词放进盒子里的嘴。
- **人格单一真源。** 人设只在 MaiBot 的 `bot_config.toml` 里改，DSH 侧永远现读，不做第二份拷贝。
- **记忆只同步事件。** 见上。
- **不假装看见。** 撞上验证页就说「被挡住」，没字幕就说「字幕没拿到」，宁可少说一句也不编。这条写在工具描述和返回文案里，是硬约束。
- **只读优先。** 点赞和收藏是唯一两个写操作，各有额度、冷却、必须说理由，还能 `dry_run` 空跑。发评论、私信、弹幕的能力一个都没做。

## 已知限制

- 贴吧 / 知乎 / 小红书看不了（见上表）。
- B站 AI 字幕大概率要大会员；没字幕的视频只能靠弹幕和评论判断。
- `look_around` 走串行锁，同一时刻只有一个浏览器实例，并发请求会排队。
- Playwright 每次启动浏览器要 3–6 秒，冷启动更慢。
- 无头模式抓的是渲染后的文本，遇到重前端站点（小黑盒）偶尔只拿到半页。

## 踩过的坑

这些是实打实踩出来的，写下来省得你重踩：

- **MaiBot 插件必须实现 `on_config_update`**，否则注册直接失败（SDK 基类有默认实现，但 loader 要求子类显式实现）。
- **`config.toml` 里要有 `config_version`**，1.3.x 起不再兼容无版本配置。
- **`@Command` 的返回值不会自动发送**：三元组里第二个元素只是日志文本，要发必须自己 `await ctx.send.text(text, stream_id)`。
- **`--home` 是全局参数，必须写在子命令前**：`maimai.py --home <MaiBot> persona`。
- **WebUI 认证只能用 Cookie** `maibot_session=<access_token>`；`Authorization: Bearer` 一律 401。
- **`access_token` 在 `<MaiBot>/data/webui.json`**；`token_source` 是 `configured` 时每次启动不变。
- **DSH 插件注册 HTTP 路由要 `export const inject = ['webServer']` + `ctx.effect(() => ctx.webServer.register(...))`**；`ctx.get('webServer')` 在 apply 阶段拿不到，`ctx.inject([...])` 的调用式写法在本加载器里不生效。最可靠的办法是去抄 `node_modules` 里能正常工作的插件。
- **`_manifest.json` 不能带 BOM**：`Set-Content -Encoding UTF8`（PS 5.1）会加 BOM，导致插件静默不加载，报 `Unexpected UTF-8 BOM`。
- **插件目录 ≠ 插件的 data 目录**：`ctx.paths.data_dir` 是 MaiBot 的 data 根，凭证路径算错就永远读不到，而且没报错。
- **Windows PowerShell 5.1 按 GBK 解码子进程输出**：计划任务里 Python 输出中文会变「鍐欒繘鍘讳簡」，`| ForEach-Object` 还会把任务挂住。交给 `cmd.exe /c "... >> log 2>&1"` 直写字节最稳。
- **`.ps1` 文件必须带 UTF-8 BOM**，否则 5.1 解析中文注释会报 `The string is missing the terminator`。
- **PowerShell 里不要用 `$home`**，它是只读自动变量。

## License

MIT —— 本项目自己写的部分。

`maibot-plugin/bili_video/` 里的 `client.py`、`credential.py`、`digest.py`、`store.py`、`target.py` 移植自
[DomainDream/maibot-bilibili-browser](https://github.com/DomainDream/maibot-bilibili-browser)，
同为 MIT，版权归原作者；`reactions.py`（点赞 / 收藏）是本项目新写的，没有改动移植来的文件。
