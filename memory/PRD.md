# DSE Power Generator Portal – PRD

## Original Problem Statement
A comprehensive monitoring and management portal for Deep Sea Electronics (DSE) power generators. Started as a secure file exchange application and evolved into a full fleet management system.

## User Personas
- **Administrator**: Full CRUD access to devices, users, service plans, MQTT config.
- **Mitarbeiter (Employee)**: Can view devices, update status/notes, create maintenance entries.
- **Kunde (Customer)**: Limited view access.

## Core Requirements
1. **Generator Monitoring**: Dashboard with real-time analytics and map location.
2. **Device Management**: Full CRUD, image/document uploads, parts management, QR codes.
3. **QR Code System**: Unique device codes with printable QR codes.
4. **Service Planning**: Maintenance schedules, checklists, measurement logs, photo uploads.
5. **User & Permissions**: Role-based access (Admin, Mitarbeiter, Kunde).
6. **File Management**: GridFS-based secure storage.
7. **Email Notifications**: Password reset via SMTP (working).
8. **MQTT Integration**: Connect DSE WebNet Gateways via MQTT for real-time telemetry.

## Tech Stack
- **Backend**: FastAPI, Python, MongoDB (Motor), GridFS, paho-mqtt
- **Frontend**: React, Tailwind CSS, Shadcn/UI, Recharts, Leaflet
- **Auth**: JWT with role-based access
- **QR**: qrcode (backend), react-qr-code (frontend)
- **Email**: smtplib SMTP_SSL smtp.mail.de:465
- **MQTT**: paho-mqtt v2.1.0 (MQTT v3.1.1)

## Architecture
```
/app/
├── backend/
│   ├── server.py
│   ├── models.py
│   ├── email_service.py
│   ├── mqtt_service.py
│   └── routes/
│       ├── generators.py
│       ├── devices.py
│       ├── serviceplan.py
│       └── mqtt_config.py
├── dse8610_module_topics.csv     # Module topic file for DSE8610 MK2
├── dse890_gateway_topics.csv     # Gateway topic file for DSE890
└── frontend/
    └── src/
        ├── App.js, api.js
        └── pages/
            ├── AdminPage.js
            ├── GeneratorDashboardPage.js
            ├── GeneratorDetailPage.js
            ├── DeviceManagementPage.js
            ├── ServiceplanPage.js
            └── MqttConfigPage.js
```

## What's Been Implemented
- ✅ Full device CRUD with image uploads, document attachments, parts management
- ✅ QR code system (unique device codes, printable QR)
- ✅ Device copy with image/parts/documents duplication
- ✅ Service plan CRUD with maintenance history (sorted newest-first)
- ✅ Cascade delete: deleting device removes service plan + maintenance entries
- ✅ Orphaned service plan cleanup and prevention
- ✅ Generator monitoring dashboard (simulated + MQTT data)
- ✅ Role-based access control
- ✅ File downloads with authenticated fetch
- ✅ SMTP Email sending (password reset) – Fixed: password typo corrected
- ✅ MQTT Integration backend:
  - Backend MQTT client service (paho-mqtt, background thread)
  - Admin MQTT config page (broker URL/port/credentials/TLS/topics)
  - Gateway-to-generator topic mapping system
  - Raw message viewer for debugging/format discovery
  - Flexible telemetry parser with DSE field mapping
  - Automatic telemetry storage with `source: "mqtt"`
  - Setup instructions for gateway configuration
  - Download endpoints for topic files
- ✅ Virtual generator support (devices shown as generators in monitoring)
- ✅ "Invalid Date" fix for virtual generators

## MQTT Integration Status
- **Backend**: Fully functional - connects to HiveMQ public broker, receives and stores messages ✅
- **Config**: broker.hivemq.com:1883, subscribed to DSEGateway4G/#, S50-18A01/#, eventenergie/#, dse/#
- **Mapping**: DSEGateway4G → Fahrgestell S50-18A01 (dev-72c3022f-3d51-4005-a21c-b09ec926fe97)
- **Gateway Status**: MQTT Client Open GSM ✅, but topic file upload not yet successful
- **BLOCKER**: DSE890 Gateway shows "Module 0 row 2/23 Invalid field value" errors
  - Root cause: Topic file needs to be uploaded ONLY to Module Index 1, NOT to Gateway slot
  - User needs to: Remove all files, restart gateway, upload module file to Module Index 1 only
  - Topic files created: `dse8610_module_topics.csv` (register reads) and `dse890_gateway_topics.csv` (status/GPS)
  - Download links: /api/download-topic-file and /api/download-gateway-topic-file

## DSE8610 MK2 Register Map (Page 4 = Instrumentation)
- Offset 0: Oil pressure (kPa, 16-bit)
- Offset 1: Coolant temp (°C, 16-bit signed)
- Offset 2: Oil temp (°C, 16-bit signed)
- Offset 3: Fuel level (%, 16-bit)
- Offset 4: Charge alternator voltage (0.1V, 16-bit)
- Offset 5: Battery voltage (0.1V, 16-bit)
- Offset 6: Engine speed (RPM, 16-bit)
- Offset 7: Generator frequency (0.1Hz, 16-bit)
- Offset 8-9: Gen L1-N voltage (0.1V, 32-bit)
- Offset 10-11: Gen L2-N voltage (0.1V, 32-bit)
- Offset 12-13: Gen L3-N voltage (0.1V, 32-bit)
- Offset 20-21: Gen L1 current (0.1A, 32-bit)
- Offset 22-23: Gen L2 current (0.1A, 32-bit)
- Offset 24-25: Gen L3 current (0.1A, 32-bit)
- Offset 28-29: Gen L1 watts (W, 32-bit signed)
- Offset 30-31: Gen L2 watts (W, 32-bit signed)
- Offset 32-33: Gen L3 watts (W, 32-bit signed)
- Offset 35: Mains frequency (0.1Hz, 16-bit)
- Offset 36-37: Mains L1-N voltage (0.1V, 32-bit)
- Offset 38-39: Mains L2-N voltage (0.1V, 32-bit)
- Offset 40-41: Mains L3-N voltage (0.1V, 32-bit)

## Known Issues
- **MQTT Topic File Upload**: Gateway shows "Invalid field value" errors. File must go to Module Index 1 only, not Gateway slot. User needs to retry with clean state.
- **Simulated Data**: Demo generators still use simulated telemetry.

## Backlog (Prioritized)
### P0 (Next Session)
- Complete DSE890 MQTT topic file configuration (user retries upload to correct slot)
- Once data flows: verify telemetry parsing and dashboard display
- Adjust MQTT field mapper to match actual DSE890 data format

### P1
- Add full support for "Messkoffer" and "Kirmeskiste" device types
- Scale MQTT to all 9+ gateways

### P2
- Implement admin-controlled file size limits
- Move from public broker to secured HiveMQ Cloud

### Refactoring
- Break down ServiceplanPage.js into smaller components
- Extract Parts management from DeviceManagementPage.js

## Test Credentials
- Admin: admin@test.com / password
- Mitarbeiter: ma1@test.com / password
- SMTP: eventenergie@mail.de / S8e?CuL7N6! (smtp.mail.de:465 SSL)

## DB Collections for MQTT
- `mqtt_config`: Broker connection settings (single document)
- `mqtt_gateway_mappings`: Topic prefix to generator_id mappings
- `mqtt_raw_messages`: Last 500 received raw MQTT messages for debugging
- `generator_telemetry`: Stores telemetry with `source: "mqtt"` field
