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

## What's Been Implemented (2026-04-18)

### DSE 890 Gateway – COMPLETE
- [x] Sentinel value filtering (valid() function + _sanitize_telemetry)
- [x] Control buttons working: Stop/Auto/Start via MQTT Function 3, {"K": key} payload
- [x] 4-segment topic format (group/type/uid/subtopic)
- [x] Auto module UID + topic prefix detection from MQTT messages
- [x] GPS from gateway applied to all connected devices
- [x] Alarm integration: P3R6 Status Bits + GenComm Page 8 Named Alarm Conditions (52+ Alarme)
- [x] L401 single-phase view (no L2/L3, no Öldruck, no cos φ)
- [x] 8610 full 3-phase view (all registers)
- [x] Betriebsstunden via Page 7 Register 6 (hours topic, 20 min interval)
- [x] Button blink animation after command (green pulse for 2 min)
- [x] Mode feedback stored on device after command
- [x] Mosquitto password auto-management

### Alarm System (2026-04-18 overhaul)
- [x] GenComm Page 8 register reading via Function 1 (13 registers = 52 named alarms)
- [x] Correct alarm condition codes: only 2/3/4/5/10 = active alarm (was: >0)
- [x] Alarm name map aligned to official GenComm Page 8 documentation
- [x] Severity from condition code: 3/4=shutdown, 2/5/10=warning
- [x] Dual format support: A-code format (Function 4) + GenComm P008 register format
- [x] Updated universal topic file includes Page 8 R1-R13

### Topic Files
- [x] Universal: All DSE controllers use same GenComm Topic File
- [x] Contains: Engine params, generator params, status bits, hours, starts, Page 8 alarms, control
- [x] Register mapping based on official DSE GenComm documentation

### Performance Optimizations
- [x] MQTT deduplication, DB lookup caching (30s TTL)
- [x] Telemetry insert throttling (Lichtmast 60s, Stromerzeuger 5min)
- [x] Snapshot-based telemetry (no N×10 queries)

### Telemetry Parsing Fixes (2026-04-18)
- [x] Hours parsing: accepts 0 seconds (never-run devices), handles string values
- [x] Fuel level clamped to max 100% (was showing 107%)
- [x] Diagnostic logging for /hours topic (MQTT hours OK / MQTT hours FEHLEND)
- [x] Diagnostic endpoint: GET /api/generators/diagnose-hours

### Pi Setup Generator (2026-04-18 overhaul)
- [x] LTE setup completely rebuilt based on user-tested working script
- [x] Uses PPP with defaultroute+replacedefaultroute+ifmetric (was: nodefaultroute)
- [x] NetworkManager metrics instead of dhcpcd (Pi 5 Bookworm compatible)
- [x] ModemManager disabled (was blocking ttyUSB ports)
- [x] GPS: gpsd + sim7600-gps-enable systemd service
- [x] Fixed port schema: ttyUSB2=GPS, ttyUSB3=AT+PPP
- [x] Status tools: lte-status, gps-status
- [x] Routing: eth0 (100) → wlan0 (600) → ppp0 (700)
- [x] Generalized for ALL DSE controllers (5510, 8610, 8610 MKII, 7310, L401)
- [x] Controller type passed to generated script (header + config)
- [x] 3-phase indicator (L1/L2/L3) shown for 8610/7310 controllers
- [x] Both DSE 890 Gateway AND Pi Setup available for 8610/7310/L401

### Finance
- [x] Invoice Payment Status (Bezahlt/Offen) & Filter UI
- [x] 2-Stage Dunning Workflow (Mahnwesen) with Admin Task integration
- [x] FinTS/HBCI Bank integration code (disabled pending bank registration)
- [x] Fuel Management (Tankbelege) UI

## Upcoming Tasks (P1)
- [ ] Microsoft 365 Postfach-Anbindung
- [ ] Test Tankwagen-Pi setup script on real hardware
- [ ] FinTS/HBCI activation when bank registers Product ID

## Future Tasks (P2)
- [ ] Eingangsrechnungen überwachen
- [ ] PayPal/Kreditkarten Integration
- [ ] Lastdiagramm Live-Test
- [ ] Chromium "Translate" Popup on RPi Kiosk
- [ ] GPS Support for Kirmeskiste

## Test Credentials
- Admin: christian.ecker@eventenergie-deutschland.de / qivbeb-Wodha1-sewram
- Admin Preview: admin@test.com / password
