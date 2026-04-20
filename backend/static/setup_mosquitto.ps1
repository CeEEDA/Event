# =====================================================
# Mosquitto MQTT Broker - Setup Script
# Eventenergie Deutschland GmbH & Co. KG
# =====================================================
# Ausführen als Administrator:
#   Rechtsklick → "Mit PowerShell ausführen"  (als Admin)
# Oder in PowerShell als Admin:
#   Set-ExecutionPolicy -Scope Process Bypass -Force
#   .\setup_mosquitto.ps1
# =====================================================

#Requires -RunAsAdministrator

$ErrorActionPreference = "Stop"

$ConfPath       = "C:\Program Files\Mosquitto\mosquitto.conf"
$PasswdPath     = "C:\eventenergie\mosquitto_passwd"
$LogPath        = "C:\eventenergie\mosquitto.log"
$PersistenceDir = "C:\eventenergie"
$ServiceName    = "mosquitto"

Write-Host "=== Mosquitto Setup gestartet ===" -ForegroundColor Cyan

# 1) Zielverzeichnis sicherstellen
if (-not (Test-Path $PersistenceDir)) {
    Write-Host "Erstelle Verzeichnis $PersistenceDir" -ForegroundColor Yellow
    New-Item -ItemType Directory -Path $PersistenceDir -Force | Out-Null
}

# 2) Passwd-Datei anlegen falls sie noch nicht existiert (leer)
if (-not (Test-Path $PasswdPath)) {
    Write-Host "Erstelle leere Passwd-Datei $PasswdPath" -ForegroundColor Yellow
    New-Item -ItemType File -Path $PasswdPath -Force | Out-Null
} else {
    Write-Host "Passwd-Datei vorhanden: $PasswdPath" -ForegroundColor Green
}

# 3) Bestehende mosquitto.conf sichern
if (Test-Path $ConfPath) {
    $Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $BackupPath = "$ConfPath.backup_$Timestamp"
    Copy-Item $ConfPath $BackupPath -Force
    Write-Host "Backup erstellt: $BackupPath" -ForegroundColor Green
}

# 4) Neue mosquitto.conf schreiben
$NewConf = @"
# =====================================================
# Mosquitto MQTT Broker - Eventenergie Deutschland GmbH
# Automatisch generiert durch setup_mosquitto.ps1
# =====================================================

# --- Globale Settings ---
per_listener_settings true

# --- Persistenz ---
persistence true
persistence_location C:/eventenergie/
persistence_file mosquitto.db

# --- Logging ---
log_dest file C:/eventenergie/mosquitto.log
log_type error
log_type warning
log_type notice
log_type information
connection_messages true
log_timestamp true

# --- Listener 1: MQTTS (TLS) - Port 8883 ---
listener 8883 0.0.0.0
protocol mqtt
allow_anonymous false
password_file C:/eventenergie/mosquitto_passwd
certfile C:/eventenergie/ssl/www.eventenergie.app_ssl_certificate.cer
keyfile C:/eventenergie/ssl/www.eventenergie.app_private_key.key
tls_version tlsv1.2

# --- Listener 2: MQTT ohne TLS - Port 1883 ---
listener 1883 0.0.0.0
protocol mqtt
allow_anonymous false
password_file C:/eventenergie/mosquitto_passwd

# --- Listener 3: Lokal ohne Auth - Port 1884 ---
listener 1884 127.0.0.1
protocol mqtt
allow_anonymous true
"@

Set-Content -Path $ConfPath -Value $NewConf -Encoding ASCII
Write-Host "Neue mosquitto.conf geschrieben: $ConfPath" -ForegroundColor Green

# 5) Firewall-Regeln prüfen/ergänzen
foreach ($Port in 1883, 8883) {
    $RuleName = "Mosquitto MQTT $Port"
    $Existing = Get-NetFirewallRule -DisplayName $RuleName -ErrorAction SilentlyContinue
    if (-not $Existing) {
        Write-Host "Firewall-Regel für Port $Port hinzufügen" -ForegroundColor Yellow
        New-NetFirewallRule -DisplayName $RuleName `
            -Direction Inbound -Protocol TCP -LocalPort $Port -Action Allow | Out-Null
    } else {
        Write-Host "Firewall-Regel $Port bereits vorhanden" -ForegroundColor Green
    }
}

# 6) Service neu starten
Write-Host "Starte $ServiceName Service neu..." -ForegroundColor Cyan
try {
    Restart-Service -Name $ServiceName -Force
    Start-Sleep -Seconds 2
    $svc = Get-Service -Name $ServiceName
    if ($svc.Status -eq "Running") {
        Write-Host "✓ Service läuft" -ForegroundColor Green
    } else {
        Write-Host "⚠ Service hat Status: $($svc.Status)" -ForegroundColor Red
    }
} catch {
    Write-Host "⚠ Service-Restart fehlgeschlagen: $_" -ForegroundColor Red
    Write-Host "  → Service evtl. nicht als Windows-Dienst installiert." -ForegroundColor Yellow
    Write-Host "  → Installation: 'C:\Program Files\Mosquitto\mosquitto.exe' install" -ForegroundColor Yellow
}

# 7) Status und Ports zeigen
Write-Host ""
Write-Host "=== Prüfung ===" -ForegroundColor Cyan
$Listening = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
    Where-Object { $_.LocalPort -in 1883, 8883, 1884 } |
    Select-Object LocalAddress, LocalPort, State
if ($Listening) {
    $Listening | Format-Table -AutoSize
} else {
    Write-Host "⚠ Keine Mosquitto-Ports (1883/8883/1884) lauschen!" -ForegroundColor Red
    Write-Host "  → Prüfe: Get-Content '$LogPath' -Tail 50" -ForegroundColor Yellow
}

# 8) Passwd-Datei-Inhalt anzeigen (Usernames)
Write-Host ""
Write-Host "=== Mosquitto Passwd-Datei ===" -ForegroundColor Cyan
if (Test-Path $PasswdPath) {
    $Users = Get-Content $PasswdPath | ForEach-Object { ($_ -split ':')[0] } | Where-Object { $_ }
    Write-Host "$($Users.Count) Einträge:"
    $Users | ForEach-Object { Write-Host "  • $_" }
} else {
    Write-Host "⚠ Keine Passwd-Datei gefunden" -ForegroundColor Red
}

# 9) Live-Log anbieten
Write-Host ""
Write-Host "=== Fertig ===" -ForegroundColor Green
Write-Host ""
Write-Host "Live-Log verfolgen mit:" -ForegroundColor Cyan
Write-Host "  Get-Content '$LogPath' -Wait -Tail 50" -ForegroundColor White
Write-Host ""
$answer = Read-Host "Jetzt Live-Log starten? (j/N)"
if ($answer -eq "j" -or $answer -eq "J") {
    Write-Host "Tail startet... (Strg+C zum Beenden)" -ForegroundColor Yellow
    Start-Sleep -Seconds 1
    Get-Content $LogPath -Wait -Tail 50
}
