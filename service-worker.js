const CORE_CACHE = 'hv-swim-v580-core-1';
const RUNTIME_CACHE = 'hv-swim-v580-runtime-1';
const PUBLIC_DATA_CACHE = 'hv-swim-v580-public-data-1';
const CORE_SHELL = [
  './offline.html', './manifest.webmanifest',
  './assets/styles.css?v=5.8.0', './assets/app.js?v=5.8.0',
  './assets/support.css?v=5.8.0', './assets/support.js?v=5.8.0',
  './assets/icons.svg', './assets/hv-swim-logo-v3.png',
  './assets/fonts/manrope-latin-variable.woff2',
  './assets/app-icon-v3-64.png', './assets/app-icon-v3-192.png',
  './assets/app-icon-v3-512.png', './assets/app-icon-v3-maskable-192.png',
  './assets/app-icon-v3-maskable-512.png'
];

self.addEventListener('install', event => {
  event.waitUntil(caches.open(CORE_CACHE).then(cache => cache.addAll(CORE_SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', event => {
  const active = new Set([CORE_CACHE, RUNTIME_CACHE, PUBLIC_DATA_CACHE]);
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => !active.has(key)).map(key => caches.delete(key)))).then(() => self.clients.claim()));
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  const requested = new URL(event.notification.data?.url || 'locations.html', self.registration.scope);
  const fallback = new URL('locations.html', self.registration.scope);
  const destination = requested.origin === self.location.origin ? requested.href : fallback.href;
  event.waitUntil((async () => {
    const windows = await self.clients.matchAll({ type:'window', includeUncontrolled:true });
    const existing = windows.find(client => new URL(client.url).origin === new URL(destination).origin);
    if (existing) { await existing.focus(); if ('navigate' in existing) await existing.navigate(destination); return; }
    await self.clients.openWindow(destination);
  })());
});

const cacheSuccessful = async (cacheName, request, response) => {
  if (response.ok && response.type === 'basic') {
    try { const cache = await caches.open(cacheName); await cache.put(request, response.clone()); } catch (_) {}
  }
  return response;
};

self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) return;

  if (url.pathname.startsWith('/api/')) {
    const publicPaths = new Set(['/api/health','/api/public/site-settings','/api/public/locations','/api/public/weather','/api/classes','/api/products']);
    if (url.pathname === '/api/public/alerts') {
      event.respondWith(fetch(event.request, { cache:'no-store' }).catch(() => new Response(JSON.stringify({alerts:[]}), {status:503,headers:{'Content-Type':'application/json'}})));
      return;
    }
    if (publicPaths.has(url.pathname)) {
      event.respondWith((async () => {
        try {
          const response = await fetch(event.request);
          if (response.ok) { try { const cache = await caches.open(PUBLIC_DATA_CACHE); await cache.put(event.request, response.clone()); } catch (_) {} }
          return response;
        } catch (_) {
          return (await caches.match(event.request)) || new Response(JSON.stringify({detail:'Live data needs an internet connection'}), {status:503,headers:{'Content-Type':'application/json'}});
        }
      })());
      return;
    }
    event.respondWith(fetch(event.request).catch(() => new Response(JSON.stringify({detail:'Sign-in and account changes need an internet connection'}), {status:503,headers:{'Content-Type':'application/json'}})));
    return;
  }

  if (event.request.mode === 'navigate') {
    event.respondWith((async () => {
      try { return await cacheSuccessful(RUNTIME_CACHE, event.request, await fetch(event.request)); }
      catch (_) { return (await caches.match(event.request)) || (await caches.match('./offline.html')); }
    })());
    return;
  }

  if (/\.(?:css|js|woff2|png|jpe?g|webp|avif|svg)$/i.test(url.pathname)) {
    event.respondWith((async () => {
      const cached = await caches.match(event.request);
      const network = fetch(event.request).then(response => cacheSuccessful(RUNTIME_CACHE, event.request, response)).catch(() => cached || Response.error());
      return cached || network;
    })());
  }
});
