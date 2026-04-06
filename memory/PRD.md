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

### Abrechnungs-Freigabe System - FERTIG (2026-04-06)
- Admin kann Lohnabrechnung pro Monat "Speichern & Freigeben"
- Freigabe speichert Snapshot der kompletten Abrechnung (Stunden, Zuschlaege, Abzuege, Netto)
- Mitarbeiter sieht freigegebene Abrechnungen unter neuer "Abrechnung" Kachel im Hub
- Aufklappbare Monats-Detailansicht mit allen Positionen
- Backend: `POST /api/employee/payroll/{user_id}/release`, `GET /api/employee/payroll/my-releases`
- DB Collection: `payroll_releases`
- Vorbereitung fuer spaetere DATEV API Integration

### Dokumente in Mitarbeiter-Detailseite verschoben - FERTIG (2026-04-06)
- "Dokumente & Zertifikate" Grid aus Benutzerverwaltung (AdminPage) entfernt
- In AdminZeitDetailPage eingebaut (nach Stammdaten, vor Regelarbeitszeit)
- Drag & Drop Upload, Ampel-Status, KI-Ablaufdatum-Erkennung weiterhin aktiv

### Umbenennung: Arbeitszeiterfassung -> Mitarbeiterverwaltung - FERTIG (2026-04-06)
- Seitentitel der Admin-Uebersicht umbenannt

### Abzug Button: "+" zu "-" geaendert - FERTIG (2026-04-06)

### Admin Avatar Upload in Benutzerverwaltung - FERTIG (2026-04-06)
- Admins koennen Profilbilder fuer jeden Benutzer direkt in der Benutzerverwaltung hochladen
- Redundante Zeiterfassungs-UI aus Admin-Benutzerverwaltung entfernt

### Admin Mitarbeiter-Zeitdetail Monatsansicht - FERTIG (2026-04-06)
- AdminZeitDetailPage komplett redesigned mit aufklappbarer Monatsansicht

### Regelarbeitszeit (Standard-Arbeitszeiten) - FERTIG (2026-04-06)
- Admin kann pro Mitarbeiter Mo-Sa Standard-Arbeitszeiten eintragen

### Auto-Ueberstundenberechnung bei Clock-out - FERTIG (2026-04-06)

### Lohnabrechnung (Payroll) - FERTIG (2026-04-06)
- Stundenlohn, automatische Zuschlaege, manuelle Abzuege, CSV-Export

### Mitarbeiter-Notizen (Gespraechsnotizen) - FERTIG (2026-04-06)

### Arbeitsfreie-Zeit-Antraege - FERTIG (2026-04-06)

### HR-Daten (Ueberstunden / Urlaub) - FERTIG (2026-04-06)

### GPS-Zeiterfassung (Stempeln) - FERTIG (2026-04-05)

### Chat & Aufgabenverwaltung - FERTIG (2026-04-05)

### Dokumentenverwaltung mit KI - FERTIG (2026-04-04/05)

### Weitere Features - FERTIG
- Auto-Speicherung Portal-Rechnungen
- Mitarbeiter-Berechtigungen, SchaustellerAnmeldungPage Refactoring
- Multi-Anschluss Buchung, Kaution, Sammelrechnung, Lastdiagramm
- Chat Detail-Panel, Gruppenbild, Aufgaben-Filter Redesign
- Profilbild-Integration, Auswertung Dokumenten-Ablauf

## Key API Endpoints
### Employee/HR
- POST /api/employee/time/clock-in, clock-out, status, report
- GET /api/employee/payroll/{user_id}, /csv
- POST /api/employee/payroll/{user_id}/release (NEU)
- GET /api/employee/payroll/{user_id}/releases (NEU)
- GET /api/employee/payroll/my-releases (NEU)
- POST /api/employee/payroll/deductions/{user_id}
- POST /api/employee/notes/{user_id}
- POST /api/employee/avatar/{user_id}/upload
- GET/PUT /api/employee/work-schedule/{userId}

## DB Collections
- employee_profiles, employee_documents, hr_data, vacation_entries
- time_entries, time_off_requests, work_schedules
- employee_notes, payroll_deductions, payroll_releases (NEU)
- chat_conversations, chat_messages, tasks, task_comments

## Prioritized Backlog
### P1
- Microsoft 365 Postfach-Anbindung
- PayPal/Kreditkarten Integration
- DATEV API fuer Lohnabrechnungen (Mitarbeiter-Abrechnungsseite vorbereitet)

### P2
- Lastdiagramm Live-Test (EMU-Messgeraete)
- Chromium Kiosk Translate-Popup unterdruecken
- Admin Dateigroessen-Limits
- Windows Installer fuer Electron App
- GPS-Support fuer Kirmeskiste
- DSE890 Gateway GSM
- AdminPage.js Refactoring (~1900 Zeilen)
