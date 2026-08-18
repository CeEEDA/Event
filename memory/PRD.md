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
### 2026-02-18 (Telefon-Kachel im Hub + Toggle in Benutzerverwaltung)
- **Neue Hub-Kachel „Telefon"** (`/app/frontend/src/pages/HubPage.js` + `/app/frontend/src/pages/TelefonPage.js` + `/app/frontend/src/App.js`): Admin + jeder Mitarbeiter mit `apps.modules.telefon===true` sieht die neue rosa Telefon-Kachel im Hub. Route `/telefon` zeigt alle Petra-Anrufe mit Statistik-Kacheln (Offen / 🚨 Notfälle / Alle), Suche, Filter, Detail-Modal mit Zusammenfassung, Anrufdauer, „Zurückrufen"-Link (tel:), Aufnahme/Transkript-Links, „Als erledigt markieren"-Button.
- **Neuer Toggle „Telefon (Anrufe)"** in UserEditModal (`/app/frontend/src/components/admin/UserEditModal.jsx`): Neues Modul-Feld `telefon` in der Hub-Kachel-Grid – wenn AN sieht der Mitarbeiter die Telefon-Kachel.
- **Backend** (`/app/backend/routes/hallopetra.py`): 3 neue Endpoints — `GET /api/hallopetra/calls?token=...&only_open=` (Liste + Statistik), `GET /api/hallopetra/calls/{id}` (Detail mit Full-Payload für Transkript/Recording), `POST /api/hallopetra/calls/{id}/mark-done`. Auth via `_can_view_telefon(caller)` = Admin oder Mitarbeiter mit `apps.modules.telefon===true`. Curl-Test grün: Admin=200, MA ohne Toggle=403, MA mit Toggle=200, Mark-Done reduziert open-Count.

### 2026-02-18 (HalloPetra Integration – Pillar 1: Inbound Webhooks)
- **HalloPetra KI-Telefonassistent** (`/app/backend/routes/hallopetra.py` + `/app/frontend/src/pages/AdminSettingsPage.js`): Webhook-Empfänger `POST /api/hallopetra/webhook` mit HMAC-SHA256-Signatur-Validierung (Header `X-Petra-Signature`). Qualifizierte Anrufe (event `call.completed`, `qualification.category != spam/unqualified/hangup/wrong_number`) werden zu Tasks in `tasks`-Collection mit `source=hallopetra`. Nicht-qualifizierte Anrufe → skipped. Notruf-Routing bleibt bei Petra (nur Spiegelung als `is_emergency=true` + 🚨-Prefix + `priority=urgent`). Idempotenz via `petra_call_id`. Automatisches Customer-Matching per Telefonnummer (letzte 8 Ziffern). Admin-Panel mit 4-Kachel-Status, kopierbare Webhook-URL, .env-Config-Snippet, Test-Buttons (Verbindung testen / Anruf simulieren / 🚨 Notfall simulieren), Liste letzter Anrufe mit Priorität-Badges. Config via .env: `HALLOPETRA_CLIENT_ID/SECRET/API_TOKEN/AUTH_HEADER/AUTH_SCHEME/WEBHOOK_SECRET/BASE_URL` – Auth-Header konfigurierbar für zukünftige Doku-Änderungen. Curl-Test grün: qualifiziert → Task, spam → skip, Duplikat → dedup, Notfall → urgent + 🚨.

### 2026-02-14 (Einsatzplanung – Lese-/Bearbeitungs-Trennung)
- **Alle Mitarbeiter sehen Einsatzplanung (Read-Only)** (`/app/frontend/src/pages/HubPage.js` + `/app/frontend/src/pages/EinsatzplanungPage.jsx` + `/app/backend/routes/employee.py`): Die Kachel „Einsatzplanung" wird jetzt jedem Mitarbeiter im Hub angezeigt. Alle können den Wochenplan mit allen Aufgaben & Mitarbeitern sehen. Bearbeitungsrechte (Zuweisungen ändern, Freigabe, Job-Anforderungen, Offday-Vergabe) erfordern jetzt `apps.modules.einsatzplanung !== false` (Toggle in Benutzerverwaltung). Neue Backend-Helper `_is_staff` (Lesen) und `_can_edit_einsatzplanung` (Schreiben); GET `/shift-plan` + `/work-schedule` öffnen für alle Staff, POST/DELETE/release/job-reqs bleiben Editor-only. Frontend zeigt „Nur Ansicht"-Badge und blendet alle Bearbeiten-Icons/Buttons/Cell-Handler aus. Curl-Test grün: MA ohne Toggle → 200 GET, 403 auf allen Schreib-Ops.

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
