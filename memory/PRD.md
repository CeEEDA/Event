# Eventenergie Portal - PRD

## Original Problem Statement
Umfassendes "Kirmes" (Jahrmarkt) Abrechnungssystem mit Tankbeleg-Digitalisierung, Auftragsverwaltung, Energiemonitoring, Zahlungsabwicklung und mehr.

## Core Architecture
- **Frontend:** React (CRA) + Tailwind CSS + Shadcn/UI
- **Backend:** FastAPI (Python) + MongoDB + GridFS
- **Desktop:** Electron Wrapper
- **External APIs:** EpiRent (ERP), Stripe (Payments), MQTT, OpenStreetMap

## What's Been Implemented (Session 2026-04-02)

### Performance-Optimierung
- MongoDB Indexes, N+1 Query Fix, RAM-Leak gefixt (25GB -> normal)

### Expanded Row Redesign (KirmesEventDetailPage)
- 3-Spalten Karten-Layout (KONTAKTDATEN | ZAEHLERDATEN | EMU-ZAEHLER)
- Gelbe Hinterlegung fuer nicht-verknuepfte Zaehler (bg-amber-50)
- Payment-Labels gefixt (pending_payment -> Ausstehend, abgerechnet -> Abgerechnet)
- Lade-Delay gefixt (limit=1 auf meter-data API, ~120ms)

### Zaehler-Detailseite (MeterDiagnosticsPage) - NEU
- **Route**: /devices/:deviceId/meters/:meterId
- **Datumsfilter**: Von/Bis mit "Anzeigen" Button und 7-Tage-Navigation (</>)
- **Verknuepfungshistorie**: Welche Veranstaltung, welcher Kunde, Zeitraum, Fahrgeschaeft, Platznr, Einbau/Ausbau/Verbrauch, Rechnungsnummer, Status (Aktiv/Beendet)
- **Messdaten-Tabelle**: 12 Spalten (Zeitstempel, kWh, kW, U L1/L2/L3, I L1/L2/L3, I ges., Hz, cos phi)
- **Anomalie-Erkennung**: Rot bei Spannung < 200V, Gelb bei Frequenz ausserhalb 49-51Hz
- Klickbare Zaehler-Eintraege in DeviceManagementPage navigieren zur Detailseite
- **Backend-Endpoints**:
  - GET /api/devices/{device_id}/meters/{meter_id}/diagnostics?limit=50&date_from=&date_to=
  - GET /api/devices/{device_id}/meters/{meter_id}/history

## Key API Endpoints
- GET /api/kirmes/signups/{signup_id}/meter-data?limit=1
- GET /api/devices/{device_id}/meters/{meter_id}/diagnostics (date range, limit)
- GET /api/devices/{device_id}/meters/{meter_id}/history (assignment history)
- GET /api/devices/{device_id}/quick-info (meter_id included)

## Prioritized Backlog

### P1 - Kommend
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
