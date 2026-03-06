# FileShare & Generator-Monitoring Portal - PRD

## Original Problem Statement
NextCloud-ähnliche Dateifreigabe für Eventenergie Deutschland mit Monitoring, Geräteverwaltung und Serviceplanung.

## Hub-Seite Buttons
- FileShare (Kunden+Mitarbeiter mit Freigabe)
- Monitoring (Kunden+Mitarbeiter mit Freigabe)
- Geräteverwaltung (Admin+Mitarbeiter)
- Serviceplan (Admin+Mitarbeiter)
- Benutzerverwaltung (Admin)

## FileShare - ABGESCHLOSSEN
- [x] JWT Auth, 3 Rollen, App-Berechtigungen
- [x] Upload/Download, Ordner, Teilen, Vorschau, Drag & Drop
- [x] Admin-Dateieinsicht, Suche, Benutzer-Tabs
- [ ] E-Mail für Passwort-Reset (Office 365, Zugangsdaten ausstehend)

## Generator-Monitoring - ABGESCHLOSSEN
- [x] Dashboard mit klickbaren Status-Karten als Filter
- [x] Kartenansicht (Leaflet/OpenStreetMap) mit farbigen Markern
- [x] Detail-Seite mit Live-Messwerten + Charts
- [x] Alarme quittieren/beheben
- [x] Berechtigungssteuerung (alle/einzelne pro User)

## Geräteverwaltung - ABGESCHLOSSEN (06.03.2026)
- [x] 4 Gerätetypen: Stromerzeuger, Lichtmast, Messkoffer, Kirmeskiste
- [x] Alle Felder: Seriennummer, Benutzerfeld, GPS, Modell, Motor, Generator, Wartung
- [x] Gerätetyp nach Anlegen gesperrt (nur Admin änderbar)
- [x] Löschen nur Admin, Mitarbeiter: nur "Außer Betrieb"
- [x] Kopierfunktion (Seriennummer → KOPIE-, Motor/Generatornr. geleert)
- [x] Dokumentenablage pro Gerät (GridFS)
- [x] Status: Aktiv / Außer Betrieb mit Toggle
- [x] Suche + Typfilter + Statusfilter

## Serviceplan - GRUNDGERÜST (06.03.2026)
- [x] Hub-Button + Seite mit Geräteauswahl
- [ ] Wartungsplan pro Gerät anlegen (Details folgen)

## Architecture
```
/app/backend/routes/
├── generators.py (Monitoring API)
└── devices.py (Geräteverwaltung API - Admin CRUD, Mitarbeiter read+status)
/app/frontend/src/pages/
├── HubPage.js (5 Buttons, rollenbasiert)
├── GeneratorDashboardPage.js (Karte + klickbare Stats)
├── GeneratorDetailPage.js
├── DeviceManagementPage.js (rollenbasierte Aktionen)
├── ServiceplanPage.js (Grundgerüst)
├── AdminPage.js (Monitoring-Berechtigungen)
└── ...
```

## DB Collections
- users, files, shares, password_resets
- generators, generator_telemetry, generator_alarms
- devices, device_documents

## Berechtigungsmatrix
| Feature | Admin | Mitarbeiter | Kunde |
|---|---|---|---|
| Gerät anlegen/löschen/typ ändern | Ja | Nein | Nein |
| Gerät bearbeiten (Daten) | Ja | Nein | Nein |
| Gerät Außer Betrieb setzen | Ja | Ja | Nein |
| Geräte sehen | Ja | Ja | Nein |
| Dokument löschen | Ja | Nein | Nein |
| Dokument hochladen | Ja | Ja | Nein |

## Test Credentials
- Admin: admin@test.com / password
- Kunde: kunde@test.com / password, kunde1@test.com / password
- Mitarbeiter: ma1@test.com / password

## Prioritized Backlog
### P0 - Serviceplan Details (User beschreibt als Nächstes)
### P1 - DSE890/PI Datenanbindung (Datensatz folgt)
### P1 - Phase 2: Generator-Fernsteuerung
### P2 - Office 365 E-Mail (Zugangsdaten ausstehend)
### P3 - Kundenzuordnung, Mobile App
