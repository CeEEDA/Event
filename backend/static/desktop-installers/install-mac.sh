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
cat > "$INSTALL_DIR/package.json" << 'PKGJSONEOF'
{
  "name": "eventenergie-portal",
  "version": "2.0.0",
  "description": "Eventenergie Portal - Desktop App mit Multi-Window und Server-Erkennung",
  "main": "main.js",
  "scripts": {
    "start": "electron .",
    "build:win": "electron-builder --win",
    "build:mac": "electron-builder --mac",
    "build:all": "electron-builder --win --mac"
  },
  "build": {
    "appId": "com.eventenergie.portal",
    "productName": "Eventenergie Portal",
    "directories": {
      "output": "dist"
    },
    "win": {
      "target": ["nsis"],
      "icon": "assets/icon.ico"
    },
    "nsis": {
      "oneClick": false,
      "allowToChangeInstallationDirectory": true,
      "installerLanguages": ["de"],
      "language": "1031"
    },
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
PKGJSONEOF

# config.json
cat > "$INSTALL_DIR/config.json" << 'CONFIGJSONEOF'
{
  "remoteUrl": "https://eventenergie.app",
  "localServers": [
    { "url": "https://172.20.200.117", "label": "Nginx (HTTPS)" },
    { "url": "http://172.20.200.117:8001", "label": "Caddy" }
  ],
  "title": "Eventenergie Portal"
}
CONFIGJSONEOF

# preload.js
cat > "$INSTALL_DIR/preload.js" << 'PRELOADJSEOF'
const { contextBridge, ipcRenderer } = require("electron");

// Monitor URL changes for login/logout detection
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
PRELOADJSEOF

# main.js
cat > "$INSTALL_DIR/main.js" << 'MAINJSEOF'
const { app, BrowserWindow, Menu, shell, dialog, ipcMain } = require("electron");
const path = require("path");
const fs = require("fs");
const https = require("https");
const http = require("http");

// ── Config ──────────────────────────────────────────────────────────────────
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
  const loaded = JSON.parse(fs.readFileSync(configPath, "utf-8"));
  config = { ...config, ...loaded };
} catch (e) {
  console.error("config.json nicht gefunden, verwende Standardwerte");
}

let baseUrl = config.remoteUrl;
let loginWindow = null;
let hubWindow = null;
const moduleWindows = new Map();

// ── Module Titles ───────────────────────────────────────────────────────────
const moduleTitles = {
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

// ── Server Detection ────────────────────────────────────────────────────────
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
  console.log("Suche lokalen Server...");
  var servers = config.localServers;
  var idx = 0;

  return new Promise(function (resolve) {
    function tryNext() {
      if (idx >= servers.length) {
        console.log("  -> Verwende Remote-Server: " + config.remoteUrl);
        resolve(config.remoteUrl);
        return;
      }
      var server = servers[idx];
      idx++;
      console.log("  Pruefe " + server.url + " (" + server.label + ")...");
      checkServer(server.url).then(function (reachable) {
        if (reachable) {
          console.log("  Lokaler Server gefunden: " + server.url);
          resolve(server.url);
        } else {
          console.log("  Nicht erreichbar");
          tryNext();
        }
      });
    }
    tryNext();
  });
}

// ── Allow self-signed certs for local server ────────────────────────────────
app.on("certificate-error", function (event, webContents, url, error, certificate, callback) {
  if (url.indexOf("172.20.200.117") !== -1) {
    event.preventDefault();
    callback(true);
  } else {
    callback(false);
  }
});

// ── Connection Error Page ───────────────────────────────────────────────────
function showConnectionError(win) {
  if (!win || win.isDestroyed()) return;
  win.loadURL("data:text/html," + encodeURIComponent(
    '<html><body style="font-family:-apple-system,BlinkMacSystemFont,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;background:#f8f9fa;">' +
    '<div style="text-align:center;max-width:500px;padding:20px;">' +
    '<h1 style="color:#dc3545;font-size:24px;">Verbindungsfehler</h1>' +
    '<p style="color:#6c757d;">Der Server unter <strong>' + baseUrl + '</strong> ist nicht erreichbar.</p>' +
    '<ul style="text-align:left;color:#6c757d;margin:20px 0;">' +
    '<li>Ist der Server gestartet?</li>' +
    '<li>Besteht eine Netzwerkverbindung?</li>' +
    '</ul>' +
    '<button onclick="location.reload()" style="padding:10px 24px;background:#a21caf;color:white;border:none;border-radius:6px;cursor:pointer;font-size:14px;">Erneut versuchen</button>' +
    '</div></body></html>'
  ));
}

// ── Login Window ────────────────────────────────────────────────────────────
function createLoginWindow() {
  if (loginWindow && !loginWindow.isDestroyed()) {
    loginWindow.focus();
    return;
  }

  loginWindow = new BrowserWindow({
    width: 480,
    height: 700,
    minWidth: 400,
    minHeight: 550,
    resizable: true,
    title: config.title + " - Anmeldung",
    icon: path.join(__dirname, "assets", process.platform === "win32" ? "icon.ico" : "icon.png"),
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      nodeIntegration: false,
      contextIsolation: true,
    },
    show: false,
    autoHideMenuBar: true,
  });

  loginWindow.setMenu(null);

  loginWindow.loadURL(baseUrl + "/login").catch(function () {
    showConnectionError(loginWindow);
  });

  // Detect login success via navigation events
  loginWindow.webContents.on("did-navigate", function (event, url) {
    if (url.indexOf("/hub") !== -1) onLoginSuccess();
  });
  loginWindow.webContents.on("did-navigate-in-page", function (event, url) {
    if (url.indexOf("/hub") !== -1) onLoginSuccess();
  });

  loginWindow.once("ready-to-show", function () {
    loginWindow.show();
  });

  loginWindow.on("closed", function () {
    loginWindow = null;
    if (!hubWindow || hubWindow.isDestroyed()) app.quit();
  });
}

// ── Login Success → Open Hub ────────────────────────────────────────────────
function onLoginSuccess() {
  if (hubWindow && !hubWindow.isDestroyed()) return;
  createHubWindow();
  if (loginWindow && !loginWindow.isDestroyed()) {
    loginWindow.close();
    loginWindow = null;
  }
}

// ── Hub Window (Desktop Mode) ───────────────────────────────────────────────
function createHubWindow() {
  hubWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 900,
    minHeight: 600,
    title: config.title,
    icon: path.join(__dirname, "assets", process.platform === "win32" ? "icon.ico" : "icon.png"),
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      nodeIntegration: false,
      contextIsolation: true,
    },
    show: false,
  });

  // Hub menu
  var menuTemplate = [
    {
      label: "Datei",
      submenu: [
        { label: "Abmelden", click: function () { handleLogout(); } },
        { type: "separator" },
        { label: "Beenden", accelerator: "CmdOrCtrl+Q", click: function () { app.quit(); } },
      ],
    },
    {
      label: "Ansicht",
      submenu: [
        { label: "Neu laden", accelerator: "CmdOrCtrl+R", click: function () { if (hubWindow) hubWindow.reload(); } },
        { type: "separator" },
        { label: "Entwicklertools", accelerator: "F12", click: function () { if (hubWindow) hubWindow.webContents.toggleDevTools(); } },
      ],
    },
    {
      label: "Hilfe",
      submenu: [
        {
          label: "Ueber " + config.title,
          click: function () {
            var isLocal = baseUrl !== config.remoteUrl;
            dialog.showMessageBox(hubWindow, {
              type: "info",
              title: config.title,
              message: config.title + " v2.0.0\n\nServer: " + baseUrl + (isLocal ? " (Lokal)" : " (Remote)") + "\n\nEventenergie Deutschland GmbH & Co. KG",
            });
          },
        },
      ],
    },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(menuTemplate));

  hubWindow.loadURL(baseUrl + "/hub?desktop=1").catch(function () {
    showConnectionError(hubWindow);
  });

  // Detect logout
  hubWindow.webContents.on("did-navigate", function (event, url) {
    if (url.indexOf("/login") !== -1) handleLogoutDetected();
  });
  hubWindow.webContents.on("did-navigate-in-page", function (event, url) {
    if (url.indexOf("/login") !== -1) handleLogoutDetected();
  });

  hubWindow.once("ready-to-show", function () { hubWindow.show(); });

  hubWindow.on("closed", function () {
    hubWindow = null;
    closeAllModuleWindows();
  });
}

// ── Module Windows ──────────────────────────────────────────────────────────
function createModuleWindow(modulePath) {
  var existing = moduleWindows.get(modulePath);
  if (existing && !existing.isDestroyed()) {
    existing.focus();
    return;
  }

  var title = moduleTitles[modulePath] || modulePath.replace("/", "");
  var win = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 800,
    minHeight: 600,
    title: title + " - " + config.title,
    icon: path.join(__dirname, "assets", process.platform === "win32" ? "icon.ico" : "icon.png"),
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      nodeIntegration: false,
      contextIsolation: true,
    },
    show: false,
  });

  // External links open in system browser
  win.webContents.setWindowOpenHandler(function (details) {
    var url = details.url;
    try {
      var baseHost = new URL(baseUrl).hostname;
      if (url.startsWith("http") && url.indexOf(baseHost) === -1) {
        shell.openExternal(url);
        return { action: "deny" };
      }
    } catch (e) {}
    return { action: "allow" };
  });

  win.loadURL(baseUrl + modulePath).catch(function () {
    showConnectionError(win);
  });

  win.once("ready-to-show", function () { win.show(); });

  win.on("closed", function () {
    moduleWindows.delete(modulePath);
  });

  moduleWindows.set(modulePath, win);
}

// ── Logout Handling ─────────────────────────────────────────────────────────
function handleLogout() {
  closeAllModuleWindows();
  if (hubWindow && !hubWindow.isDestroyed()) {
    hubWindow.close();
    hubWindow = null;
  }
  createLoginWindow();
}

function handleLogoutDetected() {
  closeAllModuleWindows();
  if (hubWindow && !hubWindow.isDestroyed()) {
    hubWindow.close();
    hubWindow = null;
  }
  createLoginWindow();
}

function closeAllModuleWindows() {
  moduleWindows.forEach(function (win) {
    if (!win.isDestroyed()) win.close();
  });
  moduleWindows.clear();
}

// ── IPC Handlers ────────────────────────────────────────────────────────────
ipcMain.on("open-module", function (event, modulePath) {
  createModuleWindow(modulePath);
});

ipcMain.on("url-changed", function (event, url) {
  // Login window: detect navigation to /hub
  if (loginWindow && !loginWindow.isDestroyed() && event.sender === loginWindow.webContents) {
    if (url.indexOf("/hub") !== -1) onLoginSuccess();
  }
  // Hub window: detect navigation to /login (logout)
  if (hubWindow && !hubWindow.isDestroyed() && event.sender === hubWindow.webContents) {
    if (url.indexOf("/login") !== -1) handleLogoutDetected();
  }
});

ipcMain.handle("get-server-info", function () {
  return {
    baseUrl: baseUrl,
    isLocal: baseUrl !== config.remoteUrl,
  };
});

// ── App Lifecycle ───────────────────────────────────────────────────────────
app.whenReady().then(function () {
  detectServer().then(function (detectedUrl) {
    baseUrl = detectedUrl;
    createLoginWindow();
  });
});

app.on("window-all-closed", function () {
  if (process.platform !== "darwin") app.quit();
});

app.on("activate", function () {
  if (BrowserWindow.getAllWindows().length === 0) {
    if (hubWindow && !hubWindow.isDestroyed()) {
      hubWindow.focus();
    } else {
      createLoginWindow();
    }
  }
});
MAINJSEOF

# App Icon (512x512 PNG, base64-encoded)
echo "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" | base64 -d > "$INSTALL_DIR/assets/icon.png"
echo -e "${GREEN}✓${NC} App-Dateien mit Icon erstellt"

# ── 4. Dependencies installieren ────────────────────────────────────────────
echo -e "${YELLOW}→${NC} Dependencies werden installiert (dauert 1-2 Minuten)..."
cd "$INSTALL_DIR"
yarn install --production=false 2>&1 | tail -5
echo -e "${GREEN}✓${NC} Dependencies installiert"

# ── 5. App bauen ────────────────────────────────────────────────────────────
echo ""
echo -e "${YELLOW}→${NC} App wird gebaut (dauert 2-5 Minuten)..."
yarn build:mac 2>&1 | tail -5

# ── 6. App installieren ────────────────────────────────────────────────────
echo ""
APP_FILE=$(find "$INSTALL_DIR/dist" -name "*.app" -maxdepth 3 2>/dev/null | head -1)
DMG_FILE=$(find "$INSTALL_DIR/dist" -name "*.dmg" -maxdepth 2 2>/dev/null | head -1)

if [ -n "$APP_FILE" ]; then
    echo -e "${YELLOW}→${NC} App wird nach /Applications kopiert..."
    if cp -R "$APP_FILE" "/Applications/$APP_NAME.app" 2>/dev/null; then
        echo -e "${GREEN}✓${NC} App installiert: /Applications/$APP_NAME.app"
    else
        echo -e "${YELLOW}→${NC} Admin-Rechte benoetigt..."
        sudo cp -R "$APP_FILE" "/Applications/$APP_NAME.app"
        echo -e "${GREEN}✓${NC} App installiert: /Applications/$APP_NAME.app"
    fi
else
    echo -e "${RED}✗${NC} Keine .app Datei gefunden"
fi

if [ -n "$DMG_FILE" ]; then
    cp "$DMG_FILE" "$HOME/Desktop/" 2>/dev/null
    echo -e "${GREEN}✓${NC} DMG auf dem Desktop: $(basename "$DMG_FILE")"
fi

# ── 7. Aufraeumen ──────────────────────────────────────────────────────────
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
echo "  App starten:"
echo "    → Finder: Programme → $APP_NAME"
echo "    → Oder: Spotlight (Cmd+Leertaste) → Eventenergie"
echo ""
if [ -n "$DMG_FILE" ]; then
echo "  DMG zum Weitergeben an Kollegen:"
echo "    → Auf dem Desktop: $(basename "$DMG_FILE")"
echo ""
fi
echo "================================================"
echo ""
