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

### Artikel positionieren - Status & Detail (abgeschlossen)
- Zeilen-Farbe, Abgebaut-Button, Detail-Modal mit OSM-Karte, PATCH Toggle-Endpoint

### Server Deployment Tools (abgeschlossen)
- Safe Update-Paket Export, Caddy Reverse Proxy, .env Templates, Hardcoded Fallback URL

### Backup-System (abgeschlossen)
- DB-Backup via mongodump (gzip), Quellcode-Backup (ZIP)
- Konfigurierbares Intervall, Aufbewahrungsrichtlinie, Manuelles Backup

### HTTPS/SSL Externer Zugang (abgeschlossen)
- nginx fuer TLS-Terminierung auf Port 443
- Portal extern erreichbar unter https://eventenergie.app

### Kirmeskiste Pi Auto-Registrierung (abgeschlossen)
- Ingest-Endpoint registriert unbekannte Meter automatisch

### MQTT Gateway-Zugangsdaten pro Geraet (abgeschlossen)
- Jedes DSE-Gateway bekommt eigene MQTT-Credentials

### DSE 5510 via RS232 + Pi (abgeschlossen)
- Pi Sync-Skript, Telemetrie-Ingest, Steuerungsbefehle

### Kirmes Billing Features (abgeschlossen - 2026-04)
- EMU Meter kW Fix (Faktor 1000)
- BCC auf allen Rechnungs-Emails
- Auto-Fill Ausbau kWh bei Rechnungsgenerierung
- L1/L2/L3 Phasen-Anzeige (statt Summe)
- GiroCode QR-Code Fix
- 1-Seiten Rechnungs-PDF Layout
- Auto-Kundennummer (K-0001)
- Finance Dashboard
- Event-level Zahlungsart Toggle
- 1-Click Email-Einladung
- 1-Click Email-Verifizierung
- Mehrfachanmeldungen
- Smartphone-Optimierung Event-Detail

### MongoDB Performance Fix (abgeschlossen - 2026-04-02)
- P0: Portal war nicht erreichbar wegen fehlender MongoDB Indexes
- 25+ Indexes auf alle kritischen Collections angelegt (emu_data, devices, emu_meters, generators, generator_telemetry, kirmes_signups, kirmes_schausteller, kirmes_events, kirmes_invoices, users, etc.)
- API Antwortzeiten von 30+ Sek auf unter 200ms reduziert
- Indexes werden automatisch beim Server-Start erstellt (idempotent)

## Key API Endpoints
- `/api/kirmes/events/{event_id}/generate-invoices`: Auto-reads meters and bills
- `/api/kirmes/public/verify-email-link`: 1-click email confirmation
- `/api/kirmes/public/register`: Schausteller registration
- `/api/backup/settings` - GET/POST Backup-Einstellungen
- `/api/devices/stats/quick/{device_id}` - GET Telemetrie-Daten
- `/api/mqtt/control/{generator_id}` - POST Steuerbefehl senden

## Prioritized Backlog

### P1 - Kommend
- PayPal Integration

### P2 - Backlog
- Diagnose-Feature fuer Zaehler (letzte 10 Rohwerte anzeigen)
- Chromium Translate Popup auf Raspberry Pi (Policy-Datei erstellen)
- Admin File Size Limits fuer Uploads
- Windows Installer (.exe) fuer Electron Desktop App

## Credentials
- Admin (lokal): admin@test.com / password
- Admin (Server): christian.ecker@eventenergie-deutschland.de / qivbeb-Wodha1-sewram
- SMTP: portal@eventenergie.app / :PlN4sFf:}6AY (smtp.ionos.de, Port 465)

## Known Issues (resolved)
- MongoDB Performance: Fehlende Indexes auf Produktion -> Portal Timeout (Fixed 2026-04-02)
- FortiGate wan1 allowaccess hatte https aktiv
- Deutsches Windows: netstat gibt ABHOEREN statt LISTENING
- DSE Control-Endpoint KeyErrors
