$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$taskPython = Get-Command py.exe -ErrorAction SilentlyContinue
if ($taskPython) {
    & $taskPython.Source -3 (Join-Path $PSScriptRoot 'app.py') @args
} else {
    $taskPython = Get-Command python.exe -ErrorAction SilentlyContinue
    if (-not $taskPython) { throw '未找到 Python，请安装带 Tkinter 的 Python 3.11 或更高版本。' }
    & $taskPython.Source (Join-Path $PSScriptRoot 'app.py') @args
}
if ($LASTEXITCODE -ne 0) { throw "启动失败，退出码：$LASTEXITCODE" }
