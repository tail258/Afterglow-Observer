$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$taskLauncher = Get-Command py.exe -ErrorAction SilentlyContinue
if ($taskLauncher) {
    $taskPython = (& $taskLauncher.Source -3 -c 'import sys; print(sys.executable)').Trim()
} else {
    $taskPython = (Get-Command python.exe -ErrorAction Stop).Source
}
if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) { throw '未找到 Python 3。' }
$taskPythonw = Join-Path (Split-Path -Parent $taskPython) 'pythonw.exe'
if (-not (Test-Path -LiteralPath $taskPythonw)) { throw '未找到 pythonw.exe。' }
& $taskPython -B (Join-Path $PSScriptRoot 'app_icon.py')
if ($LASTEXITCODE -ne 0) { throw '生成图标失败。' }
$taskShell = New-Object -ComObject WScript.Shell
$taskDesktop = [Environment]::GetFolderPath('Desktop')
$taskLink = Join-Path $taskDesktop 'Afterglow Observer.lnk'
$taskShortcut = $taskShell.CreateShortcut($taskLink)
$taskShortcut.TargetPath = $taskPythonw
$taskShortcut.Arguments = '-B "' + (Join-Path $PSScriptRoot 'app.py') + '"'
$taskShortcut.WorkingDirectory = $PSScriptRoot
$taskShortcut.IconLocation = (Join-Path $PSScriptRoot 'afterglow.local.ico') + ',0'
$taskShortcut.Description = 'Obsidian 笔记足迹 · 本地只读'
$taskShortcut.Save()
Write-Output '已创建桌面快捷方式：Afterglow Observer'
