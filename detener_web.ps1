$ErrorActionPreference='Stop'
$taskPidFile=Join-Path $PSScriptRoot '.runtime\web.pid'
if (-not (Test-Path -LiteralPath $taskPidFile)) { Write-Host 'No hay servidor local registrado.'; exit }
$taskServerId=[int](Get-Content -LiteralPath $taskPidFile)
$taskProcess=Get-CimInstance Win32_Process -Filter "ProcessId=$taskServerId"
if ($taskProcess -and $taskProcess.CommandLine -like '*servir.py*' -and $taskProcess.CommandLine -like '*Proyecto_Web*') {
    Stop-Process -Id $taskServerId
    Remove-Item -LiteralPath $taskPidFile
    Write-Host 'Servidor web local detenido. PostgreSQL permanece disponible.'
} elseif (-not $taskProcess) {
    Remove-Item -LiteralPath $taskPidFile
    Write-Host 'El servidor registrado ya estaba detenido.'
} else { throw 'El PID no corresponde al servidor de este proyecto; no se detuvo ningun proceso.' }
