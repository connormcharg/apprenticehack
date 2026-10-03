const CACHE = 'five-nine-v3';
const CORE = ['/home/', '/static/fivenine/style.css', '/manifest.webmanifest'];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(CORE)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  // Never cache: non-GET, API calls, redirects/auth bounces — only plain 200 pages.
  if (e.request.method !== 'GET' || e.request.url.includes('/api/')) return;
  e.respondWith(
    fetch(e.request).then((res) => {
      if (res.status === 200 && res.type === 'basic') {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(e.request, copy));
      }
      return res;
    }).catch(() => caches.match(e.request).then((hit) => hit || caches.match('/home/')))
  );
});
