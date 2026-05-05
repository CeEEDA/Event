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
