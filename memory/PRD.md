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
- **N+1 Query Fix**: 5 Endpoints optimiert (batch statt serial)
- API-Antwortzeiten: 30+ Sek -> unter 200ms
- RAM-Leak gefixt (25GB -> normal)

### Expanded Row Compact UI (abgeschlossen - 2026-04-02)
- **Lade-Delay gefixt**: `limit=1` auf meter-data API (90.000 -> 1 Datensatz, ~120ms)
- **Kompaktes Layout**: 3-Spalten-Grid ersetzt durch 4-zeiliges Inline-Layout
  - Zeile 1: Kontaktdaten inline (Firma | Name | Adresse | Tel | E-Mail | USt)
  - Zeile 2: EMU-Werte inline (Meter-Name | Online/Offline | kW | V | A | Hz | Messung)
  - Zeile 3: Aktionen (Neu verknuepfen | Trennen | QR | Zaehlerdaten & Export)
  - Zeile 4: Rechnung inline (RE-Nr | Datum | Betrag | PDF | E-Mail)
- **Tabelle kompakter**: min-w 1300px -> 1000px, kuerzere Spaltenheader
- **Payment-Labels gefixt**: pending_payment -> Ausstehend, abgerechnet -> Abgerechnet
- **Recharts-Import entfernt** (Chart nicht mehr in Expanded Row)
- **Invoice Confirmation Dialog** mit irreversibler Warnung

## Key API Endpoints
- `GET /api/kirmes/signups/{signup_id}/meter-data?limit=1` (Schneller Abruf)
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
- GPS-Support fuer Kirmeskiste (wartet auf Klaerung)

### Blocked
- DSE890 Gateway GSM (wartet auf neue SIM-Karten)

## Credentials
- Admin (lokal): admin@test.com / password
- Admin (Server): christian.ecker@eventenergie-deutschland.de / qivbeb-Wodha1-sewram
- SMTP: portal@eventenergie.app / :PlN4sFf:}6AY (smtp.ionos.de, Port 465)
