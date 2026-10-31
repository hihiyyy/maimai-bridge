# Maibot互联DSH

把 [MaiBot（麦麦）](https://github.com/Mai-with-u/MaiBot) 和 [DeepSeek Harness（DSH）](https://github.com/deepseek-ai) 连起来：**人格和记忆共用一份，需要动手时活交给 DSH，话还是她自己说。**

> MaiBot 的设计原则是「最像，而不是最好」——她不该长成一个什么都能干的机器人。
> 所以这个插件不给她堆功能：只在她需要的时候，把「看」和「干」递出去，结果回到她自己嘴里。

配套的 DSH 侧设置界面在同一个仓库的 `dsh-settings/`，装好后 DSH 的「设置 → Maibot互联DSH」和这里的 `config.toml` 读写的是**同一份文件**。

**QQ交流群：1033542800**

> **这是自用插件，不是打磨过的通用产品。** 只在 Windows + MaiBot 1.3.19 + DSH 桌面版上跑通过，依赖 Playwright + 本机 Edge + 一份 B站登录态，接口跟着 MaiBot 源码走、升级可能被打断，也没有测试和 CI。能自用，但不保证稳定。
>
> **1.1.0 起按官方结构重排、硬编码全部下沉成配置**（UA / 反爬词 / 动作红线 / 站点选择器都能改），
> 但功能面和 1.0.x 一样：这次是「里面怎么放」的重构，不是新功能。

## 它能做什么

| 能力 | 方向 | 怎么说人话 |
|---|---|---|
| **人格现读** | MaiBot → DSH | DSH 里的「麦麦」模式不存人设副本，每次开工现读这里的 `bot_config.toml` |
| **记忆互通** | 双向 | 她能查自己的 A-Memorix 长期记忆；DSH 那边发生的事也能写进来（每天 9:00 / 21:00 自动同步一次） |
| **任务互派** | MaiBot ↔ DSH | `dsh_task` 把活交给 `dsh --profile headless`，结果回来由她决定怎么讲 |
| **替她说一句** | DSH → 群 | DSH 回复里用 `[[speak]]…[[/speak]]` 声明台词，插件校验后代发；DSH 本身没有发送权 |
| **自己出去看** | 联网 | 无头浏览器打开指定平台，列表抓成结构化条目；撞上验证页会直接说「被挡住了」 |
| **能翻页点开** | 联网 | `page_act`：read / click / type / scroll / press / back，能点进第二页 |
| **真的看视频** | B站 | 读字幕、简介、弹幕抽样、热评、相关推荐，再用自己的语气聊 |
| **喜欢的自己动手** | B站 | 看完真心觉得好，自己点个赞、收进收藏夹（有日限、间隔、必须说理由） |
| **出门要打招呼** | 对她自己 | 她主动申请「想出去转多久」，你回一句「去吧」，限时通行证生效，到点自动失效并汇报 |
| **自己想起来** | 定时（默认关） | 允许时段内插件往群里塞一句「这会儿没人叫你」，让她自己决定要不要出去 |
| **有自己的反应** | — | 命令先回「收到」，结果之后再补一句她自己怎么想——不是复述条目 |

三条命令消息的节奏是刻意设计的 **收到 → 结果 → 观感**：

```
主人，收到，去B站看一眼，等我下喵～
B站 · 黑神话悟空（共 50 条）
1. 《黑神话：钟馗》15分钟实机演示
   1371.7万 · 15:53 · 8月20日
   https://www.bilibili.com/video/BV1kS8H6VERt/
...
B站那边看着挺热闹的，那个实机演示我看了两段，动作比上一代利索喵～
```

回执是因为抓取要几秒到十几秒，中间没动静会让人以为命令没生效；观感是因为「给一堆条目」不等于「她看过了」。
最后那句不是模板，是 `maisaka.reply.generate` 用她的人格现生成的——所以每次不一样，也可能说「这个没啥意思」。

## 三道闸门

她能自己动之后，刹车比油门重要：

1. **出门要打招呼** —— 她自己出不去。申请 → 你点头 → 限时通行证 → 到点自动失效并汇报。只认发起会话 + 发起人（或全局管理员）的回复，别人在群里喊「去吧」不算，别的会话说也不算；申请 15 分钟没回自动作废。
2. **动作白名单** —— `page_act` 只许六种动作。另有两条红线：碰「付款 / 下单 / 改密码 / 注销账号」这类，和「发评论 / 发私信 / @所有人」这类，直接拒绝并说明碰到第几步。这两组词**可以在配置里加**（`[actions].redlines` / `[actions].social_block`），但加进去只会更严、不会更松——内置的那批永远生效。
3. **代发要过审** —— DSH 想借她的嘴，只能声明台词，插件逐条查红线、字数、@所有人、每日额度。

## 安装

整个目录丢进 MaiBot 的 `plugins/` 下，名字保持 `maimai_bridge`：

```
<MaiBot>/plugins/maimai_bridge/
├── plugin.py            # 插件类、工具、命令、Hook
├── config.py            # 配置模型（Runner 据此生成 config.toml）
├── constants.py         # 内置默认值 + 解析
├── sites.py             # 站点知识表
├── _manifest.json
├── __init__.py
├── docs/architecture.md # 模块划分与数据流（给改代码的人看）
├── AGENTS.md            # 给 AI 协作者的仓库指令
├── README.md
├── CHANGELOG.md
└── bili_video/          # 看视频与点赞收藏的内置子包
```

`config.toml` 不进仓库——它由 Runner 首次加载时按 `config.py` 自动生成在插件目录下。
可写数据（cookie、出门记录、浏览器 profile）全部落在 `ctx.paths.data_dir`，
不在源码目录里。

装好后在 WebUI「插件管理」里点一次重新加载即可（改的是 Python 代码时点重新加载，
改的是 SDK 或依赖包时得重启 MaiBot）。日志里出现 `[maimai_bridge] 桥插件已加载` 就成了。

## 命令

| 命令 | 作用 |
|---|---|
| `/看` | 显示用法 |
| `/看 <平台> <关键词>` | 去那个平台看一圈，回执 → 结果 → 观感 |
| `/看 <任意网址>` | 直接看这个页面 |
| `/看视频 <BV号/链接/关键词>` | 打开视频，读字幕弹幕评论，回执 → 结果 → 观感 |

## 工具（13 个）

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

另有一个 HookHandler `slash_bridge`，挂在 `chat.receive.after_process` 上：
它负责两件事——①兜底识别 `/看` `/看视频` `/dshhelp`（`@Command` 层万一没接住时自己分发）；
②监听你对出门申请的回复（「去吧」/「算了」）。

> `@Command` 打头的消息如果被兜底接住，会 `abort` 掉这条消息的后续处理，
> 不会再进「读空气」，所以不会出现一条命令被回两遍的情况。

## 配置

`config.toml` 七段，DSH 设置页读写的是同一份文件，两边天然同步。
所有字段都有中文名（`json_schema_extra={"label": ...}`），WebUI 里看到的是中文标签。

| 段 | 关键项 |
|---|---|
| `[plugin]` | **`allow_dsh`**（准不准许调 DSH；插件的总开关 `enabled` 是宿主保留键，不在这一节）、`recall_limit`、`allow_memory_write`、`dsh_command` / `dsh_profile` / `dsh_timeout_seconds`、`speak_model`、**`admin_qq`**（全局管理员，可填多个） |
| `[browse]` | `enabled`、`browser_channel`（默认 msedge）、`headless`、`timeout_seconds`、`max_per_hour`、`use_profile`（持久登录态）、`profile_dir`、`user_agent`、`block_markers`（反爬判定词） |
| `[actions]` | `enabled`、`allowed`（六种动作白名单）、`max_steps`、`step_wait_ms`、`redlines`（额外红线词）、`social_block`（禁开的嘴：评论/私信/@所有人） |
| `[video]` | `enabled`、`desc_max_chars`、`danmaku_limit`、`comment_limit`、`credential_file`、`sessdata` / `bili_jct` / `proxy` |
| `[taste]` | `enabled`、`auto_like`、`auto_fav`、`fav_folder`、`daily_limit`、`cooldown_seconds`、`require_reason`、`dry_run` |
| `[outing]` | `enabled`、`owner_ids`、`default_minutes`、`max_minutes`、`daily_limit`、`approve_words`、`deny_words`、`auto_enabled`、`auto_windows`、`auto_daily_limit`、`auto_cooldown_minutes`、`auto_stream_id`、`auto_intent` |
| `[relay]` | `enabled`、`daily_limit`、`max_chars` |

`admin_qq`、`owner_ids`、`allowed`、`redlines`、`social_block`、`block_markers`、`auto_windows`
在设置页里是「一格一个、点 + 加一行」的输入框，可以填多个；`config.toml` 里写逗号分隔的字符串。

`[actions].redlines` / `[actions].social_block` / `[browse].block_markers` / `[browse].user_agent`
留空就用内置默认值——默认值在 `constants.py` 里，改默认值不用动 `plugin.py`。

## 登录

B 站要登录才读得到字幕：

```bash
python cookie_login.py --site bilibili --maibot "<MaiBot 目录>"
```

会弹一个真浏览器窗口，扫码成功自动写 `data/plugins/lirick.maimai-bridge/logins.json`，
并额外写一份 `data/plugins/maibot.bilibili-browser/bili_credential.json` 给「刷B站」插件。

其他八个平台（贴吧 / 小黑盒 / Steam / 知乎 / 微博 / 豆瓣 / 小红书 / GitHub）同样一条命令，`--site` 换名字就行；DSH 设置页里每个平台右侧也有「扫码登录」按钮。

判断登录成功是**两层**：Cookie 里的登录标志键出现（B站 `SESSDATA`、贴吧 `BDUSS`、知乎 `z_c0`…），
**并且**真拿这份 Cookie 去问一次该平台的「我是谁」接口，接口认了才算成功——
所以不会出现「浏览器刚打开就显示登录成功」这种假阳性。
小红书和豆瓣没有可用的「我是谁」接口，退回看 Cookie 值相对刚打开时有没有变过。

所有平台共用 `data/plugins/lirick.maimai-bridge/browser-profile`，登录态留着，`look_around` 走出去也带着。

## 和 DSH 的关系

```
你在群里说话
    ↓
麦麦读人设、查记忆、决定怎么回
    ↓ 需要动手时
dsh_task → dsh --profile headless "任务"
    ↓
DSH 干活（写代码 / 查资料 / 逛网页），结果回给麦麦
    ↓
麦麦用自己的人设把结果说出来
```

人格是**现读**的：DSH 那边每次开工会跑 `maimai.py persona` 读最新人设，你改 `bot_config.toml`，两边一起变。
记忆是**双向**的：她能查 A-Memorix，DSH 也能把「这边发生的事」写进去。

## 安全边界

- **不冒充她发消息**，除非她自己声明了台词、且过了校验
- **不碰钱和账号**：付款、充值、改密码、注销，一律拒绝
- **不往外说话**：发评论、发弹幕、发私信、@所有人，一律拒绝
- **不假装看见**：抓不到就说没看到，抓回来的只是素材
- **点赞有额度**：默认每天 10 次，冷却 5 分钟，必须说理由
- **遇到验证码就停**：不硬试、不猜内容

## 常见问题

**插件加载不了？** 查 `maibot.log` 里 `[maimai_bridge]` 那几行。常见原因是 `_manifest.json` 带 BOM、或者 Host 版本超出 `host_application.max_version`。

**命令没反应？** 先看核心适配器通不通——QQ 消息进不来时，所有斜杠命令一起失效。查日志里有没有 `NapCat 适配器已连接`。

**`/看` 有结果但不发群？** 这插件自己会发。如果你改了 `command_look`，记得返回值不会自动发送，要 `await self.ctx.send.text(...)`。

**视频字幕为空？** 三种可能：没登录、视频本身没字幕、或者要大会员才能读 AI 字幕。

**点不了、翻不了页？** `page_act` 需要 `[actions] enabled = true`，且动作名要在 `allowed` 里。

## License

MIT。`bili_video/` 下的 `client.py` / `credential.py` / `digest.py` / `store.py` / `target.py` 移植自 [DomainDream/maibot-bilibili-browser](https://github.com/DomainDream/maibot-bilibili-browser)（MIT），`reactions.py` 为本项目自写。
