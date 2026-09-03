$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Python = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) { throw "Virtual environment not found at $Python" }
if (-not (Test-Path "$Root\proto\chatbot\v1\chatbot.proto")) { throw "Missing chatbot.proto" }
if (-not (Test-Path "$Root\proto\auth\v1\auth.proto")) { throw "Missing auth.proto" }
if (-not (Test-Path "$Root\proto\hr\v1\hr.proto")) { throw "Missing HR extension. Extract/install the HR v2.2 overlay before Chatbot v2." }

$env:PYTHONPATH = "$Root;$Root\generated"

Write-Host "[1/6] Checking grpc_tools..."
& $Python -c "import grpc_tools, grpc, sqlalchemy; print('Dependencies OK')"
if ($LASTEXITCODE -ne 0) { throw "Required Python packages are missing." }

Write-Host "[2/6] Regenerating Auth + HR + Chatbot protobuf stubs..."
New-Item -ItemType Directory -Force -Path "$Root\generated\auth\v1" | Out-Null
New-Item -ItemType Directory -Force -Path "$Root\generated\hr\v1" | Out-Null
New-Item -ItemType Directory -Force -Path "$Root\generated\chatbot\v1" | Out-Null

foreach ($proto in @(
    "$Root\proto\auth\v1\auth.proto",
    "$Root\proto\hr\v1\hr.proto",
    "$Root\proto\chatbot\v1\chatbot.proto"
)) {
    & $Python -m grpc_tools.protoc -I="$Root\proto" --python_out="$Root\generated" --grpc_python_out="$Root\generated" $proto
    if ($LASTEXITCODE -ne 0) { throw "Proto generation failed for $proto" }
}

foreach ($f in @(
    "$Root\generated\auth\__init__.py", "$Root\generated\auth\v1\__init__.py",
    "$Root\generated\hr\__init__.py", "$Root\generated\hr\v1\__init__.py",
    "$Root\generated\chatbot\__init__.py", "$Root\generated\chatbot\v1\__init__.py"
)) {
    if (-not (Test-Path $f)) { New-Item -ItemType File -Path $f | Out-Null }
}

Write-Host "[3/6] Verifying Chatbot v2 Python syntax..."
& $Python -m py_compile `
    "$Root\services\chatbot\assistant_engine.py" `
    "$Root\services\chatbot\service.py" `
    "$Root\services\chatbot\config.py" `
    "$Root\scripts\test_chatbot_v2_engine.py" `
    "$Root\scripts\test_chatbot_v2_smoke.py"
if ($LASTEXITCODE -ne 0) { throw "Python syntax verification failed." }

Write-Host "[4/6] Running deterministic assistant-engine tests..."
& $Python "$Root\scripts\test_chatbot_v2_engine.py"
if ($LASTEXITCODE -ne 0) { throw "Chatbot v2 engine tests failed." }

Write-Host "[5/6] Verifying generated Chatbot v2 contract..."
& $Python -c "from chatbot.v1 import chatbot_pb2, chatbot_pb2_grpc; s=chatbot_pb2.DESCRIPTOR.services_by_name['ChatbotService']; names={m.name for m in s.methods}; required={'GetPublicWelcome','AskPublicAssistant','StartSession','AskAssistant','GetConversation','ClearSession','GetCapabilities','HealthCheck'}; missing=required-names; assert not missing, missing; r=chatbot_pb2.AskAssistantRequest(); assert 'context' in r.DESCRIPTOR.fields_by_name; sr=chatbot_pb2.SessionResponse(); assert 'welcome_message' in sr.DESCRIPTOR.fields_by_name; print('CHATBOT V2 CONTRACT OK')"
if ($LASTEXITCODE -ne 0) { throw "Chatbot v2 contract verification failed." }

Write-Host "[6/6] Installation summary"
Write-Host "  - Public login-page assistant: ENABLED (no hospital-data calls)"
Write-Host "  - Authenticated name greeting: ENABLED"
Write-Host "  - English/French: ENABLED"
Write-Host "  - Role/permission awareness: ENABLED"
Write-Host "  - Current-module/resource context: ENABLED"
Write-Host "  - ProjectX how-to knowledge: ENABLED"
Write-Host "  - Permission-safe live reads: ENABLED"
Write-Host ""
Write-Host "PROJECTX CHATBOT V2 INSTALLATION COMPLETE"
Write-Host "Restart Chatbot (or all services) before running test_chatbot_v2_smoke.py."
