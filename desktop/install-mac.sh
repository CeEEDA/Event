#!/bin/bash
# ============================================================================
#  Eventenergie Portal - Mac Desktop App Installer
#  Einfach im Terminal ausfuehren:  bash install-mac.sh
# ============================================================================

set -e
APP_NAME="Eventenergie Portal"
INSTALL_DIR="$HOME/.eventenergie-installer"
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo ""
echo "================================================"
echo "  $APP_NAME - Mac Installer"
echo "================================================"
echo ""

# ── 1. Node.js pruefen / installieren ───────────────────────────────────────
if command -v node &> /dev/null; then
    NODE_VER=$(node --version)
    echo -e "${GREEN}✓${NC} Node.js gefunden: $NODE_VER"
else
    echo -e "${YELLOW}→${NC} Node.js wird installiert..."
    if command -v brew &> /dev/null; then
        brew install node
    else
        echo -e "${YELLOW}→${NC} Homebrew wird zuerst installiert..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        # Add brew to PATH for Apple Silicon
        if [ -f "/opt/homebrew/bin/brew" ]; then
            eval "$(/opt/homebrew/bin/brew shellenv)"
        fi
        brew install node
    fi
    echo -e "${GREEN}✓${NC} Node.js installiert: $(node --version)"
fi

# ── 2. Yarn pruefen / installieren ──────────────────────────────────────────
if command -v yarn &> /dev/null; then
    echo -e "${GREEN}✓${NC} Yarn gefunden: $(yarn --version)"
else
    echo -e "${YELLOW}→${NC} Yarn wird installiert..."
    npm install -g yarn
    echo -e "${GREEN}✓${NC} Yarn installiert: $(yarn --version)"
fi

# ── 3. App-Dateien vorbereiten ──────────────────────────────────────────────
echo -e "${YELLOW}→${NC} Erstelle App-Dateien..."
rm -rf "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR/assets"

# package.json
cat > "$INSTALL_DIR/package.json" << 'PKGJSON'
{
  "name": "eventenergie-portal",
  "version": "2.0.0",
  "description": "Eventenergie Portal - Desktop App",
  "main": "main.js",
  "scripts": {
    "start": "electron .",
    "build:mac": "electron-builder --mac"
  },
  "build": {
    "appId": "com.eventenergie.portal",
    "productName": "Eventenergie Portal",
    "directories": { "output": "dist" },
    "mac": {
      "target": ["dmg", "zip"],
      "icon": "assets/icon.png",
      "category": "public.app-category.business"
    },
    "files": [
      "main.js",
      "preload.js",
      "config.json",
      "assets/**/*"
    ]
  },
  "devDependencies": {
    "electron": "^33.0.0",
    "electron-builder": "^25.0.0"
  }
}
PKGJSON

# config.json
cat > "$INSTALL_DIR/config.json" << 'CONFIGJSON'
{
  "remoteUrl": "https://eventenergie.app",
  "localServers": [
    { "url": "https://172.20.200.117", "label": "Nginx (HTTPS)" },
    { "url": "http://172.20.200.117:8001", "label": "Caddy" }
  ],
  "title": "Eventenergie Portal"
}
CONFIGJSON

# preload.js
cat > "$INSTALL_DIR/preload.js" << 'PRELOADJS'
const { contextBridge, ipcRenderer } = require("electron");

let lastUrl = "";
const startUrlMonitor = () => {
  lastUrl = window.location.href;
  setInterval(() => {
    const currentUrl = window.location.href;
    if (currentUrl !== lastUrl) {
      lastUrl = currentUrl;
      ipcRenderer.send("url-changed", currentUrl);
    }
  }, 400);
};

window.addEventListener("DOMContentLoaded", startUrlMonitor);

contextBridge.exposeInMainWorld("desktopApp", {
  platform: process.platform,
  version: "2.0.0",
  openModule: (path) => ipcRenderer.send("open-module", path),
  getServerInfo: () => ipcRenderer.invoke("get-server-info"),
});
PRELOADJS

# main.js
cat > "$INSTALL_DIR/main.js" << 'MAINJS'
const { app, BrowserWindow, Menu, shell, dialog, ipcMain } = require("electron");
const path = require("path");
const fs = require("fs");
const https = require("https");
const http = require("http");

const configPath = path.join(__dirname, "config.json");
let config = {
  remoteUrl: "https://eventenergie.app",
  localServers: [
    { url: "https://172.20.200.117", label: "Nginx (HTTPS)" },
    { url: "http://172.20.200.117:8001", label: "Caddy" },
  ],
  title: "Eventenergie Portal",
};
try {
  var loaded = JSON.parse(fs.readFileSync(configPath, "utf-8"));
  config = Object.assign({}, config, loaded);
} catch (e) {}

var baseUrl = config.remoteUrl;
var loginWindow = null;
var hubWindow = null;
var moduleWindows = new Map();

var moduleTitles = {
  "/orders": "Auftraege",
  "/einsatzplanung": "Einsatzplanung",
  "/ki-training": "KI-Training",
  "/kirmes": "Kirmes",
  "/verwaltung": "Verwaltung",
  "/generators": "Power Monitoring",
  "/energy-monitoring": "Energy Monitoring",
  "/devices": "Geraete",
  "/fileshare": "FileShare",
  "/serviceplan": "Serviceplan",
  "/admin": "Benutzer",
  "/admin/settings": "Einstellungen",
  "/chat": "Team Chat",
  "/arbeitszeit": "Arbeitszeit",
  "/abrechnung": "Abrechnung",
  "/profile": "Profil",
};

function checkServer(url, timeout) {
  timeout = timeout || 3000;
  return new Promise(function (resolve) {
    var mod = url.startsWith("https") ? https : http;
    var req = mod.get(url, { timeout: timeout, rejectUnauthorized: false }, function () {
      resolve(true);
    });
    req.on("error", function () { resolve(false); });
    req.on("timeout", function () { req.destroy(); resolve(false); });
  });
}

function detectServer() {
  var servers = config.localServers;
  var idx = 0;
  return new Promise(function (resolve) {
    function tryNext() {
      if (idx >= servers.length) { resolve(config.remoteUrl); return; }
      var server = servers[idx]; idx++;
      checkServer(server.url).then(function (ok) {
        if (ok) resolve(server.url); else tryNext();
      });
    }
    tryNext();
  });
}

app.on("certificate-error", function (event, wc, url, err, cert, cb) {
  if (url.indexOf("172.20.200.117") !== -1) { event.preventDefault(); cb(true); }
  else cb(false);
});

function showConnectionError(win) {
  if (!win || win.isDestroyed()) return;
  win.loadURL("data:text/html," + encodeURIComponent(
    '<html><body style="font-family:-apple-system,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;background:#f8f9fa;">' +
    '<div style="text-align:center;max-width:500px;padding:20px;">' +
    '<h1 style="color:#dc3545;">Verbindungsfehler</h1>' +
    '<p>Server <strong>' + baseUrl + '</strong> nicht erreichbar.</p>' +
    '<button onclick="location.reload()" style="padding:10px 24px;background:#a21caf;color:white;border:none;border-radius:6px;cursor:pointer;">Erneut versuchen</button>' +
    '</div></body></html>'
  ));
}

function createLoginWindow() {
  if (loginWindow && !loginWindow.isDestroyed()) { loginWindow.focus(); return; }
  loginWindow = new BrowserWindow({
    width: 480, height: 700, minWidth: 400, minHeight: 550,
    title: config.title + " - Anmeldung",
    icon: path.join(__dirname, "assets", "icon.png"),
    webPreferences: { preload: path.join(__dirname, "preload.js"), nodeIntegration: false, contextIsolation: true },
    show: false, autoHideMenuBar: true,
  });
  loginWindow.setMenu(null);
  loginWindow.loadURL(baseUrl + "/login").catch(function () { showConnectionError(loginWindow); });
  loginWindow.webContents.on("did-navigate", function (e, url) { if (url.indexOf("/hub") !== -1) onLoginSuccess(); });
  loginWindow.webContents.on("did-navigate-in-page", function (e, url) { if (url.indexOf("/hub") !== -1) onLoginSuccess(); });
  loginWindow.once("ready-to-show", function () { loginWindow.show(); });
  loginWindow.on("closed", function () { loginWindow = null; if (!hubWindow || hubWindow.isDestroyed()) app.quit(); });
}

function onLoginSuccess() {
  if (hubWindow && !hubWindow.isDestroyed()) return;
  createHubWindow();
  if (loginWindow && !loginWindow.isDestroyed()) { loginWindow.close(); loginWindow = null; }
}

function createHubWindow() {
  hubWindow = new BrowserWindow({
    width: 1400, height: 900, minWidth: 900, minHeight: 600,
    title: config.title,
    icon: path.join(__dirname, "assets", "icon.png"),
    webPreferences: { preload: path.join(__dirname, "preload.js"), nodeIntegration: false, contextIsolation: true },
    show: false,
  });
  var menu = [
    { label: "Datei", submenu: [
      { label: "Abmelden", click: function () { handleLogout(); } },
      { type: "separator" },
      { label: "Beenden", accelerator: "CmdOrCtrl+Q", click: function () { app.quit(); } },
    ]},
    { label: "Ansicht", submenu: [
      { label: "Neu laden", accelerator: "CmdOrCtrl+R", click: function () { if (hubWindow) hubWindow.reload(); } },
      { type: "separator" },
      { label: "Entwicklertools", accelerator: "F12", click: function () { if (hubWindow) hubWindow.webContents.toggleDevTools(); } },
    ]},
    { label: "Hilfe", submenu: [
      { label: "Ueber " + config.title, click: function () {
        dialog.showMessageBox(hubWindow, { type: "info", title: config.title,
          message: config.title + " v2.0.0\nServer: " + baseUrl + (baseUrl !== config.remoteUrl ? " (Lokal)" : " (Remote)") });
      }},
    ]},
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(menu));
  hubWindow.loadURL(baseUrl + "/hub?desktop=1").catch(function () { showConnectionError(hubWindow); });
  hubWindow.webContents.on("did-navigate", function (e, url) { if (url.indexOf("/login") !== -1) handleLogoutDetected(); });
  hubWindow.webContents.on("did-navigate-in-page", function (e, url) { if (url.indexOf("/login") !== -1) handleLogoutDetected(); });
  hubWindow.once("ready-to-show", function () { hubWindow.show(); });
  hubWindow.on("closed", function () { hubWindow = null; closeAllModuleWindows(); });
}

function createModuleWindow(modulePath) {
  var existing = moduleWindows.get(modulePath);
  if (existing && !existing.isDestroyed()) { existing.focus(); return; }
  var title = moduleTitles[modulePath] || modulePath.replace("/", "");
  var win = new BrowserWindow({
    width: 1400, height: 900, minWidth: 800, minHeight: 600,
    title: title + " - " + config.title,
    icon: path.join(__dirname, "assets", "icon.png"),
    webPreferences: { preload: path.join(__dirname, "preload.js"), nodeIntegration: false, contextIsolation: true },
    show: false,
  });
  win.webContents.setWindowOpenHandler(function (details) {
    try { var h = new URL(baseUrl).hostname; if (details.url.indexOf(h) === -1) { shell.openExternal(details.url); return { action: "deny" }; } } catch (e) {}
    return { action: "allow" };
  });
  win.loadURL(baseUrl + modulePath).catch(function () { showConnectionError(win); });
  win.once("ready-to-show", function () { win.show(); });
  win.on("closed", function () { moduleWindows.delete(modulePath); });
  moduleWindows.set(modulePath, win);
}

function handleLogout() { closeAllModuleWindows(); if (hubWindow && !hubWindow.isDestroyed()) { hubWindow.close(); hubWindow = null; } createLoginWindow(); }
function handleLogoutDetected() { closeAllModuleWindows(); if (hubWindow && !hubWindow.isDestroyed()) { hubWindow.close(); hubWindow = null; } createLoginWindow(); }
function closeAllModuleWindows() { moduleWindows.forEach(function (w) { if (!w.isDestroyed()) w.close(); }); moduleWindows.clear(); }

ipcMain.on("open-module", function (e, p) { createModuleWindow(p); });
ipcMain.on("url-changed", function (event, url) {
  if (loginWindow && !loginWindow.isDestroyed() && event.sender === loginWindow.webContents && url.indexOf("/hub") !== -1) onLoginSuccess();
  if (hubWindow && !hubWindow.isDestroyed() && event.sender === hubWindow.webContents && url.indexOf("/login") !== -1) handleLogoutDetected();
});
ipcMain.handle("get-server-info", function () { return { baseUrl: baseUrl, isLocal: baseUrl !== config.remoteUrl }; });

app.whenReady().then(function () { detectServer().then(function (u) { baseUrl = u; createLoginWindow(); }); });
app.on("window-all-closed", function () { if (process.platform !== "darwin") app.quit(); });
app.on("activate", function () { if (BrowserWindow.getAllWindows().length === 0) createLoginWindow(); });
MAINJS

echo -e "${GREEN}✓${NC} App-Dateien erstellt"

# ── 4. Icon kopieren (Platzhalter falls nicht vorhanden) ────────────────────
if [ ! -f "$INSTALL_DIR/assets/icon.png" ]; then
    # Erzeuge ein einfaches Platzhalter-Icon
    echo -e "${YELLOW}→${NC} Platzhalter-Icon wird erstellt (kann spaeter ersetzt werden)"
    # Create a simple 1x1 PNG as placeholder
    printf '\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82' > "$INSTALL_DIR/assets/icon.png"
fi

# ── 5. Dependencies installieren ────────────────────────────────────────────
echo -e "${YELLOW}→${NC} Dependencies werden installiert (dauert 1-2 Minuten)..."
cd "$INSTALL_DIR"
yarn install --production=false 2>&1 | tail -3

echo -e "${GREEN}✓${NC} Dependencies installiert"

# ── 6. DMG bauen ────────────────────────────────────────────────────────────
echo ""
echo -e "${YELLOW}→${NC} App wird gebaut (dauert 2-5 Minuten)..."
yarn build:mac 2>&1 | tail -5

# ── 7. App installieren ────────────────────────────────────────────────────
echo ""
DMG_FILE=$(find "$INSTALL_DIR/dist" -name "*.dmg" 2>/dev/null | head -1)
APP_FILE=$(find "$INSTALL_DIR/dist/mac" -name "*.app" -o -name "*.app" 2>/dev/null | head -1)
if [ -z "$APP_FILE" ]; then
    APP_FILE=$(find "$INSTALL_DIR/dist" -name "*.app" 2>/dev/null | head -1)
fi

if [ -n "$APP_FILE" ]; then
    echo -e "${YELLOW}→${NC} App wird nach /Applications kopiert..."
    cp -R "$APP_FILE" "/Applications/$APP_NAME.app" 2>/dev/null || {
        echo -e "${YELLOW}→${NC} Admin-Rechte benoetigt..."
        sudo cp -R "$APP_FILE" "/Applications/$APP_NAME.app"
    }
    echo -e "${GREEN}✓${NC} App installiert in /Applications/$APP_NAME.app"
fi

if [ -n "$DMG_FILE" ]; then
    cp "$DMG_FILE" "$HOME/Desktop/"
    echo -e "${GREEN}✓${NC} DMG-Datei auf dem Desktop: $(basename $DMG_FILE)"
fi

# ── 8. Aufraeumen ──────────────────────────────────────────────────────────
echo ""
read -p "Installer-Dateien loeschen? (j/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Jj]$ ]]; then
    rm -rf "$INSTALL_DIR"
    echo -e "${GREEN}✓${NC} Aufgeraeumt"
fi

# ── Fertig ──────────────────────────────────────────────────────────────────
echo ""
echo "================================================"
echo -e "  ${GREEN}Installation abgeschlossen!${NC}"
echo ""
echo "  Die App starten:"
echo "    → Im Finder: Programme → $APP_NAME"
echo "    → Oder im Dock suchen"
echo ""
if [ -n "$DMG_FILE" ]; then
echo "  DMG zum Weitergeben:"
echo "    → Auf dem Desktop: $(basename $DMG_FILE)"
echo ""
fi
echo "================================================"
echo ""
