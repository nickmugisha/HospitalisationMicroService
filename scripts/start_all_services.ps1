$ErrorActionPreference='Stop'
$Root=Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root
$Python=Join-Path $Root '.venv\Scripts\python.exe'
$env:PYTHONPATH="$Root;$Root\generated"
$LogDir=Join-Path $Root 'logs'; $RunDir=Join-Path $Root '.run'
New-Item -ItemType Directory -Force -Path $LogDir,$RunDir | Out-Null
$StateFile=Join-Path $RunDir 'projectx-services.json'

$Services=@(
  @{Name='auth';Port=50051;Module='services.auth.main'},
  @{Name='accueil';Port=50052;Module='services.accueil.main'},
  @{Name='hospitalisation';Port=50053;Module='services.hospitalisation.main'},
  @{Name='billing';Port=50054;Module='services.billing.main'},
  @{Name='consultation';Port=50055;Module='services.consultation.main'},
  @{Name='laboratoire';Port=50056;Module='services.laboratoire.main'},
  @{Name='pharmacie';Port=50057;Module='services.pharmacie.main'},
  @{Name='maternite';Port=50058;Module='services.maternite.main'},
  @{Name='rendezvous';Port=50059;Module='services.rendezvous.main'},
  @{Name='bi';Port=50060;Module='services.bi.main'},
  @{Name='chatbot';Port=50061;Module='services.chatbot.main'}
)

# Refuse to create duplicate service trees. Ports must be free before launch.
$occupied=@()
foreach($svc in $Services){
    $existing=Get-NetTCPConnection -LocalPort $svc.Port -State Listen -ErrorAction SilentlyContinue
    if($existing){
        foreach($conn in @($existing)){
            $occupied += ("{0}:{1} PID={2}" -f $svc.Name,$svc.Port,$conn.OwningProcess)
        }
    }
}
if($occupied.Count -gt 0){
    Write-Host '[ABORT] ProjectX ports are already occupied. Run .\scripts\stop_all_services.ps1 first.'
    $occupied | ForEach-Object { Write-Host ('  '+$_) }
    exit 2
}

$launchers=@()
foreach ($svc in $Services) {
  $out=Join-Path $LogDir ($svc.Name+'.out.log'); $err=Join-Path $LogDir ($svc.Name+'.err.log')
  # Clear old logs so a failed run cannot look successful because of stale lines.
  Set-Content -Path $out -Value ''
  Set-Content -Path $err -Value ''
  $p=Start-Process -FilePath $Python -ArgumentList @('-m',$svc.Module) -WorkingDirectory $Root -RedirectStandardOutput $out -RedirectStandardError $err -PassThru -WindowStyle Hidden
  $launchers += [pscustomobject]@{name=$svc.Name;port=$svc.Port;launcher_pid=$p.Id;module=$svc.Module}
  Write-Host ("[START] {0} :{1} launcher PID={2}" -f $svc.Name,$svc.Port,$p.Id)
}

# On Windows a venv python.exe can be a small launcher process while the real
# interpreter child owns the gRPC socket. Therefore verify the listener that
# appeared after a clean-port launch, and record its *actual* OwningProcess.
$deadline=(Get-Date).AddSeconds(20)
$online=@{}
while((Get-Date) -lt $deadline -and $online.Count -lt $Services.Count){
    foreach($svc in $Services){
        if($online.ContainsKey($svc.Name)){ continue }
        $listener=Get-NetTCPConnection -LocalPort $svc.Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
        if($listener){
            $actualPid=[int]$listener.OwningProcess
            if(Get-Process -Id $actualPid -ErrorAction SilentlyContinue){
                $online[$svc.Name]=$actualPid
            }
        }
    }
    if($online.Count -lt $Services.Count){ Start-Sleep -Milliseconds 500 }
}

Write-Host ''
$state=@()
$failed=@()
foreach($svc in $Services){
    $launcher=$launchers | Where-Object {$_.name -eq $svc.Name} | Select-Object -First 1
    if($online.ContainsKey($svc.Name)){
        $listenerPid=[int]$online[$svc.Name]
        Write-Host ("[ONLINE] {0} :{1} listener PID={2} launcher PID={3}" -f $svc.Name,$svc.Port,$listenerPid,$launcher.launcher_pid)
        $state += [pscustomobject]@{
            name=$svc.Name
            port=$svc.Port
            module=$svc.Module
            launcher_pid=[int]$launcher.launcher_pid
            listener_pid=$listenerPid
        }
    } else {
        Write-Host ("[OFFLINE] {0} :{1} (see logs\{0}.err.log)" -f $svc.Name,$svc.Port)
        $failed += $svc.Name
        $state += [pscustomobject]@{
            name=$svc.Name
            port=$svc.Port
            module=$svc.Module
            launcher_pid=[int]$launcher.launcher_pid
            listener_pid=$null
        }
    }
}
$state | ConvertTo-Json | Set-Content $StateFile

Write-Host ''
Write-Host ('Logs: '+$LogDir)
if($failed.Count -gt 0){
    Write-Host ('[FAILED] Could not start: '+($failed -join ', '))
    exit 1
}
Write-Host 'PROJECTX ALL 11 LISTENERS ONLINE.'
Write-Host 'Run global health: python .\scripts\test_all_services_health.py'
