# ========================================
#  Eventenergie Portal - Windows Setup
# ========================================
$ErrorActionPreference = "Stop"

$INSTALL_DIR = "C:\eventenergie"
$DOMAIN = "portal.eventenergie-deutschland.de"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Eventenergie Portal - Setup" -ForegroundColor Cyan
Write-Host " Zielverzeichnis: $INSTALL_DIR" -ForegroundColor Cyan
Write-Host " Domain: $DOMAIN" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ── 1/8: Voraussetzungen pruefen ──
Write-Host "[1/8] Voraussetzungen pruefen..." -ForegroundColor Yellow

$allOk = $true

# Python
try {
    $pyVer = & python --version 2>&1
    Write-Host "  OK: Python - $pyVer" -ForegroundColor Green
} catch {
    Write-Host "  FEHLT: Python - Bitte Python 3.11+ installieren!" -ForegroundColor Red
    $allOk = $false
}

# Node.js
try {
    $nodeVer = & node --version 2>&1
    Write-Host "  OK: Node.js - $nodeVer" -ForegroundColor Green
} catch {
    Write-Host "  FEHLT: Node.js - Bitte Node.js 18+ installieren!" -ForegroundColor Red
    $allOk = $false
}

# Yarn
try {
    $yarnVer = & yarn --version 2>&1
    Write-Host "  OK: Yarn - $yarnVer" -ForegroundColor Green
} catch {
    Write-Host "  FEHLT: Yarn - Bitte 'npm install -g yarn' ausfuehren!" -ForegroundColor Red
    $allOk = $false
}

# Git
try {
    $gitVer = & git --version 2>&1
    Write-Host "  OK: Git - $gitVer" -ForegroundColor Green
} catch {
    Write-Host "  FEHLT: Git - Bitte Git installieren!" -ForegroundColor Red
    $allOk = $false
}

# MongoDB - Erweiterte Suche
$mongoFound = $false
$mongodPath = $null

# 1. Im PATH suchen
try {
    $mongoVer = & mongod --version 2>&1 | Select-String "db version"
    if ($mongoVer) {
        $mongodPath = (Get-Command mongod).Source
        $mongoFound = $true
        Write-Host "  OK: MongoDB - $mongoVer (PATH)" -ForegroundColor Green
    }
} catch { }

# 2. Standard-Installationspfade durchsuchen
if (-not $mongoFound) {
    $searchPaths = @(
        "C:\Program Files\MongoDB\Server\*\bin\mongod.exe",
        "C:\Program Files (x86)\MongoDB\Server\*\bin\mongod.exe",
        "C:\MongoDB\Server\*\bin\mongod.exe",
        "C:\MongoDB\bin\mongod.exe"
    )
    foreach ($pattern in $searchPaths) {
        $found = Get-Item $pattern -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -First 1
        if ($found) {
            $mongodPath = $found.FullName
            $mongoVer = & $mongodPath --version 2>&1 | Select-String "db version"
            $mongoFound = $true
            Write-Host "  OK: MongoDB - $mongoVer" -ForegroundColor Green
            Write-Host "      Pfad: $mongodPath" -ForegroundColor DarkGray
            Write-Host "      HINWEIS: MongoDB ist nicht im PATH. Wird automatisch konfiguriert." -ForegroundColor DarkYellow
            break
        }
    }
}

# 3. Windows-Dienst pruefen
if (-not $mongoFound) {
    $mongoService = Get-Service -Name "MongoDB" -ErrorAction SilentlyContinue
    if (-not $mongoService) {
        $mongoService = Get-Service | Where-Object { $_.DisplayName -like "*MongoDB*" -or $_.Name -like "*mongo*" } | Select-Object -First 1
    }
    if ($mongoService) {
        $mongoFound = $true
        Write-Host "  OK: MongoDB - Dienst gefunden: $($mongoService.DisplayName) (Status: $($mongoService.Status))" -ForegroundColor Green
        # Dienstpfad extrahieren
        $svcPath = (Get-WmiObject win32_service | Where-Object { $_.Name -eq $mongoService.Name }).PathName
        if ($svcPath -match '"([^"]+mongod\.exe)"') {
            $mongodPath = $Matches[1]
            Write-Host "      Pfad: $mongodPath" -ForegroundColor DarkGray
        }
        if ($mongoService.Status -ne "Running") {
            Write-Host "      WARNUNG: MongoDB-Dienst ist nicht gestartet! Bitte starten: Start-Service $($mongoService.Name)" -ForegroundColor Yellow
        }
    }
}

# 4. Registry pruefen
if (-not $mongoFound) {
    $regPaths = @(
        "HKLM:\SOFTWARE\MongoDB\Server\*",
        "HKLM:\SOFTWARE\WOW6432Node\MongoDB\Server\*"
    )
    foreach ($rp in $regPaths) {
        $regEntry = Get-ItemProperty $rp -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($regEntry -and $regEntry.InstallDir) {
            $testPath = Join-Path $regEntry.InstallDir "bin\mongod.exe"
            if (Test-Path $testPath) {
                $mongodPath = $testPath
                $mongoFound = $true
                Write-Host "  OK: MongoDB - Gefunden via Registry" -ForegroundColor Green
                Write-Host "      Pfad: $mongodPath" -ForegroundColor DarkGray
                break
            }
        }
    }
}

if (-not $mongoFound) {
    Write-Host "  FEHLT: MongoDB - Konnte nicht gefunden werden!" -ForegroundColor Red
    Write-Host "      MongoDB wurde nicht im PATH, in Standardverzeichnissen," -ForegroundColor Red
    Write-Host "      als Windows-Dienst oder in der Registry gefunden." -ForegroundColor Red
    Write-Host "" -ForegroundColor Red
    Write-Host "      Bitte pruefen Sie:" -ForegroundColor Yellow
    Write-Host "      1. Ist MongoDB installiert? -> https://www.mongodb.com/try/download/community" -ForegroundColor Yellow
    Write-Host "      2. Falls ja, geben Sie den Pfad zu mongod.exe an:" -ForegroundColor Yellow
    Write-Host '         $env:MONGOD_PATH = "C:\Pfad\zu\mongod.exe"' -ForegroundColor Yellow
    Write-Host "      3. Dann fuehren Sie setup.ps1 erneut aus" -ForegroundColor Yellow
    $allOk = $false
}

# Manueller Pfad via Umgebungsvariable
if (-not $mongoFound -and $env:MONGOD_PATH -and (Test-Path $env:MONGOD_PATH)) {
    $mongodPath = $env:MONGOD_PATH
    $mongoFound = $true
    Write-Host "  OK: MongoDB - Manuell angegeben: $mongodPath" -ForegroundColor Green
}

if (-not $allOk) {
    Write-Host ""
    Write-Host "Setup abgebrochen - Bitte fehlende Software installieren." -ForegroundColor Red
    exit 1
}

Write-Host ""

# ── 2/8: Verzeichnisstruktur anlegen ──
Write-Host "[2/8] Verzeichnisstruktur anlegen..." -ForegroundColor Yellow

$dirs = @("$INSTALL_DIR", "$INSTALL_DIR\backend", "$INSTALL_DIR\frontend", "$INSTALL_DIR\storage\uploads", "$INSTALL_DIR\logs")
foreach ($d in $dirs) {
    if (-not (Test-Path $d)) {
        New-Item -ItemType Directory -Path $d -Force | Out-Null
        Write-Host "  Erstellt: $d" -ForegroundColor DarkGray
    }
}
Write-Host "  OK: Verzeichnisse bereit" -ForegroundColor Green
Write-Host ""

# ── 3/8: Dateien kopieren ──
Write-Host "[3/8] Dateien kopieren..." -ForegroundColor Yellow

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir

# Backend kopieren
Copy-Item -Path "$projectRoot\backend\*" -Destination "$INSTALL_DIR\backend\" -Recurse -Force
Write-Host "  OK: Backend kopiert" -ForegroundColor Green

# Frontend kopieren
Copy-Item -Path "$projectRoot\frontend\*" -Destination "$INSTALL_DIR\frontend\" -Recurse -Force
Write-Host "  OK: Frontend kopiert" -ForegroundColor Green
Write-Host ""

# ── 4/8: Backend-Abhaengigkeiten installieren ──
Write-Host "[4/8] Backend-Abhaengigkeiten installieren..." -ForegroundColor Yellow

Push-Location "$INSTALL_DIR\backend"
if (Test-Path "requirements.txt") {
    & python -m pip install -r requirements.txt --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/ --quiet 2>&1 | Out-Null
    Write-Host "  OK: Python-Pakete installiert" -ForegroundColor Green
} else {
    Write-Host "  WARNUNG: requirements.txt nicht gefunden" -ForegroundColor Yellow
}
Pop-Location
Write-Host ""

# ── 5/8: Frontend-Abhaengigkeiten installieren ──
Write-Host "[5/8] Frontend-Abhaengigkeiten installieren..." -ForegroundColor Yellow

Push-Location "$INSTALL_DIR\frontend"
& yarn install --silent 2>&1 | Out-Null
Write-Host "  OK: Node-Pakete installiert" -ForegroundColor Green
Pop-Location
Write-Host ""

# ── 6/8: Frontend bauen ──
Write-Host "[6/8] Frontend bauen (kann einige Minuten dauern)..." -ForegroundColor Yellow

Push-Location "$INSTALL_DIR\frontend"
$env:REACT_APP_BACKEND_URL = "https://$DOMAIN"
& yarn build 2>&1 | Out-Null
Write-Host "  OK: Frontend-Build abgeschlossen" -ForegroundColor Green
Pop-Location
Write-Host ""

# ── 7/8: Umgebungsvariablen konfigurieren ──
Write-Host "[7/8] Umgebungsvariablen pruefen..." -ForegroundColor Yellow

$backendEnv = "$INSTALL_DIR\backend\.env"
if (Test-Path $backendEnv) {
    Write-Host "  OK: backend\.env vorhanden" -ForegroundColor Green
} else {
    Write-Host "  WARNUNG: backend\.env nicht gefunden - bitte manuell anlegen!" -ForegroundColor Yellow
    Write-Host "  Vorlage: backend\.env.example" -ForegroundColor DarkGray
}
Write-Host ""

# ── 8/8: Windows-Dienste einrichten ──
Write-Host "[8/8] Start-Skripte erstellen..." -ForegroundColor Yellow

# Backend Start-Skript
$backendStart = @"
@echo off
cd /d $INSTALL_DIR\backend
python -m uvicorn server:app --host 0.0.0.0 --port 8001
"@
Set-Content -Path "$INSTALL_DIR\start-backend.bat" -Value $backendStart

# Frontend Start-Skript (serve static build)
$frontendStart = @"
@echo off
cd /d $INSTALL_DIR\frontend
npx serve -s build -l 3000
"@
Set-Content -Path "$INSTALL_DIR\start-frontend.bat" -Value $frontendStart

# Kombiniertes Start-Skript
$allStart = @"
@echo off
echo ========================================
echo  Eventenergie Portal wird gestartet...
echo ========================================
echo.
echo Backend wird gestartet (Port 8001)...
start "Eventenergie Backend" cmd /c "$INSTALL_DIR\start-backend.bat"
timeout /t 3 /nobreak >nul
echo Frontend wird gestartet (Port 3000)...
start "Eventenergie Frontend" cmd /c "$INSTALL_DIR\start-frontend.bat"
echo.
echo ========================================
echo  Portal laeuft!
echo  Backend:  http://localhost:8001
echo  Frontend: http://localhost:3000
echo ========================================
"@
Set-Content -Path "$INSTALL_DIR\start-all.bat" -Value $allStart

Write-Host "  OK: Start-Skripte erstellt" -ForegroundColor Green
Write-Host ""

# Fertig
Write-Host "========================================" -ForegroundColor Green
Write-Host " Setup abgeschlossen!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host " Starten: $INSTALL_DIR\start-all.bat" -ForegroundColor Cyan
Write-Host " Backend: http://localhost:8001" -ForegroundColor Cyan
Write-Host " Frontend: http://localhost:3000" -ForegroundColor Cyan
Write-Host ""
if ($mongodPath -and -not (Get-Command mongod -ErrorAction SilentlyContinue)) {
    $mongoBin = Split-Path $mongodPath
    Write-Host " TIPP: MongoDB zum PATH hinzufuegen:" -ForegroundColor Yellow
    Write-Host "   [Environment]::SetEnvironmentVariable('PATH', `$env:PATH + ';$mongoBin', 'Machine')" -ForegroundColor DarkGray
    Write-Host ""
}
