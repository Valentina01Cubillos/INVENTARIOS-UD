param([int]$Puerto=8000)
$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot
Set-Location -LiteralPath $taskRoot
$taskPython = Join-Path $taskRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) {
    py -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear el entorno Python.' }
}
& $taskPython -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'No se pudieron instalar las dependencias.' }
if (-not (Test-Path -LiteralPath '.env')) {
    Copy-Item -LiteralPath '.env.example' -Destination '.env'
    Write-Host 'Configure .env (clave y base PostgreSQL) antes de iniciar.'
    exit 1
}
& $taskPython manage.py migrate
if ($LASTEXITCODE -ne 0) { throw 'No se pudieron aplicar las migraciones.' }
& $taskPython manage.py crear_roles
& $taskPython manage.py check
if ($LASTEXITCODE -ne 0) { throw 'La configuracion no es valida.' }
Write-Host "Abra http://127.0.0.1:$Puerto/"
& $taskPython manage.py runserver "127.0.0.1:$Puerto"
