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
  ├── HubPage.js                # Employee Hub (desktop=1 mode: tiles open new OS windows)
  ├── EinsatzplanungPage.jsx    # Admin Shift Planning (Crewbrain integrated)
  ├── AbrechnungPage.jsx        # Employee Payroll
  ├── AdminZeitDetailPage.jsx   # Admin Employee Details
/app/desktop/
  ├── main.js           # Electron main (server detection, login→hub→module windows)
  ├── preload.js        # IPC bridge (openModule, getServerInfo, URL monitoring)
  ├── config.json       # Server URLs (local 172.20.200.117 / remote eventenergie.app)
  ├── package.json      # Electron builder config (Mac DMG + Win NSIS)
```

## Completed Features (Latest First)

### 2026-04-07: Mac Desktop App (Electron) v2.0
- Server-Erkennung: Auto-checks local 172.20.200.117 (Nginx/Caddy), fallback to eventenergie.app
- Login-Fenster: Dedicated login window on startup
- Hub-Fenster: Full hub with tiles, tasks, time clock. Tile clicks open new OS windows
- Multi-Window: Each module tile opens an independent OS window via IPC
- Logout handling: Closes all module windows, returns to login
- Self-signed cert support for local server
- Frontend HubPage.js: handleModuleClick() delegates to Electron IPC or browser navigate
- Tested: 100% Frontend (7/7)

### 2026-04-07: Kirmeskiste OTA Auto-Update System
- Backend: `/api/system/ota/check`, `/download`, `/upload`, `/versions`, `/devices`
- Pi-Script: Auto-update check on startup + every ~20min in sync loop

### 2026-04-07: PWA Configuration for Mobile
- manifest.json, service worker, apple-mobile-web-app meta tags

### 2026-04-07: Deep Crew Fetch from EpiRent Personal Chapters
- Backend searches inside "Personal" chapters (type-5 items) via `_ref_chapter_items`

### Previously Completed
- Full Time Tracking, Auto-Overtime, Payroll system
- DATEV Lohnabrechnung PDF AI parsing (Gemini)
- "Einsatzplanung" v2 (weekly grid, job cards, shift assignments)
- KI-Training page for AI prompt tuning
- Team Chat, Task Management

## Key DB Collections
- `shift_assignments`, `shift_job_reqs`, `shift_releases`, `crew_cache`
- `payroll_releases`, `devices`, `ai_settings`

## 3rd Party Integrations
- Gemini 2.5 Flash via Emergent LLM Key
- DATEV (via SMTP Email)
- EpiRent API (ERP system)

## Backlog

### P1 - Upcoming
- Windows Desktop App (Electron Builder for Win)
- Microsoft 365 Postfach-Anbindung
- PayPal/Kreditkarten Integration

### P2 - Future
- Lastdiagramm Live-Test
- Chromium Translate popup suppress (Pi Kiosk)
- Admin File Size Limits
- GPS Support for Kirmeskiste
- DSE890 Gateway GSM
- Refactor AdminPage.js
