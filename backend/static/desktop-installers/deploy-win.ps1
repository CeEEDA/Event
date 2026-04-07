# ============================================================================
#  Eventenergie Portal - Code Deployment (Windows Server)
#  PowerShell als Administrator:  .\deploy-win.ps1 [GIT-REPO-URL]
# ============================================================================

param(
    [Parameter(Position=0)]
    [string]$RepoUrl = ""
)

$ErrorActionPreference = "Stop"
$APP_DIR = "C:\eventenergie"
$DATA_DIR = "$APP_DIR\data"
$DOMAIN = "eventenergie.app"

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  Eventenergie Portal - Deployment" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# ── Code holen ──────────────────────────────────────────────────────────────
if ($RepoUrl) {
    Write-Host "[..] Code von Git laden..." -ForegroundColor Yellow
    $tempDir = Join-Path $env:TEMP "eventenergie-deploy-$(Get-Random)"
    & git clone $RepoUrl $tempDir 2>&1 | Select-Object -Last 3

    # Backend kopieren
    if (Test-Path "$tempDir\backend") {
        Copy-Item -Path "$tempDir\backend\*" -Destination "$APP_DIR\backend\" -Recurse -Force
    }
    # Frontend kopieren
    if (Test-Path "$tempDir\frontend") {
        Copy-Item -Path "$tempDir\frontend\*" -Destination "$APP_DIR\frontend\" -Recurse -Force
    }
    # Desktop-Dateien kopieren
    if (Test-Path "$tempDir\desktop") {
        New-Item -ItemType Directory -Path "$APP_DIR\desktop" -Force | Out-Null
        Copy-Item -Path "$tempDir\desktop\*" -Destination "$APP_DIR\desktop\" -Recurse -Force
    }

    Remove-Item $tempDir -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "[OK] Code deployed" -ForegroundColor Green
} else {
    if (-not (Test-Path "$APP_DIR\backend\server.py")) {
        Write-Host "Kein Code gefunden. Verwendung:" -ForegroundColor Red
        Write-Host "  .\deploy-win.ps1 https://github.com/USER/REPO.git" -ForegroundColor Yellow
        exit 1
    }
    Write-Host "[OK] Code bereits vorhanden, fahre mit Setup fort..." -ForegroundColor Green
}

# ── Backend Dependencies ────────────────────────────────────────────────────
Write-Host ""
Write-Host "[..] Backend Dependencies installieren..." -ForegroundColor Yellow
Set-Location "$APP_DIR\backend"

# Virtual Environment aktivieren
& "$APP_DIR\venv\Scripts\Activate.ps1"

& pip install --quiet -r requirements.txt 2>&1 | Select-Object -Last 3
& pip install --quiet emergentintegrations --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/ 2>&1 | Select-Object -Last 2

Write-Host "[OK] Backend Dependencies installiert" -ForegroundColor Green

# ── Backend .env ────────────────────────────────────────────────────────────
if (-not (Test-Path "$APP_DIR\backend\.env")) {
    Write-Host "[..] .env Template erstellen..." -ForegroundColor Yellow
    $envContent = @"
MONGO_URL="mongodb://localhost:27017"
DB_NAME="eventenergie"
CORS_ORIGINS="*"
JWT_SECRET="HIER-EIGENEN-KEY-EINTRAGEN"
SMTP_HOST=smtp.ionos.de
SMTP_PORT=465
SMTP_USER=portal@eventenergie.app
SMTP_PASSWORD=HIER-SMTP-PASSWORT
SMTP_SENDER_NAME=Eventenergie Portal
FRONTEND_URL=https://$DOMAIN
COMPANY_IBAN=DE72570928000221481704
COMPANY_BIC=GENODE51DIE
MOSQUITTO_PASSWD_FILE=
DYMO_PRINTER_NAME=DYMO LabelWriter 550
EMERGENT_LLM_KEY=HIER-EMERGENT-KEY
LOCAL_STORAGE_PATH=$DATA_DIR\Dokumentenablage
"@
    Set-Content -Path "$APP_DIR\backend\.env" -Value $envContent -Encoding UTF8
    Write-Host "[!] .env erstellt - BITTE ANPASSEN:" -ForegroundColor Yellow
    Write-Host "    notepad $APP_DIR\backend\.env" -ForegroundColor Gray
} else {
    Write-Host "[OK] .env bereits vorhanden" -ForegroundColor Green
}

# ── Frontend Build ──────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[..] Frontend bauen..." -ForegroundColor Yellow
Set-Location "$APP_DIR\frontend"

# Frontend .env
if (-not (Test-Path "$APP_DIR\frontend\.env")) {
    $frontendEnv = @"
REACT_APP_BACKEND_URL=https://$DOMAIN
WDS_SOCKET_PORT=443
"@
    Set-Content -Path "$APP_DIR\frontend\.env" -Value $frontendEnv -Encoding UTF8
}

& yarn install 2>&1 | Select-Object -Last 3
& yarn build 2>&1 | Select-Object -Last 5

Write-Host "[OK] Frontend gebaut" -ForegroundColor Green

# ── Desktop-Installer bereitstellen ─────────────────────────────────────────
if (Test-Path "$APP_DIR\desktop") {
    Write-Host ""
    Write-Host "[..] Desktop-Installer bereitstellen..." -ForegroundColor Yellow
    $installerDir = "$APP_DIR\backend\static\desktop-installers"
    New-Item -ItemType Directory -Path $installerDir -Force | Out-Null
    foreach ($f in @("install-mac.sh", "install-win.bat", "install-win.ps1", "server-setup-win.ps1", "db-migrate-win.ps1", "deploy-win.ps1")) {
        $src = "$APP_DIR\desktop\$f"
        if (Test-Path $src) { Copy-Item $src -Destination "$installerDir\$f" -Force }
    }
    Write-Host "[OK] Installer kopiert" -ForegroundColor Green
}

# ── Services neustarten ────────────────────────────────────────────────────
Write-Host ""
Write-Host "[..] Services neustarten..." -ForegroundColor Yellow

$services = @("EventenergieBackend", "EventenergieCaddy")
foreach ($svc in $services) {
    $s = Get-Service $svc -ErrorAction SilentlyContinue
    if ($s) {
        Restart-Service $svc -Force -ErrorAction SilentlyContinue
        Write-Host "  [OK] $svc neugestartet" -ForegroundColor Green
    } else {
        Write-Host "  [!] $svc nicht gefunden - bitte zuerst server-setup-win.ps1 ausfuehren" -ForegroundColor Yellow
    }
}

# ── Fertig ──────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  Deployment abgeschlossen!" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Checkliste:" -ForegroundColor White
Write-Host "    [ ] .env pruefen:     notepad $APP_DIR\backend\.env" -ForegroundColor Gray
Write-Host "    [ ] DNS pruefen:      $DOMAIN -> Server-IP" -ForegroundColor Gray
Write-Host "    [ ] Services pruefen: Get-Service Eventenergie*" -ForegroundColor Gray
Write-Host "    [ ] HTTPS testen:     https://$DOMAIN" -ForegroundColor Gray
Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan

Read-Host "Druecken Sie Enter zum Beenden"
