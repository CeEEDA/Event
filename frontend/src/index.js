import React from "react";
import ReactDOM from "react-dom/client";
import "@/index.css";
import App from "@/App";

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
