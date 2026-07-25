import {
  buildCatalog,
  loadCachedCatalog,
  saveCachedCatalog,
} from "./beehive.js";

const els = {
  status: document.getElementById("status"),
  refresh: document.getElementById("refresh"),
  search: document.getElementById("search"),
  priceToggle: document.getElementById("priceToggle"),
  priceFilters: document.getElementById("priceFilters"),
  sellMin: document.getElementById("sellMin"),
  sellMax: document.getElementById("sellMax"),
  buyMin: document.getElementById("buyMin"),
  buyMax: document.getElementById("buyMax"),
  meta: document.getElementById("meta"),
  results: document.getElementById("results"),
  lightbox: document.getElementById("lightbox"),
  lightboxImg: document.getElementById("lightboxImg"),
  lightboxCap: document.getElementById("lightboxCap"),
  lightboxClose: document.getElementById("lightboxClose"),
};

let catalog = null;
let namesEn = {};
let setsMeta = [];
let characterTiers = { S: [], A: [], B: [] };
let tierMatchers = null;
/** Beehive buy/trade-in prices: byKey["OP01-016|P-RP"] = { buyHkd, buyPaused } */
let buylist = null;
let refreshing = false;

/** Show cards above this sell price, or cheaper ones with a strong buy offer */
const MIN_PRICE_HKD = 50;
const MIN_BUY_SHOW_HKD = 5;
/** Leader sell<<buy mismatches are almost always wrong buylist matches */
const LEADER_NOISE_SELL_MAX = 10;
const LEADER_NOISE_BUY_MIN = 100;

/** Rarity code → English + Traditional Chinese hint */
const RARITY_BASE = {
  C: { en: "Common", zh: "普通" },
  UC: { en: "Uncommon", zh: "非普通" },
  R: { en: "Rare", zh: "稀有" },
  SR: { en: "Super Rare", zh: "超稀有" },
  SEC: { en: "Secret Rare", zh: "秘密稀有" },
  L: { en: "Leader", zh: "領袖卡" },
  SP: { en: "Special", zh: "特別卡" },
  TR: { en: "Treasure Rare", zh: "寶藏稀有" },
  DON: { en: "DON!!", zh: "DON!!卡" },
  Promo: { en: "Promo", zh: "宣傳卡" },
  P: { en: "Parallel", zh: "平行版" },
  "P-C": { en: "Parallel Common", zh: "平行·普通" },
  "P-UC": { en: "Parallel Uncommon", zh: "平行·非普通" },
  "P-R": { en: "Parallel Rare", zh: "平行·稀有" },
  "P-SR": { en: "Parallel Super Rare", zh: "平行·超稀有" },
  "P-SEC": { en: "Parallel Secret", zh: "平行·秘密稀有" },
  "P-SECP": { en: "Secret Parallel+", zh: "高階平行·秘密" },
  "P-SRP": { en: "Super Rare Parallel+", zh: "高階平行·超稀有" },
  "P-RP": { en: "Rare Parallel+", zh: "稀有" },
  "P-L": { en: "Parallel Leader", zh: "平行·領袖" },
  "P-P": { en: "Parallel Promo", zh: "平行·宣傳" },
};

const RARITY_SUFFIX = {
  特殊閃版: { en: "special foil", zh: "特殊閃版" },
  有紋: { en: "textured", zh: "有紋／壓紋" },
  金邊: { en: "gold border", zh: "金邊" },
  金: { en: "gold", zh: "金" },
  銀: { en: "silver", zh: "銀" },
};

function rarityHint(code) {
  const key = code || "?";
  if (RARITY_BASE[key]) {
    const { en, zh } = RARITY_BASE[key];
    return { code: key, en, zh };
  }
  for (const [suf, label] of Object.entries(RARITY_SUFFIX)) {
    if (!key.endsWith(`-${suf}`) && key !== suf) continue;
    const base = key.endsWith(`-${suf}`) ? key.slice(0, -(suf.length + 1)) : "";
    const baseHint = RARITY_BASE[base];
    if (baseHint) {
      return {
        code: key,
        en: `${baseHint.en} (${label.en})`,
        zh: `${baseHint.zh}（${label.zh}）`,
      };
    }
  }
  if (key.startsWith("P-")) {
    return { code: key, en: "Parallel variant", zh: "平行變體" };
  }
  return { code: key, en: "Other", zh: "其他" };
}

function normalizeName(s) {
  return String(s || "")
    .toLowerCase()
    .replace(/[.\s・'’\-_/]/g, "");
}

function buildTierMatchers() {
  const order = ["S", "A", "B"];
  return order.flatMap((tier) =>
    (characterTiers[tier] || [])
      .map((kw) => ({ tier, key: normalizeName(kw) }))
      .filter((x) => x.key.length >= 2)
      .sort((a, b) => b.key.length - a.key.length),
  );
}

function officialNameEn(card) {
  if (isDonCard(card)) return "";
  for (const k of [
    card.number && card.set ? `${card.set}-${card.number}` : "",
    card.sourceNumber,
    card.fullNumber,
  ]) {
    if (k && namesEn[k] && namesEn[k] !== "DON" && namesEn[k] !== "Event") {
      return namesEn[k];
    }
  }
  return "";
}

function isEventCard(card) {
  if (card.nameEn === "Event") return true;
  const en = officialNameEn(card);
  return (
    /^(Gum-Gum|Gear )/i.test(en) ||
    /ゴムゴム|ギア[2-5２-５]/.test(`${card.name || ""}${card.title || ""}`)
  );
}

/** Text used for tier match — not the Event/DON display label */
function tierSearchText(card) {
  const parts = [card.name, card.title, officialNameEn(card)];
  if (isDonCard(card)) {
    const m = `${card.title || ""} ${card.name || ""}`.match(
      /[（(]([^）)]+)[）)]/u,
    );
    if (m) parts.push(m[1]);
  }
  // Luffy attack events (Gear Two / Gum-Gum …)
  if (isEventCard(card)) {
    const en = officialNameEn(card);
    if (
      /^(Gum-Gum|Gear )/i.test(en) ||
      /ゴムゴム|ギア[2-5２-５]/.test(`${card.name || ""}${card.title || ""}`)
    ) {
      parts.push("Monkey D. Luffy", "モンキー・D・ルフィ", "Luffy", "ルフィ");
    }
  }
  return normalizeName(parts.filter(Boolean).join(" "));
}

/** Character popularity tier (not price) */
function popularityTier(card) {
  if (!tierMatchers) tierMatchers = buildTierMatchers();
  const hay = tierSearchText(card);
  if (!hay) return { tier: "C", label: "Tier C" };
  for (const { tier, key } of tierMatchers) {
    if (hay.includes(key)) return { tier, label: `Tier ${tier}` };
  }
  return { tier: "C", label: "Tier C" };
}

function isLeaderCard(card) {
  const r = card.rarity || "";
  return r === "L" || r === "P-L" || r.endsWith("-L");
}

function isLeaderBuyNoise(card) {
  if (!isLeaderCard(card)) return false;
  const sell = card.priceHkd;
  if (sell == null || !(sell < LEADER_NOISE_SELL_MAX)) return false;
  const buy = buyInfoFor(card)?.buyHkd || 0;
  return buy > LEADER_NOISE_BUY_MIN;
}

function filterCatalog(raw) {
  const cards = (raw.cards || []).filter((c) => {
    if (c.priceHkd == null) return false;
    if (isLeaderBuyNoise(c)) return false;
    if (c.priceHkd > MIN_PRICE_HKD) return true;
    // Also show cheap sell listings when Beehive buy is meaningful
    const buy = buyInfoFor(c);
    return buy != null && (buy.buyHkd || 0) > MIN_BUY_SHOW_HKD;
  });
  const countBySet = new Map();
  for (const c of cards) {
    countBySet.set(c.collection, (countBySet.get(c.collection) || 0) + 1);
  }
  const sets = (raw.sets || [])
    .map((s) => ({ ...s, count: countBySet.get(s.code) || 0 }))
    .filter((s) => s.count > 0);
  return { ...raw, cards, sets };
}

function isDonCard(card) {
  return (
    (card.rarity || "").startsWith("DON") ||
    /ドン!!/.test(card.title || "") ||
    /ドン!!/.test(card.name || "")
  );
}

function normalizeCardIds(card) {
  if (isDonCard(card)) {
    return {
      ...card,
      sourceNumber: "DON!!",
      fullNumber: "DON!!",
      rarity: (card.rarity || "").startsWith("DON") ? card.rarity : "DON",
    };
  }
  // Printed id only; undo older PRB01-OP01-016 / PRB01-016 rewrites
  const fullNumber =
    card.set && card.number
      ? `${card.set}-${card.number}`
      : card.sourceNumber || card.fullNumber || "";
  return { ...card, sourceNumber: fullNumber, fullNumber };
}

/** Event attack names (Gear Two / Gum-Gum …) → label as Event */
function enrichNameEn(card, lookup) {
  if (isDonCard(card)) return "DON";
  let en =
    card.nameEn ||
    namesEn[lookup] ||
    namesEn[card.fullNumber] ||
    namesEn[card.sourceNumber] ||
    "";
  if (en === "DON" || en === "Event") return en;
  // Attack / event card titles — not character names
  if (/^(Gum-Gum|Gear )/i.test(en)) return "Event";
  return en;
}

function enrichRaw(raw) {
  return {
    ...raw,
    cards: (raw.cards || []).map((c) => {
      const fixed = normalizeCardIds(c);
      const lookup =
        fixed.sourceNumber ||
        fixed.fullNumber ||
        `${fixed.set}-${fixed.number}`;
      return {
        ...fixed,
        nameEn: enrichNameEn(fixed, lookup),
      };
    }),
  };
}

function formatHkd(n) {
  if (n == null || Number.isNaN(n)) return "—";
  return `HK$${n.toLocaleString("en-HK", {
    minimumFractionDigits: n % 1 ? 2 : 0,
    maximumFractionDigits: 2,
  })}`;
}

function cardNumberKey(card) {
  if (card.set && card.number) return `${card.set}-${card.number}`;
  const fn = card.fullNumber || "";
  return fn && fn !== "DON!!" ? fn : "";
}

/** Exact match: card number + rarity → Beehive buy price */
function buyInfoFor(card) {
  if (!buylist?.byKey) return null;
  const fn = cardNumberKey(card);
  const rarity = card.rarity || "";
  if (!fn || !rarity) return null;
  return buylist.byKey[`${fn}|${rarity}`] || null;
}

function formatSyncedAt(iso) {
  if (!iso) return "unknown";
  try {
    return new Date(iso).toLocaleString("en-HK", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function setStatus(text, offline = false) {
  els.status.textContent = text;
  els.status.classList.toggle("is-offline", offline);
}

function largeImageUrl(src) {
  if (!src) return "";
  try {
    const u = new URL(src);
    // ~2x the 360px panel for sharp retina
    u.searchParams.set("width", "720");
    return u.toString();
  } catch {
    return src;
  }
}

/** Warm CDN + SW image cache before tap completes */
function prefetchLarge(thumbSrc) {
  const full = largeImageUrl(thumbSrc);
  if (!full || full === thumbSrc) return;
  const img = new Image();
  img.decoding = "async";
  img.src = full;
}

function matchesQuery(card, q) {
  if (!q) return true;
  const raw = q.trim().toLowerCase();
  if (!raw) return true;
  const hay = [
    card.fullNumber,
    card.number,
    `${card.set}-${card.number}`,
    card.nameEn,
    card.collection,
    card.rarity,
    isDonCard(card) ? "don don!!" : "",
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  const compact = hay.replace(/[\s\-]/g, "");
  const qCompact = raw.replace(/[\s\-]/g, "");
  return hay.includes(raw) || compact.includes(qCompact);
}

function groupByRarity(cards) {
  const order = catalog.rarityOrder || [];
  const map = new Map();
  for (const c of cards) {
    const key = c.rarity || "?";
    if (!map.has(key)) map.set(key, []);
    map.get(key).push(c);
  }
  const keys = [...map.keys()].sort((a, b) => {
    const ia = order.indexOf(a);
    const ib = order.indexOf(b);
    const oa = ia === -1 ? 999 : ia;
    const ob = ib === -1 ? 999 : ib;
    if (oa !== ob) return oa - ob;
    return a.localeCompare(b);
  });
  return keys.map((k) => [k, map.get(k)]);
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function openLightbox(thumbSrc, caption) {
  // Show cached list thumb first (instant), then swap in sharper art
  els.lightboxImg.src = thumbSrc || "";
  els.lightboxCap.textContent = caption || "";
  els.lightbox.hidden = false;
  document.body.classList.add("is-lightbox-open");
  const full = largeImageUrl(thumbSrc);
  if (!full || full === thumbSrc) return;
  const upgrade = new Image();
  upgrade.decoding = "async";
  upgrade.onload = () => {
    if (!els.lightbox.hidden && els.lightboxImg.src) {
      els.lightboxImg.src = full;
    }
  };
  upgrade.src = full;
}

function closeLightbox() {
  els.lightbox.hidden = true;
  els.lightboxImg.removeAttribute("src");
  document.body.classList.remove("is-lightbox-open");
}

function parsePriceBound(el) {
  const raw = (el?.value || "").trim();
  if (!raw) return null;
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
}

function matchesPriceFilters(card) {
  const sellMin = parsePriceBound(els.sellMin);
  const sellMax = parsePriceBound(els.sellMax);
  const buyMin = parsePriceBound(els.buyMin);
  const buyMax = parsePriceBound(els.buyMax);
  if (sellMin == null && sellMax == null && buyMin == null && buyMax == null) {
    return true;
  }

  const sell = card.priceHkd;
  if (sellMin != null && (sell == null || sell < sellMin)) return false;
  if (sellMax != null && (sell == null || sell > sellMax)) return false;

  const buy = buyInfoFor(card)?.buyHkd;
  if (buyMin != null && (buy == null || buy < buyMin)) return false;
  if (buyMax != null && (buy == null || buy > buyMax)) return false;
  return true;
}

function render() {
  if (!catalog) return;
  const q = els.search.value;

  let cards = catalog.cards.filter(
    (c) => matchesQuery(c, q) && matchesPriceFilters(c),
  );
  cards = cards
    .slice()
    .sort((a, b) =>
      (a.fullNumber || "").localeCompare(b.fullNumber || "", "en"),
    );

  els.meta.textContent = `${cards.length} cards · updated ${formatSyncedAt(catalog.syncedAt)}`;

  if (cards.length === 0) {
    els.results.innerHTML = `<div class="empty">No cards match your search</div>`;
    return;
  }

  const groups = groupByRarity(cards);
  els.results.innerHTML = groups
    .map(([rarity, list], idx) => {
      const items = list
        .map((c) => {
          const cardNo = c.fullNumber || c.title || "";
          const setCode = c.collection || c.set || "";
          const en = c.nameEn || "";
          const { tier, label } = popularityTier(c);
          const buy = buyInfoFor(c);
          const thumb = c.image
            ? `<button type="button" class="thumb-btn" data-img="${escapeHtml(c.image)}" data-cap="${escapeHtml(`${cardNo}${en ? " · " + en : ""}`)}" aria-label="Enlarge card art">
                <img class="thumb" src="${c.image}" alt="" loading="lazy" decoding="async" width="56" height="78" />
              </button>`
            : `<div class="thumb missing">No art</div>`;
          const buyUrl = (buy?.url || "").trim();
          const sellUrl = (c.url || "").trim();
          const sellPill = sellUrl
            ? `<a class="price-pill price-sell" href="${escapeHtml(sellUrl)}" target="_blank" rel="noopener noreferrer" title="Open Beehive shop">
                <span class="lbl">Sell</span>
                <span class="amt">${formatHkd(c.priceHkd)}</span>
              </a>`
            : `<div class="price-pill price-sell" title="Sell price">
                <span class="lbl">Sell</span>
                <span class="amt">${formatHkd(c.priceHkd)}</span>
              </div>`;
          const buyPill =
            buy == null
              ? `<div class="price-pill price-buy" title="No buylist match">
                  <span class="lbl">Buy(beehive)</span>
                  <span class="amt">—</span>
                </div>`
              : buyUrl
                ? `<a class="price-pill price-buy${buy.buyPaused ? " is-paused" : ""}" href="${escapeHtml(buyUrl)}" target="_blank" rel="noopener noreferrer" title="${
                    buy.buyPaused
                      ? "暫停回收 — buy price marked $0"
                      : "Open Beehive buylist product"
                  }">
                  <span class="lbl">Buy(beehive)</span>
                  <span class="amt">${formatHkd(buy.buyHkd)}</span>
                </a>`
                : `<div class="price-pill price-buy${buy.buyPaused ? " is-paused" : ""}" title="Buy price only (no product link)">
                  <span class="lbl">Buy(beehive)</span>
                  <span class="amt">${formatHkd(buy.buyHkd)}</span>
                </div>`;
          return `<li class="card-row">
            ${thumb}
            <div class="card-main">
              <div class="info">
                <div class="num-row">
                  <span class="num">${escapeHtml(cardNo)}</span>
                  <span class="tier tier-${tier}" title="Character popularity">${escapeHtml(label)}</span>
                </div>
                ${setCode ? `<p class="set">${escapeHtml(setCode)}</p>` : ""}
                ${en ? `<p class="name">${escapeHtml(en)}</p>` : ""}
              </div>
              <div class="price">
                ${sellPill}
                ${buyPill}
              </div>
            </div>
          </li>`;
        })
        .join("");
      const hint = rarityHint(rarity);
      return `<section class="rarity-block" style="animation-delay:${Math.min(idx, 8) * 0.04}s">
        <div class="rarity-head">
          <div class="rarity-title">
            <h2>${escapeHtml(hint.code)}</h2>
            <p class="rarity-hint">${escapeHtml(hint.en)}</p>
          </div>
          <span>${list.length}</span>
        </div>
        <ul class="card-list">${items}</ul>
      </section>`;
    })
    .join("");
}

async function persist(raw) {
  try {
    await saveCachedCatalog(raw);
  } catch (err) {
    console.warn("Could not cache catalog", err);
  }
}

async function applyCatalog(next, { sourceLabel, offline = false, persistData = true } = {}) {
  const enriched = enrichRaw(next);
  if (persistData) await persist(enriched);
  catalog = filterCatalog(enriched);
  setStatus(`${sourceLabel} · ${formatSyncedAt(catalog.syncedAt)}`, offline);
  render();
}

async function loadMeta() {
  const [namesRes, setsRes, tiersRes, buyRes] = await Promise.all([
    fetch("./data/names-en.json"),
    fetch("./data/sets.json"),
    fetch("./data/character-tiers.json"),
    fetch("./data/buylist.json?v=26", { cache: "no-store" }),
  ]);
  if (namesRes.ok) namesEn = await namesRes.json();
  if (setsRes.ok) setsMeta = await setsRes.json();
  if (tiersRes.ok) {
    characterTiers = await tiersRes.json();
    tierMatchers = null;
  }
  if (buyRes.ok) buylist = await buyRes.json();
}

async function loadBundledCatalog() {
  const res = await fetch("./data/catalog.json");
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function loadCatalog() {
  const online = navigator.onLine;
  try {
    await loadMeta();
  } catch {
    // still try to show cards
  }

  const cached = await loadCachedCatalog();
  if (cached?.cards?.length) {
    await applyCatalog(cached, {
      sourceLabel: online ? "Cached" : "Offline cache",
      offline: !online,
      persistData: false,
    });
    return;
  }

  try {
    const bundled = await loadBundledCatalog();
    await applyCatalog(bundled, {
      sourceLabel: online ? "Loaded" : "Offline · bundled",
      offline: !online,
      persistData: true,
    });
  } catch (err) {
    setStatus(online ? "Load failed" : "Offline · no cache yet", !online);
    els.results.innerHTML = `<div class="error">Could not load card data.<br/><small>${escapeHtml(err.message)}</small><br/><small>Open once while online to cache for offline use.</small></div>`;
  }
}

async function refreshFromBeehive() {
  if (refreshing) return;
  if (!navigator.onLine) {
    setStatus("Offline — cannot refresh", true);
    return;
  }

  refreshing = true;
  els.refresh.disabled = true;
  els.refresh.classList.add("is-busy");

  try {
    if (!setsMeta.length) await loadMeta();
    const sets = setsMeta.length
      ? setsMeta
      : await (await fetch("./data/sets.json")).json();

    const next = await buildCatalog(sets, {
      onProgress: ({ index, total, code }) => {
        setStatus(`Refreshing ${code} (${index}/${total})…`);
      },
    });

    if (!next.cards.length) throw new Error("No cards returned");

    await applyCatalog(next, {
      sourceLabel: "Updated",
      persistData: true,
    });
  } catch (err) {
    setStatus(`Refresh failed: ${err.message}`);
    console.error(err);
  } finally {
    refreshing = false;
    els.refresh.disabled = false;
    els.refresh.classList.remove("is-busy");
  }
}

function syncPriceToggleActive() {
  const active = [els.sellMin, els.sellMax, els.buyMin, els.buyMax].some(
    (el) => (el.value || "").trim() !== "",
  );
  els.priceToggle.classList.toggle("is-active", active);
}

function wireEvents() {
  let t = 0;
  const scheduleRender = () => {
    clearTimeout(t);
    t = setTimeout(() => {
      syncPriceToggleActive();
      render();
    }, 120);
  };
  els.search.addEventListener("input", scheduleRender);
  for (const el of [els.sellMin, els.sellMax, els.buyMin, els.buyMax]) {
    el.addEventListener("input", scheduleRender);
  }
  els.priceToggle.addEventListener("click", () => {
    const open = els.priceFilters.hidden;
    els.priceFilters.hidden = !open;
    els.priceToggle.setAttribute("aria-expanded", open ? "true" : "false");
    if (open) els.sellMin.focus();
  });
  els.refresh.addEventListener("click", refreshFromBeehive);
  // Start fetching large art on press/hover so open feels instant
  els.results.addEventListener("pointerdown", (e) => {
    const btn = e.target.closest(".thumb-btn");
    if (btn?.dataset.img) prefetchLarge(btn.dataset.img);
  });
  els.results.addEventListener("mouseover", (e) => {
    const btn = e.target.closest(".thumb-btn");
    if (btn?.dataset.img) prefetchLarge(btn.dataset.img);
  });
  els.results.addEventListener("click", (e) => {
    // Let price <a target=_blank> navigate normally; only intercept art enlarge
    if (e.target.closest("a.price-pill")) return;
    const btn = e.target.closest(".thumb-btn");
    if (!btn) return;
    e.preventDefault();
    e.stopPropagation();
    openLightbox(btn.dataset.img, btn.dataset.cap);
  });
  els.lightboxClose.addEventListener("click", closeLightbox);
  els.lightbox.addEventListener("click", (e) => {
    if (e.target === els.lightbox) closeLightbox();
  });
  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeLightbox();
  });
  window.addEventListener("online", () => {
    setStatus(`Online · ${formatSyncedAt(catalog?.syncedAt)}`);
  });
  window.addEventListener("offline", () => {
    setStatus(`Offline · cache ${formatSyncedAt(catalog?.syncedAt)}`, true);
  });
}

wireEvents();
loadCatalog();
