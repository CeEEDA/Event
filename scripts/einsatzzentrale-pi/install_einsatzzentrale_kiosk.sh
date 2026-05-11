#!/usr/bin/env bash
# ============================================================================
# Eventenergie - Einsatzzentrale Pi Kiosk Installer
# ============================================================================
# Funktioniert auf:
#   - Raspberry Pi OS (Desktop)  -> Bookworm / Bullseye
#   - Raspberry Pi OS Lite       -> minimaler X11+openbox+lightdm wird
#                                   automatisch nachinstalliert
#
# Was passiert:
#   - Falls noetig: minimaler Desktop-Stack (xserver, openbox, lightdm,
#     chromium) wird installiert
#   - Autologin wird per lightdm.conf konfiguriert (User pi/admin/SUDO_USER)
#   - Kiosk-Launcher startet Chromium im Vollbild, mit Watchdog-Restart
#   - Translate-Popup, Erste-Schritte-Wizard, Password-Manager,
#     Crash-Bubbles, Update-Prompts werden unterdrueckt
#   - Screen-Blanking + DPMS deaktiviert
#
# Benutzung:
#   sudo bash install_einsatzzentrale_kiosk.sh https://dein-portal.de/api/einsatzzentrale/kiosk-page
#
# Hinweis: Sowohl /einsatzzentrale (mit automatischem Redirect) als auch
# /api/einsatzzentrale/kiosk-page funktionieren. Empfohlen ist die direkte
# Kiosk-Page-URL, da sie einen Schritt ohne Redirect liefert.
#
# Deinstallation (nur Kiosk-Teile, OS-Pakete bleiben):
#   sudo bash install_einsatzzentrale_kiosk.sh --uninstall
# ============================================================================

set -euo pipefail

# ---------- Konfiguration ----------------------------------------------------
DEFAULT_URL="https://dein-portal.example/api/einsatzzentrale/kiosk-page"
KIOSK_USER="${SUDO_USER:-pi}"
KIOSK_HOME="$(getent passwd "$KIOSK_USER" | cut -d: -f6 || true)"
[[ -z "$KIOSK_HOME" ]] && KIOSK_HOME="/home/$KIOSK_USER"
KIOSK_PROFILE_DIR="$KIOSK_HOME/.config/einsatzzentrale-chromium"
KIOSK_LAUNCH_SCRIPT="$KIOSK_HOME/.local/bin/einsatzzentrale-kiosk.sh"
KIOSK_URL_FILE="$KIOSK_HOME/.config/einsatzzentrale-url"

C_GREEN="\033[1;32m"; C_YELLOW="\033[1;33m"; C_RED="\033[1;31m"; C_NC="\033[0m"
log()  { echo -e "${C_GREEN}[+]${C_NC} $*"; }
warn() { echo -e "${C_YELLOW}[!]${C_NC} $*"; }
err()  { echo -e "${C_RED}[x]${C_NC} $*" >&2; }

# ---------- Root-Check -------------------------------------------------------
if [[ $EUID -ne 0 ]]; then
  err "Bitte mit sudo ausfuehren."
  exit 1
fi
if [[ ! -d "$KIOSK_HOME" ]]; then
  err "Home-Verzeichnis fuer User '$KIOSK_USER' nicht gefunden ($KIOSK_HOME)."
  exit 1
fi

# ---------- Uninstall --------------------------------------------------------
if [[ "${1:-}" == "--uninstall" ]]; then
  log "Deinstalliere Einsatzzentrale Kiosk..."
  rm -f  "$KIOSK_LAUNCH_SCRIPT" "$KIOSK_URL_FILE"
  rm -rf "$KIOSK_PROFILE_DIR"
  rm -f  "$KIOSK_HOME/.config/autostart/einsatzzentrale-kiosk.desktop"
  rm -f  "$KIOSK_HOME/.config/openbox/autostart"
  for f in "$KIOSK_HOME/.config/wayfire.ini" \
           "$KIOSK_HOME/.config/labwc/autostart" \
           "$KIOSK_HOME/.config/lxsession/LXDE-pi/autostart" \
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

# ---------- Pi-ID + Key aus URL extrahieren ---------------------------------
# Falls die URL Parameter pi_id=&key= enthaelt (Setup-Generator im Portal),
# verwenden wir diese fuer den lokalen Pi-Service. CLOUD_URL = origin der URL.
CLOUD_URL=""; PI_ID=""; PI_KEY=""
if [[ "$URL" =~ ^(https?://[^/]+) ]]; then CLOUD_URL="${BASH_REMATCH[1]}"; fi
if [[ "$URL" == *"pi_id="* ]]; then
  PI_ID="$(echo "$URL" | sed -n 's/.*[?&]pi_id=\([^&]*\).*/\1/p')"
fi
if [[ "$URL" == *"key="* ]]; then
  PI_KEY="$(echo "$URL" | sed -n 's/.*[?&]key=\([^&]*\).*/\1/p')"
fi
log "Cloud-URL:   ${CLOUD_URL:-<nicht erkannt>}"
[[ -n "$PI_ID" ]] && log "Pi-ID:       ${PI_ID:0:8}..."

# ---------- Desktop-Detection ------------------------------------------------
HAS_DESKTOP=false
if command -v startx >/dev/null 2>&1 || dpkg -s xserver-xorg >/dev/null 2>&1; then
  HAS_DESKTOP=true
fi

# Apt-Update einmal vorab
export DEBIAN_FRONTEND=noninteractive
log "apt-get update..."
apt-get update -y

# ---------- Fall A: Pi OS Lite -> minimalen Stack installieren --------------
if [[ "$HAS_DESKTOP" == "false" ]]; then
  log "Pi OS Lite erkannt - installiere minimalen X11-Kiosk-Stack..."
  apt-get install -y --no-install-recommends \
    xserver-xorg xserver-xorg-legacy xserver-xorg-input-libinput \
    xinit x11-xserver-utils \
    openbox \
    lightdm \
    chromium-browser \
    unclutter \
    fonts-dejavu-core \
    libgl1-mesa-dri \
    plymouth plymouth-themes
  # Anyone may start X (sonst startx als non-root nicht erlaubt)
  if [[ -f /etc/X11/Xwrapper.config ]]; then
    sed -i 's/^allowed_users=.*/allowed_users=anybody/' /etc/X11/Xwrapper.config
  else
    echo "allowed_users=anybody" > /etc/X11/Xwrapper.config
  fi
fi

# ---------- Chromium sicherstellen -------------------------------------------
if ! command -v chromium-browser >/dev/null 2>&1 && ! command -v chromium >/dev/null 2>&1; then
  apt-get install -y --no-install-recommends chromium-browser || apt-get install -y --no-install-recommends chromium
fi
CHROMIUM_BIN="$(command -v chromium-browser || command -v chromium || true)"
log "Chromium:    ${CHROMIUM_BIN:-(noch nicht installiert)}"

apt-get install -y --no-install-recommends unclutter x11-xserver-utils openbox 2>/dev/null || true

# ============================================================================
# LOKALER PI-SERVICE (Offline-Cache + 2-Min-Sync + 3-Monats-Retention)
# ============================================================================
# Python3 + Abhaengigkeiten
log "Installiere Python3 + Pi-Service-Abhaengigkeiten..."
apt-get install -y --no-install-recommends python3 python3-pip python3-venv curl ca-certificates

PI_SERVICE_DIR="/usr/local/lib/einsatzzentrale-pi"
PI_SERVICE_VENV="$PI_SERVICE_DIR/venv"
PI_SERVICE_CONF="/etc/einsatzzentrale-pi.conf"
PI_SERVICE_DATA="/var/lib/einsatzzentrale-pi"
PI_SERVICE_LOG="/var/log/einsatzzentrale-pi.log"

install -d "$PI_SERVICE_DIR" "$PI_SERVICE_DATA" "$(dirname "$PI_SERVICE_LOG")"
touch "$PI_SERVICE_LOG"

# venv anlegen + Pakete (fastapi, uvicorn, httpx)
if [[ ! -x "$PI_SERVICE_VENV/bin/python" ]]; then
  log "Erstelle Python-venv unter $PI_SERVICE_VENV ..."
  python3 -m venv "$PI_SERVICE_VENV"
fi
"$PI_SERVICE_VENV/bin/pip" install --upgrade pip wheel >/dev/null
"$PI_SERVICE_VENV/bin/pip" install "fastapi>=0.110" "uvicorn[standard]>=0.27" "httpx>=0.26" >/dev/null

# Pi-Service-Code holen (aus dem Portal selbst, oder via base64-Embedded)
if [[ -n "$CLOUD_URL" ]]; then
  log "Lade Pi-Service-Skript vom Portal..."
  curl -fsSL -o "$PI_SERVICE_DIR/pi_service.py" "$CLOUD_URL/api/einsatzzentrale/pi-service.py" || \
    warn "Pi-Service-Download fehlgeschlagen - lokal weiterversuchen"
  # Kiosk-HTML lokal cachen damit Boot ohne Internet moeglich ist
  curl -fsSL -o "$PI_SERVICE_DIR/kiosk.html" "$CLOUD_URL/api/einsatzzentrale/kiosk-page" || \
    warn "Kiosk-HTML-Download fehlgeschlagen"
fi

# Config
cat > "$PI_SERVICE_CONF" <<PICONF_EOF
# Einsatzzentrale Pi-Service - automatisch generiert
CLOUD_URL=$CLOUD_URL
PI_ID=$PI_ID
PI_KEY=$PI_KEY
SYNC_INTERVAL_SEC=120
RETENTION_DAYS=90
PICONF_EOF
chmod 640 "$PI_SERVICE_CONF"

# systemd-Service
cat > /etc/systemd/system/einsatzzentrale-pi.service <<SYSD_EOF
[Unit]
Description=Einsatzzentrale Pi-Service (Offline-Cache + Sync)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
EnvironmentFile=$PI_SERVICE_CONF
Environment=PI_CONFIG=$PI_SERVICE_CONF
Environment=PI_DATA_DIR=$PI_SERVICE_DATA
Environment=PI_LOG=$PI_SERVICE_LOG
Environment=PI_KIOSK_HTML=$PI_SERVICE_DIR/kiosk.html
ExecStart=$PI_SERVICE_VENV/bin/python $PI_SERVICE_DIR/pi_service.py
Restart=always
RestartSec=5
StandardOutput=append:$PI_SERVICE_LOG
StandardError=append:$PI_SERVICE_LOG

[Install]
WantedBy=multi-user.target
SYSD_EOF

systemctl daemon-reload
systemctl enable einsatzzentrale-pi.service
systemctl restart einsatzzentrale-pi.service || warn "Pi-Service-Start fehlgeschlagen - siehe $PI_SERVICE_LOG"

# Chromium soll JETZT auf den lokalen Service zeigen statt zur Cloud
# (sofern wir die Cloud-URL kennen, also die Setup-Variante)
if [[ -n "$CLOUD_URL" ]]; then
  log "Stelle Chromium auf lokalen Pi-Service (localhost:8001) um"
  URL="http://localhost:8001/kiosk"
fi
# ============================================================================

# ---------- LightDM Autologin konfigurieren ---------------------------------
if command -v lightdm >/dev/null 2>&1; then
  log "Konfiguriere lightdm Autologin fuer '$KIOSK_USER'..."
  install -d /etc/lightdm/lightdm.conf.d
  cat > /etc/lightdm/lightdm.conf.d/50-einsatzzentrale.conf <<LIGHTDM_EOF
[Seat:*]
autologin-user=$KIOSK_USER
autologin-user-timeout=0
user-session=openbox
LIGHTDM_EOF
  systemctl enable lightdm.service 2>/dev/null || true
  systemctl set-default graphical.target 2>/dev/null || true
fi

# ---------- Openbox Autostart (Pi OS Lite) ----------------------------------
install -d -o "$KIOSK_USER" -g "$KIOSK_USER" "$KIOSK_HOME/.config/openbox"
OPENBOX_AS="$KIOSK_HOME/.config/openbox/autostart"
touch "$OPENBOX_AS"
chown "$KIOSK_USER":"$KIOSK_USER" "$OPENBOX_AS"
if ! grep -q "einsatzzentrale-kiosk.sh" "$OPENBOX_AS" 2>/dev/null; then
  cat >> "$OPENBOX_AS" <<EOF
# Einsatzzentrale Kiosk
$KIOSK_LAUNCH_SCRIPT &
EOF
fi

# ---------- Kiosk-Skript anlegen --------------------------------------------
log "Schreibe Launch-Skript $KIOSK_LAUNCH_SCRIPT ..."
install -d -o "$KIOSK_USER" -g "$KIOSK_USER" "$(dirname "$KIOSK_LAUNCH_SCRIPT")"
install -d -o "$KIOSK_USER" -g "$KIOSK_USER" "$KIOSK_PROFILE_DIR"
echo -n "$URL" > "$KIOSK_URL_FILE"
chown "$KIOSK_USER":"$KIOSK_USER" "$KIOSK_URL_FILE"

# Default-Scale fuer 50"-TV (kann spaeter angepasst werden)
echo -n "1.5" > "$KIOSK_HOME/.config/einsatzzentrale-scale"
chown "$KIOSK_USER":"$KIOSK_USER" "$KIOSK_HOME/.config/einsatzzentrale-scale"

# Swap auf 2 GB hochsetzen (Pi 5 mit 1GB RAM ist knapp fuer Chromium)
if [[ -f /etc/dphys-swapfile ]]; then
  log "Setze Swap auf 2048 MB (Pi mit wenig RAM)..."
  sed -i 's/^CONF_SWAPSIZE=.*/CONF_SWAPSIZE=2048/' /etc/dphys-swapfile
  systemctl stop dphys-swapfile 2>/dev/null || true
  systemctl start dphys-swapfile 2>/dev/null || true
fi

cat > "$KIOSK_LAUNCH_SCRIPT" <<'LAUNCHER_EOF'
#!/usr/bin/env bash
# Einsatzzentrale Kiosk Launcher
set -u

LOGFILE="$HOME/.local/share/einsatzzentrale-kiosk.log"
mkdir -p "$(dirname "$LOGFILE")"

# ----- SINGLE-INSTANCE-LOCK -------------------------------------------------
# Verhindert dass zwei Launcher gleichzeitig laufen (passiert wenn openbox +
# xdg-autostart + LXDE-autostart alle dieselbe Datei aufrufen). Zwei Launcher
# wuerden sich gegenseitig die Chromium-Prozesse killen.
exec 9>/tmp/einsatzzentrale-kiosk.lock
if ! flock -n 9; then
  echo "[$(date '+%F %T')] Launcher laeuft bereits (lock-fail) - exit." >> "$LOGFILE"
  exit 0
fi
echo "[$(date '+%F %T')] Launcher-Start (PID $$)" >> "$LOGFILE"

URL="$(cat "$HOME/.config/einsatzzentrale-url" 2>/dev/null || echo "")"
SCALE="$(cat "$HOME/.config/einsatzzentrale-scale" 2>/dev/null || echo "1.5")"
if [[ -z "$URL" ]]; then
  echo "Keine URL hinterlegt." >&2
  exit 1
fi

PROFILE="$HOME/.config/einsatzzentrale-chromium"
mkdir -p "$PROFILE/Default"

# Translate-Popup, Erste-Schritte, Default-Browser-Frage etc. unterdruecken
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

# Screen-Blanking deaktivieren (X11)
if command -v xset >/dev/null 2>&1; then
  xset s off 2>/dev/null || true
  xset -dpms 2>/dev/null || true
  xset s noblank 2>/dev/null || true
fi
# Maus ausblenden bei Inaktivitaet
if command -v unclutter >/dev/null 2>&1; then
  pkill -f "unclutter.*-idle" 2>/dev/null || true
  unclutter -idle 1 -root &
fi

CHROMIUM="$(command -v chromium-browser || command -v chromium)"
if [[ -z "$CHROMIUM" ]]; then
  echo "Chromium nicht installiert." >&2
  exit 1
fi

# Sicherstellen dass Chromium NICHT Wayland versucht (wir laufen auf X11+openbox).
# Mixed Wayland/X11 verursacht Renderer-Crash-Loop.
unset WAYLAND_DISPLAY
unset WAYLAND_SOCKET
export GDK_BACKEND=x11
export QT_QPA_PLATFORM=xcb
export XDG_SESSION_TYPE=x11

# Falls Chromium-Snap-Reste oder alte Wayland-Sessions liegen: cleanen
rm -f "$PROFILE/SingletonLock" "$PROFILE/SingletonCookie" "$PROFILE/SingletonSocket" 2>/dev/null || true

# Crash-Counter: nach 5 schnellen Restarts (innerhalb 60s) stoppen
# damit man den Fehler im Log sieht statt endlos zu blinken.
CRASH_COUNT=0
LAST_CRASH=0
while true; do
  # ----- WICHTIG -----
  # Nur RESIDUALE Chromium-Instanzen aus unserem eigenen Profile killen.
  # NICHT alle Chromium-Prozesse - das wuerde unseren eigenen Browser killen,
  # falls ein zweiter Launcher-Run versucht zu starten (Exit-137-Loop).
  pkill -9 -f "user-data-dir=$PROFILE" 2>/dev/null || true
  sleep 0.3
  rm -f "$PROFILE/SingletonLock" "$PROFILE/SingletonCookie" "$PROFILE/SingletonSocket" 2>/dev/null || true
  rm -f "$PROFILE/Default/SingletonLock" "$PROFILE/Default/SingletonCookie" "$PROFILE/Default/SingletonSocket" 2>/dev/null || true

  echo "[$(date '+%F %T')] Starte Chromium auf $URL (scale=$SCALE)" >> "$LOGFILE"
  "$CHROMIUM" \
    --kiosk \
    --noerrdialogs \
    --disable-infobars \
    --disable-translate \
    --disable-features=TranslateUI,Translate,AutofillEnableAccountWalletStorage,UseChromeOSDirectVideoDecoder \
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
    --lang=de-DE \
    --force-device-scale-factor="$SCALE" \
    --ozone-platform=x11 \
    --disable-gpu \
    --disable-gpu-compositing \
    --disable-software-rasterizer \
    --disable-dev-shm-usage \
    --no-sandbox \
    --process-per-site \
    --disable-low-end-device-mode \
    --disable-sync \
    --disable-background-networking \
    --disable-cloud-management-enrollment \
    --disable-default-apps \
    --js-flags=" " \
    "$URL" >> "$LOGFILE" 2>&1

  EXIT_CODE=$?
  NOW=$(date +%s)
  echo "[$(date '+%F %T')] Chromium beendet (Exit $EXIT_CODE)" >> "$LOGFILE"
  if (( NOW - LAST_CRASH < 60 )); then
    CRASH_COUNT=$((CRASH_COUNT + 1))
  else
    CRASH_COUNT=1
  fi
  LAST_CRASH=$NOW
  if (( CRASH_COUNT >= 5 )); then
    echo "[$(date '+%F %T')] 5 schnelle Crashes - stoppe Loop. Logfile: $LOGFILE" >> "$LOGFILE"
    # Zeige Fehler-Screen statt endlos zu restarten
    if command -v xmessage >/dev/null 2>&1; then
      xmessage -center "Kiosk konnte nicht starten. Log: $LOGFILE"
    fi
    sleep 30
    CRASH_COUNT=0
  else
    sleep 5
  fi
done
LAUNCHER_EOF
chmod +x "$KIOSK_LAUNCH_SCRIPT"
chown "$KIOSK_USER":"$KIOSK_USER" "$KIOSK_LAUNCH_SCRIPT"

# ---------- Zusaetzliche Autostarts (Wayland / LXDE Desktop) ----------------
# Falls Pi OS Desktop installiert war (oder spaeter wird), funktioniert es auch dort.

# XDG-Autostart
install -d -o "$KIOSK_USER" -g "$KIOSK_USER" "$KIOSK_HOME/.config/autostart"
cat > "$KIOSK_HOME/.config/autostart/einsatzzentrale-kiosk.desktop" <<DESKTOP_EOF
[Desktop Entry]
Type=Application
Name=Einsatzzentrale Kiosk
Comment=Chromium Kiosk fuer Einsatzzentrale
Exec=$KIOSK_LAUNCH_SCRIPT
Terminal=false
X-GNOME-Autostart-enabled=true
NoDisplay=false
DESKTOP_EOF
chown "$KIOSK_USER":"$KIOSK_USER" "$KIOSK_HOME/.config/autostart/einsatzzentrale-kiosk.desktop"

# Wayland labwc (Bookworm Desktop Default)
if command -v labwc >/dev/null 2>&1; then
  install -d -o "$KIOSK_USER" -g "$KIOSK_USER" "$KIOSK_HOME/.config/labwc"
  AS="$KIOSK_HOME/.config/labwc/autostart"
  touch "$AS"; chown "$KIOSK_USER":"$KIOSK_USER" "$AS"
  if ! grep -q "einsatzzentrale-kiosk.sh" "$AS" 2>/dev/null; then
    echo "$KIOSK_LAUNCH_SCRIPT &" >> "$AS"
  fi
fi
# X11 LXDE
if [[ -d "/etc/xdg/lxsession/LXDE-pi" ]]; then
  install -d -o "$KIOSK_USER" -g "$KIOSK_USER" "$KIOSK_HOME/.config/lxsession/LXDE-pi"
  AS="$KIOSK_HOME/.config/lxsession/LXDE-pi/autostart"
  if [[ ! -f "$AS" ]]; then
    cp "/etc/xdg/lxsession/LXDE-pi/autostart" "$AS" 2>/dev/null || touch "$AS"
    chown "$KIOSK_USER":"$KIOSK_USER" "$AS"
  fi
  if ! grep -q "einsatzzentrale-kiosk.sh" "$AS" 2>/dev/null; then
    echo "@$KIOSK_LAUNCH_SCRIPT" >> "$AS"
  fi
fi

# ---------- Screen-Blanking aus via raspi-config -----------------------------
if command -v raspi-config >/dev/null 2>&1; then
  raspi-config nonint do_blanking 1 || true
fi

# ---------- Fertig -----------------------------------------------------------
log ""
log "================================================================"
log "  Installation abgeschlossen."
log "================================================================"
log "  URL:        $URL"
log "  User:       $KIOSK_USER"
log "  Launcher:   $KIOSK_LAUNCH_SCRIPT"
log "  URL-Datei:  $KIOSK_URL_FILE   (zum spaeteren Aendern)"
log ""
log "  Naechster Schritt:   sudo reboot"
log ""
log "  Nach dem Reboot bootet der Pi automatisch in den Kiosk-Modus,"
log "  startet lightdm + openbox, loggt '$KIOSK_USER' automatisch ein"
log "  und oeffnet Chromium im Vollbild auf der hinterlegten URL."
log ""
log "  URL spaeter aendern:"
log "     echo 'NEUE_URL' > $KIOSK_URL_FILE && sudo reboot"
log ""
log "  Schriftgroesse fuer grossen TV anpassen (1.0=normal, 1.5=50%, 2.0=doppelt):"
log "     echo '2.0' > $KIOSK_HOME/.config/einsatzzentrale-scale && sudo reboot"
log ""
log "  Logfile zur Fehlersuche (wenn Bildschirm blinkt):"
log "     tail -f $KIOSK_HOME/.local/share/einsatzzentrale-kiosk.log"
log ""
log "  Deinstall:"
log "     sudo bash $0 --uninstall"
log "================================================================"
