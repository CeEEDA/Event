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
10. **EpiRent ERP Integration**: Order management page with live data from EpiRent ERP API.

## Tech Stack
- **Backend**: FastAPI, Python, MongoDB (Motor), GridFS, paho-mqtt, httpx
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
│   ├── static/emu_sync.py
│   └── routes/
│       ├── generators.py
│       ├── devices.py
│       ├── serviceplan.py
│       ├── mqtt_config.py
│       ├── energy_monitoring.py
│       ├── admin_settings.py
│       └── orders.py              # NEW: EpiRent order proxy
└── frontend/src/pages/
    ├── AdminPage.js
    ├── AdminSettingsPage.js
    ├── DeviceManagementPage.js
    ├── EnergyMonitoringPage.js
    ├── EnergyMonitoringDetailPage.js
    ├── GeneratorDashboardPage.js
    ├── GeneratorDetailPage.js
    └── OrdersPage.js              # NEW: Auftragsverwaltung
```

## What's Been Implemented
- All device CRUD with image uploads, document attachments, parts management
- QR code system, service plans with cascade delete
- Generator monitoring dashboard
- SMTP Email, MQTT Integration backend
- Energy Monitoring Dashboard with real EMU data
- OpenStreetMap GPS locations
- HTTPS Ingest API for Pi sync
- Pi Sync Script (downloadable)
- Account-level time-based access for Kunden
- Pi connection fields in Messkoffer device form
- Date range picker (Von/Bis) with CSV export
- Online filtering - overview only shows devices with data
- Data access range for Kunden
- DSE890 Gateway Setup with MQTT-Info and Topic-Download
- EpiRent ERP Integration: Admin-Einstellungen with API-Test
- **Auftragsverwaltung (Order Management) Page** (2026-03-08):
  - Backend proxy to EpiRent `/v1/order/filter` API with authentication
  - Contact address resolution via parallel API calls
  - Date range filter (default: -1 week to +4 weeks)
  - Free-text search (order number, event, customer, address)
  - Sortable table columns
  - Status badges (Offen, Bestätigt, Storniert, Archiviert)
  - Auth-protected endpoint

## Key API Endpoints
- `GET /api/orders/epirent` - Proxy to EpiRent orders (auth required, params: date_from, date_to, search, page, page_size)
- `GET, POST, PUT, DELETE /api/admin/integrations` - CRUD for third-party integrations
- `POST /api/admin/integrations/{id}/test` - Test integration connection
- `GET /api/energy-monitoring/devices` - List energy monitoring devices
- `GET /api/energy-monitoring/devices/:id/telemetry` - Device telemetry data
- `POST /api/energy-monitoring/ingest` - Pi batch upload

## User Permission Structure
```json
{
  "access_type": "permanent",
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

## Backlog
### P0
- Link Generators to Orders (next step after order list)

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
