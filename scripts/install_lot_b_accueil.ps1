$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot
Write-Host "PROJECTX LOT B - ACCUEIL INSTALLER"
Write-Host "Project root: $ProjectRoot"

if (-not (Test-Path "$ProjectRoot\proto\common\v1\common.proto")) {
    throw "This does not look like the ProjectX server root: proto/common/v1/common.proto is missing."
}
if (-not (Test-Path "$ProjectRoot\services\auth")) {
    throw "Auth service is missing. Install LOT B only on the existing ProjectX server tree."
}

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { throw "Virtual environment not found at $Python" }

function Add-EnvLineIfMissing([string]$Path, [string]$Key, [string]$Line) {
    if (-not (Test-Path $Path)) { return }
    $match = Select-String -Path $Path -Pattern "^$([regex]::Escape($Key))=" -Quiet
    if (-not $match) { Add-Content -Path $Path -Value $Line }
}

Add-EnvLineIfMissing "$ProjectRoot\.env" "MYSQL_ACCUEIL_DATABASE" "MYSQL_ACCUEIL_DATABASE=hospital_accueil"
Add-EnvLineIfMissing "$ProjectRoot\.env" "ACCUEIL_GRPC_HOST" "ACCUEIL_GRPC_HOST=0.0.0.0"
Add-EnvLineIfMissing "$ProjectRoot\.env" "ACCUEIL_GRPC_PORT" "ACCUEIL_GRPC_PORT=50052"
Add-EnvLineIfMissing "$ProjectRoot\.env" "AUTH_GRPC_TARGET" "AUTH_GRPC_TARGET=127.0.0.1:50051"
Add-EnvLineIfMissing "$ProjectRoot\.env" "PROJECTX_SERVICE_VERSION" "PROJECTX_SERVICE_VERSION=1.0.0"

$Example = "$ProjectRoot\server\.env.example"
if (Test-Path $Example) {
    Add-EnvLineIfMissing $Example "MYSQL_ACCUEIL_DATABASE" "MYSQL_ACCUEIL_DATABASE=hospital_accueil"
    Add-EnvLineIfMissing $Example "ACCUEIL_GRPC_HOST" "ACCUEIL_GRPC_HOST=0.0.0.0"
    Add-EnvLineIfMissing $Example "ACCUEIL_GRPC_PORT" "ACCUEIL_GRPC_PORT=50052"
    Add-EnvLineIfMissing $Example "AUTH_GRPC_TARGET" "AUTH_GRPC_TARGET=127.0.0.1:50051"
    Add-EnvLineIfMissing $Example "PROJECTX_SERVICE_VERSION" "PROJECTX_SERVICE_VERSION=1.0.0"
}

$env:PYTHONPATH = "$ProjectRoot;$ProjectRoot\generated"

Write-Host "[1/4] Generating Accueil gRPC stubs..."
& "$ProjectRoot\scripts\generate_accueil_proto.ps1"

Write-Host "[2/4] Creating hospital_accueil and granting the existing ProjectX DB user..."
$MysqlCommand = Get-Command mysql.exe -ErrorAction SilentlyContinue
if (-not $MysqlCommand) {
    $Candidate = Get-ChildItem "C:\wamp64\bin\mysql\mysql*\bin\mysql.exe" -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -First 1
    if ($Candidate) { $MysqlExe = $Candidate.FullName }
} else {
    $MysqlExe = $MysqlCommand.Source
}
if (-not $MysqlExe) {
    throw "mysql.exe was not found. Run scripts/sql/lot_b_accueil_setup.sql as MySQL root, then rerun this installer."
}

& $MysqlExe -u root --execute="CREATE DATABASE IF NOT EXISTS hospital_accueil CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; GRANT ALL PRIVILEGES ON hospital_accueil.* TO 'projectx_auth'@'127.0.0.1'; FLUSH PRIVILEGES;"
if ($LASTEXITCODE -ne 0) { throw "MySQL setup failed." }

Write-Host "[3/4] Applying Accueil Alembic migration..."
& $Python -m alembic -c "$ProjectRoot\alembic_accueil.ini" upgrade head
if ($LASTEXITCODE -ne 0) { throw "Accueil migration failed." }

Write-Host "[4/4] Verifying imports and tables..."
& $Python -c "from accueil.v1 import accueil_pb2, accueil_pb2_grpc; from sqlalchemy import inspect; from database.accueil_session import engine; print('ACCUEIL PROTO IMPORT OK'); print('ACCUEIL TABLES:', sorted(inspect(engine).get_table_names()))"
if ($LASTEXITCODE -ne 0) { throw "Accueil verification failed." }

Write-Host ""
Write-Host "=============================================="
Write-Host " PROJECTX LOT B ACCUEIL INSTALLATION COMPLETE"
Write-Host "=============================================="
Write-Host "Start Auth on 50051, then run:"
Write-Host "  .\scripts\start_accueil.ps1"
