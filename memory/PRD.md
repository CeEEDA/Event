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

### Admin Avatar Upload in Benutzerverwaltung - FERTIG (2026-04-06)
- Admins koennen Profilbilder fuer jeden Benutzer direkt in der Benutzerverwaltung hochladen
- Hover-Overlay mit Kamera-Icon auf dem Avatar-Kreis
- Backend: `POST /api/employee/avatar/{user_id}/upload` (nur Admins)
- Frontend: Upload in AdminPage.js, aktualisiert Profilcache nach Upload
- Redundante Zeiterfassungs-UI aus Admin-Benutzerverwaltung entfernt

### Admin Mitarbeiter-Zeitdetail Monatsansicht - FERTIG (2026-04-06)
- AdminZeitDetailPage (`/verwaltung/zeiterfassung/:userId`) komplett redesigned
- Aufklappbare Monatsansicht (Accordion) identisch zur Mitarbeiter-Seite (`/arbeitszeit`)
- Summary Badges pro Monat: Stunden, Urlaub, Krank
- HR-Stammdaten (Ueberstunden, Urlaubstage) bearbeitbar
- Genehmigte Urlaube eintragen/loeschen mit Kalender-Berechnung
- Jahres-Summary-Karten: Stundenkonto, Genehmigt, Resturlaub, Krankheit
- GPS-Pins fuer Ein-/Ausstempeln sichtbar (nur Admin)

### Regelarbeitszeit (Standard-Arbeitszeiten) - FERTIG (2026-04-06)
- Admin kann pro Mitarbeiter Mo-Sa Standard-Arbeitszeiten eintragen: Beginn, Ende, Pausenzeit
- Automatische Netto-Berechnung pro Tag und Wochensumme
- Backend: `work_schedules` Collection, GET/PUT `/api/employee/work-schedule/{userId}`
- Frontend: Tabelle in AdminZeitDetailPage mit Speichern-Button
- Basis fuer Ueberstundenberechnung: Stunden ueber Regelzeit = Ueberstunden

### Archiv-Funktion fuer Abgelehnte Antraege - FERTIG (2026-04-06)
- Abgelehnt/Zurueckgezogen-Sektion zeigt nur aktuelles Jahr
- Archiv-Sektion (klappbar nach Jahr) fuer vergangene Jahre
- Am 01.01. wandern alte Eintraege automatisch ins Archiv
- Auf Admin-Detailseite + Mitarbeiter-Arbeitszeitseite

### Antrags-Tasks Genehmigt/Abgelehnt Buttons - FERTIG (2026-04-06)
- Antrags-Tasks zeigen "Genehmigt" und "Abgelehnt" Buttons statt Haekchen
- Muelleimer-Button bei Antrags-Tasks entfernt
- "von undefined" Bug behoben (created_by_name fehlte bei Task-Erstellung)
- Genehmigte/Abgelehnte Antrags-Tasks werden korrekt als erledigt markiert (completed=true)

### Ueberstundenabbau-Verrechnung Bugfix - FERTIG (2026-04-06)
- Bug: Genehmigte Ueberstundenabbau-Antraege wurden nicht vom Stundenkonto abgezogen
- Fix: Bei Genehmigung (direkt + via Task) werden automatisch 8h pro Arbeitstag abgezogen

### Auto-Ueberstundenberechnung bei Clock-out - FERTIG (2026-04-06)
- Bei Clock-out werden Ist-Stunden mit Regelarbeitszeit verglichen
- Differenz wird automatisch auf das Ueberstundenkonto gebucht
- Backend: `/api/employee/time/clock-out` erweitert

### Lohnabrechnung (Payroll) - FERTIG (2026-04-06)
- Stundenlohn pro Mitarbeiter konfigurierbar
- Automatische Zuschlaege: Sonntag 50%, Feiertag 125%, Sonderfeiertag 150%, Nacht 25%
- Manuelle Abzuege (Ausruestung, etc.) verwaltbar
- CSV-Export der Lohnabrechnung
- Backend: `GET /api/employee/payroll/{user_id}/{year}/{month}`, `POST /api/employee/payroll/deductions/{user_id}`

### Mitarbeiter-Notizen (Gespraechsnotizen) - FERTIG (2026-04-06)
- Admins koennen Gespraechsnotizen pro Mitarbeiter erfassen
- Drag & Drop Dokumenten-Upload pro Notiz
- Backend: `POST /api/employee/notes/{user_id}`, Collection `employee_notes`

### Arbeitsfreie-Zeit-Antraege - FERTIG (2026-04-06)
- Mitarbeiter koennen ueber Hub-Kachel "Freie Zeit" Antraege stellen (Krank, Urlaub, Ueberstundenabbau)
- Dialog mit Dropdown, Datumsauswahl, Ganztaegig-Toggle, optionale Uhrzeiten
- Antraege erscheinen als Aufgabe bei allen Admins
- Admin kann Antraege genehmigen/ablehnen, Mitarbeiter kann zurueckziehen

### HR-Daten (Ueberstunden / Urlaub) - FERTIG (2026-04-06)
- Admin kann pro Mitarbeiter Ueberstunden, Urlaubstage und Genehmigten Urlaub eintragen
- Berechnete Anzeige: Stundenkonto, Genehmigter Urlaub, Resturlaub

### GPS-Zeiterfassung (Stempeln) - FERTIG (2026-04-05)
- SwipeClock-Slider im Hub zum Ein-/Ausstempeln
- GPS-Koordinaten werden bei jedem Stempelvorgang erfasst
- Eigene Arbeitszeitseite (`/arbeitszeit`) mit Monatsübersicht

### Auswertung Dokumenten-Ablauf - FERTIG (2026-06-04)
- Dashboard: Abgelaufen / Kritisch / Warnung / Gueltig Zaehler
- Gruppierung nach Status oder Mitarbeiter

### Profilbild-Integration & Admin-Mitarbeiterverwaltung - FERTIG (2026-06-04)
- Profilbild im Hub-Header, Chat-Nachrichten und Konversationsliste
- Mitarbeiter-Profil + Dokumente direkt in Benutzerverwaltung eingebettet

### Mitarbeiter-Profil & Dokumentenverwaltung - FERTIG (2026-06-04)
- Profilseite: Name, Profilbild, Anschrift, Telefon, Passwort aendern
- 9 Dokumenten-Kategorien mit Drag & Drop PDF-Upload
- KI-Ablaufdatum-Erkennung via Gemini 2.5 Flash

### Chat & Aufgabenverwaltung - FERTIG (2026-04-05)
- Direktnachrichten, Gruppenchats, Echtzeit-Polling
- Aufgaben mit Prioritaeten, Faelligkeitsdaten, Zuweisung

### Dokumentenverwaltung mit KI - FERTIG (2026-04-04/05)
- 66+ Masterordner, KI-Erkennung, DATEV-Weiterleitung, Drag & Drop

### Weitere Features - FERTIG
- Auto-Speicherung Portal-Rechnungen
- Mitarbeiter-Berechtigungen (Finance + Dokumentenverwaltung)
- SchaustellerAnmeldungPage Refactoring (14 Subkomponenten)
- Multi-Anschluss Buchung, Kaution, Sammelrechnung
- Lastdiagramm Feature
- Chat Detail-Panel, Gruppenbild & Namensaenderung, Aufgaben-Filter Redesign

## Key API Endpoints
### Employee/HR
- POST /api/employee/time/clock-in, clock-out, status, report
- GET /api/employee/payroll/{user_id}/{year}/{month}
- POST /api/employee/payroll/deductions/{user_id}
- POST /api/employee/notes/{user_id}
- PUT /api/employee/admin-avatar/{user_id}
- POST /api/employee/avatar/{user_id}/upload
- GET /api/employee/avatar/{user_id}
- GET/PUT /api/employee/work-schedule/{userId}

### Chat & Tasks
- GET/POST /api/chat/conversations, messages
- GET/POST/PUT/DELETE /api/chat/tasks

### Documents
- POST /api/documents/upload
- GET /api/documents/folders

## DB Collections
- employee_profiles, employee_documents, hr_data, vacation_entries
- time_entries, time_off_requests, work_schedules
- employee_notes, payroll_deductions
- chat_conversations, chat_messages, tasks, task_comments

## Prioritized Backlog
### P1
- Microsoft 365 Postfach-Anbindung
- PayPal/Kreditkarten Integration

### P2
- Lastdiagramm Live-Test (EMU-Messgeraete)
- Chromium Kiosk Translate-Popup unterdruecken
- Admin Dateigroessen-Limits
- Windows Installer fuer Electron App
- GPS-Support fuer Kirmeskiste
- DSE890 Gateway GSM
- AdminPage.js Refactoring (~1900 Zeilen)
