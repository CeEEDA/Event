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
1. Node.js LTS auf dem Server (22 empfohlen, mind. 20; prüfen: `node --version`). `winget install OpenJS.NodeJS.LTS`, danach Dienst `EventenergieBackend` neu starten (PATH).
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
- „Dienst aus" auf der Karte / `service_installed:false` → Node-Pakete fehlen. Das Backend installiert sie beim Start automatisch (wenn npm gefunden wird); sonst auf der M-Box-Seite „Jetzt installieren" (Admin) oder `cd backend\mbox_service ; npm install --omit=dev`. Ausgabe: `mbox_service\logs\npm_install.log`. Der Hinweis zeigt Ordner sowie gefundenes node/npm.
- `Zeitüberschreitung: Verbinden` → Port 4840 nicht erreichbar / OPC-UA-Server in TIA aus / Lizenz.
- `BadSecurityPolicyRejected` / `BadIdentityTokenRejected` → Security/Benutzer im Gerät passt nicht zu TIA.
- Nach TIA-Änderung der Schnittstelle: Admin → Schraubenschlüssel (Dienst neu starten) oder `POST /api/mbox/<id>/neu_verbinden`.
- Log eines Masts: `GET /api/mbox/<id>/log?lines=200` (Admin).

## Pi im Lichtmast (Audio-Durchsagen + USB-GPS)
- Hardware: Raspberry Pi mit Soundkarte (USB/HAT) + USB-GPS-Antenne. Internet (LTE/WLAN) zum Portal noetig; der Pi pollt, es ist keine eingehende Verbindung erforderlich.
- Einrichtung (wie DSE 5510): Geraeteverwaltung -> M-Box -> "Pi-Setup generieren" -> wget-Befehl auf dem Pi ausfuehren. Installiert mpg123, gpsd, `/opt/mbox_pi_sync.py`, `/etc/mbox_pi.conf`, Dienst `mbox_pi`.
- Audiodateien liegen auf dem Server in `backend/mbox_service/audio/` (aktuell `testansage.mp3`) und werden automatisch auf jeden Pi synchronisiert (Manifest mit SHA-256).
- Soundkarte waehlen: `aplay -l` auf dem Pi, ALSA-Name (z.B. `hw:1,0`) im Setup-Formular eintragen. GPS pruefen: `gpsmon` / `cgps`.
- Status: Reiter "Audio" auf der M-Box-Seite (online < 20 s seit letzter Meldung, GPS-Fix, laufende Wiedergabe, letzte Befehle). Log auf dem Pi: `journalctl -u mbox_pi -f`.

## Kunden-Zuweisung
- Kunde bekommt in der Benutzerverwaltung die EpiRent-Kundennummer. Dann sieht er unter "Power Monitoring" alle M-Boxen im Umkreis (1 km, waechst in 500-m-Schritten bis "Masten laut Auftrag", max. 10 km) der Veranstaltungsadresse seiner heute aktiven Auftraege (Dispo-Zeitraum). Position des Masts = Pi-GPS, sonst Koordinaten am Geraet.
- Kunde darf nur Licht (Lampen, Schnellstart/-stop, Quittieren) und Durchsagen. Manuelle Korrektur in der Auftrags-Kachel "M-Box Lichtmasten" (zuweisen / ausschliessen).

## Auftrags-Durchsagen (Kunden-Upload, Gruppenstart)
- **ffmpeg muss auf dem Windows-Server im PATH liegen** (https://www.gyan.dev/ffmpeg/builds/ -> `ffmpeg.exe` z.B. nach `C:\ffmpeg\bin`, PATH ergaenzen, Dienst `EventenergieBackend` neu starten). Ohne ffmpeg werden Dateien ungeprueft uebernommen (Status "bereit (ungeprueft)").
- Ablage: MongoDB GridFS (Bucket `mbox_audio`), Metadaten in `mbox_order_audio`; ffmpeg nutzt nur das System-Temp. Verarbeitung: Rauschteppich > -50 dB -> `afftdn`, dann Spitzenpegel auf 0 dBFS, MP3 192k.
- Verteilung: fertige Dateien erscheinen im Audio-Manifest aller dem Auftrag zugewiesenen Masten; der Pi laedt sie beim naechsten Sync (einmalig). Loeschen entfernt sie wieder vom Pi.
- Gruppenstart: `play` mit `start_at = jetzt + 6 s` fuer jeden Mast; Pi (ab Skript v1.3) wartet bis `start_at` (Server-Zeitversatz aus `server_time`) -> alle Masten starten gleichzeitig. Befehle, die ein Pi > 2 min nicht abholt, verfallen.
- Ab Skript v1.3.1: fehlt die Datei beim `play` auf dem Pi (z.B. direkt nach Upload oder beim Aufbau), laedt der Pi sie sofort nach (`ensure_file`, Pruefsumme aus dem Befehl) und spielt dann. Manifest enthaelt Dateien aktiver UND kommender Auftraege. Auftraege ohne Dispo-Zeitraum gelten als laufend, sobald ein Mast manuell zugewiesen oder ein Kunde freigegeben ist.
- Timer (`mbox_order_timers`): Backend-Schleife alle 10 s (Europe/Berlin) startet Durchsagen zu festen Uhrzeiten (nur bei laufendem Auftrag).
- Kundenzugang: Kundennummer am Login (automatisch) ODER Haekchen "Kundenzugang" in der Auftrags-Kachel. Kunde: Hub-Kachel "Durchsagen" -> /durchsagen.
