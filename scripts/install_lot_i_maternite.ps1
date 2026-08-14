$ErrorActionPreference="Stop"
$ProjectRoot=Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot
Write-Host "PROJECTX LOT I - MATERNITE INSTALLER"
Write-Host "Project root: $ProjectRoot"
foreach ($Required in @(
    "$ProjectRoot\proto\common\v1\common.proto",
    "$ProjectRoot\proto\accueil\v1\accueil.proto",
    "$ProjectRoot\proto\billing\v1\billing.proto",
    "$ProjectRoot\proto\consultation\v1\consultation.proto",
    "$ProjectRoot\services\auth",
    "$ProjectRoot\services\accueil",
    "$ProjectRoot\services\billing",
    "$ProjectRoot\services\consultation",
    "$ProjectRoot\services\common\auth_guard.py",
    "$ProjectRoot\scripts\seed_auth.py"
)) { if (-not (Test-Path $Required)) { throw "Required ProjectX component missing: $Required" } }
$Python=Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { throw "Virtual environment not found at $Python" }
function Add-EnvLineIfMissing([string]$Path,[string]$Key,[string]$Line) { if (-not (Test-Path $Path)) { return }; if (-not (Select-String -Path $Path -Pattern "^$([regex]::Escape($Key))=" -Quiet)) { Add-Content -Path $Path -Value $Line } }
Add-EnvLineIfMissing "$ProjectRoot\.env" "MYSQL_MATERNITE_DATABASE" "MYSQL_MATERNITE_DATABASE=hospital_maternite"
Add-EnvLineIfMissing "$ProjectRoot\.env" "MATERNITE_GRPC_HOST" "MATERNITE_GRPC_HOST=0.0.0.0"
Add-EnvLineIfMissing "$ProjectRoot\.env" "MATERNITE_GRPC_PORT" "MATERNITE_GRPC_PORT=50058"
Add-EnvLineIfMissing "$ProjectRoot\.env" "MATERNITE_GRPC_TARGET" "MATERNITE_GRPC_TARGET=127.0.0.1:50058"
Add-EnvLineIfMissing "$ProjectRoot\.env" "MATERNITE_DELIVERY_CHARGE_MINOR" "MATERNITE_DELIVERY_CHARGE_MINOR=100000"
Add-EnvLineIfMissing "$ProjectRoot\.env" "MATERNITE_CURRENCY_CODE" "MATERNITE_CURRENCY_CODE=BIF"
$Example="$ProjectRoot\server\.env.example"
if (Test-Path $Example) {
    Add-EnvLineIfMissing $Example "MYSQL_MATERNITE_DATABASE" "MYSQL_MATERNITE_DATABASE=hospital_maternite"
    Add-EnvLineIfMissing $Example "MATERNITE_GRPC_HOST" "MATERNITE_GRPC_HOST=0.0.0.0"
    Add-EnvLineIfMissing $Example "MATERNITE_GRPC_PORT" "MATERNITE_GRPC_PORT=50058"
    Add-EnvLineIfMissing $Example "MATERNITE_GRPC_TARGET" "MATERNITE_GRPC_TARGET=127.0.0.1:50058"
    Add-EnvLineIfMissing $Example "MATERNITE_DELIVERY_CHARGE_MINOR" "MATERNITE_DELIVERY_CHARGE_MINOR=100000"
    Add-EnvLineIfMissing $Example "MATERNITE_CURRENCY_CODE" "MATERNITE_CURRENCY_CODE=BIF"
}
$env:PYTHONPATH="$ProjectRoot;$ProjectRoot\generated"
Write-Host "[1/5] Generating Maternite gRPC stubs..."; & "$ProjectRoot\scripts\generate_maternite_proto.ps1"
Write-Host "[2/5] Creating hospital_maternite and granting existing ProjectX DB user..."
$MysqlCommand=Get-Command mysql.exe -ErrorAction SilentlyContinue
if (-not $MysqlCommand) { $Candidate=Get-ChildItem "C:\wamp64\bin\mysql\mysql*\bin\mysql.exe" -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -First 1; if ($Candidate) { $MysqlExe=$Candidate.FullName } } else { $MysqlExe=$MysqlCommand.Source }
if (-not $MysqlExe) { throw "mysql.exe was not found. Run scripts/sql/lot_i_maternite_setup.sql as MySQL root, then rerun this installer." }
& $MysqlExe -u root --execute="CREATE DATABASE IF NOT EXISTS hospital_maternite CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; GRANT ALL PRIVILEGES ON hospital_maternite.* TO 'projectx_auth'@'127.0.0.1'; FLUSH PRIVILEGES;"
if ($LASTEXITCODE -ne 0) { throw "MySQL setup failed." }
Write-Host "[3/5] Applying Maternite Alembic migration..."; & $Python -m alembic -c "$ProjectRoot\alembic_maternite.ini" upgrade head
if ($LASTEXITCODE -ne 0) { throw "Maternite migration failed." }
Write-Host "[4/5] Updating Auth RBAC for maternity referral..."; & $Python "$ProjectRoot\scripts\seed_auth.py"
if ($LASTEXITCODE -ne 0) { throw "Auth RBAC reseed failed." }
Write-Host "[5/5] Verifying Maternite and Consultation bridge imports..."
& $Python -c "from maternite.v1 import maternite_pb2,maternite_pb2_grpc; from sqlalchemy import inspect; from database.maternite_session import engine; from services.maternite.service import MaterniteService; from services.consultation.service import ConsultationService; print('MATERNITE PROTO IMPORT OK'); print('MATERNITE TABLES:',sorted(inspect(engine).get_table_names())); print('MATERNITE SERVICE IMPORT OK'); print('CONSULTATION -> MATERNITE BRIDGE IMPORT OK')"
if ($LASTEXITCODE -ne 0) { throw "Maternite verification failed." }
Write-Host ""; Write-Host "========================================================"; Write-Host " PROJECTX LOT I MATERNITE INSTALLATION COMPLETE"; Write-Host "========================================================"; Write-Host "Start Maternite on 50058, then restart Consultation on 50055."
