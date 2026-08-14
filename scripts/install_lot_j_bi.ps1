$ErrorActionPreference="Stop"
$ProjectRoot=Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot
Write-Host "PROJECTX LOT J - BI INSTALLER"
Write-Host "Project root: $ProjectRoot"
foreach ($Required in @(
    "$ProjectRoot\proto\common\v1\common.proto",
    "$ProjectRoot\proto\auth\v1\auth.proto",
    "$ProjectRoot\proto\accueil\v1\accueil.proto",
    "$ProjectRoot\proto\hospitalisation\v1\hospitalisation.proto",
    "$ProjectRoot\proto\billing\v1\billing.proto",
    "$ProjectRoot\proto\consultation\v1\consultation.proto",
    "$ProjectRoot\proto\laboratoire\v1\laboratoire.proto",
    "$ProjectRoot\proto\pharmacie\v1\pharmacie.proto",
    "$ProjectRoot\proto\maternite\v1\maternite.proto",
    "$ProjectRoot\proto\rendezvous\v1\rendezvous.proto",
    "$ProjectRoot\services\common\auth_guard.py"
)) { if (-not (Test-Path $Required)) { throw "Required ProjectX component missing: $Required" } }
$Python=Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { throw "Virtual environment not found at $Python" }
function Add-EnvLineIfMissing([string]$Path,[string]$Key,[string]$Line) { if (-not (Test-Path $Path)) { return }; if (-not (Select-String -Path $Path -Pattern "^$([regex]::Escape($Key))=" -Quiet)) { Add-Content -Path $Path -Value $Line } }
Add-EnvLineIfMissing "$ProjectRoot\.env" "MYSQL_BI_DATABASE" "MYSQL_BI_DATABASE=hospital_bi"
Add-EnvLineIfMissing "$ProjectRoot\.env" "BI_GRPC_HOST" "BI_GRPC_HOST=0.0.0.0"
Add-EnvLineIfMissing "$ProjectRoot\.env" "BI_GRPC_PORT" "BI_GRPC_PORT=50060"
Add-EnvLineIfMissing "$ProjectRoot\.env" "BI_GRPC_TARGET" "BI_GRPC_TARGET=127.0.0.1:50060"
Add-EnvLineIfMissing "$ProjectRoot\.env" "CHATBOT_GRPC_TARGET" "CHATBOT_GRPC_TARGET=127.0.0.1:50061"
Add-EnvLineIfMissing "$ProjectRoot\.env" "BI_MAX_PATIENT_SCAN" "BI_MAX_PATIENT_SCAN=200"
Add-EnvLineIfMissing "$ProjectRoot\.env" "BI_MAX_MEDICINE_SCAN" "BI_MAX_MEDICINE_SCAN=200"
$Example="$ProjectRoot\server\.env.example"
if (Test-Path $Example) {
  Add-EnvLineIfMissing $Example "MYSQL_BI_DATABASE" "MYSQL_BI_DATABASE=hospital_bi"
  Add-EnvLineIfMissing $Example "BI_GRPC_HOST" "BI_GRPC_HOST=0.0.0.0"
  Add-EnvLineIfMissing $Example "BI_GRPC_PORT" "BI_GRPC_PORT=50060"
  Add-EnvLineIfMissing $Example "BI_GRPC_TARGET" "BI_GRPC_TARGET=127.0.0.1:50060"
  Add-EnvLineIfMissing $Example "CHATBOT_GRPC_TARGET" "CHATBOT_GRPC_TARGET=127.0.0.1:50061"
  Add-EnvLineIfMissing $Example "BI_MAX_PATIENT_SCAN" "BI_MAX_PATIENT_SCAN=200"
  Add-EnvLineIfMissing $Example "BI_MAX_MEDICINE_SCAN" "BI_MAX_MEDICINE_SCAN=200"
}
$env:PYTHONPATH="$ProjectRoot;$ProjectRoot\generated"
Write-Host "[1/4] Generating BI gRPC stubs..."; & "$ProjectRoot\scripts\generate_bi_proto.ps1"
Write-Host "[2/4] Creating hospital_bi and granting existing ProjectX DB user..."
$MysqlCommand=Get-Command mysql.exe -ErrorAction SilentlyContinue
if (-not $MysqlCommand) { $Candidate=Get-ChildItem "C:\wamp64\bin\mysql\mysql*\bin\mysql.exe" -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -First 1; if ($Candidate) { $MysqlExe=$Candidate.FullName } } else { $MysqlExe=$MysqlCommand.Source }
if (-not $MysqlExe) { throw "mysql.exe was not found. Create hospital_bi manually, grant projectx_auth, then rerun this installer." }
& $MysqlExe -u root --execute="CREATE DATABASE IF NOT EXISTS hospital_bi CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; GRANT ALL PRIVILEGES ON hospital_bi.* TO 'projectx_auth'@'127.0.0.1'; FLUSH PRIVILEGES;"
if ($LASTEXITCODE -ne 0) { throw "MySQL setup failed." }
Write-Host "[3/4] Applying BI Alembic migration..."; & $Python -m alembic -c "$ProjectRoot\alembic_bi.ini" upgrade head
if ($LASTEXITCODE -ne 0) { throw "BI migration failed." }
Write-Host "[4/4] Verifying BI imports and own database..."
& $Python -c "from bi.v1 import bi_pb2,bi_pb2_grpc; from sqlalchemy import inspect; from database.bi_session import engine; from services.bi.service import BIService; print('BI PROTO IMPORT OK'); print('BI TABLES:',sorted(inspect(engine).get_table_names())); print('BI SERVICE IMPORT OK')"
if ($LASTEXITCODE -ne 0) { throw "BI verification failed." }
Write-Host ""; Write-Host "========================================================"; Write-Host " PROJECTX LOT J BI INSTALLATION COMPLETE"; Write-Host "========================================================"; Write-Host "Start BI on 50060. Existing business services are never accessed through SQL by BI."
