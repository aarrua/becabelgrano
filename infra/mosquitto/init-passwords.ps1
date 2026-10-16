# ==============================================================================
# Generador de archivo de contrasenas para Mosquitto (Windows PowerShell)
# ==============================================================================
[CmdletBinding()]
param (
    [string]$Username,
    [string]$Password
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PasswordsFile = Join-Path $ScriptDir "passwords"

# 1. Determinar credenciales
if (-not $Username) {
    if ($env:MQTT_USER) {
        $Username = $env:MQTT_USER
    } else {
        $EnvFile = Join-Path $ScriptDir "..\.env"
        if (Test-Path $EnvFile) {
            Get-Content $EnvFile | ForEach-Object {
                if ($_ -match "^MQTT_USER=(.*)$") {
                    $Username = $matches[1].Trim()
                }
            }
        }
    }
}
if (-not $Username) { $Username = "tanques" }

if (-not $Password) {
    if ($env:MQTT_PASSWORD) {
        $Password = $env:MQTT_PASSWORD
    } else {
        $EnvFile = Join-Path $ScriptDir "..\.env"
        if (Test-Path $EnvFile) {
            Get-Content $EnvFile | ForEach-Object {
                if ($_ -match "^MQTT_PASSWORD=(.*)$") {
                    $Password = $matches[1].Trim()
                }
            }
        }
    }
}

# Validar que la contrasena no este vacia ni sea el placeholder inseguro
if ([string]::IsNullOrWhiteSpace($Password) -or $Password -eq "cambiar-esta-clave") {
    Write-Error "ERROR: Debe definir una contrasena valida para Mosquitto (MQTT_PASSWORD). No se permite utilizar la contrasena vacia ni el valor de ejemplo 'cambiar-esta-clave'. Configure una contrasena segura en infra/.env (MQTT_PASSWORD=...) o pasela por parametro: .\init-passwords.ps1 -Username tanques -Password mi_password_segura"
    exit 1
}

Write-Host "Generando archivo de credenciales Mosquitto para el usuario: '$Username'..." -ForegroundColor Cyan

# 2. Generar archivo mediante contenedor Docker
$volPath = $ScriptDir
docker run --rm -v "${volPath}:/mosquitto/config" eclipse-mosquitto:2.0.22 mosquitto_passwd -c -b /mosquitto/config/passwords $Username $Password

if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] Archivo de contrasenas generado con exito en: $PasswordsFile" -ForegroundColor Green
    Write-Host "     Usuario configurado: $Username" -ForegroundColor Gray
} else {
    Write-Error "Error al generar el archivo de contrasenas con Docker."
}
