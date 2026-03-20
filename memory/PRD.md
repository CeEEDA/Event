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
- Messkoffer/Kirmeskiste: Reduzierter Plan
- PDF + Bilder Upload (max 25 MB)

### Artikel positionieren - Status & Detail (abgeschlossen - 2026-03-19)
- Zeilen-Farbe: Magenta-Hintergrund wenn Artikel gestellt
- "Abgebaut"-Button: Toggle in jeder Zeile
- Detail-Modal mit OpenStreetMap-Karte
- Backend: PATCH Toggle-Endpoint

### Server Deployment Tools (abgeschlossen - 2026-03-20)
- Safe Update-Paket Export (ZIP ohne .env)
- Caddy Reverse Proxy Integration
- .env Templates und Konfigurationsdateien
- Hardcoded Fallback URL in api.js

### Backup-System (abgeschlossen - 2026-03-20)
- **Datenbank-Backup:** Automatisch via mongodump mit gzip-Komprimierung
- **Quellcode-Backup:** Automatisch als ZIP (ohne .env, node_modules)
- **Konfigurierbares Intervall:** DB (Standard: 12h), Dateien (Standard: 72h)
- **Aufbewahrungsrichtlinie:** Alte Backups automatisch löschen (Standard: 7 Tage)
- **Manuelles Backup:** Über Admin UI sofort auslösbar
- **Admin UI:** Neue Sektion in AdminSettingsPage mit Toggles, Intervall-Inputs, Backup-Liste
- **Hintergrund-Scheduler:** Prüft alle 15 Min ob Backup fällig
- **Backend:** /app/backend/routes/backup.py
- **API-Endpoints:** GET/POST /api/backup/settings, GET /api/backup/list, POST /api/backup/trigger/db, POST /api/backup/trigger/files, DELETE /api/backup/{id}, GET /api/backup/{id}/download

## Key API Endpoints
- `/api/orders/epirent/{pk}/assets` - GET/POST Assets
- `/api/orders/epirent/{pk}/assets/{id}/status` - PATCH Toggle Status
- `/api/fuel-receipts/sync` - Pi-Sync
- `/api/download/tankbeleg-pi-bundle` - Pi-Script ZIP
- `/api/download/mosquitto-bundle` - Mosquitto ZIP
- `/api/download/update-package` - Update-Paket ZIP
- `/api/backup/settings` - GET/POST Backup-Einstellungen
- `/api/backup/list` - GET Backup-Liste
- `/api/backup/trigger/db` - POST DB-Backup auslösen
- `/api/backup/trigger/files` - POST Dateien-Backup auslösen
- `/api/backup/{id}` - DELETE Backup löschen
- `/api/backup/{id}/download` - GET Backup herunterladen

## Prioritized Backlog

### P1 - Kommend
- Live-Server Login-Fix (api.js Fallback deployen + npm run build)
- PayPal Integration
- Direkter QR-Label-Druck an Drucker
- Windows Installer (.exe) fuer Electron Desktop App

### P2 - Backlog
- Admin File Size Limits fuer Uploads
- craco.config.js Cleanup (obsolete Kommentare entfernen)

## Credentials
- **Admin (lokal):** admin@test.com / password
- **Admin (Server):** christian.ecker@eventenergie-deutschland.de / qivbeb-Wodha1-sewram
