# AGENTS.md — 给在这个插件仓库工作的 AI

这是 **maimai_bridge**：把 MaiBot（麦麦）和 DeepSeek Harness（DSH）连起来的桥插件。
任何 AI 助手在本仓库动手前先读完本文件。

## 权威参考（遇到疑问按此顺序查）

1. **本仓库 `docs/architecture.md`**：模块划分、数据流、设计取舍 —— 改代码前先读，改完同步。
2. **SDK / MaiBot 主程序源码**：行为疑问的唯一真相。
3. **`maibot-plugin-dev` 技能**：SDK 代理签名速查、组件规范、常见陷阱、发布收录规则。
   **用作加速器而非最终答案**：它是快照，可能落后于你的环境；与源码冲突时一律以源码为准。

## 这个插件在做什么

四件事 + 三个进阶能力：

| 能力 | 入口 | 说明 |
| --- | --- | --- |
| 人格互通 | `api_persona` / `tool_persona` | 把麦麦当前人格（人设 / 风格 / 表达）暴露给 DSH |
| 记忆互通 | `tool_recall` / `tool_remember` | 读她的 A-Memorix 长期记忆；也能请求她记下一件事 |
| 双向调用 | `tool_dsh_task` / `tool_speak` | 麦麦把活交给 DSH；DSH 用她自己的口吻说话 |
| 出去看看 | `tool_look_around` / `command_look` | 无头浏览器去看 B站 / 贴吧 / 小黑盒 / Steam… |
| 看视频 | `tool_watch_video` / `command_watch_video` | 走 B站 接口读字幕 / 简介 / 弹幕 / 热评 |
| 喜欢就动手 | `tool_bili_react` / `tool_bili_taste_status` | 看完真喜欢的，自己点赞 / 收藏（有额度和冷却） |
| 出门要打招呼 | `tool_ask_permission` / `tool_end_outing` / `tool_outing_status` | 申请 → 批准 → 限时 → 自动失效 → 汇报 |

## 目录结构

```
maimai_bridge/
├── _manifest.json      # 插件元信息（v2 严格模式，多余字段直接拒载）
├── plugin.py           # 插件类 + 组件装饰器 + 业务逻辑
├── config.py           # 全部配置模型（唯一来源，Runner 据此生成 config.toml）
├── constants.py        # 内置默认值（UA / 拦截词 / 红线词）+ 解析函数
├── sites.py            # 站点知识表（模板 / 首页 / 抽取配方 / 规范名）
├── bili_video/         # B站 接口层（移植自 DomainDream/maibot-bilibili-browser，MIT）
├── docs/architecture.md
├── __init__.py
└── .gitignore
```

## 开发规矩

- **配置**：`config.toml` 是首次运行按 `config.py` 自动生成的**运行时产物**，不进 git。
  `[plugin].enabled` 是**宿主保留键**（顶部启停 + Runner 激活门禁共用），
  配置模型里**不要声明它**；需要自己的开关就换个名字（本插件是 `allow_dsh`）。
- **不写死会变的东西**：UA、反爬拦截词、动作白线词、站点选择器，一律走 `config.py` 的字段 +
  `constants.py` / `sites.py` 的 `resolve_*` 兜底。网站改版时用户改配置即可，不用等发版。
- **可写数据只进 `ctx.paths.data_dir`**：由 `on_load` 里的 `bind_data_dir()` 绑定到模块级
  `_DATA_DIR`；源码目录保持只读。新增文件一律 `_DATA_DIR / "xxx.json"`。
- **三个生命周期必须都在**：`on_load` / `on_unload` / `on_config_update`，缺一个
  `_validate_sdk_plugin_contract` 直接抛 `TypeError`。
- **相对导入**：`from .config import ...`。PluginLoader 加载 `plugin.py` 时给了
  `submodule_search_locations`，本文件相当于包；这样不会和别的插件的 `config.py` 撞名。
- **`@Command` 的返回值**：三元组第二项只是日志文本，框架**不会发**；要发必须自己
  `await self.ctx.send.text(text, stream_id)`。
- **斜杠命令兜底**：`@Command` 在某些实例上没命中，所以另有
  `@HookHandler("chat.receive.after_process", ...)` 的 `handle_slash_bridge` 自己认
  `/看` `/看视频` `/dshhelp`，命中后返回 `{"action": "abort"}` 拦掉后续读空气。
- **`EventType.ON_MESSAGE` 不要用**：主程序里那个发射点是注释掉的，不会触发。
- **版本区间**：`host_application.max_version` 写实测过的「主.次」+`.99`（如 `1.3.99`）；
  `sdk.max_version` 锁当前主版本线（如 `2.99.99`），**禁止写 `999.999.999`**。
- **插件 `id` 发布后不得变更**；manifest 新增字段前先查 v2 必填/禁写清单。
- 文档一律简体中文。

## 发布规矩

- 固定流程：改代码 → 更新 `_manifest.json` 的 `version`（严格三段式）→ commit →
  打同版本 Tag（`v1.2.3`）→ 基于 Tag 发 GitHub Release（标题用纯版本号）→ 同步 `CHANGELOG.md`。
- Release Notes 只写用户能感知的更新要点：分「主要功能 / 细节」，一个功能一行按模块分组。
- README 面向用户，安装主路径写「WebUI 插件市场一键安装」；不写 SDK 安装步骤。
- push 前防泄漏自查：`data/`、`logins.json`、`bili_credential.json`、`config.toml`、
  带用户名的本机路径不得进仓库。

## 红线（违反即错，无例外）

- **LICENSE 与原作者署名一条不能删**。`bili_video/` 移植自
  [DomainDream/maibot-bilibili-browser](https://github.com/DomainDream/maibot-bilibili-browser)（MIT），
  其 `__init__.py` 里的来源声明必须保留。
- fork / 二次开发发布前先向原作者提 issue 或 PR。
- **不得让用户修改 MaiBot 主程序源码来使用本插件**；确需主程序改动，先向官方提 issue。
- 已经过审核的 Tag 不改写；修复一律发新版本号。
- 插件绝不代发涉及钱和账号的内容（`constants.DEFAULT_RELAY_REDLINES`），也绝不代发 `@所有人`
  （`constants.RELAY_MENTIONS`）。
