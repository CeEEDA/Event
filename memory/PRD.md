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
