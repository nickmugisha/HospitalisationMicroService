$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot
Write-Host "PROJECTX LOT F - HOSPITALISATION INSTALLER"
Write-Host "Project root: $ProjectRoot"
foreach ($Required in @(
    "$ProjectRoot\proto\common\v1\common.proto",
    "$ProjectRoot\services\auth",
    "$ProjectRoot\services\accueil",
    "$ProjectRoot\services\consultation",
    "$ProjectRoot\services\common\auth_guard.py"
)) { if (-not (Test-Path $Required)) { throw "Required ProjectX component missing: $Required" } }
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { throw "Virtual environment not found at $Python" }
function Add-EnvLineIfMissing([string]$Path, [string]$Key, [string]$Line) {
    if (-not (Test-Path $Path)) { return }
    $match = Select-String -Path $Path -Pattern "^$([regex]::Escape($Key))=" -Quiet
    if (-not $match) { Add-Content -Path $Path -Value $Line }
}
Add-EnvLineIfMissing "$ProjectRoot\.env" "MYSQL_HOSPITALISATION_DATABASE" "MYSQL_HOSPITALISATION_DATABASE=hospital_hospitalisation"
Add-EnvLineIfMissing "$ProjectRoot\.env" "HOSPITALISATION_GRPC_HOST" "HOSPITALISATION_GRPC_HOST=0.0.0.0"
Add-EnvLineIfMissing "$ProjectRoot\.env" "HOSPITALISATION_GRPC_PORT" "HOSPITALISATION_GRPC_PORT=50053"
Add-EnvLineIfMissing "$ProjectRoot\.env" "HOSPITALISATION_GRPC_TARGET" "HOSPITALISATION_GRPC_TARGET=127.0.0.1:50053"
Add-EnvLineIfMissing "$ProjectRoot\.env" "AUTH_GRPC_TARGET" "AUTH_GRPC_TARGET=127.0.0.1:50051"
Add-EnvLineIfMissing "$ProjectRoot\.env" "ACCUEIL_GRPC_TARGET" "ACCUEIL_GRPC_TARGET=127.0.0.1:50052"
Add-EnvLineIfMissing "$ProjectRoot\.env" "BILLING_GRPC_TARGET" "BILLING_GRPC_TARGET=127.0.0.1:50054"
$Example = "$ProjectRoot\server\.env.example"
if (Test-Path $Example) {
    Add-EnvLineIfMissing $Example "MYSQL_HOSPITALISATION_DATABASE" "MYSQL_HOSPITALISATION_DATABASE=hospital_hospitalisation"
    Add-EnvLineIfMissing $Example "HOSPITALISATION_GRPC_HOST" "HOSPITALISATION_GRPC_HOST=0.0.0.0"
    Add-EnvLineIfMissing $Example "HOSPITALISATION_GRPC_PORT" "HOSPITALISATION_GRPC_PORT=50053"
    Add-EnvLineIfMissing $Example "HOSPITALISATION_GRPC_TARGET" "HOSPITALISATION_GRPC_TARGET=127.0.0.1:50053"
    Add-EnvLineIfMissing $Example "AUTH_GRPC_TARGET" "AUTH_GRPC_TARGET=127.0.0.1:50051"
    Add-EnvLineIfMissing $Example "ACCUEIL_GRPC_TARGET" "ACCUEIL_GRPC_TARGET=127.0.0.1:50052"
    Add-EnvLineIfMissing $Example "BILLING_GRPC_TARGET" "BILLING_GRPC_TARGET=127.0.0.1:50054"
}
$env:PYTHONPATH = "$ProjectRoot;$ProjectRoot\generated"
Write-Host "[1/5] Generating Hospitalisation gRPC stubs..."
& "$ProjectRoot\scripts\generate_hospitalisation_proto.ps1"
Write-Host "[2/5] Creating hospital_hospitalisation and granting existing ProjectX DB user..."
$MysqlCommand = Get-Command mysql.exe -ErrorAction SilentlyContinue
if (-not $MysqlCommand) {
    $Candidate = Get-ChildItem "C:\wamp64\bin\mysql\mysql*\bin\mysql.exe" -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -First 1
    if ($Candidate) { $MysqlExe = $Candidate.FullName }
} else { $MysqlExe = $MysqlCommand.Source }
if (-not $MysqlExe) { throw "mysql.exe was not found. Run scripts/sql/lot_f_hospitalisation_setup.sql as MySQL root, then rerun this installer." }
& $MysqlExe -u root --execute="CREATE DATABASE IF NOT EXISTS hospital_hospitalisation CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; GRANT ALL PRIVILEGES ON hospital_hospitalisation.* TO 'projectx_auth'@'127.0.0.1'; FLUSH PRIVILEGES;"
if ($LASTEXITCODE -ne 0) { throw "MySQL setup failed." }
Write-Host "[3/5] Applying Hospitalisation Alembic migration..."
& $Python -m alembic -c "$ProjectRoot\alembic_hospitalisation.ini" upgrade head
if ($LASTEXITCODE -ne 0) { throw "Hospitalisation migration failed." }
Write-Host "[4/5] Seeding wards, rooms, and beds..."
& $Python "$ProjectRoot\scripts\seed_hospitalisation_structure.py"
if ($LASTEXITCODE -ne 0) { throw "Hospital structure seed failed." }
Write-Host "[5/5] Verifying imports, tables, and Consultation bridge..."
& $Python -c "from hospitalisation.v1 import hospitalisation_pb2, hospitalisation_pb2_grpc; from sqlalchemy import inspect; from database.hospitalisation_session import engine; from services.consultation.service import ConsultationService; print('HOSPITALISATION PROTO IMPORT OK'); print('HOSPITALISATION TABLES:', sorted(inspect(engine).get_table_names())); print('CONSULTATION -> HOSPITALISATION BRIDGE IMPORT OK')"
if ($LASTEXITCODE -ne 0) { throw "Hospitalisation verification failed." }
Write-Host ""
Write-Host "========================================================"
Write-Host " PROJECTX LOT F HOSPITALISATION INSTALLATION COMPLETE"
Write-Host "========================================================"
Write-Host "IMPORTANT: restart Consultation on 50055 so its Hospitalisation bridge is loaded."
Write-Host "Then start Hospitalisation with: .\scripts\start_hospitalisation.ps1"
