# DSE Power Generator Portal – PRD

## Original Problem Statement
A comprehensive monitoring and management portal for Deep Sea Electronics (DSE) power generators. Started as a secure file exchange application and evolved into a full fleet management system.

## User Personas
- **Administrator**: Full CRUD access to devices, users, service plans, MQTT config. Can manage all settings.
- **Mitarbeiter (Employee)**: Can view devices, update status/notes, create maintenance entries.
- **Kunde (Customer)**: Limited view access.

## Core Requirements
1. **Generator Monitoring**: Dashboard with real-time analytics (status, load, temperature) and map location for generators.
2. **Device Management ("Geräteverwaltung")**: Full CRUD, image/document uploads, parts management, QR codes.
3. **QR Code System**: Unique device codes with printable QR codes for quick lookup.
4. **Service Planning ("Serviceplan")**: Multi-section maintenance schedules, checklists, measurement logs, photo uploads.
5. **User & Permissions**: Role-based access (Admin, Mitarbeiter, Kunde).
6. **File Management**: GridFS-based secure storage for device images and documents.
7. **Email Notifications**: Password reset via SMTP (smtp.mail.de:465 SSL).
8. **MQTT Integration**: Connect DSE WebNet Gateways via MQTT for real-time telemetry.

## Tech Stack
- **Backend**: FastAPI, Python, MongoDB (Motor), GridFS, paho-mqtt
- **Frontend**: React, Tailwind CSS, Shadcn/UI, Recharts, Leaflet
- **Auth**: JWT with role-based access
- **QR**: qrcode (backend), react-qr-code (frontend)
- **Email**: smtplib with SMTP_SSL to smtp.mail.de:465
- **MQTT**: paho-mqtt v2.1.0 (MQTT v3.1.1)

## Architecture
```
/app/
├── backend/
│   ├── server.py
│   ├── models.py
│   ├── email_service.py
│   ├── mqtt_service.py          # NEW: MQTT client service
│   └── routes/
│       ├── generators.py
│       ├── devices.py
│       ├── serviceplan.py
│       └── mqtt_config.py       # NEW: MQTT config API
└── frontend/
    └── src/
        ├── App.js, api.js
        └── pages/
            ├── AdminPage.js
            ├── GeneratorDashboardPage.js
            ├── DeviceManagementPage.js
            ├── ServiceplanPage.js
            └── MqttConfigPage.js  # NEW: MQTT admin UI
```

## What's Been Implemented
- ✅ Full device CRUD with image uploads, document attachments, parts management
- ✅ QR code system (unique device codes, printable QR)
- ✅ Device copy with image/parts/documents duplication
- ✅ Service plan CRUD with maintenance history (sorted newest-first)
- ✅ Cascade delete: deleting a device removes its service plan + maintenance entries
- ✅ Orphaned service plan cleanup and prevention
- ✅ Generator monitoring dashboard (simulated + MQTT data)
- ✅ Role-based access control
- ✅ File downloads with authenticated fetch
- ✅ SMTP Email sending (password reset) – Fixed 2026-03-06
- ✅ **MQTT Integration** – Implemented 2026-03-06:
  - Backend MQTT client service (paho-mqtt, background thread)
  - Admin MQTT config page (broker URL/port/credentials/TLS/topics)
  - Gateway-to-generator topic mapping system
  - Raw message viewer for debugging/format discovery
  - Flexible telemetry parser (JSON with field mapping for DSE parameters)
  - Automatic telemetry storage with `source: "mqtt"`
  - Setup instructions for gateway configuration

## MQTT Data Flow
```
[DSE Gateway] --MQTT--> [Cloud Broker (HiveMQ/EMQX)] <--subscribe-- [Backend mqtt_service.py]
                                                                          |
                                                                    Parse & Map to Generator
                                                                          |
                                                                    MongoDB generator_telemetry
                                                                          |
                                                                    Frontend Dashboard
```

## Known Issues
- **Simulated Data**: Generator telemetry is mocked for demo generators (not live DSE890 data yet)

## Backlog (Prioritized)
### P1
- User configures actual cloud MQTT broker and points DSE gateways to it
- Discover real DSE890 MQTT topic format and refine parser
- Add full support for "Messkoffer" and "Kirmeskiste" device types

### P2
- Integrate live data from DSE890 generator modules (once MQTT connected)
- Implement admin-controlled file size limits

### Refactoring
- Break down ServiceplanPage.js into smaller components
- Extract Parts management and file upload logic from DeviceManagementPage.js

## Test Credentials
- Admin: admin@test.com / password
- Mitarbeiter: ma1@test.com / password
- SMTP: eventenergie@mail.de / S8e?CuL7N6! (smtp.mail.de:465 SSL)

## DB Collections for MQTT
- `mqtt_config`: Broker connection settings (single document)
- `mqtt_gateway_mappings`: Topic prefix to generator_id mappings
- `mqtt_raw_messages`: Last 500 received raw MQTT messages for debugging
