# 麦麦 × DSH 插件：在服务器上安装 dsh-settings / dsh-preset
# 用法（服务器上，管理员 PowerShell）：
#   powershell -ExecutionPolicy Bypass -File .\install-on-server.ps1
# 脚本会自动找同目录下的 dsh-settings / dsh-preset 两个文件夹。

$ErrorActionPreference = 'Stop'

$here       = Split-Path -Parent $MyInvocation.MyCommand.Path
$profileDir = Join-Path $env:USERPROFILE '.dsh\profiles\desktop'
$stamp      = Get-Date -Format 'yyyyMMdd-HHmmss'

function Step($m) { Write-Host "`n=== $m ===" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "  [OK] $m" -ForegroundColor Green }
function Bad($m)  { Write-Host "  [!!] $m" -ForegroundColor Red }
function Info($m) { Write-Host "  $m" -ForegroundColor Gray }

Step '0 环境'
Info "脚本目录: $here"
Info "用户: $env:USERNAME"
Info "profile: $profileDir"

if (-not (Test-Path $profileDir)) {
    Bad "找不到 DSH desktop profile：$profileDir"
    Bad "请先启动一次 DSH 桌面版，让它生成 profile 后再跑这个脚本。"
    exit 1
}

foreach ($pkg in @('dsh-settings', 'dsh-preset')) {
    $src = Join-Path $here $pkg
    if (-not (Test-Path (Join-Path $src 'package.json'))) {
        Bad "缺少 $pkg\package.json（脚本要和这两个文件夹放在一起）"
        exit 1
    }
    Info "$pkg -> $(Get-Item $src).FullName"
}

Step '1 找 dsh CLI'
$cands = @(
    (Join-Path $env:LOCALAPPDATA 'Programs\DeepSeek Harness\resources\runtime\cli\bin\dsh.cmd'),
    (Join-Path $env:ProgramFiles 'DeepSeek Harness\resources\runtime\cli\bin\dsh.cmd'),
    "${env:ProgramFiles(x86)}\DeepSeek Harness\resources\runtime\cli\bin\dsh.cmd"
)
$dsh = $null
foreach ($c in $cands) { if (Test-Path $c) { $dsh = $c; break } }
if (-not $dsh) {
    $found = Get-ChildItem -Path $env:LOCALAPPDATA, $env:ProgramFiles -Filter 'dsh.cmd' -Recurse -ErrorAction SilentlyContinue |
             Select-Object -First 1
    if ($found) { $dsh = $found.FullName }
}
if (-not $dsh) { Bad '没找到 dsh.cmd，请手动改脚本里的路径'; exit 1 }
Ok "dsh: $dsh"

Step '2 版本'
& $dsh --version

Step '3 现有 profile 依赖（安装前快照）'
$pkgJson = Join-Path $profileDir 'package.json'
$backup  = "$pkgJson.bak-$stamp"
Copy-Item $pkgJson $backup -Force
Ok "已备份: $backup"
$before = Get-Content $pkgJson -Raw | ConvertFrom-Json
Info ('当前依赖数: ' + ($before.dependencies.PSObject.Properties.Name | Measure-Object).Count)
Info ('当前 bundles: ' + (($before.dsh.profile.bundles) -join ', '))

Step '4 安装 dsh-settings'
& $dsh plugin --profile desktop add (Join-Path $here 'dsh-settings')
Ok 'dsh-settings 安装命令已执行'

Step '5 安装 dsh-preset'
& $dsh plugin --profile desktop add (Join-Path $here 'dsh-preset')
Ok 'dsh-preset 安装命令已执行'

Step '6 安装后核对'
$after = Get-Content $pkgJson -Raw | ConvertFrom-Json
$depsAfter = $after.dependencies.PSObject.Properties.Name
Info ('依赖数: ' + $depsAfter.Count)
foreach ($n in @('@local/dsh-maimai-settings', '@local/dsh-maimai-preset')) {
    if ($depsAfter -contains $n) {
        Ok "$n -> $($after.dependencies.$n)"
    } else {
        Bad "$n 没进 dependencies"
    }
}
$bundles = @($after.dsh.profile.bundles)
foreach ($n in @('@local/dsh-maimai-settings', '@local/dsh-maimai-preset')) {
    if ($bundles -contains $n) { Ok "$n 在 bundles 里" } else { Bad "$n 不在 bundles 里" }
}

Step '7 丢了哪些依赖（安装前有、安装后没有的）'
$lost = @($before.dependencies.PSObject.Properties.Name) | Where-Object { $depsAfter -notcontains $_ }
if ($lost.Count -eq 0) {
    Ok '没有丢包'
} else {
    Bad ('丢了 ' + $lost.Count + ' 个: ' + ($lost -join ', '))
    Info '回滚命令: Copy-Item "' + $backup + '" "' + $pkgJson + '" -Force'
}

Step '完成'
Write-Host ''
Write-Host '接下来：' -ForegroundColor Yellow
Write-Host '  1. 完全退出 DSH 桌面版（托盘也要退）' -ForegroundColor Yellow
Write-Host '  2. 重新打开' -ForegroundColor Yellow
Write-Host '  3. 看「设置 → Agent 预设」里有没有「麦麦」' -ForegroundColor Yellow
Write-Host '  4. 看左侧设置列表里有没有「Maibot互联DSH」' -ForegroundColor Yellow
Write-Host ''
