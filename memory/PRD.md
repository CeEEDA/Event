# Eventenergie Portal - PRD

## Original Problem Statement
Umfassendes "Kirmes" (Jahrmarkt) Abrechnungssystem mit Tankbeleg-Digitalisierung, Auftragsverwaltung, Energiemonitoring, Zahlungsabwicklung und mehr.

## Core Architecture
- **Frontend:** React (CRA) + Tailwind CSS + Shadcn/UI
- **Backend:** FastAPI (Python) + MongoDB + GridFS
- **Desktop:** Electron Wrapper
- **External APIs:** EpiRent (ERP), Stripe (Payments), MQTT, OpenStreetMap

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
- Hintergrund-Scheduler (15 Min Prüfintervall)

### Start/Update/Stop Scripts ueberarbeitet (abgeschlossen - 2026-03-20)
- **start-all.bat:** Stoppt alte Prozesse, MongoDB prüfen, DB-Backup beim Start, venv Support, Frontend Build prüfen, Backend + Caddy starten
- **stop-all.bat:** Stoppt Backend, Caddy und alle Portal-Prozesse (inkl. Port-Cleanup)
- **update.bat:** Auto-Erkennung des Update-Ordners, DB+Code-Backup, .env Schutz, Dependencies installieren, Build, automatischer Neustart
- **stop_services.bat / start_services.bat:** Aliase auf neue Scripts
- **deployment/start-all.bat + stop-all.bat:** Synchronisiert mit Hauptordner
- **UPDATE_ANLEITUNG.md:** Komplett ueberarbeitet mit allen neuen Features

## Key API Endpoints
- `/api/backup/settings` - GET/POST Backup-Einstellungen
- `/api/backup/list` - GET Backup-Liste
- `/api/backup/trigger/db` - POST DB-Backup ausloesen
- `/api/backup/trigger/files` - POST Dateien-Backup ausloesen
- `/api/backup/{id}` - DELETE Backup loeschen
- `/api/backup/{id}/download` - GET Backup herunterladen
- `/api/download/update-package` - GET Update-Paket ZIP

## Prioritized Backlog

### P1 - Kommend
- Live-Server Login-Fix (api.js Fallback deployen + npm run build)
- PayPal Integration
- Direkter QR-Label-Druck an Drucker
- Windows Installer (.exe) fuer Electron Desktop App

### P2 - Backlog
- Admin File Size Limits fuer Uploads

## Credentials
- **Admin (lokal):** admin@test.com / password
- **Admin (Server):** christian.ecker@eventenergie-deutschland.de / qivbeb-Wodha1-sewram
