# PRD - Eventenergie Monitoring & Management Portal

## Original Problem Statement
Comprehensive monitoring and management portal for Deep Sea Electronics (DSE) power generators.

## Tech Stack
Backend: FastAPI, Python, MongoDB, GridFS | Frontend: React, Tailwind, Shadcn/UI, Recharts, Leaflet | Auth: JWT (3 Rollen)

## Implemented Features

### Generator Monitoring (Complete)
- Dashboard with grid/map view, status filters, detail pages with charts
- Auto-includes Stromerzeuger/Lichtmast devices, stats include virtual generators

### Device Management (Complete - 2026-03-06)
- CRUD, image upload (new + edit), device copy with image + parts + documents
- Ersatzteile: Kraftstoffvorfilter, Kraftstofffilter, Ölfilter, Keilriemen, Umlenkrollen, Wasserpumpe, Luftfilter, Motoröl (+Literzahl), Sonderteil Freitext
- Dateiablage (PDFs) with authenticated download endpoint

### Service Plans (Complete - 2026-03-06)
- Device image shown in plan detail header
- Ersatzteile + Dateiablage with auth-based download in plan detail
- "Gesamt" filter card now clickable (resets filter)
- Auto-create plan on device click (no modal)
- 6-section form, months + hours mandatory, 3-state buttons, drag & drop photos
- Collapsible history entries, technician read-only

### Email Service (SMTP auth pending)
### File Management (Complete)

## Backlog
- P0: SMTP email fix
- P1: Messkoffer & Kirmeskiste device types
- P2: Admin file size limits
- P3: DSE890 live data integration

## Credentials
- Admin: admin@test.com / password | Mitarbeiter: ma1@test.com / password | Kunde: kunde@test.com / password
