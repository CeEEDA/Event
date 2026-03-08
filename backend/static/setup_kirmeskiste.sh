#!/bin/bash
# ==============================================================
#  Kirmeskiste Setup - Eventenergie Portal
#  Automatisches Setup fuer Raspberry Pi mit 4x EMU Pro II 3/5
# ==============================================================
set -e

echo "========================================================"
echo "  Kirmeskiste Setup - Eventenergie Portal"
echo "  4x EMU Professional II 3/5 via Modbus TCP"
echo "========================================================"
echo ""

# ----- Abfrage der Konfiguration -----

read -p "Portal-URL (z.B. https://portal.eventenergie-deutschland.de/api): " API_URL
read -p "Device-ID (aus dem Portal): " DEVICE_ID
read -p "Device-Key (aus dem Portal): " DEVICE_KEY

echo ""
echo "Zaehler-Konfiguration (4x EMU Professional II):"
echo "Standardmaessig: 192.168.1.101-104, Port 502"
echo ""

METER_IDS=()
METER_IPS=()
for i in 1 2 3 4; do
    DEFAULT_IP="192.168.1.$((100+i))"
    read -p "Zaehler $i - IP [$DEFAULT_IP]: " IP
    IP=${IP:-$DEFAULT_IP}
    read -p "Zaehler $i - Meter-ID (aus dem Portal): " MID
    METER_IDS+=("$MID")
    METER_IPS+=("$IP")
done

# ----- System aktualisieren -----

echo ""
echo "[1/5] System aktualisieren..."
sudo apt-get update -qq
sudo apt-get install -y -qq python3-pip python3-venv

# ----- Python-Umgebung -----

echo "[2/5] Python-Umgebung einrichten..."
INSTALL_DIR="/opt/kirmeskiste"
sudo mkdir -p "$INSTALL_DIR"
sudo python3 -m venv "$INSTALL_DIR/venv"
sudo "$INSTALL_DIR/venv/bin/pip" install --quiet pymodbus requests

# ----- Skript kopieren -----

echo "[3/5] Sync-Skript installieren..."
SCRIPT_URL="${API_URL%/api}/static/kirmeskiste_sync.py"
sudo curl -sL -o "$INSTALL_DIR/kirmeskiste_sync.py" "$SCRIPT_URL" || {
    echo "Download fehlgeschlagen. Kopiere lokale Datei..."
    sudo cp "$(dirname "$0")/kirmeskiste_sync.py" "$INSTALL_DIR/kirmeskiste_sync.py"
}
sudo chmod +x "$INSTALL_DIR/kirmeskiste_sync.py"

# ----- Konfiguration -----

echo "[4/5] Konfiguration schreiben..."
sudo mkdir -p /var/lib/kirmeskiste

sudo tee /etc/kirmeskiste.conf > /dev/null << CONF
[kirmeskiste]
api_url = ${API_URL}
device_key = ${DEVICE_KEY}
device_id = ${DEVICE_ID}
db_path = /var/lib/kirmeskiste/kirmeskiste.sqlite
read_interval = 10
sync_interval = 30
retry_delay = 30
batch_size = 500

[meter_1]
meter_id = ${METER_IDS[0]}
ip = ${METER_IPS[0]}
port = 502
slave_id = 1
name = Zaehler 1

[meter_2]
meter_id = ${METER_IDS[1]}
ip = ${METER_IPS[1]}
port = 502
slave_id = 1
name = Zaehler 2

[meter_3]
meter_id = ${METER_IDS[2]}
ip = ${METER_IPS[2]}
port = 502
slave_id = 1
name = Zaehler 3

[meter_4]
meter_id = ${METER_IDS[3]}
ip = ${METER_IPS[3]}
port = 502
slave_id = 1
name = Zaehler 4
CONF

sudo chmod 600 /etc/kirmeskiste.conf

# ----- Systemd Service -----

echo "[5/5] Systemd-Service einrichten..."
sudo tee /etc/systemd/system/kirmeskiste_sync.service > /dev/null << SERVICE
[Unit]
Description=Kirmeskiste Sync - Eventenergie Portal
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=${INSTALL_DIR}/venv/bin/python3 ${INSTALL_DIR}/kirmeskiste_sync.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
WorkingDirectory=${INSTALL_DIR}

[Install]
WantedBy=multi-user.target
SERVICE

sudo systemctl daemon-reload
sudo systemctl enable kirmeskiste_sync
sudo systemctl start kirmeskiste_sync

echo ""
echo "========================================================"
echo "  Setup abgeschlossen!"
echo "========================================================"
echo ""
echo "  Konfiguration: /etc/kirmeskiste.conf"
echo "  Datenbank:     /var/lib/kirmeskiste/kirmeskiste.sqlite"
echo "  Skript:        ${INSTALL_DIR}/kirmeskiste_sync.py"
echo ""
echo "  Service pruefen:"
echo "    sudo systemctl status kirmeskiste_sync"
echo "    sudo journalctl -u kirmeskiste_sync -f"
echo ""
echo "  Zaehler-IPs:"
for i in 0 1 2 3; do
    echo "    Zaehler $((i+1)): ${METER_IPS[$i]} -> ${METER_IDS[$i]}"
done
echo ""
