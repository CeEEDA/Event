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
