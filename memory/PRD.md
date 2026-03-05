# FileShare & Generator-Monitoring Portal - PRD

## Original Problem Statement
NextCloud-ähnliche Dateifreigabe-Anwendung für Eventenergie Deutschland mit Generator-Monitoring für DSE Aggregate.

## Core Requirements - FileShare - Status
- [x] JWT-basierte Authentifizierung (admin, mitarbeiter, kunde)
- [x] App-Berechtigungssystem (FileShare pro User)
- [x] Eigener Dateibereich + Gemeinsamer Bereich
- [x] Admin Dateien-Einsicht aller User
- [x] Ordner/Dateien teilen mit Berechtigungen
- [x] Datei-Upload mit GridFS + Drag & Drop
- [x] Ordner-Management mit Modal
- [x] Share-Links mit Ablaufdatum/Passwortschutz
- [x] Hub-Seite, Magenta/Fuchsia Theme, Logo
- [x] Passwort-Reset (User + Admin), EMAIL GEMOCKT
- [x] Download (file-saver + Iframe-Fallback-Dialog)
- [x] Löschen (ConfirmDialog statt window.confirm)
- [x] Dateien verschieben zwischen Ordnern
- [x] Ordner als ZIP herunterladen
- [x] Dateivorschau (PDF, Bilder)
- [x] Suchfunktion in FileShare
- [x] Suchfunktion in Benutzerverwaltung
- [x] Benutzer-Tabs: Kunden/Mitarbeiter
- [ ] E-Mail-Versand für Passwort-Reset (Office 365 IMAP)

## Core Requirements - Generator-Monitoring - Status
### Phase 1: Datenmodell & Dashboard (ABGESCHLOSSEN)
- [x] MongoDB-Schema für Generatoren, Telemetrie, Alarme
- [x] Generator CRUD API (Admin)
- [x] Telemetrie-Empfangsendpunkt (API-Key Auth für DSE890)
- [x] Telemetrie-Abfrage mit Zeitfilter
- [x] Alarm-Management (Erstellen, Quittieren, Beheben)
- [x] Dashboard mit Status-Übersicht (Gesamt/Läuft/Standby/Warnung/Offline)
- [x] Suchfunktion und Statusfilter
- [x] Generator-Karten mit Live-Telemetrie
- [x] Detail-Seite mit Messwerten (Spannung, Strom, Leistung, Temperatur, etc.)
- [x] Telemetrie-Charts (Recharts: Leistung, Auslastung, Spannung, Temperatur, Frequenz, Tankstand)
- [x] Aktive Alarme mit Quittier-/Beheben-Funktion
- [x] Admin-Info (Generator-ID, API-Key, DSE-Modul)
- [x] Demo-Datengenerator für Tests
- [x] Kunden sehen nur zugewiesene Generatoren

### Phase 2: Steuerung & Erweiterte Alarme (AUSSTEHEND)
- [ ] Fernsteuerung (Start/Stop/Test/Alarm-Reset)
- [ ] Schwellenwert-Konfiguration für automatische Alarme
- [ ] E-Mail/SMS-Benachrichtigungen bei Alarmen
- [ ] Alarm-Historie

### Phase 3: Kundenzuordnung & Berechtigungen (AUSSTEHEND)
- [ ] Generatoren Kunden zuweisen (Admin-UI)
- [ ] Kundenspezifische Dashboard-Ansichten
- [ ] Berechtigungssteuerung über Benutzerverwaltung

### Phase 4: Mobile App & Push (ZUKUNFT)
- [ ] Mobile App mit Push-Benachrichtigungen
- [ ] Standort-Tracking auf Karte

## Tech Stack
- Backend: FastAPI, Motor (async MongoDB), GridFS
- Frontend: React 19, Tailwind CSS, Shadcn/UI, Recharts, file-saver
- Database: MongoDB
- Auth: JWT + bcrypt

## Architecture
```
/app/
├── backend/
│   ├── .env
│   ├── requirements.txt
│   ├── server.py (FileShare API + Router init)
│   └── routes/
│       └── generators.py (Generator Monitoring API)
└── frontend/
    └── src/
        ├── pages/
        │   ├── GeneratorDashboardPage.js (Übersicht)
        │   ├── GeneratorDetailPage.js (Einzelansicht)
        │   ├── DashboardPage.js (FileShare)
        │   ├── AdminPage.js
        │   ├── HubPage.js (Navigations-Hub)
        │   └── ...
        └── ...
```

## DB Collections
- users, files, folders, shares, password_resets
- generators, generator_telemetry, generator_alarms

## Test Credentials
- Admin: admin@test.com / password
- Kunde: kunde1@test.com / password
- Mitarbeiter: ma1@test.com / password

## Prioritized Backlog
### P0
- Office 365 E-Mail-Integration (User gibt Zugangsdaten)

### P1
- Phase 2: Generator-Fernsteuerung & Erweiterte Alarme
- Phase 3: Kundenzuordnung UI

### P2
- Admin-Dateigröße-Limit pro Benutzer
- Datei-Versioning, Activity Log
- backend/server.py aufteilen (APIRouter für Auth, Users, Files)

### P3
- Mobile App mit Push-Benachrichtigungen
- Standort-Tracking auf Karte
