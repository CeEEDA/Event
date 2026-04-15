# Eventenergie Portal - PRD

## Original Problem Statement
Comprehensive "Kirmes" (Fairground) billing and HR management system with:
- Desktop Apps (Mac/Windows) via Electron
- Mobile Apps (Android/iOS) via Capacitor
- Server Infrastructure on Windows Server 2019
- DSE 890 Gateway MQTT Integration for remote generator monitoring and control

## Architecture
- **Frontend**: React (CRA + craco)
- **Backend**: FastAPI + MongoDB (motor)
- **MQTT**: Mosquitto broker on Windows Server
- **DSE Gateways**: DSE 890 MK1 with L401 and 8610 controllers

## What's Been Implemented (2026-04-13)

### DSE 890 Gateway – COMPLETE
- [x] Sentinel value filtering (valid() function + _sanitize_telemetry)
- [x] Control buttons working: Stop/Auto/Start via MQTT Function 3, {"K": key} payload
- [x] 4-segment topic format (group/type/uid/subtopic)
- [x] Auto module UID + topic prefix detection from MQTT messages
- [x] GPS from gateway applied to all connected devices
- [x] Alarm integration (Function 4, DSE alarm codes with German descriptions)
- [x] L401 single-phase view (no L2/L3, no Öldruck, no cos φ)
- [x] 8610 full 3-phase view (all registers)
- [x] Betriebsstunden via Page 7 Register 0 (hours topic, 20 min interval)
- [x] Button blink animation after command (green pulse for 2 min)
- [x] Mode feedback stored on device after command
- [x] Mosquitto password auto-management (merge, not overwrite + auto-restart)
- [x] Mosquitto passwd file path fixed to C:\Program Files\Mosquitto\passwd

### Topic Files
- [x] Universal: Alle DSE Controller (L401, 8610, 8610 MKII, 7310, 5510) nutzen dieselbe GenComm Topic-Datei (`dse_universal_module_topics.csv`)
- [x] Enthält: Oil pressure, Coolant temp, Oil temp, Fuel level, Battery voltage, Engine speed, L1-L3 Voltage/Current/Watts, Total watts, Frequency, Fault code, Status bits, Run hours (P7 R6 seconds), Number of starts (P7 R16), Alarm, Control
- [x] Gateway: status, GPS, topic_file subscribe
- [x] Backend: Alle Download-Endpoints liefern die universelle Datei (kein hardcoded content mehr)

### Performance Optimizations
- [x] MQTT deduplication (overlapping subscriptions)
- [x] DB lookup caching (30s TTL)
- [x] Telemetry insert throttling (Lichtmast 60s, Stromerzeuger 5min running / skip standby)
- [x] Status update throttling (20 min)
- [x] Module UID store throttling (5 min)
- [x] Snapshot-based telemetry (no N×10 queries on read)
- [x] EventLog polling removed
- [x] Frontend refresh: 20 min normal, 2 min after command
- [x] Build optimization: GENERATE_SOURCEMAP=false, 8GB NODE_OPTIONS
- [x] Caddy no-cache headers for /api/download-*

### UI Changes
- [x] Generator list: sorted (alarm > running > online > offline)
- [x] GPS pin in list (opens Google Maps)
- [x] Zählerstände hidden when empty
- [x] DSE 890 MQTT info box with all settings
- [x] Einsatzplanung timezone fix (getWeekDates)

### Server/Deployment
- [x] update.bat always rebuilds frontend
- [x] Mosquitto auto-restart after password change
- [x] Mosquitto passwd file path corrected
- [x] Caddy config: no-cache for downloads

## Upcoming Tasks (P1)
- [ ] Microsoft 365 Postfach-Anbindung
- [ ] PayPal/Kreditkarten Integration
- [ ] Caddy Cache-Problem für Portal-Downloads endgültig lösen
- [ ] Dymo Label Drucker: pywin32 auf Windows Server installieren

## Future Tasks (P2)
- [ ] Lastdiagramm Live-Test (requires EMU meters)
- [ ] Chromium "Translate" Popup suppression on Raspberry Pi Kiosk
- [ ] Admin File Size Limits for uploads
- [ ] GPS Support for Kirmeskiste
- [ ] AdminSettingsPage.js Refactoring

## Test Credentials
- Admin: christian.ecker@eventenergie-deutschland.de / qivbeb-Wodha1-sewram
- Admin Preview: admin@test.com / password
