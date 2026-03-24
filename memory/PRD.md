# Eventenergie Portal - PRD

## Original Problem Statement
Umfassendes "Kirmes" (Jahrmarkt) Abrechnungssystem mit Tankbeleg-Digitalisierung, Auftragsverwaltung, Energiemonitoring, Zahlungsabwicklung und mehr.

## Core Architecture
- **Frontend:** React (CRA) + Tailwind CSS + Shadcn/UI
- **Backend:** FastAPI (Python) + MongoDB + GridFS
- **Desktop:** Electron Wrapper
- **External APIs:** EpiRent (ERP), Stripe (Payments), MQTT, OpenStreetMap
- **Server:** nginx (HTTPS/443) -> Caddy (HTTP/8001) -> FastAPI (8002)
- **Firewall:** FortiGate VIP (static-nat, extern 443 -> 172.20.80.5:443)

## Network Architecture
```
Internet -> DNS (eventenergie.app -> 217.86.214.29)
         -> FortiGate VIP (static-nat, Port 443 -> 172.20.80.5:443)
         -> nginx (SSL/TLS auf Port 443)
         -> Caddy (HTTP auf Port 8001)
         -> FastAPI (Backend auf Port 8002)
         -> MongoDB (Port 27017)
```

## FortiGate Konfiguration
- wan1 IP: 192.168.0.128 (DHCP, hinter Router)
- Server VLAN: VLAN80_VPN-Strm (172.20.80.x)
- Admin VLAN: VLAN100_Admin (172.20.100.x)
- WLAN VLAN: VLAN110_WLAN (172.20.110.x)
- Server VLAN: VLAN200_Server (172.20.200.x)
- WICHTIG: wan1 allowaccess darf NICHT https enthalten (sonst fängt FortiGate Port 443 ab)
- VIP Rule 142: EEG_Portal HTTPS2, static-nat, extern 443 -> 172.20.80.5:443

## What's Been Implemented

### Phase 1 - Portal Grundfunktionen (abgeschlossen)
- Auth, Auftragsverwaltung, Energiemonitoring, Zahlungen, QR, Rechnungen, Admin, Desktop

### Phase 1b - Tankbeleg Portal UI (abgeschlossen)
- CRUD, PDF, Auto-Nummerierung, GPS-Karte, Admin-Funktionen

### Phase 1c - EpiRent API Optimierung (abgeschlossen)
- Background-Sync, Cache, Manueller Sync, Adress-Ueberschreibung

### Phase 2 - Tankbeleg Pi Script (abgeschlossen)
- ESC/POS Parser, Serial, GPS, SQLite, Auto-Sync, 48 Tests

### Self-Hosted MQTT Broker (abgeschlossen)
- Mosquitto + Let's Encrypt TLS, 3 Listener

### Serviceplan Anpassungen (abgeschlossen)
- Messkoffer/Kirmeskiste: Reduzierter Plan, PDF + Bilder Upload (max 25 MB)

### Artikel positionieren - Status & Detail (abgeschlossen - 2026-03-19)
- Zeilen-Farbe, Abgebaut-Button, Detail-Modal mit OSM-Karte, PATCH Toggle-Endpoint

### Server Deployment Tools (abgeschlossen - 2026-03-20)
- Safe Update-Paket Export, Caddy Reverse Proxy, .env Templates, Hardcoded Fallback URL

### Backup-System (abgeschlossen - 2026-03-20)
- DB-Backup via mongodump (gzip), Quellcode-Backup (ZIP)
- Konfigurierbares Intervall, Aufbewahrungsrichtlinie, Manuelles Backup
- Admin UI mit Toggles, Intervall-Inputs, Backup-Liste
- Hintergrund-Scheduler (15 Min Pruefintervall)

### Start/Update/Stop Scripts (Fix - 2026-03-23)
- Root Cause: Deutsches Windows gibt "ABHOEREN" statt "LISTENING" in netstat
- Fix: Locale-unabhaengige Port-Erkennung via findstr "0.0.0.0:PORT" + for /f
- Ergebnis: Alle Dienste korrekt erkannt [3/3] - Backend, Caddy, nginx, Mosquitto
- CRLF-Zeilenumbrueche, [XX] statt [!!] (delayed expansion Bug), goto-Loops statt for/l

### HTTPS/SSL Externer Zugang (abgeschlossen - 2026-03-24)
- nginx fuer TLS-Terminierung auf Port 443
- DNS A-Record auf 217.86.214.29 konfiguriert
- Windows Firewall Regel fuer Port 443
- FortiGate VIP (static-nat) konfiguriert: extern 443 -> 172.20.80.5:443
- FortiGate wan1 allowaccess: https ENTFERNT (damit VIP Port 443 durchlaesst)
- FortiGate Recovery nach Aussperrung via Console + Factory Reset + Backup Restore
- Portal extern erreichbar unter https://eventenergie.app

## Key API Endpoints
- `/api/backup/settings` - GET/POST Backup-Einstellungen
- `/api/backup/list` - GET Backup-Liste
- `/api/backup/trigger/db` - POST DB-Backup ausloesen
- `/api/backup/trigger/files` - POST Dateien-Backup ausloesen
- `/api/backup/{id}` - DELETE Backup loeschen
- `/api/backup/{id}/download` - GET Backup herunterladen
- `/api/download/update-package` - GET Update-Paket ZIP
- `/api/devices/stats/quick/{device_id}` - GET Telemetrie-Daten

## Prioritized Backlog

### P1 - Kommend
- PayPal Integration
- Direkter QR-Label-Druck an Drucker

### P2 - Backlog
- Chromium Translate Popup auf Raspberry Pi (Policy-Datei erstellen)
- Admin File Size Limits fuer Uploads
- Windows Installer (.exe) fuer Electron Desktop App
- Health-Check / Monitoring fuer Portal-Erreichbarkeit

## Credentials
- Admin (lokal): admin@test.com / password
- Admin (Server): christian.ecker@eventenergie-deutschland.de / qivbeb-Wodha1-sewram
- SMTP: portal@eventenergie.app / :PlN4sFf:}6AY (smtp.ionos.de, Port 465)

## Known Issues (resolved)
- FortiGate wan1 allowaccess hatte https aktiv -> FortiGate Admin fing Port 443 ab statt VIP
- Deutsches Windows: netstat gibt ABHOEREN statt LISTENING aus
- Batch Script: delayed expansion !! wird als leere Variable interpretiert
