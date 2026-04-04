# Eventenergie Portal - PRD

## Original Problem Statement
Umfassendes "Kirmes" (Jahrmarkt) Abrechnungssystem mit Tankbeleg-Digitalisierung, Auftragsverwaltung, Energiemonitoring, Zahlungsabwicklung und mehr.

## Core Architecture
- **Frontend:** React (CRA) + Tailwind CSS + Shadcn/UI
- **Backend:** FastAPI (Python) + MongoDB + GridFS
- **Desktop:** Electron Wrapper
- **External APIs:** EpiRent (ERP), Stripe (Payments), MQTT, OpenStreetMap

## What's Been Implemented

### Abrechnung Export (Billing PDF) - FERTIG (2026-04-03)
- **Endpoint**: GET /api/orders/epirent/{pk}/billing-pdf
- Deckblatt mit Projektinfos (Kunde, Auftragsnr, Zeitraum)
- Stunden-Zusammenfassung: Aggregiert pro Datum (Normalstunden, Extrastunden, Notdienststunden) + GESAMT
- Tankbelege-Zusammenfassung (Liter, Preise, Summen)
- **PDF-Merging**: Alle Projektberichte + Tankbelege werden als Einzel-PDFs angehaengt (via pypdf PdfWriter)
- Funktioniert auch bei leeren Auftraegen (nur Summary-Seite)

### Projektbericht (Digital Project Report) - FERTIG (2026-04-03)
- **Backend**: Full CRUD at /api/project-reports
- **Frontend Form**: /project-report/new und /project-report/:reportId
  - Kundendaten (auto-filled from EpiRent Kontakt-API)
  - Mitarbeiter per Dropdown aus Benutzerverwaltung
  - Externes Personal (Freitext)
  - Arbeitsprotokoll (Karten-Layout, Textbausteine per Dropdown)
  - Material/Artikel, Fahrzeuge, Bemerkungen, Uebernachtung
  - Digitale Unterschriften (Techniker + Kunde)
- **Sperre**: Nach Kundenunterschrift kein Bearbeiten mehr moeglich
- **PDF**: Professionelles Layout mit Logo, abgekuerzte Namen (C.Ecker), nur gefuellte Spalten
- **Refactored**: _generate_report_pdf() als wiederverwendbare Funktion extrahiert

### Textbausteine (Admin)
- CRUD at /api/project-reports/work-templates
- Admin kann Bezeichnung + Text anlegen
- Mitarbeiter waehlt per Dropdown, Text wird ins Arbeitsprotokoll eingefuegt

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

### Datenschutz-Modal (Schausteller Anmeldung) - FERTIG (2026-04)
- **Button**: "Datenschutz" im Footer neben "Impressum" hinzugefuegt
- Vollstaendige DSGVO-konforme Datenschutzerklaerung in 5 Abschnitten
- Scrollbar, Links klickbar, Modal schliessbar

### Lastdiagramm (Load Diagram) Feature - FERTIG (2026-04)
- **Dashboard-Sektion**: "Lastdiagramme" zeigt verfuegbare und gekaufte Diagramme
- **Kaufprozess**: 125,00 EUR netto + 19% MwSt = 148,75 EUR brutto
- **Rechnungserstellung**: Fortlaufende Nummer (R26-K-XXXX), gleiche Collection wie Kirmes-Rechnungen
- **PDF-Generierung**: Deckblatt (Event, Netzanschluss, Zeitraum, kWh, Max Strom/Phase, Max Leistung) + taegliche Lastdiagramme (Leistung kW + Strom A pro Phase L1/L2/L3)
- **Zahlungsart**: Abhaengig von Schausteller-Einstellung (kauf_auf_rechnung oder Kreditkarte/PayPal)
- **Duplikat-Schutz**: Gleiche Buchung kann nur einmal bestellt werden
- **Endpoints**: GET /api/kirmes/public/lastdiagramm/available, POST /api/kirmes/public/lastdiagramm/purchase, GET /api/kirmes/public/lastdiagramm/{id}/pdf

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
