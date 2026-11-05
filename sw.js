/* Service worker: network first, so pages and data are always fresh when online;
   the last copy is served from the cache when offline. */
var CACHE = 'boonwui-v1';

self.addEventListener('install', function () { self.skipWaiting(); });
self.addEventListener('activate', function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k !== CACHE; }).map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});

self.addEventListener('fetch', function (e) {
  var req = e.request, url = new URL(req.url);
  if (req.method !== 'GET' || url.origin !== self.location.origin) return;
  e.respondWith(fetch(req).then(function (res) {
    if (res.ok && res.type === 'basic') { var copy = res.clone(); caches.open(CACHE).then(function (c) { c.put(req, copy); }); }
    return res;
  }).catch(function () {
    return caches.match(req, { ignoreVary: true }).then(function (hit) { return hit || caches.match(req, { ignoreSearch: true }); }).then(function (hit) {
      return hit || new Response('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Offline</title><body style="font:16px system-ui;padding:24px"><h1>You are offline</h1><p>This page has not been saved on this device yet. Reconnect and try again.</p>', { status: 503, headers: { 'Content-Type': 'text/html; charset=utf-8' } });
    });
  }));
});
