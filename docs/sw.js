/* Cache app shell + catalog + card thumbnails for offline */
const CACHE = "op-price-v61";
const IMG_CACHE = "op-images-v2";
const PRECACHE = [
  "./",
  "./index.html",
  "./pokemon.html",
  "./styles.css",
  "./main.js",
  "./pokemon.js",
  "./hareruya.js",
  "./beehive.js",
  "./favicon.svg",
  "./manifest.webmanifest",
  "./data/sets.json",
  "./data/names-en.json",
  "./data/character-tiers.json",
  "./data/catalog.json",
  "./data/buylist.json",
  "./data/cardrush-op-buy.json",
  "./data/pkmjp-buylist.json",
];

function isCardArtHost(hostname) {
  return (
    hostname === "cdn.shopify.com" ||
    hostname === "beehivetcgbuylist.com" ||
    hostname === "files.cardrush.media" ||
    hostname === "production-recore-public-files.s3.ap-northeast-1.amazonaws.com" ||
    hostname.endsWith(".wp.com")
  );
}

function cacheableArtResponse(res) {
  // <img> often uses no-cors → opaque (status 0); still cacheable
  return res && (res.ok || res.type === "opaque");
}

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

  // Card art — cache for offline after first view (OP Shopify + PKM hosts)
  if (isCardArtHost(url.hostname)) {
    event.respondWith(
      caches.open(IMG_CACHE).then(async (cache) => {
        const cached = await cache.match(request);
        if (cached) return cached;
        try {
          const res = await fetch(request);
          if (cacheableArtResponse(res)) cache.put(request, res.clone());
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

  // Buylist / Card Rush buy must be network-first so prices stay fresh
  if (
    url.pathname.endsWith("/data/buylist.json") ||
    url.pathname.endsWith("/data/cardrush-op-buy.json") ||
    url.pathname.endsWith("/data/pkmjp-buylist.json")
  ) {
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
    return;
  }

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
