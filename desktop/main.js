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
    width: 820,
    height: 520,
    minWidth: 600,
    minHeight: 400,
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
