# FileShare Portal - PRD

## Original Problem Statement
NextCloud-ähnliche Dateifreigabe-Anwendung für Eventenergie Deutschland mit:
- Benutzerverwaltung (Admin, Kunde, Mitarbeiter)
- Datei-Upload/Download mit konfigurierbaren Limits
- Share-Links mit Passwortschutz
- Deutsche Benutzeroberfläche
- Design inspiriert von eventenergie-deutschland.de

## User Personas
1. **Administrator** - Volle Kontrolle, Benutzerverwaltung, System-Statistiken
2. **Mitarbeiter** - Datei-Upload/Download, Share-Links erstellen
3. **Kunde** - Dateien über Share-Links herunterladen/hochladen

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

## Implementation Status (05.03.2026)
### Completed
- Backend: FastAPI + MongoDB + GridFS
- Frontend: React + Tailwind + Shadcn/UI
- Auth: JWT mit bcrypt
- File Browser mit List/Grid View
- Share-System mit Token-URLs
- Admin-Panel mit User-Management
- Dark Industrial Theme (Orange/Gelb Akzente)
- German UI durchgehend

### Tech Stack
- Backend: FastAPI, Motor (async MongoDB), GridFS
- Frontend: React 19, Tailwind CSS, Shadcn/UI
- Database: MongoDB
- Auth: JWT + bcrypt

## Prioritized Backlog
### P0 (Critical)
- ✅ Core file sharing functionality

### P1 (High)
- Dateivorschau (PDF, Bilder)
- Bulk-Download (ZIP)
- Email-Benachrichtigungen bei Downloads

### P2 (Medium)
- Datei-Versioning
- Activity Log/Audit Trail
- Dark/Light Mode Toggle
- Erweiterte Suchfunktion

## Next Tasks
1. Dateivorschau implementieren
2. Email-Benachrichtigungen hinzufügen
3. Bulk-Operationen (mehrere Dateien löschen/downloaden)
4. Activity-Log für Admin-Panel
