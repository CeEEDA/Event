/**
 * EinsatzzentralePiPage — Smart-Redirect zur Standalone-HTML.
 *
 * Diese React-Route (/einsatzzentrale) existiert als Weiterleitung
 * zur Standalone-HTML, damit der Pi-Kiosk
 * NICHT vom Webpack-Dev-Server-WebSocket-Heartbeat alle ~10 Sekunden neu
 * geladen wird.
 *
 * Die Standalone-HTML ist Vanilla-JS und kommt direkt vom FastAPI-Backend.
 * Sie hat keinen HMR, keinen WebSocket, kein Reload-Loop.
 *
 * WICHTIG: Wir muessen die Query-Parameter (pi_id, key) ans Redirect-Ziel
 * mitgeben, sonst kommt der Kiosk nicht an seine Auth-Credentials.
 *
 * Wenn der /api/einsatzzentrale/kiosk-page Endpoint 404 gibt (alte Backend-
 * Version ohne ausgelieferte HTML-Datei), bleiben wir hier auf der React-
 * Route und zeigen einen Status-Hinweis, statt blindlings zum 404er zu
 * redirecten und dem User JSON-Fehlertext anzuzeigen.
 */

import { useEffect, useState } from "react";

const KIOSK_API = "/api/einsatzzentrale/kiosk-page";
const BUILD_ID_API = "/api/einsatzzentrale/build-id";

export default function EinsatzzentralePiPage() {
  const [status, setStatus] = useState("checking"); // checking | redirecting | unavailable

  useEffect(() => {
    if (window.__kioskRedirected) return;

    const search = window.location.search || "";
    const target = KIOSK_API + search;

    // Probe via /build-id (klein, gibt 200 wenn HTML ausgeliefert werden kann,
    // 404 wenn die HTML-Datei am Backend fehlt). HEAD ist nicht supported (405).
    fetch(BUILD_ID_API, { cache: "no-store" })
      .then((r) => {
        if (r.ok) {
          window.__kioskRedirected = true;
          setStatus("redirecting");
          window.location.replace(target);
        } else {
          setStatus("unavailable");
        }
      })
      .catch(() => setStatus("unavailable"));
  }, []);

  return (
    <div
      data-testid="einsatzzentrale-redirect"
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        background: "#0a0a0a",
        color: "#e5e7eb",
        fontFamily:
          "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        padding: 24,
        textAlign: "center",
      }}
    >
      {status === "checking" && (
        <>
          <div style={{ fontSize: 20, marginBottom: 8, color: "#d946ef" }}>
            Einsatzzentrale wird geladen…
          </div>
          <div style={{ fontSize: 13, color: "#6b7280" }}>
            Prüfe Verbindung zum Portal
          </div>
        </>
      )}
      {status === "redirecting" && (
        <div style={{ fontSize: 20, color: "#d946ef" }}>
          Weiterleitung …
        </div>
      )}
      {status === "unavailable" && (
        <>
          <div style={{ fontSize: 22, marginBottom: 8, color: "#f59e0b" }}>
            ⚠️ Kiosk-Page nicht verfügbar
          </div>
          <div
            style={{
              fontSize: 14,
              color: "#9ca3af",
              maxWidth: 540,
              lineHeight: 1.5,
            }}
          >
            Das Portal-Backend liefert die Kiosk-HTML aktuell nicht aus
            (Server-Datei fehlt oder ältere Backend-Version).
            <br />
            <br />
            <strong>Was tun?</strong>
            <br />
            Portal-Administrator: Backend aktualisieren (Save to GitHub →
            Pull auf Server → Backend-Restart). Dann lädt diese Seite
            automatisch beim nächsten Reload.
          </div>
          <button
            onClick={() => window.location.reload()}
            style={{
              marginTop: 24,
              padding: "10px 24px",
              fontSize: 14,
              background: "#d946ef",
              color: "white",
              border: 0,
              borderRadius: 6,
              cursor: "pointer",
            }}
            data-testid="einsatzzentrale-retry-btn"
          >
            Erneut versuchen
          </button>
        </>
      )}
    </div>
  );
}
