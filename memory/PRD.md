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
- All services: Backend, Caddy, nginx, Mosquitto
- SSL Certificate: Copied from old server to C:\eventenergie\ssl\
- NSSM EventenergieBackend service: DISABLED (start-all.bat manages services)
- Node 20 LTS + yarn for frontend builds
- Python 3.11 venv at C:\eventenergie\venv

## Recent Changes (2026-04-13) - DSE 890 Gateway Fix
- [x] **DSE Sentinel Value Filtering**: Enhanced `_parse_gencomm_registers()` with robust `valid()` function that catches exact DSE sentinel values (0x7FFFFFFC, 0x7FFC, etc.) via abs-comparison AND range-based filter (>1M = invalid)
- [x] **Backend Telemetry Sanitization**: New `_sanitize_telemetry()` in generators.py filters historical data exceeding field-specific thresholds (voltage>2000V, current>50kA, etc.)
- [x] **Frontend Sentinel Safety Net**: `sanitizeValue()` function in GeneratorDetailPage.js filters values >10M and field-specific limits, MetricBox shows "–" for invalid values
- [x] **Control Button Routing Fix**: Backend `send_generator_command()` now ALWAYS looks up device for `dev-` generators (was only looking up when generator doc missing). This enables DSE 890 MQTT control for device-based generators
- [x] **Auto Module UID Detection**: When MQTT data arrives, the module UID AND full topic prefix (group/type/uid) are automatically extracted and stored. This enables control for ALL generators without manual configuration
- [x] **Generator Direct Control**: Control path checks `gen.last_mqtt_topic_prefix` first for correct 4-segment topic format (`group/type/uid/control`), then falls back to legacy mapping
- [x] **Fixed Control Topic Format**: Changed from `eventenergie/{UID}/control` (3 segments) to `eventenergie/{TYPE}/{UID}/control` (4 segments) matching DSE 890 Gateway subscribe format
- [x] **L401 Module Topics Updated**: Control subscribe changed from P3/R0-restricted to generic (accepts any register write via key/complement)
- [x] **Frontend Command Routing**: `sendCommand()` always routes through `/api/mqtt/control/{id}` – backend decides between MQTT (DSE 890) and Pi-Queue (DSE 5510)
- [x] **DSE Mode Parsing**: `_parse_gencomm_registers()` now reads Page 7 (hours_run, energy_kwh, engine_starts), Page 6 (power_factor), Page 16 (dse_mode)
- [x] **Haptic Button Feedback**: Buttons derive mode from `dse_mode` OR `generator.last_dse_mode` fallback
- [x] **MQTT Telemetry Enhancement**: Both `_ingest_telemetry` and `_ingest_telemetry_device` now update `last_dse_mode` on generator document
- [x] **HTTP 503 for MQTT errors**: Control commands return 503 (Service Unavailable) when MQTT not connected

## Recent Changes (2026-04-12)
- [x] GiroCode Fallback: IBAN/BIC hardcoded als Default (funktioniert auch ohne .env)
- [x] Dokumentenablage: Cloud-Storage Fallback auf lokalen Speicher (put_object optional)
- [x] Download: Liest erst Cloud, dann lokales Dateisystem
- [x] Flieger-Button: Speichert jetzt auch in Dokumentenablage/Rechnungsausgang/YYYY/Monat
- [x] DSE 5510 Setup-Skript: LTE-Erweiterung (SIM7600E-H via UART)

## Recent Changes (2026-04-10)
- [x] DB-Backup in start-all.bat laeuft nun asynchron im Hintergrund (start /min)
- [x] Backend-Startup-Timeout von 20s auf 40s erhoeht
- [x] Backup-Log wird geschrieben nach %LOG_DIR%\backup.log

## Upcoming Tasks (P1)
- [ ] Microsoft 365 Postfach-Anbindung (email inbox document ingestion)
- [ ] PayPal/Kreditkarten Integration (payment processing)

## Future Tasks (P2)
- [ ] Lastdiagramm Live-Test (requires EMU meters)
- [ ] Chromium "Translate" Popup suppression on Raspberry Pi Kiosk
- [ ] Admin File Size Limits for uploads
- [ ] GPS Support for Kirmeskiste
- [ ] AdminSettingsPage.js Refactoring (~1800+ lines)

## Key Files
- `/app/backend/mqtt_service.py` - MQTT broker connections, Gencomm register parsing
- `/app/backend/routes/generators.py` - Generator API, telemetry sanitization
- `/app/backend/routes/mqtt_config.py` - MQTT control commands (DSE 890 + DSE 5510)
- `/app/frontend/src/pages/GeneratorDetailPage.js` - Generator detail UI, controls, charts
- `/app/frontend/src/pages/DeviceManagementPage.js` - Device management, DSE gateway setup
- `/app/update.bat` - GitHub update script
- `/app/start-all.bat` - Service start script
- `/app/stop-all.bat` - Service stop script

## 3rd Party Integrations
- Gemini (via Emergent LLM Key)
- DATEV (Email parsing)
- EpiRent API (ERP)
- Mosquitto MQTT (DSE 890 Gateways)

## Test Credentials
- Admin: christian.ecker@eventenergie-deutschland.de / qivbeb-Wodha1-sewram
- Admin Preview: admin@test.com / password
- Employee: test1@test.de / Test1234!
- Employee: test-noperm@test.com / password
