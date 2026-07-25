/** Live Hareruya2 buy-price match (existing cards only). */

export const HR_URL =
  "https://api.corp.hareruyamtg.com/user_data/hareruya2/json/products_all.json";

const TITLE_RE =
  /^(.+?)\(([^)]+)\)\{([^}]*)\}〈([^〉]+)〉\[([^\]]+)\]/;

const RARITY_ALIASES = {
  A: ["A", "AR"],
  AR: ["AR", "A"],
};

function normSet(s) {
  return String(s || "")
    .replace(/[^A-Za-z0-9]/g, "")
    .toUpperCase();
}

function normNum(num) {
  if (!num.includes("/")) return num;
  const [a, b] = num.split("/", 2);
  if (/^\d+$/.test(a) && /^\d+$/.test(b)) {
    return `${String(Number(a)).padStart(3, "0")}/${String(Number(b)).padStart(3, "0")}`;
  }
  return num;
}

function normRar(r) {
  r = String(r || "")
    .split(":")[0]
    .trim();
  return /^[\x00-\x7F]*$/.test(r) ? r.toUpperCase() : r;
}

function cleanName(name) {
  return String(name || "")
    .trim()
    .replace(/:[A-Za-z0-9]+$/, "");
}

function isMirrorTitle(title, rarity) {
  const t = title || "";
  return (
    t.includes("ミラー") ||
    String(rarity || "").includes(":") ||
    t.includes("-M]") ||
    t.includes("-EM]") ||
    t.includes("エネルギーミラー")
  );
}

function parseProduct(p) {
  const m = TITLE_RE.exec(p.title || "");
  if (!m) return null;
  const [, name, rarity, , numRaw, setRaw] = m;
  if (!/^\d+\/\d+$/.test(numRaw)) return null;
  const setc = normSet(setRaw.split("-")[0]);
  const num = normNum(numRaw);
  const rar = normRar(rarity);
  const [a, b] = num.split("/");
  return {
    id: p.id,
    buyYen: Number(p.buy_price) || 0,
    name: cleanName(name),
    mirror: isMirrorTitle(p.title || "", rarity),
    isPickup: Boolean(p.is_pickup),
    key: `${setc}\0${num}\0${rar}`,
  };
}

function pickBest(hits) {
  if (!hits.length) return null;
  const primary = hits.filter((h) => !h.mirror);
  const pool = primary.length ? primary : hits;
  return pool.reduce((best, h) => {
    if (!best) return h;
    if (h.buyYen !== best.buyYen) return h.buyYen > best.buyYen ? h : best;
    if (h.isPickup && !best.isPickup) return h;
    return best;
  }, null);
}

function cardKey(c) {
  const setc = normSet(c.set || "");
  const n = Number(c.number);
  const s = Number(c.setSize);
  if (!setc || !Number.isFinite(n) || !Number.isFinite(s)) return null;
  const num = `${String(n).padStart(3, "0")}/${String(s).padStart(3, "0")}`;
  return `${setc}\0${num}\0${normRar(c.rarity || "")}`;
}

/** Build set|num|rar → product rows index from Hareruya products list. */
export function buildHareruyaIndex(products) {
  const idx = new Map();
  for (const p of products) {
    const row = parseProduct(p);
    if (!row) continue;
    const list = idx.get(row.key);
    if (list) list.push(row);
    else idx.set(row.key, [row]);
  }
  return idx;
}

/**
 * Update buyYenHareruya on existing cards only (no add/remove).
 * Mutates cards in place; returns match stats.
 */
export function applyHareruyaPrices(cards, idx) {
  let matched = 0;
  let cleared = 0;
  for (const c of cards) {
    const key = cardKey(c);
    let hits = [];
    if (key) {
      const [setc, num, rar] = key.split("\0");
      for (const alias of RARITY_ALIASES[rar] || [rar]) {
        const more = idx.get(`${setc}\0${num}\0${alias}`);
        if (more) hits = hits.concat(more);
      }
    }
    const best = pickBest(hits);
    if (!best) {
      if (c.buyYenHareruya != null) cleared += 1;
      delete c.buyYenHareruya;
      delete c.hareruyaName;
      delete c.hareruyaId;
      continue;
    }
    matched += 1;
    c.buyYenHareruya = best.buyYen;
    c.hareruyaName = best.name;
    c.hareruyaId = best.id;
  }
  return { matched, cleared, indexedKeys: idx.size };
}

export async function fetchHareruyaProducts({ onProgress } = {}) {
  onProgress?.("Downloading Hareruya…");
  const res = await fetch(HR_URL, { cache: "no-store" });
  if (!res.ok) throw new Error(`Hareruya HTTP ${res.status}`);
  const data = await res.json();
  return data.products || [];
}

// ponytail: self-check — node --check won't run this; use scripts/check_hareruya_client.mjs
export function _selfCheck() {
  const products = [
    {
      id: 1,
      buy_price: 1200,
      is_pickup: false,
      title: "ピカチュウ(R){ポケモン}〈025/101〉[S1]",
    },
    {
      id: 2,
      buy_price: 900,
      is_pickup: true,
      title: "ピカチュウ(R){ポケモン}〈25/101〉[S1]",
    },
  ];
  const idx = buildHareruyaIndex(products);
  const cards = [{ set: "S1", number: "25", setSize: "101", rarity: "R" }];
  const { matched } = applyHareruyaPrices(cards, idx);
  if (matched !== 1 || cards[0].buyYenHareruya !== 1200) {
    throw new Error("hareruya match self-check failed");
  }
  return true;
}
