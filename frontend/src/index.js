import React from "react";
import ReactDOM from "react-dom/client";
import "@/index.css";
import App from "@/App";

// CRA's react-error-overlay zeigt bei jedem window.onerror ein modales Overlay -
// auch fuer den nutzlosen cross-origin "Script error." (z.B. vom Cloudflare RUM-
// Beacon /cdn-cgi/rum oder Esri-Tile-Scripts). Wir filtern diese hier weg, BEVOR
// das Overlay seinen eigenen Listener registriert (capture: true).
if (typeof window !== "undefined") {
  const isOpaqueScriptError = (msg, filename) =>
    (!msg || msg === "Script error." || msg === "Script error") && !filename;
  window.addEventListener(
    "error",
    (event) => {
      if (isOpaqueScriptError(event?.message, event?.filename)) {
        event.stopImmediatePropagation();
        event.preventDefault();
      }
    },
    true,
  );
  window.addEventListener(
    "unhandledrejection",
    (event) => {
      const reason = event?.reason;
      const msg = typeof reason === "string" ? reason : reason?.message;
      if (isOpaqueScriptError(msg, null)) {
        event.stopImmediatePropagation();
        event.preventDefault();
      }
    },
    true,
  );
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

if ('serviceWorker' in navigator) {
  // Service Worker NICHT auf Kiosk-Routen registrieren - sonst cached er die
  // einsatzzentrale-kiosk.html und alte Versionen bleiben haengen.
  const onKioskRoute = (
    window.location.pathname.startsWith('/einsatzzentrale') ||
    window.location.pathname.startsWith('/api/einsatzzentrale/kiosk-page')
  );
  if (!onKioskRoute) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/sw.js').catch(() => {});
    });
  } else {
    // Falls bereits registriert (von frueheren Besuchen): abmelden + Caches loeschen
    navigator.serviceWorker.getRegistrations().then((regs) => {
      regs.forEach((r) => r.unregister());
    }).catch(() => {});
    if (window.caches && caches.keys) {
      caches.keys().then((keys) => Promise.all(keys.map((k) => caches.delete(k)))).catch(() => {});
    }
  }
}
