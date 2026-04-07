# Eventenergie Portal - Desktop App v2.0

Native Desktop-Anwendung fuer **macOS** und **Windows** mit Multi-Window-Architektur.

## Features

- **Server-Erkennung**: Prueft automatisch lokalen Server (172.20.200.117), Fallback auf eventenergie.app
- **Login-Fenster**: Separates Anmeldefenster beim Start
- **Hub-Fenster**: Schlankes Fenster mit allen Modul-Kacheln nach Anmeldung
- **Multi-Window**: Jede Kachel oeffnet ein eigenes OS-Fenster
- **Automatische Abmeldung**: Alle Fenster werden bei Logout geschlossen

## Voraussetzungen

- Node.js 18+ installiert
- Yarn

## Installation

```bash
cd desktop
yarn install
```

## Konfiguration

Die Server-URLs werden in `config.json` eingestellt:

```json
{
  "remoteUrl": "https://eventenergie.app",
  "localServers": [
    { "url": "https://172.20.200.117", "label": "Nginx (HTTPS)" },
    { "url": "http://172.20.200.117:8001", "label": "Caddy" }
  ],
  "title": "Eventenergie Portal"
}
```

Die App prueft die lokalen Server in Reihenfolge und faellt auf `remoteUrl` zurueck.

## Entwicklung / Testen

```bash
yarn start
```

## Installer bauen

### macOS (.dmg)

```bash
yarn build:mac
```

Erstellt ein macOS Disk-Image unter `dist/`.

**Hinweis:** macOS-Builds muessen auf einem Mac erstellt werden.

### Windows (.exe Installer)

```bash
yarn build:win
```

### Beide Plattformen

```bash
yarn build:all
```

## Architektur

```
Start -> Server-Erkennung (Lokal/Remote)
      -> Login-Fenster (${baseUrl}/login)
      -> [Login erkannt] -> Hub-Fenster (${baseUrl}/hub?desktop=1)
      -> [Kachel-Klick] -> Modul-Fenster (${baseUrl}/{modul-pfad})
```

- Hub-Fenster zeigt nur Modul-Kacheln (Desktop-Modus via ?desktop=1)
- Jedes Modul-Fenster ist ein eigenstaendiges OS-Fenster
- Bereits offene Module werden fokussiert statt neu erstellt

## App-Icon

- `assets/icon.ico` - Windows (256x256 px, ICO-Format)
- `assets/icon.icns` - macOS (ICNS-Format)
- `assets/icon.png` - Fallback (512x512 px)

## Tastenkuerzel

| Kuerzel | Aktion |
|---------|--------|
| Ctrl+R / Cmd+R | Seite neu laden |
| F12 | Entwicklertools |
| Ctrl+Q / Cmd+Q | Beenden |
