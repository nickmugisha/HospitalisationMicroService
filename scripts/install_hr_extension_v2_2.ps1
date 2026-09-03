$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { throw "Virtual environment not found: $Python" }

function Add-EnvLineIfMissing([string]$Path,[string]$Key,[string]$Line) {
    if (-not (Test-Path $Path)) { return }
    if (-not (Select-String -Path $Path -Pattern "^$([regex]::Escape($Key))=" -Quiet)) { Add-Content -Path $Path -Value $Line }
}
foreach($target in @("$Root\.env", "$Root\server\.env.example")) {
    Add-EnvLineIfMissing $target "QR_CREDENTIAL_VALID_DAYS" "QR_CREDENTIAL_VALID_DAYS=365"
    Add-EnvLineIfMissing $target "MYSQL_HR_DATABASE" "MYSQL_HR_DATABASE=hospital_hr"
    Add-EnvLineIfMissing $target "HR_GRPC_HOST" "HR_GRPC_HOST=0.0.0.0"
    Add-EnvLineIfMissing $target "HR_GRPC_PORT" "HR_GRPC_PORT=50062"
    Add-EnvLineIfMissing $target "HR_GRPC_TARGET" "HR_GRPC_TARGET=127.0.0.1:50062"
    Add-EnvLineIfMissing $target "HR_LOCAL_UTC_OFFSET_MINUTES" "HR_LOCAL_UTC_OFFSET_MINUTES=120"
    Add-EnvLineIfMissing $target "HR_LATE_GRACE_MINUTES" "HR_LATE_GRACE_MINUTES=15"
}
$env:PYTHONPATH = "$Root;$Root\generated"

Write-Host "[1/8] Verifying Python dependencies..." -ForegroundColor Yellow
& $Python -c "import grpc, sqlalchemy, alembic, pymysql, jwt, bcrypt; import grpc_tools; print('dependencies OK')"
if ($LASTEXITCODE -ne 0) { throw "Required Python dependencies are missing." }

Write-Host "[2/8] Regenerating Auth protobuf (approval + QR)..." -ForegroundColor Yellow
& $Python -m grpc_tools.protoc -I="$Root\proto" --python_out="$Root\generated" --grpc_python_out="$Root\generated" "$Root\proto\auth\v1\auth.proto"
if ($LASTEXITCODE -ne 0) { throw "Auth protobuf generation failed." }

Write-Host "[3/8] Generating HR protobuf..." -ForegroundColor Yellow
& "$Root\scripts\generate_hr_proto.ps1"

Write-Host "[4/8] Applying Auth migrations..." -ForegroundColor Yellow
& $Python -m alembic -c "$Root\alembic.ini" upgrade head
if ($LASTEXITCODE -ne 0) { throw "Auth migration failed." }

Write-Host "[5/8] Creating hospital_hr database and granting ProjectX DB user..." -ForegroundColor Yellow
$MysqlCommand=Get-Command mysql.exe -ErrorAction SilentlyContinue
if (-not $MysqlCommand) {
    $Candidate=Get-ChildItem "C:\wamp64\bin\mysql\mysql*\bin\mysql.exe" -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -First 1
    if ($Candidate) { $MysqlExe=$Candidate.FullName }
} else { $MysqlExe=$MysqlCommand.Source }
if (-not $MysqlExe) { throw "mysql.exe was not found." }
& $MysqlExe -u root --execute="CREATE DATABASE IF NOT EXISTS hospital_hr CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; GRANT ALL PRIVILEGES ON hospital_hr.* TO 'projectx_auth'@'127.0.0.1'; FLUSH PRIVILEGES;"
if ($LASTEXITCODE -ne 0) { throw "HR MySQL database setup failed." }

Write-Host "[6/8] Applying HR migration..." -ForegroundColor Yellow
& $Python -m alembic -c "$Root\alembic_hr.ini" upgrade head
if ($LASTEXITCODE -ne 0) { throw "HR migration failed." }

Write-Host "[7/8] Refreshing canonical roles and permissions..." -ForegroundColor Yellow
& $Python "$Root\scripts\seed_auth.py"
if ($LASTEXITCODE -ne 0) { throw "Auth role seed failed." }

Write-Host "[8/8] Verifying contracts, imports and HR tables..." -ForegroundColor Yellow
& $Python -m py_compile "$Root\services\auth\service.py" "$Root\services\auth\rbac.py" "$Root\services\hr\config.py" "$Root\services\hr\models.py" "$Root\services\hr\repository.py" "$Root\services\hr\service.py" "$Root\services\hr\main.py" "$Root\scripts\test_hr_extension_smoke.py"
if ($LASTEXITCODE -ne 0) { throw "Python syntax verification failed." }
& $Python -c "from auth.v1 import auth_pb2; from hr.v1 import hr_pb2, hr_pb2_grpc; from sqlalchemy import inspect; from database.hr_session import engine; assert hasattr(auth_pb2,'QrLoginRequest'); assert hasattr(auth_pb2,'RegisterStaffRequest'); assert not hasattr(auth_pb2,'RegisterRequest'); assert hasattr(hr_pb2_grpc,'HRServiceStub'); print('HR TABLES:', sorted(inspect(engine).get_table_names())); print('PROJECTX v2.2 HR CONTRACTS OK')"
if ($LASTEXITCODE -ne 0) { throw "Final HR/Auth verification failed." }

Write-Host ""
Write-Host "PROJECTX v2.2 HR EXTENSION INSTALLATION COMPLETE" -ForegroundColor Green
Write-Host "Official v2.0 baseline: 11 services. Current project extension: 12 services with HR on port 50062." -ForegroundColor Cyan
Write-Host "Next: .\scripts\start_all_services.ps1" -ForegroundColor Green
Write-Host "Then: .\.venv\Scripts\python.exe .\scripts\test_hr_extension_smoke.py" -ForegroundColor Green
