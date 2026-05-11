/**
 * EinsatzzentralePiPage — Hard-Redirect zur Standalone-HTML.
 *
 * Diese React-Route (/einsatzzentrale) existiert nur noch als Weiterleitung
 * zur Standalone-HTML (/api/einsatzzentrale/kiosk-page), damit der Pi-Kiosk
 * NICHT vom Webpack-Dev-Server-WebSocket-Heartbeat alle ~10 Sekunden neu
 * geladen wird.
 *
 * Die Standalone-HTML ist Vanilla-JS und kommt direkt vom FastAPI-Backend.
 * Sie hat keinen HMR, keinen WebSocket, kein Reload-Loop.
 *
 * WICHTIG: Der Redirect MUSS synchron beim Modul-Load passieren (nicht im
 * useEffect), sonst lädt React noch ein paar Frames der App und ein
 * konkurrierender Navigation-Trigger bricht den Redirect mit ERR_ABORTED ab.
 */

// Synchroner Redirect VOR React-Render.
// Wird beim ersten import dieser Datei ausgefuehrt. Nur dann aktiv, wenn der
// Browser tatsaechlich auf /einsatzzentrale steht - sonst stoert es die App
// nicht (z.B. wenn das Modul nur eager-importiert ist).
if (typeof window !== "undefined") {
  const p = window.location.pathname;
  if (p === "/einsatzzentrale" || p.startsWith("/einsatzzentrale/")) {
    // Loop-Schutz: nicht endlos triggern falls etwas Eigenartiges den
    // Pathname behaelt.
    if (!window.__kioskRedirected) {
      window.__kioskRedirected = true;
      try {
        window.location.replace("/api/einsatzzentrale/kiosk-page");
      } catch (e) {
        window.location.href = "/api/einsatzzentrale/kiosk-page";
      }
    }
  }
}

export default function EinsatzzentralePiPage() {
  return (
    <div
      data-testid="einsatzzentrale-redirect"
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        background: "#f9fafb",
        color: "#6b7280",
        fontFamily:
          "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
      }}
    >
      <div style={{ fontSize: 18, marginBottom: 8 }}>
        Einsatzzentrale wird geladen…
      </div>
      <div style={{ fontSize: 13, color: "#9ca3af" }}>
        Falls die Seite nicht weiterleitet:{" "}
        <a
          href="/api/einsatzzentrale/kiosk-page"
          style={{ color: "#d946ef" }}
        >
          hier klicken
        </a>
      </div>
    </div>
  );
}
