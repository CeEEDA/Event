# =====================================================================
# Eventenergie Portal - Live-Server Update (NSSM-Service-basiert)
# =====================================================================
# Nutzt NSSM-Services (EventenergieBackend, EventenergieCaddy) statt
# manueller cmd-Fenster. Keine Port-Konflikte, keine verwaisten Prozesse.
#
# Verwendung: Rechtsklick -> "Mit PowerShell ausfuehren" (Als Admin!)
#             ODER: powershell -ExecutionPolicy Bypass -File update-live.ps1
# =====================================================================

param(
    [string]$LiveDir  = "C:\eventenergie",
    [string]$Branch   = "Main_0.9APP",
    [string]$RepoUrl  = "https://github.com/CeEEDA/Event.git",
    [switch]$SkipFrontend,
    [switch]$SkipBackend,
    [switch]$RestartCaddy
)

$ErrorActionPreference = "Continue"
$Global:LASTEXITCODE = 0

# ── Admin-Check ──────────────────────────────────────────────────────
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")
if (-not $isAdmin) {
    Write-Host "FEHLER: Bitte als Administrator ausfuehren!" -ForegroundColor Red
    Read-Host "ENTER zum Beenden"
    exit 1
}

$StartTime = Get-Date
$LogDir = Join-Path $LiveDir "logs"
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }
$LogFile = Join-Path $LogDir "update-$(Get-Date -Format 'yyyyMMdd_HHmmss').log"

function Log { param([string]$Msg, [string]$Color = "White")
    $Line = "[$(Get-Date -Format 'HH:mm:ss')] $Msg"
    Write-Host $Line -ForegroundColor $Color
    Add-Content -Path $LogFile -Value $Line -Encoding UTF8
}

Log "==================================================" "Cyan"
Log "  Eventenergie Portal - Live-Update ($Branch)"     "Cyan"
Log "==================================================" "Cyan"
Log "LiveDir: $LiveDir"
Log "LogFile: $LogFile"

if (-not (Test-Path $LiveDir)) {
    Log "FEHLER: $LiveDir nicht gefunden!" "Red"
    Read-Host "ENTER zum Beenden"
    exit 1
}
Set-Location $LiveDir

# =====================================================================
# 1) Services stoppen (nur die die wir gleich neu starten)
# =====================================================================
Log ""
Log "[1/6] NSSM-Services stoppen..." "Yellow"

$Services = @()
if (-not $SkipBackend) { $Services += "EventenergieBackend" }
if ($RestartCaddy)     { $Services += "EventenergieCaddy" }

foreach ($svc in $Services) {
    $s = Get-Service -Name $svc -ErrorAction SilentlyContinue
    if ($s) {
        if ($s.Status -eq "Running") {
            Log "  Stoppe $svc..."
            Stop-Service -Name $svc -Force -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 3
        } else {
            Log "  $svc bereits gestoppt"
        }
    } else {
        Log "  WARNUNG: Service $svc nicht installiert" "Yellow"
    }
}

# Verwaiste manuelle Prozesse killen (falls jemand uvicorn manuell laufen liess)
$OrphanedUvicorn = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -match "uvicorn.*server:app.*8002" -or $_.CommandLine -match "multiprocessing.spawn" }
foreach ($p in $OrphanedUvicorn) {
    Log "  Killt verwaisten Python-Prozess PID $($p.ProcessId)"
    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 2

# Harter Fallback: alles auf Port 8002 killen falls noch was hoert
$Port8002 = netstat -ano | Select-String ":8002\s.*ABH" | ForEach-Object {
    ($_ -split "\s+")[-1]
} | Where-Object { $_ -match "^\d+$" } | Sort-Object -Unique
foreach ($pid in $Port8002) {
    Log "  Killt verbliebenen Prozess auf Port 8002: PID $pid" "Yellow"
    Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 2

# =====================================================================
# 2) .env sichern
# =====================================================================
Log ""
Log "[2/6] .env Dateien sichern..." "Yellow"

$EnvFiles = @(
    (Join-Path $LiveDir "backend\.env"),
    (Join-Path $LiveDir "frontend\.env")
)
foreach ($env in $EnvFiles) {
    if (Test-Path $env) {
        Copy-Item -Path $env -Destination "$env.backup" -Force
        Log "  gesichert: $env"
    }
}

# =====================================================================
# 3) Git Pull
# =====================================================================
Log ""
Log "[3/6] Git Pull ($Branch)..." "Yellow"

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Log "FEHLER: Git ist nicht installiert!" "Red"
    Read-Host "ENTER zum Beenden"
    exit 1
}

if (-not (Test-Path (Join-Path $LiveDir ".git"))) {
    Log "  Kein Git-Repo - initialisiere..."
    git init 2>&1 | Tee-Object -FilePath $LogFile -Append
    git remote add origin $RepoUrl 2>&1 | Tee-Object -FilePath $LogFile -Append
}

git fetch --all 2>&1 | Tee-Object -FilePath $LogFile -Append
$currentBranch = (git branch --show-current).Trim()
if ($currentBranch -ne $Branch) {
    Log "  Wechsle von '$currentBranch' zu '$Branch'..."
    git checkout $Branch 2>&1 | Tee-Object -FilePath $LogFile -Append
}
git pull origin $Branch 2>&1 | Tee-Object -FilePath $LogFile -Append
if ($LASTEXITCODE -ne 0) {
    Log "  Pull-Konflikt - Hard-Reset auf origin/$Branch" "Yellow"
    git reset --hard "origin/$Branch" 2>&1 | Tee-Object -FilePath $LogFile -Append
}
Log "  Code aktualisiert"

# .env wiederherstellen falls durch git ueberschrieben
foreach ($env in $EnvFiles) {
    $backup = "$env.backup"
    if ((Test-Path $backup) -and (-not (Test-Path $env))) {
        Copy-Item -Path $backup -Destination $env -Force
        Log "  .env wiederhergestellt: $env" "Yellow"
    }
}

# =====================================================================
# 4) Python-Pakete
# =====================================================================
if (-not $SkipBackend) {
    Log ""
    Log "[4/6] Python-Pakete aktualisieren..." "Yellow"

    $BackendDir = Join-Path $LiveDir "backend"
    Set-Location $BackendDir

    $ReqFile = "requirements.txt"
    if (Test-Path (Join-Path $BackendDir "requirements-server.txt")) { $ReqFile = "requirements-server.txt" }

    $VenvActivate = $null
    if (Test-Path (Join-Path $LiveDir "venv\Scripts\Activate.ps1"))         { $VenvActivate = Join-Path $LiveDir "venv\Scripts\Activate.ps1" }
    elseif (Test-Path (Join-Path $BackendDir "venv\Scripts\Activate.ps1")) { $VenvActivate = Join-Path $BackendDir "venv\Scripts\Activate.ps1" }

    if ($VenvActivate) {
        Log "  venv: $VenvActivate"
        & $VenvActivate
        pip install -r $ReqFile --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/ 2>&1 | Tee-Object -FilePath $LogFile -Append
    } else {
        Log "  Kein venv - nutze System-Python" "Yellow"
        pip install -r $ReqFile --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/ 2>&1 | Tee-Object -FilePath $LogFile -Append
    }
    Log "  Python-Pakete OK"
} else {
    Log "[4/6] Backend uebersprungen (-SkipBackend)" "DarkGray"
}

# =====================================================================
# 5) Frontend Build
# =====================================================================
if (-not $SkipFrontend) {
    Log ""
    Log "[5/6] Frontend Build..." "Yellow"

    $FrontendDir = Join-Path $LiveDir "frontend"
    Set-Location $FrontendDir

    $env:GENERATE_SOURCEMAP = "false"
    $env:NODE_OPTIONS = "--max-old-space-size=8192"

    if (Get-Command yarn -ErrorAction SilentlyContinue) {
        Log "  yarn install..."
        yarn install --frozen-lockfile 2>&1 | Tee-Object -FilePath $LogFile -Append
        Log "  yarn build (kann 2-5 Min dauern)..."
        yarn build 2>&1 | Tee-Object -FilePath $LogFile -Append
    } else {
        Log "  WARNUNG: yarn nicht gefunden - nutze npm" "Yellow"
        npm install --legacy-peer-deps 2>&1 | Tee-Object -FilePath $LogFile -Append
        npm run build 2>&1 | Tee-Object -FilePath $LogFile -Append
    }

    if (Test-Path (Join-Path $FrontendDir "build\index.html")) {
        Log "  Build OK"
    } else {
        Log "  FEHLER: Build-Ordner leer!" "Red"
    }
} else {
    Log "[5/6] Frontend uebersprungen (-SkipFrontend)" "DarkGray"
}

# =====================================================================
# 6) Services starten & Health-Check
# =====================================================================
Log ""
Log "[6/6] NSSM-Services starten..." "Yellow"

foreach ($svc in $Services) {
    $s = Get-Service -Name $svc -ErrorAction SilentlyContinue
    if ($s) {
        Log "  Starte $svc..."
        Start-Service -Name $svc -ErrorAction SilentlyContinue
    }
}

# Health-Check nach 10s
Log ""
Log "Warte 10s auf Start..." "Yellow"
Start-Sleep -Seconds 10

$backendOk = $false
$frontendOk = $false
try {
    $r = Invoke-WebRequest -Uri "http://localhost:8002/api/health" -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
    $backendOk = ($r.StatusCode -eq 200 -or $r.StatusCode -eq 405)
} catch { $backendOk = $false }

try {
    $r = Invoke-WebRequest -Uri "https://www.eventenergie.app" -UseBasicParsing -TimeoutSec 10 -ErrorAction Stop
    $frontendOk = ($r.StatusCode -eq 200)
} catch { $frontendOk = $false }

$Duration = [math]::Round(((Get-Date) - $StartTime).TotalSeconds, 1)

Log ""
Log "==================================================" "Cyan"
Log "  Update-Ergebnis (Dauer: ${Duration}s)"           "Cyan"
Log "==================================================" "Cyan"
if ($backendOk)  { Log "  [OK] Backend  (localhost:8002)"           "Green" } else { Log "  [XX] Backend  antwortet NICHT"    "Red" }
if ($frontendOk) { Log "  [OK] Frontend (https://www.eventenergie.app)" "Green" } else { Log "  [XX] Frontend antwortet NICHT" "Red" }
Log ""
Log "  Log: $LogFile"
Log "  Bei Fehler:  Get-Content '$LogFile' -Tail 50"

Log ""
if (-not ($backendOk -and $frontendOk)) {
    Log "  Weitere Diagnose:" "Yellow"
    Log "    Get-Service EventenergieBackend, EventenergieCaddy"
    Log "    & 'C:\ProgramData\chocolatey\lib\NSSM\tools\nssm.exe' get EventenergieBackend AppStderr"
}

Read-Host "ENTER zum Beenden"
