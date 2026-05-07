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
### Feb 2026 – Current Session (continued)
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

### P1
- LTE Failover DNS Fix auf Pi: `usepeerdns` in `/etc/ppp/peers/m2m` + `/etc/ppp/ip-up.d/0000-lte-dns` Hook (Telekom-DNS in `/etc/resolv.conf` wenn LAN ausfällt).

### P2
- Portal-Auftragsliste "Lager"-Filter / Reiter (interne Testläufe von normalen Aufträgen trennen).
- Suchleiste über Pi-Auftragsliste (Kiosk-UI).
- GPS-Support für Legacy-Kirmeskiste (4-meter Variante).
- Lastdiagramm Live-Test.
- Chromium "Translate"-Popup auf Raspberry Pi Kiosk global unterdrücken.

### Verworfen / nicht benötigt
- ~~Übersichtskachel auf der Startseite für 8Z-Pis (X von 12 Pis online, Y mit schwachem Signal, Z ohne GPS-Fix)~~ — vom User als nicht benötigt gestrichen (Mai 2026).
