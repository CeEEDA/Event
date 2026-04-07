# Kirmes Billing & Management System - PRD

## Original Problem Statement
Comprehensive "Kirmes" (Fairground) billing and management system with internal HR/Employee Management module. Built with React, FastAPI, MongoDB. Includes native Desktop Applications (Electron) for Mac and Windows with in-app installer downloads.

## User Personas
- **Admin**: Manages employees, shift planning, payroll, EpiRent orders, documents, software downloads
- **Employee**: Views assigned shifts, payroll, personal documents

## Core Architecture
```
/app/backend/routes/
  ├── employee.py              # HR Data, Shift Planning, Absences
  ├── orders.py                # EpiRent API sync, Crew data (Crewbrain)
  ├── documents.py             # AI Document Parsing (DATEV)
  ├── software_downloads.py    # Desktop App installer file serving
/app/backend/static/desktop-installers/
  ├── install-mac.sh           # Self-contained Mac installer
  ├── install-win.bat          # Windows double-click installer
  ├── install-win.ps1          # Windows PowerShell installer
/app/frontend/src/pages/
  ├── HubPage.js               # Employee Hub (desktop=1: tiles open new OS windows)
  ├── AdminSettingsPage.js     # Includes Software Downloads section
/app/desktop/
  ├── main.js                  # Electron main (server detection, multi-window)
  ├── preload.js               # IPC bridge
  ├── config.json              # Server URLs (local/remote)
  ├── package.json             # Electron builder (Mac DMG + Win NSIS)
  ├── install-mac.sh           # Source installer (also in static/)
  ├── install-win.bat          # Source installer (also in static/)
  ├── install-win.ps1          # Source installer (also in static/)
  ├── assets/icon.png          # Mac icon (512x512)
  ├── assets/icon.ico          # Windows icon (6 sizes)
```

## Completed Features (Latest First)

### 2026-04-07: Software Downloads in Admin Settings
- New backend route: GET /api/system/downloads/{mac,win-bat,win-ps1}
- GET /api/system/downloads/info returns file list with sizes and availability
- SoftwareDownloadsSection component in AdminSettingsPage
- Download buttons for Mac and Windows installers with usage instructions
- Tested: API 200 OK, Frontend section visible

### 2026-04-07: Mac + Windows Desktop App (Electron) v2.0
- Server detection: Auto-checks local 172.20.200.117, fallback to eventenergie.app
- Login window → Hub window (full: clock, tiles, tasks) → Module windows
- install-mac.sh: Self-contained bash installer (embeds all code + icon)
- install-win.ps1 + .bat: Self-contained Windows installer
- icon.ico with 6 sizes (16px-256px)
- Frontend HubPage.js: handleModuleClick() for Electron IPC

### Previously Completed
- Kirmeskiste OTA Auto-Update System
- PWA Configuration for Mobile
- Deep Crew Fetch from EpiRent Personal Chapters
- Full Time Tracking, Auto-Overtime, Payroll
- DATEV Lohnabrechnung PDF AI parsing (Gemini)
- Einsatzplanung v2 (weekly grid, job cards, EpiRent Crewbrain)
- KI-Training page, Team Chat, Task Management

## Key API Endpoints
- GET /api/system/downloads/info - List available installers
- GET /api/system/downloads/mac - Download Mac installer
- GET /api/system/downloads/win-bat - Download Windows .bat installer
- GET /api/system/downloads/win-ps1 - Download Windows .ps1 installer

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
