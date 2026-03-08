# ============================================================
# Eventenergie Portal - Windows 11 Setup Script
# Server: 217.86.214.29
# PowerShell als Administrator ausfuehren!
# ============================================================

param(
    [string]$InstallDir = "C:\eventenergie",
    [string]$Domain = "portal.eventenergie-deutschland.de"
)

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Eventenergie Portal - Setup" -ForegroundColor Cyan
Write-Host " Zielverzeichnis: $InstallDir" -ForegroundColor Cyan
Write-Host " Domain: $Domain" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# ---------------------------------------------------
# 1. Voraussetzungen pruefen
# ---------------------------------------------------
Write-Host "`n[1/8] Voraussetzungen pruefen..." -ForegroundColor Yellow

$checks = @(
    @{ Name = "Python"; Cmd = "python --version" },
    @{ Name = "Node.js"; Cmd = "node --version" },
    @{ Name = "Yarn"; Cmd = "yarn --version" },
    @{ Name = "Git"; Cmd = "git --version" },
    @{ Name = "MongoDB"; Cmd = "mongod --version" }
)

foreach ($check in $checks) {
    try {
        $result = Invoke-Expression $check.Cmd 2>&1
        Write-Host "  OK: $($check.Name) - $result" -ForegroundColor Green
    } catch {
        Write-Host "  FEHLT: $($check.Name) - Bitte zuerst installieren!" -ForegroundColor Red
        Write-Host "  Siehe INSTALLATIONSANLEITUNG.md" -ForegroundColor Red
        exit 1
    }
}

# Caddy pruefen
if (Test-Path "C:\Caddy\caddy.exe") {
    Write-Host "  OK: Caddy gefunden" -ForegroundColor Green
} else {
    Write-Host "  FEHLT: C:\Caddy\caddy.exe - Bitte Caddy herunterladen!" -ForegroundColor Red
    exit 1
}

# NSSM pruefen
if (Test-Path "C:\nssm\nssm.exe") {
    Write-Host "  OK: NSSM gefunden" -ForegroundColor Green
} else {
    Write-Host "  FEHLT: C:\nssm\nssm.exe - Bitte NSSM herunterladen!" -ForegroundColor Red
    exit 1
}

# ---------------------------------------------------
# 2. Verzeichnisse erstellen
# ---------------------------------------------------
Write-Host "`n[2/8] Verzeichnisse erstellen..." -ForegroundColor Yellow

$dirs = @("$InstallDir", "$InstallDir\logs", "$InstallDir\backups", "$InstallDir\storage")
foreach ($dir in $dirs) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Host "  Erstellt: $dir" -ForegroundColor Green
    }
}

# ---------------------------------------------------
# 3. Code kopieren / klonen
# ---------------------------------------------------
Write-Host "`n[3/8] Anwendung kopieren..." -ForegroundColor Yellow

# Wenn Git-Repo vorhanden, klonen. Sonst manuell kopieren.
if (Test-Path "$InstallDir\backend\server.py") {
    Write-Host "  Anwendung bereits vorhanden, ueberspringe..." -ForegroundColor Gray
} else {
    Write-Host "  HINWEIS: Bitte den Anwendungscode nach $InstallDir kopieren." -ForegroundColor Yellow
    Write-Host "  Struktur: $InstallDir\backend\ und $InstallDir\frontend\" -ForegroundColor Yellow
    Write-Host "  Dann dieses Skript erneut ausfuehren." -ForegroundColor Yellow
    
    # Erstelle Platzhalter-Verzeichnisse
    New-Item -ItemType Directory -Path "$InstallDir\backend" -Force | Out-Null
    New-Item -ItemType Directory -Path "$InstallDir\frontend" -Force | Out-Null
}

# ---------------------------------------------------
# 4. Backend einrichten
# ---------------------------------------------------
Write-Host "`n[4/8] Backend einrichten..." -ForegroundColor Yellow

if (Test-Path "$InstallDir\backend\requirements.txt") {
    Push-Location "$InstallDir\backend"
    
    # Virtuelle Umgebung erstellen
    if (-not (Test-Path "venv")) {
        Write-Host "  Python venv erstellen..." -ForegroundColor Gray
        python -m venv venv
    }
    
    # Pakete installieren
    Write-Host "  Python-Pakete installieren..." -ForegroundColor Gray
    & ".\venv\Scripts\pip.exe" install -r requirements.txt --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/ 2>&1 | Out-Null
    Write-Host "  OK: Backend-Pakete installiert" -ForegroundColor Green
    
    # .env erstellen falls nicht vorhanden
    if (-not (Test-Path ".env")) {
        Write-Host "  .env Template erstellt - BITTE ANPASSEN!" -ForegroundColor Yellow
        Copy-Item "$InstallDir\deployment\env.backend.template" ".env" -ErrorAction SilentlyContinue
    }
    
    Pop-Location
} else {
    Write-Host "  Backend-Code noch nicht vorhanden, ueberspringe..." -ForegroundColor Gray
}

# ---------------------------------------------------
# 5. Frontend einrichten
# ---------------------------------------------------
Write-Host "`n[5/8] Frontend einrichten..." -ForegroundColor Yellow

if (Test-Path "$InstallDir\frontend\package.json") {
    Push-Location "$InstallDir\frontend"
    
    # Pakete installieren
    Write-Host "  Node-Pakete installieren..." -ForegroundColor Gray
    yarn install 2>&1 | Out-Null
    
    # .env erstellen
    if (-not (Test-Path ".env")) {
        "REACT_APP_BACKEND_URL=https://$Domain" | Out-File -Encoding utf8 ".env"
    }
    
    # Production Build erstellen
    Write-Host "  Frontend Build erstellen (dauert 1-2 Minuten)..." -ForegroundColor Gray
    yarn build 2>&1 | Out-Null
    Write-Host "  OK: Frontend Build erstellt" -ForegroundColor Green
    
    Pop-Location
} else {
    Write-Host "  Frontend-Code noch nicht vorhanden, ueberspringe..." -ForegroundColor Gray
}

# ---------------------------------------------------
# 6. Caddy konfigurieren
# ---------------------------------------------------
Write-Host "`n[6/8] Caddy (Reverse Proxy) konfigurieren..." -ForegroundColor Yellow

$caddyfile = @"
$Domain {
    # API-Anfragen an Backend weiterleiten
    handle /api/* {
        reverse_proxy localhost:8001
    }
    
    # Statische Dateien (Uploads, Dokumente)
    handle /static/* {
        reverse_proxy localhost:8001
    }
    handle /storage/* {
        root * $($InstallDir -replace '\\','/')
        file_server
    }

    # Frontend (React Build)
    handle {
        root * $($InstallDir -replace '\\','/')/frontend/build
        try_files {path} /index.html
        file_server
    }
}
"@

$caddyfile | Out-File -Encoding utf8 "C:\Caddy\Caddyfile"
Write-Host "  OK: Caddyfile erstellt unter C:\Caddy\Caddyfile" -ForegroundColor Green

# ---------------------------------------------------
# 7. Windows-Dienste registrieren
# ---------------------------------------------------
Write-Host "`n[7/8] Windows-Dienste registrieren..." -ForegroundColor Yellow

$nssm = "C:\nssm\nssm.exe"

# Backend-Dienst
$backendExists = Get-Service -Name "eventenergie-backend" -ErrorAction SilentlyContinue
if (-not $backendExists) {
    & $nssm install eventenergie-backend "$InstallDir\backend\venv\Scripts\python.exe"
    & $nssm set eventenergie-backend AppParameters "-m uvicorn server:app --host 0.0.0.0 --port 8001"
    & $nssm set eventenergie-backend AppDirectory "$InstallDir\backend"
    & $nssm set eventenergie-backend AppStdout "$InstallDir\logs\backend.log"
    & $nssm set eventenergie-backend AppStderr "$InstallDir\logs\backend.err.log"
    & $nssm set eventenergie-backend AppRotateFiles 1
    & $nssm set eventenergie-backend AppRotateBytes 10485760
    & $nssm set eventenergie-backend Description "Eventenergie Portal Backend (FastAPI)"
    & $nssm set eventenergie-backend Start SERVICE_AUTO_START
    Write-Host "  OK: Backend-Dienst registriert" -ForegroundColor Green
} else {
    Write-Host "  Backend-Dienst existiert bereits" -ForegroundColor Gray
}

# Caddy-Dienst
$caddyExists = Get-Service -Name "eventenergie-caddy" -ErrorAction SilentlyContinue
if (-not $caddyExists) {
    & $nssm install eventenergie-caddy "C:\Caddy\caddy.exe"
    & $nssm set eventenergie-caddy AppParameters "run --config C:\Caddy\Caddyfile"
    & $nssm set eventenergie-caddy AppDirectory "C:\Caddy"
    & $nssm set eventenergie-caddy AppStdout "$InstallDir\logs\caddy.log"
    & $nssm set eventenergie-caddy AppStderr "$InstallDir\logs\caddy.err.log"
    & $nssm set eventenergie-caddy AppRotateFiles 1
    & $nssm set eventenergie-caddy AppRotateBytes 10485760
    & $nssm set eventenergie-caddy Description "Eventenergie Caddy Reverse Proxy (HTTPS)"
    & $nssm set eventenergie-caddy Start SERVICE_AUTO_START
    Write-Host "  OK: Caddy-Dienst registriert" -ForegroundColor Green
} else {
    Write-Host "  Caddy-Dienst existiert bereits" -ForegroundColor Gray
}

# ---------------------------------------------------
# 8. Firewall-Regeln
# ---------------------------------------------------
Write-Host "`n[8/8] Firewall-Regeln setzen..." -ForegroundColor Yellow

$rules = @(
    @{ Name = "Eventenergie HTTPS (443)"; Port = 443 },
    @{ Name = "Eventenergie HTTP (80)"; Port = 80 }
)

foreach ($rule in $rules) {
    $exists = Get-NetFirewallRule -DisplayName $rule.Name -ErrorAction SilentlyContinue
    if (-not $exists) {
        New-NetFirewallRule -DisplayName $rule.Name -Direction Inbound -Protocol TCP -LocalPort $rule.Port -Action Allow | Out-Null
        Write-Host "  OK: Firewall-Regel '$($rule.Name)' erstellt" -ForegroundColor Green
    } else {
        Write-Host "  Firewall-Regel '$($rule.Name)' existiert bereits" -ForegroundColor Gray
    }
}

# ---------------------------------------------------
# Fertig
# ---------------------------------------------------
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host " Setup abgeschlossen!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Naechste Schritte:" -ForegroundColor Yellow
Write-Host "  1. Anwendungscode nach $InstallDir\backend und $InstallDir\frontend kopieren"
Write-Host "  2. $InstallDir\backend\.env anpassen (siehe env.backend.template)"
Write-Host "  3. Frontend Build: cd $InstallDir\frontend && yarn install && yarn build"
Write-Host "  4. DNS: $Domain -> A-Record -> 217.86.214.29"
Write-Host "  5. Dienste starten:"
Write-Host "     Start-Service eventenergie-backend"
Write-Host "     Start-Service eventenergie-caddy"
Write-Host "  6. Im Browser oeffnen: https://$Domain"
Write-Host ""
