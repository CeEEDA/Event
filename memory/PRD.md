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

### Einsatzplanung - FERTIG (2026-04-06)
- Admin-Wochenplan: Raster Mitarbeiter x Wochentage
- EpiRent-Auftraege der Woche oben angezeigt
- Einsaetze zuweisen: Auftrag, Rolle, Freitext
- Abwesenheiten (Urlaub, Krank, UeS-Abbau) direkt im Raster sichtbar
- Wochenplan freigeben → Mitarbeiter sieht seine Einsaetze im Hub
- Mitarbeiter-Hub: "Meine Einsaetze" unter der Stempelfunktion
- Backend: GET/POST/DELETE /api/employee/shift-plan, POST /shift-plan/release, GET /shift-plan/my-plan
- DB: shift_assignments, shift_releases

### DATEV Lohnabrechnung KI-Erkennung - FERTIG (2026-04-06)
- Ordner "Lohnabrechnung" im Dokumentenstamm (bei Finanz-Ordnern, emerald)
- KI-Erkennung: Mitarbeitername, Personalnummer, Monat, Nettobetrag
- Automatische Zuweisung zum erkannten Mitarbeiter
- Mitarbeiter-Abrechnungsseite zeigt DATEV-PDFs + interne Abrechnungen

### Abrechnungs-Freigabe System - FERTIG (2026-04-06)
- Admin: Speichern & Freigeben Button
- Mitarbeiter: Abrechnung-Kachel im Hub

### Weitere fertige Features
- Dokumente in Mitarbeiter-Detailseite verschoben
- Mitarbeiterverwaltung: Alle User angezeigt (nicht nur gestempelte)
- Admin Avatar Upload, Regelarbeitszeit, Auto-Ueberstunden
- Payroll mit Zuschlaegen + Abzuegen + CSV Export
- Mitarbeiter-Notizen, Arbeitsfreie-Zeit-Antraege, HR-Daten
- GPS-Zeiterfassung, Chat, Dokumentenverwaltung mit KI

## Key API Endpoints
### Einsatzplanung
- GET /api/employee/shift-plan?week=YYYY-WXX (Admin)
- POST /api/employee/shift-plan (Admin: Create/Update)
- DELETE /api/employee/shift-plan/{id} (Admin: Delete)
- POST /api/employee/shift-plan/release?week=YYYY-WXX (Admin: Freigabe)
- GET /api/employee/shift-plan/my-plan (Mitarbeiter: eigene Einsaetze)

## DB Collections
- shift_assignments, shift_releases (NEU)
- payroll_releases, payroll_deductions
- employee_profiles, employee_documents, hr_data, vacation_entries
- time_entries, time_off_requests, work_schedules, employee_notes

## Prioritized Backlog
### P1
- Microsoft 365 Postfach-Anbindung
- PayPal/Kreditkarten Integration

### P2
- Lastdiagramm Live-Test, Chromium Kiosk, Admin Dateigroessen-Limits
- Windows Installer, GPS-Support, DSE890 Gateway, AdminPage.js Refactoring
