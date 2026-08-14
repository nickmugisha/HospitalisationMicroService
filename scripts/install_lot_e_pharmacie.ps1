$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot
Write-Host "PROJECTX LOT E - PHARMACIE / STOCK / LOGISTIQUE INSTALLER"
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

Add-EnvLineIfMissing "$ProjectRoot\.env" "MYSQL_PHARMACIE_DATABASE" "MYSQL_PHARMACIE_DATABASE=hospital_pharmacie"
Add-EnvLineIfMissing "$ProjectRoot\.env" "PHARMACIE_GRPC_HOST" "PHARMACIE_GRPC_HOST=0.0.0.0"
Add-EnvLineIfMissing "$ProjectRoot\.env" "PHARMACIE_GRPC_PORT" "PHARMACIE_GRPC_PORT=50057"
Add-EnvLineIfMissing "$ProjectRoot\.env" "PHARMACIE_GRPC_TARGET" "PHARMACIE_GRPC_TARGET=127.0.0.1:50057"
Add-EnvLineIfMissing "$ProjectRoot\.env" "AUTH_GRPC_TARGET" "AUTH_GRPC_TARGET=127.0.0.1:50051"
Add-EnvLineIfMissing "$ProjectRoot\.env" "BILLING_GRPC_TARGET" "BILLING_GRPC_TARGET=127.0.0.1:50054"

$Example = "$ProjectRoot\server\.env.example"
if (Test-Path $Example) {
    Add-EnvLineIfMissing $Example "MYSQL_PHARMACIE_DATABASE" "MYSQL_PHARMACIE_DATABASE=hospital_pharmacie"
    Add-EnvLineIfMissing $Example "PHARMACIE_GRPC_HOST" "PHARMACIE_GRPC_HOST=0.0.0.0"
    Add-EnvLineIfMissing $Example "PHARMACIE_GRPC_PORT" "PHARMACIE_GRPC_PORT=50057"
    Add-EnvLineIfMissing $Example "PHARMACIE_GRPC_TARGET" "PHARMACIE_GRPC_TARGET=127.0.0.1:50057"
    Add-EnvLineIfMissing $Example "AUTH_GRPC_TARGET" "AUTH_GRPC_TARGET=127.0.0.1:50051"
    Add-EnvLineIfMissing $Example "BILLING_GRPC_TARGET" "BILLING_GRPC_TARGET=127.0.0.1:50054"
}

$env:PYTHONPATH = "$ProjectRoot;$ProjectRoot\generated"

Write-Host "[1/5] Generating Pharmacie gRPC stubs..."
& "$ProjectRoot\scripts\generate_pharmacie_proto.ps1"

Write-Host "[2/5] Creating hospital_pharmacie and granting existing ProjectX DB user..."
$MysqlCommand = Get-Command mysql.exe -ErrorAction SilentlyContinue
if (-not $MysqlCommand) {
    $Candidate = Get-ChildItem "C:\wamp64\bin\mysql\mysql*\bin\mysql.exe" -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -First 1
    if ($Candidate) { $MysqlExe = $Candidate.FullName }
} else { $MysqlExe = $MysqlCommand.Source }
if (-not $MysqlExe) { throw "mysql.exe was not found. Run scripts/sql/lot_e_pharmacie_setup.sql as MySQL root, then rerun this installer." }

& $MysqlExe -u root --execute="CREATE DATABASE IF NOT EXISTS hospital_pharmacie CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; GRANT ALL PRIVILEGES ON hospital_pharmacie.* TO 'projectx_auth'@'127.0.0.1'; FLUSH PRIVILEGES;"
if ($LASTEXITCODE -ne 0) { throw "MySQL setup failed." }

Write-Host "[3/5] Applying Pharmacie Alembic migration..."
& $Python -m alembic -c "$ProjectRoot\alembic_pharmacie.ini" upgrade head
if ($LASTEXITCODE -ne 0) { throw "Pharmacie migration failed." }

Write-Host "[4/5] Seeding medicines and suppliers..."
& $Python "$ProjectRoot\scripts\seed_pharmacie_catalog.py"
if ($LASTEXITCODE -ne 0) { throw "Pharmacie catalog seed failed." }

Write-Host "[5/5] Verifying imports, tables, and Consultation bridge..."
& $Python -c "from pharmacie.v1 import pharmacie_pb2, pharmacie_pb2_grpc; from sqlalchemy import inspect; from database.pharmacie_session import engine; from services.consultation.service import ConsultationService; print('PHARMACIE PROTO IMPORT OK'); print('PHARMACIE TABLES:', sorted(inspect(engine).get_table_names())); print('CONSULTATION -> PHARMACIE BRIDGE IMPORT OK')"
if ($LASTEXITCODE -ne 0) { throw "Pharmacie verification failed." }

Write-Host ""
Write-Host "========================================================"
Write-Host " PROJECTX LOT E PHARMACIE INSTALLATION COMPLETE"
Write-Host "========================================================"
Write-Host "IMPORTANT: restart Consultation on 50055 so its Pharmacy bridge is loaded."
Write-Host "Then start Pharmacie with: .\scripts\start_pharmacie.ps1"
