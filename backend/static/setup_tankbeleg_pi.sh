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

# --- Systemaktualisierung ---
echo ""
echo "[1/6] System aktualisieren..."
apt-get update -qq
apt-get install -y python3-pip python3-serial gpsd gpsd-clients python3-gps

# --- Python-Pakete ---
echo ""
echo "[2/6] Python-Pakete installieren..."
pip3 install --break-system-packages pyserial requests 2>/dev/null || \
pip3 install pyserial requests

# --- Skript kopieren ---
echo ""
echo "[3/6] Tankbeleg-Skript installieren..."
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cp "$SCRIPT_DIR/tankbeleg_pi.py" /opt/tankbeleg_pi.py
chmod +x /opt/tankbeleg_pi.py

# --- Konfiguration ---
echo ""
echo "[4/6] Konfiguration einrichten..."
if [ ! -f /etc/tankbeleg_pi.conf ]; then
    cp "$SCRIPT_DIR/tankbeleg_pi.conf" /etc/tankbeleg_pi.conf
    echo "  Konfigurationsdatei erstellt: /etc/tankbeleg_pi.conf"
    echo "  WICHTIG: Bitte api_url in /etc/tankbeleg_pi.conf anpassen!"
else
    echo "  Konfiguration existiert bereits, wird nicht ueberschrieben"
fi

# --- Datenbank-Verzeichnis ---
echo ""
echo "[5/6] Datenbank-Verzeichnis erstellen..."
mkdir -p /var/lib/tankbeleg
chown pi:pi /var/lib/tankbeleg

# --- Systemd-Service ---
echo ""
echo "[6/6] Systemd-Service einrichten..."
cp "$SCRIPT_DIR/tankbeleg_pi.service" /etc/systemd/system/tankbeleg_pi.service
systemctl daemon-reload
systemctl enable tankbeleg_pi

# --- GPS konfigurieren ---
echo ""
echo "GPS-Konfiguration:"
echo "  Fuer USB-GPS-Modul /etc/default/gpsd anpassen:"
echo "  DEVICES=\"/dev/ttyACM0\""
echo "  GPSD_OPTIONS=\"-n\""
echo "  Dann: sudo systemctl restart gpsd"

# --- Serielle Berechtigung ---
echo ""
echo "Serielle Berechtigung:"
usermod -a -G dialout pi 2>/dev/null || true
echo "  Benutzer 'pi' zur Gruppe 'dialout' hinzugefuegt"

# --- Zusammenfassung ---
echo ""
echo "=============================================="
echo "  Setup abgeschlossen!"
echo "=============================================="
echo ""
echo "  Naechste Schritte:"
echo "  1. /etc/tankbeleg_pi.conf anpassen (api_url!)"
echo "  2. USB-RS232 Adapter anschliessen"
echo "  3. Optional: GPS-Modul konfigurieren"
echo "  4. Service starten:"
echo "     sudo systemctl start tankbeleg_pi"
echo ""
echo "  Status pruefen:"
echo "     sudo systemctl status tankbeleg_pi"
echo "     sudo journalctl -u tankbeleg_pi -f"
echo ""
