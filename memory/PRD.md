# DSE Power Generator Portal – PRD

## Original Problem Statement
Comprehensive monitoring and management portal for DSE power generators with EpiRent ERP integration, energy monitoring, fleet management, and Kirmes billing system.

## Tech Stack
- **Backend**: FastAPI, Python, MongoDB (Motor), GridFS, paho-mqtt, httpx, bcrypt, reportlab, pdfrw, factur-x
- **Frontend**: React, Tailwind CSS, Shadcn/UI, Recharts, Leaflet/OpenStreetMap, open-location-code, jspdf, jspdf-autotable

## What's Been Implemented

### ZUGFeRD E-Rechnungen (2026-03-08)
- PDF invoices now include embedded factur-x.xml (ZUGFeRD 2.0 / Factur-X Basic profile)
- XSD-validated XML with seller/buyer info, line items, tax, and totals
- Uses `factur-x` Python library for PDF/A-3 embedding
- Fallback: returns normal PDF if XML validation fails

### Kirmes: EMU Meter Data Integration (2026-03-08)
- Link/unlink EMU meters to signups, live data display, power chart
- API: GET /api/kirmes/emu-meters, PUT/DELETE /api/kirmes/signups/{id}/link-meter, GET /api/kirmes/signups/{id}/meter-data

### Kirmes: Abrechnungsmodul (2026-03-08)
- Invoice generation with letterhead, auto-incrementing numbers, billing calculation
- Batch billing, PDF download, email sending, invoice search
- Rechnungen auf Schausteller-Detailseite mit Download + erneuter Versand

### Kirmes: Auth + Admin Features
- Email+Password registration with verification, admin password management
- Booking confirmation email, conditional "Auf Rechnung"

### Earlier Completed Work
- Generator/energy monitoring, MQTT, GPS/maps, EpiRent ERP, DSE remote control
- Service plans, user permissions, file management, Auftragsverwaltung

## Backlog

### P0 (Next)
- Stripe integration for deposit reservation

### P1
- Self-hosted MQTT Broker (Mosquitto)
- SMTP provider upgrade (mail.de daily limit reached)

### P2
- MQTT Broker URL -> .env refactoring
- Admin file size limits

## Test Credentials
- Admin: admin@test.com / password
- Mitarbeiter: ma1@test.com / password
