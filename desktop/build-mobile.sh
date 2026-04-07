#!/bin/bash
# ============================================================================
#  Eventenergie Portal - Mobile App Build (Mac/Linux)
#
#  Android APK:  bash build-mobile.sh android
#  iOS:          bash build-mobile.sh ios
#  Beide:        bash build-mobile.sh all
# ============================================================================

set -e
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

BACKEND_URL="https://eventenergie.app"

# Find frontend dir
if [ -d "./frontend" ]; then
  FRONTEND_DIR="./frontend"
elif [ -f "./package.json" ] && grep -q "capacitor" ./package.json 2>/dev/null; then
  FRONTEND_DIR="."
else
  FRONTEND_DIR="/opt/eventenergie/frontend"
fi

build_web() {
  echo -e "${YELLOW}[..]${NC} React-App bauen..."
  cd "$FRONTEND_DIR"
  REACT_APP_BACKEND_URL=$BACKEND_URL yarn build 2>&1 | tail -5
  echo -e "${GREEN}[OK]${NC} Web-Assets gebaut"
}

sync_cap() {
  echo -e "${YELLOW}[..]${NC} Capacitor sync..."
  npx cap sync 2>&1 | tail -5
  echo -e "${GREEN}[OK]${NC} Native Projekte synchronisiert"
}

build_android() {
  echo ""
  echo "================================================"
  echo "  Android APK bauen"
  echo "================================================"
  echo ""
  
  build_web
  sync_cap
  
  echo -e "${YELLOW}[..]${NC} Android APK bauen..."
  cd "$FRONTEND_DIR/android"
  
  if [ -f "./gradlew" ]; then
    chmod +x ./gradlew
    ./gradlew assembleRelease 2>&1 | tail -10
  else
    echo -e "${RED}[!]${NC} gradlew nicht gefunden. Android Studio verwenden:"
    echo "    npx cap open android"
    return
  fi
  
  APK=$(find . -name "*.apk" -path "*/release/*" 2>/dev/null | head -1)
  if [ -n "$APK" ]; then
    cp "$APK" "$HOME/Desktop/EventenergiePortal.apk" 2>/dev/null || cp "$APK" ./EventenergiePortal.apk
    SIZE=$(du -h "$APK" | cut -f1)
    echo ""
    echo -e "${GREEN}[OK]${NC} APK erstellt: EventenergiePortal.apk ($SIZE)"
  else
    echo -e "${YELLOW}[!]${NC} APK nicht gefunden. Android Studio verwenden:"
    echo "    npx cap open android"
  fi
}

build_ios() {
  echo ""
  echo "================================================"
  echo "  iOS App bauen"
  echo "================================================"
  echo ""
  
  if [ "$(uname)" != "Darwin" ]; then
    echo -e "${RED}[!]${NC} iOS-Apps koennen nur auf macOS gebaut werden."
    return
  fi
  
  build_web
  sync_cap
  
  echo -e "${YELLOW}[..]${NC} Xcode-Projekt oeffnen..."
  npx cap open ios
  echo ""
  echo -e "${GREEN}[OK]${NC} Xcode geoeffnet. Dort:"
  echo "     1. Signing-Zertifikat waehlen (Apple Developer Account)"
  echo "     2. Product → Archive"
  echo "     3. Distribute App → App Store / Ad Hoc"
}

case "${1:-help}" in
  android) build_android ;;
  ios)     build_ios ;;
  all)     build_android; build_ios ;;
  *)
    echo ""
    echo "Eventenergie Portal - Mobile App Builder"
    echo ""
    echo "  bash build-mobile.sh android    Android APK bauen"
    echo "  bash build-mobile.sh ios        iOS App bauen (nur Mac)"
    echo "  bash build-mobile.sh all        Beide bauen (nur Mac)"
    echo ""
    echo "Voraussetzungen:"
    echo "  Android: Android Studio + JDK 17"
    echo "  iOS:     Xcode + CocoaPods (nur macOS)"
    echo ""
    ;;
esac
