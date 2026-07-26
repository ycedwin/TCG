import {
  applyHareruyaPrices,
  buildHareruyaIndex,
  fetchHareruyaProducts,
} from "./hareruya.js";

const els = {
  status: document.getElementById("status"),
  refresh: document.getElementById("refresh"),
  search: document.getElementById("search"),
  priceToggle: document.getElementById("priceToggle"),
  priceFilters: document.getElementById("priceFilters"),
  rarityFilters: document.getElementById("rarityFilters"),
  buyMin: document.getElementById("buyMin"),
  buyMax: document.getElementById("buyMax"),
  meta: document.getElementById("meta"),
  results: document.getElementById("results"),
  lightbox: document.getElementById("lightbox"),
  lightboxImg: document.getElementById("lightboxImg"),
  lightboxCap: document.getElementById("lightboxCap"),
  lightboxClose: document.getElementById("lightboxClose"),
  backTop: document.getElementById("backTop"),
};

/** "" = all · special art-ish · RR/RRR · commons/trainers/etc */
let rarityBucket = "";

/** Hide extreme buy outliers */
const MAX_BUY_HKD = 15000;
const MAX_BUY_YEN = 300000;

/** Prefer high-end rarities first within a set; unknowns last */
const RARITY_RANK = [
  "MUR",
  "SAR",
  "UR",
  "CSR",
  "HR",
  "SSR",
  "SR",
  "ACE",
  "AR",
  "RRR",
  "RR",
  "CHR",
  "S",
  "BWR",
  "MA",
  "K",
  "A",
  "☆",
  "★",
  "◆",
  "●",
  "H",
  "P",
  "PR",
  "R",
  "U",
  "C",
  "-",
];

let catalog = null;
let refreshing = false;
/** @type {Map<string, {title: string, cards: object[]}>} */
let eraData = new Map();
let virtRaf = 0;
// ponytail: fixed row pitch; slight gaps ok if a row wraps taller on narrow phones
const VIRT_OVERSCAN = 8;
const VIRT_THRESHOLD = 48;

/** Desktop side-by-side vs phone stacked prices need different row pitch. */
function virtRowPx() {
  return window.matchMedia("(max-width: 639px)").matches ? 200 : 120;
}

function setStatus(text, offline = false) {
  els.status.textContent = text;
  els.status.classList.toggle("is-offline", offline);
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function formatHkd(n) {
  if (n == null || Number.isNaN(n)) return "—";
  return `$${Number(n).toLocaleString("en-HK", {
    maximumFractionDigits: 2,
  })}`;
}

function formatYen(n) {
  if (n == null || Number.isNaN(n)) return "—";
  return `¥${Number(n).toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
}

function formatSyncedAt(iso) {
  if (!iso) return "unknown";
  try {
    return new Date(iso).toLocaleString(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch {
    return iso;
  }
}

function parsePriceBound(el) {
  const raw = (el?.value || "").trim();
  if (!raw) return null;
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
}

function matchesQuery(card, q) {
  const needle = q.trim().toLowerCase();
  if (!needle) return true;
  const hay = [
    card.fullNumber,
    card.printId,
    card.set,
    card.number,
    card.nameEn,
    card.name,
    card.cardrushName,
    card.hareruyaName,
    card.title,
    card.rarity,
    card.setName,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return hay.includes(needle.replace(/\s+/g, " "));
}

function matchesPriceFilters(card) {
  const buyMin = parsePriceBound(els.buyMin);
  const buyMax = parsePriceBound(els.buyMax);
  if (buyMin == null && buyMax == null) return true;
  // Filter against Beehive HKD when present; Hareruya-only cards ignore HKD bounds
  const buy = card.buyHkd;
  if (buy == null) return true;
  if (buyMin != null && buy < buyMin) return false;
  if (buyMax != null && buy > buyMax) return false;
  return true;
}

function rarityRank(code) {
  const i = RARITY_RANK.indexOf(code);
  return i === -1 ? 500 : i;
}

const RARITY_SPECIAL = new Set([
  "MUR",
  "SAR",
  "UR",
  "CSR",
  "HR",
  "SSR",
  "SR",
  "AR",
  "CHR",
  "S",
  "BWR",
  "MA",
  "K",
  "A",
  "☆",
  "★",
  "◆",
]);
const RARITY_HIGH = new Set(["RRR", "RR", "ACE"]);

function rarityBucketOf(card) {
  const r = card.rarity || "-";
  if (RARITY_SPECIAL.has(r)) return "special";
  if (RARITY_HIGH.has(r)) return "high";
  return "other";
}

function matchesRarityBucket(card) {
  if (!rarityBucket) return true;
  return rarityBucketOf(card) === rarityBucket;
}

function setCodeOf(card) {
  return (card.set || "?").toUpperCase();
}

/** JP name: Card Rush first, then Hareruya, then Beehive/default. */
function jpNameOf(card) {
  return (
    card.cardrushName ||
    (card.source === "cardrush" ? card.name : "") ||
    card.hareruyaName ||
    card.name ||
    ""
  );
}

function displayNameOf(card) {
  const jp = jpNameOf(card);
  const en = (card.nameEn || "").trim();
  if (jp && en && en.toLowerCase() !== jp.toLowerCase()) return `${jp} · ${en}`;
  return jp || en;
}

function cardSortKey(card) {
  return (
    (card.buyHkd || 0) * 1e9 +
    (card.buyYenHareruya || 0) * 1e3 +
    (card.buyYenCardrush || 0)
  );
}

function compareWithinSet(a, b) {
  const na = Number.parseInt(a.number, 10);
  const nb = Number.parseInt(b.number, 10);
  if (Number.isFinite(na) && Number.isFinite(nb) && na !== nb) return na - nb;
  const numCmp = String(a.number || "").localeCompare(
    String(b.number || ""),
    "en",
    { numeric: true },
  );
  if (numCmp) return numCmp;
  const rr = rarityRank(a.rarity || "") - rarityRank(b.rarity || "");
  if (rr) return rr;
  return cardSortKey(b) - cardSortKey(a);
}

function renderCardRow(c) {
  const cardNo = c.printId || c.fullNumber || "";
  const rarity = c.rarity || "";
  const name = displayNameOf(c);
  const thumb = c.image
    ? `<button type="button" class="thumb-btn" data-img="${escapeHtml(c.image)}" data-cap="${escapeHtml(`${cardNo}${name ? " · " + name : ""}`)}" aria-label="Enlarge card art">
        <img class="thumb" src="${escapeHtml(c.image)}" alt="" decoding="async" width="56" height="78" />
      </button>`
    : `<div class="thumb missing">No art</div>`;
  const buyUrl = (c.url || "").trim();
  const hasBeehive = c.buyHkd != null;
  const buyPill = !hasBeehive
    ? `<div class="price-pill price-buy" title="Not on Beehive buylist">
        <span class="lbl">Buy BH</span>
        <span class="amt">—</span>
      </div>`
    : buyUrl
      ? `<a class="price-pill price-buy" href="${escapeHtml(buyUrl)}" target="_blank" rel="noopener noreferrer" title="Open Beehive buylist product">
          <span class="lbl">Buy BH</span>
          <span class="amt">${formatHkd(c.buyHkd)}</span>
        </a>`
      : `<div class="price-pill price-buy" title="Beehive buy price">
          <span class="lbl">Buy BH</span>
          <span class="amt">${formatHkd(c.buyHkd)}</span>
        </div>`;
  const hrYen = c.buyYenHareruya;
  const hrPill =
    hrYen == null
      ? `<div class="price-pill price-hareruya" title="No Hareruya match">
          <span class="lbl">Buy HR</span>
          <span class="amt">—</span>
        </div>`
      : `<div class="price-pill price-hareruya" title="Hareruya buy price (JPY)">
          <span class="lbl">Buy HR</span>
          <span class="amt">${formatYen(hrYen)}</span>
        </div>`;
  const sellYen = c.sellYenCardrush;
  const sellUrl = (c.sellUrlCardrush || "").trim();
  const sellPending = c.sellMatchCardrush === "ambiguous";
  const sellAmt =
    sellPending || sellYen == null ? "—" : formatYen(sellYen);
  const sellTitle = sellPending
    ? "Multiple sell matches — review needed"
    : sellYen === 0
      ? "No clean JP sell match"
      : "Card Rush sell price (JPY)";
  const sellPill = sellUrl
    ? `<a class="price-pill price-cardrush-sell" href="${escapeHtml(sellUrl)}" target="_blank" rel="noopener noreferrer" title="${escapeHtml(sellTitle)}">
        <span class="lbl">Sell CR</span>
        <span class="amt">${sellAmt}</span>
      </a>`
    : `<div class="price-pill price-cardrush-sell" title="${escapeHtml(sellTitle)}">
        <span class="lbl">Sell CR</span>
        <span class="amt">${sellAmt}</span>
      </div>`;
  const crYen = c.buyYenCardrush;
  const crExtra = (c.cardrushExtra || "").trim();
  const crTitle = crExtra
    ? `Card Rush buy (JPY) · ${crExtra}`
    : "Card Rush buy price (JPY)";
  const crPill =
    crYen == null
      ? `<div class="price-pill price-cardrush" title="No Card Rush match">
          <span class="lbl">Buy CR</span>
          <span class="amt">—</span>
        </div>`
      : `<a class="price-pill price-cardrush" href="https://cardrush.media/pokemon/buying_prices" target="_blank" rel="noopener noreferrer" title="${escapeHtml(crTitle)}">
          <span class="lbl">Buy CR</span>
          <span class="amt">${formatYen(crYen)}</span>
        </a>`;
  const tier = (c.tier || "").trim();
  const tierRank = c.tierRank;
  const tierBadge = tier
    ? `<span class="tier tier-${escapeHtml(tier)}" title="Bulbapedia 2025 visit rank${
        tierRank != null ? ` #${tierRank}` : ""
      }">Tier ${escapeHtml(tier)}</span>`
    : "";
  return `<li class="card-row">
    ${thumb}
    <div class="card-main">
      <div class="info">
        <div class="num-row">
          <span class="num">${escapeHtml(cardNo)}</span>
          ${tierBadge}
        </div>
        ${rarity ? `<p class="set">${escapeHtml(rarity)}</p>` : ""}
        ${name ? `<p class="name">${escapeHtml(name)}</p>` : ""}
      </div>
      <div class="price">${sellPill}${crPill}${hrPill}${buyPill}</div>
    </div>
  </li>`;
}

function sortEraCards(cards) {
  return cards.slice().sort((a, b) => {
    const price = cardSortKey(b) - cardSortKey(a);
    if (price) return price;
    const setCmp = setCodeOf(a).localeCompare(setCodeOf(b), "en");
    if (setCmp) return setCmp;
    return compareWithinSet(a, b);
  });
}

function renderEraShell(id, title, count, { open = false } = {}) {
  const openAttr = open ? " open" : "";
  return `<details class="fold fold-set" data-era="${escapeHtml(id)}"${openAttr}>
    <summary class="fold-head fold-head-set">
      <span class="fold-title">${escapeHtml(title)}</span>
      <span class="fold-meta">${count}</span>
    </summary>
    <div class="virt" data-era-virt="${escapeHtml(id)}">
      <ul class="card-list virt-window"></ul>
    </div>
  </details>`;
}

/** Keep overlapping rows mounted so thumbs don't remount/flash while scrolling. */
function syncVirtWindow(win, cards, start, end, row) {
  win.style.transform = `translateY(${start * row}px)`;
  let prevStart = win._virtStart;
  let prevEnd = win._virtEnd;

  if (
    prevStart == null ||
    prevEnd == null ||
    end <= prevStart ||
    start >= prevEnd
  ) {
    win.innerHTML = cards.slice(start, end).map(renderCardRow).join("");
    win._virtStart = start;
    win._virtEnd = end;
    return;
  }

  while (prevStart < start && win.firstChild) {
    win.removeChild(win.firstChild);
    prevStart++;
  }
  while (prevEnd > end && win.lastChild) {
    win.removeChild(win.lastChild);
    prevEnd--;
  }
  if (start < prevStart) {
    win.insertAdjacentHTML(
      "afterbegin",
      cards.slice(start, prevStart).map(renderCardRow).join(""),
    );
    prevStart = start;
  }
  if (end > prevEnd) {
    win.insertAdjacentHTML(
      "beforeend",
      cards.slice(prevEnd, end).map(renderCardRow).join(""),
    );
    prevEnd = end;
  }
  win._virtStart = prevStart;
  win._virtEnd = prevEnd;
}

function paintEraVirt(details) {
  const id = details.dataset.era;
  const cards = eraData.get(id)?.cards || [];
  const root = details.querySelector(".virt");
  const win = root?.querySelector(".virt-window");
  if (!root || !win) return;

  if (!details.open || !cards.length) {
    root.classList.remove("is-virt");
    root.style.height = "";
    root.style.removeProperty("--virt-row");
    win.style.transform = "";
    win._virtStart = win._virtEnd = null;
    win._virtRow = null;
    win.innerHTML = "";
    return;
  }

  if (cards.length <= VIRT_THRESHOLD) {
    root.classList.remove("is-virt");
    root.style.height = "";
    root.style.removeProperty("--virt-row");
    win.style.transform = "";
    win._virtStart = win._virtEnd = null;
    win._virtRow = null;
    win.innerHTML = cards.map(renderCardRow).join("");
    return;
  }

  const row = virtRowPx();
  if (win._virtRow != null && win._virtRow !== row) {
    // breakpoint crossed — remount so pitch matches stacked/side layout
    win._virtStart = win._virtEnd = null;
  }
  win._virtRow = row;
  root.classList.add("is-virt");
  root.style.setProperty("--virt-row", `${row}px`);
  root.style.height = `${cards.length * row}px`;

  const rootTop = root.getBoundingClientRect().top + window.scrollY;
  const viewTop = window.scrollY;
  const viewH = window.innerHeight || 800;
  let start = Math.floor((viewTop - rootTop) / row) - VIRT_OVERSCAN;
  let end = Math.ceil((viewTop + viewH - rootTop) / row) + VIRT_OVERSCAN;
  start = Math.max(0, start);
  end = Math.min(cards.length, Math.max(start + 1, end));

  if (win._virtStart === start && win._virtEnd === end) {
    win.style.transform = `translateY(${start * row}px)`;
    return;
  }
  syncVirtWindow(win, cards, start, end, row);
}

function paintAllVirt() {
  for (const d of els.results.querySelectorAll("details[data-era]")) {
    paintEraVirt(d);
  }
}

function scheduleVirtPaint() {
  if (virtRaf) return;
  virtRaf = requestAnimationFrame(() => {
    virtRaf = 0;
    paintAllVirt();
  });
}

/** Sets with any Beehive/Hareruya row — everything else is CR-only vintage. */
function modernSetCodes() {
  const modern = new Set();
  for (const c of catalog?.cards || []) {
    if (c.source !== "cardrush") modern.add(setCodeOf(c));
  }
  return modern;
}

function isVintageCard(card, modernSets) {
  return !modernSets.has(setCodeOf(card));
}

/** Prefer origin upload URL — Photon (i0.wp.com) thumbs are tiny and can look washed when upscaled */
function largeImageUrl(src) {
  if (!src) return "";
  try {
    const u = new URL(src);
    // https://i0.wp.com/beehivetcgbuylist.com/wp-content/... → https://beehivetcgbuylist.com/wp-content/...
    if (/\.wp\.com$/i.test(u.hostname)) {
      const path = u.pathname.replace(/^\/+/, "");
      const slash = path.indexOf("/");
      if (slash > 0) return `https://${path}`;
    }
    u.search = "";
    return u.toString();
  } catch {
    return src;
  }
}

const prefetchCache = new Set();
function prefetchLarge(src) {
  const full = largeImageUrl(src);
  if (!full || prefetchCache.has(full)) return;
  prefetchCache.add(full);
  const img = new Image();
  img.src = full;
}

function openLightbox(src, cap) {
  const full = largeImageUrl(src) || src;
  els.lightboxImg.src = full;
  els.lightboxCap.textContent = cap || "";
  els.lightbox.hidden = false;
  document.body.classList.add("is-lightbox-open");
}

function closeLightbox() {
  els.lightbox.hidden = true;
  els.lightboxImg.removeAttribute("src");
  document.body.classList.remove("is-lightbox-open");
}

function withinBuyCaps(card) {
  if ((card.buyHkd || 0) > MAX_BUY_HKD) return false;
  // Hareruya / Card Rush top listings sit at exactly ¥300,000
  if ((card.buyYenHareruya || 0) >= MAX_BUY_YEN) return false;
  if ((card.buyYenCardrush || 0) >= MAX_BUY_YEN) return false;
  return true;
}

function render() {
  if (!catalog) return;
  const q = els.search.value;
  const searching = q.trim().length > 0;
  let cards = (catalog.cards || []).filter(
    (c) =>
      withinBuyCaps(c) &&
      matchesQuery(c, q) &&
      matchesPriceFilters(c) &&
      matchesRarityBucket(c),
  );

  const modernSets = modernSetCodes();
  const modern = [];
  const vintage = [];
  for (const c of cards) {
    if (isVintageCard(c, modernSets)) vintage.push(c);
    else modern.push(c);
  }

  const hrAt = catalog.hareruya?.syncedAt;
  const crAt = catalog.cardrush?.syncedAt;
  const crSellAt = catalog.cardrushSell?.syncedAt;
  const bucketLbl = rarityBucket
    ? ` · ${rarityBucket === "high" ? "RR+" : rarityBucket}`
    : "";
  els.meta.textContent = `${cards.length} cards${bucketLbl} · ${modern.length} modern${
    vintage.length ? ` · ${vintage.length} vintage` : ""
  } · Beehive + Hareruya + Card Rush · updated ${formatSyncedAt(catalog.syncedAt)}${
    hrAt ? ` · HR ${formatSyncedAt(hrAt)}` : ""
  }${crAt ? ` · CR ${formatSyncedAt(crAt)}` : ""}${
    crSellAt ? ` · CR sell ${formatSyncedAt(crSellAt)}` : ""
  }`;

  if (cards.length === 0) {
    eraData = new Map();
    els.results.innerHTML = `<div class="empty">No cards match your search</div>`;
    return;
  }

  eraData = new Map();
  const parts = [];
  if (modern.length) {
    eraData.set("modern", { title: "Modern", cards: sortEraCards(modern) });
    parts.push(
      renderEraShell("modern", "Modern", modern.length, { open: searching }),
    );
  }
  if (vintage.length) {
    eraData.set("vintage", { title: "Vintage", cards: sortEraCards(vintage) });
    parts.push(
      renderEraShell("vintage", "Vintage", vintage.length, { open: searching }),
    );
  }
  // ponytail: shells only until open; then windowed rows (~viewport + overscan).
  els.results.innerHTML = parts.join("");
  paintAllVirt();
}

async function loadCatalog({ bust = false } = {}) {
  const url = bust
    ? `./data/pkmjp-buylist.json?v=${Date.now()}`
    : "./data/pkmjp-buylist.json?v=53";
  setStatus("Loading…");
  try {
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    catalog = await res.json();
    setStatus(`Ready · ${formatSyncedAt(catalog.syncedAt)}`);
    render();
  } catch (err) {
    setStatus(`Load failed: ${err.message}`);
    els.results.innerHTML = `<div class="error">Could not load Pokemon JP buylist</div>`;
  }
}

async function refreshHareruyaLive() {
  if (!catalog?.cards?.length) throw new Error("No catalog loaded");
  if (!navigator.onLine) throw new Error("Offline — cannot fetch Hareruya");
  setStatus("Fetching Hareruya (~8 MB)…");
  const products = await fetchHareruyaProducts();
  setStatus(`Matching ${products.length.toLocaleString()} Hareruya rows…`);
  const idx = buildHareruyaIndex(products);
  const { matched, cleared } = applyHareruyaPrices(catalog.cards, idx);
  catalog.hareruya = {
    ...(catalog.hareruya || {}),
    syncedAt: new Date().toISOString(),
    source: "live",
    counts: {
      ...(catalog.hareruya?.counts || {}),
      hareruyaProducts: products.length,
      indexedKeys: idx.size,
      matchedExisting: matched,
      cleared,
    },
  };
  setStatus(
    `Hareruya updated · ${matched.toLocaleString()} matched · ${formatSyncedAt(catalog.hareruya.syncedAt)}`,
  );
  render();
}

async function refresh() {
  if (refreshing) return;
  refreshing = true;
  els.refresh.disabled = true;
  els.refresh.classList.add("is-busy");
  try {
    // Beehive stays from deployed JSON; Hareruya yen is live.
    await loadCatalog({ bust: true });
    await refreshHareruyaLive();
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
  const active = [els.buyMin, els.buyMax].some(
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
  for (const el of [els.buyMin, els.buyMax]) {
    el.addEventListener("input", scheduleRender);
  }
  els.rarityFilters?.addEventListener("click", (e) => {
    const btn = e.target.closest(".rarity-chip");
    if (!btn || !els.rarityFilters.contains(btn)) return;
    rarityBucket = btn.dataset.bucket || "";
    for (const chip of els.rarityFilters.querySelectorAll(".rarity-chip")) {
      chip.classList.toggle("is-active", chip === btn);
    }
    render();
  });
  els.priceToggle.addEventListener("click", () => {
    const open = els.priceFilters.hidden;
    els.priceFilters.hidden = !open;
    els.priceToggle.setAttribute("aria-expanded", open ? "true" : "false");
    if (open) els.buyMin.focus();
  });
  els.refresh.addEventListener("click", refresh);
  els.results.addEventListener("toggle", (e) => {
    const d = e.target;
    if (!(d instanceof HTMLDetailsElement) || !d.dataset.era) return;
    if (!d.open) {
      const win = d.querySelector(".virt-window");
      if (win) {
        win.innerHTML = "";
        delete win.dataset.range;
      }
    }
    scheduleVirtPaint();
  }, true);
  els.results.addEventListener("pointerdown", (e) => {
    const btn = e.target.closest(".thumb-btn");
    if (btn?.dataset.img) prefetchLarge(btn.dataset.img);
  });
  els.results.addEventListener("mouseover", (e) => {
    const btn = e.target.closest(".thumb-btn");
    if (btn?.dataset.img) prefetchLarge(btn.dataset.img);
  });
  els.results.addEventListener("click", (e) => {
    if (e.target.closest("a.price-pill")) return;
    const btn = e.target.closest(".thumb-btn");
    if (!btn) return;
    e.preventDefault();
    openLightbox(btn.dataset.img, btn.dataset.cap);
  });
  els.lightboxClose.addEventListener("click", closeLightbox);
  els.lightbox.addEventListener("click", (e) => {
    if (e.target === els.lightbox) closeLightbox();
  });
  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeLightbox();
  });
  const syncBackTop = () => {
    els.backTop.hidden = window.scrollY < 400;
  };
  window.addEventListener(
    "scroll",
    () => {
      syncBackTop();
      scheduleVirtPaint();
    },
    { passive: true },
  );
  window.addEventListener("resize", scheduleVirtPaint, { passive: true });
  els.backTop.addEventListener("click", () => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  });
  syncBackTop();
}

wireEvents();
loadCatalog();
