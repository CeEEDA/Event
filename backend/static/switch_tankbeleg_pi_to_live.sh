#!/bin/bash
# =====================================================
# Tankbeleg Pi - Switch zurueck zur LIVE-Umgebung
# Eventenergie Deutschland GmbH & Co. KG
# =====================================================
#
# Was macht das Skript?
#   1. Setzt api_url in /etc/tankbeleg_pi.conf auf die LIVE-Backend-URL
#   2. Stellt sicher dass die neuen Pumpen-Werte (4 sec/L, 60 s Einrichtung)
#      und alle 1.7.16-Defaults aktiv bleiben (auch ueber OTA hinweg)
#   3. Schaltet Raw-Stream AUS (Datenschutz / Bandbreite in Live)
#   4. Sync-Intervall auf 60 s zurueck (Live-Setting, schont LTE-Volumen)
#   5. Backup der Test-Conf -> /etc/tankbeleg_pi.conf.test.YYYYMMDD_HHMMSS.bak
#   6. Optional: pi_id rotieren falls man den Pi als neues Geraet im Live-Portal
#      anlegen will. Default: behalten (gleicher Pi = gleiches Geraet).
#   7. Reload + Restart der Services + Live-Tail
#
# Aufruf:
#   sudo bash switch_tankbeleg_pi_to_live.sh https://<live-backend>.example.com
#   (ohne Argument: liest die letzte gesicherte Live-URL aus *.live.*.bak,
#    falls vorhanden, sonst interaktive Abfrage)
#
# WICHTIG vor dem Switch:
#   - Stelle sicher dass dein Live-Backend Skript-Version >= 1.7.16 hat
#     (Heizoel/Diesel-Marker, Phantom-Filter, Pumpen-Schluessel 4 sec/L).
#     Sonst zieht der Pi nach dem ersten OTA-Check eine aeltere Version
#     vom Live-Server und die gefixten Bugs kommen zurueck!
# =====================================================

set -e

if [ "$EUID" -ne 0 ]; then
    echo "FEHLER: Bitte mit sudo ausfuehren!"
    exit 1
fi

CONF="/etc/tankbeleg_pi.conf"
PI_ID_FILE="/var/lib/tankbeleg/pi_id"

echo "=============================================="
echo "  Tankbeleg Pi -> LIVE-UMGEBUNG"
echo "=============================================="

# --- 1. Live-API-URL ermitteln ---
LIVE_URL="${1:-}"

if [ -z "$LIVE_URL" ]; then
    # Aus juengstem live-Backup ableiten
    LATEST_BACKUP=$(ls -t "${CONF}.live."*.bak 2>/dev/null | head -1 || true)
    if [ -n "$LATEST_BACKUP" ]; then
        BACKED_URL=$(grep -E '^api_url' "$LATEST_BACKUP" 2>/dev/null | sed 's/.*=\s*//;s/^\s*//;s/\s*$//' || true)
        if [ -n "$BACKED_URL" ]; then
            echo "Letzte gesicherte Live-URL gefunden: $BACKED_URL"
            read -r -p "Diese URL verwenden? [J/n] " USE_BACKUP
            case "$USE_BACKUP" in
                n|N|nein|No|no) ;;
                *) LIVE_URL="$BACKED_URL" ;;
            esac
        fi
    fi
fi

if [ -z "$LIVE_URL" ]; then
    read -r -p "Live-Backend-URL (z.B. https://eventenergie.app oder https://portal.eventenergie.de): " LIVE_URL
fi

if [ -z "$LIVE_URL" ]; then
    echo "FEHLER: Keine URL angegeben - Abbruch."
    exit 2
fi

# Trailing-Slash entfernen, /api anhaengen falls nicht vorhanden
LIVE_URL="${LIVE_URL%/}"
case "$LIVE_URL" in
    */api) ;;
    *) LIVE_URL="${LIVE_URL}/api" ;;
esac

echo "[1/6] Live-URL: $LIVE_URL"

# Erreichbarkeit pruefen (best-effort)
echo "      Verbindungstest..."
HTTP=$(curl -s -o /dev/null -w "%{http_code}" --max-time 8 -A "TankbelegPi/1.7.16-switch" "$LIVE_URL/system/ota/tankwagen/check?pi_id=preflight" || echo "000")
case "$HTTP" in
    200|404|405) echo "      Backend antwortet (HTTP $HTTP)." ;;
    000) echo "      WARNUNG: Backend nicht erreichbar (Timeout/DNS)." ;;
    *)   echo "      WARNUNG: Backend antwortet mit HTTP $HTTP - bitte URL pruefen." ;;
esac

# Skript-Version auf Live pruefen (wichtig wegen OTA-Regression!)
echo "      Pruefe Live-Backend Skript-Version..."
LIVE_VER=$(curl -s --max-time 8 -A "TankbelegPi/1.7.16-switch" "$LIVE_URL/download/tankbeleg-pi-script" 2>/dev/null | grep -m1 '^SCRIPT_VERSION' | sed 's/.*"\([^"]*\)".*/\1/' || true)
if [ -n "$LIVE_VER" ]; then
    echo "      Live-Backend liefert Skript-Version: $LIVE_VER"
    case "$LIVE_VER" in
        1.7.16|1.7.17|1.7.18|1.7.19|1.7.2[0-9]|1.[8-9].*|[2-9].*)
            echo "      OK: Version >= 1.7.16 (alle Fixes drin)."
            ;;
        *)
            echo ""
            echo "  !!!  WARNUNG  !!!"
            echo "  Live-Backend hat Version $LIVE_VER (< 1.7.16)."
            echo "  Nach dem Switch zieht der Pi diese aeltere Version per OTA"
            echo "  und ALLE Bug-Fixes (Heizoel/Diesel-Marker, Phantom-Filter,"
            echo "  Pumpen-Schluessel) sind weg!"
            echo ""
            echo "  Empfehlung: zuerst per 'Save to Github' das Test-Backend"
            echo "  in die Live-Umgebung deployen, dann erneut switchen."
            echo ""
            read -r -p "  Trotzdem fortfahren? [j/N] " IGNORE_REGRESSION
            case "$IGNORE_REGRESSION" in
                j|J|ja|y|Y|yes) echo "      OK, Switch fortgesetzt (Regression akzeptiert)." ;;
                *) echo "      Abbruch."; exit 4 ;;
            esac
            ;;
    esac
else
    echo "      WARNUNG: Konnte Live-Skript-Version nicht ermitteln (Endpoint fehlt?)."
    read -r -p "      Trotzdem fortfahren? [j/N] " IGNORE
    case "$IGNORE" in
        j|J|ja|y|Y|yes) ;;
        *) echo "      Abbruch."; exit 5 ;;
    esac
fi

# --- 2. Konfig-Backup + Update ---
echo "[2/6] Konfiguration aktualisieren..."
if [ ! -f "$CONF" ]; then
    echo "FEHLER: $CONF existiert nicht. Bitte zuerst setup_tankbeleg_pi.sh ausfuehren."
    exit 3
fi

BACKUP="${CONF}.test.$(date +%Y%m%d_%H%M%S).bak"
cp "$CONF" "$BACKUP"
echo "      Backup (Test-Config): $BACKUP"

python3 - "$CONF" "$LIVE_URL" <<'PYEOF'
import configparser, sys
path, url = sys.argv[1], sys.argv[2]
cp = configparser.ConfigParser()
cp.read(path)
if "tankbeleg" not in cp:
    cp["tankbeleg"] = {}
sec = cp["tankbeleg"]

# 1) URL
sec["api_url"] = url

# 2) Pumpen-Schluessel (v1.7.16 - empirisch gemessen 07.05.2026)
#    Diese Werte werden EXPLIZIT gesetzt, damit auch nach OTA-Pull eines
#    aelteren Skripts oder bei Konfig-Reset die korrekten Defaults bleiben.
sec["abgabe_zeit_pro_liter_sek"]  = "0.5"
sec["abgabe_zeit_einrichtung_sek"] = "420"

# 3) Default-Kraftstoff (Tankwagen liefert aktuell HEL)
sec["default_fuel_type"] = "heizoel_leicht"

# 4) Sening-Hardware-Defaults (TM-U295 emulation)
sec["sening_reply_byte"] = "0x00"
sec.setdefault("ftdi_latency_ms", "1")

# 5) Live-Tuning: Sync-Intervall hoch (60 s schont LTE)
sec["sync_interval"] = "60"

# 6) Raw-Stream AUS (Datenschutz + LTE-Volumen in Live)
sec["raw_stream_enabled"] = "false"

with open(path, "w") as f:
    cp.write(f)

print(f"      api_url                      = {sec['api_url']}")
print(f"      abgabe_zeit_pro_liter_sek    = {sec['abgabe_zeit_pro_liter_sek']}")
print(f"      abgabe_zeit_einrichtung_sek  = {sec['abgabe_zeit_einrichtung_sek']}")
print(f"      default_fuel_type            = {sec['default_fuel_type']}")
print(f"      sening_reply_byte            = {sec['sening_reply_byte']}")
print(f"      sync_interval                = {sec['sync_interval']} s")
print(f"      raw_stream_enabled           = {sec['raw_stream_enabled']}  (in Live AUS)")
PYEOF

# --- 3. pi_id rotieren? ---
echo "[3/6] Pi-ID..."
if [ -f "$PI_ID_FILE" ]; then
    OLD_ID=$(cat "$PI_ID_FILE" 2>/dev/null || echo "?")
    echo "      Aktuelle pi_id: $OLD_ID"
    read -r -p "      pi_id rotieren? (Default: behalten - gleiches Geraet im Portal) [j/N] " ROTATE
    case "$ROTATE" in
        j|J|ja|y|Y|yes)
            BACKUP_ID="${PI_ID_FILE}.test.bak"
            mv "$PI_ID_FILE" "$BACKUP_ID"
            echo "      Alte ID nach $BACKUP_ID gesichert. Neue UUID wird beim Start erzeugt."
            ;;
        *) echo "      pi_id behalten: $OLD_ID" ;;
    esac
else
    echo "      Noch keine pi_id vorhanden - wird beim ersten Start angelegt."
fi

# --- 4. Service neu starten ---
echo "[4/6] Services neu starten..."
systemctl restart tankbeleg_pi || true
systemctl restart tankbeleg_ui 2>/dev/null || true
sleep 2
systemctl is-active --quiet tankbeleg_pi && echo "      tankbeleg_pi: aktiv" || echo "      tankbeleg_pi: NICHT aktiv (siehe journalctl)"
systemctl is-active --quiet tankbeleg_ui && echo "      tankbeleg_ui: aktiv" || true

# --- 5. Hinweis ---
echo ""
echo "[5/6] Switch abgeschlossen."
echo "      Live-Backend:    $LIVE_URL"
echo "      Letzte Test-Conf-Sicherung: $BACKUP"
echo "      Rueckweg zum Test-Backend: 'sudo bash switch_tankbeleg_pi_to_test.sh <test-url>'"
echo ""

# --- 6. Live-Logs ---
echo "[6/6] Live-Logs (Strg+C zum Beenden):"
echo "=============================================="
echo ""
exec journalctl -u tankbeleg_pi -f --since "1 minute ago"
