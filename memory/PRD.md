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


### Feb 2026 – Messprotokoll mit Verteiler-Asset verknuepfen via Karte (Feature)
- 🎯 **User-Request**: Workflow Trupp A setzt Verteiler Mo, Trupp C misst Do auf grossem Gelaende (>400 Artikel). Anstatt die Verteiler-Nr. manuell zu tippen, soll der Pruefer auf der Karte den Verteiler auswaehlen koennen.
- ✅ **Neue Komponente `components/VerteilerPickerDialog.jsx`** (170 LOC):
  - Vollbild-Map-Dialog mit Leaflet (selbe Lib wie DeviceManagementPage)
  - Laed `GET /api/orders/epirent/{orderPk}/assets`, filtert auf `asset_type === "verteiler"` (case-insensitive) + `status === "placed"` + valide Koordinaten
  - Custom Marker-Icons (orange = unausgewaehlt, violet = ausgewaehlt) mit „V"-Label
  - Auto-Zoom: bei 1 Verteiler → Zoom 17, sonst Zoom 14 ueber Schwerpunkt
  - Klick auf Marker oder Popup-„Auswaehlen" markiert; Footer zeigt aktuelle Auswahl + Verknuepfen-Button
  - Empty-State („Trupp A muss die Verteiler zuerst positionieren")
- ✅ **`components/MessprotokollDialog.jsx` erweitert**:
  - Neuer „📍 Auf Karte"-Button neben dem Stromkreisverteiler-Nr.-Input (orange Pill)
  - Bei Auswahl: `verteiler_nr` (Label), `verteiler_asset_id`, `verteiler_plus_code`, `verteiler_lat`/`lng` werden ins Form gesetzt; Hinweis-Pille „🔗 Verknuepft mit Asset · Plus Code: ..." zeigt aktuellen Link
  - Toast „Verteiler 'XYZ' verknuepft"
- ✅ **Backend** unveraendert — die bestehenden POST/PUT `/orders/messprotokoll` Endpoints speichern beliebige Felder im `data`-Dict, daher landen die neuen Felder automatisch in `messprotokolle.data`. PDF-Generator nutzt nur `verteiler_nr`, ignoriert die zusaetzlichen Asset-Felder.
- ✅ **Tests**: ESLint clean, Smoke-Test (Orders-Liste lädt mit 27 Auftraegen, kein JS-Error aus den Aenderungen).
- 📋 **So nutzt du es**: Im Messprotokoll-Dialog auf „Auf Karte" klicken → Verteiler-Marker waehlen → „Verknuepfen". Beim naechsten Bearbeiten/Reload des MP ist die Verknuepfung sichtbar.



### Feb 2026 – Messprotokolle als Admin bearbeitbar (Feature)
- 🎯 **User-Request**: „aendere hier, dass ich als admin die Messdaten anpassen kann" (Screenshot: Messprotokoll-Liste auf Order-Detail-Seite, nur PDF-Open + Delete vorhanden, kein Edit-Button).
- ✅ **Backend** in `routes/orders.py`:
  - `GET /orders/messprotokoll/{order_pk}/{doc_id}` (Admin-only): liefert ein einzelnes Messprotokoll inkl. vollstaendiger `data`-Formular-Daten zum Vorbefuellen
  - `PUT /orders/messprotokoll/{order_pk}/{doc_id}` (Admin-only): generiert PDF mit neuen Daten neu, ueberschreibt die gespeicherte PDF-Datei (selber Pfad/Dateiname), aktualisiert `messprotokolle.data` + Audit-Felder (`updated_by`, `updated_at`).
  - **Forensische Kette**: Protokoll-Nr., `pruefer_id`, `pruefer_name` werden NICHT veraendert (kommen weiter aus dem urspruenglichen Datensatz). Pruef-Datum bleibt erhalten falls nicht explizit neu gesetzt.
  - `order_documents.uploaded_at` bleibt erhalten (kein Re-Sort der Liste), separates `updated_at`-Feld dazu.
- ✅ **Frontend `components/MessprotokollDialog.jsx`**:
  - Neue Prop `existing={mp}` — wenn gesetzt, laeuft Dialog im Edit-Modus
  - Header zeigt „Messprotokoll bearbeiten · Nr. XYZ" statt „Neues Messprotokoll · Auftrag ABC"
  - `initialForm` lädt aus `existing.data` (alle Felder vorbefuellt), bei neuem MP wie bisher leeres Template
  - `save()` macht `PUT` bei Edit, sonst `POST` (unveraendert)
  - Save-Button-Label: „PDF aktualisieren & speichern" vs. „PDF erstellen & speichern"
- ✅ **Frontend `pages/OrderDetailPage.js`**:
  - Edit-Button (violet, Pencil-Icon) neben dem PDF-Open-Button in jeder MP-Zeile, NUR fuer `isAdmin`
  - Klick: holt vollstaendige Daten via `GET /orders/messprotokoll/{pk}/{mp.id}`, oeffnet Dialog mit `existing={...}`
  - `editingMessprotokoll`-State + Reset bei Close
  - `setDocCount` wird nur bei NEU (kein `existing`) erhoeht — beim Update bleibt die Dokumenten-Anzahl gleich
- ✅ **Tests**: ruff + eslint clean; Backend Import OK; unauth GET/PUT auf neue Endpoints → korrekt 403



### Feb 2026 – KirmesZaehlerPage: Auswertung auf Dispo-Zeitraum clampen + 5-Min-Chart-Bucketing (P0, Bug)
- 🎯 **User-Report**: Bei abgeschlossener Kirmes (z.B. „Osterkirmes Neuwied 2026", Dispo 20.3.–14.4.26) zeigt die Zaehlerauswertung den Stand „heute" (z.B. 27.5.26). Da der Zaehler inzwischen auf einer anderen Kirmes laeuft, sind dort fuer diese Anmeldung keine Daten. Zudem war die Datenmenge fuer die Chart-Anzeige zu hoch.
- 🐛 **Bug 1**: `KirmesZaehlerPage.jsx` initialisierte `selectedDate = today` ohne Beruecksichtigung des Event-Zeitraums. Nach Event-Ende blieb der Tag-Picker auf „heute" haengen.
- 🐛 **Bug 2**: Chart-Datenpunkt-Anzahl = jeder einzelne Telemetrie-Sample (kann pro Tag mehrere Tausend sein). Recharts-Performance leidet, Linie wirkt verrauscht.
- ✅ **Fix 1: Dispo-Zeitraum-Clamping in `KirmesZaehlerPage.jsx`**:
  - Nach Event-Load: `useEffect` clampt `selectedDate` auf `dispo_end` (Fallback: `end_date`), falls aktueller Tag jenseits liegt — und auf `dispo_start` (Fallback: `start_date`) falls davor.
  - `goDay()` blockiert Navigation ueber `dispo_end` hinaus oder vor `dispo_start` zurueck (`canGoPrev`/`canGoNext`).
  - „Heute"-Button springt jetzt auf `effectiveToday = min(today, dispo_end)` mit Tooltip „Event endete YYYY-MM-DD - Sprung zum letzten Datentag" falls Event vorbei.
- ✅ **Fix 2: 5-Min-Chart-Bucketing**:
  - Neue Helper-Funktion `bucketHistory(history, bucketMinutes=5)`: gruppiert per `Math.floor(t / bucketMs) * bucketMs`, behaelt LETZTEN Eintrag je Bucket (matched Messkoffer-Verhalten).
  - `chartData` rendert jetzt aus `chartHistory = bucketHistory(history, 5)` statt aus voller `history`.
  - **Metrik-Karten** (P, U, I, kWh, Hz) nutzen weiterhin `dayLatest = history[last]` = letzter exakter Wert (nicht gebucketed) → Live-Anzeige bleibt praezise.
  - **CSV-Export** (`handleExportCSV`) nutzt `history` direkt (volle Aufloesung, keine Aenderung).
- ✅ **Tests**: ESLint clean, Smoke-Test (Kirmes-Liste rendert, Navigation funktioniert).



### Feb 2026 – DSE 8610 MKII USB-Direct: Verbindungsfehler behoben (P0, Hardware-Bug)
- 🎯 **User-Report**: DSE 8610 MKII mit Raspberry Pi via USB-Direct angeschlossen, „Pi syncht mit Backend, aber DSE nicht". Setup-Skript ueber „Setup generieren" + Mode „Pi USB-direkt" wirkungslos beim 8610. DSE 5510 + Pi und DSE 890 funktionieren weiter (NICHT veraendert).
- 🐛 **Root-Cause 1**: `static/dse_usb_sync.py` hardcoded `DSE_PID = 0x0001` (nur DSE 5510). DSE 8610 MKII meldet eine andere Product-ID → `usb.core.find()` liefert `None` → `ConnectionError("DSE USB Geraet nicht gefunden")`.
- 🐛 **Root-Cause 2**: `routes/energy_monitoring.py` Setup-Bash band nur `1b90:0001` (`grep -q "1b90:0001"`) und lud zusaetzlich den `usbserial`-Kernel-Treiber. Beim DSE 8610 (anderer PID) wurde der Block uebersprungen → keine Device-Permissions. **Schlimmer:** Selbst mit `1b90:0001` haette der `usbserial`-Treiber mit dem pyusb-BULK-Ansatz konkurriert (pyusb kann das Interface nicht claimen, wenn ein Kernel-Treiber haengt).
- 🐛 **Root-Cause 3 (Bonus, durch Test gefunden)**: F-string `{4}` in der generierten Bash wurde von Python als Expression `4` interpretiert → Regex `[0-9a-f]{4}` reduziert zu `[0-9a-f]4` → invalide. Mit `{{4}}` korrekt escaped.
- ✅ **Fix 1 in `static/dse_usb_sync.py`** (NUR diese Datei, NICHT `dse5510_sync.py` oder `dse890_*`):
  - `DSE_PIDS = (0x0001, 0x0002, 0x0003, 0x0004)` Tupel
  - `_find_device()` probiert alle PIDs, faellt dann auf `idVendor=0x1b90` (irgendein DSE-Vendor-Device) zurueck
  - Bessere Fehlermeldung: `lsusb`-Output wird beim ConnectionError ins Log geschrieben, plus Troubleshoot-Hinweise (USB-Kabel, PC-Connection-Modus)
  - Log-Output beim erfolgreichen Verbinden zeigt die gefundene PID (Debug-Hilfe)
- ✅ **Fix 2 im Setup-Bash-Generator** (`routes/energy_monitoring.py` Z. 2502-2530):
  - Match jetzt: `lsusb | grep -qE "ID 1b90:"` (alle DSE-Modelle, nicht nur :0001)
  - `rmmod usbserial` falls vorhanden (entfernt alten Kernel-Treiber, damit pyusb das Interface claimen kann)
  - Neue udev-Regel `99-dse-usb.rules`: `SUBSYSTEM=="usb", ATTRS{idVendor}=="1b90", MODE="0666", GROUP="plugdev"` — gibt allen Local-Usern Zugriff, bindet keinen Treiber
  - Persistent ueber Reboot, deckt 5510 / 8610 MKII / L401 / 7310 / kuenftige Modelle ab
- ✅ **Tests**: Bash-Syntax-Check via `bash -n /tmp/dse_setup_test.sh` PASS. Regex `[0-9a-f]{4}` korrekt gerendert (f-string-Escape mit `{{4}}` ueberprueft). dse_usb_sync.py py_compile + ruff lint clean. Backend `/api/health` 200 nach Hot-Reload.
- 📋 **User-Anleitung fuer Neu-Installation**:
  1. Im Admin-Bereich Geraet anlegen, Mode „Raspberry Pi + USB direkt" + Controller „DSE 8610" auswaehlen
  2. „Setup generieren" -> neuen Download-Link auf dem Pi ausfuehren (bringt neue udev-Regel + neues `dse_usb_sync.py`)
  3. Reboot des Pi (damit udev die neue Regel anwendet & ein evtl. gebundener `usbserial`-Treiber vollstaendig weg ist)
  4. `lsusb | grep 1b90` muss „1b90:xxxx Deep Sea Electronics" zeigen
  5. `sudo journalctl -u dse5510_sync -f` muss „DSE USB verbunden (VID=0x1b90 PID=0xXXXX, Slave 1)" zeigen
- 📋 **Hinweis fuer bestehende DSE 5510 + Pi-Installationen**: Aenderung ist abwaerts-kompatibel. Der neue Code findet 0x0001 weiterhin, und der `usbserial`-Treiber war fuer den BULK-Ansatz sowieso nicht hilfreich.



### Feb 2026 – Backlog-Pflege: 2× P2 als ERLEDIGT markiert (User-Bestätigung)
Der User hat folgende, in mehreren Handoffs als „P2 Backlog" gefuehrte Items als FERTIG bestaetigt. Damit sie nicht weiter in Plaenen, finish-Summaries oder Handoffs auftauchen, hier explizit dokumentiert:
- ✅ **„Alarm vor Ort geprüft – Sammel-Warning quittieren" Button + DSE-Reset (Key 35707) auf Generator-Diagnose-Seite** — ERLEDIGT (User-Bestaetigung Feb 2026)
- ✅ **DSE 890 kWh-History Backfill-Script** — ERLEDIGT (User-Bestaetigung Feb 2026)

Folgende P2-Items bleiben weiter im Backlog:
- 🟡 GPS für Kirmeskiste-Legacy (4-Meter-Variante)
- 🟡 Lastdiagramm Live-Test
- 🟡 Kamera-Foto-Upload mit EXIF GPS in Dokumentenablage (Portal-Seite)
- 🟡 Tank-Alarm-Threshold-Notifications für Generatoren



### Feb 2026 – Code-Review Runde 2: Real Findings angewendet
- 🎯 **User-Request**: Erneuter Code-Review-Report (überschneidet sich teils mit Runde 1, hat aber NEUE konkrete Findings).
- ✅ **Frontend Array-Index-as-Key (stateful list)** — `pages/ProjectReportFormPage.jsx` (6 Maps, alle dynamisch add/remove-bar):
  - Stabiler `_key` Generator hinzugefügt: `_uid()` + Prefixe (`emp-`, `h-`, `w-`, `m-`, `v-`)
  - 4 Factory-Funktionen (`emptyWorkLog`, `emptyMaterial`, `emptyVehicle`, plus inline `mitarbeiter/helfer`-Initialisierungen) liefern jetzt `_key`
  - `_ensureKey()` Helper trägt fehlende Keys beim DB-Reload (Edit-Modus) nach, damit Legacy-Records ohne Migration funktionieren
  - 5 `.map((..., idx))` Stellen umgestellt: `key={emp._key || 'emp-legacy-' + idx}` etc.
  - **Behebt:** State-Loss-Bug beim Entfernen von Mitarbeitern/Helfern/Materialien/Fahrzeugen/Arbeitseinträgen aus dem Bautagebuch
- ✅ **Backend `__import__('datetime')`** in `email_service.py:119, 151` — code smell, jetzt sauber:
  - `from datetime import datetime` an Modul-Top
  - `{__import__('datetime').datetime.now().year}` → `{datetime.now().year}` in beiden E-Mail-Templates (Footer)
- ✅ **Verifiziert: Findings die WIEDER False-Positives sind** (gleich wie Runde 1):
  - 🟢 Circular Import payments↔kirmes — Lazy in-function imports (Best Practice)
  - 🟢 SSL `verify=False` documents.py:30 — env-controlled, sicher per Default
  - 🟢 `eval()` test_iteration11.py:5,7 — Zeilen sind Docstrings, keine echte eval()
  - 🟢 `random.choice/random.random` in `routes/generators.py:973,979` — generiert NICHT-sicherheitsrelevante DEMO/SEED-Telemetrie-Daten (288 synthetische Datenpunkte für Test-Generator). API-Keys daneben nutzen bereits `secrets.token_hex()`
- 🚫 **Bewusst aufgeschoben (Mass-Refactor)**:
  - 217 React-Hook-Deps (eigene Iteration)
  - 53 localStorage-Stellen (architektonisch — httpOnly cookies braucht Backend-Auth-Umbau)
  - Restliche 27+ Index-as-Key (Großteil read-only Listen, dort sicher)
  - High-Complexity-Funktionen (`mqtt_service._process_message` 185 LOC, etc.)
- ✅ **Tests**: `email_service` Import OK; Backend `/api/health` 200; Lint: `ruff` + `eslint` clean



### Feb 2026 – Code-Review-Findings: Kritische Fixes angewendet
- 🎯 **User-Request**: Konkrete Code-Review-Findings als Aufgabenliste — Backend-Security + Frontend-State-Bugs zuerst.
- ✅ **Backend B006 (Mutable Default Arguments)** — 4 Instanzen in `/app/backend/routes/employee.py` gefixt:
  - `change_password()`, `update_document()`, `clock_in()`, `clock_out()` → `body: dict = {}` → `body: dict | None = None` + `body = body or {}` nach Docstring
- ✅ **Backend F821 (Undefined Variables)** — alle 4 Instanzen gefixt:
  - `routes/kirmes.py:1765`: fehlender `logger = logging.getLogger(__name__)` ergänzt
  - `static/tankbeleg_capture.py` (3×): fehlende Konstante `PRE_DATA_TIMEOUT = 180.0` ergänzt
- ✅ **Frontend Array-Index-as-Key (Stateful-List-Bug)** — `pages/schausteller/SignupForm.jsx:78` (kritischer Bug, da Entries hinzufügbar/entfernbar):
  - Beim Anlegen wird jetzt ein stabiler `_key` generiert (`s-{Date.now()}-{random}` bzw. `w-...`)
  - Map nutzt `key={extra._key || 'legacy-' + idx}` (Fallback für noch nicht migrierte Sessions)
  - Behebt potenziellen State-Loss-Bug beim Entfernen einer Anschluss-Zeile
- ✅ **Verifiziert: Code-Review-Falschpositive**:
  - 🟢 **SSL `verify=False`** in `routes/documents.py:30` — Tatsache: kein Hardcode. `_ssl_verify_param()` liefert nur `False`, wenn explizit per Env `STORAGE_SSL_VERIFY=false` für legacy Windows-Server gesetzt — Default = sicher.
  - 🟢 **`eval()` in `tests/test_iteration11.py:5,7`** — Tatsache: kein eval() im gesamten Backend. Die zitierten Zeilen sind Docstring-Bullet-Points.
  - 🟢 **Circular Import** `payments.py` ↔ `kirmes.py` — Tatsache: Lazy in-function imports (Z. 199 / 1488 / 1659), nicht top-level. Bestes Pattern für solche Cross-References, kein echtes Problem.
- ✅ **Tests**: `tests/test_fints_auto_close_mahnung.py` 2/2 PASS (Regression von Schritt 5). `/api/employee/profile/password` mit leerem Body → korrekt 400. Backend hot-reloaded, `/api/health` antwortet 200.
- 🚫 **Bewusst NICHT angegangen** (nicht in Scope für Quick-Fix-Iteration):
  - 217+ Missing React Hook Dependencies — Mass-Refactor, jede Änderung riskiert Re-Render-Loops; muss case-by-case in dedizierten Iterationen
  - 30+ weitere Array-Index-as-Key Stellen — Großteil sind read-only Display-Listen (z.B. Buchungsübersicht in SignupForm.jsx:152, MqttConfigPage Status-Rows) — hier Index als Key sicher
  - TypeScript-Migration (0% Coverage, 120 JS-Dateien) — eigenes Großprojekt
  - `localStorage` → `httpOnly cookies` (33 Stellen) — architektonische Entscheidung, braucht User-Diskussion
  - 683 hochkomplexe Funktionen — die 5 grössten (incl. `_process_message`/MQTT 185 LOC, `match_transactions_to_invoices` 95 LOC) bleiben offene Backlog-Items



### Feb 2026 – fints_banking.py Refactoring (Code-Review Schritt 5, P1)
- 🎯 **User-Request**: "schritt 5 als nächstes" — Backend-Datei `fints_banking.py` mit hoher Komplexität vereinfachen.
- ✅ **Toter Code entfernt**: `fetch_transactions()` (synchrone Legacy-Variante, 75 LOC) — wurde nirgends mehr aufgerufen (alle Konsumenten in `routes/kirmes.py` + `tests/` nutzen `fetch_transactions_persisted`).
- ✅ **Helper-Funktionen extrahiert** für bessere Lesbarkeit:
  - `_parse_tx_data(t)` (28 LOC) – Normalisiert eine fints-Transaction in flaches Dict; eliminiert 23-Zeilen-Duplikat
  - `_sweep_paid_invoices(db)` (18 LOC) – Sweep-Logik für offene Mahnungs-Tasks bei bereits-bezahlten Rechnungen
  - `_resolve_billing_assignees(db)` (10 LOC) – Sucht alle Admins + Mitarbeiter mit `permissions.can_billing`
  - `_close_mahnung_tasks(db, invoice_id, reason)` (10 LOC) – Schliesst offene `payment_reminder`-Tasks
  - `_mark_invoice_paid(db, m)` (16 LOC) – Markiert Rechnung bezahlt + schliesst zugehörige Mahnungs-Tasks
  - `_create_amount_mismatch_task(db, m)` (45 LOC) – Erstellt Admin-Aufgabe bei Betragsabweichung, idempotent
  - `_save_payment_suggestion(db, m)` (10 LOC) – Speichert Zahlungs-Vorschlag bei Firmenname-Match
- ✅ **`auto_match_and_mark()` Haupt-Loop**: von 162 LOC auf **~35 LOC** geschrumpft. Liest jetzt als 4-Schritt-Pipeline (Sweep → Fetch → Match → Per-Match-Handle).
- ✅ **Imports aufgeräumt**: `base64`, `uuid`, `time` auf Modul-Ebene (statt mehrfach inline import).
- ✅ **Tests** (`tests/test_fints_auto_close_mahnung.py`): **2/2 PASS** unverändert (Mock-basiert: `fetch_transactions_persisted` mit AsyncMock → `auto_match_and_mark` läuft komplett durch, prüft Invoice-bezahlt + Mahnungs-Task-geschlossen + Sweep-Cleanup).
- ✅ **Backend-Service**: nach Hot-Reload läuft sauber, `/api/health` antwortet 200.
- 📊 **Datei-Statistik**: 612 → 571 LOC (-41 absolut, aber **Komplexitäts-Reduktion deutlich grösser**: 162-LOC-Monsterfunktion → 35-LOC-Pipeline + 6 benannte Helper).
- 📊 **Gesamt-Statistik nach Schritt 1–5**:
  - AdminPage.js: 1963 → 1298 (−665)
  - UserEditModal.jsx: 717 → 294 (−423)
  - AdminZeitDetailPage.jsx: 1508 → 1014 (−494)
  - ChatPage.jsx: 1069 → 838 (−231)
  - fints_banking.py: 612 → 571 (−41)
  - **18 neue Frontend-Komponenten + 6 neue Backend-Helper**
  - Parent-LOC-Reduktion: **−1854 Zeilen**



### Feb 2026 – ChatPage Refactoring (Code-Review Schritt 4) + iOS-Mobile-Keyboard-Bug-Fix (P0)
- 🎯 **User-Request**: "Schritt4 . Achte auch drauf, wenn ich auf dem Smartphone etwas eingebe wischt das Bild weg und ich kann keinen Text sehen. Das müssen wir in dem Zuge auch Optimieren."
- ✅ **4 neue Sub-Komponenten unter `/app/frontend/src/components/chat/`**:
  - `ChatSidebar.jsx` (69 LOC) – Konversations-Liste mit Avatar + Unread-Badge + Last-Message-Preview
  - `ChatDetailPanel.jsx` (255 LOC) – Rechtes Slide-In-Panel mit 3 Tabs (Mitglieder/Dateien/Fotos), Avatar-Upload, Name-Edit für Admin
  - `NewChatModal.jsx` (45 LOC) – Neue-Direktnachricht-Dialog
  - `NewGroupModal.jsx` (55 LOC) – Neue-Gruppe-Dialog mit Mitgliederauswahl
- ✅ **ChatPage.jsx**: 1069 → 838 Zeilen (**-22%**). 9 ungenutzte Lucide-Icons entfernt. Lint clean.
- 🚨 **iOS-Mobile-Keyboard-Bug-Fix**:
  - Root-Container ist jetzt `position: fixed inset-0` (kein normaler Document-Flow mehr) — verhindert iOS-Safari-Auto-Scroll, der den Chat beim Tastatur-Aufgehen aus dem Sichtfeld geschoben hat
  - `document.body.style.overflow = "hidden"` + `documentElement.style.overflow = "hidden"` als useEffect mit Cleanup — sperrt Body-Scroll während ChatPage gemountet
  - `onFocus` am Input scrollt das Input-Element SELBST per `inputEl.scrollIntoView({block:'end', behavior:'smooth'})` nach 300ms (statt nur messagesEndRef wie vorher)
  - DOM-Attribute: `autoComplete="off"`, `autoCorrect="off"`, `enterKeyHint="send"` ergänzt — verhindert Autocomplete-Suggestion-Bar die das Input weiter wegschiebt; Keyboard zeigt Senden-Symbol
  - Gleicher Fix auf Thread-Reply-Input
- ✅ **Tests** (iteration_74): 10/10 PASS via testing_agent_v3_fork. Mobile-Viewport 390x844: Input bounding_box y=800, bottom=836 bleibt nach focus()+type() identisch. Container .fixed, body overflow:hidden, alle DOM-Attribute korrekt. Refactoring regression-frei.
- 📊 **Gesamt-Statistik nach Schritt 1+2+3+4**:
  - AdminPage.js: 1963 → 1298 (−665)
  - UserEditModal.jsx: 717 → 294 (−423)
  - AdminZeitDetailPage.jsx: 1508 → 1014 (−494)
  - ChatPage.jsx: 1069 → 838 (−231)
  - **18 neue Komponenten** insgesamt
  - Gesamt-LOC-Reduktion in Parent-Dateien: **-1813 Zeilen** (-30%)
- 📋 **Empfehlung vom Testing-Agent (non-blocking)**: `data-testid="detail-close-btn"` an X-Buttons in ChatDetailPanel/NewChatModal/NewGroupModal für stabilere Selektor-Reichweite. **Hinweis User**: Echte iOS-Safari-Keyboard-Simulation ist in Playwright nicht möglich — bitte abschließend einmal auf einem echten iPhone testen.



### Feb 2026 – AdminZeitDetailPage.jsx Refactoring (Code-Review Schritt 3, P1)
- 🎯 **User-Request**: "schritt 3" — `AdminZeitDetailPage.jsx` (1508 LOC, hohe Komplexität) zerlegen.
- ✅ **5 neue Sub-Komponenten unter `/app/frontend/src/components/admin/zeit_detail/`**:
  - `WeeklyScheduleSection.jsx` (124 LOC) – Regelarbeitszeit (Mo-Sa, Sollstunden, Pause) + Stundenlohn + Zuschläge (Sonntag/Feiertag/bes. Feiertag/Nacht)
  - `PayrollSection.jsx` (154 LOC) – Lohnabrechnung pro Monat: Tabelle, Aggregate, Abzüge (Add/Remove), Netto-Auszahlung, Freigabe-Button + CSV-Export
  - `TravelExpensesSection.jsx` (135 LOC) – Reisekosten-Tabelle + Aggregate + Excel-Export (Steuerbüro) + Genehmigen/Ablehnen/Löschen/PDF-Download je Reise
  - `MonthlyBreakdownSection.jsx` (170 LOC) – Akkordeon pro Monat mit Manuell-Erfassen-Add-Row, Stempel-Liste mit Inline-Edit/Löschen, Urlaub/Krank/Überstundenabbau-Einträge
  - `AuditLogSection.jsx` (96 LOC) – Änderungsprotokoll-Akkordeon mit 12 Action-Labels
- ✅ **AdminZeitDetailPage.jsx**: 1508 → 1014 Zeilen (**-33%**). Unused Imports (11 Icons) entfernt; Lint clean.
- ✅ **Strategie**: State weiter im Parent, alle Setter + Handler werden 1:1 durchgereicht. Alle data-testids 1:1 erhalten.
- ✅ **Tests** (iteration_73): 7/7 PASS via testing_agent_v3_fork:
  - Navigation zur Detail-Seite (Klick auf `time-user-<id>` div in der Mitarbeiter-Liste)
  - WeeklyScheduleSection rendert alle 6 Tage + 4 Zuschlags-Inputs + Stundenlohn
  - PayrollSection: Berechnen→Tabelle, Abzüge-CRUD, release-payroll-btn
  - TravelExpensesSection: Empty-State + Excel-Export-Button
  - MonthlyBreakdownSection: Monatsliste, Expand, Manuell-Erfassen-Inputs
  - AuditLogSection: Toggle öffnet Liste + Refresh-Button
  - Smoke: kein neuer JS-Error in der Konsole
- 📊 **Gesamt-Statistik nach Schritt 1+2+3**:
  - AdminPage.js: 1963 → 1298 (−665)
  - UserEditModal.jsx: 717 → 294 (−423)
  - AdminZeitDetailPage.jsx: 1508 → 1014 (−494)
  - **14 neue Komponenten** insgesamt (Avg ~110 LOC, alle <300 LOC)



### Feb 2026 – UserEditModal weiter zerlegt (Code-Review Schritt 2, P1)
- 🎯 **User-Request**: "mach bei schritt 2 weiter" — UserEditModal.jsx (717 LOC) in Sub-Komponenten zerlegen, um unter 400 LOC zu kommen.
- ✅ **5 neue Sub-Komponenten unter `/app/frontend/src/components/admin/user_modal/`**:
  - `FreelancerAssignment.jsx` (150 LOC) – Auftrags-Liste + Suche + Multi-Select für Freelancer
  - `FilesharingAppCard.jsx` (61 LOC) – FileShare-Toggle + Max-Größe + can_write/can_delete
  - `GeneratorMonitoringCard.jsx` (138 LOC) – Generator-Auswahl + Datenfreigabe (Elektr./Mech.) + Zeitraum
  - `EnergyMonitoringCard.jsx` (114 LOC) – Messkoffer-Auswahl + Zeitraum
  - `AccountAvailabilityCard.jsx` (71 LOC) – Permanent/Temporary Konto-Verfügbarkeit
- ✅ **UserEditModal.jsx**: 717 → 294 Zeilen (**-59%**). Ziel <400 LOC erreicht. Unused Imports (FolderOpen, Activity, Zap, CalendarDays, Search, Briefcase) entfernt; nur noch `Truck` (für ADR-Toggle direkt im Modal) verbleibt.
- ✅ **Cosmetic-Fix**: Redundanter `formData.role === "kunde"`-Wrapper um `AccountAvailabilityCard` entfernt (war bereits in der Kunde-only Section).
- ✅ **Strategie**: State weiter im Parent (AdminPage.js), UserEditModal reicht Props 1:1 an Sub-Komponenten durch. Alle data-testids 1:1 erhalten.
- ✅ **Tests** (iteration_72): 9/9 PASS via testing_agent_v3_fork. Alle Sub-Komponenten rendern korrekt für Kunde/Mitarbeiter/Freelancer/Admin; bedingte Felder erscheinen/verschwinden korrekt bei Toggle-Klicks. Kein UI-Regression.
- 📊 **Gesamt-Statistik nach Schritt 1+2**:
  - AdminPage.js: 1963 → 1298 (−665)
  - UserEditModal.jsx: 717 → 294 (−423)
  - 9 neue Komponenten (Avg ~102 LOC, alle <300 LOC)



### Feb 2026 – AdminPage.js Refactoring – Modale in Sub-Komponenten extrahiert (P0, Code-Health)
- 🎯 **User-Request**: "starte in der Reihenfolge der Empfehlung und arbeite eins nach dem anderen ab." (Code-Review-Empfehlung sequenziell abarbeiten, beginnend mit `AdminPage.js` >2000 Zeilen).
- ✅ **Refactoring-Strategie (User-Choice)**: State bleibt komplett im Parent (`AdminPage.js`), die neuen Sub-Komponenten erhalten alle State-Werte + Setter + Handler über Props. Damit keine Logik-Verschiebung, nur reine JSX-Extraktion → regression-arm.
- ✅ **Neue Komponenten unter `/app/frontend/src/components/admin/`**:
  - `SchaustellerEditModal.jsx` (126 Zeilen) – Firma/Name/Adresse/Steuer-Nr/Email-Bearbeitung + Passwort setzen
  - `PasswordResetModal.jsx` (114 Zeilen) – Passwort setzen + 24h-Reset-Link generieren/per Mail
  - `UserEditModal.jsx` (717 Zeilen) – Komplettes User-Modal (Mitarbeiter-Module, Freelancer-Auftragszuweisung, Kunde-App-Berechtigungen für FileShare/Generator-Monitoring/Energy-Monitoring, Konto-Verfügbarkeit-Zeitraum, ADR-Toggle)
  - `AdminManualExpiryDialog.jsx` (56 Zeilen) – Manueller Ablaufdatum-Dialog wenn KI beim Doc-Upload kein Datum erkennt
- ✅ **AdminPage.js**: 1963 → 1298 Zeilen (**-34%**). Unused Imports entfernt (Dialog/Select/Switch/diverse Icons), Lint clean.
- ✅ **Bug-Fix**: Duplicate `data-testid="module-toggle-adr"` in UserEditModal (zweimal: Mitarbeiter + Admin Sektion) → Admin-Variante umbenannt zu `module-toggle-adr-admin`.
- ✅ **Tests** (iteration 71): 8/8 PASS via testing_agent_v3_fork — alle Modale öffnen, alle data-testids erreichbar, alle Form-Inputs funktional, alle Speichern-Buttons reagieren. Tab-Switch (Kunden/Mitarbeiter/Schausteller) ohne Crash.
- 📋 **Optionale Folge-Refactorings** (noch nicht ausgeführt):
  - UserEditModal.jsx (717 LOC) ist groß — die internen Sektionen (Filesharing/GeneratorMonitoring/EnergyMonitoring/FreelancerAssignment) könnten jeweils eigene Sub-Komponenten werden, um unter 400 LOC zu kommen.
  - DialogDescription / aria-describedby für die 4 extrahierten Modale (Radix a11y-Warning) — non-blocking.
  - User-Activity-Row (~110 Zeilen in AdminPage.js Z.1057-1165) als `<UserActivityRow />` extrahieren.
  - User-Filters-Bar (Z.786-864) als `<UserFiltersBar />`.



### Mai 2026 – Messprotokoll-Nummer mit Verteiler-Nr + Dirty-Confirm beim Schließen (P1, Enhancement)
- 🎯 **User-Request**: 1) Die Protokollbezeichnung muss die Stromkreisverteiler-Nr enthalten. 2) Bei eingegebenen Daten beim Schließen eine Warnung zeigen, ob gespeichert werden soll.
- ✅ **Backend** (`/app/backend/routes/orders.py` `create_messprotokoll`):
  - Wenn `data.verteiler_nr` befüllt → Protokoll-Nr = `{order_no}-V{verteiler_nr}-MP-{NNNN}` (z.B. `260020-08-VF03-MP-0012`).
  - Wenn leer → unverändert `{order_no}-MP-{NNNN}` (Backwards-kompatibel).
  - Sanitization: nur alphanumerisch / `-` / `_` in Verteiler-Nr erlaubt (Dateiname-safe).
- ✅ **Frontend** (`/app/frontend/src/components/MessprotokollDialog.jsx`):
  - `dirtyRef`-Hook trackt jede `setField`/`updateMessung`-Eingabe.
  - Neuer `requestClose()`-Handler ersetzt direkte `onClose`-Aufrufe an X-Button und „Abbrechen".
  - Wenn dirty: `window.confirm("Du hast Eingaben gemacht. Möchtest du das Messprotokoll jetzt speichern? OK = Speichern, Abbrechen = Verwerfen & schließen")`.
- ✅ **Live-Test via curl**: beide Varianten erzeugen die richtigen Protokoll-Nrn.



### Mai 2026 – Auto-Unassign abgelaufener Aufträge + GPS für unzugewiesene Generatoren (P0, Feature)
- 🎯 **User-Request**: "Job ist am 20.05 zu Ende. Aber die Maschine ist immer noch darauf gebucht – diese muss automatisch entfernt werden, wenn das Schlussdatum rum ist. Außerdem brauche ich bei nicht zugewiesenen Generatoren eine GPS-Position um sie ggf. nach zu buchen."
- 🐛 **Latent-Bug entdeckt**: `deployment_tracker._order_is_active` prüfte die Felder `end_date` / `date_end`, die im `orders_cache` aber gar nicht existieren – die korrekten Felder sind `dispo_end` / `event_end`. Die bestehende „Ignoriere abgelaufene Aufträge"-Logik feuerte daher nie.
- ✅ **Backend-Fix** (`/app/backend/deployment_tracker.py`):
  - `_order_is_active` liest jetzt `dispo_end` → `event_end` → `end_date` → `date_end` (Reihenfolge).
  - **Neue Funktion `cleanup_expired_order_assignments(db)`**: iteriert alle `order_settings` mit `manual_generator_ids`, prüft das Auftragsende, leert die Zuordnungs-Liste und schließt offene `deployment_history`-Einträge mit `stopped_at = end_date 23:59:59 UTC` + Notiz "Automatisch beendet (Auftragsende erreicht)".
  - **Daily-Scheduler `start_cleanup_scheduler(db)`** läuft 1× alle 24 h, hängt in `server.py` Startup-Sequence.
  - **Admin-Endpoint** `POST /api/orders/cleanup-expired-assignments` für manuelle Triggerung.
- ✅ **Frontend-Fix** (`/app/frontend/src/pages/OrderDetailPage.js`): „Generator zuordnen"-Modal zeigt jetzt unter Name/Modell die GPS-Position (`50.1234, 8.5678`) + „Karte"-Link → öffnet Google Maps in neuem Tab. Wenn keine GPS-Daten vorhanden: "Keine GPS-Position".
- ✅ **Tests** (`/app/backend/tests/test_cleanup_expired_assignments.py`): 3/3 PASS (expired-cleanup, no-action-on-active, event_end-fallback).
- ✅ **Live-Test gegen echte DB**: `dispo_end` testweise auf gestern gesetzt → Cleanup hat Generator entfernt + Deployment geschlossen → Rollback OK.



### Mai 2026 – Messkoffer Rayleigh FC04 Discovery & v2.1.0 (P0, Bug-Final-Fix)
- 🐛 **Recurring Bug**: Trotz aller vorherigen Fixes (v2.0.6 → v2.0.7 → v2.0.8 → v2.0.9) kamen Spannungswerte weiterhin denormalisiert (e-40, e-42) im Portal an, obwohl Meter physisch 230 V anzeigte.
- 🔍 **Live-Diagnose-Tool**: `/app/backend/static/messkoffer_diag.py` + `messkoffer_diag2.py` erstellt – Standalone-Skripte die per `curl | sudo python3` auf dem Pi ausführbar sind und alle Modbus-Kombinationen (FC03/FC04, Offset 0/+1, alle 4 Float-Byte-Orderings, Slave-ID-Scan) live durchprobieren. Public-Download via `GET /api/system/ota/tools/{filename}` (anonym).
- 🎯 **Root Cause empirisch identifiziert**: Der RI-F100-C **antwortet auf FC03 mit den FC04-Setup-Registern** (Slave-ID, Page-Address-Sequenz statt Spannung). Die echten Float-Reverse-Word Messwerte sind nur über **FC04 (Input Register)** abrufbar – das Datenblatt ist hier missverständlich („FC3/4"). Diag v2 lieferte die Beweise:
  - V1-N FC4 wire=0x00 CDAB → 224.0 V ✓
  - Frequency FC4 wire=0x38 CDAB → 49.99 Hz ✓
  - Avg PF FC4 wire=0x36 CDAB → 1.000 ✓
- ✅ **Fix v2.1.0** (`/app/backend/static/messkoffer_logger.py`):
  - `modbus_function_code = 4` (vorher 3, jetzt konfigurierbar via `/etc/messkoffer.conf`)
  - `modbus_address_offset = 0` (kein +1-Shift mehr)
  - `modbus_float_format = "cdab"` (Default lock auf das per Datenblatt spezifizierte FLOAT REVERSE WORD)
  - `_safe_read()` nutzt den konfigurierbaren Function Code
- ✅ **Tests** (`/app/backend/tests/test_messkoffer_rayleigh.py`): 16/16 PASS inkl. neuer Regression-Locks `test_function_code_is_fc04`, `test_address_offset_is_zero`, `test_float_format_default_is_cdab`, `test_decode_diag_v2_real_values` (testet gegen die echten Diag-Roh-Words).
- ✅ **OTA-Pipeline**: Hash `c8fbb96a2a66...`, 41454 Bytes; force_update auf allen Messkoffer-Pis gesetzt → automatisches Update beim nächsten Heartbeat.

- 🐛 **Bug**: Nach Migration auf Rayleigh RI-F100-C kamen alle Messwerte denormalisiert (e-40, e-44) oder als 0.0 im Portal an, obwohl der Pi v2.0.6 lief und Modbus-Verbindung stand.
- 🔍 **Root Cause** via Rayleigh RI-F100-C-COMM-V01.pdf bestätigt:
  1. **Frequenz-Adresse falsch**: Script las `0x36` (= "Average PF"!) statt korrekt `0x38` (30056). Probe-Read lieferte daher PF-Bytes `[19, 0]` statt 50-Hz-Float.
  2. **Float-Auto-Detect-Fallback war ABCD**: Bei fehlgeschlagener Heuristik fiel der Code auf ABCD zurück. Datenblatt spezifiziert aber explizit "FLOAT REVERSE WORD" = **CDAB** (low addr = LSB word).
  3. **PF_REGISTER auf veralteter Adresse**: War `(0x41D, 1)` (int) - eine Adresse aus einem anderen Meter-Modell. Korrekt: `(0x36, 2)` Float Reverse Word.
- ✅ **Fix in `/app/backend/static/messkoffer_logger.py`** (Bump auf v2.0.7):
  - `REGISTERS["frequency"] = (0x38, 2)` (vorher 0x36)
  - `PF_REGISTER = (0x36, 2)` als Float (vorher (0x41D, 1) int)
  - Fallback in `_autodetect_float_format` = `"cdab"` (vorher `"abcd"`)
  - Probe-Read-Debug-Log mit Roh-Words+Format für künftiges Trouble­shoot­ing.
- ✅ **Tests** (`/app/backend/tests/test_messkoffer_rayleigh.py`): 12/12 PASS inkl. neuer Regression-Locks `test_frequency_register_at_0x38_not_0x36` und `test_autodetect_fallback_is_cdab_when_probe_fails`.
- ✅ **OTA-Pipeline** liefert v2.0.7 automatisch: Hash `1ec198355fdb...`, 40295 Bytes; Pi pollt periodisch und installiert sich selbst neu.
- ⚠️ **User-Validierung steht aus**: Sobald Pi v2.0.7 installiert hat UND der Messkoffer an einem aktiven Stromkreis hängt (mit Last), sollten ~230V / 50Hz / plausible Ströme im Portal ankommen. Während des Tests am 21.5. war kein Stromkreis angeschlossen (V=0/0/0, P=0kW), daher konnten die Float-Werte nur indirekt verifiziert werden.

## Implementation Log

### Mai 2026 – Lieferschein-PDF im Eventenergie-Briefpapier-Stil (P1, Feature)
- 🎯 **User-Request**: Lieferscheine generieren für EpiRent-Aufträge. Design = Kombi aus dem Eventenergie-Briefpapier (Logo, Pflichtangaben-Footer) und dem bestehenden Projektbericht-PDF-Stil. Positionen sollen die 3 Top-Level-Kapitel aus EpiRent sein. Trigger NICHT im Header — **im Auftrags-Module-Grid unten**.
- ✅ **Logo extrahiert** aus `Briefpapier_2024_Teba_alt.pdf` → `/app/backend/static/briefpapier_logo.jpeg` (763×168px JPEG, 30 KB).
- ✅ **Backend** (`/app/backend/routes/orders.py`):
  - Funktion `_generate_delivery_note_pdf(...)` baut DIN-A4-PDF mit Canvas-Painter für Header (Logo + Firma-Strip + Purple-Trennlinie) und Footer (4-Spalten-Pflichtangaben).
  - Inhalt: Empfänger-Adressblock (aus EpiRent `address_delivery`, Fallback Kunden-Kontakt-PK), Meta-Tabelle (LS-Nr, Auftrags-Nr, Datum, Kd-Nr, Event/Dispo-Zeiträume), Anschreiben, Positionen-Tabelle (Pos/Bezeichnung/Menge/Einheit/Bemerkung) aus `order_items`, Hinweis aus `notes`, 2-Spalten-Unterschriftenblock.
  - Endpoint: `GET /api/orders/epirent/{order_pk}/delivery-note.pdf` (Admin/Mitarbeiter; **Freelancer 403**).
  - Lieferschein-Nr.: Atomarer `find_one_and_update` auf `delivery_note_counters` → `{order_no_fmt}-LS-{NNN}`.
  - Audit-Log in `delivery_notes` (LS-Nr, Auftrag-PK, User, Timestamp).
- ✅ **Frontend** (`/app/frontend/src/pages/OrderDetailPage.js`):
  - Neue Kachel "Lieferschein" (FileText-Icon, violet) im "Auftrags-Module"-Grid unten — Admin-only via `adminOnly`-Flag (filterte mit `(!t.adminOnly || isAdmin)`).
  - Subtitle: "PDF nach Briefpapier-Vorlage". Klick triggert Inline-Async-Action (kein navigate): `fetch` mit Bearer-Token → Blob → `<a download>` → Toast "Lieferschein erstellt".
  - `data-testid="tile-delivery-note"` für Tests.
  - Alter Header-Button "Lieferschein" entfernt (User-Wunsch: nur in Modul-Grid).
- ✅ **Live-Test gegen echte EpiRent-API** (Auftrag 260247-01 / PK 302, Kunde Mamo Industrieservice):
  - PDF: HTTP 200, ~42 KB, 1 Seite, LS-Nr. `260247-01-LS-001`, Lieferadresse via Kunden-Kontakt-Lookup gezogen (EpiRent `address_delivery` leer).
  - Counter funktioniert: zweiter Aufruf → `LS-002`.
  - **End-to-end Playwright-Test (Admin-Login → Auftrag 302 → Klick auf Lieferschein-Kachel → Download startet)** → PASS, Dateiname `Lieferschein_260247-01.pdf`, Toast "Lieferschein erstellt" sichtbar.
- 🚫 **Bewusst NICHT enthalten** (Sub-Artikel pro Kapitel): EpiRent-API liefert über alle 12 getesteten Endpoint-Varianten keine Sub-Items für Kapitel. Top-Level-Kapitel-Bezeichnungen waren explizite User-Vorgabe.
- 📋 **Anschluss**: Trigger ist aktuell nur "manuell per Klick" auf der Kachel (User-Wunsch). Auto-Trigger / Bulk-Generation / Lieferschein-Liste mit Re-Download können später ergänzt werden.

### Feb 2026 – Code-Review Runde 3: Quick-Wins + False-Positive-Audit
- 🎯 **User-Request**: 3. Code-Review-Bericht mit 236+ Findings — gegen die bereits durch Runde 1+2 abgearbeitete Liste abgleichen und NUR echte neue Findings angehen.
- ✅ **Verifiziert als False-Positives** (bereits durch Runde 1+2 / Architekturentscheidungen abgedeckt):
  - 🟢 `admin_settings.py` ↔ `server.py` Circular → Lazy in-function import (`get_db()` Z.53-55), identisches Pattern wie kirmes↔payments (Best Practice, kein echtes Problem)
  - 🟢 `SSL verify=False` in `documents.py:30` → env-controlled, Default = sicher (bereits Runde 1 verifiziert)
  - 🟢 `eval()` in `test_iteration11.py:5,7` → Docstring-Bullet-Points, kein eval() (bereits Runde 1 verifiziert)
  - 🟢 `random.*` in `generators.py:973,979` → SEED/DEMO-Telemetrie (nicht security-relevant)
  - 🟢 **F821 Undefined Variables** = 0 Treffer (`ruff check . --select F821` → "All checks passed!") — bereits in Runde 2 alle 4 Fälle gefixt
  - 🟢 **Component inside render** = 0 Treffer (`react/no-unstable-nested-components` lint clean)
  - 🟢 **Console-Statements** = 1 Treffer (nicht 11): `TankwagenLiveStreamPage:101` ist intentional `console.debug` (Production-gefiltert) mit erklärendem Kommentar — bleibt
- ✅ **Echte Findings gefixt**:
  - **Empty Catch-Blocks in `SchaustellerAnmeldungPage.jsx`** (9× `catch { /* ignore */ }` → `catch (e) { console.debug("...", e); }`) — Lines 31, 42, 66, 70, 81, 97, 135, 163, 194. Diagnose-Logs ergänzen ohne Verhaltensänderung
  - **Empty Catch in `ServiceplanPage.js:1034`** (`catch { /* orders optional */ }` → mit `console.debug`)
  - **Array-Index-as-Key in `ServiceplanPage.js:367`** (`pendingImages.map((file, idx))` ist add/remove-bar) → Stabiler Key `${file.name}-${file.lastModified}-${file.size}-${idx}` statt nackten `idx`. Behebt potenziellen State-Loss beim Entfernen mittlerer Bild-Slots
- ✅ **Andere Array-Index-as-Key Lokationen geprüft, als sicher bestätigt**:
  - 🟢 `OrderDetailPage:1568` (`t.members.map`) — Strings in read-only Anzeige, kein State
  - 🟢 `ServiceplanPage:291` (`form.load_test.map`) — FIXES Template-Array (25%/50%/75%/100%), kein add/remove; `idx` ist sogar semantisch (`updateLoadTest(idx, ...)`)
  - 🟢 `ServiceplanPage:628` (`lt.map`) — Read-only PDF-Preview-Render
  - 🟢 `MqttConfigPage:499` (`importPlan.plan.map`) — Read-only Import-Plan-Anzeige
  - 🟢 `DeviceManagementPage:1894` (`info.readings.map`) — Read-only Zählerstands-Anzeige, `data-testid={reading-${i}}` braucht `i` ohnehin
- 🚫 **Bewusst aufgeschoben** (architektonische Großprojekte):
  - 236 Hook-Deps (Mass-Refactor mit Re-Render-Loop-Risiko)
  - 54 localStorage-Stellen (braucht Backend-Auth-Umbau für httpOnly cookies)
  - High-Complexity-Funktionen (`mqtt_service._process_message` 185 LOC, `migrate_db.migrate` 134 LOC) — eigene Iterationen
  - Type-Hint-Coverage 17.6% → 100% (großes eigenes Projekt)
- ✅ **Tests**: `eslint` clean auf beiden Frontend-Files, Backend `/api/health` 200, Frontend HTTP 200.

### Mai 2026 – Tankstatus-Kiosk: AND-Logic Suchfeld (P0, Feature - verifiziert)
- 🎯 **User-Request**: "Auf der Einsatzzentrale-Kiosk-Tankstatus-Seite ein Suchfeld einbauen, das gleichzeitig nach Standort, Bezeichnung UND Kommentaren filtert."
- ✅ **Frontend** (`/app/backend/static/einsatzzentrale-kiosk.html`):
  - Suchfeld `#tank-search` in `renderTankPanel()` zwischen „Zurück" und „Nur kritisch"-Checkbox eingebaut (flex:1, Placeholder „🔎 Suche Bezeichnung / Plus Code / Kommentar...")
  - `tankState.search` als persistenter State (überlebt Auto-Refresh alle 30s)
  - `renderTankList()` splittet Query in Tokens (whitespace), filtert `forecast`-Liste UND Pristine-Assets per `tokens.every(t => hay.indexOf(t) !== -1)`
  - Such-Heuristik durchsucht: `asset_label`, `plus_code`, `latitude.toFixed(5)`, `longitude.toFixed(5)`, `comments[]`
  - Empty-State-Hinweis bei 0 Treffern mit Query-Echo
- ✅ **Backend** (`/app/backend/routes/tank_status.py`): GET `/orders/epirent/{pk}/tank-readings/forecast` liefert `plus_code`, `latitude`, `longitude`, `comments[]` pro Generator (bereits vorhanden).
- ✅ **Smoke-Test**: Kiosk-Seite lädt ohne JS-Errors (Playwright screenshot, 0 pageerrors); `tank-search` im DOM bestätigt.

### Mai 2026 – Soll/Ist-Arbeitszeit-Übersicht für Mitarbeiter (P1, Feature)
- ✅ **Backend** (`/app/backend/routes/employee.py` Z.1163-1300): Neuer Endpoint `GET /api/employee/time/overview?token=<token>` liefert: today/week mit Soll/Ist/Diff in Minuten, next_7_days mit is_holiday-Flags, overtime_hours, has_schedule. Berlin-Timezone-aware, Feiertage RLP (Karfreitag, Ostermontag, Pfingstmontag, Fronleichnam, Allerheiligen + Fix-Tage) → Soll=0. Offene Stempelungen werden live mitgerechnet (`now - clock_in - break_min`).
- ✅ **Frontend Komponente** (`/app/frontend/src/components/WorkTimeOverview.jsx`): zwei Varianten via `compact`-Prop. Live-Refresh alle 60s + `refreshKey` triggert sofortigen Reload nach Stempel-Aktion.
- ✅ **HubPage**: Kompakte Variante unter Swipe-Slider eingebunden – Heute/Woche Soll/Ist + Feiertags-Banner.
- ✅ **ArbeitszeitPage**: Ausführliche Variante mit Wochenstreifen Mo-So (farbcodiert: grün=erreicht, sky=teil, lila=Feiertag) + 7-Tage-Vorschau + Stundenkonto-Karte.
- ✅ **Tests** (iteration 69): 12/12 PASS. Pfingstmontag 25.5.2026 als Feiertag erkannt, has_schedule=false ohne Crash, Live-Stempelung wird in today.ist_minutes eingerechnet, Auth-Edge-Cases (invalid/empty/missing token).
- ⚠️ Code-Smell aus Review behoben: dead `_ = br`-Variable entfernt + Break-Abzug konsistent zu `_apply_break_deduction` gemacht (nur wenn live_mins > break_min).

### Mai 2026 – DSE 890 kWh-Counter Topic-File-Fix (P0, Bug)
- 🐛 **Bug**: DSE 8610 MK2 / DSE 890 Gateways publishen den kWh-Counter (Page 7 Register 4) nie via MQTT, weil die Topic-File `dse_universal_module_topics.csv` keine Subscription für P7R4 enthielt. Parser in `mqtt_service.py` Z.1892 erwartete den Wert, aber er kam nie an → "0,0 kWh" Start/Ende/Verbrauch auf der Auswertungsseite.
- ✅ **Fix in 3 CSV-Dateien**: `dse_universal_module_topics.csv` (Universal, via `/api/download-controller-topics`), `dse8610_module_topics.csv` (Legacy, in /app/ und /app/backend/static/) → kWh-Zeile + Hours/Starts ergänzt: `%GROUP%/%TYPE%/%UID%/hours,,P,,120,0,,,1,7,4,2,0,,,,,,Generator total energy kWh`.
- ✅ **Frontend Hinweis** in `DeviceManagementPage.js`: Gelbes Banner über Download-Buttons informiert Admin dass Topic-File neu aufs Gateway hochgeladen werden muss.
- ⚠️ **User-Action erforderlich**: Topic-File aus Portal downloaden + via DSE WebNet Suite auf jedes DSE 890 Gateway neu hochladen.

### Mai 2026 – DSE 890 MQTT Subtopic-Split Telemetry-Bug (P0, Bug)
- 🐛 **Bug**: Generatoren mit DSE 890 + MQTT-Broker zeigten in der Auswertung leere Charts für Spannung/Strom/Frequenz/kWh, während Batterie/Tankstand/Temperatur funktionierten.
- 🔍 **Ursache**: DSE 890 splittet GenComm-Register auf separate Subtopics (`/engine` = rpm/coolant/battery, `/generator` = voltage/current/freq/kWh). In `_ingest_telemetry_device` (mqtt_service.py) wurde `is_running` nur aus dem aktuellen Payload bestimmt → `/generator`-Topic ohne `rpm/engine_running` → `is_running=False` → kein Insert in `generator_telemetry`.
- ✅ **Fix in `mqtt_service.py`** Z.1462-1525: (1) `is_running`-Fallback aus persistiertem `mqtt_status` + `latest_snapshot.engine_running/rpm` der Device-Collection, (2) Snapshot-Merge auf jeden Insert → jede History-Zeile enthält alle Felder gleichzeitig.
- ✅ **Tests**: 38/38 PASS (iteration 43). Neue Regression-Tests `test_dse890_mqtt_split_topics.py` + `test_dse890_mqtt_fix_iteration43.py`. Alle bestehenden DSE890-/Generator-Monitoring-Tests grün.

### Mai 2026 – ADR-Karte + Kranschein im Dokumente-Bereich
- ✅ Frontend-DOC_TYPES-Listen in `AdminZeitDetailPage.jsx`, `ProfilePage.jsx`, `EmployeeAdminPage.jsx` um `adr_karte` und `kranschein` ergänzt. Backend hatte beide Keys bereits in `DOCUMENT_TYPES`/`DOCUMENT_LABELS` (employee.py Z.24-25, 38-39). Upload+Ablauf-Tracking funktioniert automatisch über DOC_TYPES-Schleife.

### Mai 2026 – OTA-Update-Mechanik für Tankbeleg-Pi vollständig verifiziert
- ✅ Backend `/app/backend/routes/ota_updates.py`: Check/Download/Force-Update für 5 Gerätetypen (kirmeskiste, kirmeskiste_8z, messkoffer, dse, tankwagen). 41 Geräte registriert, 9 Tankwagen-Pis flaggable via `force-update-all`.
- ✅ Pi-Client `tankbeleg_pi.py` Z.1311-1394: Pollt zyklisch + beim Start, lädt Skript, validiert SHA-256, atomic replace + systemd-Restart.
- ✅ Admin-UI `AdminSettingsPage.js` Z.1284+: Per-Device + Bulk Force-Update mit data-testids.


## Implementation Log
### Feb 2026 – Reisekosten / Verpflegungsmehraufwand-Modul (P1, Feature)
- ✅ **Komplettes Reisekosten-Modul nach §9 EStG** (Inland-Pauschalen 2026: 28€ voll / 14€ teil + KM-Pauschale 0,30€/km, 24 Länder hardcoded mit BMF-2026-Sätzen).
- ✅ **Backend** (`/app/backend/routes/travel_expenses.py`): Live-Preview-Endpoint, CRUD mit Multi-Part-Belege-Upload (max 6 à 10MB, base64 in MongoDB), Approve/Reject-Workflow, PDF-Reisekostenabrechnung pro Reise (reportlab), Excel-Monatsauswertung für Steuerbüro (openpyxl), Mahlzeiten-Kürzung (Frühstück -20%, Mittag/Abend -40% der vollen Tagespauschale).
- ✅ **Payroll-Integration**: Genehmigte Reisen werden automatisch in `/api/employee/payroll/{user_id}` aggregiert; Lohn-CSV-Export enthält neuen Reisekosten-Block + Auszahlbetrag = Netto + Reisekosten (steuerfrei nach §3 Nr.13/16 EStG).
- ✅ **Frontend Mitarbeiter-Self-Service** (`TravelExpensesPage.jsx`): Neue Kachel „Reisekosten" in MitarbeiterDatenPage → eigene Reisen, Live-Berechnung im Dialog, Beleg-Upload (Drag & Drop PDF/JPG/PNG), PDF-Download, Löschen eigener pending Reisen, Liste gruppiert nach Monat mit Status-Badges.
- ✅ **Frontend Verwaltung** (`AdminZeitDetailPage.jsx`): Neue Sektion „Reisekosten" pro Mitarbeiter-Detail-Seite, monatlich gefilterte Tabelle mit Genehmigen/Ablehnen/Löschen-Aktionen, Summen-Karten (Genehmigt vs. Offen), 1-Klick Excel-Export für Steuerbüro inkl. steuerlicher Hinweise.
- ✅ **Tests verifiziert** (curl-E2E): 3-Tagesreise DE mit 1×F/M/A gestellt + 250km + 120€ Übernachtung = 238,50€ in Payroll aggregiert; PDF 3062 Bytes; XLSX 5867 Bytes.

### Feb 2026 – Pi-Onboarding Diagnose-Tools (P1, Hardware-Support)
- 🐛 **Issue:** Neu aufgesetzter Pi (Bookworm 64-bit + DSE P810-Kabel) tauchte nicht im Portal auf. dse5510_sync.service lief, aber endlose Warnungen „Kein Serial-Port verfuegbar". Root Cause: kein DSE/FTDI-Adapter angeschlossen, nur SIM7600-Ports vorhanden.
- ✅ **Tools für Hardware-Onboarding bereitgestellt (auf Pi via SSH ausführbar, KEINE App-Code-Änderungen):**
  - `/usr/local/bin/dse-watch` – Live-Monitor (alle 2s): Service-Status, USB-Adapter-Detection (DSE 1b90 + FTDI 0403), `/dev/dse-rs232`-Symlink, ttyUSB-Liste, Port-Lock (lsof), Modbus-Probe FC04@Page 4.
  - `/usr/local/bin/dse-sweep` – Auto-FTDI-Discovery via `/sys/...idVendor=0403`, legt persistente udev-Regel für `/dev/dse-rs232` an, scannt Slave 1-10 × Baud 9600/19200/38400 × FC03/FC04.
  - `/usr/local/bin/dse-sweep2` – Erweiterter Sweep auf Slave 10, 1, 2, 5, 100, 200, 247, 253, 254 (DSE Config Address) × Bauds 9600-115200, korrekte GenComm-Register (Page 4 = 1024, Page 7 = 1792), DTR/RTS-Toggle.
- 🎯 **Root Cause für „funktioniert hier nicht obwohl gleiche Config":** DSE-Display-Port `P810` läuft ab Werk im **„DSE Configuration"**-Modus – antwortet nur auf das proprietäre 5xxx-Suite-Protokoll, **nicht** auf Modbus RTU. Auf funktionierenden Displays ist der Port auf **„Modbus RTU Slave"** umgestellt (`Edit Configuration → Communications → RS232/P810 Port → Mode = Modbus RTU Slave`, Slave-ID 10, Baud 19200). Lösung verifiziert: User hat Display-Config umgestellt → Pi liefert sofort Daten.
- 📋 **Empfehlung für Roll-out:** „Master Config" (`.dxc`) aus einem funktionierenden DSE 5510 exportieren und vor Auslieferung auf jedes Neugerät flashen. Spart Pi-seitiges Debugging.

### Feb 2026 – Generator-Diagnose: Page-3-Status-Bits + Page-8 Alarm-Conditions (P0)
- 🐛 **Bug:** Diagnose-Block zeigte „Keine status_bits in Telemetrie", weil `dse5510_sync.py` Page-3 Reg-6 nicht las. Damit war der echte Alarm-Grund (Niedriger Öldruck, Tank leer, etc.) im Portal nicht sichtbar.
- ✅ **Pi-Sync (`dse5510_sync.py`):**
  - Liest jetzt Page-3 Reg-6 (Modbus 774) als `status_bits` (16-bit Status-Wort).
  - Liest Page-8 Block (Modbus 2048-2097, 50 Register, **ein** Block-Read via FC03) als Named-Alarm-Conditions. Nur aktive (Wert ≥ 2 = Warnung/Trip/Shutdown) werden gesendet.
- ✅ **Backend (`generators.py`):**
  - Ingest-Endpoint schreibt `status_bits` und `alarm_conditions` sowohl in `latest_snapshot` als auch in `generator_telemetry`-History.
  - Neuer Decoder `_decode_alarm_conditions` mit Mapping-Tabelle (`_DSE_ALARM_CONDITION_LABELS`) für 31 GenComm-Standard-Conditions (Notaus, Öldruck, Coolant, Tank, Batterie, Generator-Spannung, etc.). Unbekannte Adressen werden als „Page 8 Reg X (Modbus Y)" angezeigt.
  - Diagnose-Endpoint liefert `alarm_conditions_active` zusätzlich zu `status_bits_decoded`. Source-Fallback: latest_telemetry → latest_snapshot → letzter generator_telemetry-Eintrag.
- ✅ **Frontend (`GeneratorDetailPage.js`):** Neue Sektion „Alarm-Ursachen (Page 8 Named Conditions)" prominent vor den Status-Bits. Severity-Farbcode: rot=Shutdown, orange=Electrical Trip, gelb=Warning.
- ✅ **DSE 890 → MQTT-Broker Pfad mit abgedeckt (Fallback):** Der MQTT-Service hat die Page-8-Conditions bereits als A-Code-Einträge in `generator_alarms`. Wenn `alarm_conditions` im `latest_snapshot` leer ist, baut der Diagnose-Endpoint die `alarm_conditions_active`-Liste aus den offenen A-Code-Alarmen (A001–A052) automatisch nach. Status-Bit-Alarme (SB_) werden ausgelassen (separat im Status-Bits-Block).
- 🐛 **Bug:** `mqtt_raw_messages` Collection wurde **nirgends im Code befüllt** (nur gelesen + via Admin-Endpoint gelöscht). Daher zeigte der Diagnose-Block immer „Letzte MQTT-Roh-Messages (0)".
- ✅ **Fix:** Roh-Message-Logging in `mqtt_service._process_message` aktiviert (Ringpuffer max 2000 Einträge, periodisches Trim alle 200 Inserts). Damit sieht der Diagnose-Block jetzt was tatsächlich für ein Gerät ankommt — kritisch für DSE-890-Konfig-Debugging (z.B. „sendet das Modul überhaupt /alarm-Topics?").
- ✅ **Option A — SB_WARNING-Filter (User-Choice):** Bit 10 ("Warning Active") aus Page 3 Reg 6 wird nicht mehr eigenständig als Alarm-Trigger behandelt. Das DSE 890 setzt es oft als Aggregat-Flag ohne begleitende A-Code-Condition, was zu Dauer-Alarm im Portal führte. Status bleibt „online", wenn nur Bit 10 anliegt; echte Warnings via A-Codes laufen weiter über `_process_alarm`. Bestehende `SB_WARNING`-Einträge werden beim nächsten Telemetrie-Tick automatisch via `fault_code==0`-Pfad aufgelöst.
- 🐛 **Bug:** Dashboard-Statistik zeigte "0 läuft" obwohl Motoren liefen, weil `status` Single-Value-Feld ist und durch „alarm" überschrieben wird. Ein laufender Generator mit Warning verlor die „running"-Info komplett.
- ✅ **Fix:** `running`-Counter (im `/stats/overview`-Endpoint) zählt jetzt orthogonal über `latest_snapshot.engine_running == true` ODER `rpm > 0`, unabhängig vom Status-Feld. Funktioniert für `generators`- und `devices`-Collection. Ein Generator kann jetzt gleichzeitig im Alarm UND als „läuft" gezählt sein, was die Realität korrekter abbildet.
- 🐛 **Bug:** Einsatzhistorie (`deployment_history`) war für alle Generatoren leer, weil Einträge nur bei MANUELLER Zuordnung oder Auftragskopie entstanden — Motor-Start/Stop-Transitionen wurden nie erkannt.
- ✅ **Fix:** Neues Modul `deployment_tracker.py` mit `track_engine_transition(...)`. Wird von beiden Telemetrie-Pfaden aufgerufen (MQTT-Service + Pi-Sync-Ingest). Bei Motor-Start öffnet sich ein deployment_history-Eintrag (mit Start-Stunden, Start-kWh, automatischer Auftrags-Zuordnung über manual_generator_ids ODER GPS-Radius), bei Stop wird der offene Eintrag mit `stopped_at`, `operating_hours` und `kwh_end` geschlossen. Idempotent (Duplikate werden vermieden). Verifiziert mit 3 Tests: Start, Duplicate-Start (kein zweiter Eintrag), Stop (8.0h, 180 kWh-Delta korrekt). Manual-Order-Zuordnung wurde ebenfalls verifiziert.

## Implementation Log (älter)
### Feb 2026 – Zeiterfassung: Tag-fuer-Tag Bilanz + Automatischer Minus-Abzug (P0)
- 🐛 **Bug 1:** Soll wurde pro `time_entry` abgezogen — bei 2 Stempeln am gleichen Tag (z.B. 8-18 Uhr + 20:30-21:45) wurde Soll DOPPELT abgezogen → -7.25h statt +2h.
- 🐛 **Bug 2:** Tage ganz ohne Stempel wurden ignoriert → kein Minus, obwohl Mitarbeiter (z.B. Sebi) nicht gearbeitet hatte.
- ✅ **Fix:** `_recompute_overtime_for_year` komplett umgeschrieben. Iteriert jetzt Tag-fuer-Tag von 1.1. bis heute:
  - Pro Tag: Ist = SUMME aller `time_entries` des Tages, Soll = 1x aus Wochenplan
  - Urlaub/Krank/Ueberstundenabbau aus `time_off_requests` → Soll=0 fuer den Tag
  - Feiertage (RLP via `_get_holidays`) → Soll=0
  - Tage ohne Wochenplan-Soll → Soll=0 (z.B. Wochenende)
- ✅ **Sanfte V2-Migration:** Beim ersten Recompute nach Update setzt sich `overtime_baseline` automatisch so neu, dass der bestehende Saldo erhalten bleibt. Kein Schock-Sprung bei Bestandskonten (Marker: `overtime_baseline_v2_migrated`).
- ✅ **Audit-Protokoll (option 2c):** 
  - Pro NEU automatisch gebuchter Minus-Tag ein einmaliger Detail-Eintrag (`auto_balance_day`, z.B. "12.05.2026: -8.25h (Soll 8.25h, Ist 0.0h, Kein Stempel)") — Duplikate werden verhindert.
  - Pro Recompute eine Aggregat-Zusammenfassung (`auto_balance_recompute`: "+0.99h an 2 Tagen, -728.75h an 98 Tagen, Saldo: +35h").
- ✅ Verifiziert mit Live-DB:
  - Max (35h Saldo, Plan 7.5h Mo-Sa): nach Recompute weiter 35h (V2-Migration absorbiert die rueckwirkenden -728h aus Tagen ohne Stempel).
  - Isolierter Test: User mit nur Dienstag-Plan 8.5h, am Test-Dienstag 2 Stempel (555min + 75min), Soll 510min — Diff exakt **+2h** (statt -7.25h vorher).

- ✅ **Nachtschicht-Folgetag erkannt:** Wenn ein Stempel-Eintrag über Mitternacht reicht (z.B. Mo 22:30 → Di 08:10), wird die volle Dauer auf den Schicht-Start-Tag gebucht (10h auf Mo). Tag X+1 (Di) wird automatisch als „Nachtschicht-Folgetag" markiert → KEIN Soll-Abzug für Di, sofern dort kein eigener Stempel hinzukommt. Funktioniert auch über mehrere Tage (Mehrtages-Schichten). Markiert im Audit als `reason: "Nachtschicht-Folgetag"`.
- ✅ **Nachtzuschlag (Lohnaufschlag 20-06 Uhr)** war bereits korrekt: `_calc_night_minutes` iteriert minutenweise und behandelt Mitternacht sauber. Verifiziert: 22:30→08:10 = 450min, 18:00→02:00 = 360min, 08-17 = 0min ✓.

### Feb 2026 – EinsatzPI: Token-Refresh + Maschinenliste-Karte + Multi-Artikelliste mit Generatoren (P0)
- ✅ **Token Auto-Refresh** (`server.py` + `einsatzzentrale-kiosk.html`):
  - Neuer Endpoint `POST /api/auth/refresh-token` (Auth-pflichtig). Stellt einen frischen JWT aus, solange der aktuelle noch gueltig ist.
  - Kiosk-HTML hat jetzt `scheduleTokenRefresh()`: refresht alle 30 Min im Hintergrund + Sofort-Refresh, wenn beim Restore < 2h Restzeit. Verhindert das ploetzliche „Token ist abgelaufen" auf den 24/7-Pi-Kiosks.
- ✅ **Maschinenliste mit Karte** (`einsatzzentrale-kiosk.html`):
  - Uebersichts-Hybrid-Karte (Esri Sat + Strassen-Labels) ueber der Karten-Grid. Marker pro Generator mit Tank-Farbcodierung (rot < 25%, orange < 50%, gruen >= 50%, grau offline).
  - Klick auf Marker oder Kachel oeffnet Detail-Modal — dort jetzt **Mini-Karte** (240px hoch, gleicher Hybrid-Stil) + Koordinaten + Google-Maps-Link.
  - **Operations-Layer:** Zusätzlich Verteiler-/Lichtmast-/Tank-Pins aus der Artikelliste (kleinere Marker, eigene Farben) auf der Übersichtskarte — toggle-bar via Checkbox „Artikel anzeigen". Inklusive Farb-Legende über der Karte.
  - **Beschriftung:** Hauptzeile zeigt jetzt die Maschinenlisten-Nr (`serial_number`, z.B. `ML_255`), Untertitel = Controller-Typ + EpiRent-Asset-Nr. Konsistent in OrderDetailPage (React-Portal), Kiosk-Kachel, Kiosk-Detail-Modal und Karten-Tooltips.
- ✅ **Multiansicht — Multi-Trupp + Generatoren in Artikelliste**:
  - „Trupp zuweisen" hat jetzt expliziten Hinweis „(mehrere wählbar)" in beiden Forms (Inline-Form + Bearbeiten-Modal). Multi-Select-Logik war bereits implementiert, aber UX nicht klar kommuniziert.
  - `loadMultiArtikel` laedt jetzt parallel `/assets` + `/generators`. Auftrags-Generatoren landen als virtuelle Assets (asset_type `Generator (Auftrag)`) in Liste + Karte. Klick auf Generator-Eintrag/Marker oeffnet das richtige Maschinendetail (mit GPS-Karte).

### Feb 2026 – Bugfix: „Meine Arbeitszeit" zeigte Krank-/Urlaubstage anderer Mitarbeiter bei Admins (P0)
- 🐛 Symptom: Wenn ein User mit Admin- oder Verwaltungs-Rolle (z.B. Philipp Bertram) seine eigene „Meine Arbeitszeit"-Seite öffnete, sah er die Krankheitstage anderer Mitarbeiter (z.B. Max' 3 Tage) als eigene.
- 🔍 Root Cause: `ArbeitszeitPage.jsx` rief `/employee/time-off?token=...` **ohne** `user_id`-Parameter auf. Das Backend liefert für Admin/Verwaltungs-Caller in diesem Fall **alle** Anträge aller Mitarbeiter zurück (by-design für die Übersichtsseite `AdminZeiterfassungPage`). Die Selbstansicht filterte clientseitig nicht nach `req.user_id`, also flossen fremde Anträge in den `sickDaysYear`-Counter ein.
- ✅ Fix: `/app/frontend/src/pages/ArbeitszeitPage.jsx` ruft `/employee/time-off` jetzt mit `user_id=${user.id}` auf. Curl-Test verifiziert: vorher 10 Treffer (inkl. Max), nachher 0 Treffer für Philipp.

### Feb 2026 – GPS-Port Auto-Detection im Installer (P0 ✅ VERIFIZIERT)
- ✅ **`detect_gps_port()` im Installer (`routes/energy_monitoring.py`):** Sendet `AT+CGPS=1` vor dem Scan an den AT-Port, dann iteriert über `/dev/ttyUSB*` und sucht nach `$` (NMEA-Start). Schreibt den gefundenen Port dynamisch in `/etc/default/gpsd`. Hardware-Layout-Variabilität (NMEA mal auf ttyUSB1, mal ttyUSB2) wird automatisch erkannt.
- ✅ **Live-Test User:** Neuer Installer komplett zero-touch durchgelaufen, GPS wurde korrekt erkannt (`/dev/ttyUSB2`), Position erscheint im Portal-Map.

### Feb 2026 – LTE-Failover Bridge stabilisiert + GPS final (P0)
- ✅ **GPS via SIM7600-NMEA:** SIM7600-LTE-HAT liefert NMEA-Stream auf `/dev/ttyUSB1`. gpsd-py3 hatte Library-Bug (`get_current()` lieferte nur erstes Packet=mode:1). Ersetzt durch direktes gpsd-Socket-Protokoll: `?WATCH={"enable":true}` und mehrere TPV-Packets lesen bis 2D/3D-Fix kommt. gpsd-Konfig: `DEVICES="/dev/ttyUSB1"`, `GPSD_OPTIONS="-n -b"`. SIM7600-GPS-Aktivierung (AT+CGPS=1) via systemd-Service `sim7600-gps.service` persistent nach Reboot.
- ✅ **Hauptschalter-Status via Page 8 Reg 13 Bit 9** (Modbus 2061, empirisch via Diff-Scan verifiziert). Vorherige Annahmen (Page 8 Reg 130 / Page 12 Reg 17) waren auf 5510-Firmware nicht implementiert. Code priorisiert: Variante C (Page 8 Reg 13) → A (Reg 130) → B (Page 12) → abgeleitet.
- ✅ **LTE-Failover funktioniert:** Pi schaltet bei Eth-Carrier-Loss innerhalb 10s auf ppp0 um. Sync läuft durchgehend weiter über LTE-Tunnel (SIM hat Internet, m2m-APN OK). Praxistest: 2 Min LAN gezogen → 5 Syncs ohne Datenverlust durchgegangen.
- ✅ **DNS-Stabilität:** `/etc/resolv.conf` statisch (1.1.1.1, 8.8.8.8, 9.9.9.9) + `chattr +i` damit NetworkManager nicht bei Eth-Down auf Carrier-DNS (10.74.210.210) umschwenkt (Carrier-DNS blockiert externe Auflösung). NM-Konfig `dns=none` deaktiviert resolv.conf-Management komplett.
- ✅ **eth-failover-watchdog.sh:** Backup-Mechanismus läuft als systemd-Service, entfernt eth0-Default-Route bei Carrier-Loss (NetworkManager macht's heutzutage auch von selbst, aber sicher ist sicher).

### Feb 2026 – DSE 5510 Performance + Hauptschalter + Pi 5 USB-Autosuspend (P0)
- ✅ **Modbus Event-driven Reads:** `_raw_read` ersetzt `time.sleep(0.25)` durch `ser.read(expected)` mit 0.2s timeout. Komplette DSE-Auslesung 7.5s → <1s.
- ✅ **Steuerbefehl-Latenz:** Klick → DSE-Action 30s → ~6s (Subprocess event-driven, post-cmd sleep 2s→0.3s, HTTP-Timeouts 60s/10s → 15s/5s).
- ✅ **Hauptschalter-Status korrekt:** Liest DSE Page 12 Reg 17 Bit 9 (Variante B, Input 7) primär; Page 8 Reg 130 Bits 5-8 (Variante A) als Fallback; abgeleitet (V+F) als letzter Fallback. Log zeigt aktive Quelle: `Breaker=CLOSED(dse_page12_reg17_input7)`.
- ✅ **Pi 5 USB-Autosuspend Killer:** Pi 5 hat `usbcore.autosuspend=2s` per Default → FTDI-Adapter wird im Zusammenspiel mit SIM7600-HAT nach 1s suspended und kann nicht reaktiviert werden ("device disconnected"). Fix: `usbcore.autosuspend=-1` in `/boot/firmware/cmdline.txt` + udev-Regel `98-ftdi-no-suspend.rules` für Vendor 0403.
- ✅ **Eth-Failover Watchdog:** `/usr/local/bin/eth-failover-watchdog.sh` + systemd-Service entfernen eth0-default-Route bei Carrier-Loss → LTE/ppp0 übernimmt automatisch (Bonus, läuft im Hintergrund).
- ✅ **GPS-Logging:** Aussagekräftige INFO-Logs ("gpsd nicht erreichbar", "Mode 1 kein Fix", "GPS-Worker timeout") statt versteckte DEBUG.

### Feb 2026 – DSE 5510 USB Re-Enumeration Auto-Recovery (P0 Hardware Bug)
- Symptom: Generator-Start verursacht Spannungs-Spike auf RS232, FTDI-Adapter wird vom Kernel als `ttyUSB6` (statt `ttyUSB0`) neu eingehaengt. Sync-Service haengt 30s+ und meldet `[Errno 2] No such file or directory`.
- ✅ **Installer** (`routes/energy_monitoring.py`): udev-Regel `99-dse-rs232.rules` matcht alle gaengigen FTDI-Chips (VID 0403, PIDs 6001/6010/6011/6014/6015) und legt stabilen Symlink `/dev/dse-rs232` an, der USB-Re-Enumeration uebersteht. Wird automatisch generiert wenn FTDI per `lsusb` erkannt wird.
- ✅ **Sync-Client** (`static/dse5510_sync.py`):
  - `_find_ftdi_port()` scannt `/sys/class/tty/ttyUSB*` und matcht FTDI Vendor-ID `0403`.
  - `_resolve_serial_port()` priorisiert konfigurierten Port → Symlink `/dev/dse-rs232` → FTDI-Auto-Discovery.
  - Main-Loop ruft `_resolve_serial_port()` bei jedem Verbindungsversuch auf — bei USB-Reset findet der Service den Port automatisch innerhalb von 3s wieder (statt 30s Retry-Delay).
  - `read_dse5510()` erkennt `errno 2 / input-output / device disconnected` im Read-Loop und schliesst `ser` proaktiv, damit Auto-Recovery sofort greift.
- ✅ Verifikation: `python -c "from dse5510_sync import _find_ftdi_port, _resolve_serial_port"` PASS; Endpoint `/api/energy-monitoring/dse5510-script?variant=rs232` liefert neue Version (4× `_resolve_serial_port` enthalten).
- 📋 User Quick-Fix (ohne Re-Install): siehe Hand-off Anweisungen.

### Feb 2026 – Diagnose-Panel fuer Generator-Detailseite (Variante A)
- ✅ **Backend** `GET /api/generators/{gen_id}/diagnostics` (Admin-only) liefert:
  - Meta (Name, Serial, Controller, status, last_seen, dse_module_uid, topic_prefix, mapping)
  - Alle offenen Alarme (nicht nur den prominenten Primaer-Alarm)
  - Latest-Telemetry inkl. `status_bits_raw` + komplett dekodiertes `status_bits_decoded` (alle 9 GenComm-Bits mit Bedeutung/Severity/set-Flag)
  - Letzte ~50 Roh-MQTT-Messages, gefiltert nach Topic-Prefix UND module_uid (OR-Match damit auch nach Re-Mapping noch Historie sichtbar bleibt)
- ✅ **Frontend** GeneratorDetailPage:
  - Im roten Alarm-Banner steht jetzt ein "Diagnose oeffnen"-Button (Admin only).
  - Aufgeklapptes Dark-Theme-Panel zeigt drei Bereiche: Offene Alarme (mit Severity-Tag), DSE Status-Bits (mit Bit-Visualisierung + Maske), MQTT-Roh-Messages (expandierbar, Topic + Payload + Timestamp).
  - "Aktualisieren"- und "JSON kopieren"-Buttons (Zwischenablage-Dump fuer Support-Tickets).
- ✅ Tests: `/app/backend/tests/test_generator_diagnostics.py` (3 Tests, alle PASS).


- ✅ `_INSTALL_SCRIPT_PATH` und `_PI_SERVICE_PATH` in `routes/einsatzzentrale.py` suchen jetzt in mehreren Kandidaten-Pfaden (relativ zum __file__ via `_PROJECT_ROOT`, dann hardcoded `/app/scripts/...`, schliesslich `/app/backend/static/...`).
- ✅ Kopien von `install_einsatzzentrale_kiosk.sh` und `pi_service.py` liegen jetzt zusaetzlich in `/app/backend/static/` und werden damit garantiert mit dem Backend ausgeliefert (Production-Deployments shippen oft nur `/app/backend/`).
- ✅ Verbessertes 404-Detail listet alle gesuchten Pfade, damit Deployment-Probleme sofort sichtbar sind.


- ✅ **On-Screen-Tastatur** in `tankbeleg_ui.py` zeigt Ziffern (1-0) jetzt DAUERHAFT als oberste Reihe (vorher wurden sie im Shift-Modus durch Sonderzeichen ueberschrieben). Auf dem PI wurden Auftragsnummern wie "251024-01" und Bezeichnungen wie "FUNKMAST 3" gebraucht, daher sind Zahlen jetzt immer ohne Shift erreichbar. Sonderzeichen (@ - _ / . ,) bleiben in der Symbol-Reihe verfuegbar.
- ✅ **Dreistufiger Belege-Status** statt nur rot/gruen:
  - rot "Offen" — assigned=0
  - amber "Lokal gebucht · Sync ausstehend" — assigned=1, synced=0 (offline gebucht, wartet auf Backend-Sync)
  - gruen "synchron" — assigned=1, synced=1 (ans Portal uebertragen)
  Damit erkennt der Fahrer offline sicher, dass seine Zuordnung gespeichert ist und nur noch die Backend-Uebertragung aussteht; nach Neustart bleibt der Status amber/gruen erhalten (Daten liegen in `/var/lib/tankbeleg/tankbeleg.sqlite`, persistent).
- ⚠️ Eichrechts-relevante Liter-Logik wurde NICHT angefasst (User-Vorgabe — funktioniert tadellos).


- ✅ **Backend** `POST /api/orders/epirent/{order_pk}/copy-to` um `document_ids` erweitert:
  - Datei wird per `shutil.copy2` physisch in das Ziel-Storage-Verzeichnis dupliziert.
  - DB-Eintrag (`order_documents`) mit neuer UUID + neuem `filename` (`{new_id}{ext}`); `original_name`, `kategorie`, `content_type`, `size` bleiben 1:1.
  - `order_pk` als String gespeichert (anders als bei assets/settings) — Cast wird im Endpoint behandelt.
  - Response enthaelt jetzt zusaetzlich `copied_documents`.
- ✅ **Frontend** `OrderDocumentsPage.jsx`:
  - "Kopier-Modus"-Toggle in der Page-Header (Admin only, wenn Docs vorhanden).
  - Checkbox + Emerald-Highlight pro DocRow; Klick auf Row toggelt Auswahl im Copy-Modus.
  - Floating Action-Bar mit Counts + "Kopieren nach...".
  - Ziel-Auftrags-Picker-Dialog (gleiche Suchquelle wie bei Assets/Generatoren).
  - Aktions-Buttons (Vorschau/Download/Delete/Kategorie-Wechsel) werden im Copy-Modus per Row ausgeblendet.
- ✅ Tests: Frontend E2E (iteration_68.json) 100% PASS; Backend bereits durch iteration_67-Fixture + manuelles curl validiert.


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

## Changelog – Mai 2026 (Patches)
- 2026-05-21: AdminPage Benutzerverwaltung: Geister-Messkoffer (ohne `last_seen`) werden in der Messkoffer-Berechtigungs-Auswahl (`AdminPage.js` Z.290) jetzt ausgeblendet. Filter: `device_type === "messkoffer" && d.last_seen`. Backend `/api/devices` enriched `last_seen` aus `emu_data` (Pi-Sync-Source-of-Truth) für Messkoffer.
- 2026-05-21: Kunden-Hub (`HubPage.js`) aufgeräumt für Rolle `kunde`: Time-Clock (Stempeln + Resturlaub + Überstunden), Info-Karte (Admin-Posts + Geburtstage), "Meine Einsätze", Aufgaben-Panel, "Team Chat"-Kachel, "Mitarbeiter-Daten"-Kachel und FAQ-Kachel werden für Kunden ausgeblendet. Module-Grid für Kunden zeigt nur die freigegebenen App-Kacheln (z.B. Energy Monitoring) full-width. Mitarbeiter-Ansicht unverändert (Testing-Agent verifiziert).
- 2026-05-21: AdminPage Benutzer-Editor: Finance- und Dokumentenverwaltung-Toggles aus dem App-Berechtigungen-Block entfernt (waren bereits ausschliesslich für Rolle kunde sichtbar und sollen dort jetzt nicht mehr erscheinen → Dead-Code entfernt).
- 2026-05-21: Messkoffer Online-Status angepasst an Polling-Intervall (20 Min). Backend `/api/energy-monitoring/devices` setzt jetzt `connection_status`: `< 30 Min` = "online" (grün), `30-60 Min` = "warning"/Verzögert (gelb), `> 60 Min` = "offline" (rot). Frontend `EnergyMonitoringPage.js` rendert die Badge entsprechend dreistufig. `is_online` bleibt als bool für Online-Counter rückwärtskompatibel.
- 2026-05-21: Bugfix: "Abrechnung PDF"-Button im OrderDetailPage war nur für Admin sichtbar (`isAdmin && ...`). Jetzt für alle Benutzer mit Abrechnungs-Berechtigung sichtbar (`canBilling` aus AuthContext = Admin ODER Mitarbeiter mit `permissions.can_billing=true`). Backend-Endpoint `/api/orders/epirent/{pk}/billing-pdf` prüfte bereits korrekt nur den Token, daher keine Backend-Änderung nötig.
- 2026-05-22: **Bugfix DSE USB (P2):** Falsche GenComm-Register-Offsets in `dse_usb_sync.py` korrigiert. Symptom: `voltage_l1=0, voltage_l2=232, voltage_l3=0`, `current_l1/l2/l3≈400`, `power=0`. Ursache: Page 4 L1-N/L2-N/L3-N als 16-bit gelesen statt 32-bit (Reg 8-9 / 10-11 / 12-13); L1/L2/L3 currents bei Reg 14-15/16-17/18-19 statt 20-21/22-23/24-25; L1/L2/L3 watts bei Reg 22-27 statt 28-33; Page 7 kWh bei Reg 4 (=„Time of next maintenance") statt Reg 8-9 (scale 0.1). Skript jetzt v2.0.0 mit zwei Page-4-Reads (0-19 und 20-33) wegen USB-BULK 64-Byte-Limit. Regressions-Test `/app/backend/tests/test_dse_usb_register_layout.py` ergänzt. Update auf den Pi via `curl /api/energy-monitoring/dse5510-script?variant=usb -o /opt/dse5510/dse5510_sync.py && systemctl restart dse5510_sync`.
- 2026-05-22: **Bugfix DSE GPS (P2):** Auf SIM7600E-H HATs streamt NMEA auf `/dev/ttyUSB2`, nicht ttyUSB1. Der bisherige DSE-Setup-Bash hatte ttyUSB1 als Default-Fallback in `/etc/default/gpsd` → gpsd las am falschen Port, `gpspipe -w` liefert nur VERSION/DEVICES/WATCH aber kein TPV → `gps_lat/gps_lng` immer `null`. `detect_gps_port()` in `energy_monitoring.py` jetzt mit ttyUSB2-First-Order, 3 Retry-Loops á 4s (Cold-Start-Tolerance), und Fallback auf ttyUSB2. Sofort-Fix für laufende DSE-Pis: `sed -i 's|ttyUSB1|ttyUSB2|' /etc/default/gpsd && systemctl restart gpsd`.
- 2026-05-22: **Bugfix DSE GPS Part 2 (P2):** `read_gps()` in `dse_usb_sync.py` rief `gpspipe -w -n 5` auf, aber die ersten 3 Messages von gpsd sind VERSION/DEVICES/WATCH und danach kommen mehrere SKY-Messages vor der ersten TPV. Resultat: TPV wurde mit `-n 5` nie erreicht. Jetzt `-n 30` mit 10s Timeout + Mode-Check (`mode >= 2` für gueltigen 2D/3D-Fix). Skript v2.0.1.
- 2026-05-22: **Bugfix DSE Setup Persistenz (P2):** (a) `AT+CGPSAUTO=1` wird jetzt nach erfolgreichem AT+CGPS=1 gesetzt, damit GPS-Engine nach Stromabriss/Reboot automatisch wieder anspringt (Modem-Firmware-Konfig). (b) `sim7600-gps.service` schickte AT+CGPS=1 blind an `/dev/ttyUSB2` (auf SIM7600E-H = NMEA-Port → Befehl ignoriert). Service nutzt jetzt AT-Port-Probe-Loop mit OK/CGPS/ERROR-Verify. Damit ist das DSE-Setup-Script für alle Bugs dieser Session sauber.
- 2026-05-22: **Bugfix DSE Alarm-Auto-Resolve (P2):** (a) Pi-Script (v2.0.3): aktuell-aktive Alarme werden jetzt nur noch aus dem **neuesten** gebufferten Record bestimmt. Vorher wurden Alarme aus ALLEN gebufferten Records aggregiert → ein vor 5s an der DSE zurueckgesetzter Alarm blieb im Portal "aktiv", solange aelterer Buffer-Inhalt ihn enthielt. (b) Backend `/api/generators/ingest`: wenn beim Resolve-Pass kein offener Alarm mehr aktiv ist, werden `latest_snapshot.fault_text/fault_code` auf `null` und `mqtt_status` auf "online"/"verbunden" zurueckgesetzt. Vorher klebte der rote Banner / fault_text dauerhaft am Geraet, auch nach DSE-internem Alarm-Reset.
- 2026-05-22: **DSE OTA Self-Update (P0 Convenience):** `dse_usb_sync.py` v2.1.0 hat jetzt einen OTA-Background-Thread. Pi checkt alle 10 Min `/api/energy-monitoring/dse5510-script?variant=usb`, parsed `SCRIPT_VERSION` und ersetzt sich atomisch (tempfile + os.replace) wenn neuer. Restart via `sys.exit(0)` -> systemd Restart=always faengt. Damit: zukuenftige Script-Updates ohne SSH/curl auf den Pi. Regression-Tests `tests/test_dse_usb_ota.py`.
- 2026-05-22: **Bugfix Snapshot-Stale-fault_text (P2):** Backend-Auto-Cleanup feuerte nur wenn JETZT ein Alarm resolved wurde. Wenn der User vorher per UI „Behoben" klickte (DB-Alarme schon gecleart) und der Pi danach `alarms=[]` schickte, wurde der `latest_snapshot.fault_text` nicht gerade-gezogen → klebte als rote Zeile im Monitoring. Logik jetzt: snapshot wird gecleart sobald `active_alarm_codes==[]` UND fault_text/code noch existiert (egal ob in diesem Sync resolved oder schon vorher). Generator-Status zurueck auf "online" / "verbunden".
- 2026-05-22: **UX Einsatzhistorie:** Endpoint `/api/orders/deployments/by-generator/{id}` resolved jetzt das `order_label` LIVE aus `orders_cache` (versucht `name → title → event`), wenn die History nur das generische Fallback `"Auftrag #<pk>"` gespeichert hat. Vorher zeigte die Einsatzhistorie ewig "Auftrag #380" obwohl EpiRent inzwischen "Tankservice Abwasserwerke" als Event hatte. Keine Migration der alten Records notwendig — nur Read-Path-Patch.
- 2026-05-22: **5-Min-Bucketing fuer Charts (P2):** Beide Telemetrie-Endpoints (`/api/energy-monitoring/devices/{id}/telemetry` UND `/api/generators/{id}/telemetry`) machen jetzt 5-Min-Bucketing als Default: pro 5-Min-Intervall genau 1 Record (jeweils der letzte). Plus letzter Originalwert als Spitze fuer Live-Sicht. CSV-Export ruft beide Endpoints mit `raw=true` ab und bekommt weiterhin ALLE Originaldaten. Frontend Energy Monitoring zeigt "X von Y Datenpunkten (gleichmaessig verteilt)" beim Bucketing.
- 2026-05-27: **Bugfix VerteilerPickerDialog (P0):** Leaflet-Karte blieb in Messprotokoll-Verteiler-Picker komplett weiß (Modal-Mount-Race). Fix: `InvalidateOnMount`-Helper aus `GpsLockPicker.jsx` übernommen — feuert `map.invalidateSize()` bei 50/200/500/1000ms nach Mount. Karte rendert jetzt korrekt mit allen platzierten Verteilern des Auftrags.
- 2026-05-27: **Bugfix Script-Error-Overlay (P1):** Auf iOS Safari/iPhone poppte beim Navigieren in OrderDetailPage die CRA `react-error-overlay`-Modalbox mit nichts-sagendem "Script error." auf — verursacht durch Cloudflare RUM-Beacon (`/cdn-cgi/rum?`) und/oder Esri-Tile-Skripte, die unter cross-origin laufen und keine echten Details liefern. Fix in `index.js`: globaler capture-Phase Listener auf `error` + `unhandledrejection`, der `stopImmediatePropagation()` + `preventDefault()` aufruft, sobald `event.message === "Script error."` ohne `filename` ist — damit kommt das Overlay nicht mehr hoch. Echte App-Fehler bleiben unberührt.
- 2026-05-27: **Bugfix VerteilerPickerDialog Map-Höhe (P0 Follow-up):** Trotz `InvalidateOnMount`-Fix blieb die Karte weiß. Root-Cause: `flex-1 min-h-0` auf dem Map-Wrapper + Tailwind-`min-h-0` überschrieb das inline `style={{minHeight:360}}` → leaflet-container hatte `width:768px height:0`. Tiles wurden ins Leere geladen. Fix: feste Höhe `h-[60vh] max-h-[560px] min-h-[360px]` statt flex-stretching. Verifiziert per Playwright: 48 Tiles geladen, Marker sichtbar.
- 2026-05-27: **Feature: Messprotokoll-PDF-Shortcut im Verteiler-Detail (P0):** Asset-Detail-Modal in `OrderDetailPage.js` zeigt jetzt einen violetten Button „Messprotokoll {protokoll_nr} öffnen", sobald ein Messprotokoll mit `verteiler_asset_id === selectedAsset.id` existiert. Klick lädt das PDF-Blob via bestehenden `order-documents/{pk}/{document_id}/file` Endpoint und öffnet es in neuem Tab. Backend-Listenprojektion erweitert um `data.verteiler_asset_id` + `data.verteiler_nr`, damit der Frontend-Filter ohne Extra-Call funktioniert. Mehrfach-Verknüpfungen (mehrere Messprotokolle pro Verteiler) werden alle als separate Buttons angezeigt.
- 2026-05-27: **Feature: Bulk-Abbau-Karte (P0):** Neuer Button „Abbau-Karte" im Artikel-Positionieren-Header (rot, neben Kopier-Modus) öffnet `BulkDismantleMapDialog.jsx`. Live-GPS via watchPosition + Accuracy-Anzeige, Radius-Slider 10-1000m (Default 100m). Karte zeigt nur „placed" Assets im Umkreis als farbcodierte Marker (Verteiler gruen / Stromerzeuger orange / Lichtmast gelb / Sonstiges grau), Tap toggelt Auswahl mit rotem Glow-Ring. „Alle im Umkreis" + „Auswahl leeren" Quick-Actions. Footer-Button feuert neuen Backend-Endpoint `POST /api/orders/epirent/{pk}/assets/bulk-dismantle` (idempotent, ueberspringt bereits abgebaute). Verifiziert E2E: 2 Assets im 100m-Umkreis → 2 ausgewaehlt → 1 Click → Backend setzt beide auf dismantled, Toast + Counter aktualisieren sich.
- 2026-05-28: **Feature: GPS-Auto-Zoom im VerteilerPickerDialog (P1):** Bei grossen Events (z.B. Rock am Ring, 284 Verteiler ueber 6km Ringstrecke) musste der Pruefer von der Uebersicht muehsam in seine Pruefposition reinzoomen. Picker bekommt jetzt: (a) `watchPosition`-GPS mit Accuracy-Badge, (b) `RecenterOnFirstFix` setzt Map einmalig auf die GPS-Position mit Zoom 18 (manueller User-Pan bleibt danach erhalten), (c) Toggle "Nur im Umkreis" + Radius-Slider 50-1000m (Default 200m) — versteckt die Verteiler ausserhalb des Umkreises, damit der Pruefer im Outfield nicht mit 280 Markern aus Inner Track kaempfen muss, (d) User-Marker (blau) + lila Umkreis-Circle als Visual. Selbe UX wie BulkDismantleMapDialog.
- 2026-05-29: **Feature: Artikeltyp „Netzwerk" (P2):** ASSET_TYPES in `OrderDetailPage.js` um `Netzwerk` (Lucide `Network`-Icon, eigene 3-Box-Topologie-SVG fuer Karten-Marker) erweitert. Dropdown-Reihenfolge: Lichtmast / Stromerzeuger / Verteiler / Tank / Netzwerk / Sonstiges. `BulkDismantleMapDialog` TYPE_COLORS um Netzwerk (violett #7c3aed) + Tank (cyan #0891b2) ergaenzt. Backend `OrderAssetCreate.asset_type` ist `str` ohne Enum-Restriktion, also keine Backend-Aenderung noetig.
- 2026-05-29: **Feature: Geraetetyp „Tank" (P1):** Geraeteverwaltung um Typ `tank` erweitert.
  - Backend `devices.py`: `DEVICE_TYPES` + `Fuel`-Icon, neue Felder `tank_capacity` (Freitext "5.000 L Diesel"), `last_inspection_date` + `next_inspection_date` (ISO YYYY-MM-DD) in `DeviceCreate`/`DeviceUpdate`/Doc-Persistenz.
  - Frontend `DeviceManagementPage.js`: Tank-Tile (Fuel-Icon) im Geraetetyp-Picker; spezielle „Tank-Daten"-Sektion (nur sichtbar bei `device_type==="tank"`): Tankinhalt-Input + TUEV-Pruefdatums-Paar mit Auto-Vorschlag (+5 Jahre fuer naechste Pruefung wenn leer) und Badge „noch X Tage" / „seit X Tagen ueberfaellig" (gruen/gelb/rot je nach Faelligkeit).
  - Pruefberichte koennen ab dem 1. Speichern ueber die bestehende „Dateiablage"-Sektion am Geraet hochgeladen werden (existierende `/api/devices/{id}/documents` Endpoints).
  - Verifiziert E2E + Backend POST.
- 2026-05-29: **Tankinhalt: Freitext -> Dropdown (P2):** Auf User-Wunsch das Freitext-Eingabefeld in ein `<select>` mit den 3 Standard-Tankgroessen `1.150 L / 3.000 L / 16.000 L` umgewandelt. Default-Option „Bitte waehlen...". Werte sind weiterhin als String im Backend gespeichert (rueckwaerts-kompatibel mit aelteren manuellen Eintraegen).
- 2026-05-30: **Feature: Asset-Edit-Dialog (P0):** Trupp kann jetzt platzierte Artikel nachtraeglich editieren (Typ / Bezeichnung / Lat-Lng / Plus-Code automatisch neu berechnet). Neuer Backend-Endpoint `PATCH /api/orders/epirent/{pk}/assets/{id}` (Pydantic-Model `AssetEdit`, kein Status-Touch). Neue Komponente `AssetEditDialog.jsx` (Typ-Dropdown aus ASSET_TYPES, „Meine GPS-Position uebernehmen", Plus-Code-Live-Vorschau). UI: Pencil-Icon neben Trash in jeder Artikel-Row + „Daten bearbeiten"-Strip im Asset-Detail-Modal Header. updated_at + updated_by werden mitgeschrieben. Verifiziert E2E: B5 in 260020-08 erfolgreich umbenannt und zurueckgesetzt.
- 2026-05-30: **Asset-Edit-Dialog Redesign (P0):** Auf User-Wunsch Optik komplett dem Detail-Modal angeglichen — Fuchsia-Gradient-Header, Karte 224px oben mit **ziehbarem Marker** (Leaflet `draggable`), Drag-Hint-Bubble, beim Drag aktualisieren Lat/Lng-Inputs (`onMarkerDragEnd` schreibt Number-Werte mit 7 Nachkommastellen). Bei manueller Lat/Lng-Eingabe oder „Meine GPS-Position" pant die Karte automatisch zum neuen Punkt (`PanTo` mit recenter-key). Plus Code Live-Vorschau unter den Inputs. Read-only Cards „Gestellt von" + „Status" am Ende — analog Detail-Modal. E2E verifiziert: Drag 60px rechts/20px runter → Lat-Wert um ~0.0003 verschoben, Lng um ~0.0006.
- 2026-05-30: **Kommentare im AssetEditDialog (P1):** Kommentare-Block direkt in den Edit-Dialog integriert (unter den Read-only-Cards), nutzt vorhandene Endpoints `POST/DELETE /api/orders/epirent/{pk}/assets/{id}/comments[/{cid}]`. Liste scrollbar (max-h-40, optimistic UI), Textarea mit Strg+Enter-Shortcut, Counter-Pill am Header. Auf Close (egal ob via Save oder Cancel) wird `fetchAssets()` getriggert, damit die Asset-Row-Counter aktuell bleiben. E2E verifiziert: Add Kommentar → erscheint mit Autor+Timestamp; Delete → optimistic verschwunden, Backend bestaetigt.
- 2026-05-30: **Feature: „+ Messprotokoll"-Button beim Verteiler-Anlegen (P0):** Trupp A kann jetzt einen Verteiler in einem Rutsch setzen + pruefen. In `OrderDetailPage.js` neuer Button neben „Hinzufuegen" (nur sichtbar wenn `assetType === "Verteiler"`, ClipboardCheck-Icon, lila Outline). Klick → `addAsset()` legt den Verteiler an und gibt das `created`-Objekt zurueck → State `prefillVerteiler` wird gesetzt → `MessprotokollDialog` oeffnet sofort. Dialog akzeptiert neue Prop `prefillVerteiler={id,label,plus_code,latitude,longitude}` → initialer Form-State enthaelt direkt `verteiler_nr` + `verteiler_asset_id` + `verteiler_plus_code` + `verteiler_lat/lng`, sodass beim Speichern die Verknuepfung Verteiler↔Messprotokoll automatisch persistiert wird (gleicher Pfad wie manuelles Verknuepfen via „Auf Karte"). E2E verifiziert: Verteiler VTEST angelegt → Dialog oeffnet mit „VTEST" vorbefuellt + gruenem „Verknuepft mit Asset · Plus Code"-Hinweis.
- 2026-05-30: **Edit-Funktion im VerteilerPickerDialog (P1):** Popup beim Verteiler-Klick jetzt mit zwei Aktionen: „Auswaehlen" (lila, verknuepft) + „Bearbeiten" (grau, Pencil-Icon). Bearbeiten oeffnet den gleichen `AssetEditDialog` (Karte mit Drag-Pin, Felder, Kommentare). Nach Schliessen/Speichern werden die Verteiler-Marker in der Picker-Karte via `reloadAssets()` aktualisiert (neuer Label/neue Position direkt sichtbar). VerteilerPickerDialog importiert `AssetEditDialog` + lokale `ASSET_TYPES_LOCAL` + `encodePlusCodeLocal` direkt — keine Prop-Durchschleifung durch MessprotokollDialog noetig.
- 2026-05-30: **Bugfix: Asset-Suche Token-AND (P1):** Suche im Artikel-Positionierung-Tab funktionierte nur als zusammenhaengende Substring-Suche. Beispiel: "UVB Tizian" lieferte 0 Treffer obwohl `label="UVB-ME-63"` + `created_by="Tizian Stern"` matchten. Fix in `OrderDetailPage.js#filteredAssets`: Query in Whitespace-Tokens splitten, ALLE Tokens muessen irgendwo im Haystack (asset_type, label, plus_code, created_by, lat/lng, comments) vorkommen (`tokens.every(t => haystack.includes(t))`). Unit-Test mit 6 Kombi-Queries: vorher 0/0/0/0/0/0, nachher 1/1/1/2/1/1.
- 2026-05-30: **Feature: Tankstatus-Modul (P0) — Phase A+B):**
  **Backend (`/app/backend/routes/tank_status.py`):**
  - Neue Collection `tank_readings` + `tank_reading_photos`
  - `POST /api/orders/epirent/{pk}/tank-readings` (Pflicht: tank_size_l beim ersten Reading je Asset, danach automatisch uebernommen; nur fuer Stromerzeuger)
  - `GET /api/orders/epirent/{pk}/tank-readings` mit Filter (asset_id, min/max_fuel_l)
  - `GET /api/orders/epirent/{pk}/tank-readings/forecast` — pro Asset: latest Reading + ueber konsekutive Paare berechneter Ø-Verbrauch L/h (Refills uebersprungen; bevorzugt `runtime_h`-Delta, sonst Wall-Clock), `hours_remaining`, `eta_empty` (ISO), Kritikalitaet (critical < 20% / < 12h, warn < 40% / < 24h, sonst ok). Sortiert nach Kritikalitaet.
  - `GET /export.csv` — UTF-8-BOM, Semikolon-getrennt (Excel-kompatibel)
  - `DELETE /{reading_id}` (loescht auch Photos)
  - `POST/GET /{reading_id}/photo` — Foto-Upload (max 4 MB) in `tank_reading_photos` als Base64
  **Frontend `TankStatusPage.jsx`:** Route `/orders/:pk/tankstatus`, 3 Tabs (Erfassen/Prognose/Historie), GPS-Naehe-Sortierung der Generatoren, Foto-Upload via Smartphone-Kamera (`capture="environment"`), Tank-Balken farbcodiert, Filter (Min/Max L, „Nur kritisch"), Sortierung (Kritikalitaet/Restzeit/Tankstand/Name), CSV-Download.
  **Frontend `OrderDetailPage.js`:** Neues Tile „Tankstatus" (amber Fuel-Icon) im Auftrags-Module-Grid, navigiert auf die neue Route.
  **Einsatzzentrale-Kiosk (`einsatzzentrale-kiosk.html`):** Neues Tile „⛽ Tankstatus" im Workspace, `renderTankPanel()` mit Read+Write (Liste sortierbar nach Kritikalitaet/Restzeit/Tankstand/Name, „Nur kritisch"-Toggle, „Erfassen"-Button pro Generator oeffnet ein In-Page-Modal). Auto-Refresh alle 30s. Syntax validiert (alle 5 Script-Bloecke parsen sauber).
  **Forecast-Beispiel:** Tag 1: 850 L, 120,5 h. Tag 2: 670 L, 130,5 h. Tag 3: 490 L, 140,5 h. → avg 18 L/h, hours_remaining 27.2, eta_empty +1 Tag.
- 2026-05-30: **Tankstatus-Umbau: Inbetriebnahme + Normales Reading (P0):**
  Workflow nun zweistufig:
  1. **Inbetriebnahme** (einmalig pro Generator): Pflicht: tank_size_l, fuel_level_l, runtime_h, kwh_total. Zeitstempel automatisch. Backend verweigert weitere Commissioning-Eintraege fuer dasselbe Asset.
  2. **Normales Reading** (ab da): Pflicht: kwh_total + load_kw + (fuel_level_l ODER fuel_percent). Das fehlende Mass wird aus Tankgroesse automatisch berechnet (z.B. 65 % von 1150 L → 747.5 L). Backend verweigert normale Readings bis Inbetriebnahme existiert.
  CSV-Export erweitert um `reading_type` + `kwh_total`. Frontend `TankStatusPage.jsx` zeigt automatisch das richtige Formular: bei Auswahl eines Generators ohne Commissioning erscheint roter Warn-Header + Inbetriebnahme-Felder; nach Commissioning gruenes Banner + Normal-Felder mit Liter-ODER-Prozent-Doppelfeld. Einsatzzentrale-Kiosk-Modal spiegelt dieselbe Logik. E2E verifiziert: Inbetriebnahme 1150L/1100L/8800h/12000kWh → Normal-Reading 65 %/45kW/12450kWh → Backend rechnet 747.5 L aus.
- 2026-05-30: **Tankstatus-Kiosk: Suchfeld (P1):** Backend-Forecast um `plus_code`, `latitude`, `longitude`, `comments` (Liste aller Reading-Kommentare des Assets) erweitert. Kiosk-Tank-Panel hat jetzt eine Suchleiste mit **Token-basierter AND-Suche** ueber Bezeichnung + Plus Code + Lat/Lng + alle Kommentare. Beispiel: „UVB Refill" findet einen Generator mit Label „UVB-GEN-1" und einem Kommentar „Refill 12 Uhr". Plus Code wird zusaetzlich als kleines lila Pill im Card-Header angezeigt. Auch „pristine" Generatoren (noch kein Reading) werden durchsucht und gefiltert.
- 2026-05-30: **LTE-Failover DNS-Fix Einsatzzentrale-Pi (P1) — ERLEDIGT** (User-bestaetigt). Damit ist die ip-up.d/`usepeerdns`-Anpassung auf den Tank-Pis live.
