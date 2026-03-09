const { app, BrowserWindow, Menu, shell, dialog } = require("electron");
const path = require("path");
const fs = require("fs");

// Load config
const configPath = path.join(__dirname, "config.json");
let config = { portalUrl: "http://portal.eventenergie.com:8001", title: "Eventenergie Portal" };
try {
  config = JSON.parse(fs.readFileSync(configPath, "utf-8"));
} catch (e) {
  console.error("config.json nicht gefunden, verwende Standardwerte");
}

let mainWindow;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 800,
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

  // Menu
  const menuTemplate = [
    {
      label: "Datei",
      submenu: [
        {
          label: "Server-URL aendern",
          click: async () => {
            const { response, checkboxChecked } = await dialog.showMessageBox(mainWindow, {
              type: "info",
              title: "Server-URL",
              message: `Aktuelle URL: ${config.portalUrl}\n\nZum Aendern bearbeiten Sie:\n${configPath}`,
              buttons: ["OK", "Datei oeffnen"],
            });
            if (response === 1) shell.openPath(configPath);
          },
        },
        { type: "separator" },
        { label: "Beenden", accelerator: "CmdOrCtrl+Q", click: () => app.quit() },
      ],
    },
    {
      label: "Ansicht",
      submenu: [
        { label: "Neu laden", accelerator: "CmdOrCtrl+R", click: () => mainWindow.reload() },
        { label: "Zurueck", accelerator: "Alt+Left", click: () => mainWindow.webContents.goBack() },
        { label: "Vorwaerts", accelerator: "Alt+Right", click: () => mainWindow.webContents.goForward() },
        { type: "separator" },
        { label: "Vollbild", accelerator: "F11", click: () => mainWindow.setFullScreen(!mainWindow.isFullScreen()) },
        { type: "separator" },
        { label: "Entwicklertools", accelerator: "F12", click: () => mainWindow.webContents.toggleDevTools() },
      ],
    },
    {
      label: "Hilfe",
      submenu: [
        {
          label: "Ueber Eventenergie Portal",
          click: () => {
            dialog.showMessageBox(mainWindow, {
              type: "info",
              title: "Eventenergie Portal",
              message: "Eventenergie Portal v1.0.0\n\nEventenergie Deutschland GmbH & Co. KG",
            });
          },
        },
      ],
    },
  ];

  Menu.setApplicationMenu(Menu.buildFromTemplate(menuTemplate));

  // Load portal URL
  mainWindow.loadURL(config.portalUrl).catch((err) => {
    mainWindow.loadURL(`data:text/html,
      <html><body style="font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;background:#f8f9fa;">
        <div style="text-align:center;max-width:500px;">
          <h1 style="color:#dc3545;">Verbindungsfehler</h1>
          <p>Das Portal unter <strong>${config.portalUrl}</strong> ist nicht erreichbar.</p>
          <p style="color:#6c757d;">Bitte pruefen Sie:</p>
          <ul style="text-align:left;color:#6c757d;">
            <li>Ist der Server gestartet?</li>
            <li>Stimmt die URL in config.json?</li>
            <li>Besteht eine Internetverbindung?</li>
          </ul>
          <button onclick="location.reload()" style="padding:10px 24px;background:#a21caf;color:white;border:none;border-radius:6px;cursor:pointer;font-size:14px;">
            Erneut versuchen
          </button>
        </div>
      </body></html>`);
  });

  // Open external links in system browser
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith("http") && !url.includes(config.portalUrl)) {
      shell.openExternal(url);
      return { action: "deny" };
    }
    return { action: "allow" };
  });

  mainWindow.once("ready-to-show", () => mainWindow.show());
  mainWindow.on("closed", () => { mainWindow = null; });
}

app.whenReady().then(createWindow);

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});
