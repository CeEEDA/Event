# PRD - Eventenergie Monitoring & Management Portal

## Original Problem Statement
Comprehensive monitoring and management portal for Deep Sea Electronics (DSE) power generators.

## Tech Stack
Backend: FastAPI, Python, MongoDB, GridFS | Frontend: React, Tailwind, Shadcn/UI, Recharts, Leaflet | Auth: JWT (3 Rollen)

## Implemented Features

### Generator Monitoring (Complete)
- Dashboard with grid/map view, status filters, detail pages with charts
- Auto-includes Stromerzeuger/Lichtmast devices from device management
- Stats correctly include virtual generators from devices (fixed 2026-03-06)
- Maintenance warnings when < 1 month or < 50 hours
- Map view filters out generators without coordinates

### Device Management (Complete - 2026-03-06)
- CRUD with role-based permissions, device image upload
- **BUG FIX: ObjectId serialization in update_device** (2026-03-06) - image_gridfs_id now properly converted to string
- Fields: Erworben am, Portal-Verknüpfung
- Dateiablage (Handbücher, Schaltpläne, Motornummern als PDF)
- "Copy from existing" with document + parts copy option
- **Ersatzteile (Parts) management per device** (2026-03-06)
  - Fixed types: Kraftstoffvorfilter, Kraftstofffilter, Ölfilter, Keilriemen, Umlenkrollen, Wasserpumpe, Luftfilter, Motoröl
  - Motoröl: extra Literzahl field
  - Sonderteil (Freitext) option for custom parts
  - Parts copied when device is duplicated

### Service Plans (Complete - 2026-03-06)
- Professional 6-section form: Mechanische/Elektrische Prüfung (3-state buttons), Messwerte, Lasttest, ATS, Diagnose
- Both months AND hours mandatory for next maintenance
- ATS and Diagnosis sections use 3-state buttons (durchgeführt/nicht durchgeführt/nicht vorhanden)
- Load test column: "Lasttest" (renamed from "Messwert")
- Drag & drop photo uploads
- Auto-navigation to plan detail after creating plan
- Technician auto-filled (read-only) from logged-in user
- Row click opens plan detail directly (no separate Details button)
- Clickable status filter cards: Einsatzbereit/Bald fällig/Überfällig/Gesamt

### Email Service (Implemented, SMTP auth pending)
- SSL Port 465 via smtp.mail.de, password reset + admin send

### File Management (Complete)
- Upload/download, folders, share links

## Backlog
- P0: SMTP email fix (user checking mail.de credentials)
- P1: New device types (Messkoffer, Kirmeskiste) full support
- P2: Admin file size limits
- P3: DSE890 live data integration

## Key API Endpoints
- PUT /api/devices/{id} - Device update (ObjectId fix applied)
- GET/POST /api/devices/{id}/parts - Parts CRUD
- PUT/DELETE /api/devices/parts/{partId} - Part update/delete
- GET /api/devices/parts/types - Part type list
- POST /api/serviceplan/{planId}/entries - Create maintenance entry (next_maintenance_months + next_maintenance_hours)
- GET /api/generators/stats/overview - Stats including virtual generators

## Credentials
- Admin: admin@test.com / password
- Mitarbeiter: ma1@test.com / password
- Kunde: kunde@test.com / password
