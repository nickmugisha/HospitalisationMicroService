$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot
Write-Host "PROJECTX LOT H - RENDEZVOUS INSTALLER"
Write-Host "Project root: $ProjectRoot"
foreach ($Required in @(
    "$ProjectRoot\proto\common\v1\common.proto",
    "$ProjectRoot\proto\accueil\v1\accueil.proto",
    "$ProjectRoot\services\auth",
    "$ProjectRoot\services\accueil",
    "$ProjectRoot\services\common\auth_guard.py"
)) { if (-not (Test-Path $Required)) { throw "Required ProjectX component missing: $Required" } }
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { throw "Virtual environment not found at $Python" }
function Add-EnvLineIfMissing([string]$Path,[string]$Key,[string]$Line) {
    if (-not (Test-Path $Path)) { return }
    $match=Select-String -Path $Path -Pattern "^$([regex]::Escape($Key))=" -Quiet
    if (-not $match) { Add-Content -Path $Path -Value $Line }
}
Add-EnvLineIfMissing "$ProjectRoot\.env" "MYSQL_RENDEZVOUS_DATABASE" "MYSQL_RENDEZVOUS_DATABASE=hospital_rendezvous"
Add-EnvLineIfMissing "$ProjectRoot\.env" "RENDEZVOUS_GRPC_HOST" "RENDEZVOUS_GRPC_HOST=0.0.0.0"
Add-EnvLineIfMissing "$ProjectRoot\.env" "RENDEZVOUS_GRPC_PORT" "RENDEZVOUS_GRPC_PORT=50059"
Add-EnvLineIfMissing "$ProjectRoot\.env" "RENDEZVOUS_GRPC_TARGET" "RENDEZVOUS_GRPC_TARGET=127.0.0.1:50059"
$Example="$ProjectRoot\server\.env.example"
if (Test-Path $Example) {
    Add-EnvLineIfMissing $Example "MYSQL_RENDEZVOUS_DATABASE" "MYSQL_RENDEZVOUS_DATABASE=hospital_rendezvous"
    Add-EnvLineIfMissing $Example "RENDEZVOUS_GRPC_HOST" "RENDEZVOUS_GRPC_HOST=0.0.0.0"
    Add-EnvLineIfMissing $Example "RENDEZVOUS_GRPC_PORT" "RENDEZVOUS_GRPC_PORT=50059"
    Add-EnvLineIfMissing $Example "RENDEZVOUS_GRPC_TARGET" "RENDEZVOUS_GRPC_TARGET=127.0.0.1:50059"
}
$env:PYTHONPATH="$ProjectRoot;$ProjectRoot\generated"
Write-Host "[1/4] Generating Rendezvous gRPC stubs..."
& "$ProjectRoot\scripts\generate_rendezvous_proto.ps1"
Write-Host "[2/4] Creating hospital_rendezvous and granting existing ProjectX DB user..."
$MysqlCommand=Get-Command mysql.exe -ErrorAction SilentlyContinue
if (-not $MysqlCommand) {
    $Candidate=Get-ChildItem "C:\wamp64\bin\mysql\mysql*\bin\mysql.exe" -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -First 1
    if ($Candidate) { $MysqlExe=$Candidate.FullName }
} else { $MysqlExe=$MysqlCommand.Source }
if (-not $MysqlExe) { throw "mysql.exe was not found. Run scripts/sql/lot_h_rendezvous_setup.sql as MySQL root, then rerun this installer." }
& $MysqlExe -u root --execute="CREATE DATABASE IF NOT EXISTS hospital_rendezvous CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; GRANT ALL PRIVILEGES ON hospital_rendezvous.* TO 'projectx_auth'@'127.0.0.1'; FLUSH PRIVILEGES;"
if ($LASTEXITCODE -ne 0) { throw "MySQL setup failed." }
Write-Host "[3/4] Applying Rendezvous Alembic migration..."
& $Python -m alembic -c "$ProjectRoot\alembic_rendezvous.ini" upgrade head
if ($LASTEXITCODE -ne 0) { throw "Rendezvous migration failed." }
Write-Host "[4/4] Verifying imports and tables..."
& $Python -c "from rendezvous.v1 import rendezvous_pb2,rendezvous_pb2_grpc; from sqlalchemy import inspect; from database.rendezvous_session import engine; from services.rendezvous.service import RendezvousService; print('RENDEZVOUS PROTO IMPORT OK'); print('RENDEZVOUS TABLES:',sorted(inspect(engine).get_table_names())); print('RENDEZVOUS SERVICE IMPORT OK')"
if ($LASTEXITCODE -ne 0) { throw "Rendezvous verification failed." }
Write-Host ""
Write-Host "========================================================"
Write-Host " PROJECTX LOT H RENDEZVOUS INSTALLATION COMPLETE"
Write-Host "========================================================"
Write-Host "Start Auth (50051), Accueil (50052), then Rendezvous (50059)."
