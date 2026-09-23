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
### 2026-02-25 (P0 Bugfix: Ausstempeln crasht mit HTTP 500 bei kaputtem clock_in-Wert)
- **Root Cause**: `datetime.fromisoformat(entry["clock_in"])` in `POST /time/clock-out` crasht mit uncaught `ValueError/TypeError` wenn der Wert None ist oder als BSON-datetime (statt ISO-String) in der DB liegt → 500 in 12ms, silent Frontend-Failure ohne Toast. Betroffener User: roberto.alfano@eventenergie-deutschland.de.
- **Backend-Fix**: `clock_out` toleriert jetzt sowohl String als auch datetime-Werte, gibt bei kaputtem Wert 400 mit klarer Anweisung an den Admin zurueck (statt 500). Logger loggt den kaputten Wert + entry_id fuer weitere Diagnose.
- **Notfall-Endpoint** `POST /employee/time/force-clock-out/{user_id}` (Admin/Verwaltung): schliesst haengenden offenen Eintrag zwangsweise, Fallback clock_in = now-30min wenn DB-Wert unrettbar. Recompute Overtime laeuft danach automatisch.
- **Frontend-Button**: In `MonthlyBreakdownSection.jsx` bei jedem `Aktiv`-Eintrag ein "Jetzt ausstempeln"-Badge. In `AdminZeitDetailPage.jsx` gewired mit confirm-Dialog + Toast.

### 2026-02-25 (Bugfix + Härtung: CSV-Route-Order + Zombie-Backend-Cleanup)
- **Route-Order-Bug**: `GET /time/entries/csv` wurde am Ende der Datei (~Zeile 3616) registriert, aber `PUT /time/entries/{entry_id}` bei ~1702. FastAPI matchte die dynamische PUT-Route zuerst (`entry_id="csv"`) → 405 mit `Allow: PUT`. Route jetzt umgezogen an Position 1330 (VOR `GET /time/entries` und den PUT/DELETE-Handlern) mit Warnkommentar. Lokal + Live-Test: GET 200 ✅.
- **Zombie-Backend-Cleanup**: Auf dem Live-Server waren 4 uvicorn-Master-Instanzen parallel aktiv (durch manuelle Starts in verschiedenen Sessions + inkorrekte NSSM-Restarts). `update-live.ps1` killte bisher nur Prozesse mit `uvicorn.*server:app.*8002`. Neu: kill auch `multiprocessing.spawn`-Worker + harter Port-8002-Fallback der jeden Prozess killt der noch auf 8002 hört. Verhindert dass sich Zombies über die Zeit ansammeln.
- **Bestätigt harmlos**: MongoDB WiredTiger belegt 42 GB RAM (Standard: 50 % vom RAM − 1 GB). Wird bei Bedarf freigegeben.

### 2026-02-25 (Feature: CSV-Export je Monat für Stempelzeiten)
- **Backend** `GET /api/employee/time/entries/csv?month=YYYY-MM&user_id=…`: UTF-8-BOM (Excel-Umlaute), Semikolon-Trennung, Spalten Datum/Tag/Beginn/Ende/Pause/Dauer h:mm/Dauer h/Typ/Manuell/Notiz/GPS + Summenzeile. Admin kann `user_id` setzen, Mitarbeiter nur eigene Daten. Berlin-TZ für Uhrzeiten. Negative Korrektur-Dauern werden korrekt mit Vorzeichen ausgegeben.
- **Frontend Mitarbeiter** `ArbeitszeitPage.jsx`: FileDown-Icon in jeder Monatskarte (öffnet CSV in neuem Tab).
- **Frontend Admin** `MonthlyBreakdownSection.jsx` + `AdminZeitDetailPage.jsx`: identisches Icon mit Callback-Prop `onExportCsv(monthKey)`.
- **Regression-Test** `tests/test_time_entries_csv_export.py`: 4/4 grün.

### 2026-02-25 (Teilzeit-Bugfix: Überstundenabbau zog 40h statt 20h ab)
- **Root Cause 1 (Frontend, `AdminZeitDetailPage.jsx` L947)**: Anzeige rechnete stur `days * 8` statt das vom Backend gelieferte `hours_deducted_display` (Wochenplan-Summe) zu verwenden. Bei 4h/Tag Teilzeit × 5 Werktage: UI zeigt 40h, Backend deduziert korrekt 20h.
- **Root Cause 2 (Backend, `employee.py` `resolve_time_off_request` L3115)**: Employee-Antrag-Approve-Pfad nutzte flat `days * 8` beim Verrechnen aufs Stundenkonto. Jetzt Wochenplan-Loop mit `_soll_minutes_from_schedule` pro Werktag, Fallback nur bei leerem Plan.
- **Root Cause 3 (Backend, `chat.py` Task-Approve L716)**: Task-basierter Approve-Pfad (Chat/Tasks) hatte gleichen Bug. Ebenfalls auf Wochenplan-Loop umgestellt. Import `_soll_minutes_from_schedule` und `timedelta` ergänzt.
- **Regression-Test** (`/app/backend/tests/test_ueberstundenabbau_teilzeit_display.py`): 3 Tests grün (Teilzeit-Berechnung 20h, soll_hours mit Nachkomma, start/end-Spanne mit Pause).

### 2026-02-25 (P0 Followup: Login-Bug durch Naked→www Redirect + NSSM-basiertes Update-Skript)
- **Login-Bug Root Cause**: Alte `Caddyfile.production` machte `redir https://www.eventenergie.app{uri} permanent` für die nackte Domain — auch für `/api/*`. Frontend war gebaut mit `REACT_APP_BACKEND_URL=https://eventenergie.app` (nackt). POST /api/auth/login → 301 → Browser bricht Redirect ab (CORS-Preflight failt, Body geht verloren) → Login schlug still fehl.
- **Fix**: `Caddyfile.production` umgebaut: `eventenergie.app, www.eventenergie.app { … }` bedient beide Domains direkt ohne Redirect. Gleicher Content, gleiche Security-Header, ACME für beide Domains.
- **NSSM-Update-Workflow**: Neues `update-live.ps1` erstellt (Admin-Check, .env-Backup, git pull, pip install, yarn build, Restart-Service EventenergieBackend, Health-Check, Log-File). Alte `update.bat` durch dünnen PowerShell-Wrapper ersetzt. Alte cmd-Fenster-basierte start-all.bat/stop-all.bat sind obsolet (verursachten `Errno 10048` Port-Konflikte mit NSSM-Services).
- **UPDATE_ANLEITUNG.md**: Komplett überarbeitet mit NSSM-Servicelogik, Fehlerbehebung, Verzeichnisstruktur.
- **Verified**: `curl -X POST https://eventenergie.app/api/auth/login` → HTTP 401 statt 301 (Endpoint direkt erreichbar), Login funktioniert im Browser.

### 2026-02-25 (P0 DevOps: Windows-Live-Server SSL-Migration Sectigo→Let's Encrypt via Caddy 2)
- **Root Cause identifiziert**: NSSM-Service `EventenergieCaddy` startete Caddy aus `C:\caddy\` mit einer alten Config die `tls internal` + `auto_https off` + `:8001` als Testport hatte → daher `SEC_E_CERT_EXPIRED` + `SEC_E_ILLEGAL_MESSAGE`. Zusätzlich lief parallel Nginx aus `C:\tools\nginx-1.29.8\` als zweiter Reverse-Proxy mit dem alten (abgelaufenen) IONOS/Sectigo-Zertifikat und blockierte Port 80 komplett.
- **Fix Nginx**: Prozess gekillt + Binary umbenannt (`nginx.exe` → `nginx.exe.disabled`) damit Watchdog ihn nicht neu startet.
- **Fix Caddy**: `Caddyfile.production` aus Repo nach `C:\caddy\Caddyfile` kopiert (nicht `C:\eventenergie\Caddyfile` wie zuerst vermutet!). NSSM-Service `EventenergieCaddy` neu gestartet → Caddy bindet jetzt Port 80 + 443, holt automatisches Let's-Encrypt-Cert via ACME.
- **Verified live**: `curl https://www.eventenergie.app` → HTTP/1.1 200; `curl https://eventenergie.app` → 301 → www; `Server: Caddy` Header; keine SSL-Fehler mehr.
- **Loose ends dokumentiert**: (1) IONOS-DNS-Record `www` fehlt noch bei User, (2) Router-Portweiterleitung Port 80 tcp extern nötig für zukünftige ACME-Renewals.


### 2026-02-25 (Offday-Bugfixes Teil 1: Multi-Day-Recompute, Audit-Log, Safety-Bypass)
- **Multi-Day-Offday-Anlage** (`POST /shift-plan` mit `date_from`/`date_to`): Rief bisher weder `_recompute_overtime_for_year` noch schrieb Audit-Log. Jetzt wird pro betroffenem Jahr Recompute mit `force=True` ausgeloest und ein Audit-Log-Eintrag mit Datumsbereich erzeugt.
- **Single-Day-Offday & Update-Flip & Delete**: Alle drei Pfade schreiben jetzt `offday_create` / `offday_update` / `offday_delete` ins Audit-Log — damit im Aenderungsprotokoll sichtbar.
- **5h-Sprung-Safety-Check** (`_recompute_overtime_for_year`): Neuer Parameter `force=False`. Legitime Mutationen (Offday, Zeit-Edit, Urlaub/Abbau-Approve, Clock-out, Manuell-Create/Delete) rufen mit `force=True` und umgehen die Blockade. Automatische Scheduler-Recomputes bleiben durch die Safety geschuetzt.
- **Bewusst OFFEN gelassen** (siehe naechster Punkt): Die Semantik-Frage „Soll ein Offday an einem Wochentag automatisch -9h vom Konto abziehen?" wurde nicht implementiert, weil (1) das aktuelle Design den Tag bereits durch fehlenden Time-Entry auf -9h bucht und (2) eine Aenderung Baseline-Migration fuer alle Bestandsuser braucht. User-Entscheidung ausstehend.
- **Regression-Test** (`/app/backend/tests/test_offday_batch_deduction_fix.py`): Safety-Blockade ohne force, force=True bypass, Audit-Log-Eintraege werden korrekt geschrieben.

### 2026-02-25 (Mitarbeiter „Meine Arbeitszeit": Geplante Abbau-Tage + Reserved-Hinweis)
- **Backend** (`/app/backend/routes/employee.py` `GET /time-off`): Endpoint reichert jetzt jeden genehmigten `ueberstundenabbau`-Antrag mit `hours_deducted_display` an — 3-Stufen-Berechnung: (1) explizite `hours_deducted` (Stunden-Modus), (2) Uhrzeit-Spanne bei Halbtags-Antrag, (3) Summe Werktags-Soll aus Wochenplan; Fallback `days * 8` wenn Wochenplan leer.
- **Frontend** (`/app/frontend/src/pages/ArbeitszeitPage.jsx`): Neue Sektion „Geplante Abbau-Tage" (mit Kalender-Icon) zeigt zukuenftige/laufende genehmigte Abbau-Antraege mit Datum-Range, Tagen, Stunden und „✓ bereits vom Konto abgezogen"-Hinweis. Header-Summe: „N Tage · Xh bereits abgezogen". Vergangene Abbau-Tage separat als „Bereits eingeloest".
- **Ueberstunden-Kachel**: kleine Zeile unter dem Wert: „davon X Std. fuer geplante freie Tage reserviert" — sichtbar nur wenn Zukunft-Abbau > 0.
- Curl+Screenshot verifiziert: 2 Zukunfts-Abbau × 5 Tage × 40h = 10 Tage · 80h, plus vergangene Abbau werden korrekt getrennt gerendert.

### 2026-02-25 (Verwaltungsmaske: Stundenkonto-Anzeige Übertrag / Monatsende / Aktuell)
- **Neuer Backend-Endpoint** `GET /api/employee/hr-data/{user_id}/saldo-summary` (`/app/backend/routes/employee.py`): Berechnet für einen User drei Werte — `carry_over` (Saldo Stand letzter Tag des Vormonats), `current` (Live overtime_hours) und `month_end` (Prognose Saldo Ende laufender Monat unter Annahme, dass alle Rest-Plan-Tage planmäßig erfüllt werden; genehmigte Urlaub/Krank/Abbau/Offday-Anträge werden korrekt eingerechnet). Skippt den Tag mit offenem Time-Entry (analog zum Clock-Out-Fix).
- **Stundenkonto-Karte** (`/app/frontend/src/pages/AdminZeitDetailPage.jsx`): Die bisherige "Aktuell"-Only-Kachel zeigt jetzt in 3 Spalten `Übertrag | Monatsende | Aktuell` mit monospace-formatierten Werten (2 Nachkommastellen). Struktur analog zur Legacy-Zeiterfassung.
- **Benutzerverwaltungs-Modal** (`/app/frontend/src/components/admin/user_modal/StundenkontoCard.jsx` + `UserEditModal.jsx`): Neue Sektion "Stundenkonto" wird beim Bearbeiten eines Mitarbeiters direkt oberhalb der Sonderberechtigungen angezeigt. Werte werden asynchron via saldo-summary-Endpoint geladen; bei Fehler wird der Block einfach ausgeblendet (Modal bleibt bedienbar).
- **Curl-Test grün**: Anna Weber (`ma1@test.com`) → carry_over 524.00, current -4.00, month_end -4.00. Christian Ecker → carry_over 6.25, current 0.0, month_end 0.0.

### 2026-02-25 (Bugfix: Clock-Out überschreibt tagsüber-Admin-Korrekturen)
- **Root Cause** (`/app/backend/routes/employee.py` `_recompute_overtime_for_year`): Wenn Admin tagsüber eine Zeitkorrektur macht (oder eine andere Aktion einen Recompute triggert), während der MA noch eingestempelt ist (offener `time_entry` mit `duration_minutes=None`), wird der Tag mit **Ist=0 vs Soll=8h** als Minus-Tag verbucht. Bei erstmaliger Baseline-Setzung / V2-Migration wird `baseline = current - diff + deduction` gerechnet und dieses temporäre Minus wird als **positive Kompensation in die Baseline eingebrannt** (z.B. +8h). Am Abend nach Ausstempeln fällt das Minus weg, aber die Baseline bleibt erhöht → es entstehen "geschenkte" +8h Überstunden.
- **Fix**: Vor der Tag-für-Tag-Bilanzschleife wird geprüft, ob aktuell ein offener `time_entry` existiert. Falls ja, wird das Datum dieses Eintrags in der Schleife **übersprungen** — so entsteht keine künstliche Baseline-Kompensation. Sobald der MA ausstempelt, läuft der nächste Recompute mit korrekten `duration_minutes` und der Tag landet regulär in der Bilanz.
- **Regression-Test** (`/app/backend/tests/test_clockout_daytime_admin_edit_fix.py`): Simuliert kompletten Ablauf (einstempeln → Recompute tagsüber → ausstempeln → Recompute abends). Kern-Assert: overtime_hours bleibt 0h wenn Ist = Soll (vorher fälschlicherweise +8h). Bonus-Fall: 9h Arbeit / 8h Soll → +1h ✓.

### 2026-02-24 (HalloPetra Sync-Throttling – MongoDB-Timeout-Fix)
- **MongoDB-Stabilität** (`/app/backend/server.py`): `serverSelectionTimeoutMS` von 10 s → **30 s** erhöht, verhindert `ServerSelectionTimeoutError` unter Last.
- **HalloPetra Auto-Sync-Loop entzerrt** (`/app/backend/routes/hallopetra.py`): Poll-Intervall von 5 Min → **30 Min** (1800 s). Drei innere Loops (Call-Import, `_import_all_contacts`, `_enrich_calls_backfill`) mit `await asyncio.sleep(0.05)` pro Iteration entlastet – DB-Pool bleibt frei.
- **Backend-Tests** (`/app/backend/tests/test_hallopetra_stability_iteration87.py`): 13/13 grün, manueller Sync `<60 s`, keine Timeouts, alle bestehenden Endpoints (Auth, Tasks, HalloPetra) unverändert.

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
