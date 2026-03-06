# PRD - Eventenergie Monitoring & Management Portal

## Original Problem Statement
Comprehensive monitoring and management portal for Deep Sea Electronics (DSE) power generators.

## Tech Stack
Backend: FastAPI, Python, MongoDB, GridFS | Frontend: React, Tailwind, Shadcn/UI, Recharts, Leaflet | Auth: JWT (3 Rollen)

## Implemented Features

### Generator Monitoring (Complete)
- Dashboard with grid/map view, status filters, detail pages with charts
- Auto-includes Stromerzeuger/Lichtmast devices from device management
- Stats correctly include virtual generators from devices

### Device Management (Complete - 2026-03-06)
- CRUD with role-based permissions, device image upload (also for new devices)
- Ersatzteile (Parts): Kraftstoffvorfilter, Kraftstofffilter, Ölfilter, Keilriemen, Umlenkrollen, Wasserpumpe, Luftfilter, Motoröl (+Literzahl), Sonderteil Freitext
- Parts shown at top of device modal, white background, copied on device duplication
- Dateiablage (PDFs) with download endpoint
- Copy from existing device with documents + parts

### Service Plans (Complete - 2026-03-06)
- Ersatzteile + Dateiablage shown in plan detail view (fetched from device)
- "Plan bearbeiten" button removed
- Auto-create plan on device click (no separate modal)
- 6-section maintenance form, both months AND hours mandatory
- 3-state buttons for ATS/Diagnosis, drag & drop photos
- Technician read-only, collapsible history entries
- Clickable status filter cards

### Email Service (SMTP auth pending - user checking credentials)
### File Management (Complete)

## Backlog
- P0: SMTP email fix
- P1: Messkoffer & Kirmeskiste device types full support
- P2: Admin file size limits
- P3: DSE890 live data integration

## Key API Endpoints
- GET /api/devices/{id}/documents/{docId}/download - Document download (new)
- GET/POST /api/devices/{id}/parts - Parts CRUD
- POST /api/serviceplan/{planId}/entries - Maintenance entry (months + hours)
- GET /api/generators/stats/overview - Stats incl. virtual generators

## Credentials
- Admin: admin@test.com / password | Mitarbeiter: ma1@test.com / password | Kunde: kunde@test.com / password
