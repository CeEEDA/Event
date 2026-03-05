# FileShare Portal - PRD

## Original Problem Statement
NextCloud-ähnliche Dateifreigabe-Anwendung für Eventenergie Deutschland mit:
- Benutzerverwaltung (Admin, Kunde, Mitarbeiter)
- App-Freigaben pro Benutzer (FileShare mit Dateigröße, Lesen/Schreiben)
- Eigener Dateibereich pro User + Gemeinsamer Bereich
- Admin kann alle Strukturen sehen
- Ordner und Dateien teilen mit Berechtigungen
- Deutsche Benutzeroberfläche mit Eventenergie-Logo
- Passwort-Reset per E-Mail und Admin-Passwort-Verwaltung

## User Personas
1. **Administrator** - Volle Kontrolle, Benutzerverwaltung, App-Freigaben, alle Dateien einsehen, Passwörter verwalten
2. **Mitarbeiter** - FileShare (wenn freigeschaltet), je nach Berechtigung Lesen/Schreiben
3. **Kunde** - Selbst-Registrierung, FileShare nur nach Admin-Freigabe

## Core Requirements
- [x] JWT-basierte Authentifizierung
- [x] Benutzerrollen (admin, mitarbeiter, kunde)
- [x] App-Berechtigungssystem (FileShare pro User aktivierbar)
- [x] FileShare-Optionen: Max. Dateigröße, Schreiben, Löschen
- [x] Eigener Dateibereich pro User
- [x] Gemeinsamer Bereich (mit Berechtigungen)
- [x] Admin kann alle User-Dateien einsehen
- [x] Ordner teilen mit Berechtigungen (Download/Upload/Bearbeiten)
- [x] Datei-Upload mit GridFS
- [x] Ordner-Management (erstellen, löschen) mit Modal
- [x] Share-Links mit Ablaufdatum und Passwortschutz
- [x] Deutsche Oberfläche mit Eventenergie-Logo
- [x] Hub-Seite nach Login
- [x] Magenta/Fuchsia Farbschema
- [x] Passwort-Reset Flow (User + Admin)
- [x] Admin Passwort-Verwaltung (Setzen + Reset-Link)
- [x] Datei Download funktioniert
- [x] Datei Löschen funktioniert
- [x] Drag & Drop Upload
- [x] Dateien zwischen Ordnern verschieben
- [x] Ordner als ZIP herunterladen
- [x] Dateivorschau für PDF und Bilder
- [ ] E-Mail-Versand für Passwort-Reset (Office 365 IMAP)
- [ ] E-Mail-Benachrichtigungen

## Implementation Status (05.03.2026)
### Completed - All Tests Passing
- **File Management**: Upload, Download, Delete, Move between folders
- **Drag & Drop**: Files direkt ins Dashboard ziehen zum Hochladen
- **Ordner ZIP**: Ganze Ordner als ZIP-Datei herunterladen
- **Dateivorschau**: PDF-Viewer und Bildvorschau direkt in der App
- **Verschieben**: Dateien per Modal in andere Ordner verschieben
- **Magenta Theme**: Fuchsia-600 across all components
- **Passwort-Reset**: User Flow + Admin Flow (EMAIL MOCKED)
- **Benutzerverwaltung**: CRUD + App-Berechtigungen + Passwort-Key-Button

### Tech Stack
- Backend: FastAPI, Motor (async MongoDB), GridFS
- Frontend: React 19, Tailwind CSS, Shadcn/UI
- Database: MongoDB
- Auth: JWT + bcrypt

## Navigation Flow
1. Login/Register → Hub
2. Hub → FileShare (wenn freigeschaltet)
3. Hub → Benutzerverwaltung (nur Admin)
4. FileShare: Mein Bereich | Gemeinsamer Bereich
5. Admin: Benutzer | Dateien (alle User einsehen)

## API Endpoints
### New Endpoints
- PUT /api/files/{file_id}/move - Datei in anderen Ordner verschieben
- GET /api/folders/{folder_id}/download - Ordner als ZIP herunterladen
- GET /api/files/{file_id}/preview - Dateivorschau (Bilder/PDF)
- GET /api/folders/all - Alle Ordner (für Verschieben-Dialog)

## Prioritized Backlog
### P0 - Erledigt
- All core features implemented and tested

### P1 (High) - Nächste Phase
- Office 365 E-Mail-Integration (User gibt IMAP-Zugangsdaten)
- E-Mail-Benachrichtigungen

### P2 (Medium)
- Datei-Versioning
- Activity Log/Audit Trail
- Erweiterte Suchfunktion

### Refactoring
- backend/server.py aufteilen (APIRouter für auth, users, files)

## Test Credentials
- Admin: admin@test.com / password
- Kunde: kunde@test.com / password
