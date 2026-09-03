$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root
$env:PYTHONPATH = "$Root;$Root\generated"
& "$Root\.venv\Scripts\python.exe" -m services.hr.main
