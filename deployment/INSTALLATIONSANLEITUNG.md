# Eventenergie Portal - Installationsanleitung Windows 11
# Server: 217.86.214.29

---

## 1. Software installieren

### 1.1 Python 3.11
- Download: https://www.python.org/downloads/release/python-3119/
- "Windows installer (64-bit)" waehlen
- WICHTIG: Haken bei "Add Python to PATH" setzen!
- "Install Now" klicken

### 1.2 Node.js 20 LTS
- Download: https://nodejs.org/en/download/
- "Windows Installer (.msi) 64-bit" waehlen
- Standard-Installation durchfuehren
- Danach in PowerShell: `npm install -g yarn`

### 1.3 MongoDB 7.0 Community Server
- Download: https://www.mongodb.com/try/download/community
- Version 7.0, Platform: Windows, Package: MSI
- "Complete" Installation waehlen
- "Install MongoDB as a Service" aktivieren (Standard)
- MongoDB Compass (GUI) optional mitinstallieren
- Startet automatisch als Windows-Dienst auf Port 27017

### 1.4 Caddy (Reverse Proxy mit Auto-HTTPS)
- Download: https://caddyserver.com/download
- Platform: Windows amd64
- Die heruntergeladene .exe nach `C:\Caddy\caddy.exe` verschieben

### 1.5 Git
- Download: https://git-scm.com/download/win
- Standard-Installation

### 1.6 NSSM (Windows Service Manager)
- Download: https://nssm.cc/download
- Die nssm.exe nach `C:\nssm\nssm.exe` kopieren
- Wird benoetigt um Backend/Frontend als Windows-Dienste zu registrieren

---

## 2. Ports fuer Firewall freigeben

| Port | Richtung | Protokoll | Zweck |
|------|----------|-----------|-------|
| **443** | Eingehend | TCP | HTTPS - Hauptanwendung + API + Stripe Webhooks + Pi-Sync |
| **80** | Eingehend | TCP | HTTP - Weiterleitung auf HTTPS |

### Nur ausgehend (keine Firewall-Regel noetig):
| Port | Zweck |
|------|-------|
| 1883 | MQTT ausgehend zu broker.hivemq.com (DSE Generatoren) |
| 465 | SMTP ausgehend zu smtp.mail.de (E-Mail-Versand) |
| 443 | HTTPS ausgehend zu api.stripe.com (Zahlungen) |

### Interne Ports (NICHT nach aussen freigeben!):
| Port | Zweck |
|------|-------|
| 8001 | Backend API (nur intern, Caddy leitet weiter) |
| 3000 | Frontend Build wird statisch ausgeliefert |
| 27017 | MongoDB (nur localhost) |

---

## 3. Installation ausfuehren

PowerShell als Administrator oeffnen und ausfuehren:

```powershell
# setup.ps1 ausfuehren (siehe Datei im deployment-Ordner)
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\setup.ps1
```

---

## 4. DNS / Domain einrichten

Damit HTTPS (Let's Encrypt) funktioniert, braucht ihr eine Domain die auf 217.86.214.29 zeigt.
Beispiel: `portal.eventenergie-deutschland.de` -> A-Record -> 217.86.214.29

Alternativ: Selbstsigniertes Zertifikat (siehe Caddyfile)

---

## 5. Nach der Installation

### Stripe Webhook einrichten
1. https://dashboard.stripe.com/webhooks oeffnen
2. "+ Endpoint hinzufuegen"
3. URL: `https://portal.eventenergie-deutschland.de/api/payments/webhook/stripe`
4. Events: `checkout.session.completed`
5. Webhook-Secret (`whsec_...`) in `C:\eventenergie\backend\.env` eintragen

### Kirmeskiste Pi's umstellen
Bei der naechsten Pi-Einrichtung einfach die neue Portal-URL angeben:
`https://portal.eventenergie-deutschland.de/api`

### DSE WebNet umstellen
MQTT-Broker bleibt gleich (broker.hivemq.com).
Keine Aenderung noetig, solange der Server ausgehend Port 1883 erreichen kann.

---

## 6. Wartung

### Dienste verwalten (PowerShell als Admin):
```powershell
# Status pruefen
Get-Service eventenergie-backend, eventenergie-caddy

# Neustarten
Restart-Service eventenergie-backend
Restart-Service eventenergie-caddy

# Logs ansehen
Get-Content C:\eventenergie\logs\backend.log -Tail 50
Get-Content C:\eventenergie\logs\caddy.log -Tail 50
```

### Backup MongoDB:
```powershell
mongodump --db eventenergie --out C:\eventenergie\backups\$(Get-Date -Format 'yyyy-MM-dd')
```

### Update deployen:
```powershell
cd C:\eventenergie
git pull
pip install -r backend\requirements.txt
cd frontend && yarn install && yarn build
Restart-Service eventenergie-backend
```
