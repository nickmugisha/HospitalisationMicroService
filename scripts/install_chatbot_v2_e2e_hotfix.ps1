$ErrorActionPreference='Stop'
$Root=Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root
$Python=Join-Path $Root '.venv\Scripts\python.exe'
$env:PYTHONPATH="$Root;$Root\generated"

Write-Host '[1/3] Verifying focused Python hotfix files...'
& $Python -m py_compile `
  '.\services\chatbot\assistant_engine.py' `
  '.\services\bi\config.py' `
  '.\services\bi\service.py' `
  '.\scripts\test_chatbot_v2_engine.py' `
  '.\scripts\test_chatbot_v2_full_e2e.py'
if($LASTEXITCODE -ne 0){ exit $LASTEXITCODE }

Write-Host '[2/3] Running deterministic Chatbot v2 regression tests...'
& $Python '.\scripts\test_chatbot_v2_engine.py'
if($LASTEXITCODE -ne 0){ exit $LASTEXITCODE }

Write-Host '[3/3] Hotfix verified.'
Write-Host 'Changes:'
Write-Host '  - French HR attendance how-to routing improved.'
Write-Host '  - French HR live attendance routing improved.'
Write-Host '  - BI service health now includes HR :50062 (12-service topology).'
Write-Host ''
Write-Host 'HOTFIX INSTALLATION CHECK: PASS'
Write-Host 'Restart ProjectX services, then rerun test_chatbot_v2_full_e2e.py.'
