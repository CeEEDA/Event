# Eventenergie / Kirmes Portal – PRD

## Original Problem Statement
Comprehensive "Kirmes" (Fairground) billing, dispatch, and HR management system.
Manage robust telemetry ingestion, order management, disruption logging, team management,
HR time-tracking/absences, Kiosk interfaces, deep hardware integration (Modbus, DSE, EMU),
AI-driven Document Management, and a full Inventory (Inventar) module.

## User Language
German (all UI + agent responses in German only).

## Core Modules
- **Kirmes**: Events, Signups, Meter linking, Invoices, Reminders, Stripe deposit + refunds
- **Inventar**: iPad-optimised, groups, scaling, PDF/XLSX exports
- **HR**: Time tracking, absences, travel expenses, offdays, Verbandsbuch, ADR
- **Telemetry**: EMU meters (MQTT), DSE generators, Kirmeskiste, Sening Tankbeleg Pi
- **Documents**: AI-driven inbox, DATEV routing, FinTS banking
- **EpiRent Integration**: Order sync, Lieferscheine (planned)
- **OTA**: Update pipeline for Pi devices

## Recently Implemented (Session current)
### 2026-07-16
- **Eingangsrechnungen Modul – Phase 1** (`/app/backend/routes/incoming_invoices.py` + `/app/frontend/src/pages/EingangsrechnungenPage.jsx`): Neuer Menüpunkt "Eingangsrechnungen" unter "Ausgangsrechnungen" in Verwaltung. Backend aggregiert alle Docs aus `rechnungseingang_*`-Ordnern inkl. AI-Metadaten (Absender, Rechnungsnr., Betrag, Datum, IBAN). Status: overdue (rot) / open (amber) / paid (grün); Fälligkeit = Override → AI-due_date → Rechnungsdatum+14T. Frontend: Summen-Kacheln, Suche, Filter-Tabs, Split-Layout mit PDF-Preview (Blob), editierbare Fälligkeit + Notiz. `POST /{id}/mark-paid` FINAL (keine Rücknahme in UI, nur DB-seitig laut User-Entscheidung 1b). `PATCH /{id}` für due_date/notes.

### 2026-07-15
- **HR Mitarbeiter-Jahresauswertung PDF** (`/app/backend/services/hr_evaluation_pdf.py` + `GET /api/employee/reports/yearly-evaluation/pdf`): Neuer "Auswertung"-Button in der Mitarbeiterverwaltung (`EmployeeAdminPage.jsx`) generiert eine einseitige PDF mit Name, Überstunden-Saldo, Urlaub genommen, Resturlaub und Krankheitstagen pro aktivem MA (role=admin/mitarbeiter, is_active≠false) + Summenzeile. Krankheitstage werden aus `time_off_requests` (type=krank, status=approved) als Werktage im aktuellen Jahr berechnet.

### 2026-07-10
- **SMTP Robustness Fix** (`/app/backend/email_service.py`): Timeout 15s→60s, 3 retries with backoff, connection reuse for BCC copies. Fixes IONOS SSL handshake timeouts on large PDF attachments.
- **Invoice "Jetzt bezahlen" Button** (`/app/backend/routes/kirmes.py`): New helper `_create_kirmes_invoice_payment_link` generates a Stripe Checkout session for open balances. Configurable via `STRIPE_INVOICE_PAYMENT_METHODS` env (default `card`), auto-fallback to card on rejection, error surfaced via `payment_link_error` on invoice. Stripe webhook auto-marks invoice as `bezahlt`.
- **Public Payment Landing Pages** (`/app/frontend/src/pages/RechnungPaymentResultPage.jsx`): `/rechnung/bezahlt` (polls Stripe status) + `/rechnung/abgebrochen`.
- **Meter Auto-Freeze on Event End** (`/app/backend/routes/kirmes.py`): Scheduler runs every 30 min, freezes final `E_imp_kWh` as `kwh_ausbau/meter_end`, computes `kwh_used`, unlinks `emu_device_id/emu_meter_id/emu_meter_name`, marks event `meters_frozen_at`. Manual trigger endpoint `POST /api/kirmes/events/{id}/freeze-meters`. UI banner + button on KirmesEventDetailPage.

## Backlog (P1)
- **Eingangsrechnungen Phase 2**: FinTS Auto-Match ausgehender Buchungen gegen Eingangsrechnungen (IBAN + Betrag + Rechnungsnr.) + Volksbank-Konto in `fints_banking.py` neben Sparkasse
- OTA-Update-Mechanik für Tankbeleg Pi (client-side polling + systemd restart)
- EpiRent "Lieferscheine" (Delivery Notes) PDF Generation
- Refactor `kirmes.py` (>4400 lines) into submodules (events / signups / invoices / meters / scheduler)

## Backlog (P2)
- Sync-Lag-Anzeige pro Zähler
- `kwh_offset` auf Ingest anwenden (E_imp_kWh)
- Disk-Watchdog Live-Server (start-all.bat)
- Bulk-Move für Tankbelege
- Admin Audit-Page für Asset-Type-Änderungen
- "Alarm vor Ort geprüft – Sammel-Warning quittieren" (DSE Key 35707)
- USB-Resilience / Hardware-Health-Dashboard pro Pi
- Camera-Foto Upload mit EXIF GPS in Dokumentenablage
- Tank-Alarm-Threshold Notifications
- Add GPS Support to Kirmeskiste (Legacy 4-meter variant)
- Lastdiagramm Live-Test
- Offday-Verfallsregel §11 Abs. 3 ArbZG (8-Wochen-Frist)
- Mail/SMS Notification bei Schichtplan-Release

## 3rd Party Integrations
- Stripe (Payments) — user API key
- EpiRent (Event software)
- Ollama (Local AI)
- IONOS IMAP / SMTP
- DATEV (Email routing)
- FinTS (Banking)
- Open-Meteo, Nominatim (weather / geocoding)
