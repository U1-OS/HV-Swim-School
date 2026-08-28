const CACHE = 'hv-swim-v5-shell-29';
const PUBLIC_DATA_CACHE = 'hv-swim-v5-public-data-2';
const SHELL = [
  './', './index.html', './about.html', './programs.html', './app.html', './mobile-shell.html', './login.html', './platform.html', './enquire.html', './locations.html', './shop.html', './customer.html', './staff.html', './admin.html', './offline.html',
  './assets/styles.css?v=5.3.1', './assets/app.js?v=5.3.1', './assets/icons.svg', './assets/hv-swim-logo-v3.png', './assets/hv-swim-mark-v3.png', './assets/fonts/manrope-latin-variable.woff2', './assets/hero-swimmer.jpg', './assets/og-share-v3.jpg', './assets/merch-collection-v2.jpg', './assets/merch-uniform-studio-v3.jpg',
  './assets/platform.css?v=5.3.1', './assets/platform.js?v=5.3.1', './assets/public-api.js?v=5.3.1', './assets/programs.js?v=5.3.1', './assets/shop.js?v=5.3.1', './assets/enquire.js?v=5.3.1', './assets/mobile-shell.css?v=5.3.1', './assets/mobile-shell.js?v=5.3.1',
  './assets/app-icon-v3-64.png', './assets/app-icon-v3-180.png', './assets/app-icon-v3-192.png', './assets/app-icon-v3-512.png', './assets/app-icon-v3-1024.png', './assets/app-icon-v3-maskable-192.png', './assets/app-icon-v3-maskable-512.png', './manifest.webmanifest'
];

self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => ![CACHE,PUBLIC_DATA_CACHE].includes(key)).map(key => caches.delete(key)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;
  const url = new URL(event.request.url);
  if (url.origin === self.location.origin && url.pathname.startsWith('/api/')) {
    const publicPaths = ['/api/health','/api/public/site-settings','/api/public/locations','/api/public/weather','/api/classes','/api/products'];
    if (publicPaths.includes(url.pathname)) {
      event.respondWith((async () => {
        try {
          const response = await fetch(event.request);
          if (response.ok) {
            try { const cache = await caches.open(PUBLIC_DATA_CACHE); await cache.put(event.request, response.clone()); } catch (_) {}
          }
          return response;
        } catch (_) {
          return (await caches.match(event.request)) || new Response(JSON.stringify({detail:'Live data needs an internet connection'}),{status:503,headers:{'Content-Type':'application/json'}});
        }
      })());
      return;
    }
    event.respondWith(fetch(event.request).catch(() => new Response(JSON.stringify({detail:'Sign-in and account changes need an internet connection'}),{status:503,headers:{'Content-Type':'application/json'}})));
    return;
  }
  event.respondWith((async () => {
    try {
      const response = await fetch(event.request);
      // Only store successful same-origin responses. Caching a 404 or a 500 would pin that
      // error for the life of the cache, and cache.put rejects on opaque cross-origin responses.
      if (response.ok && response.type === 'basic') {
        try { const cache = await caches.open(CACHE); await cache.put(event.request, response.clone()); } catch (_) {}
      }
      return response;
    } catch (_) {
      return (await caches.match(event.request)) || (event.request.mode === 'navigate' ? await caches.match('./offline.html') : Response.error());
    }
  })());
});
