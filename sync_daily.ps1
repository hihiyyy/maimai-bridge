# 把 DSH 这边最近发生的事写进麦麦的长期记忆。
# 由计划任务每天 09:00 / 21:00 调起；手动跑也可以：powershell -File sync_daily.ps1
$ErrorActionPreference = 'Continue'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$py = 'python'
$script = Join-Path $root 'sync_to_maimai.py'
$log = Join-Path $root 'sync.log'

# MaiBot 目录以设置页维护的那份为准（设置页写的是 ~/.dsh/maimai-bridge/settings.json）
$settingsFile = Join-Path $env:USERPROFILE '.dsh\maimai-bridge\settings.json'
$mbHome = ''
if (Test-Path $settingsFile) {
    try {
        $settings = Get-Content $settingsFile -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($settings.maibotHome) { $mbHome = [string]$settings.maibotHome }
        if ($settings.pythonExe -and (Test-Path ([string]$settings.pythonExe))) { $py = [string]$settings.pythonExe }
    } catch {
        # 配置读坏了就退回默认值
    }
}

$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'

# 计划任务里没有控制台，Windows PowerShell 默认按 GBK 解码子进程输出；设成 UTF-8 才不乱码
try { [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false) } catch { }
$OutputEncoding = New-Object System.Text.UTF8Encoding($false)

# 日志超过 1MB 就换一个，别无限长
if ((Test-Path $log) -and ((Get-Item $log).Length -gt 1MB)) {
    Move-Item -Path $log -Destination "$log.old" -Force
}

function Write-Log([string]$text) {
    Add-Content -Path $log -Value $text -Encoding UTF8
}

Write-Log ("[{0}] ---- 开始 ----" -f (Get-Date).ToString('yyyy-MM-dd HH:mm:ss'))

if (-not (Test-Path $script)) {
    Write-Log "找不到 sync_to_maimai.py，跳过"
    return
}

# 回看 12 小时：一天两次，中间不重不漏；state 里还有 id 去重兜底
$extra = @('--since-hours', '12')
if ($mbHome) { $extra += @('--home', $mbHome) }

# 交给 cmd 直接追加到日志：字节原样落盘，不经 PowerShell 的编码转换，
# 在「没有控制台」的计划任务里也不会卡住管道。
$quoted = (@($script) + $extra | ForEach-Object { '"' + $_ + '"' }) -join ' '
cmd.exe /c "`"$py`" $quoted >> `"$log`" 2>&1"
$code = $LASTEXITCODE

Write-Log ("[{0}] ---- 结束 exit={1} ----" -f (Get-Date).ToString('yyyy-MM-dd HH:mm:ss'), $code)
