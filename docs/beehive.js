/** Beehive catalog fetch + title parse */

export const BASE = "https://beehivetcg.com";
export const PAGE_LIMIT = 250;
export const CACHE_KEY = "op-catalog-v1";

export const RARITY_ORDER = [
  "P-SRP",
  "P-RP",
  "P-SECP",
  "P-SEC",
  "P-SR",
  "P-R",
  "P-UC",
  "P-C",
  "P-L",
  "P-P",
  "P-特殊閃版",
  "P-有紋",
  "P",
  "TR",
  "SP-金",
  "SP-銀",
  "SP",
  "SEC",
  "SR",
  "R-有紋",
  "R-特殊閃版",
  "R",
  "UC-特殊閃版",
  "UC-有紋",
  "UC",
  "C-特殊閃版",
  "C-有紋",
  "C",
  "L",
  "DON-金邊",
  "DON-有紋",
  "DON",
  "Promo",
  "-",
];

const RARITY_SET = new Set(RARITY_ORDER);
const VARIANT_SUFFIX =
  /\s+-\s*(金邊|特殊閃版|有紋|金|銀|Promo)?\s*$/u;

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

function thumbnailUrl(src) {
  if (!src) return "";
  try {
    const u = new URL(src);
    u.searchParams.set("width", "240");
    return u.toString();
  } catch {
    return src;
  }
}

function stripPrefixes(title) {
  let rest = title.trim();
  while (/^[【\[][^】\]]+[】\]]/.test(rest)) {
    rest = rest.replace(/^[【\[][^】\]]+[】\]]\s*/, "");
  }
  return rest;
}

function applyVariant(rarity, variant) {
  if (!variant) return rarity;
  if (variant === "金邊" && (rarity === "DON" || rarity === "?")) return "DON-金邊";
  if (variant === "特殊閃版") {
    if (rarity === "UC") return "UC-特殊閃版";
    if (rarity === "C") return "C-特殊閃版";
    return `${rarity}-特殊閃版`;
  }
  if (variant === "有紋") {
    if (rarity === "R") return "R-有紋";
    return `${rarity}-有紋`;
  }
  if (variant === "金" || variant === "銀") return `${rarity}-${variant}`;
  if (variant === "Promo") return "Promo";
  return rarity;
}

export function parseTitle(title) {
  let rest = stripPrefixes(title);

  let variant = "";
  const vm = rest.match(VARIANT_SUFFIX);
  if (vm) {
    variant = vm[1] || "";
    rest = rest.slice(0, vm.index).trim();
  }
  rest = rest.replace(/\s+-\s*$/, "").trim();

  if (/ドン!!/.test(rest)) {
    return {
      cardSet: "",
      number: "",
      name: rest,
      rarity: applyVariant("DON", variant),
      fullNumber: "",
    };
  }

  const m = rest.match(
    /^([A-Z]{1,4}\d{0,2}|ST\d{2}|PROMO)-?(\d{2,3})\s+(.+)$/i,
  );
  if (!m) {
    const loose = rest.match(
      /\b([A-Z]{1,4}\d{0,2}|ST\d{2})-(\d{2,3})\b(?:\s+(Promo))?$/i,
    );
    if (loose) {
      const cardSet = loose[1].toUpperCase();
      const number = loose[2].padStart(3, "0");
      return {
        cardSet,
        number,
        name: `${cardSet}-${number}`,
        rarity: applyVariant(loose[3] ? "Promo" : "?", variant),
        fullNumber: `${cardSet}-${number}`,
      };
    }
    return {
      cardSet: "",
      number: "",
      name: rest || title.trim(),
      rarity: applyVariant("?", variant),
      fullNumber: "",
    };
  }

  const cardSet = m[1].toUpperCase();
  const number = m[2].padStart(3, "0");
  const nameAndRarity = m[3].trim();
  let rarity = "?";
  let name = nameAndRarity;
  const tokens = nameAndRarity.split(/\s+/);
  for (let take = Math.min(3, tokens.length); take >= 1; take--) {
    const candidate = tokens.slice(-take).join(" ");
    if (RARITY_SET.has(candidate)) {
      rarity = candidate;
      name = tokens.slice(0, -take).join(" ").trim();
      break;
    }
  }
  if (rarity === "?" && tokens.length >= 2) {
    const last = tokens[tokens.length - 1];
    if (/^[A-Z]{1,6}(-[A-Z0-9]{1,6})?$|^P-[A-Z]+$|^DON/i.test(last)) {
      rarity = last;
      name = tokens.slice(0, -1).join(" ").trim();
    }
  }

  return {
    cardSet,
    number,
    name,
    rarity: applyVariant(rarity, variant),
    fullNumber: `${cardSet}-${number}`,
  };
}

export function productToCard(product, collectionCode) {
  const parsed = parseTitle(product.title);
  const variant = product.variants?.[0];
  const price = variant ? Number(variant.price) : NaN;
  const imageSrc = product.images?.[0]?.src || "";
  const handle = product.handle || "";

  return {
    id: String(product.id),
    collection: collectionCode,
    set: parsed.cardSet || collectionCode,
    number: parsed.number,
    fullNumber: parsed.fullNumber || product.title,
    name: parsed.name || product.title,
    rarity: parsed.rarity,
    priceHkd: Number.isFinite(price) ? price : null,
    image: thumbnailUrl(imageSrc),
    url: `${BASE}/products/${handle}`,
    title: product.title,
  };
}

/** Shopify products.json supports JSONP (CORS blocks plain fetch). */
function fetchProductsJsonp(url) {
  return new Promise((resolve, reject) => {
    const cb = `bh_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
    const script = document.createElement("script");
    const timer = setTimeout(() => {
      cleanup();
      reject(new Error("Timed out"));
    }, 45000);

    function cleanup() {
      clearTimeout(timer);
      try {
        delete window[cb];
      } catch {
        window[cb] = undefined;
      }
      script.remove();
    }

    window[cb] = (data) => {
      cleanup();
      resolve(data);
    };
    script.onerror = () => {
      cleanup();
      reject(new Error("Could not reach Beehive"));
    };
    const sep = url.includes("?") ? "&" : "?";
    script.src = `${url}${sep}callback=${cb}`;
    document.head.appendChild(script);
  });
}

async function fetchCollection(slug) {
  const products = [];
  let page = 1;
  for (;;) {
    const url = `${BASE}/collections/${slug}/products.json?limit=${PAGE_LIMIT}&page=${page}`;
    const data = await fetchProductsJsonp(url);
    const batch = data.products || [];
    if (batch.length === 0) break;
    products.push(...batch);
    if (batch.length < PAGE_LIMIT) break;
    page += 1;
    await sleep(150);
  }
  return products;
}

export async function buildCatalog(sets, { onProgress } = {}) {
  const allCards = [];
  const setSummaries = [];

  for (let i = 0; i < sets.length; i++) {
    const set = sets[i];
    onProgress?.({
      index: i + 1,
      total: sets.length,
      code: set.code,
      name: set.name,
    });
    try {
      const products = await fetchCollection(set.slug);
      const cards = products.map((p) => productToCard(p, set.code));
      allCards.push(...cards);
      setSummaries.push({
        code: set.code,
        slug: set.slug,
        name: set.name,
        count: cards.length,
      });
    } catch (err) {
      setSummaries.push({
        code: set.code,
        slug: set.slug,
        name: set.name,
        count: 0,
        error: String(err.message || err),
      });
    }
    await sleep(200);
  }

  const byId = new Map();
  for (const card of allCards) byId.set(card.id, card);
  const cards = [...byId.values()].sort((a, b) => {
    const ra = RARITY_ORDER.indexOf(a.rarity);
    const rb = RARITY_ORDER.indexOf(b.rarity);
    const oa = ra === -1 ? 999 : ra;
    const ob = rb === -1 ? 999 : rb;
    if (oa !== ob) return oa - ob;
    if (a.collection !== b.collection) {
      return a.collection.localeCompare(b.collection);
    }
    return (a.fullNumber || "").localeCompare(b.fullNumber || "");
  });

  return {
    syncedAt: new Date().toISOString(),
    source: BASE,
    currency: "HKD",
    rarityOrder: RARITY_ORDER,
    sets: setSummaries,
    cards,
  };
}

export function loadCachedCatalog() {
  try {
    const raw = localStorage.getItem(CACHE_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function saveCachedCatalog(catalog) {
  localStorage.setItem(CACHE_KEY, JSON.stringify(catalog));
}
