#!/bin/bash
# ============================================================================
#  Eventenergie Portal - Datenbank Migration
#  
#  AUF DEM ALTEN SERVER ausfuehren:
#    bash db-migrate.sh export
#    → Erstellt: eventenergie-backup.gz
#
#  AUF DEM NEUEN SERVER ausfuehren:
#    bash db-migrate.sh import eventenergie-backup.gz
#    → Importiert die Datenbank
# ============================================================================

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

OLD_DB="test_database"
NEW_DB="eventenergie"
BACKUP_FILE="eventenergie-backup.gz"

show_help() {
  echo ""
  echo "Verwendung:"
  echo "  bash db-migrate.sh export              Datenbank exportieren (alter Server)"
  echo "  bash db-migrate.sh import [datei.gz]   Datenbank importieren (neuer Server)"
  echo "  bash db-migrate.sh verify              Import pruefen"
  echo ""
}

# ── EXPORT (auf altem Server) ───────────────────────────────────────────────
do_export() {
  echo ""
  echo "================================================"
  echo "  Datenbank-Export"
  echo "================================================"
  echo ""

  # Welche DB exportieren?
  DB_TO_EXPORT="$OLD_DB"
  
  # Check if mongodump exists
  if ! command -v mongodump &> /dev/null; then
    echo -e "${YELLOW}→${NC} mongodump wird installiert..."
    apt install -y mongodb-database-tools 2>/dev/null || {
      echo -e "${RED}Bitte mongodb-database-tools installieren:${NC}"
      echo "  apt install mongodb-database-tools"
      exit 1
    }
  fi

  echo -e "${YELLOW}→${NC} Exportiere Datenbank '$DB_TO_EXPORT'..."
  
  # Full database dump with compression
  mongodump --db="$DB_TO_EXPORT" --gzip --archive="$BACKUP_FILE"
  
  FILESIZE=$(du -sh "$BACKUP_FILE" | cut -f1)
  echo ""
  echo -e "${GREEN}✓${NC} Export abgeschlossen: $BACKUP_FILE ($FILESIZE)"
  echo ""
  echo "  Naechster Schritt:"
  echo "    1. Datei auf neuen Server kopieren:"
  echo "       scp $BACKUP_FILE user@NEUER-SERVER:/tmp/"
  echo ""
  echo "    2. Auf neuem Server importieren:"
  echo "       bash db-migrate.sh import /tmp/$BACKUP_FILE"
  echo ""
  
  # Also export file uploads if they exist
  DOC_DIR="/app/data/Dokumentenablage"
  if [ -d "$DOC_DIR" ] && [ "$(ls -A $DOC_DIR 2>/dev/null)" ]; then
    echo -e "${YELLOW}→${NC} Dokumentenablage wird auch gesichert..."
    tar -czf "dokumentenablage-backup.tar.gz" -C "$(dirname $DOC_DIR)" "$(basename $DOC_DIR)"
    DOC_SIZE=$(du -sh "dokumentenablage-backup.tar.gz" | cut -f1)
    echo -e "${GREEN}✓${NC} Dokumente gesichert: dokumentenablage-backup.tar.gz ($DOC_SIZE)"
    echo ""
    echo "    Dokumente auch kopieren:"
    echo "       scp dokumentenablage-backup.tar.gz user@NEUER-SERVER:/tmp/"
  fi
}

# ── IMPORT (auf neuem Server) ───────────────────────────────────────────────
do_import() {
  FILE="${1:-$BACKUP_FILE}"
  
  echo ""
  echo "================================================"
  echo "  Datenbank-Import"
  echo "================================================"
  echo ""
  
  if [ ! -f "$FILE" ]; then
    echo -e "${RED}Datei nicht gefunden: $FILE${NC}"
    exit 1
  fi

  # Check if mongorestore exists
  if ! command -v mongorestore &> /dev/null; then
    echo -e "${YELLOW}→${NC} mongorestore wird installiert..."
    apt install -y mongodb-database-tools 2>/dev/null || {
      echo -e "${RED}Bitte mongodb-database-tools installieren${NC}"
      exit 1
    }
  fi

  FILESIZE=$(du -sh "$FILE" | cut -f1)
  echo -e "${YELLOW}→${NC} Importiere $FILE ($FILESIZE)..."
  echo "    Alte DB: $OLD_DB → Neue DB: $NEW_DB"
  echo ""

  # Restore with database rename
  mongorestore --gzip --archive="$FILE" \
    --nsFrom="${OLD_DB}.*" --nsTo="${NEW_DB}.*" \
    --drop

  echo ""
  echo -e "${GREEN}✓${NC} Datenbank importiert als '$NEW_DB'"
  echo ""
  
  # Import documents if backup exists
  DOC_BACKUP=""
  for f in dokumentenablage-backup.tar.gz /tmp/dokumentenablage-backup.tar.gz; do
    if [ -f "$f" ]; then DOC_BACKUP="$f"; break; fi
  done
  
  if [ -n "$DOC_BACKUP" ]; then
    DATA_DIR="/opt/eventenergie/data"
    mkdir -p "$DATA_DIR"
    echo -e "${YELLOW}→${NC} Dokumentenablage wird wiederhergestellt..."
    tar -xzf "$DOC_BACKUP" -C "$DATA_DIR/"
    echo -e "${GREEN}✓${NC} Dokumentenablage wiederhergestellt"
  fi
  
  echo ""
  echo "  Pruefen mit: bash db-migrate.sh verify"
  echo ""
}

# ── VERIFY ──────────────────────────────────────────────────────────────────
do_verify() {
  echo ""
  echo "================================================"
  echo "  Datenbank-Pruefung"
  echo "================================================"
  echo ""
  
  mongosh --quiet --eval "
    var db = db.getSiblingDB('$NEW_DB');
    var colls = db.getCollectionNames();
    print('Datenbank: $NEW_DB');
    print('Collections: ' + colls.length);
    print('');
    var total = 0;
    colls.forEach(function(c) {
      var count = db.getCollection(c).countDocuments({});
      total += count;
      if (count > 0) print('  ' + c + ': ' + count + ' Dokumente');
    });
    print('');
    print('Gesamt: ' + total + ' Dokumente in ' + colls.length + ' Collections');
    
    // Check key collections
    print('');
    print('--- Wichtige Daten ---');
    print('Benutzer: ' + db.users.countDocuments({}));
    print('Auftraege: ' + db.orders_cache.countDocuments({}));
    print('Schichtplanung: ' + db.shift_assignments.countDocuments({}));
    print('Zeiteintraege: ' + db.time_entries.countDocuments({}));
    print('Dokumente: ' + db.documents.countDocuments({}));
    print('Geraete: ' + db.devices.countDocuments({}));
  "
  echo ""
}

# ── Main ────────────────────────────────────────────────────────────────────
case "${1:-}" in
  export)  do_export ;;
  import)  do_import "$2" ;;
  verify)  do_verify ;;
  *)       show_help ;;
esac
