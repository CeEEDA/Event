# PRD - Eventenergie Monitoring & Management Portal

## Original Problem Statement
Secure file exchange application, evolved into a comprehensive monitoring and management portal for Deep Sea Electronics (DSE) power generators.

## Product Requirements
1. **Generator Monitoring:** Real-time analytics dashboard (status, load, temperature, etc.) with map view and detail pages. Data simulated, DSE890 integration planned.
2. **Device Management ("Geräteverwaltung"):** Fleet management for generators, light masts, etc. Full CRUD for admins, view/edit for employees.
3. **Service Planning ("Serviceplan"):** Maintenance schedules with history, intervals, task checklists, and overdue alerts.
4. **User & Permissions:** Role-based system (Administrator, Mitarbeiter, Kunde) with feature-level and device-level access control.
5. **File Management:** Secure file sharing with folder management, sharing links, and per-user access.

## User Roles
- **Administrator:** Full access to all features
- **Mitarbeiter (Employee):** Access to device management (view/edit), service plans, monitoring (if assigned)
- **Kunde (Customer):** File sharing access, monitoring (if assigned specific generators)

## Tech Stack
- **Backend:** FastAPI, Python, MongoDB, Pydantic
- **Frontend:** React, Tailwind CSS, Shadcn/UI, Recharts (charts), Leaflet (maps)
- **Auth:** JWT with role-based access control

## Core Architecture
```
/app/backend/
  server.py          - Main FastAPI app, auth, file management
  routes/
    generators.py    - Generator monitoring API (with P1 & P4)
    devices.py       - Device management API
    serviceplan.py   - Service plan & maintenance API
/app/frontend/src/
  pages/
    HubPage.js       - Main navigation hub (role-based)
    AdminPage.js     - User management (admin only)
    DeviceManagementPage.js - Device CRUD (P2: copy from existing)
    ServiceplanPage.js      - Service plans & maintenance history
    GeneratorDashboardPage.js - Monitoring dashboard (P4: warnings)
    GeneratorDetailPage.js  - Generator detail with charts
    DashboardPage.js        - File sharing dashboard
```

## What's Been Implemented

### Phase 1 - File Sharing (Complete)
- JWT authentication with 3 roles
- File/folder CRUD, upload/download
- Share links with password protection
- Admin user management with app permissions

### Phase 2 - Generator Monitoring (Complete)
- Simulated generator data with telemetry
- Dashboard with grid/list view and status filters
- Leaflet map with location markers
- Detail page with Recharts graphs
- Permission-based generator access

### Phase 3 - Device Management (Complete)
- Full CRUD for admin, view/status change for employees
- Device types: Stromerzeuger, Lichtmast, Messkoffer, Kirmeskiste
- Document upload per device
- "Copy from existing" in create flow (P2 - 2026-03-06)

### Phase 4 - Service Plans (Complete - 2026-03-06)
- Service plan CRUD per device (interval hours + months)
- Maintenance history log (who, when, hours, tasks)
- Default task checklists
- Auto-calculate next maintenance date
- Statistics (plans, bald fällig, überfällig)

### Cross-Feature Integrations (Complete - 2026-03-06)
- P1: Devices "Außer Betrieb" hidden from monitoring (serial_number cross-reference)
- P4: Maintenance warnings in generator cards (wrench badge with days)

## Prioritized Backlog

### P1 - Next
- Email Service for Password Reset (Office 365 - user deferred)

### P2 - Soon
- New Device Types support (Messkoffer, Kirmeskiste specific fields)
- Admin-controlled file size limits per user

### P3 - Future
- DSE890 Live Data Integration
- Hours-based maintenance tracking (connect operating_hours to service interval)
- Mobile-optimized views

## Known Limitations
- Generator data is SIMULATED (not from live DSE modules)
- Password reset cannot send emails (no email service configured)
- File download uses workaround for preview sandbox

## Test Credentials
- Admin: admin@test.com / password
- Mitarbeiter: ma1@test.com / password
- Kunde: kunde@test.com / password
