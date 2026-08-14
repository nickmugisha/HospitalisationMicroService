$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot
Write-Host "PROJECTX LOT G - BILLING INSTALLER"
Write-Host "Project root: $ProjectRoot"

foreach ($Required in @(
    "$ProjectRoot\proto\common\v1\common.proto",
    "$ProjectRoot\services\auth",
    "$ProjectRoot\services\accueil",
    "$ProjectRoot\services\laboratoire",
    "$ProjectRoot\services\pharmacie",
    "$ProjectRoot\services\hospitalisation",
    "$ProjectRoot\services\common\auth_guard.py",
    "$ProjectRoot\scripts\seed_auth.py"
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

Add-EnvLineIfMissing "$ProjectRoot\.env" "MYSQL_BILLING_DATABASE" "MYSQL_BILLING_DATABASE=hospital_billing"
Add-EnvLineIfMissing "$ProjectRoot\.env" "BILLING_GRPC_HOST" "BILLING_GRPC_HOST=0.0.0.0"
Add-EnvLineIfMissing "$ProjectRoot\.env" "BILLING_GRPC_PORT" "BILLING_GRPC_PORT=50054"
Add-EnvLineIfMissing "$ProjectRoot\.env" "BILLING_GRPC_TARGET" "BILLING_GRPC_TARGET=127.0.0.1:50054"
Add-EnvLineIfMissing "$ProjectRoot\.env" "AUTH_GRPC_TARGET" "AUTH_GRPC_TARGET=127.0.0.1:50051"

$Example = "$ProjectRoot\server\.env.example"
if (Test-Path $Example) {
    Add-EnvLineIfMissing $Example "MYSQL_BILLING_DATABASE" "MYSQL_BILLING_DATABASE=hospital_billing"
    Add-EnvLineIfMissing $Example "BILLING_GRPC_HOST" "BILLING_GRPC_HOST=0.0.0.0"
    Add-EnvLineIfMissing $Example "BILLING_GRPC_PORT" "BILLING_GRPC_PORT=50054"
    Add-EnvLineIfMissing $Example "BILLING_GRPC_TARGET" "BILLING_GRPC_TARGET=127.0.0.1:50054"
}

$env:PYTHONPATH = "$ProjectRoot;$ProjectRoot\generated"

Write-Host "[1/6] Generating Billing gRPC stubs..."
& "$ProjectRoot\scripts\generate_billing_proto.ps1"

Write-Host "[2/6] Creating hospital_billing and granting existing ProjectX DB user..."
$MysqlCommand = Get-Command mysql.exe -ErrorAction SilentlyContinue
if (-not $MysqlCommand) {
    $Candidate = Get-ChildItem "C:\wamp64\bin\mysql\mysql*\bin\mysql.exe" -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -First 1
    if ($Candidate) { $MysqlExe = $Candidate.FullName }
} else { $MysqlExe = $MysqlCommand.Source }
if (-not $MysqlExe) { throw "mysql.exe was not found. Run scripts/sql/lot_g_billing_setup.sql as MySQL root, then rerun this installer." }
& $MysqlExe -u root --execute="CREATE DATABASE IF NOT EXISTS hospital_billing CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; GRANT ALL PRIVILEGES ON hospital_billing.* TO 'projectx_auth'@'127.0.0.1'; FLUSH PRIVILEGES;"
if ($LASTEXITCODE -ne 0) { throw "MySQL setup failed." }

Write-Host "[3/6] Applying Billing Alembic migration..."
& $Python -m alembic -c "$ProjectRoot\alembic_billing.ini" upgrade head
if ($LASTEXITCODE -ne 0) { throw "Billing migration failed." }

Write-Host "[4/6] Updating Auth RBAC catalog for interservice billing charges..."
& $Python "$ProjectRoot\scripts\seed_auth.py"
if ($LASTEXITCODE -ne 0) { throw "Auth RBAC reseed failed." }

Write-Host "[5/6] Verifying Billing imports and tables..."
& $Python -c "from billing.v1 import billing_pb2, billing_pb2_grpc; from sqlalchemy import inspect; from database.billing_session import engine; from services.billing.service import BillingService; print('BILLING PROTO IMPORT OK'); print('BILLING TABLES:', sorted(inspect(engine).get_table_names())); print('BILLING SERVICE IMPORT OK')"
if ($LASTEXITCODE -ne 0) { throw "Billing verification failed." }

Write-Host "[6/6] Verifying Lab/Pharmacy/Hospitalisation Billing bridge imports..."
& $Python -c "from services.laboratoire.service import LaboratoireService; from services.pharmacie.service import PharmacieService; from services.hospitalisation.service import HospitalisationService; print('LAB -> BILLING BRIDGE IMPORT OK'); print('PHARMACIE -> BILLING BRIDGE IMPORT OK'); print('HOSPITALISATION -> BILLING BRIDGE IMPORT OK')"
if ($LASTEXITCODE -ne 0) { throw "Billing bridge verification failed." }

Write-Host ""
Write-Host "========================================================"
Write-Host " PROJECTX LOT G BILLING INSTALLATION COMPLETE"
Write-Host "========================================================"
Write-Host "IMPORTANT: start Billing on 50054, then restart Laboratoire, Pharmacie, and Hospitalisation so their Billing bridges are loaded."
