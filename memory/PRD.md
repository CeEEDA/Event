# DSE Power Generator Portal – PRD

## Original Problem Statement
Comprehensive monitoring and management portal for DSE power generators with EpiRent ERP integration, energy monitoring, fleet management, and Kirmes billing system.

## Tech Stack
- **Backend**: FastAPI, Python, MongoDB (Motor), GridFS, paho-mqtt, httpx, bcrypt
- **Frontend**: React, Tailwind CSS, Shadcn/UI, Recharts, Leaflet/OpenStreetMap, open-location-code, jspdf, jspdf-autotable

## What's Been Implemented

### Kirmes Auth: Email+Password + Verification (2026-03-08)
- **Registration**: Schausteller register with full contact info + email + password
- **Email Verification**: 6-digit code sent via SMTP, must be verified before login
- **Login**: Email + password authentication (bcrypt hashed)
- **Security**: password_hash and verification_code never exposed in API responses
- **Legacy accounts**: Clear error message for accounts without password

### Kirmes-Verwaltung Phase 1 & 2 (2026-03-08)
- **Event Management** (`/kirmes`): CRUD for events with status flow (entwurf->freigegeben->aktiv->abgeschlossen->abgerechnet)
- **Standard-Preisliste**: Admin-configurable prices per connection type (Schuko, 16A, 32A, 63A, 125A, Festanschluss)
- **Schausteller-Portal** (`/kirmes/anmeldung`): Public registration + email/password login, event selection, signup with Platznummer/Anschluss/Zahlungsmittel
- **Event Detail** (`/kirmes/:id`): Info cards, price overview, signups table with CRUD
- **Exhibitor invitation system**: Email invitations with direct signup link
- **Purchase on Account**: Kauf auf Rechnung option for approved exhibitors
- **PDF Export**: Montageliste as client-side PDF
- **Schausteller Management**: Admin CRUD in user management panel
- **Schausteller Detail Page**: History of events attended

### GPS Data Reception Fix (2026-03-08)
- Updated MQTT topic prefix mappings for eventenergie group name

### Earlier Completed Work
- Generator monitoring, energy monitoring (Messkoffer), device management
- MQTT integration, GPS/maps, EpiRent ERP setup
- DSE remote control, service plans, user permissions, file management
- Auftragsverwaltung with orders list, detail, map, geocoding

## Key API Endpoints

### Kirmes Auth
- `POST /api/kirmes/public/register` - Register with email+password, sends verification code
- `POST /api/kirmes/public/verify-email` - Verify email with 6-digit code
- `GET /api/kirmes/public/resend-code?email=X` - Resend verification code
- `POST /api/kirmes/public/login` - Login with JSON {email, password}

### Kirmes Module
- `GET/PUT /api/kirmes/standard-prices` - Standard price list (staff/admin)
- `POST/GET/PUT/DELETE /api/kirmes/events` - Event CRUD (staff)
- `POST /api/kirmes/events/{id}/release` - Release event for signups
- `POST /api/kirmes/events/{id}/invite` - Send email invitations
- `GET /api/kirmes/public/events` - Released events (public)
- `POST /api/kirmes/public/signup` - Event signup (public)
- `GET /api/kirmes/schausteller` - Schausteller list (staff)
- `GET /api/kirmes/schausteller/{id}` - Schausteller detail with signups
- `PUT/DELETE /api/kirmes/schausteller/{id}` - Update/delete schausteller
- `GET /api/kirmes/connection-types` - Connection types (public)
- `PUT /api/kirmes/signups/{id}/kwh` - Update meter readings

### DB Collections (Kirmes)
- `kirmes_events`: {id, name, location, start_date, end_date, dispo_start, dispo_end, status, prices[], kwh_price, handling_surcharge, notes, created_by}
- `kirmes_standard_prices`: {id, connection_type, price, avg_kwh} + {type: "global", kwh_price, handling_surcharge}
- `kirmes_schausteller`: {id, firma, name, strasse, plz, ort, steuernummer, email, password_hash, telefon, rechnungs_email, email_verified, verification_code, kauf_auf_rechnung}
- `kirmes_signups`: {id, event_id, schausteller_id, platznummer, fahrgeschaeft, connection_type, price, payment_method, payment_status, deposit_amount, meter_id, meter_start, meter_end, kwh_used, final_amount}

## Backlog

### P0 (Next)
- EMU Meter Data Integration (live/historical consumption in event detail)
- "Abrechnung" (Billing) button logic with ZUGFeRD e-invoices
- Stripe integration for deposit reservation at signup

### P1
- Billing history on Schausteller detail page
- Self-hosted MQTT Broker (Mosquitto)

### P2
- Admin file size limits
- MQTT Broker URL -> .env refactoring

## Test Credentials
- Admin: admin@test.com / password
- Mitarbeiter: ma1@test.com / password
- Test Schausteller: test-verify@example.com / test1234 (verified)
- Legacy Schausteller: hans@test.de (no password, not verified)
