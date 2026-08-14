$ErrorActionPreference="Stop"
$ProjectRoot=Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot
$Python=Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$env:PYTHONPATH="$ProjectRoot;$ProjectRoot\generated"
& $Python -m services.bi.main
