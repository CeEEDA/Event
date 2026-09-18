# Eventenergie Portal – Update & Betrieb (Live-Server Windows)

## Aktuelles Setup (Stand 2026-09-18)

Der Live-Server läuft komplett über **NSSM-Windows-Services**:

| Service | Zweck | Port |
|---------|-------|------|
| `EventenergieBackend` | FastAPI/uvicorn | 8002 (nur lokal) |
| `EventenergieCaddy`   | Caddy 2 Reverse-Proxy + Let's-Encrypt-SSL | 80 + 443 |
| `MongoDB`             | Datenbank | 27017 |
| `Mosquitto` (optional)| MQTT-Broker | 1883 |

**Wichtig:** Backend wird NIE mehr manuell mit `uvicorn` gestartet, sondern immer über `Start-Service` / `Restart-Service`. Sonst gibt es Port-Konflikte (Errno 10048).

## Update-Ablauf (empfohlen)

### Automatisch – ein Klick

1. **`update.bat` doppelklicken** (Rechtsklick → "Als Administrator ausführen")
2. Skript läuft komplett durch:
   - `.env` gesichert
   - `git pull origin Main_0.9APP`
   - Python-Pakete via pip installiert
   - Frontend gebaut (`yarn build`)
   - Backend-Service neu gestartet
   - Health-Check am Ende
3. Am Ende: Status-Zeile Backend/Frontend + Log-Datei

Die Datei `update.bat` ist nur ein dünner Wrapper – die Logik steckt in `update-live.ps1`.

### Manuell – für spezifische Fälle

```powershell
# Nur Backend updaten (Frontend überspringen)
powershell -File C:\eventenergie\update-live.ps1 -SkipFrontend

# Nur Frontend updaten (Backend-Service nicht anfassen)
powershell -File C:\eventenergie\update-live.ps1 -SkipBackend

# Auch Caddy neu starten (nur nötig wenn Caddyfile verändert)
powershell -File C:\eventenergie\update-live.ps1 -RestartCaddy
```

## Services verwalten (ohne Update)

```powershell
# Status aller Services
Get-Service EventenergieBackend, EventenergieCaddy, MongoDB

# Backend neu starten (z.B. nach .env-Aenderung)
Restart-Service EventenergieBackend

# Backend-Logs live
& "C:\ProgramData\chocolatey\lib\NSSM\tools\nssm.exe" get EventenergieBackend AppStderr
# → Pfad kopieren, dann:
Get-Content "<pfad>" -Wait -Tail 50
```

## Geschützte Dateien (werden NIE überschrieben)

- `backend\.env` – Datenbank, SMTP, JWT-Secret, Stripe-Keys, ...
- `frontend\.env` – Portal-URL
- MongoDB-Daten – komplett unberührt
- `node_modules` – wird nur ergänzt
- `C:\caddy\Caddyfile` – Caddy-Config (liegt bewusst außerhalb des Repos)

## Zertifikat / SSL

Caddy holt und erneuert das Let's-Encrypt-Zertifikat **automatisch**:
- Neu-Ausstellung: einmalig beim ersten Start (~15-30 Sek.)
- Erneuerung: automatisch ~30 Tage vor Ablauf
- Voraussetzung: Port 80 tcp muss extern erreichbar sein (Router-Port-Forwarding)

Zertifikat prüfen:
```powershell
curl.exe -vI https://www.eventenergie.app 2>&1 | Select-String "issuer|expire"
# Erwartet: issuer: Let's Encrypt (nicht Sectigo/IONOS)
```

## Backup-System

Automatische Backups laufen im Backend:
- Datenbank-Backup via `mongodump` alle 12 Stunden
- Quellcode-Backup als ZIP alle 3 Tage
- Aufbewahrung: 7 Tage
- Konfiguration: Admin → Einstellungen → Backup-System

Backup-Speicherort: `C:\eventenergie\backups\`

Datenbank wiederherstellen:
```
mongorestore --uri="mongodb://localhost:27017" --db=eventenergie ^
             --archive=PFAD_ZUM_BACKUP.gz --gzip --drop
```

## Verzeichnisstruktur

```
C:\eventenergie\               ← Git-Repo Root
  backend\                     ← FastAPI Server
    .env                       ← DB, SMTP, JWT (nicht im Git)
    server.py
    routes\
    ...
  frontend\
    .env                       ← REACT_APP_BACKEND_URL (nicht im Git)
    build\                     ← Von Caddy statisch ausgeliefert
    src\
  backups\
  update-live.ps1              ← Update-Logik
  update.bat                   ← Doppelklick-Wrapper
  logs\update-*.log

C:\caddy\                      ← Caddy-Installation (getrennt vom Repo)
  caddy.exe
  Caddyfile                    ← Produktions-Config

C:\ProgramData\chocolatey\lib\NSSM\tools\nssm.exe  ← Service-Manager
```

## Fehlerbehebung

### Update-Skript bricht mit Fehler ab
1. Log anschauen: `Get-Content C:\eventenergie\logs\update-*.log -Tail 50` (neueste Datei)
2. Services-Status: `Get-Service EventenergieBackend, EventenergieCaddy`

### Backend startet nach Update nicht
1. NSSM-Log: `& "C:\ProgramData\chocolatey\lib\NSSM\tools\nssm.exe" get EventenergieBackend AppStderr` → Pfad → `Get-Content <pfad> -Tail 50`
2. Häufigste Ursachen:
   - Neue Python-Dependency fehlt → `pip install -r backend\requirements.txt` manuell
   - `.env` fehlt → aus `.env.backup` wiederherstellen
   - MongoDB down → `Start-Service MongoDB`

### Frontend zeigt alte Version (Caching)
- Browser: `Strg+Shift+R` (Hard-Reload)
- Prüfen ob `build\index.html` das neue Datum hat

### Portal komplett nicht erreichbar (Extern)
1. `Get-Service EventenergieCaddy` → sollte Running sein
2. `netstat -ano | findstr /R ":80 :443"` → Caddy-PID sollte beide halten
3. `curl.exe -I https://www.eventenergie.app` von einem Handy im 4G-Netz testen
4. Router-Port-Forwarding 80+443 prüfen
