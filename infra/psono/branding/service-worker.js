/* Retire Psono's precache worker so runtime branding cannot become stale. */
self.addEventListener("install", () => self.skipWaiting());

self.addEventListener("activate", (event) => {
  event.waitUntil(
    Promise.all([
      caches.keys().then((keys) =>
        Promise.all(keys.map((key) => caches.delete(key))),
      ),
      self.registration.unregister(),
    ]).then(() =>
      self.clients
        .matchAll({ includeUncontrolled: true, type: "window" })
        .then((clients) =>
          Promise.all(clients.map((client) => client.navigate(client.url))),
        ),
    ),
  );
});
