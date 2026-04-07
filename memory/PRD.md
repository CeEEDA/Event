# Kirmes Billing & Management System - PRD

## Original Problem Statement
Comprehensive "Kirmes" (Fairground) billing and management system with internal HR/Employee Management module. Built with React, FastAPI, MongoDB. Includes native Desktop Applications (Electron) for Mac and Windows.

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
  ├── HubPage.js                # Employee Hub (desktop=1: tiles open new OS windows)
  ├── EinsatzplanungPage.jsx    # Admin Shift Planning (Crewbrain integrated)
/app/desktop/
  ├── main.js           # Electron main (server detection, multi-window)
  ├── preload.js        # IPC bridge (openModule, URL monitoring)
  ├── config.json       # Server URLs (local/remote)
  ├── package.json      # Electron builder (Mac DMG + Win NSIS)
  ├── install-mac.sh    # One-file Mac installer (all code + icon embedded)
  ├── install-win.ps1   # One-file Windows installer (all code + icons embedded)
  ├── install-win.bat   # Windows double-click wrapper
  ├── assets/icon.png   # Mac icon (512x512)
  ├── assets/icon.ico   # Windows icon (16-256px, 6 sizes)
```

## Completed Features (Latest First)

### 2026-04-07: Windows Desktop App (Electron)
- Windows NSIS installer via electron-builder
- icon.ico with 6 sizes (16x16 to 256x256)
- install-win.ps1: Self-contained PowerShell installer (embeds all code + icons)
- install-win.bat: Double-click wrapper for non-technical users
- Auto-installs Node.js via winget or direct MSI download
- Tested: Syntax validated, all files verified

### 2026-04-07: Mac Desktop App (Electron) v2.0
- Server detection: Auto-checks local 172.20.200.117 (Nginx/Caddy), fallback to eventenergie.app
- Login window → Hub window (full: clock, tiles, tasks) → Module windows (per tile click)
- install-mac.sh: Self-contained bash installer (embeds all code + icon)
- Self-signed cert support for local server
- Frontend HubPage.js: handleModuleClick() for Electron IPC
- Tested: 100% Frontend (7/7)

### 2026-04-07: Kirmeskiste OTA Auto-Update System
- Backend: `/api/system/ota/check`, `/download`, `/upload`, `/versions`, `/devices`
- Pi-Script: Auto-update every ~20min

### Previously Completed
- Full Time Tracking, Auto-Overtime, Payroll system
- DATEV Lohnabrechnung PDF AI parsing (Gemini)
- Einsatzplanung v2 (weekly grid, job cards, EpiRent Crewbrain)
- KI-Training page, Team Chat, Task Management, PWA

## 3rd Party Integrations
- Gemini 2.5 Flash via Emergent LLM Key
- DATEV (via SMTP Email)
- EpiRent API (ERP system)

## Backlog

### P1 - Upcoming
- Microsoft 365 Postfach-Anbindung
- PayPal/Kreditkarten Integration

### P2 - Future
- Lastdiagramm Live-Test
- Chromium Translate popup suppress (Pi Kiosk)
- Admin File Size Limits
- GPS Support for Kirmeskiste
- DSE890 Gateway GSM
- Refactor AdminPage.js
