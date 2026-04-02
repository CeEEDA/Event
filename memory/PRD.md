# Eventenergie Portal - PRD

## Original Problem Statement
Umfassendes "Kirmes" (Jahrmarkt) Abrechnungssystem mit Tankbeleg-Digitalisierung, Auftragsverwaltung, Energiemonitoring, Zahlungsabwicklung und mehr.

## Core Architecture
- **Frontend:** React (CRA) + Tailwind CSS + Shadcn/UI
- **Backend:** FastAPI (Python) + MongoDB + GridFS
- **Desktop:** Electron Wrapper
- **External APIs:** EpiRent (ERP), Stripe (Payments), MQTT, OpenStreetMap
- **Server:** nginx (HTTPS/443) -> Caddy (HTTP/8001) -> FastAPI (8002)

## What's Been Implemented

### Phase 1-2 (abgeschlossen)
- Auth, Auftragsverwaltung, Energiemonitoring, Zahlungen, QR, Rechnungen, Admin, Desktop
- Tankbeleg Portal + Pi Script, EpiRent API Sync
- MQTT Broker, Serviceplan, Server Deployment, Backup-System, HTTPS/SSL

### Kirmes Billing Features (abgeschlossen)
- EMU Meter kW Fix, BCC auf Rechnungs-Emails
- Auto-Fill Ausbau kWh, L1/L2/L3 Phasen-Anzeige
- GiroCode QR-Code Fix, 1-Seiten PDF Layout
- Auto-Kundennummer (K-0001), Finance Dashboard
- Event-level Zahlungsart Toggle, 1-Click Email-Einladung/-Verifizierung
- Mehrfachanmeldungen, Smartphone-Optimierung

### DSE Generator Features (abgeschlossen)
- DSE 5510 via RS232 + Pi, Remote Control, Sentinel-Wert Fix
- Control Panel Redesign, Event-Log, Offline-Erkennung

### Performance-Optimierung (abgeschlossen - 2026-04-02)
- **MongoDB Indexes**: 25+ Indexes auf alle kritischen Collections
- **N+1 Query Fix**: 5 Endpoints optimiert (batch statt serial):
  - `GET /kirmes/events` — Signup-Counts via Aggregation
  - `GET /kirmes/events/{id}` — Schausteller per $in-Query
  - `GET /devices` — Dokument-Counts via Aggregation
  - `GET /generators` — Telemetrie+Devices+Plans per Batch
  - `GET /energy-monitoring/devices` — Meter-Counts+Latest per Aggregation
- API-Antwortzeiten: 30+ Sek -> unter 200ms

## Key API Endpoints
- `/api/kirmes/events/{event_id}/generate-invoices`
- `/api/kirmes/public/verify-email-link`
- `/api/kirmes/public/register`
- `/api/devices`, `/api/generators`
- `/api/energy-monitoring/devices`

## Prioritized Backlog

### P1 - Kommend
- PayPal Integration

### P2 - Backlog
- Diagnose-Feature fuer Zaehler (letzte 10 Rohwerte)
- Chromium Translate Popup auf Raspberry Pi
- Admin File Size Limits fuer Uploads
- Windows Installer fuer Electron Desktop App

## Credentials
- Admin (lokal): admin@test.com / password
- Admin (Server): christian.ecker@eventenergie-deutschland.de / qivbeb-Wodha1-sewram
- SMTP: portal@eventenergie.app / :PlN4sFf:}6AY (smtp.ionos.de, Port 465)
