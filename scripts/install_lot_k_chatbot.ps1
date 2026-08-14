$ErrorActionPreference='Stop'
$ProjectRoot=Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot
Write-Host 'PROJECTX LOT K - CHATBOT + FINAL RUNTIME INSTALLER'
Write-Host "Project root: $ProjectRoot"
foreach ($Required in @(
  "$ProjectRoot\proto\common\v1\common.proto",
  "$ProjectRoot\proto\auth\v1\auth.proto",
  "$ProjectRoot\proto\accueil\v1\accueil.proto",
  "$ProjectRoot\proto\hospitalisation\v1\hospitalisation.proto",
  "$ProjectRoot\proto\billing\v1\billing.proto",
  "$ProjectRoot\proto\pharmacie\v1\pharmacie.proto",
  "$ProjectRoot\proto\rendezvous\v1\rendezvous.proto",
  "$ProjectRoot\proto\bi\v1\bi.proto"
)) { if (-not (Test-Path $Required)) { throw "Required ProjectX component missing: $Required" } }
$Python=Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $Python)) { throw "Virtual environment not found at $Python" }
function Add-EnvLineIfMissing([string]$Path,[string]$Key,[string]$Line) { if (-not (Test-Path $Path)) { return }; if (-not (Select-String -Path $Path -Pattern "^$([regex]::Escape($Key))=" -Quiet)) { Add-Content -Path $Path -Value $Line } }
foreach ($Path in @("$ProjectRoot\.env","$ProjectRoot\server\.env.example")) {
  Add-EnvLineIfMissing $Path 'MYSQL_CHATBOT_DATABASE' 'MYSQL_CHATBOT_DATABASE=hospital_chatbot'
  Add-EnvLineIfMissing $Path 'CHATBOT_GRPC_HOST' 'CHATBOT_GRPC_HOST=0.0.0.0'
  Add-EnvLineIfMissing $Path 'CHATBOT_GRPC_PORT' 'CHATBOT_GRPC_PORT=50061'
  Add-EnvLineIfMissing $Path 'CHATBOT_GRPC_TARGET' 'CHATBOT_GRPC_TARGET=127.0.0.1:50061'
}
$env:PYTHONPATH="$ProjectRoot;$ProjectRoot\generated"
Write-Host '[1/6] Generating Chatbot gRPC stubs...'; & "$ProjectRoot\scripts\generate_chatbot_proto.ps1"
Write-Host '[2/6] Creating hospital_chatbot and granting ProjectX DB user...'
$MysqlCommand=Get-Command mysql.exe -ErrorAction SilentlyContinue
if (-not $MysqlCommand) { $Candidate=Get-ChildItem 'C:\wamp64\bin\mysql\mysql*\bin\mysql.exe' -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -First 1; if ($Candidate) { $MysqlExe=$Candidate.FullName } } else { $MysqlExe=$MysqlCommand.Source }
if (-not $MysqlExe) { throw 'mysql.exe was not found.' }
& $MysqlExe -u root --execute="CREATE DATABASE IF NOT EXISTS hospital_chatbot CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; GRANT ALL PRIVILEGES ON hospital_chatbot.* TO 'projectx_auth'@'127.0.0.1'; FLUSH PRIVILEGES;"
if ($LASTEXITCODE -ne 0) { throw 'MySQL setup failed.' }
Write-Host '[3/6] Applying Chatbot Alembic migration...'; & $Python -m alembic -c "$ProjectRoot\alembic_chatbot.ini" upgrade head
if ($LASTEXITCODE -ne 0) { throw 'Chatbot migration failed.' }
Write-Host '[4/6] Extending Auth RBAC with chatbot.ask...'; & $Python "$ProjectRoot\scripts\patch_auth_rbac_chatbot.py"; & $Python "$ProjectRoot\scripts\seed_chatbot_permission.py"
if ($LASTEXITCODE -ne 0) { throw 'Chatbot RBAC setup failed.' }
Write-Host '[5/6] Verifying Chatbot imports/database...'
& $Python -c "from chatbot.v1 import chatbot_pb2,chatbot_pb2_grpc; from sqlalchemy import inspect; from database.chatbot_session import engine; from services.chatbot.service import ChatbotService; print('CHATBOT PROTO IMPORT OK'); print('CHATBOT TABLES:',sorted(inspect(engine).get_table_names())); print('CHATBOT SERVICE IMPORT OK')"
if ($LASTEXITCODE -ne 0) { throw 'Chatbot verification failed.' }
Write-Host '[6/6] Verifying Auth runtime HealthCheck wrapper...'
& $Python -c "from services.auth.runtime_service import RuntimeAuthService; print('AUTH RUNTIME HEALTH WRAPPER OK')"
if ($LASTEXITCODE -ne 0) { throw 'Auth runtime wrapper verification failed.' }
Write-Host ''; Write-Host '========================================================'; Write-Host ' PROJECTX LOT K CHATBOT INSTALLATION COMPLETE'; Write-Host '========================================================'; Write-Host 'Restart Auth, start Chatbot, then run chatbot smoke.'
