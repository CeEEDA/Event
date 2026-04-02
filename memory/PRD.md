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
- MongoDB Indexes, N+1 Query Fix, RAM-Leak gefixt

### Expanded Row Redesign (abgeschlossen - 2026-04-02)
- 3-Spalten Karten-Layout (KONTAKTDATEN | ZAEHLERDATEN | EMU-ZAEHLER)
- Gelbe Hinterlegung fuer nicht-verknuepfte Zaehler
- Payment-Labels gefixt (pending_payment -> Ausstehend, abgerechnet -> Abgerechnet)
- Lade-Delay gefixt (limit=1 auf meter-data API)

### Diagnose-Feature (abgeschlossen - 2026-04-02)
- **Backend**: Neuer Endpoint GET /api/devices/{device_id}/meters/{meter_id}/diagnostics?limit=10
  - Liefert letzte 10 Roh-Messwerte mit ts_utc, E_imp_kWh, P_sum_kW, U_L1/L2/L3, I_sum, F_Hz, cosphi
  - ~30ms Antwortzeit
- **Frontend**: Klickbare Zaehler-Eintraege in DeviceExpandedRow
  - "Klick = Diagnose" Hinweis bei jedem Zaehler
  - Diagnose-Panel mit vollstaendiger Messtabelle (9 Spalten)
  - Farbliche Markierung: Rot bei Spannung < 200V, Gelb bei Frequenz ausserhalb 49-51Hz
  - Neuester Messwert hervorgehoben
  - Schliessen-Button (X) zum Ausblenden
- **quick-info API erweitert**: meter_id in jedem Reading-Eintrag

## Key API Endpoints
- GET /api/kirmes/signups/{signup_id}/meter-data?limit=1
- GET /api/devices/{device_id}/meters/{meter_id}/diagnostics?limit=10 (NEU)
- GET /api/devices/{device_id}/quick-info (meter_id hinzugefuegt)
- /api/kirmes/events/{event_id}/generate-invoices
- /api/kirmes/public/verify-email-link
- /api/kirmes/public/register

## Prioritized Backlog

### P1 - Kommend
- PayPal Integration

### P2 - Backlog
- Chromium Translate Popup auf Raspberry Pi
- Admin File Size Limits fuer Uploads
- Windows Installer fuer Electron Desktop App
- GPS-Support fuer Kirmeskiste (wartet auf Klaerung)

### Blocked
- DSE890 Gateway GSM (wartet auf neue SIM-Karten)

## Credentials
- Admin (lokal): admin@test.com / password
- Admin (Server): christian.ecker@eventenergie-deutschland.de / qivbeb-Wodha1-sewram
- SMTP: portal@eventenergie.app / :PlN4sFf:}6AY (smtp.ionos.de, Port 465)
