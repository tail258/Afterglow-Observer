param([ValidateRange(2, 1440)][int]$Minutes = 5)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$env:PYTHONUTF8 = '1'
$taskRepo = $PSScriptRoot
$taskRemote = & git -C $taskRepo remote get-url origin
if ($LASTEXITCODE -ne 0 -or $taskRemote -notmatch '^https://github\.com/tail258/Afterglow-Observer(?:\.git)?$|^git@github\.com:tail258/Afterglow-Observer(?:\.git)?$') {
    throw '此脚本只能在 Afterglow-Observer 源码仓库使用。'
}
$taskPython = (& py -3 -c 'import sys; print(sys.executable)').Trim()
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $taskPython)) { throw '未找到 Python 3。' }
$taskPythonw = Join-Path (Split-Path -Parent $taskPython) 'pythonw.exe'
if (-not (Test-Path -LiteralPath $taskPythonw)) { throw '未找到 pythonw.exe。' }
if (Get-Command gh -ErrorAction SilentlyContinue) {
    $taskLogin = & gh api user --jq .login 2>$null
    $taskId = & gh api user --jq .id 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $taskLogin -or -not $taskId) { throw '请先运行 gh auth login。' }
    & git -C $taskRepo config --replace-all credential.helper ''
    & git -C $taskRepo config --add credential.helper '!gh auth git-credential'
    $taskAuthor = & git -C $taskRepo config user.name
    if (-not $taskAuthor) { & git -C $taskRepo config user.name $taskLogin }
    $taskEmail = & git -C $taskRepo config user.email
    if (-not $taskEmail) { & git -C $taskRepo config user.email ($taskId + '+' + $taskLogin + '@users.noreply.github.com') }
}
& $taskPython -B (Join-Path $taskRepo 'sync.py')
if ($LASTEXITCODE -ne 0) { throw '首次同步未成功，未安装定时任务。请按提示修复后重试。' }
$taskUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$taskName = 'Afterglow-Observer-Source-Sync'
$taskExisting = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($taskExisting -and $taskExisting.Actions.WorkingDirectory -ne $taskRepo) {
    throw '同名同步任务属于另一份检出，请先停用旧任务。'
}
$taskAction = New-ScheduledTaskAction -Execute $taskPythonw -Argument ('-B "' + (Join-Path $taskRepo 'sync.py') + '" --quiet') -WorkingDirectory $taskRepo
$taskRepeat = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes $Minutes)
$taskLogin = New-ScheduledTaskTrigger -AtLogOn -User $taskUser
$taskSettings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 4)
$taskPrincipal = New-ScheduledTaskPrincipal -UserId $taskUser -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $taskName -Action $taskAction -Trigger @($taskRepeat, $taskLogin) -Settings $taskSettings -Principal $taskPrincipal -Description '每隔几分钟同步 Afterglow Observer 公开源码；不访问 Obsidian 笔记。' -Force | Out-Null
Start-ScheduledTask -TaskName $taskName
Write-Output "已启用源码自动同步：登录后每 $Minutes 分钟一次。无需保持 Obsidian 足迹或 Codex 打开。"
