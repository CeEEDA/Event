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
- Maintenance warnings when < 1 month or < 50 hours

### Device Management (Complete - 2026-03-06)
- CRUD with role-based permissions, device image upload
- ObjectId serialization bug fixed in update_device
- Ersatzteile (Parts) section shown at TOP of device modal (after image)
  - Fixed types: Kraftstoffvorfilter, Kraftstofffilter, Ölfilter, Keilriemen, Umlenkrollen, Wasserpumpe, Luftfilter, Motoröl (+Literzahl)
  - Sonderteil (Freitext) option for custom parts
  - White background add-part form
  - Parts copied when device is duplicated
- Dateiablage (PDFs), Erworben am, Portal-Verknüpfung
- Copy from existing device with documents + parts

### Service Plans (Complete - 2026-03-06)
- 6-section maintenance form: Mechanische/Elektrische Prüfung, Messwerte, Lasttest, ATS, Diagnose
- Both months AND hours mandatory for next maintenance
- ATS and Diagnosis: 3-state buttons (durchgeführt/nicht durchgeführt/nicht vorhanden)
- "Lasttest" column label (renamed from "Messwert")
- Drag & drop photo uploads
- Technician read-only (auto-filled from user)
- Collapsible maintenance history entries (click to expand/collapse)
- Expanded entries show ALL 6 sections with 3-state status badges
- Auto-navigation to plan detail after creating plan
- Clickable status filter cards

### Email Service (SMTP auth pending - user checking credentials)
### File Management (Complete)

## Backlog
- P0: SMTP email fix (user checking mail.de credentials)
- P1: Messkoffer & Kirmeskiste device types full support
- P2: Admin file size limits
- P3: DSE890 live data integration

## Credentials
- Admin: admin@test.com / password
- Mitarbeiter: ma1@test.com / password
- Kunde: kunde@test.com / password
