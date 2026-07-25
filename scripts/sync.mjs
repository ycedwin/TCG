#!/usr/bin/env node
/**
 * Fetch Beehive One Piece singles via Shopify products.json and write data/catalog.json
 */
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");
const SETS_PATH = join(__dirname, "sets.json");
const OUT_PATH = join(ROOT, "public", "data", "catalog.json");
const BASE = "https://beehivetcg.com";
const PAGE_LIMIT = 250;

/** Prefer higher/rarer first for layout */
const RARITY_ORDER = [
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
  // 【PRB01】 or [OP02] — may appear more than once
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

/**
 * Parse titles like:
 *   OP16-065 サカズキ P-SRP
 *   【OP16】EB04-054 バーソロミュー・くま SP
 *   【PRB01】OP01-016 ナミ P-RP
 *   【PROMO】OP01-013 サンジ R
 *   EB01-061 Mr.2・ボン・クレー（ベンサム） P-SEC
 *   【OP16】ドン!!カード(インペルダウン) - 金邊
 *   【PRB01】OP03-055 ゴムゴムの大槌 C - 特殊閃版
 */
export function parseTitle(title) {
  let rest = stripPrefixes(title);

  let variant = "";
  const vm = rest.match(VARIANT_SUFFIX);
  if (vm) {
    variant = vm[1] || "";
    rest = rest.slice(0, vm.index).trim();
  }
  rest = rest.replace(/\s+-\s*$/, "").trim();

  // DON!! cards (often no OP##-### code)
  if (/ドン!!/.test(rest)) {
    const rarity = applyVariant("DON", variant);
    return {
      cardSet: "",
      number: "",
      name: rest,
      rarity,
      fullNumber: "",
    };
  }

  const m = rest.match(
    /^([A-Z]{1,4}\d{0,2}|ST\d{2}|PROMO)-?(\d{2,3})\s+(.+)$/i,
  );
  // e.g. "One Piece Card Game EB02-006 Promo"
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

  rarity = applyVariant(rarity, variant);

  return {
    cardSet,
    number,
    name,
    rarity,
    fullNumber: `${cardSet}-${number}`,
  };
}

async function fetchCollection(slug) {
  const products = [];
  let page = 1;
  for (;;) {
    const url = `${BASE}/collections/${slug}/products.json?limit=${PAGE_LIMIT}&page=${page}`;
    const res = await fetch(url, {
      headers: { "User-Agent": "one-piece-price-checker/1.0" },
    });
    if (!res.ok) {
      throw new Error(`HTTP ${res.status} for ${slug} page ${page}`);
    }
    const data = await res.json();
    const batch = data.products || [];
    if (batch.length === 0) break;
    products.push(...batch);
    if (batch.length < PAGE_LIMIT) break;
    page += 1;
    await sleep(200);
  }
  return products;
}

function productToCard(product, collectionCode) {
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

async function main() {
  const sets = JSON.parse(readFileSync(SETS_PATH, "utf8"));
  const allCards = [];
  const setSummaries = [];

  for (const set of sets) {
    process.stdout.write(`Sync ${set.code} (${set.slug})... `);
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
      console.log(`${cards.length} cards`);
    } catch (err) {
      console.log(`FAILED: ${err.message}`);
      setSummaries.push({
        code: set.code,
        slug: set.slug,
        name: set.name,
        count: 0,
        error: String(err.message),
      });
    }
    await sleep(300);
  }

  // Dedupe by product id (same card can appear in multiple views)
  const byId = new Map();
  for (const card of allCards) {
    byId.set(card.id, card);
  }
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

  const catalog = {
    syncedAt: new Date().toISOString(),
    source: BASE,
    currency: "HKD",
    rarityOrder: RARITY_ORDER,
    sets: setSummaries,
    cards,
  };

  mkdirSync(dirname(OUT_PATH), { recursive: true });
  writeFileSync(OUT_PATH, JSON.stringify(catalog), "utf8");
  console.log(
    `\nWrote ${cards.length} cards → ${OUT_PATH} (${setSummaries.length} sets)`,
  );
}

const isMain = process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1];
if (isMain) {
  main().catch((err) => {
    console.error(err);
    process.exit(1);
  });
}
