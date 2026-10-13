param([string]$IpServidor, [ValidateRange(1,65535)][int]$Puerto=8000)
$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
$taskPython=Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) {
    if (-not (Get-Command py -ErrorAction SilentlyContinue)) { throw 'Instale Python para Windows y vuelva a ejecutar este lanzador.' }
    py -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear el entorno .venv.' }
}
& $taskPython -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'No se pudieron instalar las dependencias de Proyecto_Web.' }
if (-not (Test-Path -LiteralPath '.env')) {
    Copy-Item -LiteralPath '.env.example' -Destination '.env'
    Write-Host 'Se creo .env desde .env.example. Configure la clave Django y PostgreSQL; luego ejecute este lanzador de nuevo.'
    exit 1
}
if (-not $IpServidor) {
    $taskInterfaces=Get-NetIPInterface -AddressFamily IPv4
    $taskRoute=Get-NetRoute -DestinationPrefix '0.0.0.0/0' | Sort-Object { $taskIndex=$_.InterfaceIndex; $_.RouteMetric + ($taskInterfaces | Where-Object InterfaceIndex -eq $taskIndex | Select-Object -First 1).InterfaceMetric } | Select-Object -First 1
    if (-not $taskRoute) { throw 'No hay una ruta de red activa. Conecte el equipo a la red o indique -IpServidor.' }
    $IpServidor=(Get-NetIPAddress -InterfaceIndex $taskRoute.InterfaceIndex -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '169.254.*' } | Select-Object -First 1).IPAddress
}
if (-not $IpServidor) { throw 'Indique la IP del servidor con -IpServidor.' }
$taskLocalIps=@(Get-NetIPAddress -AddressFamily IPv4 | Select-Object -ExpandProperty IPAddress)
if ($IpServidor -notin $taskLocalIps) { throw 'La IP indicada no pertenece a este computador.' }
if (Get-NetTCPConnection -LocalPort $Puerto -State Listen -ErrorAction SilentlyContinue) { throw "El puerto $Puerto ya esta ocupado. Detenga la instancia anterior con detener_web.ps1 o use -Puerto con otro numero." }
$env:DJANGO_ALLOWED_HOSTS="localhost,127.0.0.1,$IpServidor"
$env:DJANGO_CSRF_TRUSTED_ORIGINS="http://localhost:$Puerto,http://127.0.0.1:$Puerto,http://${IpServidor}:$Puerto"
$env:DJANGO_DEBUG='true'
& $taskPython manage.py check
if ($LASTEXITCODE -ne 0) { throw 'La aplicacion no esta configurada.' }
& $taskPython manage.py shell -c "from django.db import connection; assert connection.vendor == 'postgresql', 'Configure PostgreSQL antes de compartir en red'"
if ($LASTEXITCODE -ne 0) { throw 'La red multiusuario requiere PostgreSQL.' }
& $taskPython manage.py collectstatic --noinput
if ($LASTEXITCODE -ne 0) { throw 'No se pudieron preparar los archivos de la interfaz.' }
Write-Host "URL local: http://localhost:$Puerto/"
Write-Host "URL de red local: http://${IpServidor}:$Puerto/"
Write-Host 'Comparta la URL de red con sus companeros. Mantenga esta ventana abierta; Ctrl+C detiene el servidor.'
Write-Host 'Permita este puerto solo desde la red del laboratorio. Para internet use el proxy HTTPS descrito en README.'
# Static files for this LAN profile are handled by WhiteNoise via WSGI.
& $taskPython servir.py --host 0.0.0.0 --port $Puerto
if ($LASTEXITCODE -ne 0) { throw 'El servidor no pudo iniciarse o se interrumpio.' }
