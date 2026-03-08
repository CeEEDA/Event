# DSE Power Generator Portal – PRD

## Original Problem Statement
Comprehensive monitoring and management portal for DSE power generators with EpiRent ERP integration, energy monitoring, and fleet management.

## Tech Stack
- **Backend**: FastAPI, Python, MongoDB (Motor), GridFS, paho-mqtt, httpx
- **Frontend**: React, Tailwind CSS, Shadcn/UI, Recharts, Leaflet/OpenStreetMap, open-location-code

## What's Been Implemented

### Auftragsverwaltung (2026-03-08)
- **Orders List**: Status filter (default: Bestätigt), date range (default: heute), search
- **Order Detail Page** (`/orders/:pk`):
  - Info cards: Event, Kunde, Lieferanschrift
  - Map with geocoded address (Nominatim), configurable radius per order
  - Generators within radius (Haversine)
  - **Artikel positionieren**: Manual asset placement (Lichtmast, Stromerzeuger, Verteiler, Sonstiges)
    - GPS from device ("Meine Position")
    - Plus Codes (open-location-code) as W3W alternative
    - Orange markers on map, CRUD table with delete
- **Deployment History**: CRUD for generator deployment records, shown in GeneratorDetailPage

### Key API Endpoints
- `GET /api/orders/epirent` - Orders list with filters
- `GET /api/orders/epirent/{pk}` - Order detail with geocoding
- `PUT /api/orders/epirent/{pk}/settings` - Save radius/center
- `GET /api/orders/epirent/{pk}/generators` - Generators in radius
- `CRUD /api/orders/epirent/{pk}/assets` - Manual asset placement
- `CRUD /api/orders/epirent/{pk}/deployments` - Deployment history
- `GET /api/orders/deployments/by-generator/{id}` - Generator history

### DB Collections
- `order_settings`: {order_pk, center_lat, center_lng, radius_km}
- `order_assets`: {id, order_pk, asset_type, latitude, longitude, label, plus_code, created_by}
- `deployment_history`: {id, order_pk, generator_id, started_at, stopped_at, operating_hours, kwh_start, kwh_end, faults}

### Earlier Completed Work
- Generator monitoring, energy monitoring (Messkoffer), device management
- MQTT integration, GPS/maps, EpiRent ERP setup
- DSE remote control, service plans, user permissions, file management

## Backlog
### P0
- Auto-assign generators to orders via GPS proximity during event period

### P1
- Self-hosted MQTT Broker (Mosquitto)
- "Kirmeskiste" device type

### P2
- Admin file size limits

### Refactoring
- MQTT broker URL → .env

## Test Credentials
- Admin: admin@test.com / password
