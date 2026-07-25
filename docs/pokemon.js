const els = {
  status: document.getElementById("status"),
  refresh: document.getElementById("refresh"),
  search: document.getElementById("search"),
  priceToggle: document.getElementById("priceToggle"),
  priceFilters: document.getElementById("priceFilters"),
  buyMin: document.getElementById("buyMin"),
  buyMax: document.getElementById("buyMax"),
  meta: document.getElementById("meta"),
  results: document.getElementById("results"),
  lightbox: document.getElementById("lightbox"),
  lightboxImg: document.getElementById("lightboxImg"),
  lightboxCap: document.getElementById("lightboxCap"),
  lightboxClose: document.getElementById("lightboxClose"),
};

/** Prefer high-end rarities first; unknowns follow alphabetically */
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
  "R",
  "U",
  "C",
];

let catalog = null;
let refreshing = false;

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
    card.title,
    card.rarity,
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
  const buy = card.buyHkd;
  if (buyMin != null && (buy == null || buy < buyMin)) return false;
  if (buyMax != null && (buy == null || buy > buyMax)) return false;
  return true;
}

function rarityRank(code) {
  const i = RARITY_RANK.indexOf(code);
  return i === -1 ? 500 : i;
}

function groupByRarity(cards) {
  const map = new Map();
  for (const c of cards) {
    const key = c.rarity || "?";
    if (!map.has(key)) map.set(key, []);
    map.get(key).push(c);
  }
  const order = catalog?.rarityOrder || [];
  const keys = [...map.keys()].sort((a, b) => {
    const ra = rarityRank(a);
    const rb = rarityRank(b);
    if (ra !== rb) return ra - rb;
    const ia = order.indexOf(a);
    const ib = order.indexOf(b);
    if (ia !== -1 || ib !== -1) {
      if (ia === -1) return 1;
      if (ib === -1) return -1;
      return ia - ib;
    }
    return a.localeCompare(b);
  });
  return keys.map((k) => [k, map.get(k)]);
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

function render() {
  if (!catalog) return;
  const q = els.search.value;
  let cards = (catalog.cards || []).filter(
    (c) => matchesQuery(c, q) && matchesPriceFilters(c),
  );
  cards = cards
    .slice()
    .sort(
      (a, b) =>
        (b.buyHkd || 0) - (a.buyHkd || 0) ||
        (a.fullNumber || "").localeCompare(b.fullNumber || "", "en"),
    );

  els.meta.textContent = `${cards.length} cards · buy only · updated ${formatSyncedAt(catalog.syncedAt)}`;

  if (cards.length === 0) {
    els.results.innerHTML = `<div class="empty">No cards match your search</div>`;
    return;
  }

  const groups = groupByRarity(cards);
  els.results.innerHTML = groups
    .map(([rarity, list], idx) => {
      const items = list
        .map((c) => {
          const cardNo = c.printId || c.fullNumber || "";
          const setCode = c.set || "";
          const name = c.nameEn || c.name || "";
          const thumb = c.image
            ? `<button type="button" class="thumb-btn" data-img="${escapeHtml(c.image)}" data-cap="${escapeHtml(`${cardNo}${name ? " · " + name : ""}`)}" aria-label="Enlarge card art">
                <img class="thumb" src="${escapeHtml(c.image)}" alt="" loading="lazy" decoding="async" width="56" height="78" />
              </button>`
            : `<div class="thumb missing">No art</div>`;
          const buyUrl = (c.url || "").trim();
          const buyPill = buyUrl
            ? `<a class="price-pill price-buy" href="${escapeHtml(buyUrl)}" target="_blank" rel="noopener noreferrer" title="Open Beehive buylist product">
                <span class="lbl">Buy(beehive)</span>
                <span class="amt">${formatHkd(c.buyHkd)}</span>
              </a>`
            : `<div class="price-pill price-buy" title="Buy price">
                <span class="lbl">Buy(beehive)</span>
                <span class="amt">${formatHkd(c.buyHkd)}</span>
              </div>`;
          return `<li class="card-row">
            ${thumb}
            <div class="card-main">
              <div class="info">
                <div class="num-row">
                  <span class="num">${escapeHtml(cardNo)}</span>
                </div>
                ${setCode ? `<p class="set">${escapeHtml(setCode)}</p>` : ""}
                ${name ? `<p class="name">${escapeHtml(name)}</p>` : ""}
              </div>
              <div class="price">${buyPill}</div>
            </div>
          </li>`;
        })
        .join("");
      return `<section class="rarity-block" style="animation-delay:${Math.min(idx, 8) * 0.04}s">
        <div class="rarity-head">
          <div class="rarity-title">
            <h2>${escapeHtml(rarity)}</h2>
          </div>
          <span>${list.length}</span>
        </div>
        <ul class="card-list">${items}</ul>
      </section>`;
    })
    .join("");
}

async function loadCatalog({ bust = false } = {}) {
  const url = bust
    ? `./data/pkmjp-buylist.json?v=${Date.now()}`
    : "./data/pkmjp-buylist.json?v=32";
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

async function refresh() {
  if (refreshing) return;
  refreshing = true;
  els.refresh.disabled = true;
  els.refresh.classList.add("is-busy");
  try {
    await loadCatalog({ bust: true });
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
  els.priceToggle.addEventListener("click", () => {
    const open = els.priceFilters.hidden;
    els.priceFilters.hidden = !open;
    els.priceToggle.setAttribute("aria-expanded", open ? "true" : "false");
    if (open) els.buyMin.focus();
  });
  els.refresh.addEventListener("click", refresh);
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
}

wireEvents();
loadCatalog();
