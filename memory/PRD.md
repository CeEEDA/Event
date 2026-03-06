# PRD - Eventenergie Monitoring & Management Portal

## Original Problem Statement
Secure file exchange application, evolved into a comprehensive monitoring and management portal for Deep Sea Electronics (DSE) power generators.

## Product Requirements
1. **Generator Monitoring:** Real-time analytics dashboard with map view and detail pages. Data simulated, DSE890 integration planned.
2. **Device Management ("Geräteverwaltung"):** Fleet management with device images for visual identification. Full CRUD for admins, view/edit for employees.
3. **Service Planning ("Serviceplan"):** Maintenance schedules with operating hours tracking, checklists, photo uploads, remarks, and overdue alerts.
4. **User & Permissions:** Role-based system (Administrator, Mitarbeiter, Kunde) with feature-level and device-level access control.
5. **File Management:** Secure file sharing with folder management, sharing links, and per-user access.
6. **Email Service:** SMTP-based password reset emails via mail.de (SMTP auth pending user fix).

## Tech Stack
- **Backend:** FastAPI, Python, MongoDB, GridFS (images), Pydantic
- **Frontend:** React, Tailwind CSS, Shadcn/UI, Recharts (charts), Leaflet (maps)
- **Auth:** JWT with role-based access control
- **Email:** SMTP via smtp.mail.de (Port 587 STARTTLS)

## Core Architecture
```
/app/backend/
  server.py              - Main FastAPI app, auth, file management
  email_service.py       - SMTP email sending utility
  routes/
    generators.py        - Generator monitoring API
    devices.py           - Device management API (with images)
    serviceplan.py       - Service plan & maintenance API (with images)
/app/frontend/src/
  pages/
    HubPage.js                - Main navigation hub
    AdminPage.js              - User management + email reset
    DeviceManagementPage.js   - Device CRUD + image upload
    ServiceplanPage.js        - Service plans + maintenance history
    GeneratorDashboardPage.js - Monitoring dashboard
    GeneratorDetailPage.js    - Generator detail with charts
    ForgotPasswordPage.js     - Password reset via email
    DashboardPage.js          - File sharing dashboard
```

## What's Been Implemented

### Phase 1 - File Sharing (Complete)
- JWT authentication with 3 roles
- File/folder CRUD, upload/download
- Share links with password protection

### Phase 2 - Generator Monitoring (Complete)
- Simulated data with telemetry
- Dashboard with grid/list view, status filters, Leaflet map
- Detail page with Recharts graphs
- Permission-based access

### Phase 3 - Device Management (Complete)
- Full CRUD with role-based permissions
- Device image upload for visual identification (2026-03-06)
- Image shown in table and edit modal
- "Copy from existing" in create flow (preserves image)
- Document upload per device

### Phase 4 - Service Plans (Complete - 2026-03-06)
- Operating hours tracking (current_hours field)
- Maintenance intervals (hours AND months)
- Checklist with checkboxes for tasks
- Photo upload for technicians (mobile-friendly with camera capture)
- Remarks field for special incidents
- Maintenance history log (who, when, hours, tasks, photos, remarks)
- Auto-calculate next maintenance date
- Statistics (plans, bald fällig, überfällig)
- "Stunden bis Wartung" display

### Phase 5 - Email Service (In Progress - 2026-03-06)
- SMTP email utility implemented (smtp.mail.de)
- Password reset sends email with reset link
- Admin can send reset link per email
- ForgotPasswordPage no longer shows demo token
- **BLOCKER:** SMTP authentication failing - user checking credentials

### Cross-Feature Integrations (Complete)
- P1: Devices "Außer Betrieb" hidden from monitoring
- P4: Maintenance warnings in generator cards

## Prioritized Backlog

### P0 - Blocked
- SMTP email authentication fix (user checking mail.de settings)

### P1 - Next
- New Device Types support (Messkoffer, Kirmeskiste specific fields)

### P2 - Soon
- Admin-controlled file size limits per user
- Hours-based live maintenance tracking (connect operating_hours to intervals)

### P3 - Future
- DSE890 Live Data Integration
- Mobile-optimized views
- Office 365 email integration (user deferred)

## Known Limitations
- Generator data is SIMULATED (not from live DSE modules)
- SMTP email sending NOT WORKING (authentication failure at mail.de)
- File download uses workaround for preview sandbox

## Test Credentials
- Admin: admin@test.com / password
- Mitarbeiter: ma1@test.com / password
