// Selbstloeschender Service Worker (2026-02-18)
// Grund: Auf Android Chrome fuehrte der alte SW zu einem Reload-Loop, weil
// gecachte index.html auf inzwischen entfernte JS-Bundle-Hashes zeigte.
// Dieser SW entfernt ALLE Caches und deregistriert sich selbst beim naechsten
// Besuch, sodass danach direkt vom Netzwerk geladen wird.
self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    try {
      const keys = await caches.keys();
      await Promise.all(keys.map((k) => caches.delete(k)));
    } catch (_e) { /* ignore */ }
    try {
      await self.registration.unregister();
    } catch (_e) { /* ignore */ }
    // Alle offenen Tabs einmalig reloaden, damit sie ohne SW neu starten
    const clients = await self.clients.matchAll({ type: 'window' });
    clients.forEach((client) => {
      try { client.navigate(client.url); } catch (_e) { /* ignore */ }
    });
  })());
});

// Alle Fetches ohne Cache direkt ans Netzwerk weiterleiten
self.addEventListener('fetch', (event) => {
  // no-op: standard-fetch, kein caching
});
