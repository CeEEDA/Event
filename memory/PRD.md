# Eventenergie Portal - PRD

## Original Problem Statement
Full-stack Kirmes (Fairground) Billing System with:
- Admin dashboard, public exhibitor portal, Stripe payments, ZUGFeRD invoicing with GiroCode
- Live EMU meter data integration via MQTT, "Kirmeskiste" Raspberry Pi device management
- Fuel Receipt Digitization (Tankbeleg-Digitalisierung)
- Desktop App (Electron) for macOS/Windows

## Tech Stack
- **Frontend:** React, Tailwind CSS, Shadcn/UI
- **Backend:** FastAPI (Python)
- **Database:** MongoDB (Motor async driver)
- **Auth:** JWT-based
- **Payments:** Stripe
- **MQTT:** paho-mqtt (HiveMQ broker)
- **E-Invoicing:** factur-x (ZUGFeRD), girocode
- **Desktop:** Electron

## Architecture
```
/app/
├── backend/
│   ├── routes/
│   │   ├── admin_settings.py   # SMTP config
│   │   ├── devices.py          # Device management
│   │   ├── energy_monitoring.py# EMU meters
│   │   ├── fuel_receipts.py    # Tankbeleg CRUD, PDF, sync
│   │   ├── generators.py       # Generator monitoring
│   │   ├── kirmes.py           # Kirmes events, exhibitors
│   │   ├── mqtt_config.py      # MQTT configuration
│   │   ├── orders.py           # Order management
│   │   ├── payments.py         # Stripe payments
│   │   └── serviceplan.py      # Service plans
│   ├── server.py               # Main FastAPI app
│   ├── email_service.py        # SMTP email sending
│   └── mqtt_service.py         # MQTT client
├── frontend/src/
│   ├── pages/
│   │   ├── FuelReceiptsPage.js # Tankbeleg UI (NEW)
│   │   ├── HubPage.js          # Main navigation hub
│   │   ├── AdminPage.js        # User management
│   │   ├── OrdersPage.js       # Order management
│   │   ├── KirmesPage.js       # Kirmes events
│   │   └── ...
│   └── App.js                  # Routing
└── desktop/                    # Electron app
```

## What's Been Implemented

### Core System (Complete)
- User management (admin/staff/customer roles)
- FileShare with folder management, sharing, ZIP download
- Order management with EpiRent integration
- Generator monitoring with MQTT real-time data
- Energy monitoring with Shelly meters
- Device management (Kirmeskiste configuration)
- Service plan management
- Kirmes event management with exhibitor registration
- Stripe payment integration
- ZUGFeRD e-invoicing with GiroCode
- QR-code meter assignment
- Password reset flow
- Admin SMTP configuration
- Desktop app (macOS ARM64 build)

### Fuel Receipt Digitization - Phase 1 (Complete, 2026-03-19)
- Full CRUD API for fuel receipts (`/api/fuel-receipts`)
- Stats endpoint with aggregation by fuel type
- Confirm/Reject workflow with audit trail (confirmed_by, confirmed_at)
- PDF export (ReportLab)
- Pi sync endpoint (`/sync`) - no auth, dedup by pi_local_id
- Filter by status and fuel type
- Order/project linking via dropdown
- GPS coordinates (admin-only visibility)
- Navigation from Hub page
- **Integrated into OrderDetailPage** - Tankbelege section shows order-specific receipts with full CRUD, confirm/reject, PDF export directly in the order view

## Pending Issues
- **P1: Hardcoded MQTT Broker URL** - `mqtt_service.py` uses hardcoded `broker.hivemq.com` instead of DB/env config

## Backlog (P0-P2)

### P0
- Fuel Receipt Phase 2: Raspberry Pi serial printer emulator (BLOCKED on sample receipt)

### P1
- PayPal Integration
- Direct QR Label Printing
- Windows Installer for Electron desktop app
- Self-Hosted MQTT Broker migration

### P2
- Configurable file size limits for uploads

## Key Credentials
- Admin: `admin@test.com` / `password`
- Production Admin: `christian.ecker@eventenergie-deutschland.de` / `Kirmes#2026`
