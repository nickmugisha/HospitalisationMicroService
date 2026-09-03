$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { throw "Virtual environment not found: $Python" }
if (-not (Test-Path "$Root\.env")) { throw "Missing $Root\.env. This installer never creates database/JWT credentials." }

$listeners = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.LocalPort -ge 50051 -and $_.LocalPort -le 50062 }
if ($listeners) {
    $ports = ($listeners | Select-Object -ExpandProperty LocalPort -Unique | Sort-Object) -join ", "
    throw "ProjectX services are still listening on ports: $ports. Run .\scripts\stop_all_services.ps1 first."
}

function Get-EnvValue([string]$Path,[string]$Key) {
    if (-not (Test-Path $Path)) { return "" }
    $m = Select-String -Path $Path -Pattern "^$([regex]::Escape($Key))=(.*)$" | Select-Object -Last 1
    if (-not $m) { return "" }
    return $m.Matches[0].Groups[1].Value.Trim()
}
function Add-EnvLineIfMissing([string]$Path,[string]$Key,[string]$Line) {
    if (-not (Test-Path $Path)) { return }
    if (-not (Select-String -Path $Path -Pattern "^$([regex]::Escape($Key))=" -Quiet)) { Add-Content -Path $Path -Value $Line }
}

Write-Host "[1/12] Preparing private internal-service configuration..." -ForegroundColor Yellow
$currentInternal = Get-EnvValue "$Root\.env" "PROJECTX_INTERNAL_SERVICE_TOKEN"
if (-not $currentInternal -or $currentInternal -eq "change_me_random_internal_service_token") {
    # Remove a blank/placeholder line before writing a real local secret.
    $content = Get-Content "$Root\.env" | Where-Object { $_ -notmatch '^PROJECTX_INTERNAL_SERVICE_TOKEN=' }
    Set-Content -Path "$Root\.env" -Value $content
    $token = (& $Python -c "import secrets; print(secrets.token_urlsafe(48))").Trim()
    if (-not $token) { throw "Could not generate PROJECTX_INTERNAL_SERVICE_TOKEN." }
    Add-Content -Path "$Root\.env" -Value "PROJECTX_INTERNAL_SERVICE_TOKEN=$token"
    Write-Host "  Generated PROJECTX_INTERNAL_SERVICE_TOKEN in local .env (value not displayed)." -ForegroundColor Green
}
foreach($target in @("$Root\.env", "$Root\server\.env.example")) {
    Add-EnvLineIfMissing $target "RENDEZVOUS_REMINDER_LEAD_MINUTES" "RENDEZVOUS_REMINDER_LEAD_MINUTES=1440"
    Add-EnvLineIfMissing $target "RENDEZVOUS_REMINDER_POLL_SECONDS" "RENDEZVOUS_REMINDER_POLL_SECONDS=60"
    Add-EnvLineIfMissing $target "PHARMACIE_ALERT_POLL_SECONDS" "PHARMACIE_ALERT_POLL_SECONDS=3600"
    Add-EnvLineIfMissing $target "PHARMACIE_ALERT_EXPIRY_DAYS" "PHARMACIE_ALERT_EXPIRY_DAYS=30"
}
$env:PYTHONPATH = "$Root;$Root\generated"

Write-Host "[2/12] Verifying Python dependencies..." -ForegroundColor Yellow
& $Python -c "import grpc, grpc_tools, sqlalchemy, alembic, pymysql, jwt, bcrypt, dotenv; print('dependencies OK')"
if ($LASTEXITCODE -ne 0) { throw "Required Python dependencies are missing." }

Write-Host "[3/12] Regenerating additive gRPC contracts..." -ForegroundColor Yellow
$protos = @(
    "auth\v1\auth.proto",
    "hospitalisation\v1\hospitalisation.proto",
    "billing\v1\billing.proto",
    "laboratoire\v1\laboratoire.proto",
    "pharmacie\v1\pharmacie.proto",
    "maternite\v1\maternite.proto",
    "rendezvous\v1\rendezvous.proto",
    "hr\v1\hr.proto"
)
foreach($rel in $protos) {
    $proto = Join-Path "$Root\proto" $rel
    & $Python -m grpc_tools.protoc -I="$Root\proto" --python_out="$Root\generated" --grpc_python_out="$Root\generated" $proto
    if ($LASTEXITCODE -ne 0) { throw "Proto generation failed: $rel" }
}
foreach($pkg in @("auth","hospitalisation","billing","laboratoire","pharmacie","maternite","rendezvous","hr")) {
    foreach($f in @("$Root\generated\$pkg\__init__.py","$Root\generated\$pkg\v1\__init__.py")) {
        if (-not (Test-Path $f)) { New-Item -ItemType File -Force -Path $f | Out-Null }
    }
}

Write-Host "[4/12] Preflighting Python syntax + proto/server coverage before DB migrations..." -ForegroundColor Yellow
& $Python -m compileall -q "$Root\services" "$Root\scripts" "$Root\migrations_hospitalisation" "$Root\migrations_pharmacie" "$Root\migrations_rendezvous"
if ($LASTEXITCODE -ne 0) { throw "Python compilation failed." }
& $Python "$Root\scripts\test_backend_completion_v3_contracts.py"
if ($LASTEXITCODE -ne 0) { throw "Backend completion contract check failed." }

Write-Host "[5/12] Applying additive Hospitalisation migration..." -ForegroundColor Yellow
& $Python -m alembic -c "$Root\alembic_hospitalisation.ini" upgrade head
if ($LASTEXITCODE -ne 0) { throw "Hospitalisation migration failed." }

Write-Host "[6/12] Applying additive Pharmacie migration..." -ForegroundColor Yellow
& $Python -m alembic -c "$Root\alembic_pharmacie.ini" upgrade head
if ($LASTEXITCODE -ne 0) { throw "Pharmacie migration failed." }

Write-Host "[7/12] Applying additive Rendez-vous migration..." -ForegroundColor Yellow
& $Python -m alembic -c "$Root\alembic_rendezvous.ini" upgrade head
if ($LASTEXITCODE -ne 0) { throw "Rendez-vous migration failed." }

Write-Host "[8/12] Re-checking Auth and HR schema heads..." -ForegroundColor Yellow
& $Python -m alembic -c "$Root\alembic.ini" upgrade head
if ($LASTEXITCODE -ne 0) { throw "Auth migration check failed." }
& $Python -m alembic -c "$Root\alembic_hr.ini" upgrade head
if ($LASTEXITCODE -ne 0) { throw "HR migration check failed." }

Write-Host "[9/12] Refreshing canonical roles and permissions..." -ForegroundColor Yellow
& $Python "$Root\scripts\seed_auth.py"
if ($LASTEXITCODE -ne 0) { throw "Auth role/permission seed failed." }

Write-Host "[10/12] Recompiling server code after migration/seed..." -ForegroundColor Yellow
& $Python -m compileall -q "$Root\services" "$Root\scripts"
if ($LASTEXITCODE -ne 0) { throw "Python compilation failed." }

Write-Host "[11/12] Re-running contract coverage..." -ForegroundColor Yellow
& $Python "$Root\scripts\test_backend_completion_v3_contracts.py"
if ($LASTEXITCODE -ne 0) { throw "Backend completion contract check failed after migration." }

Write-Host "[12/12] Protecting existing Chatbot v2 behavior..." -ForegroundColor Yellow
& $Python "$Root\scripts\test_chatbot_v2_engine.py"
if ($LASTEXITCODE -ne 0) { throw "Existing Chatbot v2 regression test failed." }

Write-Host ""
Write-Host "PROJECTX BACKEND COMPLETION V3 INSTALLATION: PASS" -ForegroundColor Green
Write-Host "Ports remain 50051-50062. Existing hospital business rows were not deleted." -ForegroundColor Cyan
Write-Host "Next: .\scripts\start_all_services.ps1" -ForegroundColor Green
Write-Host "Then: .\.venv\Scripts\python.exe .\scripts\test_all_services_health.py" -ForegroundColor Green
Write-Host "Then run the v3 read-only + existing HR + Chatbot regressions from README_BACKEND_COMPLETION_V3.md." -ForegroundColor Green
