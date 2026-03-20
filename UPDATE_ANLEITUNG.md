# Eventenergie Portal - Update & Betrieb

## Schnell-Update (empfohlen)

1. **Update-Paket herunterladen** (Admin → Einstellungen → "Server Update-Paket")
2. **ZIP entpacken** an beliebige Stelle (z.B. `C:\Downloads\`)
3. **`update.bat` doppelklicken** (Als Administrator ausfuehren)
4. Das Script erkennt automatisch den Quellordner und fuehrt alles durch:
   - Sichert .env Dateien
   - Erstellt DB-Backup (mongodump)
   - Stoppt laufende Dienste
   - Aktualisiert Backend + Frontend
   - Installiert neue Abhaengigkeiten
   - Erstellt neuen Frontend-Build
   - Startet alle Dienste automatisch

## Geschuetzte Dateien (werden NIE ueberschrieben)

- `backend\.env` - Datenbank, SMTP, alle Zugangsdaten
- `frontend\.env` - Portal-URL
- MongoDB Daten - komplett unberuehrt
- `node_modules` - werden nur ergaenzt

## Dienste starten / stoppen

### Starten
```
C:\eventenergie\start-all.bat
```
Macht automatisch:
1. Stoppt alte Prozesse
2. Startet MongoDB (falls nicht aktiv)
3. Erstellt Sicherheits-Backup der Datenbank
4. Prueft Python venv
5. Prueft Frontend Build
6. Startet Backend (uvicorn, Port 8001)
7. Startet Caddy (Reverse Proxy, Port 3000)

### Stoppen
```
C:\eventenergie\stop-all.bat
```
Stoppt Backend, Caddy und alle Portal-Prozesse.

## Caddy Reverse Proxy

Caddy ersetzt `npx serve` und bietet:
- Statische Frontend-Dateien ausliefern
- API-Anfragen (`/api/*`) an Backend weiterleiten
- Kein CORS-Problem zwischen Frontend und Backend

### Installation (einmalig)
1. Caddy herunterladen: https://caddyserver.com/download (Windows amd64)
2. `caddy.exe` nach `C:\eventenergie\` kopieren
3. `Caddyfile` liegt bereits im Hauptordner

## Backup-System

Das Portal erstellt automatisch Backups:
- **Datenbank-Backup:** via `mongodump` (Standard: alle 12 Stunden)
- **Quellcode-Backup:** als ZIP (Standard: alle 3 Tage)
- **Aufbewahrung:** Alte Backups werden nach 7 Tagen automatisch geloescht
- **Konfiguration:** Admin → Einstellungen → Backup-System

### Manuelles Backup
- Ueber die Admin-UI: "Datenbank jetzt sichern" / "Quellcode jetzt sichern"
- Beim jedem Start (`start-all.bat`) wird automatisch ein DB-Backup erstellt

### Backup-Speicherort
```
C:\eventenergie\backups\
  db\          - Datenbank-Backups (.gz)
  files\       - Quellcode-Backups (.zip)
  code\        - Pre-Update Code-Backups (.zip)
```

### Datenbank wiederherstellen
```
mongorestore --uri="mongodb://localhost:27017" --db=eventenergie --archive=PFAD_ZUM_BACKUP.gz --gzip --drop
```

## Verzeichnisstruktur
```
C:\eventenergie\
  backend\         - FastAPI Server
    .env           - Datenbank + SMTP Konfiguration
    server.py      - Hauptserver
    routes\        - API-Routes
    services\      - Dienste (PDF etc.)
    static\        - Downloads, Pi-Scripts
  frontend\        - React Frontend
    .env           - Portal-URL
    src\           - Quellcode
    build\         - Kompiliertes Frontend
  backups\         - Automatische Backups
  caddy.exe        - Reverse Proxy
  Caddyfile        - Caddy-Konfiguration
  start-all.bat    - Dienste starten
  stop-all.bat     - Dienste stoppen
  update.bat       - Automatisches Update
```

## Fehlerbehebung

### Portal nicht erreichbar
1. `start-all.bat` als Administrator ausfuehren
2. Pruefen ob MongoDB laeuft: `sc query MongoDB`
3. Pruefen ob Backend laeuft: `curl http://localhost:8001/api/health`
4. Pruefen ob Caddy laeuft: `curl http://localhost:3000`

### Login funktioniert nicht
1. Pruefen ob `frontend\.env` korrekt ist: `REACT_APP_BACKEND_URL=https://portal.eventenergie.com`
2. Frontend neu bauen: `cd C:\eventenergie\frontend && npm run build`
3. Dienste neu starten: `stop-all.bat` dann `start-all.bat`

### Datenbank-Problem
1. Backup wiederherstellen (siehe oben)
2. MongoDB-Service pruefen: `sc query MongoDB`
3. MongoDB-Logdatei pruefen: `C:\Program Files\MongoDB\Server\X.X\log\`
