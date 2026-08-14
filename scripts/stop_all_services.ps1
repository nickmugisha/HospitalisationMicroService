$ErrorActionPreference='Continue'
$Root=Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$State=Join-Path $Root '.run\projectx-services.json'

# Stop both the venv launcher PID and the actual listener PID recorded by the
# fixed launcher. Then perform a port cleanup as a safety net.
if (Test-Path $State) {
    try {
        $items=Get-Content $State -Raw | ConvertFrom-Json
        if ($items -isnot [System.Array]) { $items=@($items) }
        foreach($item in $items){
            $pids=@()
            if($item.PSObject.Properties.Name -contains 'listener_pid' -and $item.listener_pid){ $pids += [int]$item.listener_pid }
            if($item.PSObject.Properties.Name -contains 'launcher_pid' -and $item.launcher_pid){ $pids += [int]$item.launcher_pid }
            if($item.PSObject.Properties.Name -contains 'pid' -and $item.pid){ $pids += [int]$item.pid } # backward compatibility
            foreach($pidToStop in ($pids | Select-Object -Unique)){
                if(Get-Process -Id $pidToStop -ErrorAction SilentlyContinue){
                    Stop-Process -Id $pidToStop -Force -ErrorAction SilentlyContinue
                    Write-Host ('[STOP PID] '+$item.name+' PID '+$pidToStop)
                }
            }
        }
    } catch {
        Write-Host '[WARN] PID state file could not be read; falling back to port cleanup.'
    }
}

Start-Sleep -Milliseconds 700
foreach($port in 50051..50061){
    $listeners=Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    foreach($listener in @($listeners)){
        $pidToStop=[int]$listener.OwningProcess
        if($pidToStop -and (Get-Process -Id $pidToStop -ErrorAction SilentlyContinue)){
            Stop-Process -Id $pidToStop -Force -ErrorAction SilentlyContinue
            Write-Host ("[STOP PORT] :$port PID $pidToStop")
        }
    }
}

Remove-Item $State -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1
$remaining=@()
foreach($port in 50051..50061){
    if(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue){ $remaining += $port }
}
if($remaining.Count -eq 0){
    Write-Host 'PROJECTX ALL SERVICE PORTS STOPPED.'
} else {
    Write-Host ('[WARN] Ports still listening: '+($remaining -join ', '))
    exit 1
}
