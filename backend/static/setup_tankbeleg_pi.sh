#!/bin/bash
# =====================================================
# Tankbeleg Pi - Setup-Skript
# Eventenergie Deutschland GmbH & Co. KG
# =====================================================
# Dieses Skript installiert alle Abhaengigkeiten und
# richtet den Tankbeleg-Dienst auf einem Raspberry Pi ein.
#
# Ausfuehren mit:
#   sudo bash setup_tankbeleg_pi.sh
# =====================================================

set -e

echo "=============================================="
echo "  Tankbeleg Pi - Setup"
echo "  Eventenergie Deutschland"
echo "=============================================="

# Root pruefen
if [ "$EUID" -ne 0 ]; then
    echo "FEHLER: Bitte mit sudo ausfuehren!"
    exit 1
fi

REAL_USER="${SUDO_USER:-$(whoami)}"
REAL_GROUP="$(id -gn "$REAL_USER" 2>/dev/null || echo "$REAL_USER")"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# --- Systemaktualisierung ---
echo ""
echo "[1/8] System aktualisieren..."
apt-get update -qq
apt-get install -y python3-pip python3-serial gpsd gpsd-clients python3-gps chromium-browser unclutter

# --- Python-Pakete ---
echo ""
echo "[2/8] Python-Pakete installieren..."
pip3 install --break-system-packages pyserial requests 2>/dev/null || \
pip3 install pyserial requests

# --- Skripte kopieren ---
echo ""
echo "[3/8] Tankbeleg-Skripte installieren..."
cp "$SCRIPT_DIR/tankbeleg_pi.py" /opt/tankbeleg_pi.py
cp "$SCRIPT_DIR/tankbeleg_ui.py" /opt/tankbeleg_ui.py
chmod +x /opt/tankbeleg_pi.py
chmod +x /opt/tankbeleg_ui.py
echo "  tankbeleg_pi.py -> /opt/"
echo "  tankbeleg_ui.py -> /opt/"

# --- Konfiguration ---
echo ""
echo "[4/8] Konfiguration einrichten..."
if [ ! -f /etc/tankbeleg_pi.conf ]; then
    cp "$SCRIPT_DIR/tankbeleg_pi.conf" /etc/tankbeleg_pi.conf
    echo "  Konfigurationsdatei erstellt: /etc/tankbeleg_pi.conf"
    echo "  WICHTIG: Bitte api_url in /etc/tankbeleg_pi.conf anpassen!"
else
    echo "  Konfiguration existiert bereits, wird nicht ueberschrieben"
fi

# --- Datenbank-Verzeichnis ---
echo ""
echo "[5/8] Datenbank-Verzeichnis erstellen..."
mkdir -p /var/lib/tankbeleg
chown "$REAL_USER:$REAL_GROUP" /var/lib/tankbeleg

# --- Systemd-Services ---
echo ""
echo "[6/8] Systemd-Services einrichten..."

# Tankbeleg Pi Service (Seriell + Sync)
sed "s/User=pi/User=$REAL_USER/g; s/Group=pi/Group=$REAL_GROUP/g" "$SCRIPT_DIR/tankbeleg_pi.service" > /etc/systemd/system/tankbeleg_pi.service

# Tankbeleg UI Service (Kiosk-Webserver)
cp "$SCRIPT_DIR/tankbeleg_ui.service" /etc/systemd/system/tankbeleg_ui.service

systemctl daemon-reload
systemctl enable tankbeleg_pi
systemctl enable tankbeleg_ui
echo "  tankbeleg_pi.service aktiviert"
echo "  tankbeleg_ui.service aktiviert"

# --- Chromium Kiosk Auto-Start ---
echo ""
echo "[7/8] Kiosk-Modus einrichten..."

AUTOSTART_DIR="/home/$REAL_USER/.config/autostart"
mkdir -p "$AUTOSTART_DIR"

cat > "$AUTOSTART_DIR/tankbeleg-kiosk.desktop" << 'KIOSK_EOF'
[Desktop Entry]
Type=Application
Name=Tankbeleg Kiosk
Exec=bash -c "sleep 5 && chromium-browser --kiosk --start-fullscreen --noerrdialogs --disable-infobars --disable-session-crashed-bubble --disable-translate --incognito --check-for-update-interval=31536000 http://localhost:8080"
X-GNOME-Autostart-enabled=true
KIOSK_EOF

chown "$REAL_USER:$REAL_GROUP" "$AUTOSTART_DIR/tankbeleg-kiosk.desktop"

# Mauszeiger ausblenden (unclutter)
cat > "$AUTOSTART_DIR/unclutter.desktop" << 'UNCLUTTER_EOF'
[Desktop Entry]
Type=Application
Name=Unclutter
Exec=unclutter -idle 1
X-GNOME-Autostart-enabled=true
UNCLUTTER_EOF

chown "$REAL_USER:$REAL_GROUP" "$AUTOSTART_DIR/unclutter.desktop"
echo "  Chromium Kiosk-Autostart eingerichtet"
echo "  Mauszeiger wird nach 1s ausgeblendet"

# --- Serielle Berechtigung + GPS ---
echo ""
echo "[8/8] Berechtigungen und GPS..."
usermod -a -G dialout "$REAL_USER" 2>/dev/null || true
echo "  Benutzer '$REAL_USER' zur Gruppe 'dialout' hinzugefuegt"
echo ""
echo "  GPS-Konfiguration:"
echo "  Fuer USB-GPS-Modul /etc/default/gpsd anpassen:"
echo "  DEVICES=\"/dev/ttyACM0\""
echo "  GPSD_OPTIONS=\"-n\""
echo "  Dann: sudo systemctl restart gpsd"

# --- Zusammenfassung ---
echo ""
echo "=============================================="
echo "  Setup abgeschlossen!"
echo "=============================================="
echo ""
echo "  Services starten:"
echo "    sudo systemctl start tankbeleg_pi"
echo "    sudo systemctl start tankbeleg_ui"
echo ""
echo "  Kiosk-UI oeffnen:"
echo "    http://localhost:8080"
echo ""
echo "  Status pruefen:"
echo "    sudo systemctl status tankbeleg_pi"
echo "    sudo systemctl status tankbeleg_ui"
echo ""
echo "  Logs:"
echo "    sudo journalctl -u tankbeleg_pi -f"
echo "    sudo journalctl -u tankbeleg_ui -f"
echo ""
echo "  Chromium startet automatisch beim naechsten"
echo "  Desktop-Login im Kiosk-Modus."
echo ""
echo "  WICHTIG: /etc/tankbeleg_pi.conf anpassen (api_url)!"
echo ""
