# FileShare Portal - PRD

## Original Problem Statement
NextCloud-ähnliche Dateifreigabe-Anwendung für Eventenergie Deutschland mit:
- Benutzerverwaltung (Admin, Kunde, Mitarbeiter)
- App-Freigaben pro Benutzer (FileShare mit Dateigröße, Lesen/Schreiben)
- Eigener Dateibereich pro User + Gemeinsamer Bereich
- Admin kann alle Strukturen sehen
- Ordner und Dateien teilen mit Berechtigungen
- Deutsche Benutzeroberfläche mit Eventenergie-Logo

## User Personas
1. **Administrator** - Volle Kontrolle, Benutzerverwaltung, App-Freigaben, alle Dateien einsehen
2. **Mitarbeiter** - FileShare (wenn freigeschaltet), je nach Berechtigung Lesen/Schreiben
3. **Kunde** - Selbst-Registrierung, FileShare nur nach Admin-Freigabe

## Core Requirements
- [x] JWT-basierte Authentifizierung
- [x] Benutzerrollen (admin, mitarbeiter, kunde)
- [x] **NEU: App-Berechtigungssystem (FileShare pro User aktivierbar)**
- [x] **NEU: FileShare-Optionen: Max. Dateigröße, Schreiben, Löschen**
- [x] **NEU: Eigener Dateibereich pro User**
- [x] **NEU: Gemeinsamer Bereich (mit Berechtigungen)**
- [x] **NEU: Admin kann alle User-Dateien einsehen**
- [x] **NEU: Ordner teilen mit Berechtigungen (Download/Upload/Bearbeiten)**
- [x] Datei-Upload mit GridFS
- [x] Ordner-Management (erstellen, löschen)
- [x] Share-Links mit Ablaufdatum und Passwortschutz
- [x] Deutsche Oberfläche mit Eventenergie-Logo
- [x] Hub-Seite nach Login

## Implementation Status (05.03.2026)
### Completed - Iteration 3
- **Logo**: Eventenergie Deutschland Logo auf allen Seiten
- **Benutzerverwaltung**:
  - App-Freigaben pro User (FileShare aktivieren/deaktivieren)
  - FileShare-Optionen: Max. Dateigröße, Schreiben, Löschen
- **Dateibereiche**:
  - "Mein Bereich" - Eigener Dateibereich pro User
  - "Gemeinsamer Bereich" - Für alle (mit Berechtigungen)
  - Admin kann alle User-Dateien im Admin-Panel einsehen
- **Ordner-Funktionen**:
  - Ordner erstellen/löschen funktioniert
  - Ordner teilen mit Berechtigungen
- **Share-System**:
  - Download erlauben
  - Upload erlauben (für Ordner)
  - Bearbeiten/Löschen erlauben (für Ordner)

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

## Prioritized Backlog
### P0 (Critical) - Erledigt
- ✅ App-Berechtigungssystem
- ✅ Dateibereiche (Eigen/Gemeinsam)
- ✅ Ordner teilen mit Berechtigungen

### P1 (High) - Nächste Phase
- Dateivorschau (PDF, Bilder)
- Email-Benachrichtigungen
- Weitere Module im Hub

### P2 (Medium)
- Datei-Versioning
- Activity Log/Audit Trail
- Erweiterte Suchfunktion

## Next Tasks
1. Weitere Module für den Hub entwickeln
2. Dateivorschau implementieren
3. Email-Benachrichtigungen hinzufügen
