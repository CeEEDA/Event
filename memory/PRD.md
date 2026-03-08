# DSE Power Generator Portal – PRD

## Original Problem Statement
Comprehensive monitoring and management portal for DSE power generators with EpiRent ERP integration, energy monitoring, fleet management, and Kirmes billing system.

## Tech Stack
- **Backend**: FastAPI, Python, MongoDB (Motor), GridFS, paho-mqtt, httpx
- **Frontend**: React, Tailwind CSS, Shadcn/UI, Recharts, Leaflet/OpenStreetMap, open-location-code

## What's Been Implemented

### Kirmes-Verwaltung Phase 1 & 2 (2026-03-08)
- **Event Management** (`/kirmes`): CRUD for events with status flow (entwurf→freigegeben→aktiv→abgeschlossen→abgerechnet)
- **Standard-Preisliste**: Admin-configurable prices per connection type (16A, 32A, 63A, 125A, Festanschluss)
- **Schausteller-Portal** (`/kirmes/anmeldung`): Public registration + email login, event selection, signup with Platznummer/Anschluss/Zahlungsmittel
- **Event Detail** (`/kirmes/:id`): Info cards, price overview, signups table with CRUD
- Hub button for "Kirmes-Verwaltung" added
- All 26 backend+frontend tests passed

### GPS Data Reception Fix (2026-03-08)
- Updated MQTT topic prefix mappings for eventenergie group name
- GPS updates every ~60s, telemetry every ~10s
- Status messages optimized: update online status only

### Auftragsverwaltung (Earlier)
- Orders List, Order Detail with map, geocoding, radius search
- Manual asset placement with Plus Codes
- Deployment History CRUD

### Earlier Completed Work
- Generator monitoring, energy monitoring (Messkoffer), device management
- MQTT integration, GPS/maps, EpiRent ERP setup
- DSE remote control, service plans, user permissions, file management

## Key API Endpoints

### Kirmes Module
- `GET/PUT /api/kirmes/standard-prices` - Standard price list (staff/admin)
- `POST/GET/PUT/DELETE /api/kirmes/events` - Event CRUD (staff)
- `POST /api/kirmes/events/{id}/release` - Release event for signups
- `POST /api/kirmes/public/register` - Public schausteller registration
- `POST /api/kirmes/public/login?email=x` - Public schausteller login
- `GET /api/kirmes/public/events` - Released events (public)
- `POST /api/kirmes/public/signup` - Event signup (public)
- `GET /api/kirmes/schausteller` - Schausteller list (staff)
- `GET /api/kirmes/connection-types` - Connection types (public)

### DB Collections (Kirmes)
- `kirmes_events`: {id, name, location, start_date, end_date, status, prices[], notes, created_by}
- `kirmes_standard_prices`: {id, connection_type, price, updated_at}
- `kirmes_schausteller`: {id, firma, name, strasse, plz, ort, steuernummer, email, telefon, rechnungs_email}
- `kirmes_signups`: {id, event_id, schausteller_id, platznummer, connection_type, price, payment_method, payment_status, deposit_amount, meter_id}

## Backlog

### P0 (Next)
- Stripe integration for deposit reservation at signup
- Kirmeskiste device + QR code generation + meter↔schausteller linking
- "Abrechnen" button with ZUGFeRD e-invoices

### P1
- Einsatzhistorie: Auto-assign generators to orders via GPS
- Self-hosted MQTT Broker (Mosquitto)

### P2
- Admin file size limits
- MQTT Broker URL → .env refactoring

## Test Credentials
- Admin: admin@test.com / password
- Mitarbeiter: ma1@test.com / password
- Test Schausteller: hans@test.de
