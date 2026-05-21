#!/bin/bash
# =====================================================
# Messkoffer Pi - Setup-Skript v2.0
# Eventenergie Deutschland GmbH & Co. KG
# =====================================================
# Hardware (ab Mai 2026):
#   - Raspberry Pi (3/4/5)
#   - Waveshare USB <-> RS485-Adapter (CH340/CP2102/FT232)
#   - Rayleigh RI-F100-C MID-Energiezaehler (Modbus RTU Slave 1)
#   - USB-GPS (optional)
#
# Eine Ausfuehrung. Dann reboot. Dann laeuft alles.
#
# Aufruf:  sudo bash setup_messkoffer.sh [API_URL] [DEVICE_KEY] [DEVICE_ID] [METER_ID]
# Beispiel:
#   sudo bash setup_messkoffer.sh \
#     https://portal.eventenergie.de/api \
#     PASTE-DEVICE-KEY-HERE \
#     mk-001 \
#     meter-001
# =====================================================

set -e

if [ "$EUID" -ne 0 ]; then
    echo "FEHLER: Bitte mit sudo ausfuehren!"
    exit 1
fi

API_URL="${1:-${MK_API_URL:-}}"
DEVICE_KEY="${2:-${MK_DEVICE_KEY:-}}"
DEVICE_ID="${3:-${MK_DEVICE_ID:-}}"
METER_ID="${4:-${MK_METER_ID:-}}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REAL_USER="${SUDO_USER:-pi}"

echo "=============================================="
echo "  Messkoffer Pi Setup v2.0"
echo "  Rayleigh RI-F100-C + USB-RS485 + GPS"
echo "  Eventenergie Deutschland"
echo "=============================================="
echo "  API:        ${API_URL:-(spaeter in /etc/messkoffer.conf eintragen)}"
echo "  Device:     ${DEVICE_ID:-(noch nicht gesetzt)}"
echo "=============================================="

# --- 1. System aktualisieren -----------------------------------------------
echo ""
echo "[1/8] System aktualisieren + Pakete installieren..."
apt-get update -qq
apt-get install -y \
    python3-pip python3-serial python3-minimalmodbus \
    python3-gps gpsd gpsd-clients \
    udev sqlite3 jq curl

# --- 2. udev-Regel fuer Waveshare-Adapter ----------------------------------
# Waveshare-Adapter haben typischerweise einen dieser USB-Chips:
#   CH340  : 1a86:7523
#   CH341  : 1a86:5523
#   CP2102 : 10c4:ea60
#   FT232  : 0403:6001
# Wir mappen ALLE bekannten Chips auf /dev/rayleigh, da pro Messkoffer
# normalerweise nur ein USB-Seriell-Adapter dran ist.
echo ""
echo "[2/8] udev-Regel fuer /dev/rayleigh anlegen..."
cat > /etc/udev/rules.d/99-rayleigh.rules << 'EOF'
# Aeltere Waveshare-Adapter (CH340/CH341 - ttyUSB)
SUBSYSTEM=="tty", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="7523", SYMLINK+="rayleigh", MODE="0660", GROUP="dialout"
SUBSYSTEM=="tty", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="5523", SYMLINK+="rayleigh", MODE="0660", GROUP="dialout"
# Neuere Waveshare-Adapter (CH343/CH9102 - ttyACM via cdc_acm)
SUBSYSTEM=="tty", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="55d3", SYMLINK+="rayleigh", MODE="0660", GROUP="dialout"
SUBSYSTEM=="tty", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="55d4", SYMLINK+="rayleigh", MODE="0660", GROUP="dialout"
# CP210x (Silicon Labs)
SUBSYSTEM=="tty", ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", SYMLINK+="rayleigh", MODE="0660", GROUP="dialout"
# FTDI FT232
SUBSYSTEM=="tty", ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6001", SYMLINK+="rayleigh", MODE="0660", GROUP="dialout"
EOF
udevadm control --reload-rules
udevadm trigger --subsystem-match=tty || true
echo "  /etc/udev/rules.d/99-rayleigh.rules angelegt"

# --- 3. gpsd konfigurieren --------------------------------------------------
echo ""
echo "[3/8] gpsd konfigurieren..."
# gpsd defaultet auf /dev/ttyACM0 (typisch fuer u-blox USB-GPS)
cat > /etc/default/gpsd << 'EOF'
# Messkoffer GPS - by setup_messkoffer.sh
START_DAEMON="true"
USBAUTO="true"
DEVICES="/dev/ttyACM0 /dev/ttyACM1 /dev/ttyUSB1"
GPSD_OPTIONS="-n -G"
EOF
systemctl enable gpsd 2>/dev/null || true
systemctl restart gpsd 2>/dev/null || true
echo "  gpsd aktiviert (sucht /dev/ttyACM0 etc.)"

# --- 4. Verzeichnisse anlegen ----------------------------------------------
echo ""
echo "[4/8] Verzeichnisse anlegen..."
mkdir -p /opt/messkoffer
mkdir -p /var/lib/messkoffer
chown "$REAL_USER:dialout" /var/lib/messkoffer
chmod 0775 /var/lib/messkoffer

# User in dialout-Gruppe (fuer Serial-Zugriff)
usermod -a -G dialout "$REAL_USER" 2>/dev/null || true

# --- 5. messkoffer_logger.py installieren ----------------------------------
echo ""
echo "[5/8] Logger-Skript installieren..."
if [ -f "$SCRIPT_DIR/messkoffer_logger.py" ]; then
    cp "$SCRIPT_DIR/messkoffer_logger.py" /opt/messkoffer/messkoffer_logger.py
    echo "  messkoffer_logger.py aus $SCRIPT_DIR"
elif [ -n "$API_URL" ]; then
    # Vom Portal nachladen, falls Setup-Skript ohne mitgeliefertes Skript verteilt
    echo "  Lade messkoffer_logger.py vom Portal: $API_URL"
    PORTAL_BASE="${API_URL%/api}"
    curl -fsSL "$API_URL/system/ota/pi/messkoffer/download?pi_id=setup-bootstrap" \
        -o /opt/messkoffer/messkoffer_logger.py \
        || curl -fsSL "$PORTAL_BASE/static/messkoffer_logger.py" \
            -o /opt/messkoffer/messkoffer_logger.py
else
    echo "FEHLER: Weder lokale messkoffer_logger.py noch API_URL fuer Download."
    exit 1
fi
chmod +x /opt/messkoffer/messkoffer_logger.py

# --- 6. Konfiguration -------------------------------------------------------
echo ""
echo "[6/8] /etc/messkoffer.conf schreiben..."
cat > /etc/messkoffer.conf << EOF
[messkoffer]
# Modbus / Rayleigh RI-F100-C
modbus_port = /dev/rayleigh
modbus_baudrate = 9600
modbus_slave_id = 1
modbus_parity = N
modbus_stopbits = 1

# Portal
api_url = ${API_URL}
device_key = ${DEVICE_KEY}
device_id = ${DEVICE_ID}
meter_id = ${METER_ID}

# Storage
db_path = /var/lib/messkoffer/messkoffer.sqlite
log_interval = 1
sync_interval = 1200
sync_batch_size = 2000
max_db_size_gb = 60
EOF
chmod 0640 /etc/messkoffer.conf
chown root:dialout /etc/messkoffer.conf
echo "  /etc/messkoffer.conf geschrieben"

# --- 7. systemd-Service -----------------------------------------------------
echo ""
echo "[7/8] systemd-Service installieren..."
cat > /etc/systemd/system/messkoffer.service << EOF
[Unit]
Description=Messkoffer Logger (Rayleigh RI-F100-C + GPS) - Eventenergie
After=network-online.target gpsd.service
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/messkoffer
ExecStart=/usr/bin/python3 /opt/messkoffer/messkoffer_logger.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable messkoffer.service
systemctl restart messkoffer.service
echo "  messkoffer.service aktiviert und gestartet"

# --- 8. Status & naechste Schritte -----------------------------------------
echo ""
echo "[8/8] Status pruefen..."
sleep 3
systemctl --no-pager status messkoffer.service | head -15 || true
echo ""
echo "=============================================="
echo "  Setup abgeschlossen!"
echo "=============================================="
echo ""
echo "  Logs live anschauen:  sudo journalctl -u messkoffer -f"
echo "  Status:               systemctl status messkoffer"
echo "  Neustart:             sudo systemctl restart messkoffer"
echo "  Konfig:               sudo nano /etc/messkoffer.conf"
echo ""
echo "  Modbus-Test (ohne Service):"
echo "    sudo systemctl stop messkoffer"
echo "    sudo python3 -c \""
echo "      import minimalmodbus, serial"
echo "      i = minimalmodbus.Instrument('/dev/rayleigh', 1)"
echo "      i.serial.baudrate = 9600"
echo "      i.serial.timeout = 1"
echo "      print('U_L1 raw:', i.read_registers(1, 2, 3))"
echo "    \""
echo "    sudo systemctl start messkoffer"
echo ""
if [ -z "$API_URL" ] || [ -z "$DEVICE_KEY" ]; then
    echo "  HINWEIS: API_URL/DEVICE_KEY noch nicht gesetzt."
    echo "  Bitte /etc/messkoffer.conf manuell vervollstaendigen und neustarten."
fi
echo ""
echo "  Reboot empfohlen damit dialout-Gruppe greift:  sudo reboot"
echo "=============================================="
