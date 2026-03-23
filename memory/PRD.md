# Eventenergie Portal - PRD

## Original Problem Statement
Umfassendes "Kirmes" (Jahrmarkt) Abrechnungssystem mit Tankbeleg-Digitalisierung, Auftragsverwaltung, Energiemonitoring, Zahlungsabwicklung und mehr.

## Core Architecture
- **Frontend:** React (CRA) + Tailwind CSS + Shadcn/UI
- **Backend:** FastAPI (Python) + MongoDB + GridFS
- **Desktop:** Electron Wrapper
- **External APIs:** EpiRent (ERP), Stripe (Payments), MQTT, OpenStreetMap
- **Server:** Nginx (HTTPS/443) -> Caddy (HTTP/8001) -> FastAPI (8002)

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

### Start/Update/Stop Scripts (ueberarbeitet - 2026-02)
- start-all.bat mit robuster Port-Pruefung via CALL :check_port Subroutine
- goto-Loops statt for/l (Backend: 20s, Caddy: 12s, Nginx: 8s)
- Klare Zusammenfassung [OK]/[XX]/[--] mit Dienste-Zaehler
- CRLF-Zeilenumbrueche, Deployment-Kopie synchronisiert
- stop-all.bat, update.bat, start_services.bat, stop_services.bat

### Nginx HTTPS Setup (abgeschlossen - 2026-02)
- Nginx fuer TLS-Terminierung auf Port 443
- SSL-Zertifikat (fullchain.pem) generiert
- Caddy nur noch HTTP (Port 8001)
- Mosquitto MQTT als Windows-Service konfiguriert

### Device Management Expandable Rows (abgeschlossen)
- Expandable rows in DeviceManagementPage.js
- /api/devices/stats/quick/{device_id} Endpoint

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

### P0 - Benutzer-Aktion erforderlich
- Port 443 Portfreigabe im Router fuer externen HTTPS-Zugriff
- start-all.bat auf Windows Server testen

### P1 - Kommend
- PayPal Integration
- Direkter QR-Label-Druck an Drucker

### P2 - Backlog
- Chromium Translate Popup auf Raspberry Pi (Policy-Datei erstellen)
- Admin File Size Limits fuer Uploads
- Windows Installer (.exe) fuer Electron Desktop App

## Credentials
- **Admin (lokal):** admin@test.com / password
- **Admin (Server):** christian.ecker@eventenergie-deutschland.de / qivbeb-Wodha1-sewram
