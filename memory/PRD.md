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
### Feb 2026 – Current Session (continued)
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
