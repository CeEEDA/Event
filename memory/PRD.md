# DSE Power Generator Portal – PRD

## Original Problem Statement
A comprehensive monitoring and management portal for Deep Sea Electronics (DSE) power generators. Started as a secure file exchange application and evolved into a full fleet management system with energy monitoring capabilities.

## User Personas
- **Administrator**: Full CRUD access to devices, users, service plans, MQTT config, energy monitoring config.
- **Mitarbeiter (Employee)**: Can view devices, update status/notes, create maintenance entries.
- **Kunde (Customer)**: Limited view access. Energy monitoring with time-based account access + data range restrictions.

## Core Requirements
1. **Generator Monitoring**: Dashboard with real-time analytics and map location.
2. **Energy Monitoring (Messkoffer)**: Dashboard with EMU meter data, GPS map, date range picker, CSV export.
3. **Device Management**: Full CRUD, image/document uploads, parts, QR codes, Pi connection data for Messkoffer.
4. **Service Planning**: Maintenance schedules, checklists, measurement logs, photo uploads.
5. **User & Permissions**: Role-based access with per-app control + data access range for Kunden.
6. **File Management**: GridFS-based secure storage.
7. **Email Notifications**: Password reset via SMTP.
8. **MQTT Integration**: DSE WebNet Gateways via MQTT.
9. **Pi Data Sync**: Raspberry Pi records locally (SQLite) and syncs via HTTPS API.

## Tech Stack
- **Backend**: FastAPI, Python, MongoDB (Motor), GridFS, paho-mqtt
- **Frontend**: React, Tailwind CSS, Shadcn/UI, Recharts, Leaflet/OpenStreetMap
- **Auth**: JWT with role-based access
- **Maps**: Leaflet + OpenStreetMap (react-leaflet)
- **Email**: smtplib SMTP_SSL

## Architecture
```
/app/
├── backend/
│   ├── server.py
│   ├── mqtt_service.py
│   ├── static/emu_sync.py          # Pi sync script
│   └── routes/
│       ├── generators.py
│       ├── devices.py               # Pi fields for Messkoffer
│       ├── serviceplan.py
│       ├── mqtt_config.py
│       └── energy_monitoring.py     # Ingest, GPS, telemetry, data access
└── frontend/src/pages/
    ├── AdminPage.js                 # User perms + data access range
    ├── DeviceManagementPage.js      # Pi connection fields for Messkoffer
    ├── EnergyMonitoringPage.js      # Dashboard + map + online filter
    └── EnergyMonitoringDetailPage.js # Date picker + charts + CSV export
```

## What's Been Implemented
- ✅ Full device CRUD with image uploads, document attachments, parts management
- ✅ QR code system, service plans with cascade delete
- ✅ Generator monitoring dashboard
- ✅ SMTP Email, MQTT Integration backend
- ✅ Energy Monitoring Dashboard with real EMU data (34,277 records)
- ✅ OpenStreetMap GPS locations
- ✅ HTTPS Ingest API for Pi sync
- ✅ Pi Sync Script (downloadable)
- ✅ Account-level time-based access for Kunden
- ✅ **Pi connection fields** in Messkoffer device form (username, password, notes only — hostname/IP/SSH removed)
- ✅ **Date range picker** (Von/Bis) replacing fixed time range selector, default = last 24h
- ✅ **CSV Export** for selected time range (semicolon separator for German Excel)
- ✅ **Online filtering** - overview only shows devices with data
- ✅ **Data access range** for Kunden - admin restricts which measurement period is visible

## Key API Endpoints (Energy Monitoring)
- `GET /api/energy-monitoring/devices` - List (with is_online field, online_only param)
- `GET /api/energy-monitoring/devices/:id/telemetry` - Data (enforces Kunde data range)
- `GET /api/energy-monitoring/data-access-range` - Get user's allowed data range
- `GET /api/energy-monitoring/locations` - GPS locations
- `POST /api/energy-monitoring/ingest` - Pi batch upload
- `GET /api/download-sync-script` - Pi sync script

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
      "device_ids": [],
      "data_access_start": null,
      "data_access_end": null
    }
  }
}
```

- ✅ **Messkoffer form cleanup**: "Seriennummer" → "Gerätenummer", removed Modell/Leistung, simplified Pi section to username+password only
- ✅ **All-in-One Pi Setup-Skript**: Single bash installer with embedded Messkoffer Logger (Shelly Pro 3EM readout + USB GPS via gpsd + local SQLite + background portal sync + 60GB auto-cleanup). One-click download from Device Management UI

## Recent Changes (2026-03-06)
- ✅ DSE Remote Control UI finalized: Button order Stop → Auto → Start, confirmation popup removed
- ✅ Dynamic button colors based on generator status (running/stopped/standby)
- ✅ Live DSE890/L401 MQTT integration (bidirectional: data + control)

- ✅ **DSE890 Gateway Setup**: Konfigurationssektion im Geräteformular mit MQTT-Info, Topic-Download, Benutzer/Passwort
- ✅ **EpiRent ERP Integration**: Admin-Einstellungen mit API-Test, Mandanten, Aufträge, Unterjobs, Kennzeichnungen (Ja/Nein/Nicht prüfen)
- ✅ **EpiRent API**: Live-Verbindung zu http://217.86.214.29:18081 (848 Artikel, 586 Bestände)

## Backlog
### P1
- Self-hosted MQTT Broker (Mosquitto) — move broker URL to .env
- "Kirmeskiste" device type support
- Scale MQTT to 9+ gateways

### P2
- Admin file size limits

### Refactoring
- Move MQTT broker URL from hardcoded to backend/.env
- Break down ServiceplanPage.js, DeviceManagementPage.js

## Test Credentials
- Admin: admin@test.com / password
- Ingest API Key: 7fbe01c5c9624306973a8d3e447b271a
