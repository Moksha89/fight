const CACHE_NAME = 'roosterrun-v1';
const STATIC_ASSETS = [
  '/play/',
  '/static/logo.png?v=2',
  '/static/pwa/icon-192x192.png',
  '/static/pwa/icon-512x512.png',
  'https://fonts.googleapis.com/icon?family=Material+Icons',
  'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap'
];

// Install — cache static assets
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return cache.addAll(STATIC_ASSETS);
    }).then(() => self.skipWaiting())
  );
});

// Activate — clean old caches
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

// Fetch — network first for API, cache first for static assets
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // Skip non-GET requests
  if (event.request.method !== 'GET') return;

  // API calls — network only (never cache dynamic data)
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/ws/')) return;

  // Static assets and app shell — stale while revalidate
  event.respondWith(
    caches.match(event.request).then(cached => {
      const fetched = fetch(event.request).then(response => {
        if (response && response.status === 200) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
        }
        return response;
      }).catch(() => {
        // Network failed — return cached or offline page
        if (cached) return cached;
        if (event.request.mode === 'navigate') {
          return caches.match('/play/');
        }
        return new Response('Offline', { status: 503, statusText: 'Offline' });
      });
      return cached || fetched;
    })
  );
});

// Push notifications (future-ready)
self.addEventListener('push', event => {
  const data = event.data ? event.data.json() : { title: 'RoosterRun', body: 'New update available' };
  event.waitUntil(
    self.registration.showNotification(data.title || 'RoosterRun', {
      body: data.body || '',
      icon: '/static/pwa/icon-192x192.png',
      badge: '/static/pwa/icon-96x96.png',
      vibrate: [100, 50, 100],
      data: { url: data.url || '/play/' }
    })
  );
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  event.waitUntil(
    clients.matchAll({ type: 'window' }).then(list => {
      for (const client of list) {
        if (client.url.includes('/play/') && 'focus' in client) return client.focus();
      }
      return clients.openWindow(event.notification.data.url || '/play/');
    })
  );
});
