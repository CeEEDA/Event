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
- [x] Dashboard mit Status-Übersicht
- [x] Suchfunktion und Statusfilter
- [x] Generator-Karten mit Live-Telemetrie
- [x] Detail-Seite mit Messwerten
- [x] Telemetrie-Charts (Recharts)
- [x] Aktive Alarme mit Quittier-/Beheben-Funktion
- [x] Admin-Info (Generator-ID, API-Key, DSE-Modul)
- [x] Demo-Datengenerator für Tests

### Phase 1.5: UI & Berechtigungen (ABGESCHLOSSEN - 05.03.2026)
- [x] Weißer Hintergrund + Logo auf allen Seiten
- [x] Lila/Fuchsia Akzente durchgängig (inkl. Hub-Buttons)
- [x] Hub: "Monitoring" (ohne Untertitel)
- [x] Benutzerverwaltung: Monitoring-Freigabe pro User
- [x] Toggle: Zugriff auf alle vs. einzelne Generatoren
- [x] Checkbox-Liste zur Geräteauswahl
- [x] Monitoring-Spalte in Benutzertabelle
- [x] Backend: Permission-basierte Filterung (BUG BEHOBEN)
- [x] Default access_all=false (UX-Fix)

### Phase 2: Steuerung & Erweiterte Alarme (AUSSTEHEND)
- [ ] Fernsteuerung (Start/Stop/Test/Alarm-Reset)
- [ ] Schwellenwert-Konfiguration für automatische Alarme
- [ ] E-Mail/SMS-Benachrichtigungen bei Alarmen
- [ ] Alarm-Historie

### Phase 3: Erweiterungen (AUSSTEHEND)
- [ ] Admin-UI Generator erstellen/bearbeiten
- [ ] Live-Kartenansicht aller Generatoren (Leaflet)

## Tech Stack
- Backend: FastAPI, Motor (async MongoDB), GridFS
- Frontend: React 19, Tailwind CSS, Shadcn/UI, Recharts
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
        │   ├── GeneratorDashboardPage.js
        │   ├── GeneratorDetailPage.js
        │   ├── DashboardPage.js (FileShare)
        │   ├── AdminPage.js (mit Monitoring-Berechtigungen)
        │   ├── HubPage.js
        │   └── ...
        └── ...
```

## DB Collections
- users (mit apps.generator_monitoring: {enabled, access_all, generator_ids})
- generators, generator_telemetry, generator_alarms
- files, shares, password_resets

## Test Credentials
- Admin: admin@test.com / password
- Kunde: kunde@test.com / password, kunde1@test.com / password
- Mitarbeiter: ma1@test.com / password

## Prioritized Backlog
### P0
- Office 365 E-Mail-Integration (Zugangsdaten ausstehend)

### P1
- Phase 2: Generator-Fernsteuerung & Erweiterte Alarme
- Admin-UI: Generator erstellen/bearbeiten

### P2
- Live-Kartenansicht (Leaflet)
- Admin-Dateigröße-Limit pro Benutzer
- backend/server.py aufteilen (APIRouter)

### P3
- Mobile App mit Push-Benachrichtigungen
