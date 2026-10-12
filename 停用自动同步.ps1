$ErrorActionPreference = 'Stop'
$taskName = 'Afterglow-Observer-Source-Sync'
$taskExisting = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if (-not $taskExisting) { Write-Output '未安装自动同步任务。'; exit 0 }
if ($taskExisting.Actions.WorkingDirectory -ne $PSScriptRoot) { throw '任务不属于当前项目目录，未作修改。' }
Stop-ScheduledTask -TaskName $taskName
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
Write-Output '已停用源码自动同步。'
