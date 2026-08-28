const CACHE = 'hv-swim-v5-shell-17';
const PUBLIC_DATA_CACHE = 'hv-swim-v4-public-data-1';
const SHELL = [
  './', './index.html', './about.html', './programs.html', './app.html', './mobile-shell.html', './login.html', './platform.html', './enquire.html', './locations.html', './shop.html', './customer.html', './staff.html', './admin.html', './offline.html',
  './assets/styles.css?v=5.1.0', './assets/app.js?v=5.1.0', './assets/hv-swim-logo.png', './assets/hero-swimmer.jpg', './assets/og-share.jpg', './assets/merch-collection-v2.jpg', './assets/merch-uniform-studio-v3.jpg',
  './assets/platform.css?v=5.1.0', './assets/platform.js?v=5.1.0', './assets/public-api.js?v=5.1.0', './assets/programs.js?v=5.1.0', './assets/shop.js?v=5.1.0', './assets/enquire.js?v=5.1.0', './assets/mobile-shell.css?v=5.1.0', './assets/mobile-shell.js?v=5.1.0',
  './assets/app-icon-192.png', './assets/app-icon-512.png', './assets/app-icon-1024.png', './manifest.webmanifest'
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
      event.respondWith(fetch(event.request).then(response => {
        if (response.ok) caches.open(PUBLIC_DATA_CACHE).then(cache => cache.put(event.request, response.clone()));
        return response;
      }).catch(() => caches.match(event.request).then(match => match || new Response(JSON.stringify({detail:'Live data needs an internet connection'}),{status:503,headers:{'Content-Type':'application/json'}}))));
      return;
    }
    event.respondWith(fetch(event.request).catch(() => new Response(JSON.stringify({detail:'Sign-in and account changes need an internet connection'}),{status:503,headers:{'Content-Type':'application/json'}})));
    return;
  }
  if (url.hostname === 'api.open-meteo.com') {
    event.respondWith(fetch(event.request).catch(() => caches.match(event.request)));
    return;
  }
  event.respondWith(fetch(event.request).then(response => {
    const copy = response.clone();
    caches.open(CACHE).then(cache => cache.put(event.request, copy));
    return response;
  }).catch(() => caches.match(event.request).then(match => match || (event.request.mode === 'navigate' ? caches.match('./offline.html') : Response.error()))));
});
