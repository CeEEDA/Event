# DSE Power Generator Portal – PRD

## Original Problem Statement
Comprehensive monitoring and management portal for DSE power generators with EpiRent ERP integration, energy monitoring, fleet management, and Kirmes billing system.

## Tech Stack
- **Backend**: FastAPI, Python, MongoDB (Motor), GridFS, paho-mqtt, httpx, bcrypt, reportlab
- **Frontend**: React, Tailwind CSS, Shadcn/UI, Recharts, Leaflet/OpenStreetMap, open-location-code, jspdf, jspdf-autotable

## What's Been Implemented

### Kirmes: Abrechnungsmodul mit Rechnungsstellung (2026-03-08)
- **Invoice Generation**: Server-side PDF generation with reportlab and custom company letterhead
- **Invoice Number**: Auto-incrementing R{YY}-K-{NNNN} format (e.g., R26-K-0001)
- **Billing Calculation**: Anschlussgebühr + Stromverbrauch (kWh) + Handlingaufschlag + 19% MwSt
- **Single/Batch**: Generate invoice per signup or batch all signups in an event
- **PDF Download**: Full letterhead with company data (Eventenergie Deutschland GmbH & Co. KG)
- **Email Sending**: Invoice PDF als Anhang per E-Mail versenden
- **Invoice Search**: Searchable in Kirmes-Verwaltung by number, company, event name
- **Endpoints**: POST/GET /api/kirmes/invoices, /invoices/{id}/pdf, /invoices/{id}/send

### Kirmes: Booking Confirmation + Admin Password (2026-03-08)
- Booking confirmation email after successful signup
- Admin password management for Schausteller
- "Auf Rechnung" only with admin approval

### Kirmes Auth: Email+Password + Verification (2026-03-08)
- Registration with email + password + email verification (6-digit code)
- Login with bcrypt hashed password

### Kirmes-Verwaltung Phase 1 & 2 (2026-03-08)
- Event Management, Standard-Preisliste, Public Portal
- Event Detail, Exhibitor invitation, Purchase on Account
- PDF Montageliste, Schausteller Management, History

### Earlier Completed Work
- Generator monitoring, energy monitoring (Messkoffer), device management
- MQTT integration, GPS/maps, EpiRent ERP, DSE remote control
- Service plans, user permissions, file management, Auftragsverwaltung

## Key API Endpoints

### Kirmes Invoices
- `POST /api/kirmes/signups/{id}/invoice` - Generate invoice for signup
- `POST /api/kirmes/events/{id}/generate-invoices` - Batch generate all
- `GET /api/kirmes/invoices` - List/search invoices (?search=, ?event_id=)
- `GET /api/kirmes/invoices/{id}` - Invoice detail
- `GET /api/kirmes/invoices/{id}/pdf` - Download PDF
- `POST /api/kirmes/invoices/{id}/send` - Send via email

### DB Collections
- `kirmes_invoices`: {id, invoice_number, signup_id, event_id, event_name, schausteller_id, schausteller_firma, schausteller_name, schausteller_email, invoice_date, line_items[], netto, mwst_rate, mwst_amount, brutto, status, schausteller{}, event{}, created_at, created_by, sent_at, sent_to}

## Company Letterhead Data
- Eventenergie Deutschland GmbH & Co. KG
- Thyssenstraße 10, 56626 Andernach
- Tel: +49 (0) 2632 30921-0, Hotline: +49 (0) 800 POWER24
- Amtsgericht Koblenz: HRA 22723, Ust.-ID: DE 333489815
- Geschäftsführung: Christian Ecker
- IBAN: DE86 7413 1000 0002 6260 00, BIC: TEKRDE71

## Backlog

### P0 (Next)
- EMU Meter Data Integration
- Stripe integration for deposit reservation

### P1
- Billing history on Schausteller detail page
- Self-hosted MQTT Broker (Mosquitto)
- ZUGFeRD-compliant invoices

### P2
- Admin file size limits
- MQTT Broker URL -> .env refactoring

## Test Credentials
- Admin: admin@test.com / password
- Mitarbeiter: ma1@test.com / password
- Test Schausteller: test-verify@example.com / test1234
