# PRD - Eventenergie Monitoring & Management Portal

## Original Problem Statement
Comprehensive monitoring and management portal for Deep Sea Electronics (DSE) power generators.

## Tech Stack
Backend: FastAPI, Python, MongoDB, GridFS | Frontend: React, Tailwind, Shadcn/UI, Recharts, Leaflet | Auth: JWT (3 Rollen)

## Implemented Features

### Generator Monitoring (Complete)
- Dashboard with grid/list/map view, status filters, detail pages with charts
- Auto-includes Stromerzeuger/Lichtmast devices from device management
- Maintenance warnings (yellow badge) when < 1 month or < 50 hours
- Ausser Betrieb devices excluded

### Device Management (Complete - 2026-03-06)
- CRUD with role-based permissions, device image upload
- Fields: Erworben am, Portal-Verknüpfung
- Dateiablage (Handbücher, Schaltpläne, Motornummern als PDF)
- "Copy from existing" with document copy option
- Wartung/GPS sections removed (maintenance in Serviceplan)

### Service Plans (Complete - 2026-03-06)
- Professional 6-section form: Mechanische/Elektrische Prüfung (3-state buttons), Messwerte, Lasttest, ATS, Diagnose
- Technician auto-filled from user, hours tracking, next maintenance calc (months OR hours)
- Clickable status filter cards: Einsatzbereit/Bald fällig/Überfällig/Gesamt
- Photo upload, remarks, expandable history with full documentation

### Email Service (Implemented, SMTP auth pending)
- SSL Port 465 via smtp.mail.de, password reset + admin send

### File Management (Complete)
- Upload/download, folders, share links

## Backlog
- P0: SMTP email fix (user checking mail.de credentials)
- P1: New device types (Messkoffer, Kirmeskiste)
- P2: Admin file size limits
- P3: DSE890 live data integration

## Credentials
- Admin: admin@test.com / password | Mitarbeiter: ma1@test.com / password
