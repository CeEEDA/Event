# Kirmes Billing & Management System - PRD

## Original Problem Statement
Comprehensive "Kirmes" (Fairground) billing and management system with internal HR/Employee Management module. Built with React, FastAPI, MongoDB. Now includes a native Desktop Application (Electron) for Mac/Windows.

## User Personas
- **Admin**: Manages employees, shift planning, payroll, EpiRent orders, documents
- **Employee**: Views assigned shifts, payroll, personal documents

## Core Architecture
```
/app/backend/routes/
  ├── employee.py       # HR Data, Shift Planning, Absences
  ├── orders.py         # EpiRent API sync, Crew data (Crewbrain), Documents
  ├── documents.py      # AI Document Parsing (DATEV Lohnabrechnung)
/app/frontend/src/pages/
  ├── HubPage.js                # Employee Hub (supports ?desktop=1 mode)
  ├── EinsatzplanungPage.jsx    # Admin Shift Planning (Crewbrain integrated)
  ├── AbrechnungPage.jsx        # Employee Payroll
  ├── AdminZeitDetailPage.jsx   # Admin Employee Details
/app/desktop/
  ├── main.js           # Electron main process (server detection, multi-window)
  ├── preload.js        # IPC bridge (openModule, getServerInfo)
  ├── config.json       # Server URLs (local/remote)
  ├── package.json      # Electron builder config (Mac DMG + Win NSIS)
```

## Completed Features (Latest First)

### 2026-04-07: Mac Desktop App (Electron) v2.0
- Server-Erkennung: Auto-checks local 172.20.200.117 (Nginx HTTPS/Caddy), fallback to eventenergie.app
- Login-Fenster: Dedicated login window on startup
- Hub-Fenster: Slim window with only module tiles (?desktop=1 mode)
- Multi-Window: Each tile opens an independent OS window for that module
- Logout handling: Closes all module windows, returns to login
- Self-signed cert support for local server
- IPC bridge for frontend-Electron communication
- Frontend HubPage.js adapted with isDesktopMode + handleModuleClick
- Tested: 100% Frontend (7/7)

### 2026-04-07: Kirmeskiste OTA Auto-Update System
- Backend: `/api/system/ota/check`, `/download`, `/upload`, `/versions`, `/devices`
- Pi-Script: Auto-update check on startup + every ~20min in sync loop
- Hash verification, backup before update, systemd restart
- Admin can upload new versions, see device check-in status

### 2026-04-07: PWA Configuration for Mobile
- manifest.json, service worker, apple-mobile-web-app meta tags
- App installable on iPhone, iPad, Samsung via "Add to Homescreen"

### 2026-04-07: Deep Crew Fetch from EpiRent Personal Chapters
- Backend searches inside "Personal" chapters (type-5 items) via `_ref_chapter_items`
- Crew data (type-3 sub-items: Elektrotechniker, Helfer etc.) with dates and times

### 2026-04-07: Improved Job Cards with Personnel Tracking
- Progress counter with visual progress bar, green checkmark when filled

### Previously Completed
- Full Time Tracking, Auto-Overtime, Payroll system
- Admin Avatar Upload, Employee Documents Management
- DATEV Lohnabrechnung PDF AI parsing (Gemini) with auto-assignment
- "Einsatzplanung" v2 (weekly grid, job cards, shift assignments)
- "Meine Einsätze" widget on Employee Hub
- Payroll "Speichern & Freigeben" (Release) functionality
- KI-Training page for AI prompt tuning

## Key DB Collections
- `shift_assignments`: `{id, user_id, order_pk, role, note, date, start_time, end_time}`
- `shift_job_reqs`: `{order_pk, count, roles}` (Manual requirements)
- `crew_cache`: `{order_pk, crew[], event, cached_at}` (30-min EpiRent cache)
- `payroll_releases`: `{user_id, month, net_amount, released_at}`
- `devices`: `{id, serial, type, version, needs_update, last_seen}`
- `ai_settings`: `{key, custom_instructions}`

## Key API Endpoints
- `GET /api/orders/epirent/{order_pk}/crew` - Single order crew data (cached)
- `POST /api/orders/epirent/crew/batch` - Batch crew data (concurrency-limited)
- `POST /api/employee/shift-plan` - Save shift assignment
- `GET /api/system/ota/download` - Device script update

## 3rd Party Integrations
- Gemini 2.5 Flash via Emergent Integrations `LlmChat` (Emergent LLM Key)
- DATEV (via SMTP Email)
- EpiRent API (ERP system - orders, crew/Crewbrain data)

## Backlog

### P1 - Upcoming
- Windows Desktop App (Electron Builder for Win - config already in package.json)
- Microsoft 365 Postfach-Anbindung (automatic document ingestion from email)
- PayPal/Kreditkarten Integration for Kirmes signups

### P2 - Future
- Lastdiagramm Live-Test (requires EMU meters)
- Suppress Chromium "Translate" popup on Raspberry Pi Kiosk
- Admin File Size Limits for uploads
- GPS Support for Kirmeskiste
- DSE890 Gateway GSM Connection
- Refactor AdminPage.js (>1900 lines)
