# DSE Power Generator Portal – PRD

## Original Problem Statement
Comprehensive monitoring and management portal for DSE power generators with EpiRent ERP integration, energy monitoring, fleet management, and Kirmes billing system.

## Tech Stack
- **Backend**: FastAPI, Python, MongoDB (Motor), GridFS, paho-mqtt, httpx, bcrypt, reportlab, pdfrw
- **Frontend**: React, Tailwind CSS, Shadcn/UI, Recharts, Leaflet/OpenStreetMap, open-location-code, jspdf, jspdf-autotable

## What's Been Implemented

### Kirmes: Abrechnungsmodul mit Rechnungsstellung (2026-03-08)
- **Invoice Generation**: Server-side PDF with company letterhead PDF as background (assets/briefpapier.pdf)
- **Invoice Number**: Auto-incrementing R{YY}-K-{NNNN} format
- **Billing Calculation**: Anschlussgebühr + Stromverbrauch (kWh) + Handlingaufschlag + 19% MwSt
- **Single/Batch**: Generate invoice per signup or batch all signups in an event
- **PDF Download**: Letterhead from uploaded PDF file, no hardcoded company data
- **Email Sending**: Invoice PDF als Anhang per E-Mail versenden
- **Invoice Search**: Searchable in Kirmes-Verwaltung by number, company, event name
- **Status**: payment_status changes to "abgerechnet" after invoice generation

### Kirmes: Auth + Admin Features (2026-03-08)
- Email+Password registration with 6-digit verification code
- Admin password management for Schausteller
- Booking confirmation email after signup
- "Auf Rechnung" only with admin approval (kauf_auf_rechnung flag)

### Kirmes-Verwaltung (2026-03-08)
- Event Management with status flow, Standard-Preisliste, Public Portal
- Event Detail with signups, kWh fields, PDF Montageliste
- Exhibitor invitation, Schausteller Management + Detail Page

### Earlier Completed Work
- Generator monitoring, energy monitoring (Messkoffer), device management
- MQTT integration, GPS/maps, EpiRent ERP, DSE remote control
- Service plans, user permissions, file management, Auftragsverwaltung

## Key API Endpoints

### Kirmes Invoices
- `POST /api/kirmes/signups/{id}/invoice` - Generate for single signup
- `POST /api/kirmes/events/{id}/generate-invoices` - Batch generate all
- `GET /api/kirmes/invoices` - List/search (?search=, ?event_id=)
- `GET /api/kirmes/invoices/{id}/pdf` - Download PDF with letterhead
- `POST /api/kirmes/invoices/{id}/send` - Send via email

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
