# SSL/HTTPS Live-Server mit Caddy 2 + Let's Encrypt (Windows)

**Ziel:** Kostenloses, automatisch erneuertes Zertifikat fuer `www.eventenergie.app`
statt kostenpflichtiges IONOS-Zertifikat.

## Dateien in diesem Repo

- `Caddyfile.production` - Neue Config fuer den Live-Server (Let's-Encrypt + Redirect)
- `Caddyfile` - Alte Config (bleibt drin als Referenz; kann nach erfolgreichem
  Umstieg archiviert werden)

## Vorbereitung auf dem Live-Server (Windows)

1. **DNS-A-Records bei IONOS** (nur DNS, nicht SSL) muessen zeigen auf die
   Server-IP:
   - `eventenergie.app`     -> Server-IP
   - `www.eventenergie.app` -> Server-IP

2. **Firewall/Router**: Diese Ports von aussen offen:
   - **80/tcp**  (ACME HTTP-01 Challenge - Pflicht!)
   - **443/tcp** (HTTPS)
   - **443/udp** (HTTP/3, optional)

3. **Caddy laeuft bereits als Windows-Service**? Falls nein:
   ```
   winget install CaddyServer.Caddy
   ```
   oder Zip von https://caddyserver.com/download -> nach `C:\Program Files\Caddy\`.

## Umstieg (Schritt fuer Schritt)

```
:: 1. Backup der aktuellen Config
copy C:\eventenergie\Caddyfile C:\eventenergie\Caddyfile.iOnos-backup

:: 2. Neue Config aktivieren
copy C:\eventenergie\Caddyfile.production C:\eventenergie\Caddyfile

:: 3. Caddy neu laden (holt automatisch Zertifikat)
:: Wenn als Service laeuft:
net stop caddy && net start caddy
:: Oder wenn manuell:
caddy reload --config C:\eventenergie\Caddyfile

:: 4. Log verfolgen ob Zertifikat da ist
type C:\eventenergie\logs\caddy_access.log
:: Alternativ Caddy-eigenes Log:
type C:\ProgramData\Caddy\caddy.log
```

Erfolgs-Indikator im Log: **"certificate obtained successfully"**.

## Verifikation

```
curl -I https://www.eventenergie.app
::  Erwartet: HTTP/2 200

curl -I https://eventenergie.app
::  Erwartet: HTTP/2 301 Location: https://www.eventenergie.app/
```

Im Browser: gruenes Schloss, Aussteller "Let's Encrypt", nicht mehr IONOS.

## Frontend/Backend Umgebungsvariablen

Falls die App noch die alte Ionos-URL oder http verwendet:

- `frontend/.env.production`: `REACT_APP_BACKEND_URL=https://www.eventenergie.app`
- Frontend-Build neu erzeugen: `cd frontend && yarn build`
- Backend CORS pruefen: `allow_origins=["https://www.eventenergie.app"]`

## IONOS-Zertifikat kuendigen

Wenn HTTPS funktioniert + Browser gruenes Schloss zeigt:
- IONOS-Kundenportal -> SSL-Vertrag fuer eventenergie.app kuendigen
- DNS-Eintraege bei IONOS BEHALTEN (die brauchen wir weiterhin)

## Wo speichert Caddy die Zertifikate?

Windows-Default:
```
C:\Users\<user>\AppData\Roaming\Caddy\
```
Bei Windows-Service als System-User:
```
C:\ProgramData\Caddy\
```

**Wichtig:** Diesen Ordner NICHT loeschen und regelmaessig sichern. Enthaelt
ACME-Account + gueltige Zertifikate. Bei Verlust muss neu ausgestellt werden
(Let's Encrypt Rate-Limit: 5/Woche/Domain).

Backup:
```
:: Wchentlich in ein Backup-Verzeichnis kopieren
xcopy C:\ProgramData\Caddy D:\Backups\Caddy /E /I /Y
```

## Wartung: Nichts.

Caddy erneuert Zertifikate ~30 Tage vor Ablauf automatisch. Kein Cron,
kein manueller Eingriff noetig. Solange Port 80 offen + DNS korrekt.

## Rollback (falls Probleme)

```
:: Zurueck zu IONOS-Config
copy C:\eventenergie\Caddyfile.ionos-backup C:\eventenergie\Caddyfile
net stop caddy && net start caddy
```

## Troubleshooting

| Symptom | Loesung |
|---------|---------|
| `no such host` bei ACME | DNS bei IONOS pruefen, propagation abwarten |
| `connection refused` Port 80 | Windows-Firewall + Router-Port-Forwarding |
| `403 Forbidden` von Backend | `allow_origins` erweitern in FastAPI |
| Login geht nicht mehr | `REACT_APP_BACKEND_URL` aktualisieren + neu builden |
| `too many failed authorizations` | 1 Stunde warten, dann erneut |
