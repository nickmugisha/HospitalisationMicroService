$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot
Write-Host "PROJECTX LOT D - LABORATOIRE INSTALLER"
Write-Host "Project root: $ProjectRoot"

foreach ($Required in @(
    "$ProjectRoot\proto\common\v1\common.proto",
    "$ProjectRoot\services\auth",
    "$ProjectRoot\services\accueil",
    "$ProjectRoot\services\consultation",
    "$ProjectRoot\services\common\auth_guard.py"
)) {
    if (-not (Test-Path $Required)) { throw "Required ProjectX component missing: $Required" }
}

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { throw "Virtual environment not found at $Python" }

function Add-EnvLineIfMissing([string]$Path, [string]$Key, [string]$Line) {
    if (-not (Test-Path $Path)) { return }
    $match = Select-String -Path $Path -Pattern "^$([regex]::Escape($Key))=" -Quiet
    if (-not $match) { Add-Content -Path $Path -Value $Line }
}

Add-EnvLineIfMissing "$ProjectRoot\.env" "MYSQL_LABORATOIRE_DATABASE" "MYSQL_LABORATOIRE_DATABASE=hospital_laboratoire"
Add-EnvLineIfMissing "$ProjectRoot\.env" "LABORATOIRE_GRPC_HOST" "LABORATOIRE_GRPC_HOST=0.0.0.0"
Add-EnvLineIfMissing "$ProjectRoot\.env" "LABORATOIRE_GRPC_PORT" "LABORATOIRE_GRPC_PORT=50056"
Add-EnvLineIfMissing "$ProjectRoot\.env" "LABORATOIRE_GRPC_TARGET" "LABORATOIRE_GRPC_TARGET=127.0.0.1:50056"
Add-EnvLineIfMissing "$ProjectRoot\.env" "AUTH_GRPC_TARGET" "AUTH_GRPC_TARGET=127.0.0.1:50051"
Add-EnvLineIfMissing "$ProjectRoot\.env" "ACCUEIL_GRPC_TARGET" "ACCUEIL_GRPC_TARGET=127.0.0.1:50052"
Add-EnvLineIfMissing "$ProjectRoot\.env" "BILLING_GRPC_TARGET" "BILLING_GRPC_TARGET=127.0.0.1:50054"

$Example = "$ProjectRoot\server\.env.example"
if (Test-Path $Example) {
    Add-EnvLineIfMissing $Example "MYSQL_LABORATOIRE_DATABASE" "MYSQL_LABORATOIRE_DATABASE=hospital_laboratoire"
    Add-EnvLineIfMissing $Example "LABORATOIRE_GRPC_HOST" "LABORATOIRE_GRPC_HOST=0.0.0.0"
    Add-EnvLineIfMissing $Example "LABORATOIRE_GRPC_PORT" "LABORATOIRE_GRPC_PORT=50056"
    Add-EnvLineIfMissing $Example "LABORATOIRE_GRPC_TARGET" "LABORATOIRE_GRPC_TARGET=127.0.0.1:50056"
    Add-EnvLineIfMissing $Example "AUTH_GRPC_TARGET" "AUTH_GRPC_TARGET=127.0.0.1:50051"
    Add-EnvLineIfMissing $Example "ACCUEIL_GRPC_TARGET" "ACCUEIL_GRPC_TARGET=127.0.0.1:50052"
    Add-EnvLineIfMissing $Example "BILLING_GRPC_TARGET" "BILLING_GRPC_TARGET=127.0.0.1:50054"
}

$env:PYTHONPATH = "$ProjectRoot;$ProjectRoot\generated"

Write-Host "[1/5] Generating Laboratoire gRPC stubs..."
& "$ProjectRoot\scripts\generate_laboratoire_proto.ps1"

Write-Host "[2/5] Creating hospital_laboratoire and granting the existing ProjectX DB user..."
$MysqlCommand = Get-Command mysql.exe -ErrorAction SilentlyContinue
if (-not $MysqlCommand) {
    $Candidate = Get-ChildItem "C:\wamp64\bin\mysql\mysql*\bin\mysql.exe" -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -First 1
    if ($Candidate) { $MysqlExe = $Candidate.FullName }
} else { $MysqlExe = $MysqlCommand.Source }
if (-not $MysqlExe) { throw "mysql.exe was not found. Run scripts/sql/lot_d_laboratoire_setup.sql as MySQL root, then rerun this installer." }

& $MysqlExe -u root --execute="CREATE DATABASE IF NOT EXISTS hospital_laboratoire CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; GRANT ALL PRIVILEGES ON hospital_laboratoire.* TO 'projectx_auth'@'127.0.0.1'; FLUSH PRIVILEGES;"
if ($LASTEXITCODE -ne 0) { throw "MySQL setup failed." }

Write-Host "[3/5] Applying Laboratoire Alembic migration..."
& $Python -m alembic -c "$ProjectRoot\alembic_laboratoire.ini" upgrade head
if ($LASTEXITCODE -ne 0) { throw "Laboratoire migration failed." }

Write-Host "[4/5] Seeding minimal laboratory catalog..."
& $Python "$ProjectRoot\scripts\seed_laboratoire_catalog.py"
if ($LASTEXITCODE -ne 0) { throw "Laboratoire catalog seed failed." }

Write-Host "[5/5] Verifying imports, tables, and Consultation bridge..."
& $Python -c "from laboratoire.v1 import laboratoire_pb2, laboratoire_pb2_grpc; from sqlalchemy import inspect; from database.laboratoire_session import engine; from services.consultation.service import ConsultationService; print('LABORATOIRE PROTO IMPORT OK'); print('LABORATOIRE TABLES:', sorted(inspect(engine).get_table_names())); print('CONSULTATION -> LAB BRIDGE IMPORT OK')"
if ($LASTEXITCODE -ne 0) { throw "Laboratoire verification failed." }

Write-Host ""
Write-Host "================================================"
Write-Host " PROJECTX LOT D LABORATOIRE INSTALLATION COMPLETE"
Write-Host "================================================"
Write-Host "IMPORTANT: restart Consultation on 50055 so its new Lab bridge is loaded."
Write-Host "Then start Laboratoire with: .\scripts\start_laboratoire.ps1"
