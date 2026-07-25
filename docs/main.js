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
};

let catalog = null;
let setNames = new Map();
let refreshing = false;

/** Hide cheap commons — only show cards above this HKD price */
const MIN_PRICE_HKD = 20;

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

function setLabel(card) {
  return (
    setNames.get(card.collection) ||
    card.collection ||
    card.set ||
    ""
  );
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

function render() {
  if (!catalog) return;
  const q = els.search.value;

  let cards = catalog.cards.filter((c) => matchesQuery(c, q));
  cards = cards.slice().sort((a, b) =>
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
          const img = c.image
            ? `<img class="thumb" src="${c.image}" alt="" loading="lazy" decoding="async" width="56" height="78" />`
            : `<div class="thumb missing">No art</div>`;
          const headline = c.fullNumber || c.name || c.title;
          const name =
            c.fullNumber && c.name && c.name !== c.fullNumber ? c.name : "";
          const set = setLabel(c);
          return `<li>
            <a class="card" href="${c.url}" target="_blank" rel="noopener noreferrer">
              ${img}
              <div class="info">
                <div class="num">${escapeHtml(headline)}</div>
                ${name ? `<p class="name">${escapeHtml(name)}</p>` : ""}
                ${set ? `<p class="set">${escapeHtml(set)}</p>` : ""}
              </div>
              <div class="price">${formatHkd(c.priceHkd)}</div>
            </a>
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

function applyCatalog(next, { sourceLabel, offline = false } = {}) {
  catalog = filterCatalog(next);
  setNames = new Map((catalog.sets || []).map((s) => [s.code, s.name]));
  setStatus(`${sourceLabel} · ${formatSyncedAt(catalog.syncedAt)}`, offline);
  render();
}

async function loadBundledCatalog() {
  const res = await fetch("./data/catalog.json", { cache: "no-cache" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function loadCatalog() {
  const online = navigator.onLine;
  const cached = loadCachedCatalog();
  if (cached?.cards?.length) {
    applyCatalog(cached, {
      sourceLabel: online ? "Local cache" : "Offline cache",
      offline: !online,
    });
    return;
  }
  try {
    const bundled = await loadBundledCatalog();
    applyCatalog(bundled, {
      sourceLabel: online ? "Bundled data" : "Offline · bundled",
      offline: !online,
    });
  } catch (err) {
    setStatus(online ? "Load failed" : "Offline · no cache", !online);
    els.results.innerHTML = `<div class="error">Could not load card data.<br/><small>${escapeHtml(err.message)}</small></div>`;
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
    const setsRes = await fetch("./data/sets.json", { cache: "no-cache" });
    if (!setsRes.ok) throw new Error("Could not load set list");
    const sets = await setsRes.json();

    const next = await buildCatalog(sets, {
      onProgress: ({ index, total, code }) => {
        setStatus(`Refreshing ${code} (${index}/${total})…`);
      },
    });

    if (!next.cards.length) throw new Error("No cards returned");

    try {
      saveCachedCatalog(next);
    } catch {
      // ponytail: quota full — still show fresh data this session
    }

    applyCatalog(next, { sourceLabel: "Updated from Beehive" });
  } catch (err) {
    setStatus(`Refresh failed: ${err.message}`);
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
  window.addEventListener("online", () => {
    setStatus(`Online · ${formatSyncedAt(catalog?.syncedAt)}`);
  });
  window.addEventListener("offline", () => {
    setStatus(`Offline · cache ${formatSyncedAt(catalog?.syncedAt)}`, true);
  });
}

wireEvents();
loadCatalog();
