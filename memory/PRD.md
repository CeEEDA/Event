# Eventenergie Portal - PRD

## Original Problem Statement
Umfassendes "Kirmes" (Jahrmarkt) Abrechnungssystem mit Tankbeleg-Digitalisierung, Auftragsverwaltung, Energiemonitoring, Zahlungsabwicklung, Dokumentenverwaltung, Team Chat und Aufgabenverwaltung.

## Core Architecture
- **Frontend:** React (CRA) + Tailwind CSS + Shadcn/UI
- **Backend:** FastAPI (Python) + MongoDB
- **Desktop:** Electron Wrapper
- **External APIs:** EpiRent (ERP), Stripe, MQTT, OpenStreetMap, Gemini 2.5 Flash (KI)
- **Object Storage:** Emergent Object Storage
- **DATEV:** Automatische Weiterleitung an uploadmail.datev.de

## What's Been Implemented

### DATEV Lohnabrechnung KI-Erkennung - FERTIG (2026-04-06)
- Neuer Ordner "Lohnabrechnung" im Dokumentenstamm mit automatischen Jahr/Monat-Unterordnern
- KI-Erkennung per Gemini 2.5 Flash: Extrahiert Mitarbeitername, Personalnummer, Monat, Nettobetrag
- Automatische Zuweisung der Lohnabrechnung zum erkannten Mitarbeiter
- Mitarbeiter-Abrechnungsseite zeigt DATEV-PDFs + interne Abrechnungen
- Backend: `_assign_payroll_to_employee()`, `GET /api/employee/payroll/my-documents`, `GET /api/employee/payroll/documents/{user_id}`
- DB: `payroll_releases`, `documents.assigned_user_id/payroll_info/payroll_month`

### Abrechnungs-Freigabe System - FERTIG (2026-04-06)
- Admin kann Lohnabrechnung pro Monat "Speichern & Freigeben"
- Mitarbeiter sieht freigegebene Abrechnungen unter "Abrechnung" Kachel im Hub
- Backend: `POST /api/employee/payroll/{user_id}/release`, `GET /api/employee/payroll/my-releases`

### Dokumente in Mitarbeiter-Detailseite verschoben - FERTIG (2026-04-06)

### Umbenennung: Arbeitszeiterfassung -> Mitarbeiterverwaltung - FERTIG (2026-04-06)

### Admin Avatar Upload - FERTIG (2026-04-06)

### Regelarbeitszeit, Auto-Ueberstunden, Payroll, Notizen, Antraege, HR-Daten - FERTIG

### GPS-Zeiterfassung, Chat, Dokumentenverwaltung mit KI - FERTIG

## Key API Endpoints
### Payroll/DATEV
- POST /api/employee/payroll/{user_id}/release
- GET /api/employee/payroll/{user_id}/releases
- GET /api/employee/payroll/my-releases
- GET /api/employee/payroll/my-documents (DATEV PDFs)
- GET /api/employee/payroll/documents/{user_id} (Admin: DATEV PDFs)

## Prioritized Backlog
### P1
- Microsoft 365 Postfach-Anbindung
- PayPal/Kreditkarten Integration

### P2
- Lastdiagramm Live-Test, Chromium Kiosk, Admin Dateigroessen-Limits
- Windows Installer, GPS-Support, DSE890 Gateway, AdminPage.js Refactoring
