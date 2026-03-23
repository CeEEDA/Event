# Eventenergie Portal - Desktop App

Native Desktop-Anwendung fuer **Windows** und **macOS**.

## Voraussetzungen

- Node.js 18+ installiert
- Yarn oder npm

## Installation

```bash
cd desktop
yarn install
```

## Konfiguration

Die Server-URL wird in `config.json` eingestellt:

```json
{
  "portalUrl": "https://eventenergie.app",
  "title": "Eventenergie Portal"
}
```

Passen Sie `portalUrl` an Ihre Server-Adresse an.

## Entwicklung / Testen

```bash
yarn start
```

Oeffnet die App im Entwicklungsmodus.

## Installer bauen

### Windows (.exe Installer)

```bash
yarn build:win
```

Erstellt einen Windows-Installer unter `dist/Eventenergie Portal Setup 1.0.0.exe`.

### macOS (.dmg)

```bash
yarn build:mac
```

Erstellt ein macOS Disk-Image unter `dist/Eventenergie Portal-1.0.0.dmg`.

**Hinweis:** macOS-Builds muessen auf einem Mac erstellt werden.

### Beide Plattformen

```bash
yarn build:all
```

## Verteilung

1. Installer bauen (siehe oben)
2. Die Datei aus `dist/` an Mitarbeiter verteilen
3. Mitarbeiter installieren die App und starten sie
4. Die App verbindet sich automatisch mit dem Portal

## App-Icon

Legen Sie Ihr eigenes Icon ab:

- `assets/icon.ico` - Windows (256x256 px, ICO-Format)
- `assets/icon.icns` - macOS (ICNS-Format)
- `assets/icon.png` - Fallback (512x512 px)

## Tastenkuerzel

| Kuerzel | Aktion |
|---------|--------|
| Ctrl+R / Cmd+R | Seite neu laden |
| Alt+Links | Zurueck |
| Alt+Rechts | Vorwaerts |
| F11 | Vollbild |
| F12 | Entwicklertools |
| Ctrl+Q / Cmd+Q | Beenden |
