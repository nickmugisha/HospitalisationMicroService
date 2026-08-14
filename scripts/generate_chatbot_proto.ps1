$ErrorActionPreference='Stop'
$Root=Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Python=Join-Path $Root '.venv\Scripts\python.exe'
$Proto=Join-Path $Root 'proto'
$Generated=Join-Path $Root 'generated'
New-Item -ItemType Directory -Force -Path $Generated | Out-Null
& $Python -m grpc_tools.protoc -I $Proto --python_out=$Generated --grpc_python_out=$Generated "$Proto\chatbot\v1\chatbot.proto"
if ($LASTEXITCODE -ne 0) { throw 'Chatbot proto generation failed.' }
Write-Host 'CHATBOT PROTO GENERATED OK'
