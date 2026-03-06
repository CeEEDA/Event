# PRD - Eventenergie Monitoring & Management Portal

## Original Problem Statement
Comprehensive monitoring and management portal for Deep Sea Electronics (DSE) power generators.

## Tech Stack
Backend: FastAPI, Python, MongoDB, GridFS, qrcode | Frontend: React, Tailwind, Shadcn/UI, Recharts, Leaflet, qrcode.react | Auth: JWT (3 Rollen)

## Implemented Features

### Generator Monitoring (Complete)
- Dashboard with grid/map view, status filters, detail pages
- Auto-includes Stromerzeuger/Lichtmast devices, stats include virtual generators

### Device Management (Complete - 2026-03-06)
- CRUD, image upload (new + edit), copy with image + parts + docs
- QR-Code System: Unique 8-char device code per device, QR code generation, print button, search by code
- Ersatzteile: Fixed types + Sonderteil Freitext, Literzahl for Motoröl
- Dateiablage (PDFs) with authenticated download

### Service Plans (Complete - 2026-03-06)
- Entries sorted newest first
- Device image + Ersatzteile + Dateiablage in plan detail
- Auto-create plan on device click, search by device_code
- 6-section form, months + hours mandatory, 3-state buttons, drag & drop photos
- Collapsible history entries, technician read-only

### Email Service (SMTP auth pending)
### File Management (Complete)

## Key API Endpoints
- GET /api/devices/{id}/qrcode - QR code PNG
- GET /api/devices/search/by-code/{code} - Find device by code
- POST /api/devices with copy_from_device_id - Create + copy image/parts/docs

## Backlog
- P0: SMTP email fix
- P1: Messkoffer & Kirmeskiste device types
- P2: Admin file size limits
- P3: DSE890 live data integration

## Credentials
- Admin: admin@test.com / password | Mitarbeiter: ma1@test.com / password | Kunde: kunde@test.com / password
