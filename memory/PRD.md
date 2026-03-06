# DSE Power Generator Portal – PRD

## Original Problem Statement
A comprehensive monitoring and management portal for Deep Sea Electronics (DSE) power generators. Started as a secure file exchange application and evolved into a full fleet management system with energy monitoring capabilities.

## User Personas
- **Administrator**: Full CRUD access to devices, users, service plans, MQTT config, energy monitoring config.
- **Mitarbeiter (Employee)**: Can view devices, update status/notes, create maintenance entries.
- **Kunde (Customer)**: Limited view access. Energy monitoring with optional time-based access control at account level.

## Core Requirements
1. **Generator Monitoring**: Dashboard with real-time analytics and map location.
2. **Energy Monitoring (Messkoffer)**: Dashboard showing EMU meter data (voltage, current, power, frequency, energy) per Messkoffer device with charts, time-range filtering, and GPS map.
3. **Device Management**: Full CRUD, image/document uploads, parts management, QR codes.
4. **QR Code System**: Unique device codes with printable QR codes.
5. **Service Planning**: Maintenance schedules, checklists, measurement logs, photo uploads.
6. **User & Permissions**: Role-based access (Admin, Mitarbeiter, Kunde) with per-app granular control.
7. **File Management**: GridFS-based secure storage.
8. **Email Notifications**: Password reset via SMTP (working).
9. **MQTT Integration**: Connect DSE WebNet Gateways via MQTT for real-time telemetry.
10. **Pi Data Sync**: Raspberry Pi records EMU data locally (SQLite) and syncs to backend via HTTPS API.

## Tech Stack
- **Backend**: FastAPI, Python, MongoDB (Motor), GridFS, paho-mqtt
- **Frontend**: React, Tailwind CSS, Shadcn/UI, Recharts, Leaflet/OpenStreetMap
- **Auth**: JWT with role-based access
- **QR**: qrcode (backend), react-qr-code (frontend)
- **Email**: smtplib SMTP_SSL smtp.mail.de:465
- **MQTT**: paho-mqtt v2.1.0 (MQTT v3.1.1)
- **Maps**: Leaflet + OpenStreetMap (react-leaflet)

## Architecture
```
/app/
├── backend/
│   ├── server.py
│   ├── models.py
│   ├── email_service.py
│   ├── mqtt_service.py
│   ├── static/emu_sync.py          # Pi sync script (downloadable)
│   └── routes/
│       ├── generators.py
│       ├── devices.py
│       ├── serviceplan.py
│       ├── mqtt_config.py
│       └── energy_monitoring.py     # Ingest API, GPS, telemetry
└── frontend/src/pages/
    ├── AdminPage.js
    ├── GeneratorDashboardPage.js
    ├── GeneratorDetailPage.js
    ├── DeviceManagementPage.js
    ├── ServiceplanPage.js
    ├── MqttConfigPage.js
    ├── EnergyMonitoringPage.js      # Dashboard + OpenStreetMap
    └── EnergyMonitoringDetailPage.js # Detail + charts + map
```

## What's Been Implemented
- ✅ Full device CRUD with image uploads, document attachments, parts management
- ✅ QR code system
- ✅ Service plan CRUD with cascade delete
- ✅ Generator monitoring dashboard (simulated + MQTT data)
- ✅ Role-based access control
- ✅ SMTP Email (password reset)
- ✅ MQTT Integration backend
- ✅ **Energy Monitoring Dashboard** with real EMU data (34,277 records imported)
- ✅ **OpenStreetMap** showing device GPS locations on dashboard + detail page
- ✅ **HTTPS Ingest API** for Pi sync (batch upload with API key auth)
- ✅ **Pi Sync Script** (downloadable Python script for Raspberry Pi)
- ✅ **Account-level time-based access** for Kunden (permanent or date-limited)
- ✅ **Admin permissions UI** for Energy Monitoring (enable, all/individual, device selection)

## Pi Sync Architecture (Option B - HTTPS Push)
```
[Raspberry Pi]                          [Backend Server]
  EMU Meters → SQLite DB (local)          MongoDB
  emu_sync.py runs as service             /api/energy-monitoring/ingest
    ↓ checks internet                       ↓
    ↓ reads new records                    stores in emu_data collection
    ↓ POST batch to server                 tracks sync state
    ↓ retries if offline                   
```

## Key API Endpoints (Energy Monitoring)
- `GET /api/energy-monitoring/devices` - List Messkoffer
- `GET /api/energy-monitoring/devices/:id` - Device detail with meters
- `GET /api/energy-monitoring/devices/:id/telemetry` - Telemetry data (time filtered)
- `GET /api/energy-monitoring/devices/:id/telemetry/latest` - Latest per meter
- `GET /api/energy-monitoring/devices/:id/location` - Latest GPS
- `GET /api/energy-monitoring/locations` - All device GPS locations
- `POST /api/energy-monitoring/ingest` - Batch data from Pi (API key auth)
- `GET /api/energy-monitoring/ingest/sync-state` - Last sync ID
- `POST /api/energy-monitoring/ingest/generate-key` - Generate API key (admin)
- `GET /api/download-sync-script` - Download Pi sync script

## DB Collections (Energy Monitoring)
- `emu_meters`: `{ id, device_id, meter_ip, meter_name, description }`
- `emu_data`: `{ id, device_id, meter_id, ts_utc, I_L1-L3, U_L1-L3, F_Hz, P_sum_kW, ..., gps_lat, gps_lon, gps_alt_m, gps_speed_mps, gps_mode }`
- `emu_settings`: `{ key: "ingest_api_key", value: "..." }`
- `emu_sync_state`: `{ device_id, meter_id, last_sync_id, last_sync_at }`

## User Permission Structure
```json
{
  "access_type": "permanent",
  "access_start": null,
  "access_end": null,
  "apps": {
    "energy_monitoring": {
      "enabled": false,
      "access_all": false,
      "device_ids": []
    }
  }
}
```
Note: access_type/start/end are at USER/account level, not per-function.

## Backlog (Prioritized)
### P0
- MQTT Gateway topic files: resume when user is ready
- Connect more Pis with real Messkoffer

### P1
- "Kirmeskiste" device type support
- Scale MQTT to 9+ gateways

### P2
- Admin file size limits
- Secure MQTT broker (HiveMQ Cloud)

### Refactoring
- Break down ServiceplanPage.js
- Extract Parts management from DeviceManagementPage.js
- Move MQTT routes from server.py to routes/mqtt_config.py

## Test Credentials
- Admin: admin@test.com / password
- Mitarbeiter: ma1@test.com / password
- Kunde: kunde@test.com / password
- Ingest API Key: 7fbe01c5c9624306973a8d3e447b271a
