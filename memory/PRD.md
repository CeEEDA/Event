# Eventenergie Portal - PRD

## Original Problem Statement
Umfassendes "Kirmes" (Jahrmarkt) Abrechnungssystem mit Tankbeleg-Digitalisierung, Auftragsverwaltung, Energiemonitoring, Zahlungsabwicklung und mehr.

## Core Architecture
- **Frontend:** React (CRA) + Tailwind CSS + Shadcn/UI
- **Backend:** FastAPI (Python) + MongoDB + GridFS
- **Desktop:** Electron Wrapper
- **External APIs:** EpiRent (ERP), Stripe (Payments), MQTT, OpenStreetMap

## What's Been Implemented

### Performance-Optimierung
- MongoDB Indexes, N+1 Query Fix, RAM-Leak gefixt (25GB -> normal)

### Expanded Row Redesign (KirmesEventDetailPage)
- 3-Spalten Karten-Layout (KONTAKTDATEN | ZAEHLERDATEN | EMU-ZAEHLER)
- Gelbe Hinterlegung fuer nicht-verknuepfte Zaehler (bg-amber-50)
- Payment-Labels gefixt
- Lade-Delay gefixt (limit=1 auf meter-data API)

### Zaehler-Detailseite (MeterDiagnosticsPage) - NEU
- **Route**: /devices/:deviceId/meters/:meterId
- Datumsfilter, Verknuepfungshistorie, Messdaten-Tabelle, Anomalie-Erkennung

### Projektbericht (Digital Project Report) - NEU (2026-04-03)
- **Backend**: Full CRUD at /api/project-reports (create, list by order, get, update, delete)
- **Frontend Form**: /project-report/new and /project-report/:reportId
  - Kundendaten (auto-filled from order API)
  - Mitarbeiter (auto-filled from logged-in user, roles: PL/ME/T/H)
  - Arbeitsprotokoll (date, description, hours per employee x type N/E/NO)
  - Material / Artikel (pos, material, vorbereitung, verarbeitet, bestellung)
  - Fahrzeuge (PKW, LKW, etc. with KM and hours)
  - Bemerkungen + Uebernachtung
  - Digitale Unterschriften (Techniker + Kunde via react-signature-canvas)
- **Integration**: Projektberichte section in OrderDetailPage (similar to Tankbelege)
- **Testing**: 100% pass rate (11/11 backend, all frontend flows)

## Key API Endpoints
- GET /api/kirmes/signups/{signup_id}/meter-data?limit=1
- GET /api/devices/{device_id}/meters/{meter_id}/diagnostics
- GET /api/devices/{device_id}/meters/{meter_id}/history
- POST/GET/PUT/DELETE /api/project-reports
- GET /api/project-reports/by-order/{order_pk}
- POST/GET/PUT/DELETE /api/fuel-receipts

## Prioritized Backlog

### P1 - Kommend
- Abrechnung Export (PDF mit allen Stunden/Abrechnungsdaten)
- PayPal Integration

### P2 - Backlog
- Chromium Translate Popup auf Raspberry Pi
- Admin File Size Limits fuer Uploads
- Windows Installer fuer Electron Desktop App
- GPS-Support fuer Kirmeskiste

### Blocked
- DSE890 Gateway GSM (wartet auf neue SIM-Karten)

## Credentials
- Admin (lokal): admin@test.com / password
- Admin (Server): christian.ecker@eventenergie-deutschland.de / qivbeb-Wodha1-sewram
- SMTP: portal@eventenergie.app / :PlN4sFf:}6AY (smtp.ionos.de, Port 465)
