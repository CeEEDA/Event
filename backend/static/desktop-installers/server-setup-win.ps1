# ============================================================================
#  Eventenergie Portal - Windows Server 2019 Installation
#  PowerShell als Administrator ausfuehren:
#    powershell -ExecutionPolicy Bypass -File server-setup-win.ps1
# ============================================================================

$ErrorActionPreference = "Stop"
$APP_DIR = "C:\eventenergie"
$DATA_DIR = "C:\eventenergie\data"
$DB_NAME = "eventenergie"
$DOMAIN = "eventenergie.app"
$NSSM_URL = "https://nssm.cc/release/nssm-2.24.zip"

# Farben
function Write-Step($num, $total, $msg) { Write-Host "[$num/$total] $msg" -ForegroundColor Yellow }
function Write-Ok($msg) { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "  [!] $msg" -ForegroundColor Yellow }

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  Eventenergie Portal - Windows Server Setup" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# Admin-Check
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "Bitte als Administrator ausfuehren!" -ForegroundColor Red
    exit 1
}

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

# ── 1. Chocolatey (Paketmanager) ────────────────────────────────────────────
Write-Step 1 8 "Chocolatey Paketmanager..."
$chocoExists = $null
try { $chocoExists = Get-Command choco -ErrorAction SilentlyContinue } catch {}

if (-not $chocoExists) {
    Write-Host "     Installiere Chocolatey..." -ForegroundColor Gray
    Set-ExecutionPolicy Bypass -Scope Process -Force
    [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
    Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
    # Refresh PATH
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
}
Write-Ok "Chocolatey bereit"

# ── 2. Node.js 20 LTS ──────────────────────────────────────────────────────
Write-Step 2 8 "Node.js 20 LTS..."
$nodeExists = $null
try { $nodeExists = Get-Command node -ErrorAction SilentlyContinue } catch {}

if (-not $nodeExists) {
    & choco install nodejs-lts -y --no-progress 2>&1 | Out-Null
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
}
$nodeVer = & node --version 2>$null
Write-Ok "Node.js $nodeVer"

# Yarn
$yarnExists = $null
try { $yarnExists = Get-Command yarn -ErrorAction SilentlyContinue } catch {}
if (-not $yarnExists) {
    & npm install -g yarn 2>&1 | Out-Null
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
}
Write-Ok "Yarn bereit"

# ── 3. Python 3.11 ─────────────────────────────────────────────────────────
Write-Step 3 8 "Python 3.11..."
$pyExists = $null
try { $pyExists = Get-Command python -ErrorAction SilentlyContinue } catch {}

if (-not $pyExists) {
    & choco install python311 -y --no-progress 2>&1 | Out-Null
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
}
$pyVer = & python --version 2>$null
Write-Ok "Python $pyVer"

# ── 4. MongoDB 7 ────────────────────────────────────────────────────────────
Write-Step 4 8 "MongoDB 7..."
$mongoService = Get-Service "MongoDB" -ErrorAction SilentlyContinue

if (-not $mongoService) {
    Write-Host "     Installiere MongoDB..." -ForegroundColor Gray
    & choco install mongodb -y --no-progress 2>&1 | Out-Null
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    
    # MongoDB als Service starten
    $mongoService = Get-Service "MongoDB" -ErrorAction SilentlyContinue
    if ($mongoService -and $mongoService.Status -ne "Running") {
        Start-Service "MongoDB"
    }
}

# MongoDB Database Tools (fuer mongodump/mongorestore)
$mongodumpExists = $null
try { $mongodumpExists = Get-Command mongodump -ErrorAction SilentlyContinue } catch {}
if (-not $mongodumpExists) {
    & choco install mongodb-database-tools -y --no-progress 2>&1 | Out-Null
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
}
Write-Ok "MongoDB bereit (Service: $(Get-Service 'MongoDB' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Status))"

# ── 5. Caddy (Reverse Proxy) ───────────────────────────────────────────────
Write-Step 5 8 "Caddy Reverse Proxy..."
$caddyDir = "C:\caddy"
$caddyExe = "$caddyDir\caddy.exe"

if (-not (Test-Path $caddyExe)) {
    Write-Host "     Installiere Caddy..." -ForegroundColor Gray
    New-Item -ItemType Directory -Path $caddyDir -Force | Out-Null
    
    # Download latest Caddy for Windows
    $caddyUrl = "https://caddyserver.com/api/download?os=windows&arch=amd64"
    Invoke-WebRequest -Uri $caddyUrl -OutFile $caddyExe -UseBasicParsing
}
Write-Ok "Caddy installiert: $caddyExe"

# ── 6. NSSM (Service Manager) ──────────────────────────────────────────────
Write-Step 6 8 "NSSM Service Manager..."
$nssmExists = $null
try { $nssmExists = Get-Command nssm -ErrorAction SilentlyContinue } catch {}

if (-not $nssmExists) {
    & choco install nssm -y --no-progress 2>&1 | Out-Null
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
}
Write-Ok "NSSM bereit"

# ── 7. Mosquitto MQTT Broker ───────────────────────────────────────────────
Write-Step 7 8 "Mosquitto MQTT Broker..."
$mqttService = Get-Service "Mosquitto Broker" -ErrorAction SilentlyContinue

if (-not $mqttService) {
    & choco install mosquitto -y --no-progress 2>&1 | Out-Null
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
}
Write-Ok "Mosquitto bereit"

# ── 8. Verzeichnisse & Konfiguration ───────────────────────────────────────
Write-Step 8 8 "Verzeichnisse und Konfiguration..."

# App-Verzeichnisse
foreach ($dir in @("$APP_DIR", "$APP_DIR\backend", "$APP_DIR\frontend", "$DATA_DIR", "$DATA_DIR\Dokumentenablage", "$DATA_DIR\backups")) {
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
}

# Python Virtual Environment
if (-not (Test-Path "$APP_DIR\venv")) {
    & python -m venv "$APP_DIR\venv"
}

# Caddyfile
$caddyfileContent = @"
{
    auto_https off
}

https://$DOMAIN {
    tls internal
    handle /api/* {
        reverse_proxy localhost:8002
    }
    handle {
        root * $APP_DIR\frontend\build
        try_files {path} /index.html
        file_server
    }
}

:8001 {
    handle /api/* {
        reverse_proxy localhost:8002
    }
    handle {
        root * $APP_DIR\frontend\build
        try_files {path} /index.html
        file_server
    }
}
"@
Set-Content -Path "$caddyDir\Caddyfile" -Value $caddyfileContent -Encoding UTF8
Write-Ok "Caddyfile erstellt: $caddyDir\Caddyfile"

# ── Windows Services mit NSSM einrichten ────────────────────────────────────
Write-Host ""
Write-Host "Services einrichten..." -ForegroundColor Yellow

# Backend Service
$backendService = Get-Service "EventenergieBackend" -ErrorAction SilentlyContinue
if (-not $backendService) {
    $uvicornPath = "$APP_DIR\venv\Scripts\uvicorn.exe"
    & nssm install EventenergieBackend $uvicornPath "server:app --host 0.0.0.0 --port 8002 --workers 2" 2>$null
    & nssm set EventenergieBackend AppDirectory "$APP_DIR\backend" 2>$null
    & nssm set EventenergieBackend DisplayName "Eventenergie Backend" 2>$null
    & nssm set EventenergieBackend Description "FastAPI Backend Server" 2>$null
    & nssm set EventenergieBackend Start SERVICE_AUTO_START 2>$null
    & nssm set EventenergieBackend AppStdout "$APP_DIR\logs\backend-out.log" 2>$null
    & nssm set EventenergieBackend AppStderr "$APP_DIR\logs\backend-err.log" 2>$null
    New-Item -ItemType Directory -Path "$APP_DIR\logs" -Force | Out-Null
    Write-Ok "Backend-Service 'EventenergieBackend' erstellt"
} else {
    Write-Ok "Backend-Service existiert bereits"
}

# Caddy Service
$caddyService = Get-Service "EventenergieCaddy" -ErrorAction SilentlyContinue
if (-not $caddyService) {
    & nssm install EventenergieCaddy $caddyExe "run --config $caddyDir\Caddyfile" 2>$null
    & nssm set EventenergieCaddy DisplayName "Eventenergie Caddy" 2>$null
    & nssm set EventenergieCaddy Description "Caddy Reverse Proxy" 2>$null
    & nssm set EventenergieCaddy Start SERVICE_AUTO_START 2>$null
    Write-Ok "Caddy-Service 'EventenergieCaddy' erstellt"
} else {
    Write-Ok "Caddy-Service existiert bereits"
}

# ── Firewall ────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "Firewall-Regeln..." -ForegroundColor Yellow

$rules = @(
    @{Name="Eventenergie HTTP";   Port=80;   Protocol="TCP"},
    @{Name="Eventenergie HTTPS";  Port=443;  Protocol="TCP"},
    @{Name="Eventenergie Caddy";  Port=8001; Protocol="TCP"},
    @{Name="Eventenergie Backend";Port=8002; Protocol="TCP"},
    @{Name="Eventenergie MQTT";   Port=1883; Protocol="TCP"}
)
foreach ($rule in $rules) {
    $existing = Get-NetFirewallRule -DisplayName $rule.Name -ErrorAction SilentlyContinue
    if (-not $existing) {
        New-NetFirewallRule -DisplayName $rule.Name -Direction Inbound -Action Allow -Protocol $rule.Protocol -LocalPort $rule.Port | Out-Null
    }
}
Write-Ok "Firewall-Regeln aktiv (80, 443, 8001, 8002, 1883)"

# ── Zusammenfassung ─────────────────────────────────────────────────────────
Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  Server-Installation abgeschlossen!" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Installierte Software:" -ForegroundColor White
Write-Host "    Node.js     : $(node --version 2>$null)" -ForegroundColor Gray
Write-Host "    Python      : $(python --version 2>$null)" -ForegroundColor Gray
Write-Host "    MongoDB     : $(Get-Service 'MongoDB' -EA 0 | Select -Exp Status)" -ForegroundColor Gray
Write-Host "    Caddy       : $caddyExe" -ForegroundColor Gray
Write-Host "    Mosquitto   : $(Get-Service 'Mosquitto*' -EA 0 | Select -First 1 -Exp Status)" -ForegroundColor Gray
Write-Host "    NSSM        : Service Manager" -ForegroundColor Gray
Write-Host ""
Write-Host "  Verzeichnisse:" -ForegroundColor White
Write-Host "    App:         $APP_DIR" -ForegroundColor Gray
Write-Host "    Backend:     $APP_DIR\backend" -ForegroundColor Gray
Write-Host "    Frontend:    $APP_DIR\frontend" -ForegroundColor Gray
Write-Host "    Daten:       $DATA_DIR" -ForegroundColor Gray
Write-Host "    Dokumente:   $DATA_DIR\Dokumentenablage" -ForegroundColor Gray
Write-Host "    Logs:        $APP_DIR\logs" -ForegroundColor Gray
Write-Host ""
Write-Host "  Windows Services:" -ForegroundColor White
Write-Host "    EventenergieBackend  (Port 8002)" -ForegroundColor Gray
Write-Host "    EventenergieCaddy    (Port 8001, 443)" -ForegroundColor Gray
Write-Host "    MongoDB              (Port 27017)" -ForegroundColor Gray
Write-Host "    Mosquitto Broker     (Port 1883)" -ForegroundColor Gray
Write-Host ""
Write-Host "  Naechste Schritte:" -ForegroundColor White
Write-Host "    1. Code deployen:    .\deploy-win.ps1" -ForegroundColor Gray
Write-Host "    2. Datenbank laden:  .\db-migrate-win.ps1 import backup.gz" -ForegroundColor Gray
Write-Host "    3. .env anpassen:    notepad $APP_DIR\backend\.env" -ForegroundColor Gray
Write-Host "    4. Services starten: Start-Service EventenergieBackend, EventenergieCaddy" -ForegroundColor Gray
Write-Host "    5. DNS eintragen:    $DOMAIN -> Server-IP" -ForegroundColor Gray
Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan

Read-Host "Druecken Sie Enter zum Beenden"
