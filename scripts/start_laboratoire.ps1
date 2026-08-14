$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot
$env:PYTHONPATH = "$ProjectRoot;$ProjectRoot\generated"
& "$ProjectRoot\.venv\Scripts\python.exe" -m services.laboratoire.main
