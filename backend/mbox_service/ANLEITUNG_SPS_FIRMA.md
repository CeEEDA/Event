# M-Box V3.0 – Fernbedienung des Lichtmasts in die Firmen-Webseite einbinden

Stand: 27.10.2026 · Lichtmast M-Box V3.0 · Steuerung Siemens S7-1214C (TIA V17) · Zugriff per OPC UA

Dieses Dokument ist die vollständige Arbeitsanweisung, um die bestehende Test-Fernbedienung des Lichtmasts auf dem Firmenserver zu installieren und in die Firmen-Webseite einzubinden. Es richtet sich an den Entwickler der Webseite **und an Claude**. Der komplette, lauffähige Quellcode steht im **Anhang** (Abschnitt A bis E).

---

## 0. Anweisung an Claude – bitte zuerst lesen

Du bekommst hier eine fertige, getestete Fachlogik: einen kleinen Node.js-Server, der per OPC UA mit der SPS des Lichtmasts spricht, und eine Bedienseite. Deine Aufgabe ist, das Ganze **auf dem Firmenserver lauffähig zu machen und in die bestehende Webseite einzubinden**.

**Arbeite in dieser Reihenfolge:**

1. Lies das ganze Dokument. Kläre vorher mit dem Benutzer, was du nicht sicher weißt, insbesondere:
   - Betriebssystem des Servers (Linux oder Windows), vorhandene Node.js-Version
   - Wie die bestehende Webseite gebaut ist (Express/Node, PHP, CMS, statisch …) und ob es schon ein Login-System gibt
   - Welcher Reverse-Proxy oder Webserver davor läuft (nginx, Apache, IIS …) und unter welcher Adresse die Seite erreichbar sein soll (z. B. `https://intern.firma.de/mbox/`)
   - Welche Personen bzw. Gruppen Zugriff bekommen sollen (siehe Abschnitt 5)
2. Lege den Dienst an, wie in Abschnitt 3 beschrieben, und übernimm die Dateien aus dem Anhang **unverändert** als Ausgangspunkt.
3. Teste die Verbindung zur SPS (Abschnitt 10, Schritte 1–3), **bevor** du irgendetwas umbaust.
4. Baue die **Berechtigung** ein (Abschnitt 5). Das ist Pflicht und muss fertig sein, bevor die Seite über das Netz erreichbar ist.
5. Binde die Seite in die Webseite ein (Abschnitt 4).
6. Passe die **Gestaltung** an den Stil der Firmen-Webseite an (Abschnitt 9).
7. Gehe die Abnahme-Checkliste durch (Abschnitt 10).

**Was du NICHT ändern darfst, ohne Rücksprache:**

- Die OPC-UA-Logik in `server.js`: Variablensuche, Index-Umrechnung (`UNTERGRENZE`), Zeitlimits, Lebenszeichen, die Abläufe bei der Zeitschaltuhr. Die Gründe stehen in Abschnitt 6.
- Die Listen `BEFEHLE`, `BEFEHL_ARRAYS` und `EINSTELLUNGEN`. Sie legen fest, was von außen überhaupt geschrieben werden darf. Bitte nicht erweitern, und vor allem **niemals einen Endpunkt bauen, der beliebige Variablen schreibt**.
- Die Variablennamen (`DB_HMI.Status.…` usw.). Sie entsprechen exakt dem SPS-Programm.
- Die Bedeutung von Codes und Zuständen (Texte in `texte.js` und die Zuordnungen in `index.html`).

**Was du ändern sollst bzw. darfst:**

- Gestaltung, Aufteilung und Komponenten der Oberfläche. Das Aussehen ist nur ein Arbeitsstand, die Funktionen und die Lese- und Schreiblogik müssen aber erhalten bleiben.
- Einbindung in die Webseite: Pfade, Login, Navigation, Reverse-Proxy, Dienst.
- Logging, Konfiguration, Prozessverwaltung.
- Die Diagnose-Endpunkte (`/api/knoten`, `/api/browse`, `/api/suche`, `/api/neu_verbinden`) und den Test-Endpunkt `/api/gps` nur für Administratoren freigeben oder ganz entfernen (siehe Abschnitt 5).

Wenn etwas im Betrieb nicht so funktioniert wie hier beschrieben, z. B. weil eine Variable nicht gefunden wird, dann **frag nach, statt zu raten**. Die SPS steuert echte Hardware: einen Generator, einen Hydraulikmast und Netzschütze.

---

## 1. Überblick

```
 Browser (Mitarbeiter)                       Firmenserver                                   Lichtmast
┌────────────────────┐   HTTPS + Login   ┌─────────────────────────────────┐   OPC UA    ┌──────────────────┐
│ Bedienseite        │ ────────────────▶ │ Reverse-Proxy (nginx/IIS/...)   │  TCP 4840   │ S7-1214C         │
│ index.html         │                   │   └▶ Node.js-Dienst (server.js) │ ──────────▶ │ OPC-UA-Server    │
│ texte.js           │ ◀──── JSON ────── │      Express + node-opcua       │ ◀────────── │ 192.168.0.100    │
└────────────────────┘                   └─────────────────────────────────┘             └──────────────────┘
```

- **Der Browser spricht nie direkt mit der SPS.** Nur der Node.js-Dienst hält die OPC-UA-Verbindung. Der Browser fragt alle 2 s über eine kleine JSON-Schnittstelle (`/api/...`) die Werte ab und schickt Befehle.
- Der Dienst hält **eine** dauerhafte OPC-UA-Sitzung zur SPS, egal wie viele Browser offen sind.
- Der Dienst schreibt alle 10 s ein **Lebenszeichen** in die SPS. Daran erkennt die SPS, dass die Gegenstelle da ist. Am Panel steht dann „Verbindung erkannt“.
- Die SPS hat eigene Sicherheitsriegel: Befehle von außen wirken nur, wenn am Panel des Masts „Fernbedienung erlaubt“ an ist, das Modul „Fernzugriff“ gebucht ist und kein Wartungsmodus aktiv ist. Diese Riegel ersetzen aber **nicht** die Berechtigung auf der Webseite.

Der Funktionsumfang der Bedienseite (7 Reiter):

| Reiter | Inhalt |
|---|---|
| Übersicht | Lampen 1–5 einzeln, Schnellstart/-stop, Lampen ein/aus, Netz-/Generatorbetrieb, Generator start/stop, Netzüberwachung ein/aus mit Zustand und Countdown, Tank, Wind, Helligkeit |
| Automatik | Automatik (Auto-Betrieb) aktivieren/deaktivieren, Quellen Dämmerung/Zeitschaltuhr/Astro, Astro-Zeiten, Einstellungen (Astro-Versätze, Dämmerungsschwelle), GPS-Testeingabe |
| Steckdosen & Audio | Steckdose 1 und 3+4, Stumpfelbox (Audioverstärker), Durchsage und Signale 1–6 |
| Zeitschaltuhr | Wochenprogramm je Tag bearbeiten (7 Schaltpaare), auf alle oder ausgewählte Tage kopieren, Datums-Schaltzeiten anlegen und löschen, Wochenübersicht |
| Meldungen & Protokoll | anstehende Störungen und Infos, Quittieren, die neuesten 30 Protokolleinträge im Klartext |
| Service | Betriebsstunden, Wartung, Kundenzähler, Probelauf, Zusatzmodule |
| Diagnose | alle Ein- und Ausgänge sowie Rohwerte |

Bewusst **nicht** von außen möglich, nur am Panel vor Ort: Mast heben/senken, Einrichtbetrieb, Teach der Tankgeber, Uhr stellen, Überbrückungen, Admin-Parameter.

---

## 2. Voraussetzungen

### 2.1 Netzwerk

- Der Firmenserver muss die SPS auf **TCP-Port 4840** erreichen. Dass Ping funktioniert, reicht nicht. Prüfen:
  - Linux: `nc -vz 192.168.0.100 4840`
  - Windows (PowerShell): `Test-NetConnection 192.168.0.100 -Port 4840`
- Die IP-Adresse der SPS im Lichtmast ist `192.168.0.100`. Liegt sie hinter VPN oder NAT, steht in `OPCUA_ENDPOINT` die vom Server aus erreichbare Adresse.
- Empfehlung: Auf Router oder Firewall des Masts Port 4840 **nur** für die IP des Firmenservers freigeben.

### 2.2 Server

- **Node.js LTS, Version 20 oder neuer** (getestet mit Node 24, node-opcua 2.186, express 4.22).
- Ausgehender Internetzugang einmalig für `npm install`, oder die Pakete werden offline mitgebracht.
- Ein Reverse-Proxy mit HTTPS, über den die Webseite ohnehin läuft. Der Node-Dienst selbst lauscht nur auf `127.0.0.1`.

### 2.3 SPS / TIA Portal

Diese Einstellungen sind auf der SPS gemacht und werden vom Steuerungsprogrammierer gepflegt. Sie stehen hier zur Kontrolle:

| Wo in TIA (CPU-Eigenschaften) | Einstellung |
|---|---|
| OPC UA → Server → Allgemein | Server aktiv, Port 4840 |
| Laufzeitlizenzen → OPC UA | Lizenz eingetragen |
| OPC UA → Server → Server-Schnittstellen | benutzerdefinierte Schnittstelle **„M-Box“** mit den DBs `DB_Fern`, `DB_HMI`, `DB_Parameter`, `DB_Module`, `DB_Zaehler`, `DB_Schaltuhr`, `DB_Astro` (**nicht** `DB_Protokoll`, keine Instanz-DBs; die S7-1200 erlaubt max. 2000 Knoten) |
| OPC UA → Server → Security | Für den Test „Keine Sicherheit“ und Gastzugang; im Betrieb `Basic256Sha256 – Sign & Encrypt` und ein eigener OPC-UA-Benutzer |
| Uhrzeit | NTP über den Router, Zeitzone Berlin mit Sommerzeit |

---

## 3. Installation von Grund auf

Die Beispiele gehen von Linux aus. Unter Windows sind die Befehle gleich, nur die Pfade unterscheiden sich, z. B. `C:\Dienste\mbox-fernbedienung`.

### 3.1 Node.js installieren

- Linux (Debian/Ubuntu), z. B. über das NodeSource-Repository oder `nvm`. Danach prüfen: `node --version`, das Ergebnis muss mindestens v20 sein.
- Windows: Installer „LTS“ von https://nodejs.org, Standardeinstellungen.

### 3.2 Projektordner anlegen

```
/opt/mbox-fernbedienung/
├── package.json        ← Anhang A
├── server.js           ← Anhang B
├── .env.beispiel       ← Anhang C  (kopieren nach .env und ausfüllen)
├── .env                ← echte Zugangsdaten, NICHT ins Git
└── public/
    ├── index.html      ← Anhang D
    └── texte.js        ← Anhang E
```

Die Dateien 1:1 aus dem Anhang anlegen, als UTF-8. Dann:

```bash
cd /opt/mbox-fernbedienung
npm install
cp .env.beispiel .env
nano .env
```

In `.env` mindestens `OPCUA_ENDPOINT` und, falls in TIA ein OPC-UA-Benutzer angelegt ist, `OPCUA_BENUTZER` und `OPCUA_PASSWORT` eintragen. Die Zugangsdaten bekommst du vom Steuerungsprogrammierer, und sie gehören **nur** in die `.env`.

Wenn ein Git-Repository verwendet wird, in `.gitignore` aufnehmen:

```
node_modules/
.env
```

### 3.3 Probestart

```bash
npm start
```

Erwartete Ausgabe nach ein paar Sekunden, bei der ersten Abfrage aus dem Browser:

```
Bedienprogramm laeuft: http://127.0.0.1:8080
SPS-Endpunkt: opc.tcp://192.168.0.100:4840
Verbunden mit opc.tcp://192.168.0.100:4840
  ns=0: http://opcfoundation.org/UA/
  ...
Knoten durchsucht: …, Variablen gefunden: …
  DBs unter: M-Box  (ns=4)
```

Auf dem Server selbst testen, z. B. über einen SSH-Tunnel oder `curl`:

```bash
curl -s -X POST http://127.0.0.1:8080/api/lesen -H "Content-Type: application/json" \
     -d '{"namen":["DB_HMI.Status.Uhrzeit_Text","DB_HMI.Status.Versorgung"]}'
```

Antwort z. B. `{"ok":true,"werte":{"DB_HMI.Status.Uhrzeit_Text":"14:05","DB_HMI.Status.Versorgung":1}}`.

### 3.4 Dauerbetrieb als Dienst

**Linux (systemd).** Datei `/etc/systemd/system/mbox-fernbedienung.service`:

```ini
[Unit]
Description=M-Box Fernbedienung (OPC UA)
After=network-online.target

[Service]
WorkingDirectory=/opt/mbox-fernbedienung
ExecStart=/usr/bin/node server.js
Restart=always
RestartSec=5
User=mbox
Environment=NODE_ENV=production

[Install]
WantedBy=multi-user.target
```

```bash
sudo useradd -r -s /usr/sbin/nologin mbox
sudo chown -R mbox /opt/mbox-fernbedienung
sudo systemctl daemon-reload
sudo systemctl enable --now mbox-fernbedienung
journalctl -u mbox-fernbedienung -f
```

`User=mbox` braucht Schreibrechte im Programmordner, weil node-opcua beim ersten Start dort ein Client-Zertifikat anlegt (PKI-Ordner).

**Windows:** z. B. mit `pm2` (`npm i -g pm2 pm2-windows-startup`, dann `pm2 start server.js --name mbox` und `pm2 save`) oder mit NSSM als Windows-Dienst.

---

## 4. Einbindung in die bestehende Webseite

Die Bedienseite verwendet **relative URLs** (`api/lesen`, `texte.js`). Sie funktioniert deshalb direkt unter einem Unterpfad wie `/mbox/`. Zwei Wege sind möglich, Weg A ist die Empfehlung.

### Weg A (empfohlen): eigener Dienst hinter dem Reverse-Proxy

Der Node-Dienst läuft separat auf `127.0.0.1:8080`, und der Webserver leitet einen Unterpfad dorthin weiter.

nginx:

```nginx
location /mbox/ {
    # Login/Berechtigung: siehe Abschnitt 5 (hier oder im Node-Dienst)
    proxy_pass http://127.0.0.1:8080/;          # Schrägstrich am Ende: /mbox/ wird entfernt
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 30s;
}
```

Apache: `ProxyPass /mbox/ http://127.0.0.1:8080/` und `ProxyPassReverse /mbox/ http://127.0.0.1:8080/`. IIS: URL-Rewrite mit ARR auf `http://127.0.0.1:8080/{R:1}`.

In der Navigation der Webseite einen Menüpunkt auf `/mbox/` setzen, und zwar **nur für berechtigte Benutzer sichtbar**. Die eigentliche Sperre muss trotzdem serverseitig sein, siehe Abschnitt 5.

### Weg B: in eine vorhandene Express-App einhängen

Läuft die Webseite selbst auf Node/Express, können Routen und statische Dateien aus `server.js` als `express.Router()` unter `/mbox` eingehängt werden. Dabei gilt:

- Der OPC-UA-Teil (Verbindung, Karte, Lebenszeichen-Timer) darf **nur einmal pro Prozess** existieren und keinesfalls pro Anfrage neu erzeugt werden.
- Die Login-Middleware der Webseite muss vor dem Router hängen.
- `app.listen` aus `server.js` fällt dann weg.

### Einbettung in ein bestehendes Seitenlayout

Die Seite ist eigenständiges HTML mit eingebettetem CSS und JS. Für ein Layout mit Kopf- und Fußbereich der Firmen-Webseite gibt es zwei Möglichkeiten: den Inhalt von `<body>` in das Seitentemplate übernehmen, oder die Seite per `<iframe src="/mbox/">` einbinden. Bei der Übernahme in ein Template darauf achten, dass die IDs, z. B. `k_licht`, `b_nub` oder `h_verbindung`, eindeutig bleiben.

---

## 5. Berechtigung (Pflicht)

Das ist eine **Testinstallation an einer echten Maschine**. Wer die Seite erreicht, kann Generator, Lampen und Netzumschaltung schalten. Deshalb gilt:

1. **Kein Zugriff ohne Anmeldung.** Alle Pfade des Dienstes, also die Seite **und** alle `/api/*`-Endpunkte, dürfen nur nach Login erreichbar sein. Den Dienst nie direkt ins Internet stellen: `WEB_HOST=127.0.0.1` lassen und den Zugriff nur über den Reverse-Proxy mit HTTPS erlauben.
2. **Nur ein ausdrücklich benannter Personenkreis.** Eine Freigabeliste (Benutzer oder Gruppe) anlegen, z. B. eine Gruppe „mbox-test“. Alle anderen angemeldeten Mitarbeiter der Webseite bekommen 403.
3. **Am besten das vorhandene Login der Firmen-Webseite nutzen** (Session, SSO, LDAP/AD, …), statt ein zweites Passwortsystem zu bauen. Falls es keins gibt: HTTP Basic Auth im Reverse-Proxy (nginx `auth_basic` mit htpasswd) als Mindestlösung. Nur über HTTPS.
4. **Zwei Stufen sind sinnvoll:**
   - **Lesen:** Status, Meldungen, Protokoll, Zähler. Endpunkt `POST /api/lesen`.
   - **Bedienen:** alle schreibenden Endpunkte: `/api/befehl/*`, `/api/einstellung`, `/api/uhr/*`.
   - **Nur Admin**, oder ganz entfernen: `/api/knoten`, `/api/browse`, `/api/suche`, `/api/neu_verbinden`, `/api/gps`. Die GPS-Position schreibt im Betrieb der Raspberry Pi des Masts selbst direkt per OPC UA. `/api/gps` ist nur zum Testen da.
   - Zusätzlich empfehlenswert: `Kundenzaehler_Reset`, `Wartung_Reset` und `Probelauf_Start` nur für Admin.
5. **Schreibende Anfragen absichern:** Bei Cookie-Sessions CSRF-Schutz einbauen, z. B. ein Token im Header oder `SameSite=Strict`-Cookies plus Prüfung des `Origin`-Headers. Die Seite benutzt für alles `fetch(..., { method: "POST" })` über die Funktion `post()` in `index.html`. Dort lässt sich ein Header zentral ergänzen.
6. **Protokollieren, wer was geschaltet hat.** Die SPS kennt nur „Befehl kam per Fernzugriff“ (Codes 300+), aber nicht die Person. Deshalb im Node-Dienst bei jedem schreibenden Endpunkt Zeit, Benutzername, Endpunkt und Parameter in ein Logfile oder die Datenbank der Webseite schreiben. Die passenden Stellen sind die `console.log("Befehl gesendet: …")` usw. in `server.js`.
7. **Rate-Limit** für schreibende Endpunkte, z. B. max. 30 Befehle pro Minute und Benutzer, damit kein Skript die Anlage takten kann.
8. **OPC UA im Betrieb absichern:** In TIA „Keine Sicherheit“ und den Gastzugang abschalten. In `.env` dann `OPCUA_SECURITY_MODE=SignAndEncrypt`, `OPCUA_SECURITY_POLICY=Basic256Sha256` und einen eigenen OPC-UA-Benutzer setzen. Beim ersten Verbinden muss das Client-Zertifikat des Servers in der SPS vertrauenswürdig sein, entweder durch „Client-Zertifikate automatisch akzeptieren“ in TIA oder durch manuelles Eintragen.

Ein Beispiel für eine Middleware, falls die Webseite selbst Express ist. Sie ist nur eine Skizze und muss an das vorhandene Session-System angepasst werden:

```js
// vor express.static und allen app.post("/api/...") einhängen
const ERLAUBT_LESEN = new Set(["mbox-test", "mbox-admin"]);     // Gruppen
const ERLAUBT_BEDIENEN = new Set(["mbox-test", "mbox-admin"]);
const NUR_ADMIN = [/^\/api\/(knoten|browse|suche|neu_verbinden|gps)/, /^\/api\/befehl\/(Kundenzaehler_Reset|Wartung_Reset|Probelauf_Start)/];

app.use((req, res, next) => {
  const user = req.session && req.session.user;              // <- aus dem Login der Webseite
  if (!user) return res.status(401).send("Anmeldung erforderlich");
  const gruppen = new Set(user.gruppen || []);
  const hat = menge => [...menge].some(g => gruppen.has(g));
  if (!hat(ERLAUBT_LESEN)) return res.status(403).send("Kein Zugriff");
  if (NUR_ADMIN.some(r => r.test(req.path)) && !gruppen.has("mbox-admin")) return res.status(403).json({ ok: false, fehler: "Nur Admin" });
  if (req.method === "POST" && req.path !== "/api/lesen" && !hat(ERLAUBT_BEDIENEN)) return res.status(403).json({ ok: false, fehler: "Keine Bedienberechtigung" });
  next();
});
```

---

## 6. Wie die SPS per OPC UA angesprochen wird

Dieser Abschnitt erklärt die Fachlogik in `server.js`. Sie funktioniert so und ist am Mast getestet.

### 6.1 Verbindung

- Bibliothek: `node-opcua` (`OPCUAClient`). Endpoint aus `.env` (`opc.tcp://192.168.0.100:4840`).
- `endpointMustExist: false`, `keepSessionAlive: true`. Eine Sitzung für alle Anfragen.
- Anmeldung: mit Benutzername und Passwort, wenn `OPCUA_BENUTZER` gesetzt ist, sonst anonym.
- **Jeder OPC-UA-Aufruf hat ein Zeitlimit** (8 s, Funktion `mitZeitlimit`). Hängt ein Aufruf, z. B. weil die Mobilfunk- oder VPN-Strecke kurz weg war, wird die Sitzung verworfen und bei der nächsten Abfrage neu aufgebaut. Ohne das blieb die Seite früher minutenlang stehen.
- Bei `connection_lost` wird ebenfalls sofort neu verbunden.

### 6.2 Variablen per Name, NodeIds werden automatisch gesucht

Die Webseite und die API arbeiten nur mit **Namen**, genau wie im SPS-Programm, z. B. `DB_HMI.Status.Versorgung` oder `DB_Schaltuhr.Woche[3,2].Ein_Std`.

Beim ersten Verbinden durchsucht der Server einmal den OPC-UA-Adressraum (Browse ab `Objects`, Funktion `karteAufbauen`) und baut eine Tabelle Name → NodeId auf. Grund: Die benutzerdefinierte Schnittstelle „M-Box“ vergibt **numerische NodeIds** (z. B. `ns=4;i=846`). Die können sich bei jeder Änderung der Schnittstelle in TIA verschieben, deshalb dürfen sie nicht fest im Code stehen.

- Die Schnittstelle „M-Box“ hat Vorrang. Ist zusätzlich die Standard-SIMATIC-Schnittstelle (`ns=3`, String-NodeIds `"DB"."Var"`) aktiv, dient sie als Rückfallebene.
- Nach einer Änderung der Server-Schnittstelle in TIA den Dienst **neu starten** (oder `POST /api/neu_verbinden`), damit neu gesucht wird.
- **Wichtige Besonderheit:** Die benutzerdefinierte Schnittstelle nummeriert Array-Elemente **immer ab 0**, auch wenn das Array in TIA ab 1 deklariert ist. Aus `Woche[1..7, 1..7]` wird auf dem Server `Woche[0..6, 0..6]`. Die Tabelle `UNTERGRENZE` in `server.js` rechnet das zurück, sodass überall die TIA-Indizes gelten. Kommt in der SPS ein neues Array dazu, das nicht bei 0 beginnt, **muss es dort eingetragen werden**, sonst ist alles um eins verschoben.

### 6.3 Lesen

- `lesen(namen)` liest in Paketen zu 100 Knoten (ein `Read`-Aufruf je Paket).
- Arrays wie `DB_HMI.Status.Lampe` oder `DB_HMI.Alarm` werden als Ganzes gelesen und kommen als JS-Array zurück. **Achtung:** Im JS-Array steht das erste Element immer auf Position 0. `Lampe[1]` aus TIA ist also `werte[...Lampe][0]`.
- Datentypen: Bool → `boolean`, Int/DInt → `number`, Real → `number` (Float), String → `string`, Time → `number` in **Millisekunden**, Word → `number` (Bitfeld).
- Nicht lesbare Variablen kommen als `{ fehler: "BadNodeIdUnknown" }` zurück, die anderen Werte trotzdem.
- `DB_Protokoll` (200 Einträge) ist absichtlich **nicht** in der Schnittstelle. Die neuesten 30 Einträge stellt die SPS in `DB_Fern.Protokoll[1..30]` bereit, `[1]` ist der neueste.

### 6.4 Befehle schreiben

- Alle Bedienbefehle sind **Impuls-Bits** in `DB_Fern.Cmd` (Struktur wie die Panel-Tasten). Der Server setzt das Bit auf `true`, die SPS übernimmt es im nächsten Zyklus und setzt es selbst zurück. Der Server setzt es nie zurück.
- Die SPS übernimmt Befehle aus `DB_Fern.Cmd` **nur**, wenn am Panel „Fernbedienung erlaubt“ an ist, das Modul „Fernzugriff“ aktiv ist und kein Wartungsmodus läuft. Sonst verwirft sie das Bit stillschweigend. Die Seite zeigt deshalb oben einen Hinweis, wenn eine dieser Bedingungen fehlt.
- Array-Befehle (`Lampe_Umschalten[1..5]`, `Audio_Umschalten[0..6]`) werden als ganzes Bool-Array geschrieben, mit genau einem `true`.
- Erlaubt sind nur die Befehle in `BEFEHLE` und `BEFEHL_ARRAYS`. Alles andere lehnt der Server ab.
- Jeder angenommene Fernbefehl landet im Ereignisprotokoll der SPS als Code `300 + Befehlsnummer`.

### 6.5 Einstellungen schreiben

Vier Einstellwerte dürfen direkt geschrieben werden (`EINSTELLUNGEN`): die Astro-Versätze und die Dämmerungsschwelle mit Hysterese. Der Server prüft Grenzwerte und Datentyp **und** liest vorher `Fern_Erlaubt`. Ist das aus, schreibt er nichts. Datentypen beim Schreiben: Int → `DataType.Int16`, Real → `DataType.Float`, Bool → `DataType.Boolean`.

### 6.6 Zeitschaltuhr (eigener Ablauf)

Für die Zeitschaltuhr hat der Fernzugriff einen **eigenen Bearbeitungspuffer** `DB_Fern.Uhr`. Das Panel hat seinen eigenen, damit sich beide nicht stören. Der Ablauf ist immer:

1. `Fern_Erlaubt` prüfen.
2. `DB_Fern.Uhr.Meldung := 0` und die Daten in den Puffer schreiben, in **einem** Write-Aufruf:
   - Wochenprogramm: `Tag` (1..7) und alle 7 Paare `Woche[1..7].{Aktiv_Ein, Aktiv_Aus, Ein_Std, Ein_Min, Aus_Std, Aus_Min}`, bei „auf Auswahl“ zusätzlich `Kopieren_Auf` (Bool-Array, 7 Tage)
   - Datum hinzufügen: `Neu.{Jahr, Monat, Tag, Std, Min, Einschalten}`
   - Datum löschen: `Loesch_Index` (1..20, Position in `DB_Schaltuhr.Datum`)
3. **Danach** in einem zweiten Write den Befehl setzen: `DB_Fern.Cmd.Woche_Speichern`, `Woche_Auf_Alle_Tage`, `Woche_Auf_Auswahl`, `Datum_Hinzufuegen` oder `Datum_Loeschen`.
4. Bis zu 2 s lang `DB_Fern.Uhr.Meldung` lesen: 1 = gespeichert, 2 = ungültig, 3 = liegt in der Vergangenheit, 4 = Liste voll, 5 = gelöscht. Bleibt sie 0, hat die SPS den Befehl nicht angenommen (Fernbedienung gesperrt).

Die SPS prüft und begrenzt die Werte selbst, sortiert die Datumsliste und protokolliert. Angezeigt wird immer aus `DB_Schaltuhr.Woche[1..7, 1..7]` und `DB_Schaltuhr.Datum[1..20]`, denn das ist der gültige Stand.

### 6.7 Lebenszeichen

Alle 10 s zählt der Server `DB_Fern.Lebenszeichen_Web` hoch (Int16). Bleibt der Wert länger stehen, meldet die SPS „Gegenseite nicht verbunden“ (`DB_HMI.Status.Fern_Verbunden = false`). Die SPS selbst zählt `DB_HMI.Status.Lebenszeichen` jede Sekunde hoch. Daran sieht die Webseite, dass die Werte frisch sind.

### 6.8 GPS (nur Info)

Im Betrieb schreibt der Raspberry Pi des Masts seine GPS-Position selbst nach `DB_Fern.GPS.{Breitengrad, Laengengrad (Real), Fix (Bool)}`. Damit rechnet die SPS Sonnenauf- und -untergang für die Astro-Automatik. `/api/gps` im Server ist nur ein Testersatz dafür.

---

## 7. API des Node-Dienstes (Browser ↔ Server)

Alle Antworten sind JSON mit `ok: true|false`, im Fehlerfall zusätzlich `fehler: "Text"`.

| Methode, Pfad | Body / Parameter | Zweck | Berechtigung |
|---|---|---|---|
| `POST api/lesen` | `{ "namen": ["DB_HMI.Status.Versorgung", …] }` (max. 1500, nur `DB_…`) | Werte lesen, Antwort `{ werte: { name: wert } }` | Lesen |
| `POST api/befehl/<Name>` | bei Arrays `?index=n` | Impulsbefehl nach `DB_Fern.Cmd` | Bedienen |
| `POST api/einstellung` | `{ "name": "DB_Astro.Versatz_Ein", "wert": 20 }` | Einstellwert schreiben | Bedienen |
| `POST api/uhr/woche` | `{ tag, paare[7], ziel: "tag"\|"alle"\|"auswahl", kopieren[7] }` | Wochenprogramm speichern | Bedienen |
| `POST api/uhr/datum` | `{ jahr, monat, tag, std, min, einschalten }` | Datums-Schaltzeit anlegen | Bedienen |
| `POST api/uhr/datum_loeschen` | `{ index }` | Datums-Schaltzeit löschen | Bedienen |
| `POST api/gps?breite=&laenge=&fix=` | – | Test: GPS wie der Pi schreiben | Admin / entfernen |
| `GET api/knoten[?alle=1]` | – | Diagnose: gefundene NodeIds | Admin |
| `GET api/browse[?node=]` | – | Diagnose: Adressraum durchklicken | Admin |
| `GET api/suche?text=` | – | Diagnose: Variablen suchen | Admin |
| `POST api/neu_verbinden` | – | Variablen neu suchen | Admin |

Befehlsnamen für `api/befehl/…`: `Quittieren, Hand, Auto, Auto_Umschalten, Schnellstart, Schnellstop, Lampen_Ein, Lampen_Aus, Gen_Start, Gen_Stop, Netzbetrieb, Generatorbetrieb, Steckdose_1_Umschalten, Steckdose_34_Umschalten, Stumpfelbox_Umschalten, Auto_Daemmerung_Umschalten, Auto_Uhr_Umschalten, Auto_Astro_Umschalten, Wartung_Reset, Kundenzaehler_Reset, Probelauf_Start, Netzueberwachung_Umschalten`, dazu `Lampe_Umschalten?index=1..5` und `Audio_Umschalten?index=0..6`.

---

## 8. Die wichtigsten Variablen

Die vollständigen Listen der gelesenen Variablen stehen in `index.html` (`STATUS_NAMEN`, `ZAEHLER_NAMEN`, `BASIS`, `EXTRA`). Hier nur die Bedeutung der Zustandswerte:

| Variable | Werte |
|---|---|
| `DB_HMI.Status.Betriebsart` | 1 Hand, 2 Auto, 3 Einrichten (nur vor Ort) |
| `DB_HMI.Status.Versorgung` | 1 Netz, 2 Generator |
| `DB_HMI.Status.Gen_Zustand` | 0 Aus, 10 Startet, 20 Läuft, 30 Fährt herunter |
| `DB_HMI.Status.Stoerung_Zustand` | 0 keine, 1 quittieren, 2 Störung steht an |
| `DB_HMI.Status.Stumpfelbox_Zustand` | 0 aus, 1 fährt hoch (10 s), 2 bereit |
| `DB_HMI.Status.Audio_Kanal` | −1 keiner, 0 Durchsage, 1–6 Signal |
| `DB_HMI.Status.Akku_Zustand` | 0 kein Akkupack, 10 Brücke offen, 20 Einspeisung, 30 Betrieb, 99 Not-Aus |
| `DB_HMI.Status.Astro_Sonderfall` | 0 normal, 1 Polarnacht, 2 Mitternachtssonne, 3 keine Position/Uhr |
| `DB_HMI.Status.Probelauf_Ergebnis` | 0 keiner, 1 OK, 2 Fehler, 3 abgebrochen |
| `DB_HMI.Alarm[0..1]` | Word-Bitfeld: Bit n = Meldung n (Wort 0 = Meldung 0–15, Wort 1 = 16–31), Texte in `texte.js` (`MELDUNGEN`) |
| `DB_Fern.Protokoll[i].Code` | 1–99 Ereignis, 100+n Meldung n, 200+n Befehl vor Ort, 300+n Befehl per Fernzugriff (Funktion `codeText` in `texte.js`) |
| `DB_HMI.Module.Aktiv[1..4]` | 1 Audio, 2 Akkupack, 3 Netzüberwachung, 4 Fernzugriff |

---

## 9. Gestaltung

Die mitgelieferte Oberfläche ist ein **funktionaler Arbeitsstand** aus dem Test, kein fertiges Design. Wer die Webseite pflegt, soll sie **an den Stil der Firmen-Webseite anpassen**: Farben, Schriften, Abstände, Buttons, Kopfbereich, Navigation, Logo, Responsive-Verhalten. Erlaubt und erwünscht:

- Das CSS komplett ersetzen und vorhandene Stylesheets oder Komponenten der Webseite verwenden.
- Reiter, Karten und Tabellen anders anordnen. Jede Funktion und jede Statusanzeige muss dabei aber erhalten bleiben.
- Die Farbbedeutungen behalten: grün = an/aktiv, gelb = läuft/Warnung, rot = Störung. Die gelben und roten Hinweise oben (Fernbedienung gesperrt, Wartungsmodus, Störung) müssen auffällig bleiben.
- Bestätigungsdialoge (`confirm(...)`) dürfen durch eigene Dialoge ersetzt werden, müssen aber bleiben.
- **Keine Verweise auf technische Interna in der Oberfläche:** keine Links oder Hinweise auf die Diagnose-Endpunkte (`api/knoten`, `api/browse`, `api/suche`), keine NodeIds, OPC-UA-Begriffe oder Fehlercodes als Dauertext. Die Diagnose ist nur für Administratoren über die direkte Adresse gedacht (Abschnitt 5).

Nicht verändern: die Abfragelogik `aktualisieren()` mit 2-s-Takt, Schutz gegen parallele Abfragen und Zeitlimit; die Namen der gelesenen Variablen; die Umrechnung von Zuständen und Codes in Text; den Ablauf im Zeitschaltuhr-Editor (ungespeicherte Änderungen werden nicht von der Abfrage überschrieben).

---

## 10. Abnahme / Test

Am besten zusammen mit jemandem am Mast oder mit Blick auf das Panel.

1. `nc -vz <SPS-IP> 4840` bzw. `Test-NetConnection`: Der Port ist erreichbar.
2. Dienst starten. Im Log stehen „Verbunden mit …“ und „DBs unter: M-Box (ns=4)“.
3. `GET api/knoten` (als Admin): Die Liste `nichtGefunden` ist leer, nachdem jeder Reiter einmal geöffnet war.
4. Ohne Login: Die Seite und **alle** `api/*` liefern 401 bzw. 403, auch per `curl` direkt am Proxy vorbei, falls von außen erreichbar.
5. Mit Lese-Berechtigung: Die Werte erscheinen, alle schreibenden Endpunkte liefern 403.
6. Mit Bedien-Berechtigung, am Panel „Fernbedienung erlaubt“ **aus**: Die Seite zeigt den gelben Hinweis, und ein Befehl hat keine Wirkung.
7. Am Panel „Fernbedienung erlaubt“ **an**:
   - Quittieren: Im Protokoll erscheint „Fern: Quittieren“ (Code 300).
   - Lampe 1 einzeln umschalten: Die Lampe schaltet, die Anzeige folgt.
   - Netzüberwachung ein/aus: Der Zustand wechselt, im Protokoll steht Code 345.
   - Zeitschaltuhr: Ein Paar für einen Tag eintragen und speichern. Die Meldung „gespeichert“ kommt, und am Panel ist dasselbe Paar am selben Tag zu sehen.
   - Datums-Schaltzeit in der Zukunft anlegen und wieder löschen.
8. Das eigene Protokoll des Dienstes (wer hat was geschaltet) enthält die Einträge aus Schritt 7.
9. Netzwerk zum Mast kurz trennen: Die Seite zeigt „keine Verbindung“. Nach dem Wiederverbinden laufen die Werte innerhalb weniger Sekunden wieder, ohne Neustart.
10. Oben rechts steht „Stand hh:mm:ss“ und aktualisiert sich alle 2 s.

---

## 11. Fehlersuche

| Symptom | Ursache / Abhilfe |
|---|---|
| `Zeitüberschreitung: Verbinden` | Port 4840 nicht erreichbar (Firewall, VPN, falsche IP), OPC-UA-Server in TIA aus, Lizenz fehlt |
| `BadSecurityPolicyRejected` / `BadIdentityTokenRejected` | Security- bzw. Benutzer-Einstellung in `.env` passt nicht zu TIA |
| `BadCertificateUntrusted` o. ä. | Client-Zertifikat in der SPS nicht vertrauenswürdig: in TIA automatisch akzeptieren oder manuell eintragen |
| Einzelne Werte `nicht lesbar` / `BadNodeIdUnknown` | Variable nicht in der Schnittstelle „M-Box“, oder der Dienst wurde nach einer TIA-Änderung nicht neu gestartet; `api/suche?text=…` prüfen |
| Werte eines Arrays um eins verschoben | Array fehlt in `UNTERGRENZE` (Abschnitt 6.2) |
| Befehl „gesendet“, aber keine Wirkung | „Fernbedienung erlaubt“ aus, Modul Fernzugriff nicht aktiv oder Wartungsmodus; das Protokoll der SPS enthält dann keinen 300er-Eintrag |
| Zeitschaltuhr: „keine Rückmeldung der SPS“ | wie oben: Befehl wurde von der SPS nicht angenommen |
| Log: `Lesen von 100 Werten dauerte … ms` | langsame Verbindung zum Mast (Mobilfunk). Unkritisch, solange es unter 8 s bleibt |

---

## 12. Grenzen und Hinweise

- Der Stand ist auf **einen** Lichtmast ausgelegt (eine SPS-Adresse in `.env`). Für mehrere Masten bräuchte es je Mast eine eigene OPC-UA-Verbindung samt Variablentabelle und eine Auswahl auf der Seite. Das ist ein eigener Ausbauschritt; bitte nicht nebenbei einbauen.
- Die SPS ist die führende Instanz. Grenzwerte, Sperren und Abläufe werden dort geprüft. Der Server prüft zusätzlich, damit falsche Eingaben gar nicht erst ankommen.
- Ansprechpartner für das SPS-Programm, die OPC-UA-Schnittstelle in TIA und die Zugangsdaten ist der Steuerungsprogrammierer. Änderungen an Variablen oder DBs immer mit ihm abstimmen.

---

# Anhang – Quellcode (Stand 27.10.2026)

Die folgenden Dateien sind der vollständige, lauffähige Stand. Bitte 1:1 übernehmen und erst danach erweitern (Login, Logging, Gestaltung).

## Anhang A – `package.json`

``json
{
  "name": "mbox-fernbedienung",
  "version": "1.0.0",
  "description": "M-Box Lichtmast per OPC UA bedienen (Webserver + Bedienseite)",
  "main": "server.js",
  "private": true,
  "engines": { "node": ">=20" },
  "scripts": {
    "start": "node server.js"
  },
  "dependencies": {
    "express": "^4.22.3",
    "node-opcua": "^2.186.17"
  }
}
``

## Anhang B – `server.js`

``js
// M-Box V3.0 – OPC-UA-Bedienprogramm (Test)
// Startet einen kleinen Webserver auf http://localhost:8080 und spricht per OPC UA mit der SPS.
// Befehle werden nach DB_Fern.Cmd geschrieben (wirken nur, wenn Modul Fernzugriff freigeschaltet,
// "Fernbedienung erlaubt" an und kein Wartungsmodus aktiv ist).
// Die NodeIds werden beim Verbinden automatisch gesucht (Server-Schnittstelle "M-Box" bevorzugt,
// sonst Standard-SIMATIC-Schnittstelle). Variablen werden nur per Name angegeben, z. B. "DB_HMI.Status.Versorgung".

const express = require("express");
const path = require("path");
const {
  OPCUAClient, MessageSecurityMode, SecurityPolicy, AttributeIds, DataType, VariantArrayType, UserTokenType
} = require("node-opcua");

// ===================== Einstellungen =====================
// Werte kommen aus der Datei ".env" im Programmordner (Vorlage: .env.beispiel) oder aus Umgebungsvariablen.
// Zugangsdaten gehoeren NICHT in den Quellcode.
(function envLaden() {
  const datei = path.join(__dirname, ".env");
  if (!require("fs").existsSync(datei)) return;
  for (const zeile of require("fs").readFileSync(datei, "utf8").split(/\r?\n/)) {
    const m = /^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$/.exec(zeile);
    if (m && !zeile.trim().startsWith("#") && process.env[m[1]] === undefined) process.env[m[1]] = m[2].replace(/^["']|["']$/g, "");
  }
})();
const KONFIG = {
  endpoint: process.env.OPCUA_ENDPOINT || "opc.tcp://192.168.0.100:4840",
  // Test: "None"/"None" + in TIA "Keine Sicherheit" erlaubt. Betrieb: "SignAndEncrypt"/"Basic256Sha256".
  securityMode: process.env.OPCUA_SECURITY_MODE || "None",        // "None" | "Sign" | "SignAndEncrypt"
  securityPolicy: process.env.OPCUA_SECURITY_POLICY || "None",    // "None" | "Basic256Sha256"
  benutzer: process.env.OPCUA_BENUTZER || "",                     // leer = Gastzugang (anonym)
  passwort: process.env.OPCUA_PASSWORT || "",
  webHost: process.env.WEB_HOST || "127.0.0.1",                   // 127.0.0.1 = nur lokal / hinter Reverse-Proxy erreichbar
  webPort: Number(process.env.WEB_PORT || 8080)
};
// =========================================================

const SIEMENS_NS_URI = "http://www.siemens.com/simatic-s7-opcua";

// Erlaubte Befehle (Name in DB_Fern.Cmd). Einrichten, Teach, Uhr stellen und Schaltuhr-Bearbeitung
// bleiben bewusst dem Panel vor Ort vorbehalten.
const BEFEHLE = ["Quittieren", "Hand", "Auto", "Auto_Umschalten",
                 "Schnellstart", "Schnellstop", "Lampen_Ein", "Lampen_Aus",
                 "Gen_Start", "Gen_Stop", "Netzbetrieb", "Generatorbetrieb",
                 "Steckdose_1_Umschalten", "Steckdose_34_Umschalten", "Stumpfelbox_Umschalten",
                 "Auto_Daemmerung_Umschalten", "Auto_Uhr_Umschalten", "Auto_Astro_Umschalten",
                 "Wartung_Reset", "Kundenzaehler_Reset", "Probelauf_Start", "Netzueberwachung_Umschalten"];
// Befehls-Arrays: Name -> [kleinster Index, Anzahl]
const BEFEHL_ARRAYS = { Lampe_Umschalten: [1, 5], Audio_Umschalten: [0, 7] };

// Einstellungen, die von aussen geschrieben werden duerfen (nur bei "Fernbedienung erlaubt")
const EINSTELLUNGEN = {
  "DB_Astro.Versatz_Ein": { typ: DataType.Int16, min: -120, max: 120, ganz: true },
  "DB_Astro.Versatz_Aus": { typ: DataType.Int16, min: -120, max: 120, ganz: true },
  "DB_Parameter.Daemmerung_Ein": { typ: DataType.Float, min: 10, max: 400 },
  "DB_Parameter.Daemmerung_Hysterese": { typ: DataType.Float, min: 5, max: 100 }
};

let client = null, session = null, ns = 3, verbindet = null, lebenszeichen = 0;
let karte = new Map();          // "DB_HMI.Status.Versorgung" -> NodeId
let karteInfo = { knoten: 0, variablen: 0, schnittstellen: [] };
const angefragt = new Set();    // alle Namen, die die Webseite schon gelesen hat (fuer /api/knoten)

// Namenspfad vereinheitlichen: ["Protokoll", "[1]", "Code"] bzw. ["Protokoll", "Protokoll[1]", "Code"] -> "Protokoll[1].Code"
function schluesselAus(teile) {
  const aus = [];
  for (const t of teile) {
    const nurIndex = /^\[[\d,\s]+\]$/.test(t);
    const mitName = /^(.+?)(\[[\d,\s]+\])$/.exec(t);
    if (nurIndex && aus.length) aus[aus.length - 1] += t.replace(/\s/g, "");
    else if (mitName && aus.length && aus[aus.length - 1] === mitName[1]) aus[aus.length - 1] = t.replace(/\s/g, "");
    else aus.push(t);
  }
  return aus.join(".");
}

// Eigene Server-Schnittstellen ("M-Box") nummerieren Array-Elemente immer ab 0, unabhaengig von der Deklaration
// (Woche[1..7, 1..7] erscheint als Woche[0..6, 0..6]). Die Standard-SIMATIC-Schnittstelle nutzt die deklarierten Indizes.
// Damit die Webseite ueberall mit den Indizes aus TIA arbeiten kann, wird hier um die Untergrenze verschoben.
// Nicht aufgefuehrte Arrays beginnen bei 0 (z. B. Audio_Name[0..6], Alarm[0..1]).
const UNTERGRENZE = {
  "DB_Schaltuhr.Woche": 1, "DB_Schaltuhr.Datum": 1,
  "DB_Fern.Uhr.Woche": 1, "DB_Fern.Uhr.Kopieren_Auf": 1, "DB_Fern.Protokoll": 1, "DB_Fern.Cmd.Lampe_Umschalten": 1,
  "DB_HMI.Uhr.Woche": 1, "DB_HMI.Uhr.Kopieren_Auf": 1, "DB_HMI.Protokoll.Anzeige": 1, "DB_HMI.Cmd.Lampe_Umschalten": 1,
  "DB_HMI.Status.Lampe": 1, "DB_HMI.Module.Aktiv": 1, "DB_HMI.Module.Abgelaufen": 1, "DB_HMI.Module.Rest_Tage": 1,
  "DB_Parameter.Lampen_Auswahl": 1, "DB_Module.Modul": 1
};
function aufDeklariert(schluessel) {
  const ohneIndex = [];
  return schluessel.split(".").map(t => {
    const m = /^(.+?)\[([\d,]+)\]$/.exec(t);
    ohneIndex.push(m ? m[1] : t);
    if (!m) return t;
    const ug = UNTERGRENZE[ohneIndex.join(".")] || 0;
    return `${m[1]}[${m[2].split(",").map(x => Number(x) + ug).join(",")}]`;
  }).join(".");
}
// Durchsucht den Server ab "Objects" und merkt sich zu jedem Knoten unterhalb eines DB_... den Namenspfad.
async function karteAufbauen(sess) {
  const neu = new Map(), besucht = new Set(), schnittstellen = new Set();
  let ebene = [{ nodeId: "ns=0;i=85", pfad: [] }];
  let gezaehlt = 0;
  for (let tiefe = 0; tiefe < 10 && ebene.length && gezaehlt < 12000; tiefe++) {
    const naechste = [];
    for (let i = 0; i < ebene.length; i += 50) {
      const teil = ebene.slice(i, i + 50);
      const ergebnisse = await sess.browse(teil.map(t => ({
        nodeId: t.nodeId, referenceTypeId: "HierarchicalReferences", includeSubtypes: true,
        browseDirection: 0, nodeClassMask: 0, resultMask: 63
      })));
      for (let j = 0; j < teil.length; j++) {
        let r = ergebnisse[j];
        const refs = r.references ? [...r.references] : [];
        while (r.continuationPoint && r.continuationPoint.length) {
          r = await sess.browseNext(r.continuationPoint, false);
          if (r.references) refs.push(...r.references);
        }
        for (const ref of refs) {
          const id = ref.nodeId.toString();
          if (ref.nodeId.namespace === 0 || besucht.has(id)) continue;   // Standardknoten (Server, Typen) auslassen
          besucht.add(id); gezaehlt++;
          const pfad = [...teil[j].pfad, ref.browseName.name];
          const start = pfad.findIndex(n => /^DB_/.test(n));
          if (start >= 0) {
            let schluessel = schluesselAus(pfad.slice(start));
            if (ref.nodeId.namespace !== ns) schluessel = aufDeklariert(schluessel);   // eigene Schnittstelle: Index ab 0
            const vorhanden = neu.get(schluessel);
            // eigene Schnittstelle ("M-Box") hat Vorrang vor der Standard-SIMATIC-Schnittstelle
            if (!vorhanden || (vorhanden.ns === ns && ref.nodeId.namespace !== ns)) {
              neu.set(schluessel, { id, ns: ref.nodeId.namespace });
            }
            if (start === pfad.length - 1) schnittstellen.add(pfad.slice(0, start).join(" / ") + "  (ns=" + ref.nodeId.namespace + ")");
            if (/^DB_Protokoll$/.test(pfad[start])) continue;   // 200 Eintraege, wird nicht gebraucht
          }
          if (/^iDB_/.test(ref.browseName.name)) continue;          // Instanz-DBs (nur Standard-Schnittstelle) nicht durchsuchen
          naechste.push({ nodeId: id, pfad });
        }
      }
    }
    ebene = naechste;
  }
  karte = new Map([...neu].map(([k, v]) => [k, v.id]));
  karteInfo = { knoten: gezaehlt, variablen: karte.size, schnittstellen: [...schnittstellen] };
  console.log(`Knoten durchsucht: ${gezaehlt}, Variablen gefunden: ${karte.size}`);
  for (const s of schnittstellen) console.log("  DBs unter: " + s);
}

// Jeder OPC-UA-Aufruf bekommt ein Zeitlimit. Haengt eine Anfrage (z. B. weil die Verbindung im Hintergrund
// weggebrochen ist), wird die Verbindung verworfen und bei der naechsten Abfrage neu aufgebaut.
const ZEITLIMIT_MS = 8000;
function mitZeitlimit(versprechen, was, ms = ZEITLIMIT_MS) {
  let t;
  const ablauf = new Promise((_, nein) => { t = setTimeout(() => nein(new Error(`Zeitüberschreitung: ${was} (${ms / 1000} s)`)), ms); });
  return Promise.race([versprechen, ablauf]).finally(() => clearTimeout(t));
}

async function verbinden() {
  if (session) return session;
  if (verbindet) return verbindet;
  verbindet = (async () => {
    client = OPCUAClient.create({
      applicationName: "MBox-Fernbedienung",
      connectionStrategy: { initialDelay: 1000, maxRetry: 1 },
      securityMode: MessageSecurityMode[KONFIG.securityMode],
      securityPolicy: SecurityPolicy[KONFIG.securityPolicy],
      endpointMustExist: false,
      keepSessionAlive: true
    });
    client.on("connection_lost", () => { console.log("Verbindung zur SPS verloren"); trennen(); });
    await mitZeitlimit(client.connect(KONFIG.endpoint), "Verbinden", 8000);
    const identitaet = KONFIG.benutzer
      ? { type: UserTokenType.UserName, userName: KONFIG.benutzer, password: KONFIG.passwort }
      : undefined;
    const s = await mitZeitlimit(client.createSession(identitaet), "Sitzung anlegen", 8000);
    const nsArray = await mitZeitlimit(s.readNamespaceArray(), "Namespaces lesen");
    const idx = nsArray.indexOf(SIEMENS_NS_URI);
    if (idx >= 0) ns = idx;
    console.log(`Verbunden mit ${KONFIG.endpoint}`);
    nsArray.forEach((u, i) => console.log(`  ns=${i}: ${u}`));
    if (karte.size === 0) await mitZeitlimit(karteAufbauen(s), "Variablen suchen", 120000);   // nur beim ersten Mal suchen, nicht bei jedem Neuverbinden
    session = s;
    return session;
  })();
  try { return await verbindet; }
  catch (e) { await trennen(); throw e; }
  finally { verbindet = null; }
}

async function trennen() {
  // sofort freigeben, das Schliessen laeuft im Hintergrund (darf nicht selbst haengen bleiben)
  const s = session, c = client;
  session = null; client = null;
  if (s) mitZeitlimit(s.close(), "Sitzung schliessen", 3000).catch(() => {});
  if (c) mitZeitlimit(c.disconnect(), "Trennen", 3000).catch(() => {});
}

// Name -> NodeId (gefunden), sonst Schema der Standard-SIMATIC-Schnittstelle
const knoten = (name) => karte.get(name) ||
  `ns=${ns};s=` + name.split(".").map(t => { const m = /^(.+?)(\[.*\])$/.exec(t); return m ? `"${m[1]}"${m[2]}` : `"${t}"`; }).join(".");

async function lesen(namen) {
  const sess = await verbinden();
  const ergebnis = {};
  for (let i = 0; i < namen.length; i += 100) {
    const teil = namen.slice(i, i + 100);
    const start = Date.now();
    const werte = await mitZeitlimit(sess.read(teil.map(n => ({ nodeId: knoten(n), attributeId: AttributeIds.Value }))), "Lesen");
    if (Date.now() - start > 2000) console.log(`Lesen von ${teil.length} Werten dauerte ${Date.now() - start} ms`);
    teil.forEach((n, j) => {
      angefragt.add(n);
      if (!werte[j].statusCode.isGood()) { ergebnis[n] = { fehler: werte[j].statusCode.name }; return; }
      const v = werte[j].value ? werte[j].value.value : null;
      ergebnis[n] = (v && typeof v === "object" && v.length !== undefined && typeof v !== "string") ? Array.from(v) : v;
    });
  }
  return ergebnis;
}

async function schreiben(liste) {   // liste: [{ name, dataType, wert, array }]
  const sess = await verbinden();
  const status = await mitZeitlimit(sess.write(liste.map(e => ({
    nodeId: knoten(e.name), attributeId: AttributeIds.Value,
    value: { value: e.array
      ? { dataType: e.dataType, arrayType: VariantArrayType.Array, value: e.wert }
      : { dataType: e.dataType, value: e.wert } }
  }))), "Schreiben an SPS");
  const fehler = liste.map((e, i) => status[i].isGood() ? null : `${e.name}: ${status[i].toString()}`).filter(Boolean);
  if (fehler.length) throw new Error("Schreiben " + fehler.join("; "));
}

async function antwort(res, fn) {
  try { res.json({ ok: true, ...(await fn()) }); }
  catch (e) {
    console.log("Fehler:", e.message);
    if (!/^(Schreiben |Abgelehnt)/.test(e.message)) await trennen();
    res.json({ ok: false, fehler: e.message });
  }
}

const app = express();
app.use(express.json());
app.use(express.static(path.join(__dirname, "public")));

// Werte lesen: POST /api/lesen  { "namen": ["DB_HMI.Status.Versorgung", ...] }
app.post("/api/lesen", (req, res) => antwort(res, async () => {
  const namen = Array.isArray(req.body.namen) ? req.body.namen.filter(n => typeof n === "string" && /^DB_\w+/.test(n)) : [];
  return { werte: await lesen(namen.slice(0, 1500)) };
}));

// Befehl: POST /api/befehl/Schnellstart   bzw.  /api/befehl/Lampe_Umschalten?index=3
app.post("/api/befehl/:name", (req, res) => antwort(res, async () => {
  const name = req.params.name;
  if (BEFEHLE.includes(name)) {
    await schreiben([{ name: "DB_Fern.Cmd." + name, dataType: DataType.Boolean, wert: true }]);
  } else if (BEFEHL_ARRAYS[name]) {
    const [erster, anzahl] = BEFEHL_ARRAYS[name], idx = Number(req.query.index);
    if (!Number.isInteger(idx) || idx < erster || idx >= erster + anzahl) throw new Error("Abgelehnt: Index ungültig");
    const feld = new Array(anzahl).fill(false); feld[idx - erster] = true;   // SPS setzt alle Bits wieder zurueck
    await schreiben([{ name: "DB_Fern.Cmd." + name, dataType: DataType.Boolean, wert: feld, array: true }]);
  } else {
    throw new Error("Abgelehnt: unbekannter Befehl");
  }
  console.log("Befehl gesendet:", name, req.query.index ?? "");
  return {};
}));

// ===================== Zeitschaltuhr =====================
// Eigener Puffer DB_Fern.Uhr: erst Daten schreiben, dann Befehl. Die SPS prueft, uebernimmt, sortiert
// und meldet das Ergebnis in DB_Fern.Uhr.Meldung (1 gespeichert, 2 ungueltig, 3 Vergangenheit, 4 voll, 5 geloescht).
const UHR_MELDUNG = { 1: "gespeichert", 2: "Eingabe ungültig", 3: "liegt in der Vergangenheit", 4: "Liste voll (max. 20)", 5: "gelöscht" };

async function uhrBefehl(daten, befehl) {
  const ganz = (x, min, max) => { const n = Number(x); if (!Number.isInteger(n) || n < min || n > max) throw new Error(`Abgelehnt: Wert ${x} ungültig`); return n; };
  const erlaubt = (await lesen(["DB_HMI.Status.Fern_Erlaubt"]))["DB_HMI.Status.Fern_Erlaubt"];
  if (erlaubt !== true) throw new Error("Abgelehnt: am Panel ist \"Fernbedienung erlaubt\" aus");
  await schreiben([{ name: "DB_Fern.Uhr.Meldung", dataType: DataType.Int16, wert: 0 }, ...daten(ganz)]);
  await schreiben([{ name: "DB_Fern.Cmd." + befehl, dataType: DataType.Boolean, wert: true }]);
  // Rueckmeldung der SPS abwarten (max. 2 s)
  for (let i = 0; i < 10; i++) {
    await new Promise(r => setTimeout(r, 200));
    const m = (await lesen(["DB_Fern.Uhr.Meldung"]))["DB_Fern.Uhr.Meldung"];
    if (m) { console.log("Schaltuhr:", befehl, "->", UHR_MELDUNG[m] || m); if (m === 1 || m === 5) return { meldung: UHR_MELDUNG[m] }; throw new Error("Abgelehnt: " + (UHR_MELDUNG[m] || m)); }
  }
  throw new Error("Abgelehnt: keine Rückmeldung der SPS (Befehl angenommen? Modul Fernzugriff / Wartungsmodus prüfen)");
}

// Wochenprogramm: POST /api/uhr/woche
// { tag: 1..7, paare: [ {aktivEin, einStd, einMin, aktivAus, ausStd, ausMin} x7 ], ziel: "tag" | "alle" | "auswahl", kopieren: [7 x bool] }
app.post("/api/uhr/woche", (req, res) => antwort(res, async () => {
  const { tag, paare, ziel, kopieren } = req.body;
  if (!Array.isArray(paare) || paare.length !== 7) throw new Error("Abgelehnt: 7 Paare erwartet");
  const befehl = { tag: "Woche_Speichern", alle: "Woche_Auf_Alle_Tage", auswahl: "Woche_Auf_Auswahl" }[ziel];
  if (!befehl) throw new Error("Abgelehnt: Ziel ungültig");
  return uhrBefehl(ganz => {
    const liste = [{ name: "DB_Fern.Uhr.Tag", dataType: DataType.Int16, wert: ganz(tag, 1, 7) }];
    paare.forEach((p, i) => {
      const b = `DB_Fern.Uhr.Woche[${i + 1}].`;
      liste.push(
        { name: b + "Aktiv_Ein", dataType: DataType.Boolean, wert: !!p.aktivEin },
        { name: b + "Aktiv_Aus", dataType: DataType.Boolean, wert: !!p.aktivAus },
        { name: b + "Ein_Std", dataType: DataType.Int16, wert: ganz(p.einStd, 0, 23) },
        { name: b + "Ein_Min", dataType: DataType.Int16, wert: ganz(p.einMin, 0, 59) },
        { name: b + "Aus_Std", dataType: DataType.Int16, wert: ganz(p.ausStd, 0, 23) },
        { name: b + "Aus_Min", dataType: DataType.Int16, wert: ganz(p.ausMin, 0, 59) });
    });
    if (ziel === "auswahl") {
      if (!Array.isArray(kopieren) || kopieren.length !== 7) throw new Error("Abgelehnt: Zieltage fehlen");
      liste.push({ name: "DB_Fern.Uhr.Kopieren_Auf", dataType: DataType.Boolean, wert: kopieren.map(Boolean), array: true });
    }
    return liste;
  }, befehl);
}));

// Datums-Schaltzeit hinzufuegen: POST /api/uhr/datum  { jahr, monat, tag, std, min, einschalten }
app.post("/api/uhr/datum", (req, res) => antwort(res, async () => {
  const d = req.body;
  return uhrBefehl(ganz => [
    { name: "DB_Fern.Uhr.Neu.Jahr", dataType: DataType.Int16, wert: ganz(d.jahr, 2024, 2099) },
    { name: "DB_Fern.Uhr.Neu.Monat", dataType: DataType.Int16, wert: ganz(d.monat, 1, 12) },
    { name: "DB_Fern.Uhr.Neu.Tag", dataType: DataType.Int16, wert: ganz(d.tag, 1, 31) },
    { name: "DB_Fern.Uhr.Neu.Std", dataType: DataType.Int16, wert: ganz(d.std, 0, 23) },
    { name: "DB_Fern.Uhr.Neu.Min", dataType: DataType.Int16, wert: ganz(d.min, 0, 59) },
    { name: "DB_Fern.Uhr.Neu.Einschalten", dataType: DataType.Boolean, wert: !!d.einschalten }
  ], "Datum_Hinzufuegen");
}));

// Datums-Schaltzeit loeschen: POST /api/uhr/datum_loeschen  { index: 1..20 }
app.post("/api/uhr/datum_loeschen", (req, res) => antwort(res, async () =>
  uhrBefehl(ganz => [{ name: "DB_Fern.Uhr.Loesch_Index", dataType: DataType.Int16, wert: ganz(req.body.index, 1, 20) }], "Datum_Loeschen")));

// Einstellung schreiben: POST /api/einstellung  { "name": "DB_Astro.Versatz_Ein", "wert": 20 }
app.post("/api/einstellung", (req, res) => antwort(res, async () => {
  const { name } = req.body, def = EINSTELLUNGEN[name], wert = Number(req.body.wert);
  if (!def) throw new Error("Abgelehnt: Einstellung nicht freigegeben");
  if (!isFinite(wert) || wert < def.min || wert > def.max || (def.ganz && !Number.isInteger(wert)))
    throw new Error(`Abgelehnt: Wert muss zwischen ${def.min} und ${def.max} liegen`);
  const erlaubt = (await lesen(["DB_HMI.Status.Fern_Erlaubt"]))["DB_HMI.Status.Fern_Erlaubt"];
  if (erlaubt !== true) throw new Error("Abgelehnt: am Panel ist \"Fernbedienung erlaubt\" aus");
  await schreiben([{ name, dataType: def.typ, wert }]);
  console.log("Einstellung:", name, "=", wert);
  return {};
}));

// GPS-Position wie der Raspberry Pi schreiben: /api/gps?breite=53.55&laenge=9.99&fix=1
app.post("/api/gps", (req, res) => antwort(res, async () => {
  const breite = Number(req.query.breite), laenge = Number(req.query.laenge), fix = req.query.fix === "1";
  if (!isFinite(breite) || !isFinite(laenge)) throw new Error("Abgelehnt: Breite/Länge ungültig");
  await schreiben([
    { name: "DB_Fern.GPS.Breitengrad", dataType: DataType.Float, wert: breite },
    { name: "DB_Fern.GPS.Laengengrad", dataType: DataType.Float, wert: laenge },
    { name: "DB_Fern.GPS.Fix", dataType: DataType.Boolean, wert: fix }
  ]);
  console.log(`GPS gesendet: ${breite} / ${laenge} Fix=${fix}`);
  return {};
}));

// Diagnose: welche NodeId wurde fuer welche Variable gefunden?
// Aufruf: http://localhost:8080/api/knoten          (alle Variablen, die die Webseite liest)
//         http://localhost:8080/api/knoten?alle=1   (alle gefundenen Variablen)
app.get("/api/knoten", async (req, res) => {
  try {
    await verbinden();
    const zeile = n => ({ name: n, nodeId: knoten(n), gefunden: karte.has(n) });
    const benutzt = [...angefragt].sort().map(zeile);
    res.json({
      ...karteInfo,
      siemensNamespace: ns,
      nichtGefunden: benutzt.filter(z => !z.gefunden).map(z => z.name),
      webseite: benutzt,
      alle: req.query.alle ? [...karte.keys()].sort().map(zeile) : "mit ?alle=1 anzeigen"
    });
  } catch (e) {
    res.json({ fehler: e.message });
  }
});

// Diagnose: Knoten des Servers durchklicken
// Aufruf: http://localhost:8080/api/browse            (Start: Objects)
//         http://localhost:8080/api/browse?node=<NodeId>
app.get("/api/browse", async (req, res) => {
  try {
    const sess = await verbinden();
    const start = req.query.node || "ns=0;i=85";   // 85 = Objects
    let ergebnis = await sess.browse({
      nodeId: start, referenceTypeId: "HierarchicalReferences", includeSubtypes: true,
      browseDirection: 0, nodeClassMask: 0, resultMask: 63
    });
    let refs = ergebnis.references ? [...ergebnis.references] : [];
    while (ergebnis.continuationPoint && ergebnis.continuationPoint.length) {
      ergebnis = await sess.browseNext(ergebnis.continuationPoint, false);
      if (ergebnis.references) refs.push(...ergebnis.references);
    }
    res.json({
      knoten: start,
      status: ergebnis.statusCode.name,
      anzahl: refs.length,
      kinder: refs.map(r => ({
        name: r.browseName.toString(),
        nodeId: r.nodeId.toString(),
        weiter: "/api/browse?node=" + encodeURIComponent(r.nodeId.toString())
      }))
    });
  } catch (e) {
    await trennen();
    res.json({ fehler: e.message });
  }
});

// Diagnose: gefundene Variablen nach Namen filtern
// Aufruf: http://localhost:8080/api/suche?text=Schnellstart
app.get("/api/suche", async (req, res) => {
  const text = String(req.query.text || "DB_HMI").toLowerCase();
  try {
    await verbinden();
    const treffer = [...karte].filter(([k]) => k.toLowerCase().includes(text)).map(([k, v]) => ({ name: k, nodeId: v }));
    res.json({ gesucht: text, anzahl: treffer.length, treffer });
  } catch (e) {
    res.json({ fehler: e.message });
  }
});

// Karte neu aufbauen (z. B. nach Aenderung der Server-Schnittstelle in TIA)
app.post("/api/neu_verbinden", async (req, res) => {
  await trennen();
  karte = new Map();
  try { await verbinden(); res.json({ ok: true, ...karteInfo }); }
  catch (e) { res.json({ ok: false, fehler: e.message }); }
});

// Lebenszeichen der Gegenseite alle 10 s hochzaehlen -> in der SPS wird St_Fern_Verbunden = 1
setInterval(async () => {
  if (!session) return;
  try {
    lebenszeichen = (lebenszeichen + 1) % 32767;
    await schreiben([{ name: "DB_Fern.Lebenszeichen_Web", dataType: DataType.Int16, wert: lebenszeichen }]);
  } catch (e) {
    // Verbindung nur bei echten Verbindungsfehlern neu aufbauen, nicht bei "Variable unbekannt"
    console.log("Lebenszeichen:", e.message);
    if (!/^Schreiben/.test(e.message)) await trennen();
  }
}, 10000);

app.listen(KONFIG.webPort, KONFIG.webHost, () => {
  console.log(`Bedienprogramm laeuft: http://${KONFIG.webHost}:${KONFIG.webPort}`);
  console.log(`SPS-Endpunkt: ${KONFIG.endpoint}`);
});
``

## Anhang C – `.env.beispiel`

``ini
# Vorlage: kopieren nach .env und anpassen. Die .env NIE ins Git / in Doku / in Chats.
# Adresse der SPS (OPC-UA-Server der S7-1214C)
OPCUA_ENDPOINT=opc.tcp://192.168.0.100:4840
# Test: None/None. Betrieb: SignAndEncrypt/Basic256Sha256 (in TIA freigeben)
OPCUA_SECURITY_MODE=None
OPCUA_SECURITY_POLICY=None
# OPC-UA-Benutzer aus TIA (CPU > OPC UA > Server > Security > Benutzerverwaltung). Leer = Gastzugang
OPCUA_BENUTZER=
OPCUA_PASSWORT=
# Webserver: 127.0.0.1 = nur hinter Reverse-Proxy erreichbar (empfohlen)
WEB_HOST=127.0.0.1
WEB_PORT=8080
``

## Anhang D – `public/index.html`

``html
<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>M-Box Fernbedienung</title>
<style>
  * { box-sizing: border-box; }
  body { font-family: "Segoe UI", Arial, sans-serif; margin: 0; background: #f3f5f8; color: #1a1a1a; font-size: 15px; }
  header { background: #1F4E78; color: #fff; padding: 10px 16px; display: flex; flex-wrap: wrap; gap: 8px 16px; justify-content: space-between; align-items: center; }
  header .rechts { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; font-size: 14px; }
  .pill { padding: 2px 10px; border-radius: 12px; background: rgba(255,255,255,.15); white-space: nowrap; }
  .pill.ok { background: #2e7d32; } .pill.warn { background: #b26a00; } .pill.err { background: #c62828; }
  nav { display: flex; flex-wrap: wrap; gap: 4px; padding: 8px 16px 0; max-width: 1100px; margin: 0 auto; }
  nav button { border: 1px solid #c9d1db; border-bottom: none; border-radius: 8px 8px 0 0; background: #e6eaef; padding: 8px 14px; font-size: 14px; cursor: pointer; }
  nav button.aktiv { background: #fff; font-weight: 600; }
  main { max-width: 1100px; margin: 0 auto; padding: 0 16px 24px; }
  .seite { display: none; background: #fff; border: 1px solid #c9d1db; border-radius: 0 8px 8px 8px; padding: 16px; }
  .seite.aktiv { display: block; }
  .raster { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 14px; }
  .karte { border: 1px solid #d6dbe2; border-radius: 10px; padding: 14px; }
  h2 { font-size: 16px; margin: 0 0 10px 0; color: #1F4E78; }
  .buttons { display: flex; flex-wrap: wrap; gap: 8px; margin: 8px 0; }
  button.b { font-size: 14px; padding: 9px 14px; border-radius: 8px; border: 1px solid #9aa5b1; background: #fff; cursor: pointer; }
  button.b:active { transform: scale(0.98); }
  button.haupt { background: #1F4E78; color: #fff; border-color: #1F4E78; }
  button.an { background: #2e7d32; color: #fff; border-color: #2e7d32; }
  button.laeuft { background: #f2c94c; border-color: #d4a017; }
  table { width: 100%; border-collapse: collapse; }
  td, th { padding: 5px 4px; border-bottom: 1px solid #eef0f3; text-align: left; vertical-align: top; }
  td:first-child { color: #555; }
  th { font-size: 13px; color: #555; font-weight: 600; }
  .lampen { display: flex; gap: 10px; margin: 6px 0 10px; }
  .lampe { width: 46px; height: 46px; border-radius: 50%; border: 2px solid #9aa5b1; background: #e4e7eb; font-weight: 600; cursor: pointer; position: relative; }
  .lampe.an { background: #f2c94c; border-color: #d4a017; }
  .lampe.aus_gewaehlt::after { content: ""; position: absolute; right: -2px; top: -2px; width: 10px; height: 10px; border-radius: 50%; background: #9aa5b1; }
  .dot { display: inline-block; width: 12px; height: 12px; border-radius: 50%; background: #d5d9df; vertical-align: -1px; }
  .dot.gruen { background: #2e7d32; } .dot.gelb { background: #f2c94c; } .dot.rot { background: #c62828; }
  .balken { height: 14px; background: #e4e7eb; border-radius: 7px; overflow: hidden; margin-top: 3px; }
  .balken div { height: 100%; background: #1F4E78; }
  .balken div.warn { background: #d4a017; } .balken div.err { background: #c62828; }
  .hinweis { padding: 8px 12px; border-radius: 8px; margin: 0 0 12px; }
  .hinweis.warn { background: #fff4d6; border: 1px solid #e8c766; }
  .hinweis.err { background: #fde3e3; border: 1px solid #e6a1a1; }
  .klein { font-size: 13px; color: #555; }
  .badge { font-size: 12px; padding: 1px 7px; border-radius: 8px; background: #e4e7eb; }
  .badge.S { background: #fde3e3; color: #8b1a1a; } .badge.I { background: #e3eefb; color: #1F4E78; }
  input[type=number], input[type=text] { width: 90px; padding: 5px 6px; font-size: 14px; border: 1px solid #9aa5b1; border-radius: 6px; }
  .einst { display: grid; grid-template-columns: 1fr auto auto; gap: 6px 8px; align-items: center; }
  .uhr td { font-size: 13px; white-space: nowrap; }
  h2.titel { display: flex; justify-content: space-between; align-items: center; gap: 8px; flex-wrap: wrap; }
  input[type=time], input[type=date], select { padding: 4px 6px; font-size: 14px; border: 1px solid #9aa5b1; border-radius: 6px; }
  #k_uhr_edit input[type=time] { width: 96px; }
  #k_uhr_edit input:disabled { opacity: .45; }
  #k_woche tr.waehlbar { cursor: pointer; } #k_woche tr.gewaehlt td { background: #e3eefb; }
  button.klein { font-size: 12px; padding: 3px 9px; border-radius: 6px; border: 1px solid #9aa5b1; background: #fff; cursor: pointer; }
  .geaendert { color: #b26a00; font-size: 13px; }
  .io { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 2px 14px; font-size: 13px; }
  #meldung { position: fixed; left: 50%; bottom: 18px; transform: translateX(-50%); background: #333; color: #fff; padding: 8px 16px; border-radius: 8px; font-size: 14px; display: none; max-width: 90vw; }
</style>
<script src="texte.js"></script>
</head>
<body>
<header>
  <strong>M-Box Fernbedienung</strong>
  <div class="rechts">
    <span id="h_zeit" class="pill">--:--</span>
    <span id="h_stoerung" class="pill">Störungen</span>
    <span id="h_fern" class="pill">Fernbedienung</span>
    <span id="h_verbindung" class="pill">verbinde …</span>
  </div>
</header>
<nav id="tabs">
  <button data-seite="uebersicht" class="aktiv">Übersicht</button>
  <button data-seite="automatik">Automatik</button>
  <button data-seite="audio">Steckdosen &amp; Audio</button>
  <button data-seite="uhr">Zeitschaltuhr</button>
  <button data-seite="meldungen">Meldungen &amp; Protokoll</button>
  <button data-seite="service">Service</button>
  <button data-seite="diagnose">Diagnose</button>
</nav>
<main>
  <div id="hinweise" style="margin-top:12px"></div>

  <section class="seite aktiv" id="s_uebersicht">
    <div class="raster">
      <div class="karte"><h2>Licht</h2><div id="k_licht"></div>
        <div class="buttons">
          <button class="b haupt" onclick="befehl('Schnellstart')">Schnellstart</button>
          <button class="b" onclick="befehl('Schnellstop')">Schnellstop</button>
          <button class="b" onclick="befehl('Lampen_Ein')">Lampen ein</button>
          <button class="b" onclick="befehl('Lampen_Aus')">Lampen aus</button>
        </div>
        <p class="klein">Lampe antippen = einzeln ein/aus. Schnellstart startet im Generatorbetrieb zuerst den Motor.</p>
      </div>
      <div class="karte"><h2>Versorgung &amp; Generator</h2><div id="k_energie"></div>
        <div class="buttons">
          <button class="b" id="b_netz" onclick="befehl('Netzbetrieb')">Netzbetrieb</button>
          <button class="b" id="b_gen" onclick="befehl('Generatorbetrieb')">Generatorbetrieb</button>
        </div>
        <div class="buttons">
          <button class="b" onclick="befehl('Gen_Start')">Generator start</button>
          <button class="b" onclick="befehl('Gen_Stop')">Generator stop</button>
        </div>
      </div>
      <div class="karte"><h2 class="titel">Netzüberwachung <button class="b" id="b_nub" onclick="befehl('Netzueberwachung_Umschalten')">einschalten</button></h2>
        <div id="k_nub"></div>
        <p class="klein">Wirkt nur im Netzbetrieb: Fällt das Netz aus, startet der Generator und alle Lampen gehen an. Ist das Netz wieder stabil da, geht es nach der Rückkehrzeit zurück in Wartestellung.</p>
      </div>
      <div class="karte"><h2>Tank &amp; Messwerte</h2><div id="k_mess"></div></div>
    </div>
  </section>

  <section class="seite" id="s_automatik">
    <div class="raster">
      <div class="karte"><h2 class="titel">Automatik-Quellen <button class="b" id="b_auto_akt" onclick="befehl('Auto_Umschalten')">Automatik aktivieren</button></h2>
        <p class="klein">Wirken nur in Betriebsart Auto. Wer zuerst „an“ bzw. „aus“ sagt, schaltet. Nach SPS-Neustart sind alle Quellen abgewählt.</p>
        <div class="buttons">
          <button class="b" id="b_qd" onclick="befehl('Auto_Daemmerung_Umschalten')">Dämmerung</button>
          <button class="b" id="b_qu" onclick="befehl('Auto_Uhr_Umschalten')">Zeitschaltuhr</button>
          <button class="b" id="b_qa" onclick="befehl('Auto_Astro_Umschalten')">Astro</button>
        </div>
        <div id="k_auto"></div>
      </div>
      <div class="karte"><h2>Astro-Uhr</h2><div id="k_astro"></div>
        <h2 style="margin-top:14px">GPS wie Raspberry Pi senden</h2>
        <div class="buttons" style="align-items:center">
          <label>Breite <input type="text" id="gps_breite" value="53.55"></label>
          <label>Länge <input type="text" id="gps_laenge" value="9.99"></label>
          <label><input type="checkbox" id="gps_fix" checked> Fix</label>
          <button class="b" onclick="gps()">Senden</button>
        </div>
      </div>
      <div class="karte"><h2>Einstellungen</h2>
        <div class="einst">
          <span>Astro: Ein [min nach Untergang]</span><input type="number" id="e_DB_Astro.Versatz_Ein" min="-120" max="120"><button class="b" onclick="einstellen('DB_Astro.Versatz_Ein')">Setzen</button>
          <span>Astro: Aus [min nach Aufgang]</span><input type="number" id="e_DB_Astro.Versatz_Aus" min="-120" max="120"><button class="b" onclick="einstellen('DB_Astro.Versatz_Aus')">Setzen</button>
          <span>Dämmerung: Ein unter [Lux]</span><input type="number" id="e_DB_Parameter.Daemmerung_Ein" min="10" max="400"><button class="b" onclick="einstellen('DB_Parameter.Daemmerung_Ein')">Setzen</button>
          <span>Dämmerung: Hysterese [Lux]</span><input type="number" id="e_DB_Parameter.Daemmerung_Hysterese" min="5" max="100"><button class="b" onclick="einstellen('DB_Parameter.Daemmerung_Hysterese')">Setzen</button>
        </div>
        <p class="klein">Der graue Wert im Feld ist der aktuelle Wert. Schreiben geht nur bei „Fernbedienung erlaubt“.</p>
      </div>
    </div>
  </section>

  <section class="seite" id="s_audio">
    <div class="raster">
      <div class="karte"><h2>Steckdosen</h2><div class="buttons" id="k_steckdosen"></div></div>
      <div class="karte"><h2>Stumpfelbox / Audio</h2><div id="k_audio"></div></div>
    </div>
  </section>

  <section class="seite" id="s_uhr">
    <div class="raster">
      <div class="karte"><h2>Wochenprogramm bearbeiten</h2>
        <div class="buttons" id="k_uhr_tage"></div>
        <table class="uhr" id="k_uhr_edit"></table>
        <div class="buttons">
          <button class="b haupt" id="b_uhr_tag" onclick="uhrSpeichern('tag')">Speichern</button>
          <button class="b" onclick="uhrSpeichern('alle')">Auf alle Tage</button>
        </div>
        <div class="buttons" style="align-items:center">
          <button class="b" onclick="uhrSpeichern('auswahl')">Auf ausgewählte Tage:</button>
          <span id="k_uhr_kopieren"></span>
        </div>
        <p class="klein">Jedes Paar hat einen Ein- und einen Aus-Schaltpunkt, beide einzeln abschaltbar. Liegt „Aus“ vor „Ein“, ist der Aus-Punkt am Folgetag. Es gilt immer der zuletzt erreichte Schaltpunkt.</p>
      </div>
      <div class="karte"><h2>Datums-Schaltzeiten</h2>
        <table id="k_datum"></table>
        <h2 style="margin-top:14px">Neue Datums-Schaltzeit</h2>
        <div class="buttons" style="align-items:center">
          <input type="date" id="ud_datum">
          <input type="time" id="ud_zeit">
          <select id="ud_art"><option value="1">Ein</option><option value="0">Aus</option></select>
          <button class="b" onclick="datumHinzu()">Hinzufügen</button>
        </div>
        <p class="klein">Eine fällige Datums-Schaltzeit übersteuert das Wochenprogramm bis zum nächsten Schaltpunkt der Woche und wird danach automatisch gelöscht. Max. 20 Einträge.</p>
      </div>
    </div>
    <div class="karte" style="margin-top:14px"><h2>Wochenübersicht</h2>
      <div style="overflow-x:auto"><table class="uhr" id="k_woche"></table></div>
      <p class="klein">Zeile antippen, um den Tag zu bearbeiten.</p>
    </div>
  </section>

  <section class="seite" id="s_meldungen">
    <div class="karte"><h2>Anstehende Meldungen</h2><div id="k_meldungen"></div>
      <div class="buttons"><button class="b haupt" onclick="befehl('Quittieren')">Quittieren</button></div>
    </div>
    <div class="karte" style="margin-top:14px"><h2>Ereignisprotokoll (neueste 30)</h2><table id="k_protokoll"></table></div>
  </section>

  <section class="seite" id="s_service">
    <div class="raster">
      <div class="karte"><h2>Zähler &amp; Wartung</h2><div id="k_zaehler"></div>
        <div class="buttons">
          <button class="b" onclick="befehl('Wartung_Reset', null, 'Wartung als erledigt quittieren?')">Wartung erledigt</button>
          <button class="b" onclick="befehl('Kundenzaehler_Reset', null, 'Kundenzähler wirklich auf 0 setzen?')">Kundenzähler zurücksetzen</button>
        </div>
      </div>
      <div class="karte"><h2>Probelauf</h2><div id="k_probelauf"></div>
        <div class="buttons"><button class="b" onclick="befehl('Probelauf_Start', null, 'Probelauf jetzt starten? Der Generator läuft an.')">Probelauf starten</button></div>
      </div>
      <div class="karte"><h2>Zusatzmodule</h2><div id="k_module"></div></div>
      <div class="karte"><h2>Anlage</h2><div id="k_anlage"></div></div>
    </div>
  </section>

  <section class="seite" id="s_diagnose">
    <div class="karte"><h2>Eingänge, Ausgänge, Rohwerte</h2><div class="io" id="k_io"></div></div>
  </section>
</main>
<div id="meldung"></div>

<script>
// ===================== Variablen =====================
const ST = "DB_HMI.Status.";
const STATUS_NAMEN = ["Betriebsart","Versorgung","Netzwaechter","Licht_Ein","Lampen_Alle_An","Lampen_Alle_Aus","Notbetrieb",
  "NUB_Rueckkehr_Laeuft","NUB_Rest_Min","NUB_Rest_Sek","Gen_Zustand","Netzschuetz","Generatorschuetz","Lampe","Ladung_Aktiv",
  "Abschaltung_Aktiv","Umschalten_Gesperrt","Uhr_Gueltig","Uhrzeit_Text","Datum_Text","Datum_Uebersteuert","Auto_Licht_Soll",
  "Auto_Daemmerung","Auto_Uhr","Auto_Astro","Astro_An","Astro_Aufgang","Astro_Untergang","Astro_Ein","Astro_Aus","Astro_Sonderfall",
  "GPS_Aktuell","Dunkel","Mast_Zustand","Mast_Heben_Gesperrt","Mast_Senken_Gesperrt","Windalarm","Sammelstoerung","Stoerung_Zustand",
  "Steckdose_1","Steckdose_34","Stumpfelbox","Stumpfelbox_Zustand","Audio_Bereit","Audio_Kanal","Tank_Extern_Angeschlossen",
  "Tank_Extern_Plausibel","Tank_Extern_Aktiv","Probelauf_Aktiv","Probelauf_Ergebnis","Tank_Niedrig","Tank_Kritisch","Wartungsmodus",
  "Fern_Erlaubt","Fern_Verbunden","Lebenszeichen","Akku_Zustand"];
const ZAEHLER_NAMEN = ["Betrieb_h","Betrieb_min","Wartung_Bei_h","Wartung_Rest_h","Wartung_Rest_min","Wartung_Faellig","Wartung_Vorwarnung",
  "Wartung_Datum_Jahr","Wartung_Datum_Monat","Wartung_Datum_Tag","Wartung_Rest_Tage","Kunde_h","Kunde_min","Kunde_Minuten_Gesamt"];
const BASIS = [
  ...STATUS_NAMEN.map(n => ST + n),
  ...["Wind","Daemmerung","Fuellstand_Intern","Fuellstand_Extern"].map(n => "DB_HMI.Analog." + n),
  "DB_Parameter.NUB_Ausfall_Verz", "DB_Parameter.NUB_Rueckkehr_Zeit",
  "DB_HMI.Module.Aktiv", "DB_HMI.Module.Abgelaufen", "DB_HMI.Module.Rest_Tage", "DB_HMI.Alarm",
  ...ZAEHLER_NAMEN.map(n => "DB_HMI.Zaehler." + n),
  "DB_Parameter.Lampen_Auswahl", "DB_Parameter.Audio_Name", "DB_Parameter.Daemmerung_Ein", "DB_Parameter.Daemmerung_Hysterese",
  "DB_Parameter.Generator_Gesperrt", "DB_Parameter.Netzueberwachung_Ein",
  "DB_Astro.Breite", "DB_Astro.Laenge", "DB_Astro.Position_Gueltig", "DB_Astro.Versatz_Ein", "DB_Astro.Versatz_Aus"
];
const ZEIT = ["Jahr","Monat","Tag","Std","Min","Sek"];
const EXTRA = {
  meldungen: Array.from({ length: 30 }, (_, i) => [...ZEIT.map(z => `DB_Fern.Protokoll[${i + 1}].Zeit.${z}`), `DB_Fern.Protokoll[${i + 1}].Code`]).flat(),
  uhr: [
    ...Array.from({ length: 49 }, (_, k) => ["Aktiv_Ein","Aktiv_Aus","Ein_Std","Ein_Min","Aus_Std","Aus_Min"]
      .map(f => `DB_Schaltuhr.Woche[${Math.floor(k / 7) + 1},${k % 7 + 1}].${f}`)).flat(),
    ...Array.from({ length: 20 }, (_, i) => ["Belegt","Einschalten","Jahr","Monat","Tag","Std","Min"].map(f => `DB_Schaltuhr.Datum[${i + 1}].${f}`)).flat()
  ],
  diagnose: ["DI_NotAus_OK","DI_Isowaechter_1","DI_Isowaechter_2","DI_Stoerung_Allgemein","DI_Motor_Betriebsbereit","DI_Motor_Stoerung",
    "DI_Batterieueberwachung","DI_Taster_Mast_Ab","DI_Taster_Mast_Auf","DI_Mast_Einfahrposition","DI_Mast_SichereHoehe","DI_Tank_Extern_Stecker",
    "DI_Sicherheitswanne_OK","DI_Netzwaechter","DI_Akkupack_Angeschlossen","DI_Akkupack_Stoerung","AI_Windsensor","AI_Daemmerungssensor",
    "AI_Fuellstand_Intern","AI_Fuellstand_Extern","AI_Temp_Gehaeuse","AI_Temp_Netzteil","DQ_Netzschuetz","DQ_Generatorschuetz",
    "DQ_Akku_Einspeisung","DQ_Akku_Bruecke","DQ_Akku_Abgabe","DQ_Lampe_1","DQ_Lampe_2","DQ_Lampe_3","DQ_Lampe_4","DQ_Lampe_5",
    "DQ_Audiosignal_1","DQ_Audiosignal_2","DQ_Audiosignal_3","DQ_Audiosignal_4","DQ_Audiosignal_5","DQ_Audiosignal_6","DQ_Steckdose_1",
    "DQ_Steckdose_3_4","DQ_Hydraulikmotor","DQ_Mast_Senken","DQ_Generator_RemoteStart","DQ_StumpfelBox","DQ_Audioverstaerker",
    "DQ_Akku_Extern_EinAus","DQ_Tank_Umschaltventil","DQ_Generator_DisplayFreigabe"].map(n => "DB_HMI.IO." + n)
};

// ===================== Hilfen =====================
let W = {}, seite = "uebersicht", laeuft = false;
const roh = n => W[n];
const v = n => { const x = W[n]; return (x && typeof x === "object" && !Array.isArray(x) && x.fehler) ? undefined : x; };
const s = n => v(ST + n);
const ja = b => b === true ? "ja" : b === false ? "nein" : "–";
const dot = (b, farbe = "gruen") => `<span class="dot ${b === true ? farbe : ""}"></span>`;
const zeile = (label, wert) => `<tr><td>${label}</td><td>${wert ?? "–"}</td></tr>`;
const tab = zeilen => `<table>${zeilen.join("")}</table>`;
const z2 = x => String(typeof x === "number" ? x : 0).padStart(2, "0");
const zahl = (x, st = 1) => typeof x === "number" ? x.toLocaleString("de-DE", { minimumFractionDigits: st, maximumFractionDigits: st }) : "–";
const text = (map, x) => map[x] ?? (x === undefined ? "–" : x);
const fehlt = n => { const x = roh(n); return x && x.fehler ? ` <span class="klein" title="${x.fehler}">(nicht lesbar)</span>` : ""; };
const esc = t => String(t ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

const GEN = { 0: "Aus", 10: "Startet", 20: "Läuft", 30: "Fährt herunter" };
const MAST = { 0: "Ruhe", 10: "Heben", 20: "Senken (Tippen)", 30: "Senken automatisch", 40: "Senken wegen Wind" };
const AKKU = { 0: "kein Akkupack", 10: "Brücke offen", 20: "Einspeisung", 30: "Betrieb", 99: "Not-Aus" };
const PROBE = { 0: "noch keiner", 1: "OK", 2: "Fehler", 3: "abgebrochen" };
const SONDER = { 0: "normal", 1: "Polarnacht (immer an)", 2: "Mitternachtssonne (immer aus)", 3: "keine Position oder Uhrzeit" };
const BOX = { 0: "aus", 1: "fährt hoch (10 s)", 2: "bereit" };
const TAGE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"];
const MODULE = ["Audio", "Akkupack", "Netzüberwachung", "Fernzugriff"];

function zeigeMeldung(t, fehler) {
  const m = document.getElementById("meldung");
  m.textContent = t; m.style.background = fehler ? "#c62828" : "#333"; m.style.display = "block";
  clearTimeout(zeigeMeldung.t); zeigeMeldung.t = setTimeout(() => m.style.display = "none", fehler ? 6000 : 2000);
}
async function post(url, body) {
  // nach 15 s abbrechen, damit eine haengende Anfrage die Aktualisierung nicht blockiert
  const abbruch = new AbortController(), t = setTimeout(() => abbruch.abort(), 20000);
  try {
    const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: body ? JSON.stringify(body) : undefined, signal: abbruch.signal });
    return await r.json();
  } catch (e) {
    if (e.name === "AbortError") throw new Error("keine Antwort vom Programm (20 s) - beim ersten Verbinden sucht es noch die Variablen, sonst Eingabeaufforderung prüfen");
    throw e;
  } finally { clearTimeout(t); }
}

// ===================== Aktionen =====================
async function befehl(name, index, frage) {
  if (frage && !confirm(frage)) return;
  try {
    const r = await post("api/befehl/" + name + (index !== undefined && index !== null ? "?index=" + index : ""));
    if (!r.ok) return zeigeMeldung(r.fehler, true);
    const gesperrt = s("Fern_Erlaubt") === false || s("Wartungsmodus") === true;
    zeigeMeldung(gesperrt ? "gesendet – wird aber ignoriert (Fernbedienung gesperrt)" : "gesendet", gesperrt);
    setTimeout(aktualisieren, 400);
  } catch (e) { zeigeMeldung(e.message, true); }
}
async function einstellen(name) {
  const feld = document.getElementById("e_" + name);
  if (feld.value === "") return zeigeMeldung("Erst einen Wert eingeben.", true);
  try {
    const r = await post("api/einstellung", { name, wert: Number(feld.value.replace(",", ".")) });
    if (!r.ok) return zeigeMeldung(r.fehler, true);
    feld.value = ""; zeigeMeldung("gespeichert"); setTimeout(aktualisieren, 400);
  } catch (e) { zeigeMeldung(e.message, true); }
}
async function gps() {
  const q = new URLSearchParams({ breite: gps_breite.value.replace(",", "."), laenge: gps_laenge.value.replace(",", "."), fix: gps_fix.checked ? "1" : "0" });
  try {
    const r = await post("api/gps?" + q);
    zeigeMeldung(r.ok ? "GPS gesendet" : r.fehler, !r.ok);
  } catch (e) { zeigeMeldung(e.message, true); }
}

// ===================== Anzeige =====================
function kopf() {
  h_zeit.textContent = (s("Datum_Text") || "") + "  " + (s("Uhrzeit_Text") || "--:--");
  const sz = s("Stoerung_Zustand");
  h_stoerung.textContent = sz === 2 ? "Störung" : sz === 1 ? "Quittieren" : "keine Störung";
  h_stoerung.className = "pill " + (sz === 2 ? "err" : sz === 1 ? "warn" : "ok");
  const fe = s("Fern_Erlaubt"), fm = (v("DB_HMI.Module.Aktiv") || [])[3];
  h_fern.textContent = fm === false ? "Modul Fernzugriff aus" : fe ? "Fernbedienung erlaubt" : "Fernbedienung gesperrt";
  h_fern.className = "pill " + (fe && fm !== false ? "ok" : "warn");
  const h = [];
  if (fm === false) h.push(["warn", "Das Modul Fernzugriff ist nicht freigeschaltet. Befehle werden von der SPS ignoriert."]);
  else if (fe === false) h.push(["warn", "Am Panel ist „Fernbedienung erlaubt“ aus. Befehle werden von der SPS ignoriert."]);
  if (s("Wartungsmodus")) h.push(["warn", "Wartungsmodus aktiv: Fernbefehle und Generator sind gesperrt."]);
  if (sz === 2) h.push(["err", "Eine Störung steht an, siehe Meldungen."]);
  hinweise.innerHTML = h.map(([k, t]) => `<div class="hinweis ${k}">${t}</div>`).join("");
}

function uebersicht() {
  const lampen = v(ST + "Lampe") || [], ausw = v("DB_Parameter.Lampen_Auswahl") || [];
  k_licht.innerHTML = `<div class="lampen">${[1, 2, 3, 4, 5].map(i =>
      `<button class="lampe ${lampen[i - 1] ? "an" : ""} ${ausw[i - 1] === false ? "aus_gewaehlt" : ""}" title="Lampe ${i}" onclick="befehl('Lampe_Umschalten', ${i})">${i}</button>`).join("")}</div>` +
    tab([zeile("Licht zentral ein", ja(s("Licht_Ein"))), zeile("Alle an / alle aus", ja(s("Lampen_Alle_An")) + " / " + ja(s("Lampen_Alle_Aus")))]);
  const vs = s("Versorgung");
  b_netz.className = "b" + (vs === 1 ? " an" : ""); b_gen.className = "b" + (vs === 2 ? " an" : "");
  k_energie.innerHTML = tab([
    zeile("Versorgung", { 1: "Netz", 2: "Generator" }[vs] ?? "–"),
    zeile("Netz liegt an", dot(s("Netzwaechter")) + " " + ja(s("Netzwaechter"))),
    zeile("Generator", text(GEN, s("Gen_Zustand")) + (v("DB_Parameter.Generator_Gesperrt") ? " (gesperrt)" : "")),
    zeile("Netz- / Generatorschütz", dot(s("Netzschuetz")) + " " + dot(s("Generatorschuetz"))),
    zeile("Batterieladung", ja(s("Ladung_Aktiv"))),
    zeile("Störabschaltung", s("Abschaltung_Aktiv") ? dot(true, "rot") + " aktiv" : "nein"),
    zeile("Akkupack", text(AKKU, s("Akku_Zustand"))),
    s("Umschalten_Gesperrt") ? zeile("Hinweis", "Netz/Generator nur umschaltbar, wenn Generator und Lampen aus") : ""
  ]);
  // Netzueberwachung
  const nEin = v("DB_Parameter.Netzueberwachung_Ein"), nModul = (v("DB_HMI.Module.Aktiv") || [])[2];
  b_nub.textContent = nEin ? "ausschalten" : "einschalten";
  b_nub.className = "b" + (nEin ? " an" : "");
  const sek = ms => typeof ms === "number" ? (ms >= 60000 ? zahl(ms / 60000, ms % 60000 ? 1 : 0) + " min" : zahl(ms / 1000, 0) + " s") : "–";
  let zustand;
  if (nModul === false) zustand = dot(false) + " Modul nicht freigeschaltet";
  else if (!nEin) zustand = dot(false) + " aus";
  else if (s("Notbetrieb")) zustand = dot(true, "rot") + " Notbetrieb – Generator versorgt die Lampen";
  else if (vs !== 1) zustand = dot(true, "gelb") + " ein, aber nicht wirksam (nur im Netzbetrieb)";
  else zustand = dot(true) + " überwacht";
  k_nub.innerHTML = tab([
    zeile("Zustand", zustand),
    zeile("Netz liegt an", dot(s("Netzwaechter")) + " " + ja(s("Netzwaechter"))),
    s("NUB_Rueckkehr_Laeuft") ? zeile("Netz wieder da", `zurück in Wartestellung in ${s("NUB_Rest_Min")}:${z2(s("NUB_Rest_Sek"))}`) : "",
    zeile("Notbetrieb nach Netzausfall von", sek(v("DB_Parameter.NUB_Ausfall_Verz"))),
    zeile("Rückkehr nach Netz stabil für", sek(v("DB_Parameter.NUB_Rueckkehr_Zeit")))
  ]);
  const balken = (p, warn, err) => `<div class="balken"><div class="${err ? "err" : warn ? "warn" : ""}" style="width:${Math.max(0, Math.min(100, p || 0))}%"></div></div>`;
  const fi = v("DB_HMI.Analog.Fuellstand_Intern"), fx = v("DB_HMI.Analog.Fuellstand_Extern");
  k_mess.innerHTML = tab([
    zeile("Tank intern", zahl(fi, 0) + " %" + balken(fi, s("Tank_Niedrig"), s("Tank_Kritisch"))),
    s("Tank_Extern_Angeschlossen") ? zeile("Tank extern" + (s("Tank_Extern_Aktiv") ? " (aktiv)" : ""),
      s("Tank_Extern_Plausibel") === false ? "unplausibel" : zahl(fx, 0) + " %" + balken(fx)) : zeile("Tank extern", "nicht angeschlossen"),
    zeile("Wind", zahl(v("DB_HMI.Analog.Wind")) + " m/s"),
    zeile("Helligkeit", zahl(v("DB_HMI.Analog.Daemmerung"), 0) + " Lux")
  ]);
}

function automatik() {
  const ba = s("Betriebsart");
  b_auto_akt.textContent = ba === 2 ? "Automatik deaktivieren" : ba === 3 ? "Einrichten aktiv (nur vor Ort)" : "Automatik aktivieren";
  b_auto_akt.className = "b" + (ba === 2 ? " an" : "");
  b_qd.className = "b" + (s("Auto_Daemmerung") ? " an" : "");
  b_qu.className = "b" + (s("Auto_Uhr") ? " an" : "");
  b_qa.className = "b" + (s("Auto_Astro") ? " an" : "");
  k_auto.innerHTML = tab([
    zeile("Betriebsart", { 1: "Hand", 2: "Auto", 3: "Einrichten" }[s("Betriebsart")] ?? "–"),
    zeile("Automatik verlangt Licht", ja(s("Auto_Licht_Soll"))),
    zeile("Dämmerung: dunkel erkannt", ja(s("Dunkel")) + " (" + zahl(v("DB_HMI.Analog.Daemmerung"), 0) + " Lux)"),
    zeile("Datums-Schaltzeit übersteuert", ja(s("Datum_Uebersteuert"))),
    zeile("Uhrzeit gültig", ja(s("Uhr_Gueltig")))
  ]);
  k_astro.innerHTML = tab([
    zeile("Sonnenaufgang / -untergang", (s("Astro_Aufgang") || "--:--") + " / " + (s("Astro_Untergang") || "--:--")),
    zeile("Licht ein / aus", "<b>" + (s("Astro_Ein") || "--:--") + " / " + (s("Astro_Aus") || "--:--") + "</b>"),
    zeile("Astro sagt gerade", s("Astro_An") === undefined ? "–" : s("Astro_An") ? "an" : "aus"),
    zeile("Sonderfall", text(SONDER, s("Astro_Sonderfall"))),
    zeile("GPS", s("GPS_Aktuell") ? "aktuell" : v("DB_Astro.Position_Gueltig") ? "letzte Position" : "keine Position"),
    zeile("Position", zahl(v("DB_Astro.Breite"), 4) + " / " + zahl(v("DB_Astro.Laenge"), 4) + fehlt("DB_Astro.Breite"))
  ]);
  for (const n of ["DB_Astro.Versatz_Ein", "DB_Astro.Versatz_Aus", "DB_Parameter.Daemmerung_Ein", "DB_Parameter.Daemmerung_Hysterese"]) {
    const x = v(n); document.getElementById("e_" + n).placeholder = typeof x === "number" ? Math.round(x * 10) / 10 : "?";
  }
}

function audio() {
  k_steckdosen.innerHTML =
    `<button class="b ${s("Steckdose_1") ? "an" : ""}" onclick="befehl('Steckdose_1_Umschalten')">Steckdose 1: ${s("Steckdose_1") ? "an" : "aus"}</button>` +
    `<button class="b ${s("Steckdose_34") ? "an" : ""}" onclick="befehl('Steckdose_34_Umschalten')">Steckdose 3+4: ${s("Steckdose_34") ? "an" : "aus"}</button>`;
  if ((v("DB_HMI.Module.Aktiv") || [])[0] === false) { k_audio.innerHTML = `<p class="klein">Das Modul Audio ist nicht freigeschaltet.</p>`; return; }
  const bz = s("Stumpfelbox_Zustand"), kanal = s("Audio_Kanal"), namen = v("DB_Parameter.Audio_Name") || [];
  k_audio.innerHTML =
    `<div class="buttons"><button class="b ${bz === 2 ? "an" : bz === 1 ? "laeuft" : ""}" onclick="befehl('Stumpfelbox_Umschalten')">Stumpfelbox: ${text(BOX, bz)}</button></div>` +
    `<div class="buttons">${[0, 1, 2, 3, 4, 5, 6].map(i =>
      `<button class="b ${kanal === i ? "an" : ""}" onclick="befehl('Audio_Umschalten', ${i})">${esc(namen[i] || (i ? "Signal " + i : "Durchsage"))}</button>`).join("")}</div>` +
    `<p class="klein">${s("Audio_Bereit") ? "Audio bereit. Nochmal tippen schaltet aus." : "Erst die Stumpfelbox einschalten (10 s Hochlauf)."}</p>`;
}

// ----- Zeitschaltuhr: Editor fuer einen Tag. Wird nur neu gefuellt, solange nichts geaendert wurde.
let uhrTag = 1, uhrGeaendert = false;
const UHR_PAARE = [1, 2, 3, 4, 5, 6, 7];

function uhrTagWaehlen(d) {
  if (uhrGeaendert && d !== uhrTag && !confirm("Änderungen für " + TAGE[uhrTag - 1] + " sind noch nicht gespeichert. Verwerfen?")) return;
  uhrTag = d; uhrGeaendert = false; uhr();
}
function uhrEditorFuellen() {
  let h = `<tr><th>Paar</th><th>Einschalten</th><th>Ausschalten</th></tr>`;
  for (const p of UHR_PAARE) {
    const b = `DB_Schaltuhr.Woche[${uhrTag},${p}].`, ae = v(b + "Aktiv_Ein") === true, aa = v(b + "Aktiv_Aus") === true;
    h += `<tr><td>${p}</td>` +
      `<td><input type="checkbox" id="ue_ae${p}" ${ae ? "checked" : ""}> <input type="time" id="ue_e${p}" value="${z2(v(b + "Ein_Std"))}:${z2(v(b + "Ein_Min"))}" ${ae ? "" : "disabled"}></td>` +
      `<td><input type="checkbox" id="ue_aa${p}" ${aa ? "checked" : ""}> <input type="time" id="ue_a${p}" value="${z2(v(b + "Aus_Std"))}:${z2(v(b + "Aus_Min"))}" ${aa ? "" : "disabled"}></td></tr>`;
  }
  k_uhr_edit.innerHTML = h;
}
k_uhr_edit.addEventListener("input", e => {
  uhrGeaendert = true;
  b_uhr_tag.innerHTML = "Speichern für " + TAGE[uhrTag - 1] + ` <span class="geaendert">●</span>`;
  const m = /^ue_a([ea])(\d)$/.exec(e.target.id);   // Haken steuert, ob die Uhrzeit eingebbar ist
  if (m) document.getElementById(`ue_${m[1]}${m[2]}`).disabled = !e.target.checked;
});

async function uhrSpeichern(ziel) {
  const paare = [];
  for (const p of UHR_PAARE) {
    const aktivEin = document.getElementById("ue_ae" + p).checked, aktivAus = document.getElementById("ue_aa" + p).checked;
    const ein = document.getElementById("ue_e" + p).value || "00:00", aus = document.getElementById("ue_a" + p).value || "00:00";
    if ((aktivEin && !document.getElementById("ue_e" + p).value) || (aktivAus && !document.getElementById("ue_a" + p).value))
      return zeigeMeldung(`Paar ${p}: Uhrzeit fehlt.`, true);
    const [einStd, einMin] = ein.split(":").map(Number), [ausStd, ausMin] = aus.split(":").map(Number);
    paare.push({ aktivEin, einStd, einMin, aktivAus, ausStd, ausMin });
  }
  const kopieren = UHR_PAARE.map(d => document.getElementById("uk_" + d).checked);
  if (ziel === "auswahl" && !kopieren.some(Boolean)) return zeigeMeldung("Erst die Zieltage anhaken.", true);
  if (ziel === "alle" && !confirm("Das Programm von " + TAGE[uhrTag - 1] + " auf ALLE 7 Tage übernehmen?")) return;
  try {
    const r = await post("api/uhr/woche", { tag: uhrTag, paare, ziel, kopieren });
    if (!r.ok) return zeigeMeldung(r.fehler, true);
    zeigeMeldung(r.meldung || "gespeichert");
    uhrGeaendert = false;
    UHR_PAARE.forEach(d => document.getElementById("uk_" + d).checked = false);
    setTimeout(aktualisieren, 300);
  } catch (e) { zeigeMeldung(e.message, true); }
}

async function datumHinzu() {
  if (!ud_datum.value || !ud_zeit.value) return zeigeMeldung("Datum und Uhrzeit eingeben.", true);
  const [jahr, monat, tag] = ud_datum.value.split("-").map(Number), [std, min] = ud_zeit.value.split(":").map(Number);
  try {
    const r = await post("api/uhr/datum", { jahr, monat, tag, std, min, einschalten: ud_art.value === "1" });
    if (!r.ok) return zeigeMeldung(r.fehler, true);
    zeigeMeldung(r.meldung || "gespeichert"); ud_datum.value = ""; ud_zeit.value = "";
    setTimeout(aktualisieren, 300);
  } catch (e) { zeigeMeldung(e.message, true); }
}
async function datumLoeschen(i, text) {
  if (!confirm("Datums-Schaltzeit " + text + " löschen?")) return;
  try {
    const r = await post("api/uhr/datum_loeschen", { index: i });
    if (!r.ok) return zeigeMeldung(r.fehler, true);
    zeigeMeldung(r.meldung || "gelöscht"); setTimeout(aktualisieren, 300);
  } catch (e) { zeigeMeldung(e.message, true); }
}

function uhr() {
  k_uhr_tage.innerHTML = TAGE.map((t, i) => `<button class="b ${uhrTag === i + 1 ? "haupt" : ""}" onclick="uhrTagWaehlen(${i + 1})">${t}</button>`).join("");
  if (!k_uhr_kopieren.innerHTML) k_uhr_kopieren.innerHTML = TAGE.map((t, i) => `<label style="margin-right:8px"><input type="checkbox" id="uk_${i + 1}"> ${t}</label>`).join("");
  if (!uhrGeaendert && !k_uhr_edit.contains(document.activeElement)) {
    uhrEditorFuellen();
    b_uhr_tag.textContent = "Speichern für " + TAGE[uhrTag - 1];
  }
  let h = `<tr><th>Tag</th>${UHR_PAARE.map(p => `<th>Paar ${p}</th>`).join("")}</tr>`;
  for (let d = 1; d <= 7; d++) {
    h += `<tr class="waehlbar ${d === uhrTag ? "gewaehlt" : ""}" onclick="uhrTagWaehlen(${d})"><td>${TAGE[d - 1]}</td>`;
    for (let p = 1; p <= 7; p++) {
      const b = `DB_Schaltuhr.Woche[${d},${p}].`, t = [];
      if (v(b + "Aktiv_Ein")) t.push("Ein " + z2(v(b + "Ein_Std")) + ":" + z2(v(b + "Ein_Min")));
      if (v(b + "Aktiv_Aus")) t.push("Aus " + z2(v(b + "Aus_Std")) + ":" + z2(v(b + "Aus_Min")));
      h += `<td>${roh(b + "Aktiv_Ein")?.fehler ? "?" : t.join("<br>") || "<span class='klein'>–</span>"}</td>`;
    }
    h += "</tr>";
  }
  k_woche.innerHTML = h;
  const zeilen = [];
  for (let i = 1; i <= 20; i++) {
    const b = `DB_Schaltuhr.Datum[${i}].`;
    if (!v(b + "Belegt")) continue;
    const text = `${z2(v(b + "Tag"))}.${z2(v(b + "Monat"))}.${v(b + "Jahr")} ${z2(v(b + "Std"))}:${z2(v(b + "Min"))}`;
    zeilen.push(`<tr><td>${text}</td><td>${v(b + "Einschalten") ? "Ein" : "Aus"}</td>` +
      `<td style="text-align:right"><button class="klein" onclick="datumLoeschen(${i}, '${text}')">Löschen</button></td></tr>`);
  }
  k_datum.innerHTML = zeilen.length ? zeilen.join("") : `<tr><td class="klein">keine Einträge${fehlt("DB_Schaltuhr.Datum[1].Belegt")}</td></tr>`;
}

function meldungen() {
  const w = v("DB_HMI.Alarm") || [], aktiv = [];
  for (let n = 0; n < 32; n++) if (((w[n >> 4] || 0) >> (n & 15)) & 1) aktiv.push(n);
  k_meldungen.innerHTML = aktiv.length ? tab(aktiv.map(n => {
    const m = MELDUNGEN[n] || ["I", "Meldung " + n, ""];
    return `<tr><td style="width:70px"><span class="badge ${m[0]}">${m[0] === "S" ? "Störung" : "Info"}</span></td><td><b>${m[1]}</b><br><span class="klein">${m[2]}</span></td></tr>`;
  })) : `<p class="klein">keine Meldungen${fehlt("DB_HMI.Alarm")}</p>`;
  const zeilen = [];
  for (let i = 1; i <= 30; i++) {
    const b = `DB_Fern.Protokoll[${i}].`, code = v(b + "Code");
    if (!code) continue;
    const zt = n => v(b + "Zeit." + n);
    zeilen.push(`<tr><td style="white-space:nowrap">${z2(zt("Tag"))}.${z2(zt("Monat"))}.${zt("Jahr")} ${z2(zt("Std"))}:${z2(zt("Min"))}:${z2(zt("Sek"))}</td><td>${esc(codeText(code))}</td><td class="klein">${code}</td></tr>`);
  }
  k_protokoll.innerHTML = zeilen.length ? `<tr><th>Zeit</th><th>Ereignis</th><th>Code</th></tr>` + zeilen.join("")
    : `<tr><td class="klein">keine Einträge${fehlt("DB_Fern.Protokoll[1].Code")}</td></tr>`;
}

function service() {
  const z = n => v("DB_HMI.Zaehler." + n);
  k_zaehler.innerHTML = tab([
    zeile("Betriebsstunden", `${z("Betrieb_h") ?? "–"} h ${z2(z("Betrieb_min"))} min`),
    zeile("Nächste Wartung bei", `${z("Wartung_Bei_h") ?? "–"} h (noch ${z("Wartung_Rest_h") ?? "–"} h ${z2(z("Wartung_Rest_min"))} min)`),
    zeile("Wartung spätestens am", z("Wartung_Datum_Jahr") ? `${z2(z("Wartung_Datum_Tag"))}.${z2(z("Wartung_Datum_Monat"))}.${z("Wartung_Datum_Jahr")} (noch ${z("Wartung_Rest_Tage")} Tage)` : "–"),
    zeile("Wartung", z("Wartung_Faellig") ? dot(true, "rot") + " fällig" : z("Wartung_Vorwarnung") ? dot(true, "gelb") + " bald fällig" : "ok"),
    zeile("Kundenzähler", `${z("Kunde_h") ?? "–"} h ${z2(z("Kunde_min"))} min (${z("Kunde_Minuten_Gesamt") ?? "–"} min gesamt)`)
  ]);
  k_probelauf.innerHTML = tab([zeile("Läuft gerade", ja(s("Probelauf_Aktiv"))), zeile("Letztes Ergebnis", text(PROBE, s("Probelauf_Ergebnis")))]);
  const ak = v("DB_HMI.Module.Aktiv") || [], ab = v("DB_HMI.Module.Abgelaufen") || [], rt = v("DB_HMI.Module.Rest_Tage") || [];
  k_module.innerHTML = tab(MODULE.map((m, i) => zeile(m, ak[i] ? dot(true) + " aktiv" + (rt[i] > 0 ? ` (noch ${rt[i]} Tage)` : "")
    : ab[i] ? dot(true, "rot") + " abgelaufen" : dot(false) + " nicht gebucht")));
  k_anlage.innerHTML = tab([
    zeile("Wartungsmodus", ja(s("Wartungsmodus"))),
    zeile("Generator gesperrt", ja(v("DB_Parameter.Generator_Gesperrt"))),
    zeile("Netzüberwachung ein", ja(v("DB_Parameter.Netzueberwachung_Ein"))),
    zeile("Mast Heben / Senken gesperrt", ja(s("Mast_Heben_Gesperrt")) + " / " + ja(s("Mast_Senken_Gesperrt"))),
    zeile("Verbindung erkannt (SPS)", ja(s("Fern_Verbunden"))),
    zeile("Lebenszeichen SPS", s("Lebenszeichen") ?? "–")
  ]);
}

function diagnose() {
  k_io.innerHTML = EXTRA.diagnose.map(n => {
    const kurz = n.replace("DB_HMI.IO.", ""), x = v(n);
    return `<div>${typeof x === "number" ? `<b>${x}</b>` : dot(x)} ${kurz}</div>`;
  }).join("");
}

const ANZEIGE = { uebersicht, automatik, audio, uhr, meldungen, service, diagnose };

async function aktualisieren() {
  if (laeuft) return; laeuft = true;
  try {
    const r = await post("api/lesen", { namen: [...BASIS, ...(EXTRA[seite] || [])] });
    if (!r.ok) { h_verbindung.textContent = "keine Verbindung"; h_verbindung.className = "pill err"; h_verbindung.title = r.fehler; zeigeMeldung(r.fehler, true); return; }
    Object.assign(W, r.werte);
    h_verbindung.textContent = "Stand " + new Date().toLocaleTimeString("de-DE"); h_verbindung.className = "pill ok"; h_verbindung.title = "letzte erfolgreiche Abfrage";
    kopf(); ANZEIGE[seite]();
  } catch (e) {
    h_verbindung.textContent = "Programm nicht erreichbar"; h_verbindung.className = "pill err"; h_verbindung.title = e.message;
  } finally { laeuft = false; }
}

tabs.addEventListener("click", e => {
  const b = e.target.closest("button"); if (!b) return;
  seite = b.dataset.seite;
  document.querySelectorAll("nav button").forEach(x => x.classList.toggle("aktiv", x === b));
  document.querySelectorAll(".seite").forEach(x => x.classList.toggle("aktiv", x.id === "s_" + seite));
  ANZEIGE[seite](); aktualisieren();
});
// Browser bremsen Zeitgeber in verdeckten oder minimierten Fenstern -> beim Zurueckkommen sofort aktualisieren
document.addEventListener("visibilitychange", () => { if (!document.hidden) aktualisieren(); });
aktualisieren();
setInterval(aktualisieren, 2000);
</script>
</body>
</html>
``

## Anhang E – `public/texte.js`

``js
// Texte fuer Meldungen und Ereignisprotokoll (Stand wie Meldeliste.xlsx)

// Meldungen: Bit n in DB_HMI.Alarm (Wort 0 = Bit 0..15, Wort 1 = Bit 16..31). S = Stoerung (quittieren), I = Info
const MELDUNGEN = {
  0: ["S", "Not-Aus betätigt", "Not-Aus entriegeln, dann quittieren."],
  1: ["S", "Isowächter 1 ausgelöst", "Isolationsfehler im Generatornetz. Generator fährt herunter."],
  2: ["S", "Isowächter 2 ausgelöst", "Isolationsfehler im Generatornetz. Generator fährt herunter."],
  3: ["S", "Störung allgemein", ""],
  4: ["S", "Störung Generator-Motor", "Generator fährt herunter. Motorsteuergerät prüfen."],
  5: ["S", "Sicherheitswanne ausgelöst", "Leckage? Generator fährt herunter."],
  6: ["S", "Störung Akkupack", "Akkupack wird abgeschaltet, Brücke geschlossen."],
  7: ["I", "Batterie-Unterspannung", "Im Generatorbetrieb wird die Batterie automatisch geladen."],
  8: ["I", "Windalarm - Mast fährt auf sichere Höhe", "Heben gesperrt, bis der Wind nachlässt."],
  9: ["S", "Drahtbruch Füllstand interner Tank", ""],
  10: ["S", "Drahtbruch Füllstand externer Tank", ""],
  11: ["S", "Drahtbruch Temperatur Gehäuse", ""],
  12: ["S", "Drahtbruch Temperatur Netzteil", ""],
  13: ["S", "Zeitüberschreitung Mast automatisch senken", "Sensor sichere Höhe prüfen."],
  14: ["S", "Generator startet nicht", "Keine Rückmeldung Betriebsbereit innerhalb der Startzeit."],
  15: ["S", "Generator ausgefallen", "Rückmeldung Betriebsbereit im Betrieb weggefallen."],
  16: ["I", "Überbrückung aktiv", "Eine Schutzfunktion ist im Admin-Menü überbrückt."],
  17: ["I", "Generator gesperrt", "Motorstart ist gesperrt (z. B. Halle)."],
  18: ["I", "Uhrzeit ungültig - bitte Systemzeit stellen", "Zeitschaltuhr arbeitet erst mit gültiger Uhrzeit."],
  19: ["I", "Netzausfall - Notbetrieb aktiv", ""],
  20: ["S", "Externer Tank: Füllstand unplausibel", "Es wird aus dem internen Tank gefahren."],
  21: ["I", "Externer Tank leer - Umschaltung auf internen Tank", ""],
  22: ["I", "Wartung fällig", "Nach der Wartung zurücksetzen."],
  23: ["I", "Tankfüllstand niedrig", "Bitte nachtanken."],
  24: ["I", "Tankfüllstand kritisch", "Bitte umgehend nachtanken."],
  25: ["I", "Wartung bald fällig", ""],
  26: ["I", "Wartungsmodus aktiv - Generator gesperrt", "Generator kann nicht starten."],
  27: ["I", "Zusatzmodul abgelaufen", "Die Laufzeit eines gebuchten Moduls ist überschritten."],
  28: ["I", "Akkupack angeschlossen, aber nicht freigeschaltet", "Modul Akkupack ist nicht gebucht."]
};

const EREIGNISSE = {
  1: "SPS-Anlauf", 2: "Netzausfall", 3: "Netz wieder da", 4: "Notbetrieb gestartet", 5: "Notbetrieb beendet",
  6: "Generator läuft (betriebsbereit)", 7: "Generator aus", 8: "Licht ein", 9: "Licht aus", 10: "Probelauf gestartet",
  11: "Probelauf erfolgreich", 12: "Probelauf fehlgeschlagen", 13: "Batterieladung gestartet", 14: "Batterieladung beendet",
  15: "Wartungsmodus ein", 16: "Wartungsmodus aus", 17: "Fernbedienung freigegeben", 18: "Fernbedienung gesperrt",
  24: "Betriebsart Hand", 25: "Betriebsart Auto", 26: "Betriebsart Einrichten",
  27: "Versorgung Netz", 28: "Versorgung Generator", 29: "Generator gesperrt", 30: "Generator freigegeben",
  31: "Umschaltung auf externen Tank", 32: "Umschaltung auf internen Tank", 33: "Akkupack zugeschaltet", 34: "Akkupack abgeschaltet",
  35: "Netzüberwachung ein", 36: "Netzüberwachung aus", 37: "Modul Audio freigeschaltet", 38: "Modul Akkupack freigeschaltet",
  39: "Modul Netzüberwachung freigeschaltet", 40: "Modul Fernzugriff freigeschaltet", 41: "Modul Audio gesperrt / abgelaufen",
  42: "Modul Akkupack gesperrt / abgelaufen", 43: "Modul Netzüberwachung gesperrt / abgelaufen", 44: "Modul Fernzugriff gesperrt / abgelaufen",
  45: "Stumpfelbox an", 46: "Stumpfelbox aus", 47: "Tankumschaltung gesperrt", 48: "Tankumschaltung freigegeben"
};

const BEFEHLSTEXTE = ["Quittieren", "Betriebsart Hand", "Betriebsart Auto", "Betriebsart Einrichten", "Teach Tank intern leer",
  "Teach Tank intern voll", "Teach Tank extern leer", "Teach Tank extern voll", "Versorgung Netz gewählt", "Versorgung Generator gewählt",
  "Generator Start", "Generator Stop", "Schnellstart", "Schnellstop", "Lampen ein", "Lampen aus", "Lampe 1 umgeschaltet",
  "Lampe 2 umgeschaltet", "Lampe 3 umgeschaltet", "Lampe 4 umgeschaltet", "Lampe 5 umgeschaltet", "Wochenprogramm gespeichert",
  "Wochenprogramm auf alle Tage", "Wochenprogramm auf Auswahl", "Datums-Schaltzeit hinzugefügt", "Datums-Schaltzeit gelöscht",
  "Steckdose 1 umgeschaltet", "Steckdose 3+4 umgeschaltet", "Stumpfelbox ein/aus", "Durchsage ein/aus", "Audio-Signal 1",
  "Audio-Signal 2", "Audio-Signal 3", "Audio-Signal 4", "Audio-Signal 5", "Audio-Signal 6", "Wartung quittiert",
  "Kundenzähler zurückgesetzt", "", "Systemzeit gestellt", "Probelauf gestartet (Taste)", "Automatik Dämmerung an/ab",
  "Automatik Uhr an/ab", "Automatik ein/aus", "Automatik Astro an/ab", "Netzüberwachung ein/aus"];

function codeText(code) {
  if (!code) return "";
  if (code < 100) return EREIGNISSE[code] || "Ereignis " + code;
  if (code < 200) { const m = MELDUNGEN[code - 100]; return "Meldung: " + (m ? m[1] : code - 100); }
  if (code < 300) return "Vor Ort: " + (BEFEHLSTEXTE[code - 200] || "Befehl " + (code - 200));
  if (code < 400) return "Fern: " + (BEFEHLSTEXTE[code - 300] || "Befehl " + (code - 300));
  return "Code " + code;
}
``
