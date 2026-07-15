const CACHE_NAME = 'ninf-v1';
const STATIC_ASSETS = ['/', '/manifest.json'];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Passthrough para chamadas de API (sempre online)
  if (url.pathname.startsWith('/api/')) return;

  // Cache-first para assets estáticos
  event.respondWith(
    caches.match(event.request).then(
      (cached) => cached ?? fetch(event.request).catch(() => caches.match('/'))
    )
  );
});

// --- Web Push Listener ---
self.addEventListener('push', (event) => {
  if (!event.data) {
    console.warn('[Service Worker] Evento de push recebido sem dados.');
    return;
  }

  try {
    const payload = event.data.json();
    console.log('[Service Worker] Push recebido:', payload);

    const title = payload.title || 'Alerta ness.';
    const options = {
      body: payload.body || 'Novo incidente crítico detectado.',
      icon: '/favicon.svg',
      badge: '/favicon.svg',
      vibrate: [200, 100, 200],
      data: {
        incident_id: payload.incident_id,
        fingerprint: payload.fingerprint,
        url: payload.incident_id ? `/?view=incidents&id=${payload.incident_id}` : '/?view=incidents'
      },
      tag: payload.fingerprint || 'general-incident',
      renotify: true
    };

    event.waitUntil(
      self.registration.showNotification(title, options)
    );
  } catch (err) {
    console.error('[Service Worker] Erro ao tratar payload de push:', err);
    const text = event.data.text();
    event.waitUntil(
      self.registration.showNotification('Alerta ness.', {
        body: text,
        icon: '/favicon.svg'
      })
    );
  }
});

self.addEventListener('notificationclick', (event) => {
  console.log('[Service Worker] Notificação clicada:', event.notification);
  event.notification.close();

  const clickUrl = event.notification.data?.url || '/';

  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if (client.url.includes(self.location.origin) && 'focus' in client) {
          return client.focus().then((focusedClient) => {
            if ('navigate' in focusedClient) {
              return focusedClient.navigate(clickUrl);
            }
          });
        }
      }
      if (self.clients.openWindow) {
        return self.clients.openWindow(clickUrl);
      }
    })
  );
});
