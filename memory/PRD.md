# PRD - Eventenergie Monitoring & Management Portal

## Original Problem Statement
Comprehensive monitoring and management portal for Deep Sea Electronics (DSE) power generators.

## Tech Stack
Backend: FastAPI, Python, MongoDB, GridFS | Frontend: React, Tailwind, Shadcn/UI, Recharts, Leaflet | Auth: JWT (3 Rollen)

## Implemented Features

### Generator Monitoring (Complete)
- Dashboard with grid/map view, status filters, detail pages with charts
- Auto-includes Stromerzeuger/Lichtmast devices from device management
- Stats now correctly include virtual generators from devices (fixed 2026-03-06)
- Maintenance warnings (yellow badge) when < 1 month or < 50 hours
- Ausser Betrieb devices excluded

### Device Management (Complete - 2026-03-06)
- CRUD with role-based permissions, device image upload
- Fields: Erworben am, Portal-Verknüpfung
- Dateiablage (Handbücher, Schaltpläne, Motornummern als PDF)
- "Copy from existing" with document + parts copy option
- **NEW: Ersatzteile (Parts) management per device** (2026-03-06)
  - Predefined types: Kraftstofffilter, Ölfilter, Luftfilter, Keilriemen, Kühlmittel, Motoröl, Zündkerze, Batterie, Dichtung, Sicherung
  - Custom free-text type option
  - Part number, liters (for oil/coolant), notes per part
  - Parts copied when device is duplicated

### Service Plans (Complete - 2026-03-06)
- Professional 6-section form: Mechanische/Elektrische Prüfung (3-state buttons), Messwerte, Lasttest, ATS, Diagnose
- **UPDATED: Both months AND hours mandatory for next maintenance** (2026-03-06)
- **UPDATED: ATS and Diagnosis sections use 3-state buttons** (2026-03-06)
- **UPDATED: Load test column renamed "Messwert" -> "Lasttest"** (2026-03-06)
- **UPDATED: Drag & drop support for photo uploads** (2026-03-06)
- **FIX: Auto-navigation to plan detail after creating plan** (2026-03-06)
- Technician auto-filled from user, hours tracking
- Clickable status filter cards: Einsatzbereit/Bald fällig/Überfällig/Gesamt
- Photo upload, remarks, expandable history with full documentation

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
- GET/POST /api/devices/{id}/parts - Parts CRUD
- PUT/DELETE /api/devices/parts/{partId} - Part update/delete
- POST /api/serviceplan/{planId}/entries - Create maintenance entry (accepts next_maintenance_months + next_maintenance_hours)
- GET /api/generators/stats/overview - Stats including virtual generators

## Credentials
- Admin: admin@test.com / password | Mitarbeiter: anna.weber@test.com / password
