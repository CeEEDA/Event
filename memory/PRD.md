# DSE Power Generator Portal – PRD

## Original Problem Statement
A comprehensive monitoring and management portal for Deep Sea Electronics (DSE) power generators with EpiRent ERP integration, energy monitoring, and fleet management.

## User Personas
- **Administrator**: Full CRUD access to devices, users, service plans, MQTT config, energy monitoring config.
- **Mitarbeiter (Employee)**: Can view devices, update status/notes, create maintenance entries.
- **Kunde (Customer)**: Limited view access with time-based data restrictions.

## Tech Stack
- **Backend**: FastAPI, Python, MongoDB (Motor), GridFS, paho-mqtt, httpx
- **Frontend**: React, Tailwind CSS, Shadcn/UI, Recharts, Leaflet/OpenStreetMap
- **Auth**: JWT with role-based access

## Architecture
```
/app/backend/routes/
├── generators.py         # Generator CRUD + telemetry
├── devices.py            # Device CRUD
├── serviceplan.py        # Service plans
├── mqtt_config.py        # MQTT config
├── energy_monitoring.py  # Messkoffer
├── admin_settings.py     # Third-party integrations
└── orders.py             # EpiRent orders + deployments

/app/frontend/src/pages/
├── OrdersPage.js         # Order list with filters
├── OrderDetailPage.js    # Order detail with map + generators
├── GeneratorDetailPage.js # Generator detail + Einsatzhistorie
└── ... (other pages)
```

## What's Been Implemented

### Auftragsverwaltung (Order Management) - 2026-03-08
- **Orders List**: Filterable table with date range, search, status dropdown (default: Bestätigt)
- **Order Detail Page**: Click on row opens `/orders/:pk` with:
  - Info cards: Event/Projekt, Kunde, Lieferanschrift
  - Map centered on geocoded delivery address (via Nominatim OSM)
  - Configurable radius per order (default 5km, saved to MongoDB)
  - Generators within radius shown on map + list panel
  - Haversine distance calculation for GPS matching
- **Deployment History (Einsatzhistorie)**:
  - CRUD API for deployment records per order/generator
  - Fields: started_at, stopped_at, operating_hours, kwh_start, kwh_end, faults
  - Displayed in GeneratorDetailPage
  - Linked to orders via order_pk

### Key API Endpoints
- `GET /api/orders/epirent` - Orders list (auth, date/search/status filters)
- `GET /api/orders/epirent/{pk}` - Order detail with geocoded address
- `PUT /api/orders/epirent/{pk}/settings` - Save radius/center per order
- `GET /api/orders/epirent/{pk}/generators` - Generators in radius
- `POST /api/orders/epirent/{pk}/deployments` - Create deployment entry
- `GET /api/orders/epirent/{pk}/deployments` - Order deployments
- `GET /api/orders/deployments/by-generator/{id}` - Generator deployment history

### DB Collections
- `order_settings`: {order_pk, center_lat, center_lng, radius_km, updated_at}
- `deployment_history`: {id, order_pk, generator_id, generator_name, started_at, stopped_at, operating_hours, kwh_start, kwh_end, faults, notes, created_at, created_by}

### Earlier Completed Work
- Generator monitoring dashboard with live MQTT data
- Energy monitoring (Messkoffer) with Pi sync
- Device management with image/document uploads
- Service plans, QR codes, user/permission management
- EpiRent ERP integration setup in admin settings
- DSE890 Gateway setup, GPS/map features

## Backlog
### P0
- Link generators to orders (auto-assign via GPS proximity during event period)

### P1
- Self-hosted MQTT Broker (Mosquitto) — move broker URL to .env
- "Kirmeskiste" device type support

### P2
- Admin file size limits

### Refactoring
- Move MQTT broker URL from hardcoded to backend/.env

## Test Credentials
- Admin: admin@test.com / password
- Ingest API Key: 7fbe01c5c9624306973a8d3e447b271a
