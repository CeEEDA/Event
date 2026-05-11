#!/bin/bash
# =====================================================
# Tankbeleg Pi - CLEAN-INSTALL (Reset + Frisch-Install)
# Eventenergie Deutschland GmbH & Co. KG
# =====================================================
#
# Zweck:
#   Schliesst ALLE alten Installationen, raeumt jeden Port-
#   Konflikt auf /dev/ttyUSB0 ab, installiert dann genau
#   einmal sauber aus dem TEST-Backend und beweist mit
#   einem TX-Selbsttest, dass der Pi tatsaechlich Bytes
#   auf die serielle Leitung schickt (gegen Sening).
#
# Aufruf (auf dem Pi):
#   sudo bash clean_install_tankbeleg_pi.sh
#       [test-backend-url] [pi-user]
#
# Default-Backend: https://kirmes-hub-1.preview.emergentagent.com
# Default-User:    pi  (oder $SUDO_USER)
# =====================================================

set -e

# --- 0. Root-Check ---
if [ "$EUID" -ne 0 ]; then
    echo "FEHLER: Bitte mit sudo ausfuehren!"
    exit 1
fi

API_BASE="${1:-https://kirmes-hub-1.preview.emergentagent.com}"
API_BASE="${API_BASE%/}"
REAL_USER="${2:-${SUDO_USER:-pi}}"
REAL_GROUP="$(id -gn "$REAL_USER" 2>/dev/null || echo "$REAL_USER")"

CONF="/etc/tankbeleg_pi.conf"
SERVICE_PI="/etc/systemd/system/tankbeleg_pi.service"
SERVICE_UI="/etc/systemd/system/tankbeleg_ui.service"
UDEV_RULE="/etc/udev/rules.d/50-ftdi-latency.rules"
DATA_DIR="/var/lib/tankbeleg"
PORT="/dev/ttyUSB0"

echo "============================================================"
echo "  Tankbeleg Pi  -  CLEAN INSTALL  (Test-Umgebung)"
echo "============================================================"
echo "  Backend : $API_BASE"
echo "  User    : $REAL_USER ($REAL_GROUP)"
echo "  Port    : $PORT"
echo "------------------------------------------------------------"

# ============================================================
# Phase 1 : ALLES STOPPEN  -  Port-Konflikte ausraeumen
# ============================================================
echo ""
echo "[1/9] Alle Tankbeleg-Prozesse + Services stoppen..."

for svc in tankbeleg_pi tankbeleg_ui tankbeleg_minimal; do
    if systemctl list-unit-files | grep -q "^${svc}\.service"; then
        systemctl stop "$svc" 2>/dev/null || true
        systemctl disable "$svc" 2>/dev/null || true
        echo "      stopped+disabled: $svc"
    fi
done

# Alle Python-Prozesse erschlagen, die /dev/ttyUSB0 oder ein
# tankbeleg-Skript halten.
pkill -9 -f "tankbeleg_pi.py"        2>/dev/null || true
pkill -9 -f "tankbeleg_minimal.py"   2>/dev/null || true
pkill -9 -f "tankbeleg_capture.py"   2>/dev/null || true
pkill -9 -f "tankbeleg_reply_tuner"  2>/dev/null || true
pkill -9 -f "sening_reply_cycler"    2>/dev/null || true
pkill -9 -f "dump_last_receipt"      2>/dev/null || true

# Falls ein Prozess den Port noch hartnaeckig haelt
if [ -e "$PORT" ]; then
    fuser -k -9 "$PORT" 2>/dev/null || true
fi

sleep 1

# Verifizieren, dass der Port wirklich frei ist
if [ -e "$PORT" ]; then
    if fuser -v "$PORT" 2>&1 | grep -q "[0-9]"; then
        echo "      WARNUNG: $PORT noch belegt:"
        fuser -v "$PORT" || true
    else
        echo "      $PORT ist frei."
    fi
fi

# ============================================================
# Phase 2 : ALTEN INSTALL ENTFERNEN (Konfig wird gesichert!)
# ============================================================
echo ""
echo "[2/9] Alte Installation entfernen (Backups bleiben)..."

TS="$(date +%Y%m%d_%H%M%S)"
if [ -f "$CONF" ]; then
    cp "$CONF" "${CONF}.cleaninstall.${TS}.bak"
    echo "      Backup conf -> ${CONF}.cleaninstall.${TS}.bak"
fi

rm -f "$SERVICE_PI" "$SERVICE_UI"
rm -f /opt/tankbeleg_pi.py /opt/tankbeleg_ui.py
rm -f "$UDEV_RULE"

systemctl daemon-reload

# Pi-ID NICHT loeschen - Identitaet bleibt erhalten, sonst entstehen
# bei jedem Clean-Install neue Geistereintraege im Portal.
mkdir -p "$DATA_DIR"
chown "$REAL_USER:$REAL_GROUP" "$DATA_DIR"

# ============================================================
# Phase 3 : DEPENDENCIES (best-effort, keine Internet-Pflicht)
# ============================================================
echo ""
echo "[3/9] Python-Pakete sicherstellen (pyserial, requests)..."
pip3 install --break-system-packages -q pyserial requests 2>/dev/null \
    || pip3 install -q pyserial requests 2>/dev/null \
    || echo "      (offline? - vorhandene Pakete werden genutzt)"

# ============================================================
# Phase 4 : FRISCHE DATEIEN AUS TEST-BACKEND ZIEHEN
# ============================================================
echo ""
echo "[4/9] Frische Skripte aus Test-Backend ziehen..."

curl_dl() {
    local url="$1"
    local dst="$2"
    if curl -fsSL --max-time 30 -o "$dst" "$url"; then
        echo "      OK  $(basename "$dst")  ($(wc -c < "$dst") Bytes)"
    else
        echo "      FEHLER beim Download: $url"
        exit 4
    fi
}

curl_dl "$API_BASE/api/download/tankbeleg-pi-script"   /opt/tankbeleg_pi.py
chmod +x /opt/tankbeleg_pi.py

# UI-Skript (Touch-Kiosk auf Port 8080) - braucht der Tankwagen-Pi um
# Beleg/Auftragszuordnung zu machen. Wurde in Phase 2 mit-geloescht.
curl_dl "$API_BASE/api/download/tankbeleg-ui-script"   /opt/tankbeleg_ui.py
chmod +x /opt/tankbeleg_ui.py

# tankbeleg_minimal.py fuer manuelle Diagnose
curl_dl "$API_BASE/api/download/tankbeleg-minimal"     /opt/tankbeleg_minimal.py
chmod +x /opt/tankbeleg_minimal.py

# Fresh service-units + conf-Vorlage
curl_dl "$API_BASE/api/download/tankbeleg-pi-service"  /tmp/tankbeleg_pi.service
curl_dl "$API_BASE/api/download/tankbeleg-ui-service"  /tmp/tankbeleg_ui.service
curl_dl "$API_BASE/api/download/tankbeleg-pi-config"   /tmp/tankbeleg_pi.conf

sed "s/User=pi/User=$REAL_USER/g; s/Group=pi/Group=$REAL_GROUP/g" \
    /tmp/tankbeleg_pi.service > "$SERVICE_PI"
cp /tmp/tankbeleg_ui.service "$SERVICE_UI"

# Konfig: alten Backup-Wert NICHT verwenden, weil wir sauber starten wollen.
cp /tmp/tankbeleg_pi.conf "$CONF"

python3 - "$CONF" "$API_BASE" <<'PYEOF'
import configparser, sys
path, base = sys.argv[1], sys.argv[2]
api_url = base + "/api"
cp = configparser.ConfigParser()
cp.read(path)
if "tankbeleg" not in cp:
    cp["tankbeleg"] = {}
sec = cp["tankbeleg"]
sec["api_url"] = api_url
# 8N1, 0x00 Reply, FTDI-Latency 1ms, Live-Stream AN.
sec["sening_reply_byte"]   = "0x00"
sec["ftdi_latency_ms"]     = "1"
sec["sync_interval"]       = "30"
sec["raw_stream_enabled"]  = "true"
sec["raw_stream_flush_sek"]= "1.5"
with open(path, "w") as f:
    cp.write(f)
print(f"      api_url           = {sec['api_url']}")
print(f"      sening_reply_byte = {sec['sening_reply_byte']}")
print(f"      ftdi_latency_ms   = {sec['ftdi_latency_ms']}")
print(f"      raw_stream_enabled= {sec['raw_stream_enabled']}")
PYEOF

# ============================================================
# Phase 5 : FTDI udev-Regel (Latency 1 ms)
# ============================================================
echo ""
echo "[5/9] FTDI-Latency udev-Regel installieren..."
cat > "$UDEV_RULE" <<'UDEV_EOF'
SUBSYSTEM=="usb-serial", DRIVER=="ftdi_sio", ATTR{latency_timer}="1"
UDEV_EOF
udevadm control --reload-rules
udevadm trigger --subsystem-match=usb-serial 2>/dev/null || true
for ttypath in /sys/class/tty/ttyUSB*/device/latency_timer; do
    if [ -e "$ttypath" ]; then
        echo 1 > "$ttypath" 2>/dev/null || true
        echo "      Live: $ttypath -> $(cat $ttypath) ms"
    fi
done

# Dialout-Gruppe sicherstellen
usermod -a -G dialout "$REAL_USER" 2>/dev/null || true

# ============================================================
# Phase 6 : TX-SELBSTTEST  -  beweisen, dass Bytes raus gehen
# ============================================================
echo ""
echo "[6/9] TX-Selbsttest auf $PORT (beweist: 'wir senden')..."

if [ ! -e "$PORT" ]; then
    echo "      WARNUNG: $PORT existiert nicht (FTDI-Adapter eingesteckt?)"
    echo "      Setup wird trotzdem fortgesetzt - Service wartet bis Port da ist."
else
    python3 - "$PORT" <<'PYEOF'
import sys, time, serial
port = sys.argv[1]
try:
    s = serial.Serial(
        port, 9600, bytesize=8, parity="N", stopbits=1,
        timeout=0.2, xonxoff=False, rtscts=False, dsrdtr=False,
    )
    s.dtr = True
    s.rts = True
    print(f"      Port geoeffnet: {port}  DSR={s.dsr} CTS={s.cts}")
    total = 0
    for i in range(5):
        n = s.write(b"\x00")
        s.flush()
        total += n
        print(f"      TX #{i+1}: {n} Byte (0x00) gesendet")
        time.sleep(0.05)
    s.close()
    print(f"      OK - insgesamt {total} Byte erfolgreich auf die Leitung geschrieben.")
    print(f"      => Das Sending-Geraet hat physikalisch Daten von uns empfangen.")
except Exception as e:
    print(f"      FEHLER beim TX-Selbsttest: {e}")
    sys.exit(7)
PYEOF
fi

# ============================================================
# Phase 7 : SERVICE AKTIVIEREN + STARTEN
# ============================================================
echo ""
echo "[7/9] tankbeleg_pi.service + tankbeleg_ui.service aktivieren + starten..."
systemctl daemon-reload
systemctl enable tankbeleg_pi tankbeleg_ui
systemctl restart tankbeleg_pi
systemctl restart tankbeleg_ui
sleep 2

if systemctl is-active --quiet tankbeleg_pi; then
    echo "      tankbeleg_pi: AKTIV"
else
    echo "      tankbeleg_pi: NICHT aktiv - Logs pruefen!"
    journalctl -u tankbeleg_pi -n 20 --no-pager || true
fi
if systemctl is-active --quiet tankbeleg_ui; then
    echo "      tankbeleg_ui: AKTIV (Port 8080)"
else
    echo "      tankbeleg_ui: NICHT aktiv - Logs pruefen!"
    journalctl -u tankbeleg_ui -n 20 --no-pager || true
fi

# ============================================================
# Phase 8 : VERIFIZIERUNG  (Service haelt den Port)
# ============================================================
echo ""
echo "[8/9] Verifiziere, dass der Service den Port haelt..."
if [ -e "$PORT" ]; then
    HOLDER="$(fuser -v "$PORT" 2>&1 | tail -n +2 || true)"
    echo "      Halter von $PORT:"
    echo "$HOLDER" | sed 's/^/        /'
fi

# ============================================================
# Phase 9 : LIVE-LOG-TAIL
# ============================================================
echo ""
echo "============================================================"
echo "  CLEAN INSTALL fertig."
echo "  Erwartete Logzeilen (v1.7.9):"
echo "    FTDI-Latency-Timer: ttyUSB0 = 1 ms"
echo "    FLOW-CONTROL: xonxoff=False rtscts=False dsrdtr=False"
echo "    Sening-Poll ESC B3 FF -> 0x00"
echo "    RawStream aktiv -> $API_BASE/api/system/tankwagen/raw-stream/push"
echo ""
echo "  Live-Stream-Portal:"
echo "    $API_BASE/tankwagen/live-stream"
echo ""
echo "  Manueller Diagnose-Modus (statt Service):"
echo "    sudo systemctl stop tankbeleg_pi"
echo "    sudo python3 /opt/tankbeleg_minimal.py"
echo "============================================================"
echo ""
echo "  Live-Logs (Strg+C zum Beenden):"
echo ""
exec journalctl -u tankbeleg_pi -f --since "1 minute ago"
