# 提示词：给服务器上的 DSH 用（让它给自己和 MaiBot 装插件）

把下面整段贴给**服务器上那台 DSH**（新建一个会话，模式选「标准模式」或「创造模式」都行）。

---

## 提示词正文（从这里开始复制）

```
帮我在这台机器上装一套东西，它叫「麦麦 × DSH」，由三部分组成：

1. DSH 插件 `dsh-settings` —— 在 DSH 设置里多一页「Maibot互联DSH」
2. DSH 预设 `dsh-preset` —— 在模式下拉里多一个「麦麦」，用 MaiBot 的人格说话
3. MaiBot 插件 `maimai_bridge` —— 让麦麦能调 DSH 干活、出去看网页、看 B 站视频

代码在这里（公开仓库，MIT）：
https://github.com/hihiyyy/maimai-bridge

如果 github 拉不动，用镜像前缀：
https://ghproxy.vip/https://github.com/hihiyyy/maimai-bridge

要求：
- 一步一步做，每步做完把结果告诉我
- 出错就停下来，把完整报错贴出来，不要自己猜着跳过
- 不要手改 `.dsh/profiles/desktop/package.json` 或 `cordis.patch.yml`，DSH 插件必须走 `dsh plugin add`
- 装之前先备份 `package.json`

---

## 第 0 步：探清环境（先别动手）

跑这些，把结果发我：

```powershell
# DSH 版本
Get-ChildItem "$env:LOCALAPPDATA\Programs\DeepSeek Harness\resources\runtime\cli\bin\dsh.cmd" -ErrorAction SilentlyContinue | Select-Object FullName

# profile 目录
Get-ChildItem "$env:USERPROFILE\.dsh\profiles" -ErrorAction SilentlyContinue | Select-Object Name

# desktop profile 现有依赖和 bundles
if (Test-Path "$env:USERPROFILE\.dsh\profiles\desktop\package.json") {
  $j = Get-Content "$env:USERPROFILE\.dsh\profiles\desktop\package.json" -Raw | ConvertFrom-Json
  "依赖数: " + ($j.dependencies.PSObject.Properties.Name).Count
  "bundles: " + (($j.dsh.profile.bundles) -join ', ')
}

# 找 MaiBot（要有 bot.py 和 config/bot_config.toml）
Get-ChildItem -Path C:\,D:\ -Filter 'bot_config.toml' -Recurse -Depth 6 -ErrorAction SilentlyContinue |
  Where-Object { $_.FullName -like '*config*' } | Select-Object -First 5 FullName

# 找 MaiBot 用的 python
Get-ChildItem -Path C:\,D:\ -Filter 'python.exe' -Recurse -Depth 6 -ErrorAction SilentlyContinue |
  Where-Object { $_.FullName -like '*python-env*' -or $_.FullName -like '*venv*' } | Select-Object -First 5 FullName
```

---

## 第 1 步：把代码拿下来

```powershell
$dest = "$env:USERPROFILE\maimai-bridge"
if (Test-Path $dest) { Remove-Item $dest -Recurse -Force }
New-Item -ItemType Directory -Path $dest | Out-Null

$url = 'https://github.com/hihiyyy/maimai-bridge/archive/refs/heads/main.zip'
try {
    Invoke-WebRequest -Uri $url -OutFile "$env:TEMP\mb.zip" -TimeoutSec 120
} catch {
    Invoke-WebRequest -Uri "https://ghproxy.vip/$url" -OutFile "$env:TEMP\mb.zip" -TimeoutSec 180
}
Expand-Archive "$env:TEMP\mb.zip" -DestinationPath $dest -Force
# 解压后通常多一层 maimai-bridge-main
$repo = Get-ChildItem $dest -Directory | Select-Object -First 1
if ($repo) { $repo.FullName }
Get-ChildItem $repo.FullName | Select-Object Name
```

应该看到这些东西：`dsh-settings\`、`maibot-plugin\`、`emit_preset.py`、`maimai.py`、`README.md`。

---

## 第 2 步：装 DSH 插件 `dsh-settings`

```powershell
$dsh = "$env:LOCALAPPDATA\Programs\DeepSeek Harness\resources\runtime\cli\bin\dsh.cmd"
$pkgJson = "$env:USERPROFILE\.dsh\profiles\desktop\package.json"
Copy-Item $pkgJson "$pkgJson.bak-$(Get-Date -Format yyyyMMddHHmmss)"      # 先备份

& $dsh --version
& $dsh plugin --profile desktop add "$repo\dsh-settings"
```

装完核对：

```powershell
$j = Get-Content $pkgJson -Raw | ConvertFrom-Json
$j.dependencies.'@local/dsh-maimai-settings'     # 应该有值
$j.dsh.profile.bundles -contains '@local/dsh-maimai-settings'   # 应该是 True
```

**如果 pnpm 顺手删掉了别的依赖**（比如某个插件从 dependencies 里消失），把删掉的列出来，并把它们装回去：
```powershell
& $dsh plugin --profile desktop add <被删的包名>
```

---

## 第 3 步：生成并装 DSH 预设 `dsh-preset`

这一步要用这台机器上**真实存在的 MaiBot 人设**，不能照抄别的机器的文件。

```powershell
# 把 $mbHome 和 $py 换成第 0 步探测到的真实路径
$mbHome = 'C:\....\modules\MaiBot'          # 必须是含 bot.py 和 config\bot_config.toml 的那层
$py     = 'C:\....\python-env\python.exe'   # 跑 MaiBot 用的那个 python

& $py "$repo\emit_preset.py" --home $mbHome --python $py --out "$repo\dsh-preset"
```

**看输出里这一行**：
- `人格：已内联（N 字）` → 成功，用的是 MaiBot 的真实人设
- 如果出现「用了兜底」→ 说明 `--home` 没指对，回去检查路径

然后装：

```powershell
& $dsh plugin --profile desktop add "$repo\dsh-preset"
```

核对：

```powershell
$j = Get-Content $pkgJson -Raw | ConvertFrom-Json
$j.dependencies.'@local/dsh-maimai-preset'
$j.dsh.profile.bundles -contains '@local/dsh-maimai-preset'
```

---

## 第 4 步：装 MaiBot 插件 `maimai_bridge`

```powershell
$src  = "$repo\maibot-plugin"                       # 仓库里那份
$dst  = Join-Path $mbHome 'plugins\maimai_bridge'   # 就是 MaiBot 目录下的 plugins
# 如果 $mbHome 里没有 plugins 目录，说明路径指错了，先确认它下面有没有 plugins\ 和 config\bot_config.toml

if (Test-Path $dst) { Copy-Item $dst "$dst.bak-$(Get-Date -Format yyyyMMddHHmmss)" -Recurse -Force }
New-Item -ItemType Directory -Path $dst -Force | Out-Null
Copy-Item "$src\*" $dst -Recurse -Force
Get-ChildItem $dst | Select-Object Name, Length
```

应该看到：`plugin.py`、`_manifest.json`、`config.toml`、`CHANGELOG.md`、`README.md`、`bili_video\`。

**检查 manifest 没有 BOM**（有 BOM 会导致插件静默不加载）：
```powershell
$b = [System.IO.File]::ReadAllBytes("$dst\_manifest.json")[0..2] -join ','
"前三字节: $b"     # 239,187,191 = 有 BOM，必须去掉
if ($b -eq '239,187,191') {
  $t = [System.IO.File]::ReadAllText("$dst\_manifest.json", [System.Text.Encoding]::UTF8)
  [System.IO.File]::WriteAllText("$dst\_manifest.json", $t, (New-Object System.Text.UTF8Encoding($false)))
  "已去掉 BOM"
}
```

**检查 MaiBot 版本够不够**（插件要求 Host ≥ 1.3.0、SDK ≥ 2.0.0）：
```powershell
& $py -m pip show maibot | Select-String 'Version'
& $py -m pip show maibot-plugin-sdk | Select-String 'Version'
```

---

## 第 5 步：重启与验证

1. **完全退出 DSH 桌面版**（含托盘），重新打开
2. 看两个地方：
   - 左侧设置列表里有没有「**Maibot互联DSH**」
   - 模式下拉里有没有「**麦麦**」
3. **MaiBot**：重开一键包启动器 → 点「启动」→ 看日志里有没有
   `[plugin.lirick.maimai-bridge] [maimai_bridge] 桥插件已加载`

如果「麦麦」没出现在下拉里，那是它加载失败了（DSH 会把 broken 的预设从下拉里藏起来）。去 **设置 → Agent 预设 → 自定义**，把「麦麦」那张卡的红 badge 悬停，把报错全文发我。

---

## 踩过的坑（照着避开，别重复踩）

1. **`$home` 不能当变量名** —— 它是 PowerShell 只读自动变量，赋值会静默失败，`--home` 收到空串，脚本退回兜底人设还打印「已生成」，看起来成功。用 `$mbHome`。
2. **写 `.json` / `.ps1` 一定要 UTF-8 无 BOM** —— `Set-Content -Encoding UTF8` 在 PowerShell 5.1 会加 BOM，插件 manifest 带 BOM 会静默不加载。
3. **DSH 插件必须走 `dsh plugin add`** —— 手改 `package.json` 和 `cordis.patch.yml` 不会生效，因为 profile 的 node_modules 是 pnpm 管的。
4. **`dsh plugin add` 会重新解析整个依赖树** —— 如果 profile 里有「已从 npm 下架」的包，整次安装会失败（`ERR_PNPM_UNPUBLISHED_PKG`）。这时把那个包本地化：复制到 `.vendor/`，`package.json` 里改 `"file:.vendor/xxx"`。
5. **装完 DSH 一定要完全退出再开** —— 只关窗口不算，托盘里也要退。
6. **MaiBot 的插件要在启动器里点「启动」** —— 直接 `python bot.py` 起会抢端口，导致启动器起不来（报「端口 8001/6099 已被占用」）。要手动起就先 `Get-Process python | Stop-Process -Force`。
7. **DSH 预设里 `tool-fs-search` 和 `tool-todo` 有必填 config** —— 空 config 会让整个 preset mount 失败，报 `$.sampleOverCapGlobResults missing required value`。`emit_preset.py` 已经处理好了，别去手改。
8. **改完文件先比时间** —— 如果你改完让用户重启，先确认 `<文件 LastWriteTime>` 晚于 `<进程 StartTime>`，否则加载的还是旧文件（白重启一次）。

---

做完把这几样发我：
- `dsh --version` 的输出
- 两个包在 `dependencies` 和 `bundles` 里的值
- `emit_preset.py` 输出里那行「人格：已内联（N 字）」
- DSH 重启后设置列表和模式下拉的截图
- MaiBot 日志里 `[maimai_bridge] 桥插件已加载` 那行
```

## 提示词结束（到这里复制完）

---

## 说明

- 这段提示词是让**服务器上的 DSH 自己干活**，不需要云控制台、不需要开 5985、不需要我远程连。
- 它需要服务器能访问 github（国内慢的话会自动走 `ghproxy.vip`）。
- 第 3 步是关键：`dsh-preset` 必须用**服务器上 MaiBot 的人设**现场生成，不能拷本机那份（路径和人设都不一样）。
- 如果服务器上还没有 MaiBot，那就先只装 DSH 侧（第 1、2 步），`dsh-preset` 等 MaiBot 就位再生成。
