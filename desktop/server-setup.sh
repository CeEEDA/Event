#!/bin/bash
# ============================================================================
#  Eventenergie Portal - Server-Installation (Ubuntu 22.04 / 24.04)
#  Ausfuehren als root:  bash server-setup.sh
# ============================================================================

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'
DOMAIN="eventenergie.app"
APP_DIR="/opt/eventenergie"
DATA_DIR="/opt/eventenergie/data"
DB_NAME="eventenergie"

echo ""
echo "================================================"
echo "  Eventenergie Portal - Server Setup"
echo "================================================"
echo ""

# Pruefen ob root
if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}Bitte als root ausfuehren: sudo bash server-setup.sh${NC}"
  exit 1
fi

# ── 1. System aktualisieren ─────────────────────────────────────────────────
echo -e "${YELLOW}[1/9]${NC} System aktualisieren..."
apt update -qq && apt upgrade -y -qq
echo -e "${GREEN}  ✓${NC} System aktuell"

# ── 2. Grundlegende Pakete ──────────────────────────────────────────────────
echo -e "${YELLOW}[2/9]${NC} Grundpakete installieren..."
apt install -y -qq \
  curl wget git build-essential software-properties-common \
  supervisor certbot ufw \
  poppler-utils \
  python3 python3-pip python3-venv \
  2>/dev/null
echo -e "${GREEN}  ✓${NC} Grundpakete installiert"

# ── 3. Node.js 20 LTS ──────────────────────────────────────────────────────
echo -e "${YELLOW}[3/9]${NC} Node.js 20 LTS installieren..."
if ! command -v node &> /dev/null; then
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  apt install -y -qq nodejs
  npm install -g yarn
fi
echo -e "${GREEN}  ✓${NC} Node.js $(node --version), Yarn $(yarn --version)"

# ── 4. MongoDB 7 ────────────────────────────────────────────────────────────
echo -e "${YELLOW}[4/9]${NC} MongoDB 7 installieren..."
if ! command -v mongod &> /dev/null; then
  curl -fsSL https://www.mongodb.org/static/pgp/server-7.0.asc | \
    gpg -o /usr/share/keyrings/mongodb-server-7.0.gpg --dearmor
  echo "deb [ signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | \
    tee /etc/apt/sources.list.d/mongodb-org-7.0.list
  apt update -qq
  apt install -y -qq mongodb-org
  systemctl enable mongod
  systemctl start mongod
fi
echo -e "${GREEN}  ✓${NC} MongoDB $(mongod --version | head -1)"

# ── 5. Caddy (Reverse Proxy + Auto-HTTPS) ──────────────────────────────────
echo -e "${YELLOW}[5/9]${NC} Caddy installieren..."
if ! command -v caddy &> /dev/null; then
  apt install -y -qq debian-keyring debian-archive-keyring apt-transport-https
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | \
    gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | \
    tee /etc/apt/sources.list.d/caddy-stable.list
  apt update -qq
  apt install -y -qq caddy
fi
echo -e "${GREEN}  ✓${NC} Caddy $(caddy version 2>/dev/null || echo 'installiert')"

# ── 6. Mosquitto (MQTT Broker fuer IoT) ────────────────────────────────────
echo -e "${YELLOW}[6/9]${NC} Mosquitto MQTT Broker installieren..."
if ! command -v mosquitto &> /dev/null; then
  apt install -y -qq mosquitto mosquitto-clients
  systemctl enable mosquitto
  systemctl start mosquitto
fi
echo -e "${GREEN}  ✓${NC} Mosquitto installiert"

# ── 7. App-Verzeichnis anlegen ──────────────────────────────────────────────
echo -e "${YELLOW}[7/9]${NC} App-Verzeichnis vorbereiten..."
mkdir -p "$APP_DIR"
mkdir -p "$DATA_DIR/Dokumentenablage"
mkdir -p "$DATA_DIR/backups"
mkdir -p "$APP_DIR/backend"
mkdir -p "$APP_DIR/frontend"

# Python Virtual Environment
if [ ! -d "$APP_DIR/venv" ]; then
  python3 -m venv "$APP_DIR/venv"
fi
echo -e "${GREEN}  ✓${NC} Verzeichnisse angelegt"

# ── 8. Caddy Konfiguration ─────────────────────────────────────────────────
echo -e "${YELLOW}[8/9]${NC} Caddy konfigurieren..."
cat > /etc/caddy/Caddyfile << CADDYEOF
$DOMAIN {
    handle /api/* {
        reverse_proxy localhost:8002
    }
    handle {
        root * $APP_DIR/frontend/build
        try_files {path} /index.html
        file_server
    }
}

# Lokaler Zugang (ohne HTTPS, Port 8001)
:8001 {
    handle /api/* {
        reverse_proxy localhost:8002
    }
    handle {
        root * $APP_DIR/frontend/build
        try_files {path} /index.html
        file_server
    }
}
CADDYEOF
systemctl restart caddy
echo -e "${GREEN}  ✓${NC} Caddy konfiguriert fuer $DOMAIN"

# ── 9. Supervisor Konfiguration ────────────────────────────────────────────
echo -e "${YELLOW}[9/9]${NC} Supervisor konfigurieren..."
cat > /etc/supervisor/conf.d/eventenergie.conf << SUPEOF
[program:backend]
command=$APP_DIR/venv/bin/uvicorn server:app --host 0.0.0.0 --port 8002 --workers 2
directory=$APP_DIR/backend
autostart=true
autorestart=true
environment=
    MONGO_URL="mongodb://localhost:27017",
    DB_NAME="$DB_NAME",
    JWT_SECRET="$(openssl rand -hex 32)",
    LOCAL_STORAGE_PATH="$DATA_DIR/Dokumentenablage",
    FRONTEND_URL="https://$DOMAIN"
stderr_logfile=/var/log/supervisor/eventenergie-backend.err.log
stdout_logfile=/var/log/supervisor/eventenergie-backend.out.log
stopsignal=TERM
stopwaitsecs=30
SUPEOF
supervisorctl reread
supervisorctl update
echo -e "${GREEN}  ✓${NC} Supervisor konfiguriert"

# ── Firewall ────────────────────────────────────────────────────────────────
echo ""
echo -e "${YELLOW}Firewall einrichten...${NC}"
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP (Caddy redirect)
ufw allow 443/tcp   # HTTPS (Caddy)
ufw allow 8001/tcp  # Lokaler Zugang (Caddy)
ufw allow 8002/tcp  # Backend direkt (intern)
ufw allow 1883/tcp  # MQTT
ufw --force enable
echo -e "${GREEN}  ✓${NC} Firewall aktiv"

# ── Zusammenfassung ─────────────────────────────────────────────────────────
echo ""
echo "================================================"
echo -e "  ${GREEN}Server-Installation abgeschlossen!${NC}"
echo "================================================"
echo ""
echo "  Installierte Software:"
echo "    Node.js   $(node --version)"
echo "    Python    $(python3 --version | cut -d' ' -f2)"
echo "    MongoDB   $(mongod --version 2>/dev/null | grep 'db version' | cut -d'v' -f2 || echo 'installiert')"
echo "    Caddy     $(caddy version 2>/dev/null | cut -d' ' -f1 || echo 'installiert')"
echo "    Mosquitto $(mosquitto -h 2>&1 | head -1 | awk '{print $3}' || echo 'installiert')"
echo "    Supervisor $(supervisord --version 2>/dev/null || echo 'installiert')"
echo ""
echo "  Verzeichnisse:"
echo "    App:       $APP_DIR"
echo "    Backend:   $APP_DIR/backend"
echo "    Frontend:  $APP_DIR/frontend"
echo "    Daten:     $DATA_DIR"
echo "    Dokumente: $DATA_DIR/Dokumentenablage"
echo ""
echo "  Naechste Schritte:"
echo "    1. Code deployen:    bash deploy.sh"
echo "    2. Datenbank laden:  bash db-migrate.sh"
echo "    3. .env anpassen:    nano $APP_DIR/backend/.env"
echo "    4. DNS eintragen:    $DOMAIN → Server-IP"
echo ""
echo "================================================"
echo ""
