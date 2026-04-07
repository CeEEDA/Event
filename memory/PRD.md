# Kirmes Billing & Management System - PRD

## Original Problem Statement
Comprehensive "Kirmes" (Fairground) billing and management system with internal HR/Employee Management module. Built with React, FastAPI, MongoDB.

## User Personas
- **Admin**: Manages employees, shift planning, payroll, EpiRent orders, documents
- **Employee**: Views assigned shifts, payroll, personal documents

## Core Architecture
```
/app/backend/routes/
  ├── employee.py       # HR Data, Shift Planning, Absences
  ├── orders.py         # EpiRent API sync, Crew data (Crewbrain), Documents
  ├── documents.py      # AI Document Parsing (DATEV Lohnabrechnung)
/app/frontend/src/pages/
  ├── HubPage.js                # Employee Hub
  ├── EinsatzplanungPage.jsx    # Admin Shift Planning (Crewbrain integrated)
  ├── AbrechnungPage.jsx        # Employee Payroll
  ├── AdminZeitDetailPage.jsx   # Admin Employee Details
```

## Completed Features (Latest First)

### 2026-04-07: Improved Job Cards with Personnel Tracking
- Job cards show "X/Y Zugewiesen" progress counter with visual progress bar
- Green background + checkmark when all positions filled
- Orange border when partially filled
- "+ Personal definieren" button for cards without requirements
- Dispo date range shown on cards
- Both EpiRent crew data AND manual requirements supported

## 2026-04-07: Only Show Confirmed Orders with Dispo in Week
- Frontend filter changed: only `is_confirmed: true` orders appear in job cards
- Reduces noise from unconfirmed/draft orders (42 → 14 in test week)

## 2026-04-07: EpiRent Crewbrain Integration in Einsatzplanung
- Backend: `GET /api/orders/epirent/{order_pk}/crew` with 30-min caching
- Backend: `POST /api/orders/epirent/crew/batch` with semaphore(3) concurrency limiting
- Frontend: Job cards show EpiRent crew requirements (count, title, time) with "EpiRent" badge
- Frontend: Orders without crew data show manual "Kein Personal definiert" editor
- Tested: 100% Backend (13/13), 100% Frontend - All features verified

### Previously Completed
- Full Time Tracking, Auto-Overtime, Payroll system
- Admin Avatar Upload
- Employee Documents Management in AdminZeitDetailPage
- DATEV Lohnabrechnung PDF AI parsing (Gemini) with auto-assignment
- Employee "Abrechnung" (Payroll) view with released payrolls
- "Einsatzplanung" v2 (weekly grid, job cards, shift assignments)
- "Meine Einsätze" widget on Employee Hub
- Payroll "Speichern & Freigeben" (Release) functionality
- Test/Live Database isolation verified

## Key DB Collections
- `shift_assignments`: `{id, user_id, order_pk, role, note, date, start_time, end_time}`
- `shift_job_reqs`: `{order_pk, count, roles}` (Manual requirements)
- `shift_releases`: `{week_str, released_at, released_by}`
- `crew_cache`: `{order_pk, crew[], event, cached_at}` (30-min EpiRent cache)
- `payroll_releases`: `{user_id, month, net_amount, released_at}`

## Key API Endpoints
- `GET /api/orders/epirent/{order_pk}/crew` - Single order crew data (cached)
- `POST /api/orders/epirent/crew/batch` - Batch crew data (concurrency-limited)
- `POST /api/employee/shift-plan` - Save shift assignment
- `POST /api/employee/shift-plan/release` - Release week to employees
- `GET /api/orders/epirent` - Orders list with date filtering

## 3rd Party Integrations
- Gemini 2.5 Flash via Emergent Integrations `LlmChat` (Emergent LLM Key)
- DATEV (via SMTP Email)
- EpiRent API (ERP system - orders, crew/Crewbrain data)

## Backlog

### P1 - Upcoming
- Microsoft 365 Postfach-Anbindung (automatic document ingestion from email)
- PayPal/Kreditkarten Integration for Kirmes signups

### P2 - Future
- Lastdiagramm Live-Test (requires EMU meters)
- Suppress Chromium "Translate" popup on Raspberry Pi Kiosk
- Admin File Size Limits for uploads
- Windows Installer for Electron app
- GPS Support for Kirmeskiste
- DSE890 Gateway GSM Connection
- Refactor AdminPage.js (>1900 lines)
