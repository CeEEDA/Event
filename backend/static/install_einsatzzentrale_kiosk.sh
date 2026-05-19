#!/usr/bin/env bash
# ============================================================================
# Eventenergie - Einsatzzentrale Kiosk Installer (Ubuntu Desktop)
# ============================================================================
# Zielsystem:
#   - Ubuntu Desktop 22.04 / 24.04 (GNOME + GDM3)
#   - Kein Raspberry Pi! (Pi 4/5 hat zu wenig GPU-Power fuer Kiosk-Renderer)
#
# Was passiert (idempotent - kann beliebig oft wiederholt werden):
#   1. Google Chrome stable (DEB) installieren (Snap-Chromium hat Sandboxing-
#      Probleme im Kiosk-Modus -> wir nehmen Chrome direkt)
#   2. GDM3 Autologin fuer aktuellen User aktivieren
#   3. Wayland deaktivieren (Chrome-Kiosk laeuft nur stabil unter Xorg)
#   4. Kiosk-Launcher-Skript mit Watchdog-Restart anlegen
#   5. XDG-Autostart-Eintrag damit Chrome nach Login automatisch startet
#   6. Screen-Blanking + DPMS + Notification-Popups + Screensaver aus
#   7. Translate-Popup, Default-Browser-Frage, Password-Manager unterdruecken
#
# Benutzung:
#   sudo bash install_einsatzzentrale_kiosk.sh https://dein-portal.de/einsatzzentrale?pi_id=...&key=...
#
# Deinstallation:
#   sudo bash install_einsatzzentrale_kiosk.sh --uninstall
#
# URL spaeter aendern:
#   echo "NEUE_URL" > ~/.config/einsatzzentrale-url && sudo reboot
#
# Schriftgroesse anpassen (1.0=normal, 1.5=+50%, 2.0=doppelt):
#   echo "1.5" > ~/.config/einsatzzentrale-scale && sudo reboot
# ============================================================================

set -euo pipefail

KIOSK_USER="${SUDO_USER:-$USER}"
KIOSK_HOME="$(getent passwd "$KIOSK_USER" | cut -d: -f6 || true)"
[[ -z "$KIOSK_HOME" ]] && KIOSK_HOME="/home/$KIOSK_USER"
KIOSK_PROFILE_DIR="$KIOSK_HOME/.config/einsatzzentrale-chromium"
KIOSK_LAUNCH_SCRIPT="$KIOSK_HOME/.local/bin/einsatzzentrale-kiosk.sh"
KIOSK_URL_FILE="$KIOSK_HOME/.config/einsatzzentrale-url"
KIOSK_SCALE_FILE="$KIOSK_HOME/.config/einsatzzentrale-scale"

C_GREEN="\033[1;32m"; C_YELLOW="\033[1;33m"; C_RED="\033[1;31m"; C_NC="\033[0m"
log()  { echo -e "${C_GREEN}[+]${C_NC} $*"; }
warn() { echo -e "${C_YELLOW}[!]${C_NC} $*"; }
err()  { echo -e "${C_RED}[x]${C_NC} $*" >&2; }

if [[ $EUID -ne 0 ]]; then err "Bitte mit sudo ausfuehren."; exit 1; fi
if [[ "$KIOSK_USER" == "root" ]]; then
  err "Bitte als normaler User aufrufen, nicht direkt als root."; exit 1
fi
if [[ ! -d "$KIOSK_HOME" ]]; then err "Home '$KIOSK_HOME' nicht gefunden."; exit 1; fi

# ---------- Uninstall --------------------------------------------------------
if [[ "${1:-}" == "--uninstall" ]]; then
  log "Deinstalliere Einsatzzentrale Kiosk..."
  rm -f  "$KIOSK_LAUNCH_SCRIPT" "$KIOSK_URL_FILE" "$KIOSK_SCALE_FILE"
  rm -rf "$KIOSK_PROFILE_DIR"
  rm -f  "$KIOSK_HOME/.config/autostart/einsatzzentrale-kiosk.desktop"
  if [[ -f /etc/gdm3/custom.conf ]]; then
    sed -i '/^AutomaticLoginEnable/d;/^AutomaticLogin=/d' /etc/gdm3/custom.conf
  fi
  systemctl stop einsatzzentrale-pi.service 2>/dev/null || true
  systemctl disable einsatzzentrale-pi.service 2>/dev/null || true
  rm -f /etc/systemd/system/einsatzzentrale-pi.service /etc/einsatzzentrale-pi.conf
  rm -rf /usr/local/lib/einsatzzentrale-pi /var/lib/einsatzzentrale-pi
  systemctl daemon-reload 2>/dev/null || true
  log "Fertig. Bitte neu starten."
  exit 0
fi

URL="${1:-}"
if [[ -z "$URL" ]]; then
  err "Keine URL angegeben."
  err "Beispiel: sudo bash $0 \"https://eventenergie.app/einsatzzentrale?pi_id=XXX&key=YYY\""
  exit 1
fi
if [[ ! "$URL" =~ ^https?:// ]]; then err "URL muss mit http(s):// beginnen."; exit 1; fi

log "Kiosk-URL:   $URL"
log "Kiosk-User:  $KIOSK_USER ($KIOSK_HOME)"

if [[ -r /etc/os-release ]]; then
  . /etc/os-release
  log "OS:          ${PRETTY_NAME:-$ID}"
  if [[ "${ID:-}" != "ubuntu" ]] && [[ "${ID_LIKE:-}" != *"ubuntu"* ]]; then
    warn "Skript ist fuer Ubuntu Desktop. Erkannt: ${ID:-unbekannt}. Fahre fort..."
  fi
fi

export DEBIAN_FRONTEND=noninteractive
log "apt-get update..."
apt-get update -y -qq

# ---------- Google Chrome stable installieren --------------------------------
if ! command -v google-chrome-stable >/dev/null 2>&1; then
  log "Installiere Google Chrome stable (DEB-Repo)..."
  install -d /usr/share/keyrings
  curl -fsSL https://dl.google.com/linux/linux_signing_key.pub \
    | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg
  cat > /etc/apt/sources.list.d/google-chrome.list <<'GCR'
deb [arch=amd64,arm64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main
GCR
  apt-get update -y -qq
  apt-get install -y --no-install-recommends google-chrome-stable
fi
CHROME_BIN="$(command -v google-chrome-stable)"
log "Chrome:      $CHROME_BIN ($(google-chrome-stable --version 2>/dev/null | head -1))"

log "Installiere Hilfspakete..."
apt-get install -y --no-install-recommends \
  unclutter x11-xserver-utils fonts-noto-color-emoji curl ca-certificates zenity \
  >/dev/null 2>&1 || true
fc-cache -f 2>/dev/null || true

# ---------- GDM3 Autologin + Wayland aus -------------------------------------
if [[ -f /etc/gdm3/custom.conf ]] || command -v gdm3 >/dev/null 2>&1; then
  log "GDM3: Autologin '$KIOSK_USER' + Wayland aus..."
  install -d /etc/gdm3
  if [[ ! -f /etc/gdm3/custom.conf ]]; then
    cat > /etc/gdm3/custom.conf <<'GDMINIT'
[daemon]
[security]
[xdmcp]
[chooser]
[debug]
GDMINIT
  fi
  if grep -q '^#\?\s*WaylandEnable' /etc/gdm3/custom.conf; then
    sed -i 's/^#\?\s*WaylandEnable.*/WaylandEnable=false/' /etc/gdm3/custom.conf
  else
    sed -i '/^\[daemon\]/a WaylandEnable=false' /etc/gdm3/custom.conf
  fi
  sed -i '/^AutomaticLoginEnable/d;/^AutomaticLogin=/d' /etc/gdm3/custom.conf
  sed -i "/^\[daemon\]/a AutomaticLoginEnable=true\nAutomaticLogin=$KIOSK_USER" /etc/gdm3/custom.conf
  systemctl enable gdm3.service 2>/dev/null || true
  systemctl set-default graphical.target 2>/dev/null || true
else
  warn "GDM3 nicht gefunden - Autologin manuell konfigurieren."
fi

# ---------- URL- + Scale-Datei -----------------------------------------------
install -d -o "$KIOSK_USER" -g "$KIOSK_USER" "$KIOSK_HOME/.config"
install -d -o "$KIOSK_USER" -g "$KIOSK_USER" "$KIOSK_HOME/.local/bin"
install -d -o "$KIOSK_USER" -g "$KIOSK_USER" "$KIOSK_PROFILE_DIR"
install -d -o "$KIOSK_USER" -g "$KIOSK_USER" "$KIOSK_HOME/.config/autostart"

echo -n "$URL" > "$KIOSK_URL_FILE"
chown "$KIOSK_USER":"$KIOSK_USER" "$KIOSK_URL_FILE"
if [[ ! -s "$KIOSK_SCALE_FILE" ]]; then
  echo -n "1.0" > "$KIOSK_SCALE_FILE"
  chown "$KIOSK_USER":"$KIOSK_USER" "$KIOSK_SCALE_FILE"
fi

# ---------- Launcher-Skript --------------------------------------------------
log "Schreibe Launcher: $KIOSK_LAUNCH_SCRIPT"
cat > "$KIOSK_LAUNCH_SCRIPT" <<'LAUNCHER_EOF'
#!/usr/bin/env bash
set -u
LOGFILE="$HOME/.local/share/einsatzzentrale-kiosk.log"
mkdir -p "$(dirname "$LOGFILE")"

# Single-Instance-Lock
exec 9>/tmp/einsatzzentrale-kiosk.lock
if ! flock -n 9; then
  echo "[$(date '+%F %T')] Launcher laeuft bereits - exit." >> "$LOGFILE"
  exit 0
fi
echo "[$(date '+%F %T')] === Launcher-Start (PID $$) ===" >> "$LOGFILE"

URL="$(cat "$HOME/.config/einsatzzentrale-url" 2>/dev/null || echo "")"
SCALE="$(cat "$HOME/.config/einsatzzentrale-scale" 2>/dev/null || echo "1.0")"
if [[ -z "$URL" ]]; then echo "Keine URL hinterlegt." >&2; exit 1; fi

PROFILE="$HOME/.config/einsatzzentrale-chromium"
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

# Display-Blanking aus
command -v xset >/dev/null 2>&1 && { xset s off 2>/dev/null || true; xset -dpms 2>/dev/null || true; xset s noblank 2>/dev/null || true; }
command -v unclutter >/dev/null 2>&1 && { pkill -f "unclutter.*-idle" 2>/dev/null || true; unclutter -idle 1 -root & }

# GNOME-Notifications + Screensaver aus (best effort)
if command -v gsettings >/dev/null 2>&1; then
  gsettings set org.gnome.desktop.notifications show-banners false 2>/dev/null || true
  gsettings set org.gnome.desktop.session idle-delay 0 2>/dev/null || true
  gsettings set org.gnome.desktop.screensaver lock-enabled false 2>/dev/null || true
  gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-ac-type 'nothing' 2>/dev/null || true
fi

unset WAYLAND_DISPLAY WAYLAND_SOCKET
export GDK_BACKEND=x11
export QT_QPA_PLATFORM=xcb
export XDG_SESSION_TYPE=x11

CRASH_COUNT=0
LAST_CRASH=0
while true; do
  pkill -9 -f "user-data-dir=$PROFILE" 2>/dev/null || true
  sleep 0.3
  rm -f "$PROFILE/SingletonLock" "$PROFILE/SingletonCookie" "$PROFILE/SingletonSocket" 2>/dev/null || true
  rm -f "$PROFILE/Default/SingletonLock" "$PROFILE/Default/SingletonCookie" "$PROFILE/Default/SingletonSocket" 2>/dev/null || true

  echo "[$(date '+%F %T')] Starte Chrome auf $URL (scale=$SCALE)" >> "$LOGFILE"
  google-chrome-stable \
    --kiosk \
    --noerrdialogs \
    --disable-infobars \
    --disable-translate \
    --disable-features=TranslateUI,Translate,AutofillEnableAccountWalletStorage \
    --no-first-run \
    --no-default-browser-check \
    --disable-session-crashed-bubble \
    --disable-component-update \
    --disable-pinch \
    --overscroll-history-navigation=0 \
    --autoplay-policy=no-user-gesture-required \
    --user-data-dir="$PROFILE" \
    --start-fullscreen \
    --check-for-update-interval=31536000 \
    --password-store=basic \
    --lang=de-DE \
    --force-device-scale-factor="$SCALE" \
    --ozone-platform=x11 \
    --no-sandbox \
    --disable-dev-shm-usage \
    --disable-sync \
    --disable-background-networking \
    --disable-default-apps \
    "$URL" >> "$LOGFILE" 2>&1

  EXIT_CODE=$?
  NOW=$(date +%s)
  echo "[$(date '+%F %T')] Chrome beendet (Exit $EXIT_CODE)" >> "$LOGFILE"
  if (( NOW - LAST_CRASH < 60 )); then CRASH_COUNT=$((CRASH_COUNT + 1)); else CRASH_COUNT=1; fi
  LAST_CRASH=$NOW
  if (( CRASH_COUNT >= 5 )); then
    echo "[$(date '+%F %T')] 5 Crashes in 60s - 30s Pause." >> "$LOGFILE"
    command -v zenity >/dev/null 2>&1 && zenity --error --no-wrap --title="Kiosk-Fehler" --text="Chrome konnte nicht starten.\n\nLog: $LOGFILE" 2>/dev/null &
    sleep 30; CRASH_COUNT=0
  else
    sleep 3
  fi
done
LAUNCHER_EOF
chmod +x "$KIOSK_LAUNCH_SCRIPT"
chown "$KIOSK_USER":"$KIOSK_USER" "$KIOSK_LAUNCH_SCRIPT"

# ---------- XDG Autostart -----------------------------------------------------
cat > "$KIOSK_HOME/.config/autostart/einsatzzentrale-kiosk.desktop" <<DESKTOP_EOF
[Desktop Entry]
Type=Application
Name=Einsatzzentrale Kiosk
Comment=Eventenergie Einsatzzentrale Chrome-Kiosk
Exec=$KIOSK_LAUNCH_SCRIPT
Terminal=false
X-GNOME-Autostart-enabled=true
NoDisplay=false
DESKTOP_EOF
chown "$KIOSK_USER":"$KIOSK_USER" "$KIOSK_HOME/.config/autostart/einsatzzentrale-kiosk.desktop"

# ---------- Aufraeumen Pi-Service-Reste --------------------------------------
if systemctl list-unit-files 2>/dev/null | grep -q "einsatzzentrale-pi.service"; then
  log "Entferne alte Pi-Service-Reste..."
  systemctl stop einsatzzentrale-pi.service 2>/dev/null || true
  systemctl disable einsatzzentrale-pi.service 2>/dev/null || true
  rm -f /etc/systemd/system/einsatzzentrale-pi.service /etc/einsatzzentrale-pi.conf
  rm -rf /usr/local/lib/einsatzzentrale-pi /var/lib/einsatzzentrale-pi
  systemctl daemon-reload 2>/dev/null || true
fi

log ""
log "================================================================"
log "  Installation abgeschlossen."
log "================================================================"
log "  URL:      $URL"
log "  User:     $KIOSK_USER"
log "  Browser:  $CHROME_BIN"
log "  Launcher: $KIOSK_LAUNCH_SCRIPT"
log ""
log "  Naechster Schritt:   sudo reboot"
log ""
log "  URL aendern:    echo 'NEUE_URL' | sudo tee $KIOSK_URL_FILE && sudo reboot"
log "  Scale aendern:  echo '1.5' > $KIOSK_SCALE_FILE && sudo reboot"
log "  Log:            tail -f $KIOSK_HOME/.local/share/einsatzzentrale-kiosk.log"
log "  Deinstall:      sudo bash $0 --uninstall"
log "================================================================"
