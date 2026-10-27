# M-Box Lichtmast-Fernbedienung – Betrieb auf dem Windows-Server

## Architektur
```
Browser ──HTTPS/JWT──▶ Caddy ──/api/mbox/*──▶ FastAPI (routes/mbox.py)
                                               │  Berechtigung, Rate-Limit, Audit (mbox_audit)
                                               └─▶ je Gerät: node server.js  (127.0.0.1:810x)
                                                        └─OPC UA 4840─▶ Siemens S7-1214C
```
- `backend/mbox_service/` = **unveränderter** Code der SPS-Firma (server.js, texte.js, Anleitung).
  Nicht ändern ohne Rücksprache: OPC-UA-Logik, `BEFEHLE`, `BEFEHL_ARRAYS`, `EINSTELLUNGEN`, `UNTERGRENZE`.
- Das Backend startet pro Gerät vom Typ **M-Box** (Geräteverwaltung) einen Node-Kindprozess mit den
  Verbindungsdaten des Geräts (ENV: OPCUA_ENDPOINT, OPCUA_SECURITY_*, OPCUA_BENUTZER/PASSWORT, WEB_PORT).
  Ports werden ab 8101 automatisch vergeben (`mbox_port` im Gerät). Logs: `backend/mbox_service/logs/mbox_<serial>.log`
  (oder `MBOX_LOG_DIR`). Node-Binary: `MBOX_NODE_BIN` (Default `node` im PATH).
- Caddy braucht **keine** Änderung (alles läuft über `/api`).

## Installation / Update
1. Node.js LTS ≥ 20 auf dem Server (prüfen: `node --version`).
2. `update.bat` ausführen – `update-live.ps1` macht jetzt zusätzlich `npm install` in `backend\mbox_service`.
3. Netzwerk: `Test-NetConnection 192.168.0.100 -Port 4840` muss `TcpTestSucceeded : True` liefern.
4. Geräteverwaltung → Neues Gerät → Typ **M-Box** → SPS-Adresse `opc.tcp://<IP>:4840`, Security (Test: None/None), optional OPC-UA-Benutzer.
5. Power Monitoring (`/generators`) → Sektion „M-Box Lichtmasten" → Fernbedienung öffnen (`/mbox/<id>`).

## Berechtigungen
| Stufe | Wer | Darf |
|---|---|---|
| lesen | Mitarbeiter mit Modul `mbox_lesen` | Status, Meldungen, Protokoll, Zähler |
| bedienen | Mitarbeiter mit Modul `mbox_bedienen` | + Befehle, Einstellungen, Zeitschaltuhr, Audit einsehen |
| admin | Rolle admin | + Diagnose-Reiter, GPS-Test, `Wartung_Reset`, `Kundenzaehler_Reset`, `Probelauf_Start`, Dienst-Neustart, Log |
Schalter in Admin → Benutzer → Mitarbeiter bearbeiten → „M-Box Lichtmast". Standard: kein Zugriff.
Rate-Limit: 30 schreibende Befehle/min je Benutzer+Gerät. Jeder Schreibzugriff landet in `mbox_audit` (wer/was/wann/ok).

## Abnahme am Mast (Abschnitt 10 der Anleitung)
1. `/mbox/<id>` → Pille „Stand hh:mm:ss" grün, Werte erscheinen.
2. Am Panel „Fernbedienung erlaubt" aus → gelber Hinweis, Befehl ohne Wirkung.
3. „Fernbedienung erlaubt" an → Quittieren (Protokoll Code 300), Lampe 1 einzeln, Netzüberwachung (Code 345), Zeitschaltuhr-Paar speichern, Datums-Schaltzeit anlegen/löschen.
4. Admin → Audit (`GET /api/mbox/<id>/audit`) enthält die Einträge.
5. Netz zum Mast kurz trennen → „keine Verbindung", danach automatisch wieder da.

## Fehlersuche
- „Dienst aus" auf der Karte / `service_installed:false` → `npm install` in `backend\mbox_service` fehlt.
- `Zeitüberschreitung: Verbinden` → Port 4840 nicht erreichbar / OPC-UA-Server in TIA aus / Lizenz.
- `BadSecurityPolicyRejected` / `BadIdentityTokenRejected` → Security/Benutzer im Gerät passt nicht zu TIA.
- Nach TIA-Änderung der Schnittstelle: Admin → Schraubenschlüssel (Dienst neu starten) oder `POST /api/mbox/<id>/neu_verbinden`.
- Log eines Masts: `GET /api/mbox/<id>/log?lines=200` (Admin).
