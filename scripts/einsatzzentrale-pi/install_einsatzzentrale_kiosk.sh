#!/usr/bin/env bash
# ============================================================================
# Eventenergie - Einsatzzentrale Pi Kiosk Installer
# ============================================================================
# Installiert Chromium-Kiosk fuer die Einsatzzentrale auf Raspberry Pi OS.
#
# Was passiert:
#   - Chromium wird (falls noetig) installiert
#   - Autostart-Snippet wird angelegt (Wayland labwc/wayfire ODER X11/LXDE)
#   - Screen-Blanking + Power-Management werden deaktiviert
#   - Chromium startet bei Boot im Kiosk-Modus auf der konfigurierten URL
#   - Translate-Popup, Erste-Schritte-Wizard, Password-Manager, Crash-Bubbles
#     werden unterdrueckt
#
# Voraussetzungen:
#   - Raspberry Pi OS (Bookworm oder neuer; Bullseye funktioniert auch)
#   - Desktop-Variante mit Autologin aktiviert (raspi-config -> System -> Boot
#     -> Desktop Autologin)
#   - Internet-Verbindung
#
# Benutzung:
#   sudo bash install_einsatzzentrale_kiosk.sh https://dein-portal.de/einsatzzentrale
#
# Deinstallation:
#   sudo bash install_einsatzzentrale_kiosk.sh --uninstall
# ============================================================================

set -euo pipefail

# ---------- Konfiguration ----------------------------------------------------
DEFAULT_URL="https://dein-portal.example/einsatzzentrale"
KIOSK_USER="${SUDO_USER:-pi}"
KIOSK_HOME="$(getent passwd "$KIOSK_USER" | cut -d: -f6)"
KIOSK_PROFILE_DIR="$KIOSK_HOME/.config/einsatzzentrale-chromium"
KIOSK_LAUNCH_SCRIPT="$KIOSK_HOME/.local/bin/einsatzzentrale-kiosk.sh"
KIOSK_URL_FILE="$KIOSK_HOME/.config/einsatzzentrale-url"

# Farben
C_GREEN="\033[1;32m"; C_YELLOW="\033[1;33m"; C_RED="\033[1;31m"; C_NC="\033[0m"
log()  { echo -e "${C_GREEN}[+]${C_NC} $*"; }
warn() { echo -e "${C_YELLOW}[!]${C_NC} $*"; }
err()  { echo -e "${C_RED}[x]${C_NC} $*" >&2; }

# ---------- Root-Check -------------------------------------------------------
if [[ $EUID -ne 0 ]]; then
  err "Bitte mit sudo ausfuehren."
  exit 1
fi
if [[ -z "$KIOSK_HOME" || ! -d "$KIOSK_HOME" ]]; then
  err "Home-Verzeichnis fuer User '$KIOSK_USER' nicht gefunden."
  exit 1
fi

# ---------- Uninstall --------------------------------------------------------
if [[ "${1:-}" == "--uninstall" ]]; then
  log "Deinstalliere Einsatzzentrale Kiosk..."
  rm -f  "$KIOSK_LAUNCH_SCRIPT"
  rm -f  "$KIOSK_URL_FILE"
  rm -rf "$KIOSK_PROFILE_DIR"
  rm -f  "$KIOSK_HOME/.config/autostart/einsatzzentrale-kiosk.desktop"
  # Wayland labwc autostart Eintrag entfernen
  for f in "$KIOSK_HOME/.config/wayfire.ini" "$KIOSK_HOME/.config/labwc/autostart"; do
    [[ -f "$f" ]] && sed -i '/einsatzzentrale-kiosk\.sh/d' "$f" || true
  done
  # X11 LXDE Autostart
  for f in "$KIOSK_HOME/.config/lxsession/LXDE-pi/autostart" \
           "/etc/xdg/lxsession/LXDE-pi/autostart"; do
    [[ -f "$f" ]] && sed -i '/einsatzzentrale-kiosk\.sh/d' "$f" || true
  done
  log "Fertig. Bitte neu starten."
  exit 0
fi

# ---------- URL-Parameter ----------------------------------------------------
URL="${1:-}"
if [[ -z "$URL" ]]; then
  warn "Keine URL angegeben. Verwende Default: $DEFAULT_URL"
  URL="$DEFAULT_URL"
fi
if [[ ! "$URL" =~ ^https?:// ]]; then
  err "URL muss mit http:// oder https:// beginnen."
  exit 1
fi
log "Kiosk-URL:   $URL"
log "Kiosk-User:  $KIOSK_USER ($KIOSK_HOME)"

# ---------- Chromium installieren -------------------------------------------
if command -v chromium-browser >/dev/null 2>&1; then
  CHROMIUM_BIN="$(command -v chromium-browser)"
elif command -v chromium >/dev/null 2>&1; then
  CHROMIUM_BIN="$(command -v chromium)"
else
  log "Chromium nicht gefunden - installiere..."
  apt-get update
  apt-get install -y --no-install-recommends chromium-browser || apt-get install -y --no-install-recommends chromium
  CHROMIUM_BIN="$(command -v chromium-browser || command -v chromium)"
fi
log "Chromium:    $CHROMIUM_BIN"

# Hilfstools (xset, unclutter optional, jq)
apt-get install -y --no-install-recommends unclutter xdotool x11-xserver-utils 2>/dev/null || true

# ---------- Kiosk-Skript anlegen --------------------------------------------
log "Schreibe Launch-Skript $KIOSK_LAUNCH_SCRIPT ..."
install -d -o "$KIOSK_USER" -g "$KIOSK_USER" "$(dirname "$KIOSK_LAUNCH_SCRIPT")"
install -d -o "$KIOSK_USER" -g "$KIOSK_USER" "$KIOSK_PROFILE_DIR"
echo -n "$URL" > "$KIOSK_URL_FILE"
chown "$KIOSK_USER":"$KIOSK_USER" "$KIOSK_URL_FILE"

cat > "$KIOSK_LAUNCH_SCRIPT" <<'LAUNCHER_EOF'
#!/usr/bin/env bash
# Einsatzzentrale Kiosk - wird bei Login/Boot automatisch gestartet.
set -u

URL="$(cat "$HOME/.config/einsatzzentrale-url" 2>/dev/null || echo "")"
if [[ -z "$URL" ]]; then
  echo "Keine URL hinterlegt." >&2
  exit 1
fi

PROFILE="$HOME/.config/einsatzzentrale-chromium"
mkdir -p "$PROFILE"

# Translate-Popup, Erste-Schritte, Default-Browser-Frage etc. unterdruecken
mkdir -p "$PROFILE/Default"
cat > "$PROFILE/Default/Preferences" <<JSON_EOF
{
  "browser": { "check_default_browser": false, "show_home_button": false },
  "credentials_enable_service": false,
  "profile": {
    "password_manager_enabled": false,
    "exit_type": "Normal",
    "exited_cleanly": true
  },
  "translate": { "enabled": false },
  "translate_blocked_languages": ["de", "en", "fr", "it", "es", "pl", "tr"]
}
JSON_EOF

# Screen-Blanking deaktivieren (nur unter X11)
if command -v xset >/dev/null 2>&1; then
  xset s off 2>/dev/null || true
  xset -dpms 2>/dev/null || true
  xset s noblank 2>/dev/null || true
fi
# Maus ausblenden bei Inaktivitaet
if command -v unclutter >/dev/null 2>&1; then
  unclutter -idle 1 -root &
fi

# Chromium bestimmen
CHROMIUM="$(command -v chromium-browser || command -v chromium)"
if [[ -z "$CHROMIUM" ]]; then
  echo "Chromium nicht installiert." >&2
  exit 1
fi

# Endlosschleife: Browser nach Crash neu starten
while true; do
  "$CHROMIUM" \
    --kiosk \
    --noerrdialogs \
    --disable-infobars \
    --disable-translate \
    --disable-features=TranslateUI,Translate,AutofillEnableAccountWalletStorage \
    --no-first-run \
    --disable-session-crashed-bubble \
    --disable-component-update \
    --disable-pinch \
    --overscroll-history-navigation=0 \
    --autoplay-policy=no-user-gesture-required \
    --user-data-dir="$PROFILE" \
    --start-fullscreen \
    --check-for-update-interval=31536000 \
    --password-store=basic \
    --enable-features=OverlayScrollbar \
    --lang=de-DE \
    "$URL"
  echo "Chromium beendet (Exit $?). Restart in 3s..."
  sleep 3
done
LAUNCHER_EOF
chmod +x "$KIOSK_LAUNCH_SCRIPT"
chown "$KIOSK_USER":"$KIOSK_USER" "$KIOSK_LAUNCH_SCRIPT"

# ---------- Autostart-Eintrag ------------------------------------------------
# Pi OS Bookworm nutzt standardmaessig Wayland (labwc oder wayfire).
# Pi OS Bullseye / aelter nutzt X11 + LXDE. Wir decken beide ab.

# 1) XDG-Autostart (funktioniert sowohl X11 als auch Wayland sessions)
install -d -o "$KIOSK_USER" -g "$KIOSK_USER" "$KIOSK_HOME/.config/autostart"
cat > "$KIOSK_HOME/.config/autostart/einsatzzentrale-kiosk.desktop" <<DESKTOP_EOF
[Desktop Entry]
Type=Application
Name=Einsatzzentrale Kiosk
Comment=Chromium Kiosk fuer Einsatzzentrale
Exec=$KIOSK_LAUNCH_SCRIPT
Terminal=false
X-GNOME-Autostart-enabled=true
X-LXQt-Need-Tray=false
NoDisplay=false
DESKTOP_EOF
chown "$KIOSK_USER":"$KIOSK_USER" "$KIOSK_HOME/.config/autostart/einsatzzentrale-kiosk.desktop"

# 2) Wayland labwc Autostart (Pi OS Bookworm Default)
if [[ -d "$KIOSK_HOME/.config/labwc" ]] || command -v labwc >/dev/null 2>&1; then
  install -d -o "$KIOSK_USER" -g "$KIOSK_USER" "$KIOSK_HOME/.config/labwc"
  AS="$KIOSK_HOME/.config/labwc/autostart"
  touch "$AS"
  chown "$KIOSK_USER":"$KIOSK_USER" "$AS"
  if ! grep -q "einsatzzentrale-kiosk.sh" "$AS" 2>/dev/null; then
    echo "$KIOSK_LAUNCH_SCRIPT &" >> "$AS"
  fi
fi

# 3) X11 LXDE Autostart (Pi OS Bullseye / aelter)
if [[ -d "$KIOSK_HOME/.config/lxsession/LXDE-pi" ]] || [[ -d "/etc/xdg/lxsession/LXDE-pi" ]]; then
  install -d -o "$KIOSK_USER" -g "$KIOSK_USER" "$KIOSK_HOME/.config/lxsession/LXDE-pi"
  AS="$KIOSK_HOME/.config/lxsession/LXDE-pi/autostart"
  if [[ ! -f "$AS" && -f "/etc/xdg/lxsession/LXDE-pi/autostart" ]]; then
    cp "/etc/xdg/lxsession/LXDE-pi/autostart" "$AS"
    chown "$KIOSK_USER":"$KIOSK_USER" "$AS"
  fi
  touch "$AS"
  chown "$KIOSK_USER":"$KIOSK_USER" "$AS"
  if ! grep -q "einsatzzentrale-kiosk.sh" "$AS" 2>/dev/null; then
    echo "@$KIOSK_LAUNCH_SCRIPT" >> "$AS"
  fi
fi

# ---------- Energiesparen global aus ----------------------------------------
# raspi-config ueber CLI: Screen-Blanking aus
if command -v raspi-config >/dev/null 2>&1; then
  raspi-config nonint do_blanking 1 || true
fi

# ---------- Fertig -----------------------------------------------------------
log ""
log "================================================================"
log "  Installation abgeschlossen."
log "================================================================"
log "  URL:         $URL"
log "  User:        $KIOSK_USER"
log "  Launcher:    $KIOSK_LAUNCH_SCRIPT"
log "  URL-Datei:   $KIOSK_URL_FILE   (zum spaeteren Aendern)"
log ""
log "  Naechste Schritte:"
log "    1. Pruefe: raspi-config -> System -> Boot -> Desktop Autologin"
log "    2. Neustart:    sudo reboot"
log "    3. URL aendern: echo 'NEUE_URL' > $KIOSK_URL_FILE && sudo reboot"
log "    4. Deinstall:   sudo bash $0 --uninstall"
log ""
log "  Hinweis: Bei Bookworm+ kann Wayland (labwc) oder X11 aktiv sein."
log "  Wir haben beide Autostarts hinterlegt - es passt von selbst."
log "================================================================"
