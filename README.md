# Maibot互联DSH

把 [MaiBot（麦麦）](https://github.com/Mai-with-u/MaiBot) 和 [DeepSeek Harness（DSH）](https://github.com/deepseek-ai) 接起来：

**麦麦负责「像人」，DSH 负责「干活」，人格和记忆两边共用一份。**

> MaiBot 的设计原则是「最像，而不是最好」——她不该长成一个什么都能干的机器人。
> 所以这个项目不给她加功能，只在她需要动手的时候，把活递给 DSH，干完再以她自己的口吻说出来。

**版本 1.0.1** · 自用项目 · MIT

---

**QQ交流群：1033542800**

## ⚠️ 这是我自用的插件，不是通用产品

写清楚免得你踩坑：

- **只在我自己那台机器上跑通过**：Windows + MaiBot 1.3.19 一键包 + DSH 桌面版。Linux、Docker、macOS 全没试过。
- **路径是硬编码的**：配置默认指向我本机的目录结构，你得自己在设置页改 `settings.json`。
- **依赖几个第三方东西**：Playwright + 本机 Edge、一个能用的 B 站登录态、MaiBot 的 `plugin_runtime`（1.3.x）。少一样就有一段功能是灰色的。
- **接口是跟着 MaiBot 源码走的**：`@Command`、`ctx.maisaka.*` 这些没有稳定承诺，MaiBot 升级可能直接打断。
- **没有测试、没有 CI**：所有「能跑」都是我在群里手点出来的。
- **1.0.0 是「功能齐了」的正式版**，不是「打磨好了」的成熟版。之前的 1.9.x–2.4.0 是开发期编号，现在归一到 1.0。

如果你要的是一个能长期维护的项目，这里大概率不是。但如果你也在折腾「让 bot 有点自主性」这件事，里面的踩坑记录应该能省你几天。

**状态**：能自用，但不保证稳定性。Issue 欢迎，能不能修看缘分。

---

## 它现在能做什么

| 能力 | 方向 | 说明 |
|---|---|---|
| **人格现读** | MaiBot → DSH | DSH 的「麦麦」模式不内联人设，每次开工现读 `bot_config.toml` 的 `[personality]`，你改麦麦的人设，DSH 这边跟着变 |
| **记忆只读** | MaiBot → DSH | 在 DSH 里检索麦麦的 A-Memorix 长期记忆 |
| **记忆写入** | DSH → MaiBot | 把「DSH 这边发生的事」写进麦麦的长期记忆 |
| **任务互派** | MaiBot ↔ DSH | 工具 `dsh_task` 把活交给 `dsh --profile headless`，结果回到麦麦手里，由她决定怎么说 |
| **替她说一句** | DSH → MaiBot | DSH 可以在回复里用 `[[speak]]…[[/speak]]` 声明一句台词，插件校验后代发；DSH 本身没有发送权 |
| **自动同步** | 定时 | 每天 9:00 / 21:00 把 DSH 的项目记忆压成一段「最近发生的事」写进麦麦记忆 |
| **自己出去看** | MaiBot → 网络 | `/看 <平台> <关键词>` 或 `look_around`，无头 Edge 真打开网页，抽成结构化条目 |
| **能翻页点开** | MaiBot → 网络 | `page_act`：read / click / type / scroll / press / back 六种动作，能点进第二页 |
| **真的看视频** | MaiBot → B站 | `/看视频 <BV号>` 读字幕、简介、弹幕抽样、热评，让她能聊内容而不是标题 |
| **喜欢就动手** | MaiBot → B站 | 看完真喜欢的自己点赞 / 收藏，有日额度、冷却、必须说理由 |
| **出门要打招呼** | MaiBot → 主人 | 她主动申请「想出去转多久」，你回一句「去吧」，限时通行证生效，到点自动失效并汇报 |
| **自己想起来** | 定时 → MaiBot | 允许时段内，插件往群里塞一句「这会儿没人叫你」，让她自己决定要不要出去 |
| **九个平台扫码登录** | 设置页 | 每个平台点「扫码登录」都会弹浏览器，登录成功自动存 Cookie，不用手抄 SESSDATA |

三条命令消息的节奏是刻意设计的：**收到 → 结果 → 观感**。回执是因为抓取要几秒到十几秒，中间没动静会让人以为命令没生效；观感是因为「给一堆条目」不等于「她看过了」。

### 三道闸门

她越能自己动，越需要有人踩刹车。这里有三层：

1. **出门要打招呼**：她自己出不去。要先发申请、等你点头、拿到限时通行证，到点自动失效。
2. **动作白名单**：`page_act` 只许 read / click / type / scroll / press / back。另有两条**写死的红线**（配置文件改不了）——碰「付款、下单、改密码、注销账号」这类，和「发评论、发私信、@所有人」这类，直接拒绝并说明碰到哪一步。
3. **代发要过审**：DSH 想借她的嘴说话，只能用 `[[speak]]` 声明台词，插件逐条查红线、字数、@所有人、每日额度，通过了才发。

---

## 组成

```
.
├── maimai.py             # CLI：读人格 / 检索记忆 / 写入记忆
├── emit_preset.py        # 生成 DSH 侧「麦麦」模式的 bundle
├── persona_sync.py       # 只生成人格文本（emit_preset 的简化版）
├── sync_to_maimai.py     # 把 meow-memory 的项目记忆同步进麦麦
├── sync_daily.ps1        # 计划任务入口（Windows）
├── bili_login.py         # 扫码登录 B站（专用版，写两份凭证）
├── cookie_login.py       # 扫码登录任意平台（九个平台通用版）
├── maibot-plugin/        # 麦麦侧插件（MaiBot plugin，id: lirick.maimai-bridge）
├── dsh-settings/         # DSH 侧设置界面（Cordis bundle，设置 → Maibot互联DSH）
└── dsh-preset/           # 由 emit_preset.py 生成，不进版本库
```

四块各自独立安装，可以只用其中一两个。

## 安装

### 0. 需要什么

- MaiBot（1.3.19 以上）跑起来，WebUI 能打开（端口见 `config/bot_config.toml` 的 `[http].port`，默认 8001）
- DSH（带 `webServer` 服务的版本）
- Python 3.10+（跑桥接脚本）
- 想用「出去看看 / 看视频」：`pip install playwright` + 本机装了 Edge（用 `channel="msedge"`，不用下载 Chromium）

> 脚本里的 MaiBot 目录和 WebUI 地址都**不写死**：依次取命令行参数、环境变量
> （`MAIBOT_HOME` / `MAIBOT_WEBUI`）、一键包默认位置、`config/bot_config.toml`。
> 指定了却对不上会直接报错，不会静默退到别的路径。

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

重启 MaiBot，日志里出现 `[maimai_bridge] 桥插件已加载` 就成了。

### 2. 扫码登录

启动任意一个平台：

```bash
python cookie_login.py --site bilibili --maibot "<MaiBot 目录>"
```

会弹一个真实浏览器窗口，你在里面扫码登录，成功之后自动写 Cookie 并关窗。
也可以用 DSH 设置页里的「扫码登录」按钮，效果一样。

九个平台都能这么登：`bilibili` / `tieba` / `xiaoheihe` / `steam` / `zhihu` / `weibo` / `douban` / `xhs` / `github`。

### 3. DSH 侧设置界面

```bash
dsh plugin --profile <你的 profile> add <本仓库>/dsh-settings
```

装完重启 DSH，设置里会多一页「Maibot互联DSH」，能改插件参数、看记忆、查登录态、一键扫码。

### 4. DSH 侧「麦麦」模式

```bash
python emit_preset.py --home "<MaiBot 目录>" --python "<python>" --out "<本仓库>/dsh-preset"
dsh plugin --profile <profile> add <本仓库>/dsh-preset
```

重启后模式选择里多出「麦麦」。

### 5. 自动同步（可选）

```powershell
schtasks /create /tn "MaiBot-Sync-AM" /sc daily /st 09:00 /tr "powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File <本仓库>\sync_daily.ps1"
```

---

## 命令与工具

### 聊天里能用的命令

| 命令 | 作用 |
|---|---|
| `/看` | 显示用法 |
| `/看 <平台> <关键词>` | 去那个平台看一圈，回执 → 结果 → 观感 |
| `/看 <任意网址>` | 直接看这个页面 |
| `/看视频 <BV号/链接/关键词>` | 打开视频，读字幕弹幕评论，回执 → 结果 → 观感 |
| `/dshhelp` | 一张说明书：聊天指令、她现在的开关状态、管理员是谁、今天动过几次手 |

### 给模型用的工具（13 个）

| 工具 | 用途 |
|---|---|
| `maimai_persona` | 读麦麦当前人设 |
| `maimai_recall` | 检索麦麦的长期记忆 |
| `maimai_remember` | 让麦麦自己记一件事 |
| `maimai_speak` | 用麦麦的口吻生成一句话（不发送） |
| `dsh_task` | 把活交给 DSH |
| `look_around` | 打开一个网页看内容 |
| `page_act` | 在网页上做动作（翻页、点开、滚动） |
| `watch_video` | 看 B 站视频内容 |
| `bili_react` | 点赞 / 收藏 |
| `bili_taste_status` | 今天动过几次手 |
| `ask_permission` | 申请出门（问主人要通行证） |
| `end_outing` | 提前结束出门并汇报 |
| `outing_status` | 现在能不能出去 |

另有一个消息事件 `outing_reply`：监听你对出门申请的回复（「去吧」/「算了」）。

---

## 各平台现在到底能看什么

| 平台 | 状态 | 说明 |
|---|---|---|
| B站 | ✅ | 搜索页结构化：标题 / 作者 / 播放 / 时长 / 日期 |
| Steam | ✅ | 商店搜索：标题 / 发售日 / 价格 |
| 微博 | ✅ | 手机版首页信息流 + 热搜榜 |
| 豆瓣 | ✅ | 首页热门话题 + 电影榜单 |
| 小黑盒 | ✅ | 社区首页信息流（标题 / 正文摘要） |
| GitHub | ⚠️ | 能抓搜索结果，但字段粗糙（统一叫「条目」） |
| 贴吧 | ❌ | 无头浏览器直接被「百度安全验证」拦 |
| 知乎 | ❌ | 同上，安全验证 / 登录墙 |
| 小红书 | ❌ | 登录墙 + 验证码 |

后三个**不是配方问题**——换了四五个入口全是验证页。真要过得用真浏览器指纹 + 登录态，那已经不是「看一眼」的成本了。

---

## 配置

`<MaiBot>/plugins/maimai_bridge/config.toml`，七段：

| 段 | 管什么 |
|---|---|
| `[plugin]` | 总开关、记忆条数、DSH 命令与超时、说话用哪个模型、**全局管理员 QQ**（逗号分隔多个） |
| `[browse]` | 浏览器：开不开、用哪个 channel、无头不无头、超时、每小时额度、**是否用持久 profile**（登录态） |
| `[actions]` | `page_act`：开不开、允许哪些动作、一次最多几步、每步等多久 |
| `[video]` | 看视频：字幕长度、简介长度、弹幕/评论条数、**凭证文件路径** |
| `[taste]` | 点赞收藏：开不开、只赞还是也收藏、收藏夹、日额度、冷却、必须说理由、演练模式 |
| `[outing]` | 出门：开不开、谁说了算、默认/最长时长、每日次数、**自动叫醒**（时段 / 额度 / 冷却 / 自定义台词） |
| `[relay]` | 替她说一句：开不开、每日几句、单句字数上限 |

DSH 设置页读写的是**同一份 config.toml**，所以两边天然同步——你在哪边改都一样。

---

## 登录

### 扫码（推荐）

设置页每个平台右侧有「扫码登录」，或者命令行：

```bash
python cookie_login.py --site <平台> --maibot "<MaiBot 目录>"
```

判断登录成功看的是 Cookie 里的登录标志键，不看页面长什么样：

| 平台 | 认的键 |
|---|---|
| B站 | `SESSDATA` |
| 贴吧 | `BDUSS` |
| 小黑盒 | `heybox_id` / `heybox_uid` |
| Steam | `steamLoginSecure` |
| 知乎 | `z_c0` |
| 微博 | `SUB` |
| 豆瓣 | `dbcl2` |
| 小红书 | `web_session` |
| GitHub | `user_session` |

所有平台共用同一个 `browser-profile`，登录态留着，`look_around` 走出去也带着。

### 手工（B站 专用）

浏览器 F12 → Application → Cookies → bilibili.com → 复制 `SESSDATA`，贴在设置页的输入框里。

读字幕需要它，所以 B 站还会额外写一份 `data/plugins/maibot.bilibili-browser/bili_credential.json` 给「刷B站」插件用。

---

## 设计取舍

- **不给 DSH 发送权**。DSH 只能说「我有话想发」，能不能发、发什么，由插件判断。这样 DSH 再聪明也没法绕过闸门。
- **不假装看见**。抓不到就说「没看到」，抓回的内容只是素材，她可以挑着聊，但绝不会因为没内容就编。
- **只读优先**。能不做写操作就不做；必须做的（点赞收藏）单独一段开关 + 额度 + 冷却 + 理由。
- **人格现读不拷贝**。拷一份人格到 DSH 就会有两个版本的麦麦，改了一边另一边不知道。
- **同步只挑「事」**。只同步 topic 和 project 的 overview/decisions/quotes/todo；fact/lesson/rules 是操作知识，搬过去只会稀释她的人格。
- **她的看法是她自己说的**。「观感」不是模板，是 `maisaka.reply.generate` 用她的人格现生成的——所以每次都不一样，也可能说「这个没啥意思」。

## 已知限制

- **前三个平台固定看不了**（贴吧 / 知乎 / 小红书），无头浏览器在这三家面前没有胜算。
- **AI 字幕要大会员**。没大会员时只有 UP 主自己传的字幕能读，大部分视频会显示「字幕没拿到」，此时靠简介 + 弹幕 + 热评判断内容。
- **浏览是串行的**。一次只能开一个浏览器，她「出去转」的时候你 `/看` 会排队。
- **冷启动 3–6 秒**。每次开浏览器都要起进程。
- **重前端站点只拿得到半页**。等 1.2 秒后仍没渲染完的，抓下来就是残缺的。
- **自动叫醒默认关着**，而且只在允许时段、有额度、不在冷却、她没在外面时才叫。

## 踩过的坑

留在这里，省你重踩一遍：

1. **`_manifest.json` 带 BOM 会静默不加载**。PowerShell 的 `Set-Content -Encoding UTF8` 默认加 BOM，MaiBot 报 `Unexpected UTF-8 BOM` 后连失败上报都挂掉。写文件要用 `UTF8Encoding($false)`。
2. **插件数据目录 ≠ MaiBot 数据目录**。`_video_data_dir()` 返回的是 MaiBot 的 `data/`，不是插件自己的子目录，写凭证写偏了就是「明明配好了却读不到」。
3. **`@Command` 的返回值不会发出去**。三元组里第二项只是日志文本，要发言必须自己 `await self.ctx.send.text(...)`。
4. **适配器配反**。一键包默认开着 `snowluma-adapter`（连 7988）把 `napcat-adapter`（连 7998）关着，结果收得到消息发不出去。而且 `napcat-adapter` 的 manifest 写着 `max_version 1.2.99`，Host 1.3.19 直接拒绝加载——所有斜杠命令一起失效。
5. **`_resolve_recipe("微博", ...)` 查不到 `"weibo"`**。查表前不规范化输入，配方永远是空，还不报错。
6. **空壳卡片**。微博先渲染 10 个空 `div.card.m-panel` 再填内容，`matched>0` 但 `items=0`，要 `wait_for` 具体选择器。
7. **`pass` 是 Python 关键字**，pydantic 字段名用不了，`alias` 也救不回来，只能换段名。
8. **DSH 插件的 Host 侧不热重载**。改 `index.js` 必须重启 DSH，改 `client.js` 却能靠 HMR 自动生效——两边版本不一致时会出现「页面报未知接口」。
9. **`-Tail` 看日志会被刷屏冲掉**。适配器每 5 秒重连一次，把启动那几行淹了，得整文件搜。

---

## 版本

- **1.0.1**（2026-10-31）：加 `/dshhelp` —— 一张说明书，列出聊天指令、她现在的开关状态、管理员是谁、今天动过几次手。同时修好 DSH 侧「麦麦」模式：人格从「每次会话现读」改成生成时内联（现读要靠 agent 主动跑命令，跑不到就退回兜底人设），并补齐两个工具的必填配置。
- **1.0.0**（2026-10-31）：功能齐了。人格/记忆互通、双向调用、九个平台扫码登录、看网页翻页、看视频、点赞收藏、出门通行证、自动叫醒、代发。
- 开发期编号 1.1.0 → 2.4.0 已合并进 1.0.0，详见 `maibot-plugin/CHANGELOG.md`。

## License

MIT。`maibot-plugin/bili_video/` 下的 `client.py` / `credential.py` / `digest.py` / `store.py` / `target.py` 移植自 [DomainDream/maibot-bilibili-browser](https://github.com/DomainDream/maibot-bilibili-browser)（MIT），`reactions.py` 为本项目自写。
