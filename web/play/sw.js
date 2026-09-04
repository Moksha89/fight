const CACHE_NAME = 'roosterrun-v62-public-viewer-poll';
const STATIC_ASSETS = [
  '/play/',
  '/play/manifest.json',
  '/play/styles.css',
  '/play/app.js',
  '/play/api.js',
  '/play/components.js',
  '/play/data.js',
  '/play/icons.js',
  '/play/simulator.js',
  '/play/store.js',
  '/play/streaming.js',
  '/play/ui.js',
  '/play/srs.sdk.js',
  '/static/ic_rooster.svg',
  '/static/arena-poster-v2.png',
  '/static/cockfight-home-hero-v1.png',
  '/static/cockfight-live-card-v1.png',
  '/static/cockfight-highlights-v1.png',
  '/static/home-live-games-banner-v3.png',
  '/static/home-cockfight-livestream-v2.png',
  '/static/home-short-video-v2.png',
  '/static/home-youtube-highlight-v2.png',
  '/static/pwa/icon-192x192.png',
  '/static/pwa/icon-96x96.png',
  '/static/pwa/icon-512x512.png'
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

  // App shell / HTML navigations — network first so the latest UI always wins
  if (event.request.mode === 'navigate' || url.pathname === '/play/' || url.pathname.endsWith('index.html')) {
    event.respondWith(
      fetch(event.request).then(response => {
        if (response && response.status === 200) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
        }
        return response;
      }).catch(() => caches.match(event.request).then(c => c || caches.match('/play/')))
    );
    return;
  }

  // Other static assets — stale while revalidate
  event.respondWith(
    caches.match(event.request).then(cached => {
      const fetched = fetch(event.request).then(response => {
        if (response && response.status === 200) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
        }
        return response;
      }).catch(() => {
        if (cached) return cached;
        return new Response('Offline', { status: 503, statusText: 'Offline' });
      });
      return cached || fetched;
    })
  );
});

// Display notifications supplied by a supported browser push provider.
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
