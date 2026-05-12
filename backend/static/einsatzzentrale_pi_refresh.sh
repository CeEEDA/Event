#!/usr/bin/env bash
# Pi-Refresh-Skript: holt aktuelle pi_service.py + kiosk.html von der Cloud,
# loescht stale Caches (SQLite + Chromium) und startet den Service neu.
# Behaelt Pi-ID + Pi-Key + Konfig.
#
# Aufruf auf dem Pi:
#   sudo curl -fsSL "$CLOUD/api/einsatzzentrale/refresh-pi" | sudo bash
#
set -e

# CLOUD_URL aus bestehender Konfig holen (Pi-Service-Konfig vom Setup)
CONF="/etc/einsatzzentrale-pi.conf"
if [[ -f "$CONF" ]]; then
  CLOUD=$(grep '^CLOUD_URL=' "$CONF" | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'")
fi
CLOUD="${CLOUD:-https://bestand-copy.preview.emergentagent.com}"

# Kiosk-User-Profile finden (Default: admin)
KIOSK_USER="${KIOSK_USER:-admin}"
if ! id -u "$KIOSK_USER" >/dev/null 2>&1; then
  # Erstbenutzer ausser root
  KIOSK_USER=$(getent passwd 1000 | cut -d: -f1)
fi
KIOSK_HOME=$(getent passwd "$KIOSK_USER" | cut -d: -f6)
PROFILE="$KIOSK_HOME/.config/einsatzzentrale-chromium"
SERVICE_DIR="/usr/local/lib/einsatzzentrale-pi"

echo "Cloud-URL:   $CLOUD"
echo "Kiosk-User:  $KIOSK_USER (Home: $KIOSK_HOME)"
echo ""

echo "[1/8] Stoppe Pi-Service + Chromium..."
systemctl stop einsatzzentrale-pi 2>/dev/null || true
pkill -9 -f chromium 2>/dev/null || true
sleep 2

echo "[2/8] Pruefe Emoji-Font (fonts-noto-color-emoji)..."
if ! dpkg -l fonts-noto-color-emoji 2>/dev/null | grep -q "^ii"; then
  echo "  -> nicht installiert, hole ihn nach (sonst leere Kaestchen statt Wetter-Icons)"
  apt-get install -y --no-install-recommends fonts-noto-color-emoji 2>/dev/null || true
  fc-cache -f 2>/dev/null || true
else
  echo "  -> bereits installiert"
fi

echo "[3/8] Aktualisiere CLOUD_URL in $CONF..."
if [[ -f "$CONF" ]]; then
  sed -i "s|^CLOUD_URL=.*|CLOUD_URL=$CLOUD|" "$CONF"
  grep -q "^CLOUD_URL=" "$CONF" || echo "CLOUD_URL=$CLOUD" >> "$CONF"
else
  echo "CLOUD_URL=$CLOUD" > "$CONF"
fi

echo "[4/8] Lade frischen pi_service.py..."
mkdir -p "$SERVICE_DIR"
curl -fsSL "$CLOUD/api/einsatzzentrale/pi-service.py" -o "$SERVICE_DIR/pi_service.py.new"
if [[ -s "$SERVICE_DIR/pi_service.py.new" ]]; then
  mv "$SERVICE_DIR/pi_service.py.new" "$SERVICE_DIR/pi_service.py"
else
  echo "  WARN: Pi-Service Download leer - alte Version bleibt aktiv."
  rm -f "$SERVICE_DIR/pi_service.py.new"
fi

echo "[5/8] Lade frische kiosk.html (Offline-Fallback)..."
curl -fsSL "$CLOUD/api/einsatzzentrale/kiosk-page" -o "$SERVICE_DIR/kiosk.html.new"
if [[ -s "$SERVICE_DIR/kiosk.html.new" ]]; then
  mv "$SERVICE_DIR/kiosk.html.new" "$SERVICE_DIR/kiosk.html"
else
  rm -f "$SERVICE_DIR/kiosk.html.new"
fi

echo "[6/8] Loesche Pi-Service SQLite-Cache..."
rm -f /var/lib/einsatzzentrale-pi/cache.db*

echo "[7/8] Loesche Chromium-Caches..."
rm -rf "$PROFILE/Default/Cache"             2>/dev/null || true
rm -rf "$PROFILE/Default/Code Cache"        2>/dev/null || true
rm -rf "$PROFILE/Default/Service Worker"    2>/dev/null || true
rm -rf "$PROFILE/Default/GPUCache"          2>/dev/null || true
rm -rf "$PROFILE/Default/Application Cache" 2>/dev/null || true
rm -rf "$PROFILE/ShaderCache"               2>/dev/null || true
rm -rf "$PROFILE/GrShaderCache"             2>/dev/null || true

echo "[8/8] Starte Pi-Service neu..."
systemctl start einsatzzentrale-pi
sleep 2

echo ""
echo "================================"
echo "Pi-Service Status:"
curl -s http://localhost:8001/pi-status 2>/dev/null || echo "  (Service noch nicht ready)"
echo ""
echo ""
KIOSK_HTTP=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/kiosk || echo "0")
echo "Kiosk-Page lokal:  HTTP $KIOSK_HTTP"
echo "================================"
echo "Fertig. Chromium kommt per Launcher-Loop automatisch hoch (~5 Sek)."
echo "Bleibt der Bildschirm schwarz: 'sudo systemctl restart lightdm' oder 'sudo reboot'."
