# ============================================================================
#  Eventenergie Portal - Mobile App Build
#  
#  Android APK:  .\build-mobile.ps1 android
#  iOS:          .\build-mobile.ps1 ios        (nur auf Mac)
#  Beide:        .\build-mobile.ps1 all        (nur auf Mac)
# ============================================================================

param(
    [Parameter(Position=0)]
    [ValidateSet("android", "ios", "all", "help")]
    [string]$Platform = "help"
)

$ErrorActionPreference = "Stop"
$FRONTEND_DIR = if (Test-Path ".\frontend") { ".\frontend" } elseif (Test-Path ".\package.json") { "." } else { "C:\eventenergie\frontend" }
$BACKEND_URL = "https://eventenergie.app"

function Show-Help {
    Write-Host ""
    Write-Host "Eventenergie Portal - Mobile App Builder" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  .\build-mobile.ps1 android    Android APK bauen" -ForegroundColor Gray
    Write-Host "  .\build-mobile.ps1 ios        iOS App bauen (nur Mac)" -ForegroundColor Gray
    Write-Host "  .\build-mobile.ps1 all        Beide bauen (nur Mac)" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Voraussetzungen:" -ForegroundColor Yellow
    Write-Host "  Android: Android Studio + JDK 17" -ForegroundColor Gray
    Write-Host "  iOS:     Xcode + CocoaPods (nur macOS)" -ForegroundColor Gray
    Write-Host ""
}

function Build-WebAssets {
    Write-Host "[..] React-App bauen..." -ForegroundColor Yellow
    Set-Location $FRONTEND_DIR
    
    $env:REACT_APP_BACKEND_URL = $BACKEND_URL
    & yarn build 2>&1 | Select-Object -Last 5
    
    Write-Host "[OK] Web-Assets gebaut" -ForegroundColor Green
}

function Sync-Capacitor {
    Write-Host "[..] Capacitor sync..." -ForegroundColor Yellow
    & npx cap sync 2>&1 | Select-Object -Last 5
    Write-Host "[OK] Native Projekte synchronisiert" -ForegroundColor Green
}

function Build-Android {
    Write-Host ""
    Write-Host "================================================" -ForegroundColor Cyan
    Write-Host "  Android APK bauen" -ForegroundColor Cyan
    Write-Host "================================================" -ForegroundColor Cyan
    Write-Host ""
    
    Build-WebAssets
    Sync-Capacitor
    
    Write-Host "[..] Android APK bauen..." -ForegroundColor Yellow
    Set-Location "$FRONTEND_DIR\android"
    
    # Gradle build
    if (Test-Path ".\gradlew.bat") {
        & .\gradlew.bat assembleRelease 2>&1 | Select-Object -Last 10
    } else {
        & .\gradlew assembleRelease 2>&1 | Select-Object -Last 10
    }
    
    # APK suchen
    $apk = Get-ChildItem -Path ".\app\build\outputs\apk" -Filter "*.apk" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
    
    if ($apk) {
        $desktop = [Environment]::GetFolderPath("Desktop")
        Copy-Item $apk.FullName -Destination "$desktop\EventenergiePortal.apk" -Force
        Write-Host ""
        Write-Host "[OK] APK erstellt!" -ForegroundColor Green
        Write-Host "     Desktop: EventenergiePortal.apk" -ForegroundColor Gray
        Write-Host "     Groesse: $([math]::Round($apk.Length / 1MB, 1)) MB" -ForegroundColor Gray
    } else {
        Write-Host "[!] APK nicht gefunden. Bitte Android Studio verwenden:" -ForegroundColor Yellow
        Write-Host "    npx cap open android" -ForegroundColor Gray
    }
}

function Build-iOS {
    Write-Host ""
    Write-Host "================================================" -ForegroundColor Cyan
    Write-Host "  iOS App bauen" -ForegroundColor Cyan
    Write-Host "================================================" -ForegroundColor Cyan
    Write-Host ""
    
    if ($env:OS -eq "Windows_NT") {
        Write-Host "[!] iOS-Apps koennen nur auf macOS gebaut werden." -ForegroundColor Red
        Write-Host "    Bitte auf einem Mac ausfuehren:" -ForegroundColor Gray
        Write-Host "    bash build-mobile.sh ios" -ForegroundColor Gray
        return
    }
    
    Build-WebAssets
    Sync-Capacitor
    
    Write-Host "[..] Xcode-Projekt oeffnen..." -ForegroundColor Yellow
    & npx cap open ios
    Write-Host ""
    Write-Host "[OK] Xcode geoeffnet. Dort:" -ForegroundColor Green
    Write-Host "     1. Signing-Zertifikat waehlen (Apple Developer Account)" -ForegroundColor Gray
    Write-Host "     2. Product → Archive" -ForegroundColor Gray
    Write-Host "     3. Distribute App → App Store / Ad Hoc" -ForegroundColor Gray
}

switch ($Platform) {
    "android" { Build-Android }
    "ios"     { Build-iOS }
    "all"     { Build-Android; Build-iOS }
    default   { Show-Help }
}

Write-Host ""
Read-Host "Druecken Sie Enter zum Beenden"
