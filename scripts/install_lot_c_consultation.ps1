$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot
Write-Host "PROJECTX LOT C - CONSULTATION INSTALLER"
Write-Host "Project root: $ProjectRoot"

if (-not (Test-Path "$ProjectRoot\proto\common\v1\common.proto")) {
    throw "This does not look like the ProjectX server root: proto/common/v1/common.proto is missing."
}
if (-not (Test-Path "$ProjectRoot\services\auth")) {
    throw "Auth service is missing. LOT C requires the existing ProjectX Auth service."
}
if (-not (Test-Path "$ProjectRoot\services\accueil")) {
    throw "Accueil service is missing. Install and validate LOT B before LOT C."
}
if (-not (Test-Path "$ProjectRoot\services\common\auth_guard.py")) {
    throw "services/common/auth_guard.py is missing. Reinstall LOT B first."
}

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { throw "Virtual environment not found at $Python" }

function Add-EnvLineIfMissing([string]$Path, [string]$Key, [string]$Line) {
    if (-not (Test-Path $Path)) { return }
    $match = Select-String -Path $Path -Pattern "^$([regex]::Escape($Key))=" -Quiet
    if (-not $match) { Add-Content -Path $Path -Value $Line }
}

Add-EnvLineIfMissing "$ProjectRoot\.env" "MYSQL_CONSULTATION_DATABASE" "MYSQL_CONSULTATION_DATABASE=hospital_consultation"
Add-EnvLineIfMissing "$ProjectRoot\.env" "CONSULTATION_GRPC_HOST" "CONSULTATION_GRPC_HOST=0.0.0.0"
Add-EnvLineIfMissing "$ProjectRoot\.env" "CONSULTATION_GRPC_PORT" "CONSULTATION_GRPC_PORT=50055"
Add-EnvLineIfMissing "$ProjectRoot\.env" "ACCUEIL_GRPC_TARGET" "ACCUEIL_GRPC_TARGET=127.0.0.1:50052"
Add-EnvLineIfMissing "$ProjectRoot\.env" "AUTH_GRPC_TARGET" "AUTH_GRPC_TARGET=127.0.0.1:50051"

$Example = "$ProjectRoot\server\.env.example"
if (Test-Path $Example) {
    Add-EnvLineIfMissing $Example "MYSQL_CONSULTATION_DATABASE" "MYSQL_CONSULTATION_DATABASE=hospital_consultation"
    Add-EnvLineIfMissing $Example "CONSULTATION_GRPC_HOST" "CONSULTATION_GRPC_HOST=0.0.0.0"
    Add-EnvLineIfMissing $Example "CONSULTATION_GRPC_PORT" "CONSULTATION_GRPC_PORT=50055"
    Add-EnvLineIfMissing $Example "ACCUEIL_GRPC_TARGET" "ACCUEIL_GRPC_TARGET=127.0.0.1:50052"
    Add-EnvLineIfMissing $Example "AUTH_GRPC_TARGET" "AUTH_GRPC_TARGET=127.0.0.1:50051"
}

$env:PYTHONPATH = "$ProjectRoot;$ProjectRoot\generated"

Write-Host "[1/4] Generating Consultation gRPC stubs..."
& "$ProjectRoot\scripts\generate_consultation_proto.ps1"

Write-Host "[2/4] Creating hospital_consultation and granting the existing ProjectX DB user..."
$MysqlCommand = Get-Command mysql.exe -ErrorAction SilentlyContinue
if (-not $MysqlCommand) {
    $Candidate = Get-ChildItem "C:\wamp64\bin\mysql\mysql*\bin\mysql.exe" -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -First 1
    if ($Candidate) { $MysqlExe = $Candidate.FullName }
} else {
    $MysqlExe = $MysqlCommand.Source
}
if (-not $MysqlExe) {
    throw "mysql.exe was not found. Run scripts/sql/lot_c_consultation_setup.sql as MySQL root, then rerun this installer."
}

& $MysqlExe -u root --execute="CREATE DATABASE IF NOT EXISTS hospital_consultation CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; GRANT ALL PRIVILEGES ON hospital_consultation.* TO 'projectx_auth'@'127.0.0.1'; FLUSH PRIVILEGES;"
if ($LASTEXITCODE -ne 0) { throw "MySQL setup failed." }

Write-Host "[3/4] Applying Consultation Alembic migration..."
& $Python -m alembic -c "$ProjectRoot\alembic_consultation.ini" upgrade head
if ($LASTEXITCODE -ne 0) { throw "Consultation migration failed." }

Write-Host "[4/4] Verifying imports and tables..."
& $Python -c "from consultation.v1 import consultation_pb2, consultation_pb2_grpc; from sqlalchemy import inspect; from database.consultation_session import engine; print('CONSULTATION PROTO IMPORT OK'); print('CONSULTATION TABLES:', sorted(inspect(engine).get_table_names()))"
if ($LASTEXITCODE -ne 0) { throw "Consultation verification failed." }

Write-Host ""
Write-Host "=================================================="
Write-Host " PROJECTX LOT C CONSULTATION INSTALLATION COMPLETE"
Write-Host "=================================================="
Write-Host "Keep Auth on 50051 and Accueil on 50052, then run:"
Write-Host "  .\scripts\start_consultation.ps1"
