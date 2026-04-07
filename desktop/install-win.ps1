# ============================================================================
#  Eventenergie Portal - Windows Desktop App Installer
#  PowerShell-Script: Rechtsklick → "Mit PowerShell ausfuehren"
#  Oder im Terminal:  powershell -ExecutionPolicy Bypass -File install-win.ps1
# ============================================================================

$ErrorActionPreference = "Stop"
$APP_NAME = "Eventenergie Portal"
$INSTALL_DIR = "$env:TEMP\eventenergie-installer"

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  $APP_NAME - Windows Installer" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# ── 1. Node.js pruefen / installieren ───────────────────────────────────────
$nodeExists = $null
try { $nodeExists = Get-Command node -ErrorAction SilentlyContinue } catch {}

if ($nodeExists) {
    $nodeVer = & node --version
    Write-Host "[OK] Node.js gefunden: $nodeVer" -ForegroundColor Green
} else {
    Write-Host "[..] Node.js wird installiert..." -ForegroundColor Yellow
    
    # Try winget first (Windows 10 1709+)
    $wingetExists = $null
    try { $wingetExists = Get-Command winget -ErrorAction SilentlyContinue } catch {}
    
    if ($wingetExists) {
        Write-Host "     Verwende winget..." -ForegroundColor Gray
        & winget install OpenJS.NodeJS.LTS --accept-package-agreements --accept-source-agreements
    } else {
        # Download Node.js installer directly
        Write-Host "     Lade Node.js herunter..." -ForegroundColor Gray
        $nodeUrl = "https://nodejs.org/dist/v22.15.0/node-v22.15.0-x64.msi"
        $nodeInstaller = "$env:TEMP\node-installer.msi"
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri $nodeUrl -OutFile $nodeInstaller -UseBasicParsing
        Write-Host "     Installiere Node.js..." -ForegroundColor Gray
        Start-Process msiexec.exe -ArgumentList "/i `"$nodeInstaller`" /qn" -Wait -NoNewWindow
        Remove-Item $nodeInstaller -Force -ErrorAction SilentlyContinue
    }
    
    # Refresh PATH
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    Write-Host "[OK] Node.js installiert" -ForegroundColor Green
}

# ── 2. Yarn pruefen / installieren ──────────────────────────────────────────
$yarnExists = $null
try { $yarnExists = Get-Command yarn -ErrorAction SilentlyContinue } catch {}

if ($yarnExists) {
    $yarnVer = & yarn --version 2>$null
    Write-Host "[OK] Yarn gefunden: $yarnVer" -ForegroundColor Green
} else {
    Write-Host "[..] Yarn wird installiert..." -ForegroundColor Yellow
    & npm install -g yarn 2>$null
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    Write-Host "[OK] Yarn installiert" -ForegroundColor Green
}

# ── 3. App-Dateien vorbereiten ──────────────────────────────────────────────
Write-Host "[..] Erstelle App-Dateien..." -ForegroundColor Yellow

if (Test-Path $INSTALL_DIR) { Remove-Item $INSTALL_DIR -Recurse -Force }
New-Item -ItemType Directory -Path "$INSTALL_DIR\assets" -Force | Out-Null

# package.json
$packageJson = @'
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
'@
Set-Content -Path "$INSTALL_DIR\package.json" -Value $packageJson -Encoding UTF8

# config.json
$configJson = @'
{
  "remoteUrl": "https://eventenergie.app",
  "localServers": [
    { "url": "https://172.20.200.117", "label": "Nginx (HTTPS)" },
    { "url": "http://172.20.200.117:8001", "label": "Caddy" }
  ],
  "title": "Eventenergie Portal"
}
'@
Set-Content -Path "$INSTALL_DIR\config.json" -Value $configJson -Encoding UTF8

# preload.js
$preloadJs = @'
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
'@
Set-Content -Path "$INSTALL_DIR\preload.js" -Value $preloadJs -Encoding UTF8

# main.js
$mainJs = @'
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
'@
Set-Content -Path "$INSTALL_DIR\main.js" -Value $mainJs -Encoding UTF8

# App Icons (base64)
$iconPngB64 = "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"
[System.IO.File]::WriteAllBytes("$INSTALL_DIR\assets\icon.png", [System.Convert]::FromBase64String($iconPngB64))

$iconIcoB64 = "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"
[System.IO.File]::WriteAllBytes("$INSTALL_DIR\assets\icon.ico", [System.Convert]::FromBase64String($iconIcoB64))

Write-Host "[OK] App-Dateien mit Icons erstellt" -ForegroundColor Green

# ── 4. Dependencies installieren ────────────────────────────────────────────
Write-Host ""
Write-Host "[..] Dependencies werden installiert (dauert 1-2 Minuten)..." -ForegroundColor Yellow
Set-Location $INSTALL_DIR
& yarn install --production=false 2>&1 | Select-Object -Last 5
Write-Host "[OK] Dependencies installiert" -ForegroundColor Green

# ── 5. Windows-Installer bauen ──────────────────────────────────────────────
Write-Host ""
Write-Host "[..] Windows-Installer wird gebaut (dauert 2-5 Minuten)..." -ForegroundColor Yellow
& yarn build:win 2>&1 | Select-Object -Last 5
Write-Host "[OK] Build abgeschlossen" -ForegroundColor Green

# ── 6. Installer suchen und ausfuehren ─────────────────────────────────────
Write-Host ""
$setupExe = Get-ChildItem -Path "$INSTALL_DIR\dist" -Filter "*.exe" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1

if ($setupExe) {
    # Copy installer to Desktop
    $desktopPath = [Environment]::GetFolderPath("Desktop")
    Copy-Item $setupExe.FullName -Destination "$desktopPath\$($setupExe.Name)" -Force
    Write-Host "[OK] Installer auf dem Desktop: $($setupExe.Name)" -ForegroundColor Green
    
    Write-Host ""
    $runNow = Read-Host "Installer jetzt ausfuehren? (j/n)"
    if ($runNow -match "^[jJyY]") {
        Write-Host "[..] Starte Installer..." -ForegroundColor Yellow
        Start-Process $setupExe.FullName
    }
} else {
    Write-Host "[!] Kein Installer gefunden in $INSTALL_DIR\dist" -ForegroundColor Red
    Write-Host "    Bitte manuell pruefen." -ForegroundColor Gray
}

# ── 7. Aufraeumen ──────────────────────────────────────────────────────────
Write-Host ""
$cleanup = Read-Host "Installer-Dateien loeschen? (j/n)"
if ($cleanup -match "^[jJyY]") {
    Set-Location $env:USERPROFILE
    Remove-Item $INSTALL_DIR -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "[OK] Aufgeraeumt" -ForegroundColor Green
}

# ── Fertig ──────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  Installation abgeschlossen!" -ForegroundColor Green
Write-Host "" -ForegroundColor Cyan
if ($setupExe) {
    Write-Host "  Installer zum Weitergeben:" -ForegroundColor White
    Write-Host "    → Desktop: $($setupExe.Name)" -ForegroundColor Gray
}
Write-Host ""
Write-Host "  Nach Installation die App starten:" -ForegroundColor White
Write-Host "    → Startmenue → $APP_NAME" -ForegroundColor Gray
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

Read-Host "Druecken Sie Enter zum Beenden"
