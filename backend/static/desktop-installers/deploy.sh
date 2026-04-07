#!/bin/bash
# ============================================================================
#  Eventenergie Portal - Code Deployment
#  Ausfuehren auf dem neuen Server:  bash deploy.sh
# ============================================================================

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

APP_DIR="/opt/eventenergie"
REPO_URL="${1:-}"

echo ""
echo "================================================"
echo "  Eventenergie Portal - Deployment"
echo "================================================"
echo ""

if [ -z "$REPO_URL" ]; then
  echo "Verwendung: bash deploy.sh https://github.com/USER/REPO.git"
  echo ""
  echo "Oder manuell:"
  echo "  1. Code nach $APP_DIR kopieren"
  echo "  2. Dieses Script ohne URL ausfuehren fuer Setup"
  echo ""
  
  if [ ! -d "$APP_DIR/backend" ] || [ ! -f "$APP_DIR/backend/server.py" ]; then
    echo -e "${RED}Kein Code gefunden in $APP_DIR/backend${NC}"
    echo "Bitte zuerst den Code deployen."
    exit 1
  fi
  
  echo -e "${YELLOW}→${NC} Code bereits vorhanden, fahre mit Setup fort..."
else
  echo -e "${YELLOW}→${NC} Code von Git laden..."
  
  TEMP_DIR=$(mktemp -d)
  git clone "$REPO_URL" "$TEMP_DIR/repo"
  
  # Copy backend and frontend
  cp -r "$TEMP_DIR/repo/backend/"* "$APP_DIR/backend/"
  cp -r "$TEMP_DIR/repo/frontend/"* "$APP_DIR/frontend/"
  
  # Copy server scripts
  if [ -d "$TEMP_DIR/repo/desktop" ]; then
    cp -r "$TEMP_DIR/repo/desktop" "$APP_DIR/desktop/"
  fi
  
  rm -rf "$TEMP_DIR"
  echo -e "${GREEN}  ✓${NC} Code deployed"
fi

# ── Backend Setup ───────────────────────────────────────────────────────────
echo -e "${YELLOW}→${NC} Backend Dependencies installieren..."
cd "$APP_DIR/backend"

# Activate venv
source "$APP_DIR/venv/bin/activate"

pip install --quiet -r requirements.txt
pip install --quiet emergentintegrations --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/

echo -e "${GREEN}  ✓${NC} Backend Dependencies installiert"

# ── Backend .env ────────────────────────────────────────────────────────────
if [ ! -f "$APP_DIR/backend/.env" ]; then
  echo -e "${YELLOW}→${NC} .env Template erstellen..."
  cat > "$APP_DIR/backend/.env" << 'ENVEOF'
MONGO_URL="mongodb://localhost:27017"
DB_NAME="eventenergie"
CORS_ORIGINS="*"
JWT_SECRET="HIER-EIGENEN-KEY-EINTRAGEN"
SMTP_HOST=smtp.ionos.de
SMTP_PORT=465
SMTP_USER=portal@eventenergie.app
SMTP_PASSWORD=HIER-SMTP-PASSWORT
SMTP_SENDER_NAME=Eventenergie Portal
FRONTEND_URL=https://eventenergie.app
COMPANY_IBAN=DE72570928000221481704
COMPANY_BIC=GENODE51DIE
MOSQUITTO_PASSWD_FILE=
DYMO_PRINTER_NAME=DYMO LabelWriter 550
EMERGENT_LLM_KEY=HIER-EMERGENT-KEY
LOCAL_STORAGE_PATH=/opt/eventenergie/data/Dokumentenablage
ENVEOF
  echo -e "${YELLOW}  ! .env erstellt - BITTE ANPASSEN: nano $APP_DIR/backend/.env${NC}"
else
  echo -e "${GREEN}  ✓${NC} .env bereits vorhanden"
fi

# ── Frontend Build ──────────────────────────────────────────────────────────
echo -e "${YELLOW}→${NC} Frontend bauen..."
cd "$APP_DIR/frontend"

# Create frontend .env
if [ ! -f ".env" ]; then
  cat > ".env" << 'FENVEOF'
REACT_APP_BACKEND_URL=https://eventenergie.app
WDS_SOCKET_PORT=443
FENVEOF
fi

yarn install --frozen-lockfile 2>&1 | tail -3
yarn build 2>&1 | tail -5

echo -e "${GREEN}  ✓${NC} Frontend gebaut"

# ── Desktop Installer in Static kopieren ────────────────────────────────────
if [ -d "$APP_DIR/desktop" ]; then
  echo -e "${YELLOW}→${NC} Desktop-Installer bereitstellen..."
  mkdir -p "$APP_DIR/backend/static/desktop-installers"
  for f in install-mac.sh install-win.bat install-win.ps1; do
    if [ -f "$APP_DIR/desktop/$f" ]; then
      cp "$APP_DIR/desktop/$f" "$APP_DIR/backend/static/desktop-installers/"
    fi
  done
  echo -e "${GREEN}  ✓${NC} Desktop-Installer kopiert"
fi

# ── Services neustarten ────────────────────────────────────────────────────
echo -e "${YELLOW}→${NC} Services neustarten..."
supervisorctl restart all 2>/dev/null || true
systemctl restart caddy 2>/dev/null || true

echo ""
echo "================================================"
echo -e "  ${GREEN}Deployment abgeschlossen!${NC}"
echo "================================================"
echo ""
echo "  Checkliste:"
echo "    [ ] .env anpassen:  nano $APP_DIR/backend/.env"
echo "    [ ] DNS pruefen:    eventenergie.app → Server-IP"
echo "    [ ] HTTPS pruefen:  https://eventenergie.app"
echo "    [ ] Login testen:   Admin-Account vorhanden?"
echo ""
echo "================================================"
echo ""
