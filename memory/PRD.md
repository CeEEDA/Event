# PRD - Eventenergie Monitoring & Management Portal

## Original Problem Statement
Comprehensive monitoring and management portal for Deep Sea Electronics (DSE) power generators with device management, maintenance scheduling, and secure file sharing.

## Tech Stack
- **Backend:** FastAPI, Python, MongoDB, GridFS
- **Frontend:** React, Tailwind CSS, Shadcn/UI, Recharts, Leaflet
- **Auth:** JWT with 3 roles (Administrator, Mitarbeiter, Kunde)

## Architecture
```
/app/backend/
  server.py, email_service.py
  routes/ generators.py, devices.py, serviceplan.py
/app/frontend/src/pages/
  HubPage.js, AdminPage.js, DeviceManagementPage.js
  ServiceplanPage.js, GeneratorDashboardPage.js
  GeneratorDetailPage.js, ForgotPasswordPage.js, DashboardPage.js
```

## Implemented Features

### Generator Monitoring (Complete)
- Simulated data dashboard with grid/list/map view
- Status filters, detail pages with charts
- Permission-based generator access
- Maintenance warnings (yellow badge) when < 1 month or < 50 hours

### Device Management (Complete)
- CRUD with role-based permissions
- Device image upload for visual identification
- "Copy from existing" in create flow (preserves image)
- Document upload per device

### Service Plans - Wartungsplan (Complete - 2026-03-06)
**Professional 6-section maintenance form for generators/light masts:**
1. Mechanische Prüfung (12 items, 3-state: durchgeführt/nicht durchgeführt/nicht vorhanden)
2. Elektrische Prüfung (13 items, 3-state push buttons)
3. Generator Messwerte (15 measurement input fields)
4. Lasttest Generator (25%/50%/75%/100% table)
5. ATS / Netzumschaltung Test (6 checkboxes + Umschaltzeit)
6. Diagnose (Fehlerspeicher, Fehlercodes freies Feld)

**Additional features:**
- Technician auto-filled from logged-in user
- Next maintenance: choose months OR hours, auto-calculated
- Operating hours tracking
- Photo upload (mobile camera support)
- Remarks field for special incidents
- Search function, stats dashboard

### Email Service (Implemented, SMTP auth pending)
- Password reset emails, admin "Per E-Mail senden"

### File Management (Complete)
- Upload/download, folder management, share links

## Backlog
- P0: SMTP email fix (user checking mail.de credentials)
- P1: New device types (Messkoffer, Kirmeskiste fields)
- P2: Admin file size limits, hours-based live tracking
- P3: DSE890 live data integration

## Test Credentials
- Admin: admin@test.com / password
- Mitarbeiter: ma1@test.com / password
