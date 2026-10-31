# 架构说明

> 改了模块划分、数据流向、关键取舍，就同步这份文件。它是这个插件「为什么长这样」的唯一记录。

## 一、它夹在哪两个东西中间

```
        ┌──────────────────────┐          ┌──────────────────────────┐
        │  MaiBot（麦麦）      │          │  DeepSeek Harness（DSH） │
        │  QQ 群里的那个角色   │          │  你的编码 / 电脑操作 Agent│
        └──────────┬───────────┘          └─────────────┬────────────┘
                   │  Host ⇄ Runner IPC（msgpack）       │
                   │  Tool / Command / Hook              │  HTTP（WebUI）
                   ▼                                     ▼
        ┌────────────────────────────────────────────────────────────┐
        │                      maimai_bridge                         │
        │  人格互通 · 记忆互通 · 双向调用 · 出去看看 · 看视频 · 代发   │
        └────────────────────────────────────────────────────────────┘
```

DSH 侧另有两个配套包（不在本目录）：`dsh-preset/`（把当前人格写进 DSH 的「麦麦」模式）
与 `dsh-settings/`（DSH 设置页里的「Maibot互联DSH」面板）。

## 二、模块划分

| 文件 | 职责 | 不该放什么 |
| --- | --- | --- |
| `plugin.py` | 插件类、组件装饰器、业务流程编排 | 配置模型、站点表、可变的默认值 |
| `config.py` | **全部**配置模型的唯一定义处 | 业务逻辑 |
| `constants.py` | 内置默认值（UA / 拦截词 / 红线词）+ `resolve_*` | 站点知识 |
| `sites.py` | 站点知识（搜索模板 / 首页 / 抽取配方 / 规范名） | 业务逻辑 |
| `bili_video/` | B站 接口层（签名、凭证、字幕、评论、点赞收藏） | 桥接流程 |

为什么这么分：**会跟着外部世界变的东西要和会跟着我们想法变的东西分开**。
网站改版只动 `sites.py` 或配置，产品逻辑只动 `plugin.py`。

## 三、一次「出去看看」的数据流

```
麦麦决定去看
   │
   ├─ tool_look_around(site, query)
   │      │
   │      ├─ sites.canonical_site()         把「B站 / b站 / bili」统一成 bilibili
   │      ├─ SITE_BROWSE_ONLY 判定            微博/豆瓣/小黑盒 → 只给首页（搜索页是死路）
   │      ├─ SITE_TEMPLATES / SITE_HOMES       拼 URL
   │      ├─ _open_browser_context()           持久 profile（与扫码登录共用 cookie）
   │      ├─ 反爬判定：constants.resolve_block_markers() 命中就停
   │      ├─ sites.resolve_recipe()            按站点挑选择器，选不到回退整页正文
   │      └─ 组装文字 → 交给麦麦当上下文
   │
   └─ tool_page_act(动作)                      允许点、填、翻页、滚动
          │
          ├─ validate_action()                 白名单
          ├─ constants.resolve_action_redlines()   钱 / 账号 → 拒
          └─ constants.resolve_action_social()     对外说话 → 拒
```

## 四、斜杠命令为什么有两套入口

`@Command(pattern=...)` 在部分部署上没有被 `find_command_by_text` 接住（见
issue #1），所以除了三个 `@Command`，还有一条兜底：

`@HookHandler("chat.receive.after_process", mode=BLOCKING, order=EARLY)`
→ `handle_slash_bridge`：拿 `processed_plain_text`，以 `/` 开头就按 `_SLASH_ROUTES`
匹配，命中就自己调对应的 `command_*`，然后返回 `{"action": "abort"}` 把消息从主流程里摘掉，
避免它继续走到「读空气」。

为什么挂这个 Hook：`chat.receive.after_process` 在主链里是实打实 `await` 的，
且 `HookSpec` 声明了 `allow_abort=True`，能真正拦住后续。

## 五、数据放在哪

| 位置 | 内容 | 进仓库吗 |
| --- | --- | --- |
| `ctx.paths.data_dir`（模块级 `_DATA_DIR`） | `outing.json` / `taste.json` / `relay.json` / `logins.json` / `bili_credential.json` / `browser-profile/` | 否 |
| 插件源码目录 | `bili_video/`、模板、文档 | 是 |
| `config.toml`（Runner 生成） | 用户配置 | 否 |

「先申请再出去」的流程状态：`outing.json` 存当前租约（谁批的、几点到期、额度用了几次）。
到期不是靠定时器，是**每次访问时按 `expires_at` 判定**，这样重启也不会漏。

## 六、关键取舍

- **不让 DSH 直接发消息**。DSH 只能写 `[[speak]]台词[[/speak]]`，由插件校验长度、
  每日额度、红线后代发。理由：发出去的话收不回来，必须留一道闸。
- **动作白名单而不是黑名单**。只放行明确允许的动作；红线词是**额外的**第二道闸。
- **点赞收藏必须给理由**（`taste.require_reason`）。没有理由的「喜欢」不值得记住。
- **站点配方可配置**。网站改版是常态，写死等于每次都要发新版。
- **额度用 `daily_limit` + `cooldown`，不用窗口限流**。她的行为是低频、事件驱动的，
  滑动窗口没有意义，按天计数更好理解也更好解释给她听。
