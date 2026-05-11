# Einsatzzentrale Pi - Kiosk-Installation

Komplettes Setup für einen Raspberry Pi, der die **Einsatzzentrale**-Oberfläche
im Vollbild-Kiosk-Modus zeigt. Browser startet automatisch nach Boot, kommt
nach Absturz wieder hoch, Bildschirm bleibt an, kein Translate-Popup, keine
Erste-Schritte-Wizards.

## Vorbereitung des Pi

1. **Raspberry Pi OS (Desktop-Variante)** flashen — Bookworm oder Bullseye.
2. Bei Erstinbetriebnahme die normale Einrichtung durchlaufen (User, WLAN, …).
3. **Autologin aktivieren** (sonst startet der Kiosk nicht ohne dass jemand
   sich einloggt):

   ```bash
   sudo raspi-config
   #  -> 1 System Options
   #  -> S5 Boot / Auto Login
   #  -> B4 Desktop Autologin
   ```

4. WLAN/LAN testen — Pi muss `https://dein-portal.de/einsatzzentrale` erreichen.

## Installation

Skript hochladen (z.B. via `scp` oder USB-Stick) und ausführen:

```bash
chmod +x install_einsatzzentrale_kiosk.sh
sudo bash install_einsatzzentrale_kiosk.sh https://dein-portal.de/einsatzzentrale
sudo reboot
```

Nach dem Reboot sollte Chromium automatisch im Vollbild starten und direkt
die Einsatzzentrale-Seite anzeigen.

### One-Liner (wenn Skript online liegt)

```bash
curl -sSL https://dein-portal.de/scripts/install_einsatzzentrale_kiosk.sh \
  | sudo bash -s -- https://dein-portal.de/einsatzzentrale
```

## URL nachträglich ändern

```bash
echo "https://test.dein-portal.de/einsatzzentrale" > ~/.config/einsatzzentrale-url
sudo reboot
```

## Was das Skript macht

- ✅ Installiert Chromium (falls noch nicht vorhanden) + `unclutter` (versteckt
  die Maus bei Inaktivität) + `xset` (deaktiviert Bildschirmschoner).
- ✅ Legt ein eigenes Chrome-Profil unter `~/.config/einsatzzentrale-chromium`
  an mit deaktiviertem Translate-Popup, Password-Manager, Default-Browser-Frage
  und Erste-Schritte-Wizard.
- ✅ Schreibt `~/.local/bin/einsatzzentrale-kiosk.sh` als Launcher (mit
  Watchdog-Schleife — wenn Chromium abstürzt, neu starten).
- ✅ Hinterlegt **drei** Autostart-Methoden gleichzeitig, damit es egal ist
  ob das Pi-OS mit X11/LXDE, Wayland/labwc oder Wayfire läuft:
   1. `~/.config/autostart/einsatzzentrale-kiosk.desktop` (XDG-Standard)
   2. `~/.config/labwc/autostart` (Bookworm Default)
   3. `~/.config/lxsession/LXDE-pi/autostart` (Bullseye / ältere)
- ✅ Deaktiviert Screen-Blanking via `raspi-config nonint do_blanking 1`.

## Chromium-Flags im Detail

| Flag | Wirkung |
|------|---------|
| `--kiosk` | Vollbild, keine Adressleiste, keine Tabs |
| `--noerrdialogs` | Keine Fehlerdialoge bei Crash |
| `--disable-infobars` | Keine "Chrome wird von …" Banner |
| `--disable-translate --disable-features=TranslateUI,Translate` | **Translate-Popup aus** |
| `--no-first-run` | Kein Setup-Wizard |
| `--disable-session-crashed-bubble` | Keine "Wiederherstellen?" Frage |
| `--check-for-update-interval=31536000` | Keine Update-Prompts |
| `--password-store=basic` | Kein Keyring-Popup |
| `--lang=de-DE` | UI auf Deutsch |
| `--start-fullscreen` | Wirklich Vollbild |
| `--autoplay-policy=no-user-gesture-required` | Audio/Video läuft sofort |

## Deinstallation

```bash
sudo bash install_einsatzzentrale_kiosk.sh --uninstall
sudo reboot
```

## Troubleshooting

**Chromium startet nicht automatisch nach Boot**
- Autologin geprüft? (`sudo raspi-config` → Boot/Auto Login → Desktop Autologin)
- `journalctl --user -u graphical-session.target` zeigt Fehler?
- Manueller Test: `bash ~/.local/bin/einsatzzentrale-kiosk.sh`

**Translate-Popup erscheint trotzdem**
- Profil leeren: `rm -rf ~/.config/einsatzzentrale-chromium && sudo reboot`

**Bildschirm geht aus**
- `sudo raspi-config` → Display Options → Screen Blanking → Disable
- Falls X11: zusätzlich `xset s off -dpms` im Launcher (ist drin).

**Pi soll andere URL zeigen**
```bash
echo "https://andere.url" > ~/.config/einsatzzentrale-url
sudo reboot
```

**Tastenkürzel um Kiosk zu beenden** (für Wartung)
`Strg+Alt+F2` → Login → `pkill -f chromium` → Browser stoppt.
Mit `Strg+Alt+F7` (oder `F1`) zurück zur Grafik.

## Sicherheits-Tipp

Wenn der Pi öffentlich steht: **Login auf dem Pi-User** (nicht im Browser!)
mit Passwort schützen oder den OS-Default-User `pi` durch einen
Service-Account ersetzen. Der Browser-Login der Einsatzzentrale ist davon
unabhängig.
