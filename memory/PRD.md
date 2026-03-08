# DSE Power Generator Portal – PRD

## Original Problem Statement
Comprehensive monitoring and management portal for DSE power generators with EpiRent ERP integration, energy monitoring, fleet management, and Kirmes billing system.

## Tech Stack
- **Backend**: FastAPI, Python, MongoDB (Motor), GridFS, paho-mqtt, httpx, bcrypt
- **Frontend**: React, Tailwind CSS, Shadcn/UI, Recharts, Leaflet/OpenStreetMap, open-location-code, jspdf, jspdf-autotable

## What's Been Implemented

### Kirmes: Booking Confirmation Email + Admin Password Management (2026-03-08)
- **Booking Confirmation Email**: Schausteller receive detailed HTML email after successful event signup (event name, location, dates, Platznummer, Fahrgeschäft, connection type, price, payment method)
- **Admin Password Management**: Staff/Admins can set passwords for Schausteller directly in the edit modal. Sets password_hash + marks email as verified.
- **Endpoint**: `POST /api/kirmes/schausteller/{id}/set-password`

### Kirmes Auth: Email+Password + Verification (2026-03-08)
- **Registration**: Schausteller register with full contact info + email + password
- **Email Verification**: 6-digit code sent via SMTP, must be verified before login
- **Login**: Email + password authentication (bcrypt hashed)
- **Security**: password_hash and verification_code never exposed in API responses

### Kirmes-Verwaltung Phase 1 & 2 (2026-03-08)
- **Event Management** (`/kirmes`): CRUD with status flow
- **Standard-Preisliste**: Per connection type pricing with avg kWh and deposit calculation
- **Schausteller-Portal** (`/kirmes/anmeldung`): Public registration + login, event selection, signup
- **Event Detail** (`/kirmes/:id`): Info cards, prices, signups table, kWh fields, PDF export
- **Exhibitor invitation, Purchase on Account, Schausteller Management, Detail Page**

### Earlier Completed Work
- Generator monitoring, energy monitoring (Messkoffer), device management
- MQTT integration, GPS/maps, EpiRent ERP, DSE remote control
- Service plans, user permissions, file management, Auftragsverwaltung

## Key API Endpoints

### Kirmes Auth
- `POST /api/kirmes/public/register` - Register with email+password
- `POST /api/kirmes/public/verify-email` - Verify email with code
- `GET /api/kirmes/public/resend-code?email=X` - Resend code
- `POST /api/kirmes/public/login` - Login with {email, password}

### Kirmes Admin
- `POST /api/kirmes/schausteller/{id}/set-password` - Admin sets Schausteller password
- `GET/PUT/DELETE /api/kirmes/schausteller/{id}` - Schausteller CRUD

### Kirmes Events
- `POST/GET/PUT/DELETE /api/kirmes/events` - Event CRUD
- `POST /api/kirmes/events/{id}/release` - Release for signups
- `POST /api/kirmes/events/{id}/invite` - Email invitations
- `GET /api/kirmes/public/events` - Public event list
- `POST /api/kirmes/public/signup` - Event signup (sends confirmation email)

## DB Collections (Kirmes)
- `kirmes_schausteller`: {id, firma, name, strasse, plz, ort, steuernummer, email, password_hash, telefon, rechnungs_email, email_verified, verification_code, kauf_auf_rechnung}
- `kirmes_events`: {id, name, location, start_date, end_date, dispo_start, dispo_end, status, prices[], kwh_price, handling_surcharge}
- `kirmes_signups`: {id, event_id, schausteller_id, platznummer, fahrgeschaeft, connection_type, price, payment_method, payment_status, deposit_amount, meter_id, kwh_einbau, kwh_ausbau, kwh_used}

## Backlog

### P0 (Next)
- EMU Meter Data Integration
- "Abrechnung" button logic with ZUGFeRD e-invoices
- Stripe integration for deposit reservation

### P1
- Billing history on Schausteller detail page
- Self-hosted MQTT Broker (Mosquitto)

### P2
- Admin file size limits
- MQTT Broker URL -> .env refactoring

## Test Credentials
- Admin: admin@test.com / password
- Mitarbeiter: ma1@test.com / password
- Test Schausteller: test-verify@example.com / test1234
