<#
.SYNOPSIS
    Levanta la demo de Fase 4 (UTN FRSF / GITDA): nivel, temperatura y bomba simulados,
    caudal medido por el caudalímetro real (Arduino Uno por USB), backend en perfil prod
    y bridge con MQTT real. Ver docs/06-demo.md.

.PARAMETER SinCaudal
    Plan B 100% simulado: omite --flow-serial (no se abre el puerto del caudalímetro real).

.NOTES
    Para Windows PowerShell 5.1. No imprime secretos en pantalla.
    Ejecutar siempre sobre una red propia (router/hotspot dedicado), nunca sobre la red
    institucional (ver AGENTS.md, punto 10).
#>

param(
    [switch]$SinCaudal
)

# ==============================================================================
# Variables editables
# ==============================================================================
$PuertoCaudal   = "COM4"
$BaudrateCaudal = 115200
$JdkBaseDir     = "C:\Program Files\Eclipse Adoptium"
$InfluxUrlPorDefecto = "http://localhost:8086"
$SegundosEsperaInflux = 60

$RepoRoot   = Split-Path -Parent $PSScriptRoot
$InfraDir   = Join-Path $RepoRoot "infra"
$EdgeDir    = Join-Path $RepoRoot "edge"
$BackendDir = Join-Path $RepoRoot "backend"
$EnvFile    = Join-Path $InfraDir ".env"

Write-Host "=== Demo Caudal Real - Kit Didactico de Tanques (UTN FRSF / GITDA) ===" -ForegroundColor Cyan
if ($SinCaudal) {
    Write-Host "Modo -SinCaudal: plan B 100% simulado, no se abre el puerto del caudalimetro." -ForegroundColor Yellow
} else {
    Write-Host "Caudal real habilitado por $PuertoCaudal. Nivel, temperatura y bomba: simulados." -ForegroundColor Yellow
}
Write-Host "Recordatorio: usar una red propia (router/hotspot dedicado), NUNCA la red institucional." -ForegroundColor Yellow
Write-Host ""

# ==============================================================================
# 1. JDK 21 de Eclipse Adoptium -> JAVA_HOME y Path
# ==============================================================================
if (-not (Test-Path $JdkBaseDir)) {
    Write-Host "ERROR: no se encontro Eclipse Adoptium en '$JdkBaseDir'. Instala el JDK 21 Temurin." -ForegroundColor Red
    exit 1
}

$CandidatosJdk21 = Get-ChildItem -Path $JdkBaseDir -Directory -Filter "jdk-21*" -ErrorAction SilentlyContinue |
    ForEach-Object {
        $verTexto = ($_.Name -replace '^jdk-', '') -replace '-hotspot$', ''
        try {
            [PSCustomObject]@{ Carpeta = $_; Version = [version]$verTexto }
        } catch {
            $null
        }
    } | Where-Object { $_ -ne $null }

if (-not $CandidatosJdk21 -or $CandidatosJdk21.Count -eq 0) {
    Write-Host "ERROR: no se encontro ninguna carpeta 'jdk-21*' dentro de '$JdkBaseDir'. Instala el JDK 21 Temurin." -ForegroundColor Red
    exit 1
}

$Jdk21 = ($CandidatosJdk21 | Sort-Object Version -Descending | Select-Object -First 1).Carpeta
$env:JAVA_HOME = $Jdk21.FullName
$env:Path = "$($env:JAVA_HOME)\bin;$($env:Path)"
Write-Host "JAVA_HOME = $($env:JAVA_HOME)"

# ==============================================================================
# 2. Cargar infra\.env en el entorno (sin mostrar los valores)
# ==============================================================================
if (-not (Test-Path $EnvFile)) {
    Write-Host "ERROR: no existe '$EnvFile'. Copia infra\.env.example a infra\.env y completalo." -ForegroundColor Red
    exit 1
}

Write-Host "Cargando infra\.env en el entorno (los valores no se muestran)..."
Get-Content -Path $EnvFile | ForEach-Object {
    $linea = $_.Trim()
    if ($linea -eq "" -or $linea.StartsWith("#")) { return }
    $idx = $linea.IndexOf("=")
    if ($idx -lt 1) { return }
    $clave = $linea.Substring(0, $idx).Trim()
    $valor = $linea.Substring($idx + 1).Trim()
    if ($clave -ne "") {
        Set-Item -Path "Env:$clave" -Value $valor
    }
}

# ==============================================================================
# 3. INFLUX_URL
# ==============================================================================
if ([string]::IsNullOrWhiteSpace($env:INFLUX_URL)) {
    $env:INFLUX_URL = $InfluxUrlPorDefecto
}
Write-Host "INFLUX_URL = $($env:INFLUX_URL)"

# ==============================================================================
# 4. JWT_SECRET aleatorio (256 bits, nunca se imprime)
# ==============================================================================
$bytesSecreto = New-Object byte[] 48
[System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytesSecreto)
$env:JWT_SECRET = [Convert]::ToBase64String($bytesSecreto)
Write-Host "JWT_SECRET generado al azar para esta sesion (no se muestra)."

# ==============================================================================
# 5. Contrasenas iniciales de DOCENTE y ALUMNO (Read-Host, nunca en claro en pantalla)
# ==============================================================================
function ConvertFrom-SecureStringPlano {
    param([System.Security.SecureString]$Secreto)
    $bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($Secreto)
    try {
        return [System.Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    } finally {
        [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

$DocenteSecure = Read-Host -Prompt "Contrasena inicial para el usuario DOCENTE" -AsSecureString
$AlumnoSecure  = Read-Host -Prompt "Contrasena inicial para el usuario ALUMNO" -AsSecureString
$env:DOCENTE_PASSWORD = ConvertFrom-SecureStringPlano -Secreto $DocenteSecure
$env:ALUMNO_PASSWORD  = ConvertFrom-SecureStringPlano -Secreto $AlumnoSecure

# ==============================================================================
# 6. Verificacion de las seis variables obligatorias
# ==============================================================================
$VariablesObligatorias = @("JAVA_HOME", "INFLUX_URL", "INFLUX_TOKEN", "JWT_SECRET", "DOCENTE_PASSWORD", "ALUMNO_PASSWORD")
$Faltantes = @()
foreach ($nombre in $VariablesObligatorias) {
    $valor = [Environment]::GetEnvironmentVariable($nombre)
    if ([string]::IsNullOrWhiteSpace($valor)) {
        $Faltantes += $nombre
    }
}

if ($Faltantes.Count -gt 0) {
    Write-Host "ERROR: faltan variables obligatorias: $($Faltantes -join ', '). Abortando sin levantar nada." -ForegroundColor Red
    Write-Host "Revisa infra\.env (debe definir INFLUX_TOKEN) y volve a correr el script." -ForegroundColor Red
    exit 1
}
Write-Host "OK: las seis variables obligatorias estan definidas (JAVA_HOME, INFLUX_URL, INFLUX_TOKEN, JWT_SECRET, DOCENTE_PASSWORD, ALUMNO_PASSWORD)." -ForegroundColor Green
Write-Host ""

# ==============================================================================
# 7. docker compose (InfluxDB, Grafana, Mosquitto, Nginx) desde infra/
# ==============================================================================
Write-Host "Levantando docker compose desde infra\..." -ForegroundColor Cyan
Push-Location $InfraDir
try {
    docker compose up -d
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: 'docker compose up -d' termino con codigo $LASTEXITCODE." -ForegroundColor Red
        exit 1
    }
} finally {
    Pop-Location
}

Write-Host "Esperando a que InfluxDB responda en $($env:INFLUX_URL)/health (hasta $SegundosEsperaInflux s)..."
$influxListo = $false
$intentos = [Math]::Max(1, [Math]::Ceiling($SegundosEsperaInflux / 2))
for ($i = 0; $i -lt $intentos; $i++) {
    try {
        $resp = Invoke-WebRequest -Uri "$($env:INFLUX_URL)/health" -UseBasicParsing -TimeoutSec 2
        if ($resp.StatusCode -eq 200) {
            $influxListo = $true
            break
        }
    } catch {
        # Todavia no esta arriba; se reintenta.
    }
    Start-Sleep -Seconds 2
}
if ($influxListo) {
    Write-Host "InfluxDB listo." -ForegroundColor Green
} else {
    Write-Host "AVISO: InfluxDB no respondio dentro del tiempo de espera. Se continua igual; revisa 'docker compose logs' en infra\ si algo falla." -ForegroundColor Yellow
}
Write-Host ""

# ==============================================================================
# 8. Bridge en una ventana separada (edge/bridge.py --source sim [--flow-serial ...])
# ==============================================================================
$PythonExe = Join-Path $EdgeDir ".venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    $PythonExe = "python"
}

if ($SinCaudal) {
    $ArgsBridge = @("bridge.py", "--source", "sim")
} else {
    $ArgsBridge = @("bridge.py", "--source", "sim", "--flow-serial", $PuertoCaudal, "--baudrate", "$BaudrateCaudal")
}

$ComandoBridge = "Set-Location -LiteralPath '$EdgeDir'; & '$PythonExe' $($ArgsBridge -join ' ')"
Write-Host "Abriendo el bridge en una ventana nueva..." -ForegroundColor Cyan
Start-Process -FilePath "powershell.exe" -ArgumentList @("-NoExit", "-Command", $ComandoBridge)

# ==============================================================================
# 9. Backend Spring Boot en perfil prod en una ventana separada
# ==============================================================================
$ComandoBackend = "Set-Location -LiteralPath '$BackendDir'; mvn spring-boot:run '-Dspring-boot.run.profiles=prod'"
Write-Host "Abriendo el backend (perfil prod) en una ventana nueva..." -ForegroundColor Cyan
Start-Process -FilePath "powershell.exe" -ArgumentList @("-NoExit", "-Command", $ComandoBackend)

Write-Host ""
Write-Host "=== Demo iniciada ===" -ForegroundColor Green
Write-Host "Web     : http://localhost/"
Write-Host "Grafana : http://localhost/grafana"
Write-Host "Bomba real: SIEMPRE MANUAL. El boton de la web solo controla la bomba simulada."
if (-not $SinCaudal) {
    Write-Host "Caudal real: Arduino Uno conectado por USB en $PuertoCaudal (MODO_SIM_SIN_SENSORES 0)."
}
Write-Host "Las dos ventanas nuevas (bridge y backend) quedan abiertas; cerralas para detener la demo."
