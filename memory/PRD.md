# Eventenergie Portal - PRD

## Original Problem Statement
Umfassendes "Kirmes" (Jahrmarkt) Abrechnungssystem mit Tankbeleg-Digitalisierung, Auftragsverwaltung, Energiemonitoring, Zahlungsabwicklung und mehr.

## Core Architecture
- **Frontend:** React (CRA) + Tailwind CSS + Shadcn/UI
- **Backend:** FastAPI (Python) + MongoDB + GridFS
- **Desktop:** Electron Wrapper
- **External APIs:** EpiRent (ERP), Stripe (Payments), MQTT, OpenStreetMap

## What's Been Implemented

### Multi-Anschluss Buchung (Multi-Connection Booking) - FERTIG (2026-04)
- **Hauptanschluss** + beliebig viele Zusatzanschluesse + Wohnwagen-Anschluesse in einem Formular
- **Buchungsuebersicht**: Zeigt alle Anschluesse mit korrekten Preisen und Gesamtsumme (netto)
- **Einheitliches Zahlungsmittel**: Ein Zahlungsmittel-Dropdown oberhalb der AGBs fuer alle Buchungen
- **Wohnwagen-Preise korrekt**: Backend und Frontend unterscheiden zwischen regulaeren und Wohnwagen-Preisen (gleicher connection_type, unterschiedliche Preislisten)
- **Validierung**: Wohnwagen braucht nur Platznummer + Anschluss, normale Anschluesse zusaetzlich Fahrgeschaeft/Betrieb
- **Buttons untereinander**: "Weiteren Anschluss anmelden" und "Wohnwagen-Anschluss anmelden" vertikal angeordnet
- **Kein grauer Hintergrund** bei Zusatzanschluss-Formularen
- **Kein Nutzungs-Feld** beim Wohnwagen-Formular

### Lastdiagramm (Load Diagram) Feature - FERTIG (2026-04)
- **Dashboard-Sektion**: "Lastdiagramme" zeigt verfuegbare und gekaufte Diagramme
- **Kaufprozess**: 125,00 EUR netto + 19% MwSt = 148,75 EUR brutto
- **PDF-Generierung**: Deckblatt + taegliche Lastdiagramme (Leistung kW + Strom A pro Phase L1/L2/L3)
- **Endpoints**: GET /api/kirmes/public/lastdiagramm/available, POST /purchase, GET /{id}/pdf

### Datenschutz-Modal - FERTIG (2026-04)
- Button "Datenschutz" im Footer, vollstaendige DSGVO-konforme Datenschutzerklaerung

### Abrechnung Export (Billing PDF) - FERTIG (2026-04-03)
- Deckblatt mit Projektinfos, Stunden-Zusammenfassung, Tankbelege-Zusammenfassung

### Projektbericht (Digital Project Report) - FERTIG (2026-04-03)
- Full CRUD, digitale Unterschriften, PDF-Export

### Vorherige Features
- Expanded Row Redesign, Zaehler-Detailseite, Performance-Optimierung

## Key API Endpoints
- POST /api/kirmes/public/signup (Multi-Anschluss, korrekte Preisberechnung)
- GET/POST /api/kirmes/public/lastdiagramm/*
- POST /api/kirmes/signups/{signup_id}/invoice
- POST /api/kirmes/events/{event_id}/generate-invoices
- GET /api/kirmes/admin/lastdiagramm/{signup_id}/pdf

## Prioritized Backlog

### P1 - Kommend
- PayPal/Kreditkarten Integration

### P2 - Backlog
- Chromium Translate Popup auf Raspberry Pi
- Admin File Size Limits fuer Uploads
- Windows Installer fuer Electron Desktop App
- GPS-Support fuer Kirmeskiste

### Blocked
- DSE890 Gateway GSM (wartet auf neue SIM-Karten)

### Refactoring
- SchaustellerAnmeldungPage.jsx aufteilen (aktuell >1300 Zeilen)
