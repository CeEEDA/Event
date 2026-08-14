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
### 2026-02-14 (Bugfix Einsatzplanung Notiz-Edit)
- **Bugfix: Zuweisung verschwindet beim Notiz-Edit** (`/app/frontend/src/pages/EinsatzplanungPage.jsx` + `/app/backend/routes/employee.py`): Beim Editieren einer bestehenden Zuweisung via Stift-Icon sendete das Frontend `user_id` und `date` NICHT im Update-Payload → Backend setzte beide Felder auf `None` → Assignment war nicht mehr an den User gekoppelt und verschwand aus der Ansicht. Fix: Frontend `saveAssignment` schickt `user_id`/`date` aus `editCell` mit; Backend defensive Guard – falls Felder fehlen, bleiben die alten `prev`-Werte erhalten. Curl-Test mit "alten" Payload bestätigt: `user_id`/`date`/`note` bleiben nach Update korrekt gesetzt.

### 2026-07-16 (später Nachmittag)
- **ZUGFeRD / Factur-X / XRechnung Parser im Heuristic-Fallback** (`/app/backend/services/zugferd_parser.py` + `/app/backend/services/heuristic_analyzer.py`): Neue Byte-basierte Helfer `extract_zugferd_xml_from_bytes()` + `try_zugferd_parse_bytes()`. `analyze_document_fallback()` prüft PDF jetzt zuerst auf eingebettete `factur-x.xml` / `zugferd-invoice.xml` / `xrechnung.xml`. Wenn gefunden: Absender, Empfänger, Rechnungsnummer, Datum, Betrag, IBAN, Waehrung kommen direkt aus der strukturierten XML (`_authoritative_source="zugferd_xml"`). Richtung (Eingang/Ausgang) wird über BuyerTradeParty vs. Firmen-Marker bestimmt – behebt Fehlklassifikation von PDFs mit irreführendem Sichttext (z.B. Mathias Normann). End-to-End Test grün.
- **Bank-Statuszeile in Eingangsrechnungen** (`GET /api/incoming-invoices/bank-status` + Header-Zeile in `EingangsrechnungenPage.jsx`): Übersicht aller konfigurierten Banken (Sparkasse + Volksbank) mit letztem Sync-Zeitpunkt, SCA-Verlängerungs-Countdown und Enabled-Status. UI-Icon je Zustand (Wifi/WifiOff/ShieldAlert).
- **Bulk-Zahlung** (`POST /api/incoming-invoices/bulk-mark-paid` + Frontend): Checkboxes pro offener/überfälliger Rechnung, "Alle wählen"-Toggle, Sammel-Betrag im UI, Server-seitig Filter `eingang_paid|_by_creditcard|_by_sepa: {$ne: True}` (idempotent + schützt bereits ausgeblendete CC/SEPA-Zahlungen). Limit 500 pro Batch. 12/12 Testing-Agent-Tests grün (`/app/test_reports/iteration_86.json`).

### 2026-07-16
- **Eingangsrechnungen Modul – Phase 2 (FinTS Sparkasse Auto-Match)** (`/app/backend/fints_banking.py` + `POST /api/incoming-invoices/fints/auto-match`): Ausgehende Sparkassen-Buchungen (amount<0) werden gegen offene Eingangsrechnungen aus `rechnungseingang_*` gematcht. Match-Logik analog Kirmes: (1) Rechnungsnr. exakt/Suffix/fuzzy im Verwendungszweck + Betrag → `auto_paid`; (2) Rechnungsnr. gefunden aber Betrag weicht ab → Admin-Task `fints_incoming_amount_mismatch`; (3) Nur Absender + Betrag, 1 Kandidat → `auto_paid` (conf 70); (4) Absender + Betrag, mehrere Kandidaten (z.B. 4× gleiche Rechnung) → Admin-Task `fints_incoming_ambiguous` mit allen Kandidaten. Sammelüberweisungen ausdrücklich ausgeschlossen. UI-Button "FinTS-Abgleich" auf `EingangsrechnungenPage`. Alle 6 Test-Szenarien (exakt/ambig/mismatch/unique/eingehend/suffix) laufen korrekt.
- **Eingangsrechnungen Modul – Phase 1** (`/app/backend/routes/incoming_invoices.py` + `/app/frontend/src/pages/EingangsrechnungenPage.jsx`): Neuer Menüpunkt "Eingangsrechnungen" unter "Ausgangsrechnungen" in Verwaltung. Backend aggregiert alle Docs aus `rechnungseingang_*`-Ordnern inkl. AI-Metadaten (Absender, Rechnungsnr., Betrag, Datum, IBAN). Status: overdue (rot) / open (amber) / paid (grün); Fälligkeit = Override → AI-due_date → Rechnungsdatum+14T. Frontend: Summen-Kacheln, Suche, Filter-Tabs, Split-Layout mit PDF-Preview (Blob), editierbare Fälligkeit + Notiz. `POST /{id}/mark-paid` FINAL (keine Rücknahme in UI, nur DB-seitig laut User-Entscheidung 1b). `PATCH /{id}` für due_date/notes.

### 2026-07-15
- **HR Mitarbeiter-Jahresauswertung PDF** (`/app/backend/services/hr_evaluation_pdf.py` + `GET /api/employee/reports/yearly-evaluation/pdf`): Neuer "Auswertung"-Button in der Mitarbeiterverwaltung (`EmployeeAdminPage.jsx`) generiert eine einseitige PDF mit Name, Überstunden-Saldo, Urlaub genommen, Resturlaub und Krankheitstagen pro aktivem MA (role=admin/mitarbeiter, is_active≠false) + Summenzeile. Krankheitstage werden aus `time_off_requests` (type=krank, status=approved) als Werktage im aktuellen Jahr berechnet.

### 2026-07-10
- **SMTP Robustness Fix** (`/app/backend/email_service.py`): Timeout 15s→60s, 3 retries with backoff, connection reuse for BCC copies. Fixes IONOS SSL handshake timeouts on large PDF attachments.
- **Invoice "Jetzt bezahlen" Button** (`/app/backend/routes/kirmes.py`): New helper `_create_kirmes_invoice_payment_link` generates a Stripe Checkout session for open balances. Configurable via `STRIPE_INVOICE_PAYMENT_METHODS` env (default `card`), auto-fallback to card on rejection, error surfaced via `payment_link_error` on invoice. Stripe webhook auto-marks invoice as `bezahlt`.
- **Public Payment Landing Pages** (`/app/frontend/src/pages/RechnungPaymentResultPage.jsx`): `/rechnung/bezahlt` (polls Stripe status) + `/rechnung/abgebrochen`.
- **Meter Auto-Freeze on Event End** (`/app/backend/routes/kirmes.py`): Scheduler runs every 30 min, freezes final `E_imp_kWh` as `kwh_ausbau/meter_end`, computes `kwh_used`, unlinks `emu_device_id/emu_meter_id/emu_meter_name`, marks event `meters_frozen_at`. Manual trigger endpoint `POST /api/kirmes/events/{id}/freeze-meters`. UI banner + button on KirmesEventDetailPage.

## Backlog (P1)
- **Eingangsrechnungen Volksbank**: Zweit-Bank neben Sparkasse in `fints_banking.py` einbinden (FINTS_URL/BLZ/USER/PIN parametrisieren, Konto-Auswahl über IBAN)
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
