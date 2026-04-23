# Kirmes Billing & HR System — PRD

## Original Problem Statement
Comprehensive "Kirmes" (Fairground) billing and HR management system. Core focus on hardware integration for fuel receipts (Tankwagen) via a Raspberry Pi emulating an EPSON TM-U295 printer to intercept serial data from a Sening MultiFlow system.

## Core Requirements
- Desktop Apps (Mac/Windows), Mobile Apps (Capacitor), Windows Server 2019.
- Hardware: DSE Gateways, EPSON Printer emulation via Raspberry Pi.
- Finance/HR: Invoices, FinTS, AI document categorization, Time tracking.

## Product Language
German (UI + all user communication).

---

## Recently Completed
- **2026-02 — P0 Fix: Pi Sync 404.** `tankbeleg_pi.py` now uses a `_api_base()` helper that appends `/api` exactly once, so both `api_url=https://eventenergie.app` and `api_url=https://eventenergie.app/api` work. Verified via curl against `/api/fuel-receipts/sync` (HTTP 200).
- Heuristic Sening receipt parser + ESC/POS bitmap → PNG rendering on Pi.
- Null-Modem serial handshake (`dsrdtr=False`), Sening Poll reply `0x00`.
- Frontend fuel management displays PNG receipts.
- "Angemeldet als" multi-company display in Schausteller login.

## In Progress
- User verification of Pi sync fix (requires `git pull` + script re-download on Pi).

## Backlog (prioritized)
### P1
- "Lager" quick-action button on Pi Touchscreen UI + backend `lager_entry` key fix (`pk` → `primary_key`).

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

## 3rd Party Integrations
- OpenAI GPT-4o via Emergent LLM Key (AI document categorization).
- Stripe (user-provided keys).
- FinTS banking (user credentials + product ID).

## Hardware Deployment Loop
Every change to `tankbeleg_pi.py` or `tankbeleg_ui.py`:
1. Agent pushes to repo.
2. User `git pull` on Windows Server + restarts backend.
3. On Pi: `sudo curl -sL -o /opt/tankbeleg/tankbeleg_pi.py "https://eventenergie.app/api/download/tankbeleg-pi-script?v=$(date +%s)" && sudo systemctl restart tankbeleg_pi`.
