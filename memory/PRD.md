# Kirmes Billing & Management System - PRD

## Original Problem Statement
Comprehensive "Kirmes" (Fairground) billing and management system with internal HR/Employee Management module. Built with React, FastAPI, MongoDB. Includes native Desktop Applications (Electron) for Mac/Windows, and Mobile Apps (Capacitor) for Android/iOS.

## Core Architecture
```
/app/backend/routes/
  ├── software_downloads.py    # Desktop + Mobile + Server installer downloads
/app/frontend/
  ├── capacitor.config.json    # Capacitor config (Android/iOS)
  ├── android/                 # Native Android project (Capacitor)
  ├── ios/                     # Native iOS project (Capacitor)
/app/desktop/
  ├── main.js, preload.js      # Electron desktop app
  ├── install-mac.sh           # Mac desktop installer
  ├── install-win.bat/ps1      # Windows desktop installer
  ├── server-setup-win.ps1     # Windows Server 2019 setup
  ├── db-migrate-win.ps1       # Database migration
  ├── deploy-win.ps1           # Code deployment
  ├── build-mobile.ps1/.sh     # Android/iOS build scripts
```

## Completed Features (Latest First)

### 2026-04-07: Mobile Apps (Capacitor - Android + iOS)
- Capacitor 6 integration with existing React frontend
- Android project with custom app icons (5 density buckets) + splash screen
- iOS project with full icon set (15 sizes) + AppIcon.appiconset
- Build scripts: build-mobile.ps1 (Windows) + build-mobile.sh (Mac)
- Downloads available in Portal Settings → Software Downloads

### 2026-04-07: Windows Server 2019 Setup Scripts
- server-setup-win.ps1: Chocolatey, Node.js 20, Python 3.11, MongoDB 7, Caddy, NSSM, Mosquitto, Firewall
- db-migrate-win.ps1: Export/Import/Verify with DB rename
- deploy-win.ps1: Git clone, pip install, yarn build, service restart

### 2026-04-07: Mac + Windows Desktop App (Electron) v2.0
- Server detection (local 172.20.200.117 → fallback eventenergie.app)
- Login → Hub → Multi-window architecture
- Self-contained installers with embedded code + icons

### 2026-04-07: Software Downloads Portal
- Admin Settings → Software Downloads section
- 3 categories: Desktop Apps, Mobile Apps, Server-Administration
- All files downloadable from the portal

## 3rd Party Integrations
- Gemini 2.5 Flash via Emergent LLM Key
- DATEV (via SMTP Email)
- EpiRent API (ERP system)
- Capacitor 6 (Android + iOS native wrapper)

## Backlog
### P1
- Microsoft 365 Postfach-Anbindung
- PayPal/Kreditkarten Integration
### P2
- Lastdiagramm Live-Test, Chromium Translate, Admin Dateigrößen, GPS, DSE890, AdminPage Refactoring
