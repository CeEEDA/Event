#!/bin/bash
# =====================================================
# Tankbeleg Pi - Switch zu Test-Umgebung
# Eventenergie Deutschland GmbH & Co. KG
# =====================================================
#
# Was macht das Skript?
#   1. Setzt api_url in /etc/tankbeleg_pi.conf auf die Test-Backend-URL
#   2. Installiert udev-Regel fuer FTDI-Latency-Timer = 1 ms
#      (notwendig fuer v1.7.5 ohne root-Rechte zur Laufzeit)
#   3. Setzt 'sening_reply_byte' und 'ftdi_latency_ms' auf sinnvolle Defaults
#   4. Loescht die pi_id (optional) damit der Test-Pi im Portal neu erscheint
#      und nicht den Live-Pi-Eintrag ueberschreibt
#   5. Reload + Restart der Services
#   6. Live-Tail der Logs zur Sofort-Diagnose
#
# Aufruf:
#   sudo bash switch_tankbeleg_pi_to_test.sh https://<test-backend>.example.com
#   (ohne Argument fragt das Skript interaktiv)
# =====================================================

set -e

if [ "$EUID" -ne 0 ]; then
    echo "FEHLER: Bitte mit sudo ausfuehren!"
    exit 1
fi

CONF="/etc/tankbeleg_pi.conf"
UDEV_RULE="/etc/udev/rules.d/50-ftdi-latency.rules"
PI_ID_FILE="/var/lib/tankbeleg/pi_id"

echo "=============================================="
echo "  Tankbeleg Pi -> TEST-UMGEBUNG"
echo "=============================================="

# --- 1. Test-API-URL einlesen ---
TEST_URL="${1:-}"
if [ -z "$TEST_URL" ]; then
    read -r -p "Test-Backend-URL (z.B. https://test.eventenergie.app): " TEST_URL
fi

if [ -z "$TEST_URL" ]; then
    echo "FEHLER: Keine URL angegeben - Abbruch."
    exit 2
fi

# Trailing-Slash entfernen, /api anhaengen falls nicht vorhanden (tankbeleg_pi.py
# normalisiert das auch zur Laufzeit, aber wir wollen die conf sauber haben)
TEST_URL="${TEST_URL%/}"
case "$TEST_URL" in
    */api) ;;
    *) TEST_URL="${TEST_URL}/api" ;;
esac

echo "[1/6] Test-URL: $TEST_URL"

# Erreichbarkeit pruefen (best-effort, kein hard fail)
echo "      Verbindungstest..."
if curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$TEST_URL/system/ota/tankwagen/check?pi_id=preflight" | grep -qE "^(200|404|405)$"; then
    echo "      Backend antwortet."
else
    echo "      WARNUNG: Backend antwortet nicht oder unerwarteter Status."
    echo "      (Setup wird trotzdem fortgesetzt - Pi pollt bei naechstem sync_interval)"
fi

# --- 2. Konfig-Backup + Update ---
echo "[2/6] Konfiguration aktualisieren..."
if [ ! -f "$CONF" ]; then
    echo "FEHLER: $CONF existiert nicht. Bitte zuerst setup_tankbeleg_pi.sh ausfuehren."
    exit 3
fi

BACKUP="${CONF}.live.$(date +%Y%m%d_%H%M%S).bak"
cp "$CONF" "$BACKUP"
echo "      Backup: $BACKUP"

python3 - "$CONF" "$TEST_URL" <<'PYEOF'
import configparser, sys
path, url = sys.argv[1], sys.argv[2]
cp = configparser.ConfigParser()
cp.read(path)
if "tankbeleg" not in cp:
    cp["tankbeleg"] = {}
sec = cp["tankbeleg"]
sec["api_url"] = url
# Test-Defaults setzen.
# sening_reply_byte: SETZEN (nicht setdefault) - der TM-U295-spec-konforme
# Wert 0x12 (Bit1+4 fixed ON laut Spec). Vorher war hier 0x00, was die
# Spec-Invariante verletzt - bei Update auf v1.7.8 muessen Bestands-Pis
# auf 0x12 gehoben werden.
sec["sening_reply_byte"] = "0x12"
sec.setdefault("ftdi_latency_ms", "1")
sec.setdefault("sync_interval", "30")  # in Test schneller pollen
# Live-Raw-Stream einschalten - kann im Portal unter /tankwagen/live-stream
# beobachtet werden. In Live AUS lassen (Datenschutz/Bandbreite).
sec["raw_stream_enabled"] = "true"
sec.setdefault("raw_stream_flush_sek", "1.5")
with open(path, "w") as f:
    cp.write(f)
print(f"      api_url           = {sec['api_url']}")
print(f"      ftdi_latency_ms   = {sec['ftdi_latency_ms']}")
print(f"      sening_reply      = {sec['sening_reply_byte']}")
print(f"      sync_interval     = {sec['sync_interval']} s")
print(f"      raw_stream_enabled= {sec['raw_stream_enabled']}  (Live-Stream im Portal aktiv)")
PYEOF

# --- 3. udev-Regel fuer FTDI-Latency ---
echo "[3/6] udev-Regel fuer FTDI-Latency-Timer (1 ms)..."
cat > "$UDEV_RULE" <<'UDEV_EOF'
# Tankbeleg Pi v1.7.5 - FTDI USB-Serial Latency-Timer auf 1 ms.
# Verhindert 16-Byte UART-FIFO-Overrun bei langen Sening-Belegen
# (Symptom vor dem Fix: 1316 L wurde als 13 L empfangen).
SUBSYSTEM=="usb-serial", DRIVER=="ftdi_sio", ATTR{latency_timer}="1"
UDEV_EOF
udevadm control --reload-rules
udevadm trigger --subsystem-match=usb-serial 2>/dev/null || true
echo "      $UDEV_RULE installiert + reloaded"

# Sofort live anwenden falls FTDI bereits gesteckt
for ttypath in /sys/class/tty/ttyUSB*/device/latency_timer; do
    if [ -e "$ttypath" ]; then
        echo 1 > "$ttypath" 2>/dev/null && echo "      Live: $ttypath -> 1 ms" || true
    fi
done

# --- 4. pi_id rotieren (optional, default ja) ---
echo "[4/6] Pi-ID..."
if [ -f "$PI_ID_FILE" ]; then
    OLD_ID=$(cat "$PI_ID_FILE" 2>/dev/null || echo "?")
    read -r -p "      pi_id rotieren damit Test-Pi nicht den Live-Eintrag ueberschreibt? [J/n] " ROTATE
    case "$ROTATE" in
        n|N|nein|No|no) echo "      pi_id behalten: $OLD_ID" ;;
        *)
            BACKUP_ID="${PI_ID_FILE}.live.bak"
            mv "$PI_ID_FILE" "$BACKUP_ID"
            echo "      Alte ID nach $BACKUP_ID gesichert. Neue UUID wird beim Start erzeugt."
            ;;
    esac
else
    echo "      Noch keine pi_id vorhanden - wird beim ersten Start angelegt."
fi

# --- 5. Service neu starten (zwingt OTA-Pull der v1.7.5) ---
echo "[5/6] Services neu starten..."
systemctl restart tankbeleg_pi || true
systemctl restart tankbeleg_ui 2>/dev/null || true
sleep 2
systemctl is-active --quiet tankbeleg_pi && echo "      tankbeleg_pi: aktiv" || echo "      tankbeleg_pi: NICHT aktiv (siehe journalctl)"

# --- 6. Live-Logs ---
echo ""
echo "=============================================="
echo "  Erwartete Log-Zeilen (v1.7.6):"
echo "    FTDI-Latency-Timer: ... = 1 ms"
echo "    FLOW-CONTROL: xonxoff=False rtscts=False dsrdtr=True"
echo "    RawStream aktiv -> .../system/tankwagen/raw-stream/push"
echo "    Status-Query DLE EOT 4 -> 0x12  (oder)  Sening-Poll ESC B3 FF -> 0x00"
echo ""
echo "  Live-Stream im Portal:"
echo "    -> https://<test-portal>/tankwagen/live-stream"
echo "=============================================="
echo "  Live-Logs (Strg+C zum Beenden):"
echo ""

exec journalctl -u tankbeleg_pi -f --since "1 minute ago"
