# Eventenergie Portal - Update-Anleitung

## Schnell-Update (3 Schritte)

### 1. Code auf den Server bringen

**Option A: Git (empfohlen)**
```
cd C:\eventenergie
git pull origin main
```

**Option B: ZIP**
- ZIP entpacken nach `C:\eventenergie`
- Bestehende `.env` Dateien NICHT ueberschreiben!

### 2. Update ausfuehren
```
Rechtsklick auf update.bat -> Als Administrator ausfuehren
```

Das Script macht automatisch:
- Backup der aktuellen Installation
- Abhaengigkeiten installieren
- Datenbank-Migration
- Dienste neu starten

### 3. Pruefen
- Backend: http://localhost:8001/api/health
- Frontend: http://localhost:3000

---

## Was hat sich geaendert? (ab 19.03.2026 18:00)

### Neue Features
- **Tankbeleg Pi Script** - Raspberry Pi Drucker-Emulator
- **Mosquitto MQTT Broker** - Self-Hosted Setup mit TLS
- **Serviceplan** - PDF-Upload + reduzierter Plan fuer Messkoffer/Kirmeskiste
- **Artikel positionieren** - Status (gestellt/abgebaut) + Detail-Modal mit Karte

### Datenbank-Aenderungen (automatisch per migrate_db.py)
- `order_assets`: Neues Feld `status` (placed/dismantled)
- `maintenance_entries`: Neues Feld `attachments` (PDF-Metadaten)
- Neue Indizes fuer bessere Performance

### Neue Dateien
```
backend/
  migrate_db.py              <- Datenbank-Migration
  static/
    tankbeleg_pi.py          <- Pi Script
    tankbeleg_pi.conf        <- Pi Konfiguration
    tankbeleg_pi.service     <- Pi Systemd Service
    tankbeleg_simulator.py   <- Pi Test-Suite
    setup_tankbeleg_pi.sh    <- Pi Installation
    mosquitto_eventenergie.conf  <- MQTT Broker Config
    setup_mosquitto.sh       <- MQTT Broker Installation
    update.bat               <- Dieses Update-Script
    start_services.bat       <- Dienste starten
    stop_services.bat        <- Dienste stoppen
```

---

## Dienste verwalten

### Starten
```
start_services.bat
```

### Stoppen
```
stop_services.bat
```

### Fuer Produktion (PM2 empfohlen)
```
npm install -g pm2
pm2 start ecosystem.config.js
pm2 save
pm2 startup
```

---

## Wichtig: .env Dateien

Die `.env` Dateien enthalten Ihre Zugangsdaten und duerfen
NICHT ueberschrieben werden. Falls sie verloren gehen:

**backend/.env** muss enthalten:
```
MONGO_URL=mongodb://...
DB_NAME=eventenergie_db
JWT_SECRET=...
STRIPE_SECRET_KEY=...
(weitere Keys)
```

**frontend/.env** muss enthalten:
```
REACT_APP_BACKEND_URL=https://ihre-domain.de
```

---

## Bei Problemen

1. Logs pruefen (Backend-Fenster oder PM2 logs)
2. `update.bat` nochmal ausfuehren
3. Backup wiederherstellen: `C:\eventenergie\backups\`
