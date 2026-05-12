# Kirmes Billing & HR System – PRD

## Original Problem Statement
Comprehensive Kirmes (Fairground) billing and HR management system: hardware integration for fuel receipts (Tankwagen-Pi), HR document management, chat, task scheduling, role-based permissions, and Messprotokoll (Measurement Protocol) generation following IHK / DIN VDE 0100-600 / DGUV V3 standards.

User language: **German** (Agent must respond in German).

## Core Modules
- Orders / Auftragsdetails (with documents, fuel receipts, GPS, Messprotokolle)
- Time Tracking & Presence (HubPage)
- HR Document management
- Generator / Energy Monitoring (DSE USB Modbus – BLOCKED hardware)
- Service Plans
- Tankwagen-Pi Kiosk (PIN login via 6-digit DOB)
- Schausteller Portal (Kirmes Anmeldung)
- Messprotokoll PDF Generator (ReportLab)

## Implementation Log
### Feb 2026 – Admin Copy-Funktion fuer Auftraege (P0)
- ✅ **Backend** `POST /api/orders/epirent/{order_pk}/copy-to` (Admin-only):
  - Body: `{ target_order_pk, asset_ids: [...], generator_ids: [...] }`.
  - Artikel werden 1:1 dupliziert (neue UUID, Position/Status/Kommentare bleiben; Audit-Kommentar "Kopiert aus Auftrag #X" haengt an).
  - Generatoren werden zusaetzlich an `order_settings.manual_generator_ids` des Ziel-Auftrags angehaengt (`$addToSet`) — Quelle behaelt die Zuordnung (kopieren, nicht verschieben).
  - Auto-Deployment-Eintrag fuer jeden neu zugeordneten Generator wird in `deployment_history` angelegt (analog zu `add_manual_generator`).
  - Validierung: Self-Copy 400, leere Auswahl 400, unbekanntes Ziel 404, Non-Admin 403.
- ✅ **Frontend** `OrderDetailPage.js`:
  - "Kopier-Modus"-Toggle in Header von Generatoren-Panel und Artikel-Section (nur Admin, nur wenn Items vorhanden).
  - Checkbox-Spalte in Asset-Tabelle + Checkbox je Generator-Card.
  - Floating Action-Bar mit Counts + "Kopieren nach...".
  - Ziel-Auftrags-Picker-Dialog (debounced Search via `/orders/epirent-search/quick`).
  - Confirm + Toast + State-Reset nach Erfolg.
- ✅ Tests: Backend 8/8 PASS (test_copy_to_order_iteration67.py), Frontend Playwright e2e PASS (Toggle, Checkboxen, Action-Bar, Picker, Confirm, Toast, Regression Move-Dialog).


## Implementation Log
### Feb 2026 – Auto-Learn Verifikation
- ✅ **MQTT Auto-Learn Logik final verifiziert** (Feb 2026):
  - 7 Unit-Tests in `/app/backend/tests/test_mqtt_auto_learn_gps.py` (kein dotenv, kein echtes Mongo — FakeDB In-Memory).
  - Verifiziert alle 3 Auto-Learn Match-Pfade in `_process_message` (mappings_cache, generators_cache prefix, devices_cache module_uid) und das nachgelagerte GPS-Routing in `_process_gateway_gps` via gelerntem `dse_gateway_uid`.
  - Inkl. negativem Test: unbekannte Module-UIDs werden korrekt als `rejected_no_module_match` geloggt und updaten KEIN Device.
  - Resultat: **7/7 PASS**. User bekommt Deploy-Freigabe fuer mqtt_service.py.



### Feb 2026 – Einsatzzentrale Pi-Kiosk (Workspace komplett)
- ✅ **Workspace-Maske** auf dem Pi nach Auftrags-Auswahl:
  - **Projekt-Header** (Auftrag-Nr, Event, Kunde, Adresse, Event-/Dispo-Zeitraum, Bearbeiter) aus EpiRent.
  - **Wetter-Widget**: Open-Meteo-Forecast fuer den Veranstaltungszeitraum (max. 16 Tage in die Zukunft). Pro Tag: Code+Emoji, Min/Max-Temp, Niederschlag mm + Wahrscheinlichkeit, Wind-Boeen. KEIN API-Key noetig.
  - **4 Tiles**: Maschinenliste (Cog/emerald), Einsatztagebuch (BookOpen/slate), Plaene (FileText/blue), Standortliste (MapPinned/fuchsia). Klick oeffnet Tile-Panel-Vollbild (aktuell Platzhalter).
- ✅ **Backend** neue Endpoints:
  - `GET /api/einsatzzentrale/orders/{pk}` — Auftrags-Kurzbeschreibung inkl. center_lat/lng aus order_settings.
  - `GET /api/einsatzzentrale/weather?lat=&lng=&start=&end=` — Open-Meteo-Proxy (forecast + archive), liefert deutsche Labels + Emojis. Daily-Felder: temp_max/min, precipitation_sum, precipitation_probability_max, wind_speed/gusts, sunrise/sunset, weather_code.
- ✅ Smoke-Test mit Anna Weber: Login -> Order-Filter -> Tile-Grid sichtbar.

### Feb 2026 – Einsatzzentrale Pi-Kiosk
- ✅ **Backend** `routes/einsatzzentrale.py`:
  - `GET /api/einsatzzentrale/users` (PUBLIC, kein Auth) — liefert nur Mitarbeiter+Freelancer (id, name, role; KEINE Emails/Telefon).
  - `POST /api/einsatzzentrale/login` — Login via `user_id + password`. Admins/Kunden werden mit 403 geblockt.
  - `GET /api/einsatzzentrale/orders` — aktive Auftraege im Zeitfenster heute -14d/+14d (event_start/end oder dispo_start/end Overlap-Check). Freelancer sehen nur eigene Auftraege.
- ✅ **Frontend** `EinsatzzentralePiPage.jsx` (Touch-Kiosk, Dark Theme) mit State-Machine:
  1. User-Grid (Avatar mit Initialen, Farbcodierung Mitarbeiter/Freelancer, Suchfeld).
  2. Passwort-Eingabe fuer ausgewaehlten User.
  3. Auftrags-Auswahl (Cards mit Event/Kunde/Adresse/Zeitraum, Suchfeld, Zeitfenster-Hinweis).
  4. Workspace-Platzhalter (Inhalt kommt vom User).
- ✅ Header mit prominentem **"Abmelden"-Button** (rot) in jeder Post-Login-Phase. Logout setzt sessionStorage zurueck und springt zur User-Auswahl.
- ✅ Route `/einsatzzentrale` (PUBLIC, kein ProtectedRoute) — Pi startet direkt darauf.


### Feb 2026 – Einsatztagebuch Auswertungs-Seite
- ✅ **Neuer Backend-Endpoint** `GET /api/orders/diary/auswertung`:
  - Aggregiert alle Diary-Eintraege pro Auftrag (nur Auftraege mit >=1 Eintrag).
  - Pro Auftrag: total/open/resolved/nachtrag_count, avg_duration_minutes, total_minutes, unique_callers, recurring_callers_count, callers-Liste (sortiert nach Anruf-Haeufigkeit).
  - Summary: total_orders, total_entries, total_open, total_resolved, Ø-Bearbeitungszeit, Gesamtzeit.
  - Freelancer-Filter: nur eigene Auftraege.
- ✅ **Neue Frontend-Seite** `/verwaltung/auswertung/einsatztagebuch` (`AuswertungEinsatztagebuchPage.jsx`):
  - 6 Stat-Cards oben (Auftraege/Stoerungen/Behoben/Offen/Ø-Dauer/Gesamtzeit).
  - Volltextsuche (Auftrag-Nr, Kunde, Adresse, Event).
  - Auftrags-Liste: jeder Eintrag aufklappbar, zeigt Anrufer-Statistik mit Wiederholungstaeter-Badge, Nachtrag-Hinweis, "Oeffnen"-Link.
- ✅ **Tile** im AuswertungIndexPage hinzugefuegt (slate-farbig, BookOpen-Icon).
- ✅ Test in `test_order_trupps.py` ergaenzt — Auswertung-Endpoint laeuft 4/4 PASS.

### Feb 2026 – Einsatztagebuch: Trupp-Management (pro Auftrag)
- ✅ **Trupp-CRUD pro Auftrag** (`/app/backend/routes/order_diary.py`, neue Collection `order_trupps`):
  - Endpunkte: `GET/POST /api/orders/{pk}/trupps`, `PUT/DELETE /api/orders/{pk}/trupps/{tid}`.
  - Auto-Naming: leerer Name -> "Trupp N" (count + 1).
  - Mitglieder pro Trupp: max. 4 (Freitext-Strings).
  - Beim Loeschen eines Trupps wird er aus allen Diary-Eintraegen entfernt (`$pull`).
- ✅ **assigned_trupp_ids** auf Diary-Eintraege erweitert (`POST` + `PUT`).
- ✅ **Status-Logik abgeleitet**: `is_busy=True` wenn der Trupp einer **offenen** Stoerung zugewiesen ist. Wechselt automatisch auf `False` sobald die Stoerung als "Behoben" markiert wird. Keine doppelte State-Haltung.
- ✅ **Frontend (`OrderDetailPage.js`)**: Trupp-Panel unter "Zurueck zur Uebersicht" (nur sichtbar wenn Diary-Tab aktiv). Karten-Grid mit Status-Punkt (gruen=verfuegbar, rot=unterwegs), Inline-Bearbeiten von Name + 4 Mitglieder-Feldern, "+ Trupp hinzufuegen", Loeschen. In der "Neue Stoerungsmeldung"-Form werden Trupps als Chips zur Multi-Auswahl angeboten. Zugewiesene Trupps werden als Badges in jedem Diary-Eintrag angezeigt.
- ✅ **Tests**: `/app/backend/tests/test_order_trupps.py` – CRUD, Auto-Naming, Busy-Wechsel verifiziert (2/2 PASS).

### Feb 2026 – Current Session (continued)
- ✅ **Leaflet-Crash Final-Fix: Strict-Number-Check statt Number()-Coercion** (Feb 2026, Bug fix Iteration 4):
  - **Root Cause Iteration 1**: Vorher hatte ich `Number.isFinite(Number(g.latitude))` benutzt. Problem: `Number(null) === 0` und `Number.isFinite(0) === true` -> `null`-Koordinaten kamen durch den Filter durch, Leaflet bekam `position=[0, 0]` oder `[null, null]` und crashte mit "can't access property lat, e is null".
  - **Fix**: Filter strikt auf `typeof g.latitude === "number" && isFinite(g.latitude)` umgestellt. `Number.isFinite()` (ohne Wrapper) macht KEINE Type-Coercion - blockt `null`, `undefined`, Strings sauber, laesst echte 0er aber durch (gueltige Koordinate am Aequator).
  - Auch in `OrderDetailPage.js` (Generator+Asset Marker, FitBounds, Asset-Modal), `EnergyMonitoringPage.js` und `EnergyMonitoringDetailPage.js` umgestellt.
  - **Stress-Test verifiziert**: Generator mit `latitude=None` zu echtem Auftrag manuell zugeordnet -> Seite laedt sauber, Generator erscheint in Liste mit "MANUELL"-Badge, wird auf Karte korrekt **ausgeblendet**, 0 Page Errors.
  - **Wichtig fuer User**: Live-Build `main.3cf9f80b.js` enthaelt noch alten Code -> bei naechstem Deploy muss der neue Bundle-Hash ausgerollt werden.

- ✅ **MQTT GPS-Routing: Modul-UID aus JSON-Payload-Key matchen** (Feb 2026, Bug fix Iteration 3):
  - **Root Cause**: DSE890-Gateway publiziert GPS unter `eventenergie/{ANLAGE}/{GATEWAY-UID}/gps`. Im Topic steht die **Gateway-UID** (z.B. `1912C4E76883D4B`, 15 Hex), im **JSON-Payload als Top-Level-Key** steht die **Modul-UID** (z.B. `6D2B5CD695`, 10 Hex = `dse_module_uid` im Portal). Vorherige Match-Logik basierte auf Topic-Segmenten → unmoeglich zu matchen.
  - **Fix**: `_process_gateway_gps` parst jetzt die JSON-Payload-Keys (`{"6D2B5CD695": {"LAT": x, "LON": y}}`) und matcht diese gegen `dse_module_uid` der Devices. Unterstuetzt Multi-Modul-Payloads (mehrere UIDs im selben Topic) — jedes Modul bekommt seine individuelle Position.
  - Sekundaere Fallbacks: Substring-Match in Mapping/Generator-Prefix, Live-DB-Regex-Suche bei Cache-Stale, Flat-Format-Fallback ohne Modul-Wrapper.
  - **Tests**: Single-Module-Match ✅ und Multi-Modul (2 Devices unter 1 Gateway) ✅ direkt gegen Live-Funktion verifiziert.
  - GPS-Log neue Routes: `gateway_module_match` (Erfolg), `rejected_no_module_match` (Modul-UID nicht im Portal hinterlegt).

- ✅ **GPS-Diagnose-UI fuer Admin** (`/admin/gps-diagnose`) (Feb 2026): Drei Tabs
  - **Status & Duplikate**: Liste aller Devices + Generators mit Koordinaten, Alter (Min/h/Tage farblich kodiert), Duplikat-Warnung wenn mehrere Eintraege dieselbe Position teilen.
  - **Live-Log**: zeigt die letzten 200 MQTT-GPS-Events mit Topic, Route (`per_generator`/`per_device`/`gateway_fallback`/`rejected`) und welches Geraet getroffen wurde. "0 Events" Warnung wenn aktuell nichts reinkommt.
  - **Reset**: Stundenfilter ("Aelter als N Stunden"), loescht stale `latitude`/`longitude`/`last_gps_update` damit beim naechsten echten Telegramm die korrekte Position pro Geraet neu geschrieben wird.
  - Backend: `routes/admin_gps.py` mit `GET /api/admin/gps/status`, `GET /api/admin/gps/log`, `POST /api/admin/gps/reset`. Admin-Only via JWT.
  - Logging: jedes verarbeitete GPS-Event landet in `mqtt_gps_log` (max 1000 Eintraege Auto-Pruning).

- ✅ **P0 Frontend-Crash Fix (React-Leaflet "lat is null")** (Feb 2026):
  - `OrderDetailPage.js`: Generators + Assets mit null/undefined Koordinaten werden vor `<Marker position={[lat, lng]}>` herausgefiltert (`Number.isFinite` Check). `FitBounds` ignoriert ungueltige Punkte. Asset-Modal-Map zeigt Fallback "Keine GPS-Position vorhanden".
  - `EnergyMonitoringPage.js`: Map-Block rendert nur Standorte mit gueltigen `gps_lat`/`gps_lon`. MapContainer-Center nutzt den ersten validierten Standort.
  - `EnergyMonitoringDetailPage.js`: Map-Block gegated auf `Number.isFinite(location.gps_lat) && Number.isFinite(location.gps_lon)`.
  - Verifiziert per Screenshot: Auftrag 260095-01 mit DSE L401-Generator laedt ohne Crash. Lint clean.

- ✅ **MQTT-GPS-Fix: Gateway-genaue Zuordnung statt Anlagen-Spreizung** (Feb 2026):
  - **Bug**: `_process_gateway_gps` hat GPS-Updates auf den **Anlagen-Prefix** (z.B. `eventenergie/35072/`) gespreizt. Bei mehreren DSE890-Gateways mit eigenen GPS-Antennen unter derselben Anlage haben sich die Positionen gegenseitig ueberschrieben → "alle auf einer Position".
  - **Fix**: `_process_gateway_gps` matcht jetzt streng auf den vollen Gateway-Topic (inkl. UID, z.B. `eventenergie/35072/1922A5D409E1601`). Mappings/Generators/Devices werden nur dann beruehrt, wenn ihr Topic-Prefix mit diesem Gateway uebereinstimmt. Zusaetzlicher Fallback: wenn nichts gefunden wird, sucht der Service Devices mit passender `dse_module_uid` aus dem letzten Topic-Segment.
  - **Bonus**: `_process_gps_device` propagiert GPS jetzt auch auf den verknuepften virtuellen Generator (`dev-<id>`) UND auf einen echten Generator-Eintrag mit gleicher `serial_number`, sodass `list_generators` direkt die neue Position zurueckgibt.
  - Lint clean, Backend startet sauber. **User-Test auf Live ausstehend.**

- ✅ **Tankbeleg-Pi v1.7.13 — 0L-Phantom-Filter, Timezone & Heizöl-Default** (Antwort auf User-Bugreport zu Belegen 16974/16975 + -1h Verschiebung + Diesel/Heizöl):
  - **Timezone-Fix**: `now_berlin()`-Helper mit `ZoneInfo("Europe/Berlin")` ersetzt alle `datetime.now()`-Aufrufe für Belegzeitstempel. Pi auf UTC liefert jetzt korrekte CEST/CET-Zeiten (DST automatisch). Behebt -1h-Offset auf den Belegen.
  - **0L-Phantom-Filter verschärft (v1.7.13)**: Stub wird nur noch erstellt wenn (1) Sening-Header vorhanden, (2) M+-Region enthält Zahlenwert > 0, UND (3) `parse_receipt_sening` lieferte `menge_liter > 0`. Probedrucke mit "0" oder "00.0" als Mengenangabe werden nicht mehr in der DB gespeichert. Behebt Geister-Belege wie 16974/16975.
  - **Heizöl statt Diesel**: `default_fuel_type` in DEFAULT_CONF + ausgelieferter `tankbeleg_pi.conf` von "" auf `"heizoel_leicht"` umgestellt. Blinder `\bDiesel\b`-Fallback in `parse_receipt_sening` entfernt — bei mehrdeutigem Bitmap bleibt fuel_type=None und der Config-Default greift in `enrich_receipt_with_heuristics`.
  - OTA-Auslieferung verifiziert: `/api/download/tankbeleg-pi-script` zeigt v1.7.13 + neue Funktionen, `/api/download/tankbeleg-pi-config` enthält `default_fuel_type = heizoel_leicht`.
  - Pi zieht Update beim nächsten OTA-Tick (≤60s) automatisch.

- ✅ **Tankbeleg-Pi v1.7.8 — TM-U295-Spec-Konform (offizielles PDF abgearbeitet)**: User hat `https://www.jarltech.com/.../TM-U295_spc_I.pdf` geliefert. Kompletter Status-Reply-Code dagegen verifiziert.
  - **Fix 1**: `DLE EOT n=4` entfernt (existiert NICHT in TM-U295, war TM-U220 receipt-Drucker). Stattdessen `n=5` (Slip Paper Status) hinzugefuegt.
  - **Fix 2**: `sening_reply_byte` Default von `0x00` → `0x12`. TM-U295-Spec definiert Bit 1+4 als FIXED ON in jedem Status-Byte (`00010010 = 0x12`). `0x00` verletzt diese Invarianten und wird vom Sening wahrscheinlich als "Drucker offline" gewertet.
  - **Fix 3**: `ESC c 3 n` / `ESC c 4 n` (4-Byte Paper-Sensor-Konfig vom Sening) werden jetzt silent konsumiert statt im Beleg-Buffer zu landen → keine Mistdaten mehr im Beleg.
  - **Fix 4**: `ESC u` ist 3 Bytes (mit drawer-Parameter), nicht 2.
  - **Fix 5**: Erweiterte Logs mit Spec-Referenzen damit man bei Problemen direkt im Code sieht welcher Spec-Eintrag gemeint ist.
  - 31/31 Tests grün (5 neue Tests für DLE EOT n=5, n=4-no-reply, ESC c 3/4 silent-consume, ESC c partial buffering).

- ✅ **Tankbeleg-Pi v1.7.7 — DSR/DTR Bug behoben (FINAL FIX für Sening "Drucker nicht erreichbar")**: Live-Diagnose vom User hat bewiesen: Sening MultiFlow nutzt 3-Wire Null-Modem-Kabel. `DSR=False, CTS=False, CD=False, RI=False`. Mit `dsrdtr=True` (v1.7.5/v1.7.6) hat pyserial deshalb auf DSR=High vor jedem write() gewartet → ALLE Status-Replies blockiert → Sening lief in Timeout. Fix: zurück auf `dsrdtr=False, xonxoff=False, rtscts=False`. Manueller Test des Users zeigt korrektes RX (`1b b3 ff` Polls alle ~600ms). 26/26 Tests grün.
- ✅ **Sening Reply-Byte-Cycler Diagnose-Tool**: `static/sening_reply_cycler.py` (Download `/api/download/sening-reply-cycler`). Probiert systematisch 13 Kandidaten-Bytes (0x00, 0x12, 0x14, 0x16, 0x10, 0x18, 0x1A, 0x06, 0x90, 0x80, 0x40, 0x7F, 0xFF) durch und meldet welcher Wert den Sening dazu bringt einen Druckjob zu senden (Treffer-Heuristik: >50 Bytes nach Reply). Manuelles Workaround falls 0x00 nach v1.7.7 immer noch nicht reicht.

- ✅ **Tankwagen Live-Raw-Stream (v1.7.6)**: Live-Debug-Helper. Pi pusht alle empfangenen UND gesendeten Bytes (RX/TX) batched zum Backend, neue Frontend-Seite `/tankwagen/live-stream` (Admin-only) tail't mit 1s-Polling.
  - **Backend**: Neuer Routes-Modul `routes/tankwagen_raw_stream.py` mit `POST /push` (anonym/pi_id-auth), `GET /tail` (since_ts long-poll-light), `DELETE` (clear). MongoDB-Collection mit TTL-Index 24h + max 5000 Eintraege/Pi. Lazy index-init (motor-async kompatibel).
  - **Pi-Side**: Neue `RawStreamPusher`-Klasse (Daemon-Thread, batched flush). Hooks in `read_receipt()` (RX) und neuer `_reply()`-Helper in `_handle_status_queries` (TX). Konfig-Keys `raw_stream_enabled`, `raw_stream_flush_sek`, `raw_stream_max_batch`. Default OFF.
  - **Frontend**: `TankwagenLiveStreamPage.js` mit Pi-Filter, Richtungs-Filter, Auto-Scroll, Live-Stats (RX/TX Counts + Bytes), Pause/Play, Export als .log, Clear-Button. Heuristische Annotation bekannter Sequenzen (Sening-Poll ESC B3, DLE EOT, ESC v, GS r, ESC u). Dark Terminal-Optik mit Hex+ASCII Spalten.
  - **Switch-Skript** ergaenzt: setzt `raw_stream_enabled=true` automatisch beim Switch zur Test-Umgebung.
  - 7 neue E2E-Tests (`test_tankwagen_raw_stream.py`) gegen die laufende Backend-Instanz, alle gruen. Gesamttests Tankbeleg: 26/26 gruen.

- ✅ **Tankbeleg-Pi v1.7.5 für Test-Umgebung**: Sening Handshake & FIFO-Overrun fix.
  - **Flow-Control zurück**: `xonxoff=False, dsrdtr=True, rtscts=False`. Vorheriger v1.7.4-Versuch mit `xonxoff=True` hat den Sening eingefroren ("Drucker antwortet nicht" / "Papier einlegen") weil 0x11/0x13 als reguläre Datenbytes vom Sening kamen, von pyserial aber als XON/XOFF interpretiert wurden → Schreibblockade.
  - **FTDI Latency-Timer Fix**: Neuer Helper `_set_ftdi_latency_timer()` setzt `/sys/class/tty/ttyUSBx/device/latency_timer` auf 1ms (statt Kernel-Default 16ms). Löst den 16-Byte UART-FIFO-Overrun (Symptom "1316L → 13L") ohne Software-Flow-Control. Konfigurierbar via `ftdi_latency_ms` in `/etc/tankbeleg_pi.conf`.
  - **Erweiterte Epson-Status-Antworten** im `_handle_status_queries`:
    - `DLE EOT n` (n=1..4) → `0x12` (online, paper OK) [vorher schon vorhanden]
    - `DLE ENQ n` → `0x00`
    - `ESC v` (TM-U295 legacy paper sensor) → `0x00` (paper present, not near-end) **NEU**
    - `ESC u` (peripheral status) → `0x00` **NEU**
    - `GS r n` (transmit status, paper roll/drawer) → `0x00` **NEU**
    - `ESC B3 n` (Sening proprietary poll) → `sening_reply_byte` (default `0x00`)
    - Partial-Prefix-Buffering korrigiert (ESC v/u sind 2 Bytes, DLE/GS/ESC B3 sind 3 Bytes)
  - **Logging**: FTDI-Latency-Verifikation, Flow-Control-State, unbekannte ESC-Sequenzen mit Hex-Preview.
  - 14/14 neue Unit-Tests grün (`test_tankbeleg_status_replies.py`), bestehende 5 Fuel-Default-Tests weiterhin grün.
  - OTA liefert v1.7.5 (79.490 Bytes) am `/api/system/ota/pi/tankwagen/download` aus → bereit für Test-Pi-Flash.

- ✅ **Karten global auf Hybrid + Layer-Switcher in JEDER Karte**: User wollte den Layer-Switcher auch in der Modal-Mini-Map und Hybrid als Default ueber alle Karten. Umsetzung:
  - Neue Komponente `/app/frontend/src/components/MapTileLayer.jsx` kapselt Tile-Layer + Switcher (OSM/Sat/Hybrid). Auswahl persistiert in `localStorage["mapLayer"]`, Default ist "hybrid".
  - 7 Stellen umgestellt: OrderDetailPage (grosse Karte + Modal-Mini-Map), GpsLockPicker, EnergyMonitoringPage, GeneratorDetailPage, GeneratorDashboardPage, EnergyMonitoringDetailPage, DeviceManagementPage.
  - Jede Map hat jetzt automatisch den Layer-Switcher oben rechts und bootet in Hybrid (Esri Sat + transparente Stamen-Strassen-Labels).
  - E2E gruen (localStorage-Wert "hybrid" verifiziert, Mini-Map im Asset-Modal hat Layer-Control, Sat-Tiles werden geladen).

- ✅ **Karten-Layer (Satellit/Hybrid) + Marker-Klick + Verschieben**: User-Wuensche umgesetzt:
  - **Layer-Switcher** oben rechts auf der Karte: "Karte (OSM)" / "Satellit" (Esri World Imagery - frei, Google-Sat-vergleichbar) / "Hybrid" (Sat + transparente Strassen-Labels). Auswahl wird in localStorage persistiert.
  - **Marker-Klick oeffnet direkt das Asset-Detail-Modal** (statt Popup) - schnellerer Workflow, Modal hat alle Details + Kommentare + Move-Funktion.
  - **Asset in anderen Auftrag verschieben**: Neuer Button im Modal "In anderen Auftrag verschieben" oeffnet Picker-Dialog. Live-Suche (debounced 300ms) ueber Event-Name/Auftragsnr/Kundenname/Adresse. Auswahl + Bestaetigung verschiebt den Eintrag, behaelt Position/Status/Kommentare und ergaenzt automatisch einen `kind:'system'`-Audit-Kommentar.
  - Backend: 2 neue Endpoints `PATCH /assets/{id}/move`, `GET /epirent-search/quick` (Quick-Order-Search, exclude_pk Param). E2E gruen: Asset auf Auftrag #3 angelegt → verschoben nach #19 → in #19 wiedergefunden inkl. Audit-Kommentar → Cleanup.

- ✅ **Asset-Filter wirkt jetzt auch auf der Karte**: User-Wunsch nach der Suchen/Filter-Optimierung. Wenn man "Tank" filtert oder nach "Bühne" sucht, werden nur die passenden Marker auf der Map angezeigt; FitBounds zoomt automatisch auf die gefilterten Positionen. Tabelle und Map nutzen jetzt eine gemeinsame `filteredAssets`-Quelle - keine doppelte Filter-Logik. E2E gruen (Filter=all → 6 Marker, Filter=Tank → 4 Marker bei gleichem Datenstand).

- ✅ **Asset-Liste: Volltextsuche + Typ-Filter + neuer "Tank"-Typ**: User Wunsch:
  - "Tank" als neuer Artikeltyp ergaenzt (Icon: lucide `Fuel`, Maps-Marker als Tankwagen-SVG)
  - Volltextsuche-Bar oben in der Asset-Liste: durchsucht Bezeichnung, Plus Code, Ersteller, Koordinaten UND Kommentar-Text (Ein-Klick-X zum Zuruecksetzen)
  - Typ-Filter-Dropdown rechts neben der Suche: zeigt nur Typen die tatsaechlich vorhanden sind, jeweils mit Count (z.B. "Tank (2)"); Auto-Hide leerer Typen
  - "Zuruecksetzen"-Link wenn Suche/Filter aktiv
  - Live-Counter "X von Y angezeigt" rechts
  - Empty-State wenn Filter nichts findet (zeigt aktive Suche/Typ in der Meldung)
  - E2E gruen: Typ-Dropdown enthaelt Tank, Filter zeigt Counts, Filter=Tank reduziert Liste, Suche=Suchtest filtert auf 2 Zeilen, Cleanup OK

- ✅ **Asset-Kommentarfunktion (Verteiler/Lichtmast/Stromerzeuger/Tank)**: User wollte unter den positionierten Artikeln im Auftragsdetail die Moeglichkeit zu kommentieren ("Steht morgen ab", "Defekt", etc.). Implementiert:
  - 2 neue Endpoints: `POST /api/orders/epirent/{order_pk}/assets/{asset_id}/comments` (add) und `DELETE …/comments/{comment_id}` (nur Autor oder Admin)
  - Kommentare als embedded Array im `order_assets`-Dokument (1 DB-Read fuer Asset+Comments)
  - Pi-UI im Asset-Detail-Modal: Liste mit Avatar-User-Icon, Zeitstempel, Loesch-Icon (nur eigene/Admin); Eingabe-Textarea (max 2000 Zeichen) mit Enter-zu-senden + Send-Button mit Loader
  - **Direkt beim Anlegen mit-eingebbar**: Kommentar-Textarea im "Artikel positionieren"-Formular, wird automatisch an den frisch angelegten Asset gepostet (1 Action statt 2)
  - Asset-Tabelle zeigt Badge `💬 N` hinter dem Label fuer Assets mit Kommentaren
  - Optimistic UI: neuer Kommentar erscheint sofort ohne Modal-Reload
  - E2E ueber Playwright (Login, Asset+Kommentar in einem Schritt anlegen, Modal oeffnen, Kommentar verifizieren, Cleanup) - alles gruen

- ⏪ **Kraftstoff-Override am Pi rueckgaengig** (Eichrecht-konform): Auf User-Hinweis Pi-UI Buttons + Backend-Sync-Update entfernt. Fahrer darf den vom Sening gemessenen Kraftstoff NICHT manuell aendern (sonst manipulierbar). Parser-Fix (kein silent diesel) bleibt; `default_fuel_type` als Deployment-Konfig bleibt fuer den Fall dass Sening nichts erkennen liess. Fuer die 4 falsch klassifizierten Belege: User schickt morgen einen Hex-Dump, dann erweitere ich den Bitmap-Decoder um automatische HEL-Erkennung.

- ✅ **Tankbeleg fuel_type Bug-Fix (v1.7.3)**: Sening-Display zeigte "HEL schwefelarm" → Portal speicherte 4 Belege als "Diesel". Root-Cause: `parse_receipt()` nutzte `fuel_map.get(.., "diesel")` und `sync_to_portal()` `row.get('fuel_type') or 'diesel'` → stiller Default. Fix:
  - `parse_receipt()`: kein silent diesel-Fallback mehr (None bleibt None)
  - `sync_to_portal()`: sendet None statt diesel
  - Neue Config-Option `default_fuel_type` in `/etc/tankbeleg_pi.conf` (User-Wahl per Truck)
  - `enrich_receipt_with_heuristics()` nutzt Default + setzt `needs_review=True`
  - Backend `FuelReceiptCreate.fuel_type` jetzt `Optional[str]` (vorher required)
  - Sync-Update propagiert `fuel_type`-Korrekturen (Pi-UI Override → Portal)
  - Pi-UI: Kraftstoff-Auswahl-Buttons (HEL/Diesel/HVO) im Zuordnungsformular - Fahrer kann nachtraeglich korrigieren
  - "Diesel"-Fallback in Pi-UI durch "Unbekannt" ersetzt
  - 5 Unit-Tests in `/app/backend/tests/test_tankbeleg_fuel_default.py`, alle gruen
  - kirmes.py install-script akzeptiert Query-Param `default_fuel_type` (whitelist: heizoel_leicht/diesel/hvo)

- ✅ **Tankbeleg `xonxoff` Fix (v1.7.2)**: Version auf 1.7.2 gebumpt, zusaetzliche FLOW-CONTROL Diagnose-Log-Zeile ergaenzt damit per `journalctl -u tankbeleg_pi -f` sofort erkennbar ist, ob der Pi die neue Version mit aktiviertem XON/XOFF geladen hat. User-Test auf Production ausstehend.

- ✅ **LTE Failover DNS Fix** (P1 vom Backlog erledigt): User berichtete dass HAT-LED am Pi blinkt (LTE up), aber Portal sagt offline; LAN ziehen → Pi offline.
  - Root cause: `/etc/ppp/peers/m2m` fehlt `usepeerdns`-Direktive UND ip-up.d/20-set-dns Hook. Folge: keine Provider-DNS uebernommen, beim LAN-Ausfall verschwindet der einzige nameserver (192.168.x.1) → keine Namensaufloesung mehr → Portal unerreichbar trotz UP-ppp0.
  - Fix in `routes/energy_monitoring.py` (Setup-Script-Generator) fuer beide Varianten (8Z + Legacy):
    - `usepeerdns` zu peers/m2m hinzugefuegt
    - `ip-up.d/20-set-dns` schreibt `$DNS1 $DNS2 1.1.1.1 8.8.8.8` zusaetzlich in /etc/resolv.conf
    - `ip-down.d/20-restore-dns` raeumt sauber auf bei Trennung
  - Hotfix-Script fuer bereits deployten Pi: `/tmp/lte_dns_hotfix.sh` (am Pi via SSH ausfuehrbar), erweitert peers/m2m + erstellt Hooks + reconnected ppp0

- ✅ **iOS-Notch / Dynamic-Island: Zurück-Button war hinter Statusbar versteckt**:
  - Root cause: `viewport-fit=cover` (gesetzt fuer Tastatur-Fix iOS17+) laesst Inhalte edge-to-edge laufen, wodurch der Page-Header unter der translucenten iPhone-Statusbar verschwindet → Zurück-Button war auf iPhones mit Notch nicht erreichbar.
  - Fix global in `index.css`:
    - Utility-Klassen `safe-area-pad`, `safe-top`, `safe-bottom` mit `env(safe-area-inset-*)` definiert
    - Globale Auto-Anwendung: `header.sticky.top-0` und `div.sticky.top-0` bekommen `padding-top: calc(env(safe-area-inset-top, 0px) + 0.75rem)` -> auf Desktop unsichtbar (inset=0px), auf iPhone ~47px Padding nach oben -> Back-Button rutscht unter den Notch.
  - Fix `ChatPage.jsx`: Wrapper-Container `safe-area-pad` (Top/Left/Right/Bottom Inset), weil Chat keinen `sticky top-0` Header nutzt sondern feste Hoehe.
  - Verifiziert: Desktop-Rendering unveraendert (Finance-Page sieht identisch aus), iPhone wird auf echtem Geraet zu pruefen sein.

- ✅ **Stripe-Abgleich Button + erweiterter Repair** (Folge des vorherigen Fixes):
  - Vorheriger Sweep fand nur Transaktionen mit `payment_status="paid"` in unserer DB. Wenn der Stripe-Webhook nie korrekt feuerte (z.B. Webhook-URL nicht in Stripe-Dashboard registriert) UND der User nicht auf die Erfolgs-Seite zurückkam, blieb unsere Transaktion auf `pending` → Sweep ignorierte sie → Live-Rechnung blieb hängen auf "Fällig".
  - Erweiterung in `/api/payments/repair-stripe-paid-invoices`: Pollt jetzt auch alle `pending`/`initiated` Invoice-Transaktionen direkt bei Stripe nach. Bei `paid` wird die Transaktion aktualisiert UND die Rechnung wird per `_mark_kirmes_invoice_paid()` korrekt verbucht (inkl. Mahnung schließen).
  - Frontend: Neuer Button **"Stripe abgleichen"** (Admin-only, mit Refresh-Spinner) in der `Rechnungsverwaltung` Header-Leiste. Toast zeigt nach Abgleich an wie viele Rechnungen repariert wurden, mit Liste der Rechnungsnummern.

- ✅ **Stripe-Zahlung wird jetzt korrekt als 'bezahlt' markiert** (P0):
  - Root cause: In `payments.py` Webhook + Status-Polling schrieb der Code in die falsche Collection (`db.invoices` statt `db.kirmes_invoices`) und mit englischem Status (`"paid"` statt deutsch `"bezahlt"`). Außerdem schloss er keine offenen Mahnungs-Tasks. → Stripe-bezahlte Rechnungen blieben fälschlicherweise auf "Fällig" stehen, automatische Mahnungen wurden trotzdem ausgelöst.
  - Fix:
    - Neuer Helper `_mark_kirmes_invoice_paid()` mit korrekter Collection, deutschem Status, `paid_at`, `paid_amount`, und Mahnungs-Task-Closure (gleiche Logik wie der manuelle Mark-as-paid Admin-Endpoint).
    - Webhook + Status-Polling rufen jetzt diesen Helper.
    - Idempotent: erneute Aufrufe schreiben nichts wenn bereits "bezahlt".
  - Bonus-Endpoint: `POST /api/payments/repair-stripe-paid-invoices` (Admin) — einmaliger Sweep, findet alle Stripe-paid-aber-Rechnung-nicht-bezahlt Faelle und repariert sie. Nuetzlich um die durch den Bug haengen gebliebenen Altfaelle zu reparieren.

- ✅ **Wochenplan: Sollzeiten → Sollstunden umgestellt** (Verwaltung > Arbeitszeiterfassung):
  - Vorher: User mussten `Beginn 08:00` + `Ende 17:00` + `Pause 30min` eintragen → System rechnete Spanne minus Pause als SOLL
  - Jetzt: User trägt direkt `Sollstunden 8` + `Pause 30min` ein → das sind die NETTO-Sollstunden, Pause wird zusätzlich von der gemessenen Anwesenheit abgezogen (siehe vorherigen Fix)
  - Backend (`employee.py` Überstundenberechnung): liest jetzt bevorzugt `day_schedule.soll_hours`, fällt für alte Pläne auf `start/end - break_min` zurück → **rückwärtskompatibel**, kein Daten-Migrationsskript nötig
  - Frontend (`AdminZeitDetailPage.jsx`):
    - Tabellenspalten: `TAG | SOLLSTUNDEN | PAUSE (MIN.) | SUMME`
    - Sollstunden = Number-Input mit `step=0.25`
    - Migrationshilfe: Alte Pläne mit `start/end` zeigen die berechneten Stunden im neuen Sollstunden-Feld an, sodass der User sie nur einmal speichern muss um auf das neue Format umzustellen
  - `EinsatzplanungPage.jsx` (Soll-Stunden für Einsatzplanung) ebenfalls auf `soll_hours` umgestellt mit Fallback
  - Verifiziert: Mo=8h direkt, Di=7.5h aus alter `09:00-17:00 -30min` Logik abgeleitet, Mi=4.5h direkt → UI zeigt alle korrekt + Wochensumme 20h

- ✅ **PI-STATUS-Panel jetzt auch fuer Tankwagen + alle Pi-Typen** (war vorher nur fuer Kirmeskiste 8Z):
  - Server (`routes/ota_updates.py`): OTA-Check akzeptiert jetzt zusaetzlich `lte_ip, lte_csq, lte_dbm, lte_operator, lte_act, gps_lat, gps_lon, version, hostname` als Query-Params und persistiert sie in `ota_checkins`.
  - Server (`routes/devices.py` Quick-Info): Wenn `device.pi_health` leer ist, wird der zugehoerige `ota_checkin` als Fallback angezogen (Match: `device.pi_id` falls gesetzt, sonst einziger aktiver Checkin desselben device_type in den letzten 30 Min).
  - Pi (`tankbeleg_pi.py`): Neue `_collect_pi_status_for_otacheck()` Helper sammelt LTE-IP via `ip addr show ppp0`, CSQ + Operator via AT-Befehl an SIM7600 (best-effort wenn Port frei), GPS aus gpsd. Wird bei jedem OTA-Check (60s) mitgesendet. `SCRIPT_VERSION = 1.7.0` als Konstante.
  - Frontend: `PiHealthPanel` rendert bereits unter `{info.pi_health && ...}` → kein Frontend-Change noetig.
  - Verifiziert per curl: OTA-Check mit Status-Daten persistiert korrekt; Quick-Info des Tankwagens liefert `pi_health` mit LTE-IP, Signal, Provider, Version, Hostname, Pi-ID + GPS.

- ✅ **Tankbeleg-Klassifikation: Diesel wurde als Heizöl erkannt** (P0):
  - Root cause: Die Bitmap-Parser-Heuristik in `tankbeleg_pi.py` matchte den Substring `"hel" in text.lower()`. Da der Sening MultiFlow auf jedem Beleg ALLE konfigurierten Fuel-Typen als Header listet (z.B. "HEL schwefelarm"), wurde **jeder Beleg** — auch echte Diesel-Belege — als `heizoel_leicht` klassifiziert. Außerdem fiel das Default unbedingt auf `heizoel_leicht`.
  - Fix in `backend/static/tankbeleg_pi.py` (parse_receipt_sening Heuristik):
    - Sucht jetzt zuerst gezielt das mit `*` markierte Produkt (`*Diesel*`, `*HEL schwefelarm*`, `*HVO*`) — das ist die Sening-Konvention für das tatsächlich abgegebene Fuel
    - Fallback nur wenn der Text **nur eines** der Worte enthält (z.B. nur "Diesel" oder nur "HVO" → eindeutig)
    - Bei Mehrdeutigkeit (Header listet HEL + Diesel) wird **nicht mehr geraten**, sondern `fuel_type=None` + `needs_review=True` gesetzt — Operator muss manuell bestätigen
  - Verifiziert mit 5 Test-Cases:
    - `*HEL*` Marker → heizoel_leicht ✓
    - `*Diesel*` Marker → diesel ✓ (vorher: heizoel_leicht ✗)
    - Beide ohne Marker → None + Review ✓
    - Nur "Diesel" → diesel ✓
    - Nur "HVO" → hvo ✓
  - Bestehende Simulator-Tests (`tankbeleg_simulator.py --test`) bestätigen: HEL- und Diesel-Belege werden weiterhin korrekt erkannt.

- ✅ **Chat Auto-Scroll-Behavior verbessert**: Vorher wurde bei jedem Poll-Tick (4s) erzwungen ans Ende gescrollt → User konnte beim Lesen alter Nachrichten nicht hochscrollen.
  - Fix in `ChatPage.jsx`: 
    - `handleMessagesScroll` tracked `isAtBottom` (Toleranz 80px) via Scroll-Listener auf dem Messages-Container
    - Auto-Scroll nur noch wenn `isAtBottom === true`. Andernfalls bleibt die Lese-Position erhalten.
    - Sticky Floating-Button **"Neue Nachrichten"** (lila pulsierend) erscheint, wenn neue Nachrichten reinkommen während User hochgescrollt hat. "Nach unten" als sekundärer Hint, wenn User selbst ohne neue Nachrichten gescrollt hat.
    - Eigene Nachrichten/Datei-Uploads setzen `isAtBottom = true` → springen automatisch ans Ende.
    - Konversation-Wechsel → reset auf `isAtBottom = true`.
    - iOS-Tastatur-onFocus-Scroll: nur noch wenn ohnehin am Ende (kein ungewolltes Hochreißen).

- ✅ **GPS-Lock-Picker (WhatsApp-Style) für Artikel-Positionierung**: User berichtete, dass die ungenaue Direkt-Übernahme der GPS-Position oft hunderte Meter daneben lag.
  - Neue Komponente: `frontend/src/components/GpsLockPicker.jsx` (Modal mit Leaflet-Karte, drag-barer Stecknadel, Live-Genauigkeit-Badge)
  - Verhalten:
    - Klick auf "Meine Position" öffnet das Modal statt sofort eine ggf. ungenaue Position zu übernehmen
    - `watchPosition()` liefert kontinuierlich Updates → Genauigkeit wird live als Badge angezeigt (rot >80m, gelb >30m, grün ≤30m, sehr genau ≤10m)
    - Pin folgt dem GPS-Fix automatisch — sobald der User ihn manuell verschiebt, bleibt die manuelle Position erhalten ("Auf GPS zurücksetzen"-Button erscheint)
    - "Position speichern" überträgt Lat/Lng zurück ins Asset-Form
  - In `OrderDetailPage.js` verdrahtet: `getMyPosition` öffnet jetzt nur noch das Modal, `onGpsPicked` füllt die Felder
  - Verifiziert per Playwright: Modal lädt, watchPosition fired (50.4286, 7.4630, ±15m), Map mit Pin rendert korrekt, Save überträgt Werte ins Form, Plus Code wird automatisch generiert.

- ✅ **Pausenzeiten werden nun korrekt von der Arbeitszeit abgezogen** (P0):
  - Root cause: Backend hat `break_min` aus dem Wochenplan zwar für die SOLL-Berechnung der Überstunden genutzt, aber **nie von `duration_minutes` abgezogen** → Reports/Listen zeigten die volle Anwesenheitszeit statt der bereinigten Arbeitszeit.
  - Fix in `backend/routes/employee.py`: Helper `_get_break_min_for_date()` + `_apply_break_deduction()`. Wird in `clock_out`, `time/manual` und `PUT time/entries/{id}` angewendet. Die konfigurierte Tagespause wird nur abgezogen wenn die geleistete Zeit > Pause ist (Schutz gegen negative Werte).
  - Bonus: `break_min` wird jetzt auf jedem Eintrag mitgespeichert (Transparenz).
  - Frontend: `AdminZeitDetailPage.jsx` zeigt ein blaues Badge `−Xm Pause` neben Einträgen, von denen eine Pause abgezogen wurde.
  - Verifiziert per curl:
    - 9h Schicht (08-17) bei 30min Pause → 510min (8:30h) ✅
    - 20min Schicht bei 30min Pause → 20min (kein Abzug, würde negativ) ✅
    - Tag ohne Plan (Sa) → 0 break_min, voller Wert ✅
    - Überstundenberechnung bleibt korrekt (Pause kürzt sowohl IST als SOLL).

- ✅ **iOS-Eingabe-Bug bei Zeiterfassung & Wartung behoben**: Daten erschienen erst nach 2.–3. Versuch.
  - Root cause: iOS Safari committed Werte aus `<input type="time">` / `<input type="date">` erst beim **blur** des Inputs. Wenn der User direkt von der Picker-Auswahl auf "Speichern"/"Hinzufügen" tippt, schließt der erste Tap nur den Picker — der React-State ist beim Click-Handler noch leer, Validierung scheitert oder leere Daten werden gesendet.
  - Fix: Submit-Handler erzwingen jetzt `document.activeElement.blur()` und warten 60ms, bis React den onChange aus dem Blur propagiert. Werte werden dann via `useRef` zuverlässig gelesen.
  - Betroffene Stellen: `AdminZeitDetailPage.jsx` (`submitAddRow`, `saveEditEntry`, `addVacation`) und `ServiceplanPage.js` (`MaintenanceEntryForm.handleSave`).
  - Backend verifiziert via curl: `/api/employee/time/manual` legt Eintrag korrekt an (200 OK), `/time/entries` gibt ihn sofort zurück.

- ✅ **iOS-Tastatur-Fix im Team Chat**: Eingabefeld verschwand auf iOS hinter virtueller Tastatur.
  - Root cause: Container nutzte `h-screen / 100dvh` — auf iOS Safari bleibt das die volle Browser-Höhe, auch wenn die Tastatur den Viewport verkleinert.
  - Fix: `ChatPage.jsx` setzt jetzt die Container-Höhe via `window.visualViewport.height` (resize/scroll-Listener); Input erhält `onFocus` mit `scrollIntoView` ans Listenende.
  - Zusatz: Viewport-Meta-Tag erweitert um `viewport-fit=cover, interactive-widget=resizes-content` (iOS 17+ Bonus).
- ✅ **iOS-Crash bei Order Details behoben** (P0):
  - Root cause: FastAPI 422-Fehler liefert `detail` als Array-of-Objects; React rendert das in `OrderDetailPage.js` direkt als `{error}` → "Objects are not valid as a React child" → iOS Safari zeigt White-Screen / Crash.
  - Fix 1: `OrderDetailPage.js` validiert `pk` (parseInt) vor API-Call → bei `undefined`/non-numeric wird "Ungültige Auftragsnummer" angezeigt statt 422.
  - Fix 2: `OrderDetailPage.js` nutzt jetzt zentralen `getErrorMsg()` Helper aus `lib/api.js` (wandelt Pydantic-Validation-Arrays in lesbare Strings um).
  - Fix 3 (defensiv): `HubPage.js` (myPlan) und `GeneratorDetailPage.js` (Deployments) prüfen `order_pk` als positiven Integer vor Navigation.
  - Verifiziert: Login → `/orders/undefined` zeigt Fehlerseite; `/orders/3` lädt normal.

- ✅ **Kirmeskiste 8Z – LIVE-DEPLOYMENT erfolgreich!** Nach intensivem Debugging (8 Iterationen):
  - PPP läuft jetzt über `/dev/ttyUSB2` (statt ttyUSB3 — das ist bei diesem SIM7600-Composite der korrekte AT/PPP-Port)
  - LTE: `inet 10.27.23.227 peer 10.64.64.64` via Telekom M2M (`internet.m2mportal.de`, PIN `0000`)
  - Signal: `+CSQ: 20,99` (sehr gut), Provider: `Telekom.de`, Modus: `7=E-UTRAN (LTE)`
  - 8 S0-Pulse-Counter loggen + syncen ans Portal
  - Sequent HAT auto-discovers Stack-Level (war hier 0x27 = Stack 7)
  - **Hardware-Lessons** dauerhaft im Setup-Skript abgefangen:
    1. USB-Datenkabel zwischen Pi-USB-A und HAT "USB"-Buchse PFLICHT (Setup warnt explizit bei fehlender 1e0e:9001-Erkennung)
    2. PPP-Default jetzt ttyUSB2 (nicht ttyUSB3)
    3. `noipv6` gesetzt (Telekom-M2M-APN ist IPv4-only, sonst IPV6CP-Timeout-Loop)
    4. LCP-Echo (30s/4) für robustes Reconnect
    5. `+++` / `ATH` Escape im Chat-Skript um Modem aus Data-Mode zu hebeln
    6. Stack-Level-Auto-Discovery für Sequent HAT (0..7)
    7. Auto-Reboot am Ende für UART-Aktivierung
- ✅ **Kirmeskiste 8 Zähler – Pi-Implementation komplett** (Backend + UI + Pi-Sync + OTA):
  - **Backend** (`/app/backend/routes/energy_monitoring.py`):
    - `POST /api/energy-monitoring/devices/{id}/kirmeskiste-8z-setup` – legt 8 Zähler in `emu_meters` an (mit `hat_channel` 1-8, `pulses_per_kwh=1000`, `kwh_offset=0`, `meter_type="ABB D11/D13 (S0 Pulse)"`), generiert Geräte-Key, baut Bash-Setup-Skript (Pi 5 + Sequent 16-LV HAT + SIM7600 LTE/GPS + Telekom-APN + lokale SQLite + Systemd + OTA-Auto-Update + Sequent-Init-Service nach Boot).
    - `PUT /api/energy-monitoring/devices/{id}/meters/{mid}/kwh-offset` – Admin/Abrechnung trägt Anfangs-kWh-Stand ein.
    - `GET /api/energy-monitoring/devices/{id}/meters/{mid}/kwh-offset?api_key=…` – Pi holt Anfangsstand.
  - **OTA** (`/app/backend/routes/ota_updates.py`): `kirmeskiste_8z` registriert als neuer Device-Type → integriert sich nahtlos ins bestehende OTA-Dashboard.
  - **Pi-Sync-Skript** (`/app/backend/static/kirmeskiste8z_sync.py`): Liest 8 S0-Pulse-Counter via `16inpind`-CLI, speichert lokal in SQLite, syncht alle 60s zu `/api/energy-monitoring/ingest` als `E_imp_kWh`, erkennt Counter-Reset, hat OTA-Self-Update, GPS via gpsd, robust bei LTE-Ausfall (lokale Pufferung 14 Tage).
  - **Frontend** (`DeviceManagementPage.js`): Im Geräte-Modal erscheint bei Variante 8Z ein "Zähler"-Bereich mit 8 Zeilen (K1-K8) für Anfangsstand-Eingabe + 8 QR-Druck-Buttons. Setup-Button ruft den neuen 8Z-Endpoint auf.
- Tests: `/app/backend/tests/test_kirmeskiste_8z_setup.py` (8 Checks alle grün), Frontend-Smoke-Screenshot bestätigt UI.
- ✅ **Kirmeskiste 8 Zähler – Variante (Datenmodell + UI)** – Vorbereitung für 12 neue Pi-basierte Geräte (SIM7600 LTE+GPS, HAT-Board, 8 Impuls-Zähler):
  - Neues Feld `kirmeskiste_variant` in `devices`-Collection: `"standard"` (Live, unverändert) | `"8z"` (neue Generation).
  - Backend (`/app/backend/routes/devices.py`): Pydantic `DeviceCreate` & `DeviceUpdate` akzeptieren das Feld; Default `"standard"` für neue Kirmeskisten, `null` für andere Gerätetypen → bestehende Live-Geräte unangetastet.
  - Frontend (`DeviceManagementPage.js`): Sub-Selektor "Variante" erscheint nur bei `device_type === "kirmeskiste"`; "8Z"-Badge in der Geräteliste.
  - Pi-Implementation kommt im nächsten Prompt.
  - Tests: `/app/backend/tests/test_kirmeskiste_variant.py` – grün.
- ✅ **Genehmigt: 0 Tage** – durch RBAC-Fix in `employee.py` (Verwaltung-Helper statt Admin-Strict-Check) bereits behoben (Christian bestätigt 02/2026).
- ✅ **Mahnungs-Tasks Auto-Close (P0)** – 3 Wege schließen offene Mahnungs-Aufgaben automatisch:
  1. **FinTS Auto-Match** (`fints_banking.auto_match_and_mark`): Bei automatischer Zahlungs-Zuordnung wird die zugehörige `payment_reminder`-Task auf `completed=True` gesetzt.
  2. **FinTS Sweep-Cleanup** (neu): Beim Lauf von `auto_match_and_mark` werden zusätzlich alle offenen Mahnungs-Tasks geschlossen, deren Rechnung bereits `payment_status="bezahlt"` hat – egal ob durch FinTS oder manuell markiert.
  3. **Manueller Bezahlt-Status** (`PUT /api/kirmes/invoices/{id}/payment-status`): Wenn Admin/Abrechnung den Status auf `bezahlt` setzt, werden offene Mahnungs-Tasks automatisch geschlossen.
  - Tests: `/app/backend/tests/test_fints_auto_close_mahnung.py`, `/app/backend/tests/test_manual_paid_closes_mahnung.py` – beide grün.

### Feb 2026 – Current Session
- ✅ **Freelancer-Rolle + Auftragszuweisung** – Neue Rolle `freelancer` mit:
  - User-Feld `freelancer_orders: [order_pk, ...]`
  - Edit-Modal: Suchmaske + Checkbox-Liste zur Auftragszuweisung
  - Auftragsliste: zeigt nur zugewiesene Aufträge, automatischer Filter 5 Tage nach Job-Ende
  - Auftragsdetail: Kundendaten (Name, Kd-Nr, Tel, Email, Adresse, Summen) ausgeblendet
  - Tankbelege-Section komplett ausgeblendet (Frontend) + Backend 403
  - 403 bei Detail-Zugriff auf nicht-zugewiesene oder abgelaufene Aufträge
- ✅ **Messprotokoll Delete (Admin only)** – DELETE `/api/orders/messprotokoll/{order_pk}/{doc_id}` mit Trash-Button im UI

### Previous Session
- ✅ Messprotokoll feature (PDF generator, 7-tab modal, numbering `{OrderNo}-MP-{NNNN}`)
- ✅ Tankwagen-Pi PIN login (6-digit DOB-based, bcrypt hashed in SQLite)
- ✅ RBAC overhaul (Verwaltung, Finance) – no more bouncing
- ✅ Hub Presence bug (`clocked_in` flag)
- ✅ Hub tiles legacy checks removed
- ✅ Mahnung task persists when email fails (`reminder_email_ok`)
- ✅ Admin task default filter "both" on Aktuell tab
- ✅ ADR Hub tile removed

## Roadmap

### P2 – Upcoming
- Pi-Status-Dashboard im Portal (last sync, unsynced count, GPS status)
- Portal-Auftragsliste "Lager"-Filter/Reiter
- Suchleiste über Auftragsliste in Pi-UI

### P2 – Future / Backlog
- GPS-Support für Kirmeskiste
- Lastdiagramm Live-Test
- Chromium "Translate"-Popup auf Pi-Kiosk global unterdrücken
- DSE USB Modbus Sync (BLOCKED – Hardware-Test nötig)

### Refactoring
- Unified `usePermissions()` hook to align `App.js` routing protection with backend permission checks

## Key API Endpoints
- `POST /api/orders/messprotokoll/{order_pk}` – Create + generate PDF
- `GET /api/orders/messprotokoll/{order_pk}` – List for order
- `DELETE /api/orders/messprotokoll/{order_pk}/{doc_id}` – Admin-only delete (NEW)
- `POST /api/fuel-receipts/pi/verify-pin` – Pi Kiosk PIN auth

## Key DB Schemas
- `messprotokolle`: `{id, order_pk, protokoll_nr, pruefer_name, pruef_datum, data, document_id, created_by, created_at}`
- `order_documents`: PDFs/images with `kategorie` field; storage at `backend/storage/order_documents/{order_pk}/`
- `tasks`: includes `reminder_email_ok`, `reminder_sent_at`
- Pi SQLite `drivers_cache`: includes `pin_hash`

## Tech Stack
- Backend: FastAPI + Motor (MongoDB) + ReportLab + bcrypt
- Frontend: React + TailwindCSS + shadcn/ui + lucide-react
- Pi Kiosk: Python + SQLite (offline cache)
- Integrations: Stripe (live keys), Ollama (local), python-fints (banking)


## Roadmap (offene Tasks)

### Recently Completed (Feb 2026)
- **Einsatzzentrale Pi-Kiosk Reload-Loop endgültig gefixt** (mehrere Iterationen):
  - Pre-Bundle Inline-Skript-Redirect in `public/index.html`: `/einsatzzentrale` redirected synchron VOR React-Bundle-Laden zu `/api/einsatzzentrale/kiosk-page` (kein WDS-HMR-Flacker mehr).
  - Logo-Bild + Text-Fallback in der Standalone-HTML.
  - `window.location.reload` als no-op überschrieben, WebSocket-Hijack-Block für `/ws`-Verbindungen.
  - **localStorage statt sessionStorage** für Token → Session überlebt Reload/Crash/Chromium-Restart.
  - **Install-Script Fix: Single-Instance-Lock (`flock`)** verhindert Doppel-Launcher, **targeted `pkill -f user-data-dir=$PROFILE`** killt nur eigene Chromium-Instanzen (nicht alle) → behebt den 5-Sekunden-„Opening in existing browser session"-Loop auf dem Pi.
  - Diagnose-Badge unten rechts (Loads-Counter, Uptime, Erst-Load-Zeitstempel).
- **Multiansicht-Tile** (Feb 2026): Split-Screen mit Einsatztagebuch links + Artikelliste rechts, beide live mit Auto-Refresh 30s. Volle Bildschirmbreite (`max-width: none`).
- **Geocoding-Verbesserung** (Feb 2026): Nominatim (OpenStreetMap) als priorisierter Geocoder fuer deutsche Adressen, Open-Meteo Geocoding als Fallback. Strategie: Volle Adresse -> PLZ+Ort -> nur Ort. Adressen wie "Nürburgring", "Vallendar", "Randersacker" werden jetzt zuverlaessig geocoded (vorher: alle KEIN TREFFER bei Open-Meteo). Re-geocoded automatisch alle 32 bestehenden Auftraege.
- **Workspace Bildschirmnutzung** (Feb 2026): `kiosk-main` max-width auf 1920px erweitert, im Tile-Mode `fullscreen` (none).
- **Einsatzzentrale Pi-Setup-Generator + Offline-Mode (Option B)** (Feb 2026):
  - **Admin -> Einstellungen -> Einsatzzentrale Pi-Kioske** (fuchsia Section): Pi-Name + Standort eingeben -> One-Liner-Befehl + Pi-Liste (mit Heartbeat-Status, Key-Prefix, Loeschen)
  - Backend: `POST /api/einsatzzentrale/pis/generate-setup` (anlegen+Key), `GET /pis` (Liste), `DELETE /pis/{id}`, `POST /pis/{id}/heartbeat`, `GET /pi-service.py` (Code-Download)
  - DB-Collection: `einsatzzentrale_pis` mit `{id, name, standort, device_key_hash, last_seen, status}`
  - **Lokaler Pi-Service** (`/app/scripts/einsatzzentrale-pi/pi_service.py`, Python+FastAPI+SQLite, laeuft als systemd auf Port 8001):
    - Smart-Proxy fuer `/api/*` Routes: GETs aggressiv cached, POST/PUT/PATCH/DELETE bei Online durchgereicht / bei Offline in Outbox-Queue
    - Sync-Worker alle 2 Min: pollt aktive Auftrag-Daten (Orders, Diary, Trupps, Assets, Generatoren, Documents) und cached sie in SQLite
    - Outbox-Flush: gequeuete Mutationen werden beim naechsten Online-Zyklus zur Cloud nachgesendet
    - Retention: Cache-Eintraege & abgearbeitete Outbox-Items aelter als 90 Tage werden taeglich geloescht
    - Heartbeat alle 2 Min an Cloud `/pis/{id}/heartbeat` damit Portal sieht ob Pi online ist
    - Liefert kiosk-page lokal aus (`/kiosk` -> bei Erstinstall aus Cloud gezogen + lokal gecached)
    - `/pi-status` Endpoint fuer Debug (Cache-Count, Outbox-Pending, Online-Flag)
  - **Install-Skript** parst `pi_id` und `key` aus der URL und erstellt `/etc/einsatzzentrale-pi.conf`, installiert Python-venv + Service-Code in `/usr/local/lib/einsatzzentrale-pi/`, registriert systemd-Service `einsatzzentrale-pi.service`, stellt Chromium auf `http://localhost:8001/kiosk` um -> Pi laeuft komplett offline-faehig.
- **Maschinenliste-Tile** (Feb 2026):
  - Liefert die "Generatoren im Radius" (selbe Quelle wie React `OrderDetailPage`: `GET /api/orders/epirent/{pk}/generators`)
  - Name (z.B. `ML_252`) gross zuerst, darunter Serien-Nr + Modell, Status-Punkt rechts oben
  - Live-Telemetrie pro Karte: **Tankstand** (farbcodiert: gruen >=50%, gelb 25-49%, rot <25%) mit Fill-Bar, **Leistung in kW**, optional Distanz
  - **Sortier-Optionen**: Name auf/ab, Tankstand niedrig zuerst, Tankstand voll zuerst, Leistung hoechste, Distanz naechste, Online zuerst
  - Suche (Name/Modell/Serien-Nr) + Status-Filter (online/offline/alle)
  - **Auto-Refresh alle 30s** waehrend das Tile geoeffnet ist
  - Klick auf Karte oeffnet Detail-Modal mit allen Telemetriewerten (Tankstand-Bar, Leistung, Spannung L1, Frequenz, Betriebsstunden, letzte Aktualisierung)
- **Dokumentenablage-Tile** (Feb 2026):
  - 4 Kategorien (Messprotokolle / Plaene / Fotos / Sonstiges) wie React-App, mit Counts pro Kategorie
  - Drag&Drop-Upload + "Datei waehlen"-Button mit Auto-Kategorie-Erkennung
  - **Foto-Direkt-Aufnahme** via `<input capture="environment">` (oeffnet Pi-Kamera, falls vorhanden) -> immer Kategorie "fotos"
  - **PDF-Viewer**: Browser-natives `<embed type="application/pdf">` mit eingebautem Zoom/Page-Fit
  - **Bild-Viewer**: Custom Pan+Zoom (Wheel-Zoom, Drag-Pan, Doppelklick Toggle, Touch-Pinch, +/-/100% Buttons), Esc-Schliessen, Download-Link
  - Token via `?token=` Query an `/file` Endpoint -> funktioniert in `<embed>`/`<img>` ohne Auth-Header
  - Verwendet `/api/orders/order-documents/...` Endpoints (Upload, List, File, Thumbnail)
- **Artikelliste-Tile (read-only)** (Feb 2026):
  - Vier-Spalten-Layout: Karte links + Liste rechts, Toolbar oben (Suche/Typ-Filter/Status-Filter)
  - Live-Suche ueber Bezeichnung/Typ/Plus-Code/Anleger
  - Karten-Marker farbcodiert nach Typ (Stromerzeuger=orange, Verteiler=gruen, Lichtmast=gelb), Klick oeffnet Detail
  - Detail-Modal mit Plus-Code, GPS (Google-Maps-Link), Anleger, Datum, Kommentaren
  - Read-only: keine Loesch-/Edit-Buttons (das macht weiterhin nur die React-App)
  - Wiederverwendet `/api/orders/epirent/{pk}/assets` (kein neuer Endpoint noetig)
- **Workspace mit Regenradar + Stunden-Forecast** (Feb 2026):
  - 2-Spalten-Layout (links: Tiles + 7-Tage-Wetter, rechts: Regenradar + 24h-Stunden-Prognose)
  - **Auto-Geocoding** im Backend: Auftragsadresse -> lat/lng via Open-Meteo Geocoding-API (kein vor-Detail-Oeffnen mehr noetig)
  - **Regenradar** via RainViewer-API (kostenlos, kein API-Key) mit Leaflet-Karte, Veranstaltungsort-Marker, Vergangenheit + Nowcast-Frames mit Play/Stopp-Animation und Slider
  - **24h-Hourly-Forecast** als Bar-Chart mit Regen-Wahrscheinlichkeit (low/mid/high Farbcode) + Summary (Sigma mm, Max-Wkt)
  - Kompakter Auftrags-Header (Strip statt grosser Karte) -> bessere Bildschirmnutzung auf 50"-TV
  - Neuer Endpoint `GET /api/einsatzzentrale/weather/hourly?lat=&lng=&hours=`

- **Einsatztagebuch-Tile** in Standalone-HTML komplett funktionsfähig:
  - Liste aller Diary-Einträge mit Status-Badge (offen/behoben), Filter-Suche
  - Stats-Header (offen / behoben / gesamt)
  - „+ Neue Störung"-Modal mit Anrufer/Tel/Ort/Grund/Nachtrag/Trupp-Zuweisung
  - Resolve/Reopen/Edit/Delete pro Eintrag
  - Trupp-Sektion mit Anlegen/Bearbeiten/Pause/Löschen + Live-Status (verfügbar/unterwegs/Pause)
  - CSV-Export Button (lädt direkt vom Backend)
  - Touch-optimiert (44px+ Buttons, große Modal-Inputs)

### P1
- Workspace-Tiles in der Standalone-HTML mit echten Daten füllen (Maschinenliste, Pläne, Standortliste) — Einsatztagebuch ✅ fertig.
- EpiRent „Lieferscheine" PDF-Generierung (wartet auf Layout-Feedback vom User).
- LTE Failover DNS Fix auf Pi: `usepeerdns` in `/etc/ppp/peers/m2m` + `/etc/ppp/ip-up.d/0000-lte-dns` Hook (Telekom-DNS in `/etc/resolv.conf` wenn LAN ausfällt).

### P2
- Portal-Auftragsliste "Lager"-Filter / Reiter (interne Testläufe von normalen Aufträgen trennen).
- Suchleiste über Pi-Auftragsliste (Kiosk-UI).
- GPS-Support für Legacy-Kirmeskiste (4-meter Variante).
- Lastdiagramm Live-Test.
- Chromium "Translate"-Popup auf Raspberry Pi Kiosk global unterdrücken.

### Verworfen / nicht benötigt
- ~~Übersichtskachel auf der Startseite für 8Z-Pis (X von 12 Pis online, Y mit schwachem Signal, Z ohne GPS-Fix)~~ — vom User als nicht benötigt gestrichen (Mai 2026).
