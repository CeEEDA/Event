/**
 * Oeffnet eine URL plattform-unabhaengig:
 * - Auf Capacitor (iOS/Android): verwendet @capacitor/browser (In-App-Browser
 *   mit "Fertig"/"Schliessen"-Button oben links), damit User zurueck zur App kommt
 * - Im Web-Browser: oeffnet in neuem Tab wie gewohnt
 *
 * Verwendung: openExternal(url, { title: "Tankbeleg" })
 */
export async function openExternal(url, options = {}) {
  const isNative =
    typeof window !== "undefined" &&
    window.Capacitor &&
    typeof window.Capacitor.isNativePlatform === "function" &&
    window.Capacitor.isNativePlatform();

  if (isNative) {
    try {
      const mod = await import("@capacitor/browser");
      await mod.Browser.open({
        url,
        presentationStyle: options.presentationStyle || "popover",
        toolbarColor: options.toolbarColor || "#8b5cf6",
      });
      return true;
    } catch (e) {
      // Fallback, falls Plugin nicht registriert
      window.open(url, "_blank", "noopener,noreferrer");
      return true;
    }
  }

  // Web: neuer Tab
  window.open(url, "_blank", "noopener,noreferrer");
  return true;
}
