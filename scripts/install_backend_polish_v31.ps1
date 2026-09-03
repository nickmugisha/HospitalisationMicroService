$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { throw "Virtual environment not found: $Python" }
if (-not (Test-Path "$Root\.env")) { throw "Missing $Root\.env" }

$listeners = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.LocalPort -ge 50051 -and $_.LocalPort -le 50062 }
if ($listeners) {
    $ports = ($listeners | Select-Object -ExpandProperty LocalPort -Unique | Sort-Object) -join ", "
    throw "ProjectX services are still listening on ports: $ports. Run .\scripts\stop_all_services.ps1 first."
}

$env:PYTHONPATH = "$Root;$Root\generated"

Write-Host "[1/8] Verifying v3 baseline and Python dependencies..." -ForegroundColor Yellow
foreach($required in @(
    "$Root\migrations\versions\a14b2026hr01_add_staff_hr_workflow.py",
    "$Root\migrations_pharmacie\versions\pharmacie_0002_stock_alert_dispatches.py",
    "$Root\proto\hr\v1\hr.proto",
    "$Root\scripts\test_chatbot_v2_engine.py"
)) {
    if (-not (Test-Path $required)) { throw "Required v3 baseline file missing: $required" }
}
& $Python -c "import grpc, grpc_tools, sqlalchemy, alembic, pymysql, jwt, bcrypt, dotenv; print('dependencies OK')"
if ($LASTEXITCODE -ne 0) { throw "Required Python dependencies are missing." }

Write-Host "[2/8] Regenerating Auth + Consultation + Pharmacy protobuf stubs..." -ForegroundColor Yellow
foreach($rel in @("auth\v1\auth.proto", "consultation\v1\consultation.proto", "pharmacie\v1\pharmacie.proto")) {
    $proto = Join-Path "$Root\proto" $rel
    & $Python -m grpc_tools.protoc -I="$Root\proto" --python_out="$Root\generated" --grpc_python_out="$Root\generated" $proto
    if ($LASTEXITCODE -ne 0) { throw "Proto generation failed: $rel" }
}
foreach($pkg in @("auth", "consultation", "pharmacie")) {
    foreach($f in @("$Root\generated\$pkg\__init__.py", "$Root\generated\$pkg\v1\__init__.py")) {
        if (-not (Test-Path $f)) { New-Item -ItemType File -Force -Path $f | Out-Null }
    }
}

Write-Host "[3/8] Preflighting syntax and additive contracts..." -ForegroundColor Yellow
& $Python -m compileall -q "$Root\services\auth" "$Root\services\consultation" "$Root\services\pharmacie" "$Root\scripts\test_backend_polish_v31_contracts.py" "$Root\migrations" "$Root\migrations_consultation" "$Root\migrations_pharmacie"
if ($LASTEXITCODE -ne 0) { throw "Python compilation failed." }
& $Python "$Root\scripts\test_backend_polish_v31_contracts.py"
if ($LASTEXITCODE -ne 0) { throw "v3.1 contract check failed." }

Write-Host "[4/8] Applying Auth self-service/session migration..." -ForegroundColor Yellow
& $Python -m alembic -c "$Root\alembic.ini" upgrade head
if ($LASTEXITCODE -ne 0) { throw "Auth migration failed." }

Write-Host "[5/8] Applying Consultation prescription-source migration..." -ForegroundColor Yellow
& $Python -m alembic -c "$Root\alembic_consultation.ini" upgrade head
if ($LASTEXITCODE -ne 0) { throw "Consultation migration failed." }

Write-Host "[6/8] Applying Pharmacy prescription-source migration..." -ForegroundColor Yellow
& $Python -m alembic -c "$Root\alembic_pharmacie.ini" upgrade head
if ($LASTEXITCODE -ne 0) { throw "Pharmacy migration failed." }

Write-Host "[7/8] Re-running contracts and existing v3 coverage..." -ForegroundColor Yellow
& $Python "$Root\scripts\test_backend_polish_v31_contracts.py"
if ($LASTEXITCODE -ne 0) { throw "v3.1 contract check failed after migrations." }
if (Test-Path "$Root\scripts\test_backend_completion_v3_contracts.py") {
    & $Python "$Root\scripts\test_backend_completion_v3_contracts.py"
    if ($LASTEXITCODE -ne 0) { throw "Existing v3 contract regression failed." }
}

Write-Host "[8/8] Protecting Chatbot v2 deterministic behavior..." -ForegroundColor Yellow
& $Python "$Root\scripts\test_chatbot_v2_engine.py"
if ($LASTEXITCODE -ne 0) { throw "Existing Chatbot v2 engine regression failed." }

Write-Host ""
Write-Host "PROJECTX BACKEND POLISH V3.1 INSTALLATION: PASS" -ForegroundColor Green
Write-Host "Additive changes: username/email login, self password/profile, hospital/external prescription lines." -ForegroundColor Cyan
Write-Host "Next: .\scripts\start_all_services.ps1" -ForegroundColor Green
Write-Host "Then: .\.venv\Scripts\python.exe .\scripts\test_all_services_health.py" -ForegroundColor Green
Write-Host "Then: .\.venv\Scripts\python.exe .\scripts\test_backend_polish_v31_auth_smoke.py" -ForegroundColor Green
