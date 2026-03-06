# DSE Power Generator Portal – PRD

## Original Problem Statement
A comprehensive monitoring and management portal for Deep Sea Electronics (DSE) power generators. Started as a secure file exchange application and evolved into a full fleet management system with energy monitoring capabilities.

## User Personas
- **Administrator**: Full CRUD access to devices, users, service plans, MQTT config, energy monitoring config.
- **Mitarbeiter (Employee)**: Can view devices, update status/notes, create maintenance entries.
- **Kunde (Customer)**: Limited view access. Energy monitoring with optional time-based access control.

## Core Requirements
1. **Generator Monitoring**: Dashboard with real-time analytics and map location.
2. **Energy Monitoring (Messkoffer)**: Dashboard showing EMU meter data (voltage, current, power, frequency, energy) per Messkoffer device with charts and time-range filtering.
3. **Device Management**: Full CRUD, image/document uploads, parts management, QR codes.
4. **QR Code System**: Unique device codes with printable QR codes.
5. **Service Planning**: Maintenance schedules, checklists, measurement logs, photo uploads.
6. **User & Permissions**: Role-based access (Admin, Mitarbeiter, Kunde) with per-app granular control.
7. **File Management**: GridFS-based secure storage.
8. **Email Notifications**: Password reset via SMTP (working).
9. **MQTT Integration**: Connect DSE WebNet Gateways via MQTT for real-time telemetry.

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
│       ├── mqtt_config.py
│       └── energy_monitoring.py  # NEW
├── dse8610_module_topics.csv
├── dse890_gateway_topics.csv
└── frontend/
    └── src/
        ├── App.js, api.js
        └── pages/
            ├── AdminPage.js
            ├── GeneratorDashboardPage.js
            ├── GeneratorDetailPage.js
            ├── DeviceManagementPage.js
            ├── ServiceplanPage.js
            ├── MqttConfigPage.js
            ├── EnergyMonitoringPage.js       # NEW
            └── EnergyMonitoringDetailPage.js  # NEW
```

## What's Been Implemented
- ✅ Full device CRUD with image uploads, document attachments, parts management
- ✅ QR code system (unique device codes, printable QR)
- ✅ Device copy with image/parts/documents duplication
- ✅ Service plan CRUD with maintenance history
- ✅ Cascade delete: deleting device removes service plan + maintenance entries
- ✅ Generator monitoring dashboard (simulated + MQTT data)
- ✅ Role-based access control
- ✅ File downloads with authenticated fetch
- ✅ SMTP Email sending (password reset)
- ✅ MQTT Integration backend (broker connection, topic mapping, telemetry storage)
- ✅ Virtual generator support
- ✅ **Energy Monitoring (Messkoffer)** - NEW:
  - Hub page button with amber/yellow accent
  - Dashboard listing Messkoffer devices with stats (total, online, kW, kWh)
  - Detail page with 5 chart types (Power per phase, Voltage, Current, Energy Import, Frequency)
  - Real-time metric cards (Leistung, Spannung, Strom, Frequenz, Energie, Cos Phi)
  - Time range selector (1h, 6h, 24h, 7d)
  - Per-meter filtering
  - Admin permission management (enable/disable, all/individual devices)
  - **Kunden time-based access** (permanent or date-limited with auto-expiry)
  - Demo data seeding endpoint
  - Backend permission checking with time-based access validation

## Energy Monitoring Data Model
### EMU Meter Fields (per reading):
- `ts_utc`, `meter_ts` - Timestamps
- `I_L1`, `I_L2`, `I_L3`, `I_sum` - Current (A)
- `U_L1`, `U_L2`, `U_L3` - Voltage (V)
- `F_Hz` - Frequency (Hz)
- `P_sum_kW`, `P_L1_kW`, `P_L2_kW`, `P_L3_kW` - Active Power (kW)
- `Q_sum`, `Q_L1`, `Q_L2`, `Q_L3` - Reactive Power (VAR)
- `PF_L1`, `PF_L2`, `PF_L3` - Power Factor
- `E_imp_kWh`, `E_exp_kWh` - Energy Import/Export (kWh)
- `http_ok`, `error` - Status

### User Permission Structure:
```json
{
  "apps": {
    "energy_monitoring": {
      "enabled": false,
      "access_all": false,
      "device_ids": [],
      "access_type": "permanent",
      "access_start": null,
      "access_end": null
    }
  }
}
```

## Known Issues
- **MQTT Topic File Upload**: PAUSED - waiting for user to retry hardware configuration
- **Simulated Data**: Demo generators still use simulated telemetry
- **Energy Monitoring Data**: Currently uses DEMO/seeded data. External EMU database connection pending.

## Backlog (Prioritized)
### P0 (Current/Next)
- Connect Energy Monitoring to user's real EMU database (external DB)
- Resume DSE890 MQTT topic file configuration when user is ready

### P1
- Add full support for "Kirmeskiste" device type
- Scale MQTT to all 9+ gateways
- Once MQTT data flows: verify telemetry parsing and dashboard display

### P2
- Implement admin-controlled file size limits
- Move from public broker to secured HiveMQ Cloud

### Refactoring
- Break down ServiceplanPage.js into smaller components
- Extract Parts management from DeviceManagementPage.js
- Move MQTT route definitions from server.py to routes/mqtt_config.py

## DB Collections
### Energy Monitoring
- `emu_meters`: `{ id, device_id, meter_ip, meter_name, description, created_at }`
- `emu_data`: `{ id, device_id, meter_id, ts_utc, meter_ts, I_L1-L3, U_L1-L3, F_Hz, P_sum_kW, ... }`

### MQTT
- `mqtt_config`: Broker connection settings
- `mqtt_gateway_mappings`: Topic prefix to generator_id mappings
- `mqtt_raw_messages`: Debugging raw MQTT messages
- `generator_telemetry`: Telemetry with `source: "mqtt"` field

## Test Credentials
- Admin: admin@test.com / password
- Mitarbeiter: ma1@test.com / password
- Kunde: kunde@test.com / password
- SMTP: eventenergie@mail.de / S8e?CuL7N6! (smtp.mail.de:465 SSL)
