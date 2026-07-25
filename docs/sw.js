/* Cache app shell + catalog + card thumbnails for offline */
const CACHE = "op-price-v15";
const IMG_CACHE = "op-images-v1";
const PRECACHE = [
  "./",
  "./index.html",
  "./styles.css",
  "./main.js",
  "./beehive.js",
  "./favicon.svg",
  "./manifest.webmanifest",
  "./data/sets.json",
  "./data/names-en.json",
  "./data/character-tiers.json",
  "./data/catalog.json",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE)
      .then((c) => c.addAll(PRECACHE))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  const keep = new Set([CACHE, IMG_CACHE]);
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((k) => !keep.has(k)).map((k) => caches.delete(k))),
      )
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const url = new URL(request.url);

  // Card art (Shopify CDN) — cache for offline after first view
  if (url.hostname === "cdn.shopify.com") {
    event.respondWith(
      caches.open(IMG_CACHE).then(async (cache) => {
        const cached = await cache.match(request);
        if (cached) return cached;
        try {
          const res = await fetch(request);
          if (res.ok) cache.put(request, res.clone());
          return res;
        } catch {
          return cached || Response.error();
        }
      }),
    );
    return;
  }

  if (url.origin !== self.location.origin) return;

  const isCatalog =
    url.pathname.endsWith("/data/catalog.json") ||
    url.pathname.endsWith("/data/names-en.json") ||
    url.pathname.endsWith("/data/character-tiers.json");

  if (isCatalog) {
    event.respondWith(
      caches.match(request).then((cached) => {
        const network = fetch(request)
          .then((res) => {
            if (res.ok) {
              const copy = res.clone();
              caches.open(CACHE).then((c) => c.put(request, copy));
            }
            return res;
          })
          .catch(() => cached);
        return cached || network;
      }),
    );
    return;
  }

  event.respondWith(
    fetch(request)
      .then((res) => {
        if (res.ok) {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(request, copy));
        }
        return res;
      })
      .catch(() =>
        caches.match(request).then((cached) => cached || Response.error()),
      ),
  );
});
