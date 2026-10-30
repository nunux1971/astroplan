// AstroPlan : fonctionnement hors ligne.
// La page vient du réseau quand il répond (mises à jour immédiates), sinon du cache.
const CACHE = "astroplan-__VERSION__";
const SHELL = ["./", "index.html", "manifest.webmanifest", "icons/icon-192.png", "icons/icon-512.png",
  "icons/maskable-192.png", "icons/maskable-512.png", "icons/apple-touch-icon.png"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k.startsWith("astroplan-") && k !== CACHE)
    .map(k => caches.delete(k)))).then(() => self.clients.claim()));
});

function timeout(ms) { return new Promise((_, rej) => setTimeout(() => rej(new Error("timeout")), ms)); }

// réseau d'abord (4 s au plus), puis cache
async function networkFirst(req, keep) {
  const cache = await caches.open(CACHE);
  try {
    const res = await Promise.race([fetch(req), timeout(4000)]);
    if (res && res.ok && keep) cache.put(req, res.clone());
    return res;
  } catch (e) {
    const hit = await cache.match(req, { ignoreSearch: true }) || (req.mode === "navigate" ? await cache.match("index.html") : null);
    if (hit) return hit;
    throw e;
  }
}
// cache d'abord (polices, icônes)
async function cacheFirst(req) {
  const cache = await caches.open(CACHE);
  const hit = await cache.match(req);
  if (hit) return hit;
  const res = await fetch(req);
  if (res && (res.ok || res.type === "opaque")) cache.put(req, res.clone());
  return res;
}

self.addEventListener("fetch", e => {
  const req = e.request, url = new URL(req.url);
  if (req.method !== "GET") return;
  if (url.origin === location.origin) {
    if (url.pathname.endsWith("/sw.js")) return;
    if (req.mode === "navigate" || url.pathname.endsWith(".html") || url.pathname.endsWith("journal.json") || url.pathname.endsWith("astrobin.json") || url.pathname.endsWith("space.json")) {
      e.respondWith(networkFirst(req, true)); return;
    }
    e.respondWith(cacheFirst(req)); return;
  }
  if (url.hostname === "fonts.googleapis.com" || url.hostname === "fonts.gstatic.com") { e.respondWith(cacheFirst(req)); return; }
  if (url.hostname === "api.open-meteo.com") { e.respondWith(networkFirst(req, true)); return; }
  // images du ciel, image du Soleil (SDO) et vignettes AstroBin : laissées au navigateur
});
