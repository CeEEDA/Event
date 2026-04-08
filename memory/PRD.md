# Eventenergie Portal - PRD

## Original Problem Statement
Comprehensive "Kirmes" (Fairground) billing and HR management system with:
- Desktop Apps (Mac/Windows) via Electron
- Mobile Apps (Android/iOS) via Capacitor
- Server Infrastructure on Windows Server 2019
- Time tracking, Payroll (DATEV), Employee Hub, Orders, Shift planning

## Architecture
- **Frontend**: React (CRA + craco)
- **Backend**: FastAPI + MongoDB (motor)
- **Desktop**: Electron wrapper with local/remote IP fallback
- **Mobile**: Capacitor 6 native builds
- **Server**: Windows Server 2019, Caddy (HTTP:8001), nginx (HTTPS:443), MongoDB, Mosquitto MQTT

## What's Been Implemented
- [x] Full-stack app: Time tracking, Payroll, Employee Hub, Orders, Shift planning
- [x] Mac + Windows Desktop App (Electron)
- [x] Android + iOS Mobile Apps (Capacitor 6)
- [x] Software Downloads Portal in Admin
- [x] Windows Server 2019 deployment scripts (setup, migrate, deploy)
- [x] **update.bat** - GitHub pull, build & restart (goto-based, locale-independent)
- [x] **start-all.bat** - Service management (goto-based, auto Caddy download)
- [x] **stop-all.bat** - Clean service shutdown (locale-independent port killing)
- [x] **requirements-server.txt** - Optimized for Windows Server (no dev tools)
- [x] NSSM service disabled, start-all.bat is sole service manager
- [x] SSL/HTTPS via nginx with existing certificate
- [x] Mosquitto MQTT broker integration
- [x] All 4 services running: Backend(8002), Caddy(8001), nginx(443), Mosquitto(1883)

## Server Deployment Status (2026-04-08)
- Windows Server 2019: FULLY OPERATIONAL
- All services: Backend ✅, Caddy ✅, nginx ✅, Mosquitto ✅
- SSL Certificate: Copied from old server to C:\eventenergie\ssl\
- NSSM EventenergieBackend service: DISABLED (start-all.bat manages services)
- Node 20 LTS + yarn for frontend builds
- Python 3.11 venv at C:\eventenergie\venv

## Upcoming Tasks (P1)
- [ ] Microsoft 365 Postfach-Anbindung (email inbox document ingestion)
- [ ] PayPal/Kreditkarten Integration (payment processing)

## Future Tasks (P2)
- [ ] Lastdiagramm Live-Test (requires EMU meters)
- [ ] Chromium "Translate" Popup suppression on Raspberry Pi Kiosk
- [ ] Admin File Size Limits for uploads
- [ ] GPS Support for Kirmeskiste
- [ ] DSE890 Gateway GSM Connection
- [ ] AdminSettingsPage.js Refactoring (~1800+ lines)
- [ ] MQTT port alignment (backend connects 1884, Mosquitto on 1883)

## Key Files
- `/app/update.bat` - GitHub update script
- `/app/start-all.bat` - Service start script
- `/app/stop-all.bat` - Service stop script
- `/app/nginx.conf` - HTTPS reverse proxy config
- `/app/Caddyfile` - HTTP reverse proxy config
- `/app/backend/requirements-server.txt` - Server-optimized Python packages

## 3rd Party Integrations
- Gemini (via Emergent LLM Key)
- DATEV (Email parsing)
- EpiRent API (ERP)

## Test Credentials
- Admin: christian.ecker@eventenergie-deutschland.de / qivbeb-Wodha1-sewram
- Admin Preview: admin@test.com / password
- Employee: test1@test.de / Test1234!
- Employee: test-noperm@test.com / password
