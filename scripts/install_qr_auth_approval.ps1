$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root

Write-Host "==============================================" -ForegroundColor Cyan
Write-Host " PROJECTX - QR AUTH + ADMIN APPROVAL INSTALL " -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    throw "Project virtual environment not found at .venv\Scripts\python.exe"
}

$Python = Join-Path $Root ".venv\Scripts\python.exe"
$env:PYTHONPATH = "$Root;$Root\generated"

Write-Host "[1/5] Checking grpc_tools..." -ForegroundColor Yellow
& $Python -c "import grpc_tools.protoc" | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "grpcio-tools is missing. Install it in the existing ProjectX .venv before continuing."
}

Write-Host "[2/5] Regenerating Auth gRPC Python code..." -ForegroundColor Yellow
& $Python -m grpc_tools.protoc `
    -I="$Root\proto" `
    --python_out="$Root\generated" `
    --grpc_python_out="$Root\generated" `
    "$Root\proto\auth\v1\auth.proto"
if ($LASTEXITCODE -ne 0) { throw "Auth protobuf generation failed." }

Write-Host "[3/5] Applying Auth database migration..." -ForegroundColor Yellow
& $Python -m alembic -c "$Root\alembic.ini" upgrade head
if ($LASTEXITCODE -ne 0) { throw "Alembic migration failed." }

Write-Host "[4/5] Refreshing roles and permissions..." -ForegroundColor Yellow
& $Python "$Root\scripts\seed_auth.py"
if ($LASTEXITCODE -ne 0) { throw "Auth seed failed." }

Write-Host "[5/5] Verifying Python syntax and generated contract..." -ForegroundColor Yellow
& $Python -m py_compile `
    "$Root\services\auth\models.py" `
    "$Root\services\auth\repository.py" `
    "$Root\services\auth\security.py" `
    "$Root\services\auth\service.py" `
    "$Root\services\auth\rbac.py" `
    "$Root\scripts\test_auth_qr_approval_smoke.py"
if ($LASTEXITCODE -ne 0) { throw "Python syntax verification failed." }

& $Python -c "from auth.v1 import auth_pb2; assert hasattr(auth_pb2, 'QrLoginRequest'); assert hasattr(auth_pb2, 'ApproveUserRequest'); print('Auth QR contract: OK')"
if ($LASTEXITCODE -ne 0) { throw "Generated Auth contract verification failed." }

Write-Host ""
Write-Host "INSTALLATION COMPLETE" -ForegroundColor Green
Write-Host "Next:" -ForegroundColor Green
Write-Host "  1. Start Auth or all ProjectX services"
Write-Host "  2. Run: .venv\Scripts\python.exe scripts\test_auth_qr_approval_smoke.py"
Write-Host ""
Write-Host "IMPORTANT: the raw QR payload is a login credential. Do not log it or commit it." -ForegroundColor Yellow
