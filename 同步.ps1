$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$env:PYTHONUTF8 = '1'
& py -3 -B (Join-Path $PSScriptRoot 'sync.py') @args
exit $LASTEXITCODE
