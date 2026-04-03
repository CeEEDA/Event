# Eventenergie Portal - PRD

## Original Problem Statement
Umfassendes "Kirmes" (Jahrmarkt) Abrechnungssystem mit Tankbeleg-Digitalisierung, Auftragsverwaltung, Energiemonitoring, Zahlungsabwicklung und mehr.

## Core Architecture
- **Frontend:** React (CRA) + Tailwind CSS + Shadcn/UI
- **Backend:** FastAPI (Python) + MongoDB + GridFS
- **Desktop:** Electron Wrapper
- **External APIs:** EpiRent (ERP), Stripe (Payments), MQTT, OpenStreetMap

## What's Been Implemented

### Projektbericht (Digital Project Report) - NEU (2026-04-03)
- **Backend**: Full CRUD at /api/project-reports
- **Frontend Form**: /project-report/new and /project-report/:reportId
  - Kundendaten (auto-filled from EpiRent Kontakt-API)
  - Mitarbeiter per Dropdown aus Benutzerverwaltung
  - Externes Personal (Freitext)
  - Arbeitsprotokoll (Karten-Layout, Textbausteine per Dropdown)
  - Material/Artikel, Fahrzeuge, Bemerkungen, Uebernachtung
  - Digitale Unterschriften (Techniker + Kunde)
- **Sperre**: Nach Kundenunterschrift kein Bearbeiten mehr moeglich
- **PDF**: Professionelles Layout mit Logo, abgekuerzte Namen (C.Ecker), nur gefuellte Spalten

### Textbausteine (Admin)
- CRUD at /api/project-reports/work-templates
- Admin kann Bezeichnung + Text anlegen
- Mitarbeiter waehlt per Dropdown, Text wird ins Arbeitsprotokoll eingefuegt

### Abrechnung Export - NEU (2026-04-03)
- **Endpoint**: GET /api/orders/epirent/{pk}/billing-pdf
- Deckblatt mit Projektinfos (Kunde, Auftragsnr, Zeitraum)
- Stunden-Zusammenfassung (alle Berichte aggregiert, nur gefuellte Spalten, GESAMT)
- Tankbelege-Zusammenfassung (Liter, Preise, Summen)
- Anhang: Alle Projektberichte einzeln mit Arbeitsprotokoll + Unterschriften
- Anhang: Alle Tankbelege

### Vorherige Features
- Expanded Row Redesign (3-Spalten Karten-Layout)
- Zaehler-Detailseite (MeterDiagnosticsPage)
- Performance-Optimierung (MongoDB Indexes, RAM-Leak Fix)

## Key API Endpoints
- POST/GET/PUT/DELETE /api/project-reports
- GET /api/project-reports/by-order/{order_pk}
- GET /api/project-reports/{id}/pdf
- GET/POST/PUT/DELETE /api/project-reports/work-templates
- GET /api/orders/epirent/{pk}/billing-pdf
- GET /api/devices/{device_id}/meters/{meter_id}/diagnostics

## Prioritized Backlog

### P1 - Kommend
- PayPal Integration

### P2 - Backlog
- Chromium Translate Popup auf Raspberry Pi
- Admin File Size Limits fuer Uploads
- Windows Installer fuer Electron Desktop App
- GPS-Support fuer Kirmeskiste

### Blocked
- DSE890 Gateway GSM (wartet auf neue SIM-Karten)
