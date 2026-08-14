$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { throw "Virtual environment not found at $Python" }

$env:PYTHONPATH = "$ProjectRoot;$ProjectRoot\generated"
$GrpcInclude = (& $Python -c "import grpc_tools, pathlib; print(pathlib.Path(grpc_tools.__file__).parent / '_proto')").Trim()
if (-not $GrpcInclude) { throw "Could not locate grpc_tools built-in protobuf includes." }

New-Item -ItemType Directory -Force -Path "$ProjectRoot\generated\consultation\v1" | Out-Null

& $Python -m grpc_tools.protoc `
    -I "$ProjectRoot\proto" `
    -I "$GrpcInclude" `
    --python_out "$ProjectRoot\generated" `
    --grpc_python_out "$ProjectRoot\generated" `
    "$ProjectRoot\proto\consultation\v1\consultation.proto"
if ($LASTEXITCODE -ne 0) { throw "Consultation protobuf generation failed." }

New-Item -ItemType File -Force -Path "$ProjectRoot\generated\consultation\__init__.py" | Out-Null
New-Item -ItemType File -Force -Path "$ProjectRoot\generated\consultation\v1\__init__.py" | Out-Null
Write-Host "PROJECTX CONSULTATION PROTO GENERATED OK"
