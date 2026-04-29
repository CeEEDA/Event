# Kirmes Billing & HR System — PRD

## Original Problem Statement
Comprehensive "Kirmes" (Fairground) billing and HR management system. Core focus on hardware integration for fuel receipts (Tankwagen) via a Raspberry Pi emulating an EPSON TM-U295 printer to intercept serial data from a Sening MultiFlow system.

## Core Requirements
- Desktop Apps (Mac/Windows), Mobile Apps (Capacitor), Windows Server 2019.
- Hardware: DSE Gateways, EPSON Printer emulation via Raspberry Pi.
- Finance/HR: Invoices, FinTS, AI document categorization, Time tracking.
- **Offline-first**: Pi must work fully offline (no LTE). Orders, drivers, receipts are cached in local SQLite and synced when connectivity returns.

## Product Language
German (UI + all user communication).

---

## Recently Completed
- **2026-02 — P0 Bugfix (Mahn-Aufgaben verschwinden nicht nach Versenden):**
  - **Symptom**: Nach Klick auf "Versenden" einer Mahnungs-Task blieb diese in der Aufgabenliste sichtbar.
  - **Wurzel**: Race-Condition zwischen `send-reminder`-Endpoint (markiert Task als completed) und dem Mahnungs-Scheduler `check_overdue_invoices` (laeuft alle 6h + bei Server-Start). Der Scheduler suchte nur nach `completed: False`-Tasks fuer dieselbe Stufe; nach einem Versenden war die Bedingung erfuellt → er erstellte sofort eine neue Task mit identischer Stufe. Hot-Reload triggerte das exakt ~9 Sekunden nach einem User-Versand → User sah scheinbar "die Task ist immer noch da".
  - **Backend-Fix** (`/app/backend/routes/kirmes.py`): Existenz-Check ignoriert `completed`-Status (`is_deleted: {"$ne": True}` reicht). Damit blockiert eine bereits ERLEDIGTE Mahn-Task einer Stufe das Neu-Erstellen derselben Stufe. Naechste Stufe wird erst nach 14 Tagen erzeugt. Kommentar fuer den Aufraeum-Code in `send-reminder` wurde praeziser.
  - **Frontend-Fix** (`/app/frontend/src/pages/HubPage.js`): Optimistisches `setTasks(prev => prev.filter(...))` direkt beim Klick auf "Versenden"/"Ablehnen" → Task verschwindet sofort. Bei API-Fehler wird `loadTasks()` aufgerufen → Task taucht ggf. wieder auf.
  - Aufraeumung: 1 hangengebliebene Race-Altlast-Task (Meyer R26-K-0002) per Script geschlossen.
  - Verifiziert: curl-Flow vorher 1 offen → POST send-reminder → nachher 0 offen ✅.

- **2026-02 — P1 Feature (Hub: Admin-Anwesenheits-Panel im Stempelkarten-Header):**
  - Backend (`/app/backend/routes/employee.py` `/time/presence`): Endpoint liefert jetzt ALLE aktiven Admins/Mitarbeiter mit `clocked_in`-Status (nicht nur die eingestempelten). Sortierung: eingestempelt zuerst, dann alphabetisch. Kunden ausgeschlossen.
  - Frontend (`/app/frontend/src/pages/HubPage.js`): Neuer `presence`-State + 10s-Polling. Im Stempelkarten-Header neben Resturlaub/Überstunden ein Panel "ANWESENHEIT" mit Counter `online/total` und Liste aller Mitarbeiter mit grünen/grauen Punkten (Vorname + Tooltip mit vollen Namen und Uhrzeit). Wird nur Admins angezeigt.
  - Verifiziert per curl + Playwright: Anna stempelt ein → Counter 1/10, grüner Punkt + Sortierung an erste Stelle. Mitarbeiter erhalten 403.

- **2026-02 — P1 Feature (Chat: Teams-Style Reactions + Threaded Replies):**
  - Backend (`/app/backend/routes/chat.py`): `reactions: dict[emoji,[user_ids]]` + `parent_id` auf Messages, neuer `POST /chat/messages/{id}/react`, Top-Level-Liste mit `reply_count`-Aggregation, Replies auf Replies werden auf Root geflacht.
  - Frontend (`/app/frontend/src/pages/ChatPage.jsx`): Schwebende Reaktionsleiste auf Hover (4 Quick + erweitertes 12-Emoji-Picker + Antworten), Reaktion-Badges unter Nachricht (toggle bei Klick), "X Antworten"-Link expandiert inline-Thread mit fuchsia-Linker-Border + Reply-Input.
  - Verifiziert per curl + Playwright: Reaktionen toggle sauber, Thread-Replies persistiert, Polling synchronisiert offenen Thread.

- **2026-02 — P1 Feature (Mitarbeiter: eigene Dokumente einsehen):**
  - Mitarbeiter koennen jetzt im Bereich "Mitarbeiter-Daten" ihre eigenen Personaldokumente (Personalausweis, Fuehrerschein, Fahrerkarte, Erste Hilfe, Sicherheitsunterweisung, Staplerschein, Hubarbeitsbuehne, Teleskoplader, Baumaschine) einsehen und herunterladen.
  - Neuer Tile "Dokumente" in `MitarbeiterDatenPage.jsx` (fuchsia, FileText) → Route `/mitarbeiter-daten/dokumente`.
  - Neue Seite `MitarbeiterDokumentePage.jsx` mit Stats-Strip (Gesamt/Gueltig/Laeuft bald/Abgelaufen), Status-Karten je Dokumenttyp (gruen/amber/rot) und `openExternal`-Anbindung fuer Tablet-PDF-Viewer.
  - **Sicherheit verifiziert per curl** (6-Schritte-Test):
    1. Mitarbeiter ohne `user_id` → eigene Docs ✅
    2. Mitarbeiter mit `user_id=admin` injiziert → Backend ignoriert, eigene Docs ✅
    3. Admin laedt Dok fuer MA1 hoch → korrekt zugeordnet ✅
    4. MA1 sieht hochgeladenes Dok ✅
    5. MA1 lädt eigenes Dok runter → 200 ✅
    6. MA1 versucht fremdes Admin-Dok zu downloaden → **403** ✅
  - Backend (`/app/backend/routes/employee.py`) war bereits sauber abgesichert (Zeile 268+472): `target_id = user_id if user_id and caller.role==admin else caller.id`.

- **2026-02 — P0 Bugfix (Generator-Detail: "Laedt forever" fuer Mitarbeiter):**
  - Symptom: Mitarbeiter sieht 7 Maschinen in Monitoring-Liste, beim Klick bleibt manchmal nur "Laedt..." stehen (nicht immer, Maschine egal).
  - Wurzel: `GET /api/generators/{id}` (`server-side`) lehnte Mitarbeiter ohne expliziten `generator_monitoring.generator_ids`-Eintrag mit 403 ab. Die LIST aber blendet automatisch ALLE aktiven Stromerzeuger-/Lichtmast-Devices als virtuelle `dev-`-Generatoren ein (ohne Permission-Check) → Inkonsistenz. Ergebnis: 403 in `Promise.all([device, telemetry, alarms])` killte alle 3, Frontend fiel in `catch` → Toast + Navigate zurueck → User sieht "Laedt"-Flackern.
  - Backend-Fix (`/app/backend/routes/generators.py` `get_generator`): Rolle `mitarbeiter` erhaelt vollen Zugriff (konsistent mit Liste). `kunde` bleibt strikt eingeschraenkt.
  - Frontend-Robustheit (`GeneratorDetailPage.js` `fetchData`): `Promise.all` durch sequenzielle Calls ersetzt. Generator-Doc laedt zuerst (kritisch), beendet `loading`. Telemetry + Alarms laden im Hintergrund nach – einzelne Fehler killen nicht mehr die ganze Seite.
  - Auch `EnergyMonitoringDetailPage.js` defensiv gehaertet (Loading nur an `fetchDevice` gekoppelt + 15s Safety-Timer + distinkter Loading-Text "Geraetedaten werden geladen..." um zukuenftiges Debugging zu vereinfachen).
  - Verifiziert per curl mit `ma1@test.com`: `GET /generators/dev-xxx` → 200, `GET /telemetry` → 200, `GET /alarms` → 200.

- **2026-02 — P1 UX (Textbausteine: aus Einstellungen → Verwaltung verschoben):**
  - Textbausteine-Bereich aus `AdminSettingsPage.js` (Einstellungen) entfernt und als eigenstaendige Admin-Seite `/verwaltung/textbausteine` neu angelegt (`TextbausteineAdminPage.jsx`).
  - Neuer Tile "Textbausteine" (FileText, amber) in `VerwaltungPage.jsx` zwischen Mitarbeiter und KI-Training.
  - Erweiterungen vs. alter Section: optionales Kategorie-Feld beim Anlegen, Volltextsuche (Bezeichnung/Text/Kategorie), Gruppierung nach Kategorie in Gruppen-Karten.
  - Verifiziert: Admin sieht Tile, Liste mit 5 Bausteinen, Suche "kabel" filtert auf 3 (gruppiert ELEKTRO + ALLGEMEIN), Add/Edit/Delete funktionieren.

- **2026-02 — P1 Feature (Projektbericht leer + Stundenberichte-Verwaltung):**
  - Neuer Button "Projektbericht leer" im Header der `OrdersPage` (`/orders`) → oeffnet `/project-report/new` ohne `order_pk`/`order_name` (Mitarbeiter fuellt Kundendaten manuell aus). Datenmodell unterstuetzte das schon (`order_pk: Optional[str]`).
  - Neue Admin-Seite `/verwaltung/stundenberichte` (`StundenberichteListPage.jsx`) mit Volltextsuche (Kunde, Projektnummer, Ort, Mitarbeiter, Arbeitsbeschreibung, Bemerkungen) und Filter-Pills (Alle / Mit Projekt / Blanko).
  - Blanko-Berichte (`order_pk == null`) sind optisch klar gekennzeichnet: gelber Linker Rand, BLANKO-Badge, FileWarning-Icon, Amber-Tint.
  - Tile "Stundenberichte" als erster Eintrag in `AuswertungIndexPage` (Verwaltung > Auswertung).
  - Backend: `GET /api/project-reports` (admin-only) mit kompakter Projektion (~12 Felder) – sortiert nach `created_at desc`, Limit 2000.
  - Verifiziert: Blanko-Bericht via curl erstellt, taucht mit BLANKO-Badge in Liste auf, Suche/Filter funktionieren, Mitarbeiter-Token erhaelt 403.

- **2026-02 — P1 UX (Projektbericht: Textbaustein-Picker mit Suche):**
  - Bug/UX: Bei spaeter 40+ Textbausteinen wurde das native `<select>`-Dropdown unuebersichtlich.
  - Fix (`/app/frontend/src/pages/ProjectReportFormPage.jsx`): Inline-`<select>` durch Button "Textbaustein" ersetzt; oeffnet Dialog (`shadcn/ui Dialog`) mit Suchleiste (Auto-Fokus, durchsucht Bezeichnung+Text+Kategorie), Gruppierung nach Kategorie (z.B. AUFBAU, ELEKTRO, ALLGEMEIN ans Ende), und Klick fuegt den Text ein und schliesst das Popup. Footer-Counter mit Gesamtzahl.
  - Verifiziert: 5 Bausteine -> Suche "kabel" filtert auf 3, Klick fuegt Text in Arbeitsbeschreibung ein.

- **2026-02 — P0 Hotfix (Projektbericht: Mitarbeiter & Vorlagen für Nicht-Admins):**
  - Bug: Normale Mitarbeiter sahen im `/project-report/new` weder das Mitarbeiter-Auswahl-Dropdown noch die Textbaustein-Vorlagen. Ursache: `GET /api/users` ist Admin-only (403 für Mitarbeiter) und der Frontend-Call lief in einem `Promise.all` zusammen mit `/work-templates` → bei 403 wurde die ganze Promise abgewiesen, beide State-Setter sprangen nie.
  - Backend (`/app/backend/server.py`): Neuer Endpoint `GET /api/users/active` mit `Depends(get_current_user)` (nur Login nötig). Liefert ausschliesslich `id, name, email, role, is_active` aktiver Nicht-Kunden – keine sensiblen Felder (`password_hash`, `permissions`, `access_*`, `apps`).
  - Frontend (`/app/frontend/src/pages/ProjectReportFormPage.jsx`): Calls für `/users/active` und `/project-reports/work-templates` in zwei separate `try/catch`-Blöcke aufgeteilt → ein Fehler killt nicht mehr beide Listen. URL geändert: `/users` → `/users/active`.
  - Verifiziert: Mitarbeiter-Login (`ma1@test.com`) → Dropdown zeigt 10 aktive User (Anna Weber, Max, Christine Ecker, Sebastian Heidmann, Marcel Pfefferkorn, Martin Mull + Admins), `Textbaustein einfuegen…` Dropdown ist sichtbar. `/api/users` weiterhin 403 für Nicht-Admins.

- **2026-02 — P0 Hotfix (Sening Tankbeleg-Parser: Bitmap-Digit-Decode):**
  - Sening MultiFlow rendert manchmal die letzte Ziffer der Menge als Sening-Bitmap-Encoding (Eichmarker). Beispiel: 1296 L wurde als 129 erkannt (ASCII), 154 L als 15.
  - **Reverse-Engineering der Sening-Bitmap-Codierung** anhand 5 echter Hex-Dumps (Belege 16940-16944) ergab eine eindeutige Formel:
    ```
    bitmap_4_bytes = [byte1] [byte2] 0x72 0xd3
    byte1 = 0x83 + d * 8     (d = Ziffer 0..9)
    byte2 = 0x12 - d
    ```
  - Verifiziert: a3 0e 72 d3 = "4" (Beleg 154 L), b3 0c 72 d3 = "6" (Beleg 1296 L), 03 8e 3a c8 = kein Ziffer-Bitmap (Endemarker bei 23 L).
  - Neue Funktion `decode_sening_bitmap_digit()` in `tankbeleg_pi.py` decodiert die Bitmap-Bytes mathematisch zur fehlenden Ziffer (Doppelpruefung byte1+byte2 fuer Robustheit).
  - **Ergebnis**: Alle 5 echten Belege (23/41/1148/154/1296) werden jetzt KORREKT automatisch erkannt - ohne manuelle Eingabe.
  - Falls Sening jemals ein anderes Bitmap-Pattern verwendet (unwahrscheinlich, da mathematisch konsistent fuer alle Ziffern 0-9), wird der Beleg als `needs_review` mit Hex-Hinweis fuer Pattern-Erweiterung markiert.
  - File: `/app/backend/static/tankbeleg_pi.py`

- **2026-02 — P1 Feature (Schausteller-Portal: Bezahlvorgang nach Abbruch wiederaufnehmen):**
  - Neuer Button „Bezahlvorgang abwickeln" pro Buchung im Dashboard (`/app/frontend/src/pages/schausteller/Dashboard.jsx`).
  - Sichtbar nur bei `payment_status === "pending_payment"` UND `!deposit_paid` UND `payment_method !== "rechnung"`.
  - Handler `handlePayBooking` in `SchaustellerAnmeldungPage.jsx` ruft den bestehenden Endpoint `POST /api/payments/checkout/deposit` auf → neue Stripe-Session → Redirect.
  - Kein Backend-Change nötig: der Endpoint prüft `signup.deposit_paid`, nicht eine alte Session, also kann er ein abgebrochenes Signup neu abwickeln.
- **2026-02 — P0 Hotfix (Mosquitto Zombie-Prozess):**
  - `broker/restart` und `_regenerate_passwd_file()` härter gemacht: Primärversuch `Restart-Service` mit Status-Verifikation, Fallback Stop-Service + Kill aller `mosquitto.exe` + Start-Service.
  - Löst den Fall, wo aktive DSE890-Clients das saubere Stoppen verhindern und ein Zombie-Prozess Port 1883 blockiert → Service `Stopped`, aber Port belegt, neuer Start schlägt mit `StartServiceFailed` fehl.
- **2026-02 — P1 Bugfix (Mosquitto Passwd-Datei vs. DB):**
  - Neuer Endpoint `POST /api/mqtt/passwd-file/import-to-db` (dry-run + apply) in `backend/routes/mqtt_config.py`.
  - Fuzzy-Matching von `gw_<token>` → `devices.serial_number/user_field/name` oder `generators.serial_number/name`.
  - UI-Erweiterung in `MqttConfigPage.js`: „In DB importieren…" Button im file-only Block zeigt Plan mit link/conflict/unmatched-Status, dann bestätigter Apply-Schritt.
  - Sichert die historisch gewachsenen 13 Lichtmast-User in die DB, damit künftige Passwort-Rotation über das Portal möglich ist und die passwd-Datei bei versehentlichem Overwrite aus der DB rekonstruiert werden kann.
- **2026-02 — P1 Bugfix (iOS Mobile App Login):**
  - Root cause: `/app/frontend/src/lib/api.js` checked `origin.includes('localhost')` → matched Capacitor native origin `capacitor://localhost` → `BACKEND_URL = ''` → login went to `capacitor://localhost/api/auth/login` (404).
  - Fix: Detect Capacitor/Ionic protocol (`capacitor:` / `ionic:`) or `window.Capacitor.isNativePlatform()` → always use `REACT_APP_BACKEND_URL` (falls back to `https://eventenergie.app`).
  - Requires rebuild & redeploy of the iOS/Android app (`bash desktop/build-mobile.sh ios|android` with `REACT_APP_BACKEND_URL=https://eventenergie.app`).
- **2026-02 — P1 UI Fix (Pi Touchscreen):**
  - Removed "Standort (optional)" field from Beleg-Zuordnung — only "Bemerkung" remains.
  - Added prominent **"Lager / Testlauf"** quick-action button above the Auftrag dropdown (orange, single-tap booking to Lager).
  - Fixed backend `lager_entry` key naming (`pk` → `primary_key`, `name`/`customer_name` → `event`/`contact_name`) so the entry is correctly cached in Pi SQLite and appears in the orders dropdown.
- **2026-02 — P0 Fix: Pi Sync 404.** `tankbeleg_pi.py` now uses `_api_base()` helper that appends `/api` exactly once. Verified via curl (HTTP 200).
- Heuristic Sening receipt parser + ESC/POS bitmap → PNG rendering on Pi.
- Null-Modem serial handshake (`dsrdtr=False`), Sening Poll reply `0x00`.
- Frontend fuel management displays PNG receipts.
- "Angemeldet als" multi-company display in Schausteller login.

## In Progress
- User verification of UI changes (requires Pi script re-download + UI service restart).

## Backlog (prioritized)
### P2
- GPS polling timeout hardening in `tankbeleg_pi.py` (currently disabled via config).
- Beleg-Counter Jahreswechsel-Logik (reset Jan 1st).
- Admin-Button "KI neu analysieren".
- Admin-Button "Alle Mitarbeiter-Dateien lokal sichern".
- Lastdiagramm Live-Test.
- GPS support for Kirmeskiste.
- Suppress Chromium "Translate" popup globally on Pi kiosk.
- FinTS error 9078 — waiting for ZKA propagation.

## Key Files
- `/app/backend/static/tankbeleg_pi.py` — Pi printer emulator, parser, PNG renderer, sync.
- `/app/backend/static/tankbeleg_ui.py` — Pi touchscreen UI.
- `/app/backend/routes/fuel_receipts.py` — Sync endpoints, PNG serving, `/pi/orders`, `/pi/drivers`.
- `/app/frontend/src/pages/FuelManagementPage.jsx` — Portal receipt view.

## Key Endpoints
- `POST /api/fuel-receipts/sync` — Bulk sync from Pi (no auth).
- `GET /api/fuel-receipts/{id}/pdf`, `/bitmap.png`.
- `GET /api/fuel-receipts/pi/orders`, `/pi/drivers`.
- `GET /api/download/tankbeleg-pi-script` — Serves the current Pi script.
- `GET /api/download/tankbeleg-ui-script` — Serves the current UI script.

## Offline Behavior (confirmed)
- Pi caches orders + drivers in local SQLite (`orders_cache`, `drivers_cache`).
- Receipts are written to local SQLite immediately upon serial capture.
- Assignment (including Lager) works offline — changes mark `synced=0` and are flushed when backend is reachable.
- Sync runs periodically (`sync_interval`, default 60 s) and only sends unsynced receipts.

## 3rd Party Integrations
- OpenAI GPT-4o via Emergent LLM Key (AI document categorization).
- Stripe (user-provided keys).
- FinTS banking (user credentials + product ID).

## Hardware Deployment Loop
Every change to `tankbeleg_pi.py` or `tankbeleg_ui.py`:
1. Agent pushes to repo.
2. User `git pull` on Windows Server + `sudo supervisorctl restart backend`.
3. On Pi:
   ```
   sudo curl -sL -o /opt/tankbeleg/tankbeleg_pi.py "https://eventenergie.app/api/download/tankbeleg-pi-script?v=$(date +%s)"
   sudo curl -sL -o /opt/tankbeleg/tankbeleg_ui.py "https://eventenergie.app/api/download/tankbeleg-ui-script?v=$(date +%s)"
   sudo systemctl restart tankbeleg_pi tankbeleg_ui
   ```
