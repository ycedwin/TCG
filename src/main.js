import "./styles.css";
import {
  buildCatalog,
  loadCachedCatalog,
  saveCachedCatalog,
} from "./beehive.js";

const els = {
  status: document.getElementById("status"),
  refresh: document.getElementById("refresh"),
  search: document.getElementById("search"),
  setSelect: document.getElementById("setSelect"),
  sortSelect: document.getElementById("sortSelect"),
  meta: document.getElementById("meta"),
  results: document.getElementById("results"),
};

/** @type {{ syncedAt: string, rarityOrder: string[], sets: any[], cards: any[] } | null} */
let catalog = null;
let refreshing = false;

function formatHkd(n) {
  if (n == null || Number.isNaN(n)) return "—";
  return `HK$${n.toLocaleString("zh-HK", {
    minimumFractionDigits: n % 1 ? 2 : 0,
    maximumFractionDigits: 2,
  })}`;
}

function formatSyncedAt(iso) {
  if (!iso) return "未知";
  try {
    return new Date(iso).toLocaleString("zh-HK", {
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

function populateSets() {
  const current = els.setSelect.value;
  els.setSelect.innerHTML = `<option value="">全部系列</option>`;
  const frag = document.createDocumentFragment();
  for (const s of catalog.sets) {
    if (!s.count) continue;
    const opt = document.createElement("option");
    opt.value = s.code;
    opt.textContent = `${s.name}（${s.count}）`;
    frag.appendChild(opt);
  }
  els.setSelect.appendChild(frag);
  if ([...els.setSelect.options].some((o) => o.value === current)) {
    els.setSelect.value = current;
  }
}

function matchesQuery(card, q) {
  if (!q) return true;
  const raw = q.trim().toLowerCase();
  if (!raw) return true;

  const hay = [
    card.fullNumber,
    card.number,
    card.name,
    card.title,
    card.set,
    card.rarity,
    `${card.set}-${card.number}`,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();

  const compact = hay.replace(/[\s\-・]/g, "");
  const qCompact = raw.replace(/[\s\-・]/g, "");
  return hay.includes(raw) || compact.includes(qCompact);
}

function sortCards(cards, mode) {
  const copy = cards.slice();
  if (mode === "price-asc") {
    copy.sort((a, b) => (a.priceHkd ?? Infinity) - (b.priceHkd ?? Infinity));
  } else if (mode === "price-desc") {
    copy.sort((a, b) => (b.priceHkd ?? -1) - (a.priceHkd ?? -1));
  } else {
    copy.sort((a, b) =>
      (a.fullNumber || "").localeCompare(b.fullNumber || "", "en"),
    );
  }
  return copy;
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

function render() {
  if (!catalog) return;
  const q = els.search.value;
  const setCode = els.setSelect.value;
  const sort = els.sortSelect.value;

  let cards = catalog.cards;
  if (setCode) cards = cards.filter((c) => c.collection === setCode);
  cards = cards.filter((c) => matchesQuery(c, q));
  cards = sortCards(cards, sort);

  els.meta.textContent = `共 ${cards.length} 張卡 · 更新於 ${formatSyncedAt(catalog.syncedAt)}`;

  if (cards.length === 0) {
    els.results.innerHTML = `<div class="empty">找不到符合條件的卡牌</div>`;
    return;
  }

  const groups = groupByRarity(cards);
  els.results.innerHTML = groups
    .map(([rarity, list], idx) => {
      const items = list
        .map((c) => {
          const img = c.image
            ? `<img class="thumb" src="${c.image}" alt="" loading="lazy" decoding="async" width="56" height="78" />`
            : `<div class="thumb missing">無圖</div>`;
          const headline = c.fullNumber || c.name || c.title;
          const sub =
            c.fullNumber && c.name && c.name !== c.fullNumber
              ? c.name
              : c.collection || "";
          return `<li>
            <a class="card" href="${c.url}" target="_blank" rel="noopener noreferrer">
              ${img}
              <div class="info">
                <div class="num">${escapeHtml(headline)}</div>
                ${sub ? `<p class="name">${escapeHtml(sub)}</p>` : ""}
              </div>
              <div class="price">${formatHkd(c.priceHkd)}</div>
            </a>
          </li>`;
        })
        .join("");
      return `<section class="rarity-block" style="animation-delay:${Math.min(idx, 8) * 0.04}s">
        <div class="rarity-head">
          <h2>${escapeHtml(rarity)}</h2>
          <span>${list.length} 張</span>
        </div>
        <ul class="card-list">${items}</ul>
      </section>`;
    })
    .join("");
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function applyCatalog(next, { sourceLabel, offline = false } = {}) {
  catalog = next;
  populateSets();
  setStatus(
    `${sourceLabel} · ${formatSyncedAt(catalog.syncedAt)}`,
    offline,
  );
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
      sourceLabel: online ? "本機快取" : "離線快取",
      offline: !online,
    });
    return;
  }
  try {
    const bundled = await loadBundledCatalog();
    applyCatalog(bundled, {
      sourceLabel: online ? "內建資料" : "離線 · 內建資料",
      offline: !online,
    });
  } catch (err) {
    setStatus(online ? "載入失敗" : "離線且無快取", !online);
    els.results.innerHTML = `<div class="error">無法載入卡牌資料。<br/><small>${escapeHtml(err.message)}</small></div>`;
  }
}

async function refreshFromBeehive() {
  if (refreshing) return;
  if (!navigator.onLine) {
    setStatus("離線中，無法更新", true);
    return;
  }

  refreshing = true;
  els.refresh.disabled = true;
  els.refresh.classList.add("is-busy");

  try {
    const setsRes = await fetch("./data/sets.json", { cache: "no-cache" });
    if (!setsRes.ok) throw new Error("無法讀取系列清單");
    const sets = await setsRes.json();

    const next = await buildCatalog(sets, {
      onProgress: ({ index, total, code }) => {
        setStatus(`更新中 ${code}（${index}/${total}）…`);
      },
    });

    if (!next.cards.length) throw new Error("沒有抓到卡牌");

    try {
      saveCachedCatalog(next);
    } catch {
      // ponytail: quota full — still show fresh data this session
    }

    applyCatalog(next, { sourceLabel: "已更新自 Beehive" });
  } catch (err) {
    setStatus(`更新失敗：${err.message}`);
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
  els.setSelect.addEventListener("change", render);
  els.sortSelect.addEventListener("change", render);
  els.refresh.addEventListener("click", refreshFromBeehive);
  window.addEventListener("online", () => {
    setStatus(`已連線 · ${formatSyncedAt(catalog?.syncedAt)}`);
  });
  window.addEventListener("offline", () => {
    setStatus(`離線 · 使用快取 ${formatSyncedAt(catalog?.syncedAt)}`, true);
  });
}

wireEvents();
loadCatalog();
