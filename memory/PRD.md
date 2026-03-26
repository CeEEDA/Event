# Eventenergie Portal - PRD

## Original Problem Statement
Umfassendes "Kirmes" (Jahrmarkt) Abrechnungssystem mit Tankbeleg-Digitalisierung, Auftragsverwaltung, Energiemonitoring, Zahlungsabwicklung und mehr.

## Core Architecture
- **Frontend:** React (CRA) + Tailwind CSS + Shadcn/UI
- **Backend:** FastAPI (Python) + MongoDB + GridFS
- **Desktop:** Electron Wrapper
- **External APIs:** EpiRent (ERP), Stripe (Payments), MQTT, OpenStreetMap
- **Server:** nginx (HTTPS/443) -> Caddy (HTTP/8001) -> FastAPI (8002)
- **Firewall:** FortiGate VIP (static-nat, extern 443 -> 172.20.80.5:443)

## Network Architecture
```
Internet -> DNS (eventenergie.app -> 217.86.214.29)
         -> FortiGate VIP (static-nat, Port 443 -> 172.20.80.5:443)
         -> nginx (SSL/TLS auf Port 443)
         -> Caddy (HTTP auf Port 8001)
         -> FastAPI (Backend auf Port 8002)
         -> MongoDB (Port 27017)
```

## FortiGate Konfiguration
- wan1 IP: 192.168.0.128 (DHCP, hinter Router)
- Server VLAN: VLAN80_VPN-Strm (172.20.80.x)
- Admin VLAN: VLAN100_Admin (172.20.100.x)
- WLAN VLAN: VLAN110_WLAN (172.20.110.x)
- Server VLAN: VLAN200_Server (172.20.200.x)
- WICHTIG: wan1 allowaccess darf NICHT https enthalten (sonst faengt FortiGate Port 443 ab)
- VIP Rule 142: EEG_Portal HTTPS2, static-nat, extern 443 -> 172.20.80.5:443

## What's Been Implemented

### Phase 1 - Portal Grundfunktionen (abgeschlossen)
- Auth, Auftragsverwaltung, Energiemonitoring, Zahlungen, QR, Rechnungen, Admin, Desktop

### Phase 1b - Tankbeleg Portal UI (abgeschlossen)
- CRUD, PDF, Auto-Nummerierung, GPS-Karte, Admin-Funktionen

### Phase 1c - EpiRent API Optimierung (abgeschlossen)
- Background-Sync, Cache, Manueller Sync, Adress-Ueberschreibung

### Phase 2 - Tankbeleg Pi Script (abgeschlossen)
- ESC/POS Parser, Serial, GPS, SQLite, Auto-Sync, 48 Tests

### Self-Hosted MQTT Broker (abgeschlossen)
- Mosquitto + Let's Encrypt TLS, 3 Listener

### Serviceplan Anpassungen (abgeschlossen)
- Messkoffer/Kirmeskiste: Reduzierter Plan, PDF + Bilder Upload (max 25 MB)

### Artikel positionieren - Status & Detail (abgeschlossen - 2026-03-19)
- Zeilen-Farbe, Abgebaut-Button, Detail-Modal mit OSM-Karte, PATCH Toggle-Endpoint

### Server Deployment Tools (abgeschlossen - 2026-03-20)
- Safe Update-Paket Export, Caddy Reverse Proxy, .env Templates, Hardcoded Fallback URL

### Backup-System (abgeschlossen - 2026-03-20)
- DB-Backup via mongodump (gzip), Quellcode-Backup (ZIP)
- Konfigurierbares Intervall, Aufbewahrungsrichtlinie, Manuelles Backup
- Admin UI mit Toggles, Intervall-Inputs, Backup-Liste
- Hintergrund-Scheduler (15 Min Pruefintervall)

### Start/Update/Stop Scripts (Fix - 2026-03-23)
- Root Cause: Deutsches Windows gibt "ABHOEREN" statt "LISTENING" in netstat
- Fix: Locale-unabhaengige Port-Erkennung via findstr "0.0.0.0:PORT" + for /f
- Ergebnis: Alle Dienste korrekt erkannt [3/3] - Backend, Caddy, nginx, Mosquitto
- CRLF-Zeilenumbrueche, [XX] statt [!!] (delayed expansion Bug), goto-Loops statt for/l

### HTTPS/SSL Externer Zugang (abgeschlossen - 2026-03-24)
- nginx fuer TLS-Terminierung auf Port 443
- DNS A-Record auf 217.86.214.29 konfiguriert
- Windows Firewall Regel fuer Port 443
- FortiGate VIP (static-nat) konfiguriert: extern 443 -> 172.20.80.5:443
- FortiGate wan1 allowaccess: https ENTFERNT (damit VIP Port 443 durchlaesst)
- FortiGate Recovery nach Aussperrung via Console + Factory Reset + Backup Restore
- Portal extern erreichbar unter https://eventenergie.app

### Kirmeskiste Pi Auto-Registrierung (abgeschlossen - 2026-03-24)
- Ingest-Endpoint `/api/energy-monitoring/ingest` registriert unbekannte Meter automatisch
- Bedingung: Geraet muss existieren UND device_key muss gueltig sein
- Meter wird mit Name "Auto-registriert (Geraetname)" angelegt
- Keine Duplikate bei wiederholtem Ingest
- Sicherheit bleibt gewahrt: Falsche Keys und unbekannte Geraete werden weiterhin abgelehnt

### MQTT Gateway-Zugangsdaten pro Geraet (abgeschlossen - 2026-03-24)
- Jedes DSE-Gateway (Stromerzeuger/Lichtmast) bekommt eigene MQTT-Credentials
- Credentials werden im Portal im "Geraet bearbeiten" Dialog generiert (DSE890 Sektion)
- Mosquitto passwd-Datei wird automatisch aktualisiert (PBKDF2-SHA512 $7$ Format)
- Backend .env Variable: MOSQUITTO_PASSWD_FILE (Pfad zur Mosquitto passwd-Datei)
- Auf Server setzen: MOSQUITTO_PASSWD_FILE=C:\Program Files\Mosquitto\passwd
- Backend MQTT Config auf 127.0.0.1:1884 (lokaler Listener, keine Auth noetig)
- Endpoints: GET/POST/DELETE /api/mqtt/device-credentials/{device_id}
- Auch verfuegbar auf der MQTT-Config-Seite fuer Generatoren
- Zaehlerstaende-Anzeige korrigiert (E_imp_kWh/P_sum_kW statt falsche Feldnamen)

### DSE Remote Control Fix (abgeschlossen - 2026-03-25)
- P0 Bug: "Generator nicht gefunden" beim Start/Stop von DSE-Geraeten behoben
- Root Cause 1: KeyError `dse_cmd["description"]` statt `dse_cmd["label"]`
- Root Cause 2: `gen.get("name")` NoneType-Fehler im Legacy-Pfad wenn Device statt Generator
- Fix: Control-Endpoint erkennt `dev-{device_id}` korrekt und baut MQTT-Topic via dse_module_uid

### DSE Remote Control Modbus-Register Fix (abgeschlossen - 2026-02-05)
- P0 Bug: Payload nutzte falsche Modbus-Register (P003/R000 statt P016/R008+R009)
- Root Cause: DSE_COMMANDS wurde auf key/complement aktualisiert, aber Payload-Konstruktion referenzierte noch `dse_cmd["value"]` (KeyError) und falsche Register
- Fix: Beide Code-Pfade (Device + Gateway) korrigiert auf `{uid: {"P016": {"R008": key, "R009": complement}}}`
- DSE Gencomm Protocol: System Control Key auf Register 4104 + Complement auf Register 4105
- Befehle: start(35705), stop(35700), auto_on(35701), manual(35702), mute(35706), reset(35707)

### Device Offline-Erkennung (abgeschlossen - 2026-03-25)
- P1 Bug: Online-Status aktualisierte sich nicht wenn Geraete offline gingen
- Loesung: Timeout-basierter Hintergrund-Task (alle 60s, Timeout: 5min)
- Markiert Geraete und Generatoren automatisch als "offline" wenn kein last_seen innerhalb 5min
- Virtuelle Generatoren uebernehmen jetzt mqtt_status, last_seen, GPS-Koordinaten vom Device

## Key API Endpoints
- `/api/backup/settings` - GET/POST Backup-Einstellungen
- `/api/backup/list` - GET Backup-Liste
- `/api/backup/trigger/db` - POST DB-Backup ausloesen
- `/api/backup/trigger/files` - POST Dateien-Backup ausloesen
- `/api/backup/{id}` - DELETE Backup loeschen
- `/api/backup/{id}/download` - GET Backup herunterladen
- `/api/download/update-package` - GET Update-Paket ZIP
- `/api/devices/stats/quick/{device_id}` - GET Telemetrie-Daten
- `/api/mqtt/credentials` - GET alle Gateway-Credentials auflisten
- `/api/mqtt/credentials/{id}/generate` - POST Credentials generieren
- `/api/mqtt/credentials/{id}` - DELETE Credentials widerrufen
- `/api/mqtt/control/{generator_id}` - POST Steuerbefehl senden (Start/Stop/Auto)

### Serviceplan Kategorisierung + QR-Scanner (abgeschlossen - 2026-03-25)
- Kategorie-Filter: Stromerzeuger / Lichtmasten / Kirmeskisten / Verteiler / Messkoffer als Tabs
- QR-Code Scanner neben Suchleiste: Scannt Geraete-QR-Etikett und oeffnet direkt den Serviceplan
- Neuer Geraetetyp "Verteiler" im Backend und Frontend hinzugefuegt
- Status-Zaehler (Einsatzbereit, etc.) filtern jetzt auch nach Kategorie

### Mehrfachanmeldungen (abgeschlossen - 2026-03-25)
- Schausteller koennen jetzt mehrere Staende fuer dasselbe Event anmelden
- Backend: Duplikat-Pruefung entfernt (kirmes.py public/signup Endpoint)
- Frontend: "Weiteren Stand anmelden" Button auf Erfolgsseite hinzugefuegt
- Einladungs-/Anmeldelink erlaubt erneute Anmeldung

### Smartphone-Optimierung Kirmes Event-Detail (abgeschlossen - 2026-03-25)
- P0: Komplett responsive Event-Detailseite fuer Smartphone-Nutzung
- Mobile Card View: Anmeldungen als aufklappbare Karten statt Tabelle (< lg Breakpoint)
- Desktop Table View: Bestehende Tabelle bleibt fuer grosse Bildschirme (>= lg Breakpoint)
- QR-Scanner Fullscreen Overlay: Kamera-Ansicht als Vollbild-Overlay auf Mobile
- Header-Buttons: Nur Icons auf Mobile, Icons + Text auf Desktop
- "Preise pro Anschluss" Sektion entfernt (auf Wunsch des Benutzers)
- kWh Inline-Bearbeitung auf Mobile Cards mit Einbau/Ausbau Feldern
- Event-Info-Karten: 2x2 Grid auf Mobile, 4-spaltig auf Desktop
- Telefon-Links klickbar auf Mobile (tel: Link)

### Event-Log (Ereignisprotokoll) auf 3 Seiten (abgeschlossen - 2026-03-25)
- Event-Log Ingest-Fehler behoben (Auth-Key Problem)
- Wiederverwendbare EventLog-Komponente erstellt (`/app/frontend/src/components/EventLog.js`)
- Ereignisprotokoll in GeneratorDetailPage, Geraeteverwaltung (DeviceManagementPage) und Serviceplan (ServiceplanPage) integriert
- Events: Motor Start/Stop, Uebertemperatur, Niedriger Oeldruck, Unterfrequenz, Not-Aus, Generator Zu/Abschalten, Modbus-Disconnect
- GPS-Positionen und Zeitstempel bei jedem Event
- Kompakter Modus fuer eingebettete Ansichten (Geraeteverwaltung, Serviceplan)
- Backend-APIs: GET /api/generators/events/{generator_id}, GET /api/generators/events-by-device/{device_id}
- 100% getestet (Backend 7/7, Frontend alle 3 Seiten verifiziert)

## Prioritized Backlog

### P1 - Kommend
- PayPal Integration

### P2 - Backlog
- Diagnose-Feature fuer Zaehler (letzte 10 Rohwerte anzeigen)
- Chromium Translate Popup auf Raspberry Pi (Policy-Datei erstellen)
- Admin File Size Limits fuer Uploads
- Windows Installer (.exe) fuer Electron Desktop App
- Health-Check / Monitoring fuer Portal-Erreichbarkeit

### DSE 5510 Sentinel-Wert Fix (abgeschlossen - 2026-03-26)
- P0 Bug: GenComm Sentinel-Werte (0x7FFB=32763, 0xFFFB=65531) loesten Fehlalarme aus bei ausgeschaltetem Generator
- Root Cause: `read_uint16()` filterte nur `GENCOMM_NA_VALUES`, nicht `GENCOMM_NA_SIGNED` -> 32763 wurde als gueltige Temperatur interpretiert
- Fix 1: `read_uint16()` filtert jetzt auch `GENCOMM_NA_SIGNED` Werte
- Fix 2: Alarm-Logik mit Plausibilitaetsgrenzen abgesichert (Temp 1-300C, Oeldruck 1-2000kPa, Batterie 1-50V)
- Neuer Endpoint: GET /api/generators/dse5510-sync fuer direkten Skript-Download

### DSE 5510 via RS232 + Pi (abgeschlossen - 2026-03-25)
- Pi Sync-Skript (`dse5510_sync.py`): Liest DSE 5510 via RS232 Modbus RTU (GenComm Pages 4/6/7/16)
- Setup-Skript Generator (`POST /api/energy-monitoring/devices/{device_id}/dse5510-setup`)
- Telemetrie-Ingest per HTTPS (`POST /api/generators/ingest` mit device_key Auth)
- Steuerungsbefehle: Stop, Auto, Manuell, Start, Gen EIN, Gen AUS (via Pi Command Queue)
- GPS-Unterstuetzung via gpsd
- DSE5510PiSetupSection im Frontend mit Serieller Port, Baud Rate, Slave ID Konfiguration
- Telemetrie-Normalisierung: Pi-Felder auf Frontend-kompatible Namen gemappt
- Gen EIN/AUS Buttons auf Generator-Detailseite

### Refactoring (erledigt - 2026-02-05)
- old_device_ids Code komplett entfernt (Backend: DeviceCreate Model, add-alias Endpoint, Ingest Fallback; Frontend: FormData)
- Ungenutzte Variablen in mqtt_service.py bereinigt (client_name, result, topic_lower)
- MQTT-Matching: Case-insensitive Vergleich und Whitespace-Trimming hinzugefuegt

## Credentials
- Admin (lokal): admin@test.com / password
- Admin (Server): christian.ecker@eventenergie-deutschland.de / qivbeb-Wodha1-sewram
- SMTP: portal@eventenergie.app / :PlN4sFf:}6AY (smtp.ionos.de, Port 465)

## Known Issues (resolved)
- FortiGate wan1 allowaccess hatte https aktiv -> FortiGate Admin fing Port 443 ab statt VIP
- Deutsches Windows: netstat gibt ABHOEREN statt LISTENING aus
- Batch Script: delayed expansion !! wird als leere Variable interpretiert
- Control-Endpoint: KeyError dse_cmd["description"] -> korrigiert zu dse_cmd["label"]
- Control-Endpoint: NoneType gen.get("name") wenn Device ohne Generator -> entity fallback
- Virtuelle Generatoren hatten immer Status "standby" statt echtem mqtt_status
