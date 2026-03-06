# FileShare & Generator-Monitoring Portal - PRD

## Original Problem Statement
NextCloud-ähnliche Dateifreigabe-Anwendung für Eventenergie Deutschland mit Generator-Monitoring und Geräteverwaltung für DSE Aggregate.

## Core Requirements - FileShare - Status
- [x] JWT-basierte Authentifizierung (admin, mitarbeiter, kunde)
- [x] App-Berechtigungssystem (FileShare pro User)
- [x] Eigener Dateibereich + Gemeinsamer Bereich
- [x] Admin Dateien-Einsicht aller User
- [x] Ordner/Dateien teilen mit Berechtigungen
- [x] Datei-Upload mit GridFS + Drag & Drop
- [x] Ordner-Management, Share-Links, Dateivorschau
- [x] Suche in FileShare und Benutzerverwaltung
- [x] Passwort-Reset (User + Admin), EMAIL GEMOCKT
- [x] Download Workaround (Iframe-Fallback-Dialog)
- [ ] E-Mail-Versand für Passwort-Reset (Office 365 IMAP)

## Core Requirements - Generator-Monitoring - Status
### Phase 1: Datenmodell & Dashboard (ABGESCHLOSSEN)
- [x] MongoDB-Schema für Generatoren, Telemetrie, Alarme
- [x] Generator CRUD API + Telemetrie-Empfang (API-Key Auth)
- [x] Dashboard mit klickbaren Status-Karten als Filter
- [x] Generator-Karten mit Live-Telemetrie
- [x] Detail-Seite mit Messwerten + Telemetrie-Charts (Recharts)
- [x] Aktive Alarme mit Quittier-/Beheben-Funktion
- [x] Kartenansicht mit Leaflet/OpenStreetMap (farbige Marker nach Status)
- [x] Berechtigungssteuerung (alle/einzelne Generatoren pro User)
- [x] Weißer Hintergrund, Lila/Fuchsia Akzente, Logo

### Phase 2: Steuerung & Erweiterte Alarme (AUSSTEHEND)
- [ ] Fernsteuerung (Start/Stop/Test/Alarm-Reset)
- [ ] Schwellenwert-Konfiguration, Alarm-Historie

## Core Requirements - Geräteverwaltung - Status (ABGESCHLOSSEN 06.03.2026)
- [x] Gerätetypen: Stromerzeuger, Lichtmast, Messkoffer, Kirmeskiste
- [x] Gemeinsame Felder: Seriennummer, Benutzerfeld (Freitext, suchbar), GPS
- [x] Stromerzeuger/Lichtmast: Modell, Motor (Hersteller/Typ/Nummer), Generator (Hersteller/Typ/Nummer), Baujahr, Leistung, Steuerung
- [x] Wartungsfelder: Letzte/Nächste Wartung (überfällig-Anzeige)
- [x] Dokumentenablage pro Gerät (Upload/Download/Löschen via GridFS)
- [x] Gerät kopieren (Seriennummer → KOPIE-, Motor/Generatornummer geleert)
- [x] Suche + Typfilter, Admin-Only
- [x] Hub-Button "Geräteverwaltung" für Admins

## Architecture
```
/app/backend/
├── server.py (FileShare API + Router init)
└── routes/
    ├── generators.py (Monitoring API)
    └── devices.py (Geräteverwaltung API)
/app/frontend/src/pages/
├── HubPage.js (4 Buttons: FileShare, Monitoring, Geräteverwaltung, Benutzer)
├── GeneratorDashboardPage.js (mit Karte + klickbare Stats)
├── GeneratorDetailPage.js
├── DeviceManagementPage.js (CRUD + Copy + Docs)
├── AdminPage.js (mit Monitoring-Berechtigungen)
└── ...
```

## DB Collections
- users, files, shares, password_resets
- generators, generator_telemetry, generator_alarms
- devices, device_documents

## Test Credentials
- Admin: admin@test.com / password
- Kunde: kunde@test.com / password, kunde1@test.com / password

## Prioritized Backlog
### P0 - Office 365 E-Mail-Integration (Zugangsdaten ausstehend)
### P1 - Messkoffer/Kirmeskiste Datensatz (technisch gleich wie Stromerzeuger)
### P1 - Phase 2: Fernsteuerung + Schwellenwert-Alarme
### P1 - DSE890/PI Datenanbindung (Datensatz folgt vom User)
### P2 - Kundenzuordnung für Geräte + Wartungsplan
### P3 - Mobile App, Backend-Refactoring
