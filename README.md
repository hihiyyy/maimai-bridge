# Maibot × DSH 桥

把 [MaiBot（麦麦）](https://github.com/Mai-with-u/MaiBot) 和 [DeepSeek Harness（DSH）](https://github.com/deepseek-ai) 接起来：

**麦麦负责「像人」，DSH 负责「干活」，人格和记忆两边共用一份。**

> MaiBot 的设计原则是「最像，而不是最好」——她不该长成一个什么都能干的机器人。
> 所以这个项目不给她加功能，只在她需要动手的时候，把活递给 DSH，干完再以她自己的口吻说出来。

## 它能做什么

| 能力 | 方向 | 说明 |
|---|---|---|
| **人格现读** | MaiBot → DSH | DSH 的「麦麦」模式不内联人设，每次开工现读 `bot_config.toml` 的 `[personality]`，你改麦麦的人设，DSH 这边跟着变 |
| **记忆只读** | MaiBot → DSH | DSH 里能检索麦麦的 A-Memorix 长期记忆（`/api/webui/memory/records/search`） |
| **记忆写入** | DSH → MaiBot | 把「DSH 这边发生的事」写进麦麦的长期记忆（`/api/webui/memory/import/paste`） |
| **任务互派** | MaiBot ↔ DSH | 麦麦的工具 `dsh_task` 会把任务交给 `dsh --profile headless` 执行，结果回到麦麦手里，由她决定怎么说 |
| **自动同步** | 定时 | 每天固定时间把 DSH 的项目记忆压缩成一段「最近发生的事」写进麦麦的记忆 |

## 组成

```
.
├── maimai.py             # CLI：读人格 / 检索记忆 / 写入记忆
├── emit_preset.py        # 生成 DSH 侧「麦麦」模式的 bundle
├── persona_sync.py       # 只生成人格文本（emit_preset 的简化版）
├── sync_to_maimai.py     # 把 meow-memory 的项目记忆同步进麦麦
├── sync_daily.ps1        # 计划任务入口（Windows）
├── maibot-plugin/        # 麦麦侧插件（MaiBot plugin，id: lirick.maimai-bridge）
├── dsh-settings/         # DSH 侧设置界面（Cordis bundle，设置 → Maibot互联DSH）
└── dsh-preset/           # 由 emit_preset.py 生成，不进版本库
```

三个包各自独立安装，可以只用其中一两个。

## 安装

### 0. 需要什么

- MaiBot（1.3.19 以上）跑起来，WebUI 能在 `http://127.0.0.1:8001` 打开
- DSH（带 `webServer` 服务的版本）
- Python 3.10+（跑桥接脚本）

### 1. 麦麦侧插件

把 `maibot-plugin/` 整个目录复制到 MaiBot 的 `plugins/` 下，改名 `maimai_bridge`：

```
<MaiBot>/plugins/maimai_bridge/
├── plugin.py
├── _manifest.json
├── config.toml
└── CHANGELOG.md
```

重启 MaiBot，日志里应该出现：

```
[plugin.lirick.maimai-bridge] [maimai_bridge] 桥插件已加载
```

插件给你的麦麦加了五个工具：`maimai_persona` / `maimai_recall` / `maimai_remember` / `maimai_speak` / `dsh_task`。

配置在 `plugins/maimai_bridge/config.toml`（也可以在 DSH 设置页里改）：

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

### 2. DSH 侧设置界面

```
# 在 DSH 里
plugin_manager install_bundle(target: "<本仓库绝对路径>/dsh-settings")
```

装完重启 DSH，设置里会多一页「Maibot互联DSH」：连通状态、MaiBot 侧插件参数、路径、人格现读/重新生成 preset、长期记忆读写。

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
# 每天 9 点和 21 点各一次
schtasks /create /tn "MaiBot-Sync-AM" /tr "powershell -NoProfile -ExecutionPolicy Bypass -File <本仓库>\sync_daily.ps1" /sc daily /st 09:00 /f
schtasks /create /tn "MaiBot-Sync-PM" /tr "powershell -NoProfile -ExecutionPolicy Bypass -File <本仓库>\sync_daily.ps1" /sc daily /st 21:00 /f
```

同步什么：只同步 DSH 记忆库里 **topic 全量 + project 的 `overview` / `decisions` / `quotes` / `todo`**——「发生了什么、拍板了什么、原话怎么说的」。

**不同步** `fact` / `lesson` / `rules` / `soul` / `user`——那些是操作知识和太私人的东西，搬进麦麦的记忆只会稀释她，让她变得不像群里那个人。

每条压到 120 字、整批 1500 字，一次最多 8 条。`sync-state.json` 记已写过的 id，不会重复写。

## 设计取舍

- **发租约，而不是发权限。** 让麦麦「出去看看」这类事，应该是「申请 → 你授权 → 限时活动 → 回来汇报」，不是给她一张永久通行证。
- **代发的话必须过审。** DSH 不直接持有发言权，它只能在 stdout 里用 `[[speak]]…[[/speak]]` 声明想说的话，由插件校验后发出——DSH 只是一张写好台词放进盒子里的嘴。
- **人格单一真源。** 人设只在 MaiBot 的 `bot_config.toml` 里改，DSH 侧永远现读，不做第二份拷贝。
- **记忆只同步事件。** 见上。

## 踩过的坑

这些是实打实踩出来的，写下来省得你重踩：

- **MaiBot 插件必须实现 `on_config_update`**，否则注册直接失败（SDK 基类有默认实现，但 loader 要求子类显式实现）。
- **`config.toml` 里要有 `config_version`**，1.3.x 起不再兼容无版本配置。
- **`--home` 是全局参数，必须写在子命令前**：`maimai.py --home <MaiBot> persona`，写成 `persona --home X` 会报 unrecognized arguments。
- **WebUI 认证只能用 Cookie** `maibot_session=<access_token>`；`Authorization: Bearer` 一律 401。
- **`access_token` 在 `<MaiBot>/data/webui.json`**；如果 `token_source` 是 `configured`，每次启动不会变，否则会变。
- **DSH 插件注册 HTTP 路由要 `export const inject = ['webServer']` + `ctx.effect(() => ctx.webServer.register(...))`**；`ctx.get('webServer')` 在 apply 阶段拿不到，`ctx.inject([...])` 的调用式写法在本加载器里不生效。这类写法最可靠的办法是去抄 `node_modules` 里能正常工作的插件。
- **Windows PowerShell 5.1 按 GBK 解码子进程输出**：计划任务里 Python 输出中文会变「鍐欒繘鍘讳簡」，而且 `| ForEach-Object` 在无控制台环境会把任务挂住。交给 `cmd.exe /c "... >> log 2>&1"` 直写字节最稳。
- **`.ps1` 文件必须带 UTF-8 BOM**，否则 5.1 解析中文注释会报 `The string is missing the terminator`。
- **PowerShell 里不要用 `$home`**，它是只读自动变量。

## License

MIT
