# DSE Power Generator Portal – PRD

## Original Problem Statement
A comprehensive monitoring and management portal for Deep Sea Electronics (DSE) power generators. Started as a secure file exchange application and evolved into a full fleet management system.

## User Personas
- **Administrator**: Full CRUD access to devices, users, service plans. Can manage all settings.
- **Mitarbeiter (Employee)**: Can view devices, update status/notes, create maintenance entries.
- **Kunde (Customer)**: Limited view access.

## Core Requirements
1. **Generator Monitoring**: Dashboard with real-time analytics (status, load, temperature) and map location for generators.
2. **Device Management ("Geräteverwaltung")**: Full CRUD, image/document uploads, parts management, QR codes.
3. **QR Code System**: Unique device codes with printable QR codes for quick lookup.
4. **Service Planning ("Serviceplan")**: Multi-section maintenance schedules, checklists, measurement logs, photo uploads.
5. **User & Permissions**: Role-based access (Admin, Mitarbeiter, Kunde).
6. **File Management**: GridFS-based secure storage for device images and documents.
7. **Email Notifications**: Password reset via SMTP (currently blocked by external config).

## Tech Stack
- **Backend**: FastAPI, Python, MongoDB (Motor), GridFS
- **Frontend**: React, Tailwind CSS, Shadcn/UI, Recharts, Leaflet
- **Auth**: JWT with role-based access
- **QR**: qrcode (backend), react-qr-code (frontend)

## Architecture
```
/app/
├── backend/
│   ├── server.py
│   ├── models.py
│   ├── email_service.py
│   └── routes/
│       ├── generators.py
│       ├── devices.py
│       └── serviceplan.py
└── frontend/
    └── src/
        ├── App.js, api.js
        └── pages/
            ├── AdminPage.jsx
            ├── GeneratorDashboardPage.js
            ├── DeviceManagementPage.js
            └── ServiceplanPage.js
```

## What's Been Implemented
- ✅ Full device CRUD with image uploads, document attachments, parts management
- ✅ QR code system (unique device codes, printable QR)
- ✅ Device copy with image/parts/documents duplication
- ✅ Service plan CRUD with maintenance history (sorted newest-first)
- ✅ Cascade delete: deleting a device removes its service plan + maintenance entries
- ✅ Orphaned service plan cleanup and prevention
- ✅ Generator monitoring dashboard (simulated data)
- ✅ Role-based access control
- ✅ File downloads with authenticated fetch

## Known Issues
- **SMTP Email**: Password reset blocked by external mail.de server config (BLOCKED)
- **Simulated Data**: Generator telemetry is mocked (not live DSE890 data)

## Backlog (Prioritized)
### P1
- Add full support for "Messkoffer" and "Kirmeskiste" device types in device management and service planning

### P2
- Integrate live data from DSE890 generator modules
- Implement admin-controlled file size limits
- SMTP email fix (pending user's mail.de account resolution)

### Refactoring
- Break down ServiceplanPage.js into smaller components
- Extract Parts management and file upload logic from DeviceManagementPage.js

## Test Credentials
- Admin: admin@test.com / password
- Mitarbeiter: ma1@test.com / password
