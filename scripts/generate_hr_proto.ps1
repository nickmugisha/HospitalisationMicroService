$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { throw "Virtual environment not found at $Python" }
New-Item -ItemType Directory -Force -Path "$Root\generated\hr\v1" | Out-Null
$env:PYTHONPATH = "$Root;$Root\generated"
& $Python -m grpc_tools.protoc -I="$Root\proto" --python_out="$Root\generated" --grpc_python_out="$Root\generated" "$Root\proto\hr\v1\hr.proto"
if ($LASTEXITCODE -ne 0) { throw "HR protobuf generation failed." }
foreach ($f in @("$Root\generated\hr\__init__.py", "$Root\generated\hr\v1\__init__.py")) { if (-not (Test-Path $f)) { New-Item -ItemType File -Path $f | Out-Null } }
Write-Host "HR protobuf generation OK"
