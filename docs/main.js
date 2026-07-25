import {
  buildCatalog,
  loadCachedCatalog,
  saveCachedCatalog,
} from "./beehive.js";

const els = {
  status: document.getElementById("status"),
  refresh: document.getElementById("refresh"),
  search: document.getElementById("search"),
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
let refreshing = false;

/** Hide cheap commons — only show cards above this HKD price */
const MIN_PRICE_HKD = 50;

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

/** Character popularity tier (not price) */
function popularityTier(card) {
  if (!tierMatchers) tierMatchers = buildTierMatchers();
  const hay = normalizeName(
    [card.nameEn, card.name, card.title].filter(Boolean).join(" "),
  );
  if (!hay) return { tier: "C", label: "Tier C" };
  for (const { tier, key } of tierMatchers) {
    if (hay.includes(key)) return { tier, label: `Tier ${tier}` };
  }
  return { tier: "C", label: "Tier C" };
}

function filterCatalog(raw) {
  const cards = (raw.cards || []).filter(
    (c) => c.priceHkd != null && c.priceHkd > MIN_PRICE_HKD,
  );
  const countBySet = new Map();
  for (const c of cards) {
    countBySet.set(c.collection, (countBySet.get(c.collection) || 0) + 1);
  }
  const sets = (raw.sets || [])
    .map((s) => ({ ...s, count: countBySet.get(s.code) || 0 }))
    .filter((s) => s.count > 0);
  return { ...raw, cards, sets };
}

function enrichRaw(raw) {
  return {
    ...raw,
    cards: (raw.cards || []).map((c) => ({
      ...c,
      nameEn: c.nameEn || namesEn[c.fullNumber] || "",
    })),
  };
}

function formatHkd(n) {
  if (n == null || Number.isNaN(n)) return "—";
  return `HK$${n.toLocaleString("en-HK", {
    minimumFractionDigits: n % 1 ? 2 : 0,
    maximumFractionDigits: 2,
  })}`;
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
    u.searchParams.set("width", "800");
    return u.toString();
  } catch {
    return src;
  }
}

function matchesQuery(card, q) {
  if (!q) return true;
  const raw = q.trim().toLowerCase();
  if (!raw) return true;
  const hay = [card.fullNumber, card.number, `${card.set}-${card.number}`]
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
  const full = largeImageUrl(thumbSrc);
  els.lightboxImg.src = full || thumbSrc;
  els.lightboxCap.textContent = caption || "";
  if (typeof els.lightbox.showModal === "function") {
    els.lightbox.showModal();
  } else {
    els.lightbox.setAttribute("open", "");
  }
}

function closeLightbox() {
  if (typeof els.lightbox.close === "function") {
    els.lightbox.close();
  } else {
    els.lightbox.removeAttribute("open");
  }
  els.lightboxImg.removeAttribute("src");
}

function render() {
  if (!catalog) return;
  const q = els.search.value;

  let cards = catalog.cards.filter((c) => matchesQuery(c, q));
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
          const setNo = c.collection || c.set || "";
          const en = c.nameEn || "";
          const { tier, label } = popularityTier(c);
          const thumb = c.image
            ? `<button type="button" class="thumb-btn" data-img="${escapeHtml(c.image)}" data-cap="${escapeHtml(`${cardNo}${en ? " · " + en : ""}`)}" aria-label="Enlarge card art">
                <img class="thumb" src="${c.image}" alt="" loading="lazy" decoding="async" width="56" height="78" />
              </button>`
            : `<div class="thumb missing">No art</div>`;
          return `<li class="card-row">
            ${thumb}
            <div class="card-main">
              <div class="info">
                <div class="num-row">
                  <span class="num">${escapeHtml(cardNo)}</span>
                  <span class="tier tier-${tier}" title="Character popularity">${escapeHtml(label)}</span>
                </div>
                ${setNo ? `<p class="set">${escapeHtml(setNo)}</p>` : ""}
                ${en ? `<p class="name">${escapeHtml(en)}</p>` : ""}
              </div>
              <div class="price">${formatHkd(c.priceHkd)}</div>
            </div>
          </li>`;
        })
        .join("");
      return `<section class="rarity-block" style="animation-delay:${Math.min(idx, 8) * 0.04}s">
        <div class="rarity-head">
          <h2>${escapeHtml(rarity)}</h2>
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
  const [namesRes, setsRes, tiersRes] = await Promise.all([
    fetch("./data/names-en.json"),
    fetch("./data/sets.json"),
    fetch("./data/character-tiers.json"),
  ]);
  if (namesRes.ok) namesEn = await namesRes.json();
  if (setsRes.ok) setsMeta = await setsRes.json();
  if (tiersRes.ok) {
    characterTiers = await tiersRes.json();
    tierMatchers = null;
  }
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

function wireEvents() {
  let t = 0;
  els.search.addEventListener("input", () => {
    clearTimeout(t);
    t = setTimeout(render, 120);
  });
  els.refresh.addEventListener("click", refreshFromBeehive);
  els.results.addEventListener("click", (e) => {
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
