# Eventenergie Portal - Desktop App v2.0

Native Desktop-Anwendung fuer **macOS** und **Windows** mit Multi-Window-Architektur.

## Features

- **Server-Erkennung**: Prueft automatisch lokalen Server (172.20.200.117), Fallback auf eventenergie.app
- **Login-Fenster**: Separates Anmeldefenster beim Start
- **Hub-Fenster**: Vollstaendige Hub-Ansicht (Zeiterfassung, Kacheln, Aufgaben)
- **Multi-Window**: Jede Kachel oeffnet ein eigenes OS-Fenster
- **Automatische Abmeldung**: Alle Fenster werden bei Logout geschlossen

## Installation

### Mac - Ein Befehl:

```bash
bash install-mac.sh
```

Oder Terminal oeffnen und eintippen:
```bash
cd /pfad/zum/desktop-ordner
bash install-mac.sh
```

→ Installiert Node.js (falls noetig), baut die App, kopiert sie nach /Applications
→ Legt die DMG auf den Desktop zum Weitergeben

### Windows - Doppelklick:

Die Datei `install-win.bat` doppelklicken.

Oder PowerShell oeffnen und eintippen:
```powershell
powershell -ExecutionPolicy Bypass -File install-win.ps1
```

→ Installiert Node.js (falls noetig), baut den Installer, legt ihn auf den Desktop

## Verteilung an Mitarbeiter

### Einfachste Methode:

1. **Sie** bauen die App einmal (Mac: `bash install-mac.sh` / Win: `install-win.bat`)
2. Die fertige Datei weitergeben:
   - **Mac**: DMG-Datei vom Desktop per E-Mail/Chat schicken
   - **Windows**: EXE-Installer vom Desktop per E-Mail/Chat schicken
3. **Mitarbeiter** oeffnen nur die DMG/EXE - kein Terminal noetig

## Konfiguration

Server-URLs in `config.json`:

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

## Architektur

```
Start → Server-Erkennung (Lokal/Remote)
      → Login-Fenster
      → [Login] → Hub-Fenster (Zeiterfassung + Kacheln + Aufgaben)
      → [Kachel-Klick] → Neues Modul-Fenster
```

## Dateien

| Datei | Beschreibung |
|-------|-------------|
| `install-mac.sh` | Mac-Installer (alles in einer Datei) |
| `install-win.bat` | Windows-Installer (Doppelklick) |
| `install-win.ps1` | Windows-Installer (PowerShell) |
| `main.js` | Electron Hauptprozess |
| `preload.js` | IPC-Bridge (Frontend ↔ Electron) |
| `config.json` | Server-Konfiguration |
| `assets/icon.png` | App-Icon (Mac, 512x512) |
| `assets/icon.ico` | App-Icon (Windows, Multi-Size) |

## Tastenkuerzel

| Kuerzel | Aktion |
|---------|--------|
| Ctrl+R / Cmd+R | Seite neu laden |
| F12 | Entwicklertools |
| Ctrl+Q / Cmd+Q | Beenden |
