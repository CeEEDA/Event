# FileShare Portal - PRD

## Original Problem Statement
NextCloud-ähnliche Dateifreigabe-Anwendung für Eventenergie Deutschland.

## Core Requirements - Status
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
- [x] **Suchfunktion in FileShare** — clientseitig, filtert Dateien/Ordner
- [x] **Suchfunktion in Benutzerverwaltung** — filtert nach Name/E-Mail
- [x] **Benutzer-Tabs: Kunden/Mitarbeiter** — getrennte Ansichten mit Zähler
- [ ] E-Mail-Versand für Passwort-Reset (Office 365 IMAP)
- [ ] E-Mail-Benachrichtigungen

## Tech Stack
- Backend: FastAPI, Motor (async MongoDB), GridFS
- Frontend: React 19, Tailwind CSS, Shadcn/UI, file-saver
- Database: MongoDB
- Auth: JWT + bcrypt

## Prioritized Backlog
### P1 - Nächste Phase
- Office 365 E-Mail-Integration (User gibt IMAP-Zugangsdaten)
- E-Mail-Benachrichtigungen

### P2
- Datei-Versioning, Activity Log, Erweiterte Suche (serverseitig)

### Refactoring
- backend/server.py aufteilen (APIRouter)

## Test Credentials
- Admin: admin@test.com / password
- Kunde: kunde1@test.com / password, kunde@test.com / password
- Mitarbeiter: ma1@test.com / password
