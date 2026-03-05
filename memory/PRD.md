# FileShare Portal - PRD

## Original Problem Statement
NextCloud-ähnliche Dateifreigabe-Anwendung für Eventenergie Deutschland mit:
- Benutzerverwaltung (Admin, Kunde, Mitarbeiter)
- Datei-Upload/Download mit konfigurierbaren Limits
- Share-Links mit Passwortschutz
- Deutsche Benutzeroberfläche
- Design: Weißer Hintergrund, Eventenergie Branding, zentrale Anmeldebox

## User Personas
1. **Administrator** - Volle Kontrolle, Benutzerverwaltung, System-Statistiken
2. **Mitarbeiter** - Datei-Upload/Download, Share-Links erstellen
3. **Kunde** - Kann sich selbst registrieren, braucht Admin-Freigabe

## Core Requirements
- [x] JWT-basierte Authentifizierung
- [x] Benutzerrollen (admin, mitarbeiter, kunde)
- [x] Datei-Upload mit GridFS
- [x] Ordner-Management
- [x] Share-Links mit Ablaufdatum
- [x] Passwortgeschützte Shares
- [x] Kunden-Upload über Share-Links
- [x] Admin-Dashboard mit Statistiken
- [x] Benutzerverwaltung (CRUD)
- [x] Upload-Limits pro Benutzer
- [x] Deutsche Oberfläche
- [x] Selbst-Registrierung für Kunden
- [x] Hub-Seite nach Login

## Implementation Status (05.03.2026)
### Completed - Iteration 2
- Neues Design: Weißer Hintergrund, Eventenergie Branding
- Hub-Seite: Zentrale Navigationsseite nach Login
  - FileShare Button (alle User)
  - Benutzerverwaltung Button (nur Admin)
  - Platzhalter für zukünftige Funktionen
- Selbst-Registrierung für Kunden aktiviert
- Zurück-Navigation von FileShare/Admin zum Hub

### Tech Stack
- Backend: FastAPI, Motor (async MongoDB), GridFS
- Frontend: React 19, Tailwind CSS, Shadcn/UI
- Database: MongoDB
- Auth: JWT + bcrypt

## Navigation Flow
1. Login/Register → Hub
2. Hub → FileShare (Dateiverwaltung)
3. Hub → Admin (nur für Admins)
4. FileShare/Admin → Hub (Zurück-Button)

## Prioritized Backlog
### P0 (Critical) - Erledigt
- ✅ Core file sharing functionality
- ✅ Hub page with module selection

### P1 (High) - Nächste Phase
- Dateivorschau (PDF, Bilder)
- Email-Benachrichtigungen bei Downloads
- Weitere Module im Hub

### P2 (Medium)
- Datei-Versioning
- Activity Log/Audit Trail
- Erweiterte Suchfunktion

## Next Tasks
1. Weitere Module für den Hub entwickeln
2. Email-Benachrichtigungen hinzufügen
3. Dateivorschau implementieren
