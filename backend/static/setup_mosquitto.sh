#!/bin/bash
# =====================================================
# Mosquitto MQTT Broker - Setup mit Let's Encrypt
# Eventenergie Deutschland GmbH & Co. KG
# =====================================================
#
# Installiert und konfiguriert einen selbst-gehosteten
# Mosquitto MQTT Broker mit TLS-Verschluesselung.
#
# Voraussetzungen:
#   - Debian/Ubuntu Server
#   - Domain zeigt auf diesen Server (DNS A-Record)
#   - Port 80, 8883, 9883 muessen offen sein
#   - Root-Rechte
#
# Ausfuehren mit:
#   sudo bash setup_mosquitto.sh
#
# =====================================================

set -e

# ====== Farben ======
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=============================================="
echo "  Mosquitto MQTT Broker - Setup"
echo "  Eventenergie Deutschland"
echo -e "==============================================${NC}"
echo ""

# Root pruefen
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}FEHLER: Bitte mit sudo ausfuehren!${NC}"
    exit 1
fi

# ====== Parameter abfragen ======
echo -e "${YELLOW}Konfiguration:${NC}"
echo ""

# Domain
read -p "Domain fuer den MQTT Broker (z.B. mqtt.eventenergie.de): " DOMAIN
if [ -z "$DOMAIN" ]; then
    echo -e "${RED}FEHLER: Domain ist erforderlich!${NC}"
    exit 1
fi

# E-Mail fuer Let's Encrypt
read -p "E-Mail fuer Let's Encrypt Zertifikat: " LE_EMAIL
if [ -z "$LE_EMAIL" ]; then
    echo -e "${RED}FEHLER: E-Mail ist erforderlich!${NC}"
    exit 1
fi

# MQTT Benutzer
read -p "MQTT Benutzername fuer DSE Gateways [eventenergie]: " MQTT_USER
MQTT_USER=${MQTT_USER:-eventenergie}

# MQTT Passwort
read -s -p "MQTT Passwort fuer '$MQTT_USER': " MQTT_PASS
echo ""
if [ -z "$MQTT_PASS" ]; then
    echo -e "${RED}FEHLER: Passwort ist erforderlich!${NC}"
    exit 1
fi

# Zusaetzlichen Portal-Benutzer anlegen?
read -p "Zusaetzlichen Benutzer fuer Portal-Backend? (j/n) [j]: " CREATE_PORTAL_USER
CREATE_PORTAL_USER=${CREATE_PORTAL_USER:-j}
if [ "$CREATE_PORTAL_USER" = "j" ]; then
    read -p "Portal MQTT Benutzername [portal]: " PORTAL_USER
    PORTAL_USER=${PORTAL_USER:-portal}
    read -s -p "Portal MQTT Passwort: " PORTAL_PASS
    echo ""
fi

echo ""
echo -e "${GREEN}Zusammenfassung:${NC}"
echo "  Domain:        $DOMAIN"
echo "  E-Mail:        $LE_EMAIL"
echo "  MQTT User:     $MQTT_USER"
echo "  Portal User:   ${PORTAL_USER:-keiner}"
echo "  Ports:         8883 (MQTTS), 9883 (WSS), 1883 (lokal)"
echo ""
read -p "Weiter? (j/n) [j]: " CONFIRM
CONFIRM=${CONFIRM:-j}
if [ "$CONFIRM" != "j" ]; then
    echo "Abgebrochen."
    exit 0
fi

# ====== Installation ======

echo ""
echo -e "${GREEN}[1/7] System aktualisieren...${NC}"
apt-get update -qq
apt-get upgrade -y -qq

echo ""
echo -e "${GREEN}[2/7] Mosquitto installieren...${NC}"
apt-get install -y mosquitto mosquitto-clients

echo ""
echo -e "${GREEN}[3/7] Certbot installieren...${NC}"
apt-get install -y certbot

echo ""
echo -e "${GREEN}[4/7] Let's Encrypt Zertifikat anfordern...${NC}"
# Mosquitto/nginx stoppen falls auf Port 80
systemctl stop mosquitto 2>/dev/null || true
systemctl stop nginx 2>/dev/null || true
systemctl stop apache2 2>/dev/null || true

certbot certonly \
    --standalone \
    --non-interactive \
    --agree-tos \
    --email "$LE_EMAIL" \
    -d "$DOMAIN" \
    --preferred-challenges http

if [ ! -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
    echo -e "${RED}FEHLER: Zertifikat konnte nicht erstellt werden!${NC}"
    echo "Stellen Sie sicher, dass:"
    echo "  - Die Domain $DOMAIN auf diesen Server zeigt"
    echo "  - Port 80 offen und nicht belegt ist"
    exit 1
fi
echo -e "${GREEN}Zertifikat erstellt!${NC}"

# Mosquitto Zugriff auf Zertifikate
chmod 755 /etc/letsencrypt/live/
chmod 755 /etc/letsencrypt/archive/
chmod 644 /etc/letsencrypt/live/$DOMAIN/*.pem
chmod 644 /etc/letsencrypt/archive/$DOMAIN/*.pem

echo ""
echo -e "${GREEN}[5/7] Mosquitto konfigurieren...${NC}"

# Konfigurations-Datei kopieren und Domain ersetzen
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cp "$SCRIPT_DIR/mosquitto_eventenergie.conf" /etc/mosquitto/conf.d/eventenergie.conf
sed -i "s/DOMAIN/$DOMAIN/g" /etc/mosquitto/conf.d/eventenergie.conf

# Default Konfiguration anpassen (Standard-Listener deaktivieren)
if [ -f /etc/mosquitto/mosquitto.conf ]; then
    # Kommentiere den Standard-Listener aus
    sed -i 's/^listener/#listener/' /etc/mosquitto/mosquitto.conf
    sed -i 's/^allow_anonymous/#allow_anonymous/' /etc/mosquitto/mosquitto.conf
fi

echo ""
echo -e "${GREEN}[6/7] MQTT Benutzer anlegen...${NC}"

# Passwort-Datei erstellen
touch /etc/mosquitto/passwd

# Gateway-Benutzer
mosquitto_passwd -b /etc/mosquitto/passwd "$MQTT_USER" "$MQTT_PASS"
echo "  Benutzer '$MQTT_USER' angelegt"

# Portal-Benutzer
if [ "$CREATE_PORTAL_USER" = "j" ] && [ -n "$PORTAL_PASS" ]; then
    mosquitto_passwd -b /etc/mosquitto/passwd "$PORTAL_USER" "$PORTAL_PASS"
    echo "  Benutzer '$PORTAL_USER' angelegt"
fi

chmod 600 /etc/mosquitto/passwd

echo ""
echo -e "${GREEN}[7/7] Firewall und Service konfigurieren...${NC}"

# UFW Firewall (falls installiert)
if command -v ufw &> /dev/null; then
    ufw allow 8883/tcp comment "MQTTS"
    ufw allow 9883/tcp comment "MQTT WebSockets"
    echo "  UFW: Ports 8883 und 9883 geoeffnet"
fi

# Certbot Auto-Renewal Hook fuer Mosquitto
cat > /etc/letsencrypt/renewal-hooks/deploy/mosquitto-restart.sh << 'HOOK'
#!/bin/bash
# Mosquitto nach Zertifikatserneuerung neustarten
# Berechtigungen aktualisieren
chmod 644 /etc/letsencrypt/live/*/fullchain.pem
chmod 644 /etc/letsencrypt/live/*/privkey.pem
chmod 644 /etc/letsencrypt/live/*/chain.pem
# Neustart
systemctl restart mosquitto
HOOK
chmod +x /etc/letsencrypt/renewal-hooks/deploy/mosquitto-restart.sh

# Mosquitto starten
systemctl enable mosquitto
systemctl restart mosquitto

# Status pruefen
sleep 2
if systemctl is-active --quiet mosquitto; then
    echo -e "${GREEN}Mosquitto laeuft!${NC}"
else
    echo -e "${RED}FEHLER: Mosquitto konnte nicht gestartet werden!${NC}"
    echo "Logs pruefen: sudo journalctl -u mosquitto -n 50"
    exit 1
fi

# ====== Verbindungstest ======
echo ""
echo -e "${GREEN}Verbindungstest...${NC}"
# Lokaler Test (ohne TLS)
if mosquitto_pub -h 127.0.0.1 -p 1883 -t "test/setup" -m "Setup OK" 2>/dev/null; then
    echo -e "  ${GREEN}Lokal (1883): OK${NC}"
else
    echo -e "  ${YELLOW}Lokal (1883): Fehlgeschlagen (nicht kritisch)${NC}"
fi

# TLS Test
if mosquitto_pub -h "$DOMAIN" -p 8883 -u "$MQTT_USER" -P "$MQTT_PASS" \
    --cafile /etc/letsencrypt/live/$DOMAIN/chain.pem \
    -t "test/setup" -m "TLS Setup OK" 2>/dev/null; then
    echo -e "  ${GREEN}TLS (8883): OK${NC}"
else
    echo -e "  ${YELLOW}TLS (8883): Fehlgeschlagen - DNS/Firewall pruefen${NC}"
fi

# ====== Zusammenfassung ======
echo ""
echo -e "${GREEN}=============================================="
echo "  Setup abgeschlossen!"
echo -e "==============================================${NC}"
echo ""
echo "  Broker:       $DOMAIN"
echo "  MQTTS Port:   8883 (TLS)"
echo "  WSS Port:     9883 (WebSockets + TLS)"
echo "  Lokal Port:   1883 (nur 127.0.0.1)"
echo ""
echo -e "  ${YELLOW}DSE Webnet Gateway Konfiguration:${NC}"
echo "    Broker:     $DOMAIN"
echo "    Port:       8883"
echo "    TLS:        Aktiviert"
echo "    Username:   $MQTT_USER"
echo "    Passwort:   (wie oben eingegeben)"
echo ""
echo -e "  ${YELLOW}Portal MQTT Einstellungen:${NC}"
echo "    Broker URL: $DOMAIN"
if [ "$CREATE_PORTAL_USER" = "j" ]; then
    echo "    Port:       8883 (extern mit TLS)"
    echo "    Oder:       1883 (lokal ohne TLS)"
    echo "    Username:   $PORTAL_USER"
    echo "    Passwort:   (wie oben eingegeben)"
    echo "    TLS:        Ja (bei Port 8883)"
else
    echo "    Port:       1883 (lokal)"
    echo "    TLS:        Nein"
fi
echo ""
echo "  Befehle:"
echo "    Status:     sudo systemctl status mosquitto"
echo "    Logs:       sudo tail -f /var/log/mosquitto/mosquitto.log"
echo "    Neustart:   sudo systemctl restart mosquitto"
echo "    User hinz.: sudo mosquitto_passwd /etc/mosquitto/passwd NEUER_USER"
echo ""
echo "  Zertifikat wird automatisch erneuert (certbot timer)"
echo "  Naechste Erneuerung pruefen: sudo certbot renew --dry-run"
echo ""
