#!/usr/bin/env python3
"""Dry-run: Card Rush Pokémon buy → Beehive match report (no enrich)."""

from __future__ import annotations

import json
import re
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
BH = ROOT / "docs/data/pkmjp-buylist.json"
CACHE = ROOT / "scripts/.cache/cardrush-pkm-buy-raw.json"
OUT = ROOT / "docs/data/cardrush-pkm-buy-review.json"
SOURCE = "https://cardrush.media/pokemon/buying_prices"

MIN_YEN = 200
MAX_YEN = 300_000  # exclusive

SKIP_RE = re.compile(
    r"状態|PSA|ARS|BGS|鑑定|未開封|開封|"
    r"英語版|中国版|英語|中国|Asia|ASIA|France|フランス"
)

DISPLAY_CATS = ("最新弾", "スタンダード", "エクストラ", "旧裏")


def curl(url: str) -> str:
    return subprocess.check_output(
        ["curl", "-sL", "-A", "Mozilla/5.0", "--max-time", "90", url],
        text=True,
    )


def page_url(page: int, limit: int = 100) -> str:
    cats = "".join(f"&display_category%5B%5D={quote(c)}" for c in DISPLAY_CATS)
    return (
        f"{SOURCE}?"
        f"displayMode={quote('リスト')}&limit={limit}&page={page}"
        "&sort%5Bkey%5D=amount&sort%5Border%5D=desc"
        "&associations%5B%5D=ocha_product"
        "&to_json_option%5Bexcept%5D%5B%5D=original_image_source"
        "&to_json_option%5Bexcept%5D%5B%5D=created_at"
        "&to_json_option%5Binclude%5D%5Bocha_product%5D%5Bonly%5D%5B%5D=id"
        "&to_json_option%5Binclude%5D%5Bocha_product%5D%5Bmethods%5D%5B%5D=image_source"
        f"{cats}"
    )


def fetch_page(page: int) -> tuple[list[dict], int]:
    html = curl(page_url(page))
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html)
    if not m:
        raise RuntimeError(f"no __NEXT_DATA__ on page {page}")
    pp = json.loads(m.group(1))["props"]["pageProps"]
    return pp["buyingPrices"], int(pp["lastPage"])


def hay(it: dict) -> str:
    return " ".join(
        [
            it.get("name") or "",
            it.get("extra_difference") or "",
            it.get("searchable_name") or "",
            it.get("pack_code") or "",
            it.get("model_number") or "",
        ]
    )


def norm_model(mn: str) -> str:
    """132/106 or 026/PLAY → keep; pad card# to 3 when numeric/numeric."""
    mn = (mn or "").strip()
    m = re.fullmatch(r"(\d+)/(\d+|[A-Za-z0-9-]+)", mn)
    if not m:
        return mn
    left, right = m.group(1), m.group(2)
    if right.isdigit():
        return f"{int(left):03d}/{int(right):03d}"
    return f"{int(left):03d}/{right}"


def bh_key(c: dict) -> tuple[str, str, str]:
    return (
        (c.get("set") or "").upper(),
        norm_model(f"{c['number']}/{c['setSize']}"),
        (c.get("rarity") or "").strip() or "-",
    )


def cr_key(it: dict) -> tuple[str, str, str] | None:
    pack = (it.get("pack_code") or "").strip().upper()
    mn = norm_model(it.get("model_number") or "")
    rar = (it.get("rarity") or "").strip() or "-"
    if not pack or pack in ("その他", "OTHER") or mn in ("", "-", "旧裏"):
        return None
    return pack, mn, rar


def load_or_fetch() -> list[dict]:
    if CACHE.exists():
        raw = json.loads(CACHE.read_text(encoding="utf-8"))
        print(f"cache hit {CACHE} · {len(raw['items'])} items")
        return raw["items"]

    items, last = fetch_page(1)
    all_items = list(items)
    print(f"page 1/{last}: {len(all_items)}")
    for p in range(2, last + 1):
        batch, _ = fetch_page(p)
        all_items.extend(batch)
        if p % 20 == 0 or p == last:
            print(f"page {p}/{last}: total {len(all_items)}")

    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(
        json.dumps(
            {
                "syncedAt": datetime.now(timezone.utc)
                .isoformat()
                .replace("+00:00", "Z"),
                "items": all_items,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"cached {CACHE}")
    return all_items


def main() -> None:
    bh_cards = json.loads(BH.read_text(encoding="utf-8"))["cards"]
    modern_sets = {c["set"].upper() for c in bh_cards}
    by_bh: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for c in bh_cards:
        by_bh[bh_key(c)].append(c)

    counts: Counter[str] = Counter()
    # key -> list of CR rows (after filters)
    cr_by_key: dict[tuple[str, str, str], list[dict]] = defaultdict(list)

    for it in load_or_fetch():
        counts["fetched"] += 1
        amount = int(it.get("amount") or 0)
        if amount < MIN_YEN or amount >= MAX_YEN:
            counts["price"] += 1
            continue
        if SKIP_RE.search(hay(it)):
            counts["skip"] += 1
            continue
        key = cr_key(it)
        if key is None:
            counts["no_pack"] += 1
            continue
        pack, _, _ = key
        if pack not in modern_sets:
            counts["not_modern"] += 1
            continue
        counts["kept"] += 1
        cr_by_key[key].append(
            {
                "id": it.get("id"),
                "name": it.get("name"),
                "extra": (it.get("extra_difference") or "").strip(),
                "rarity": key[2],
                "modelNumber": key[1],
                "set": pack,
                "packName": it.get("pack_name"),
                "buyYen": amount,
            }
        )

    unique: list[dict] = []
    multiple: list[dict] = []
    no_bh: list[dict] = []

    for key, rows in sorted(cr_by_key.items(), key=lambda kv: -max(r["buyYen"] for r in kv[1])):
        pack, model, rar = key
        rows = sorted(rows, key=lambda r: -r["buyYen"])
        bh_hits = by_bh.get(key) or []
        entry = {
            "set": pack,
            "modelNumber": model,
            "rarity": rar,
            "printId": f"{pack} {model}",
            "crCount": len(rows),
            "buyYen": [r["buyYen"] for r in rows],
            "extras": [r["extra"] for r in rows],
            "names": list({r["name"] for r in rows if r["name"]}),
            "bhTitles": [c.get("title") for c in bh_hits],
            "bhBuyHkd": [c.get("buyHkd") for c in bh_hits],
            "rows": rows,
        }
        if not bh_hits:
            no_bh.append(entry)
            counts["cr_no_bh"] += 1
        elif len(rows) == 1:
            unique.append(entry)
            counts["unique"] += 1
        else:
            multiple.append(entry)
            counts["multiple"] += 1

    # Beehive cards with no CR
    bh_miss = 0
    for key, cards in by_bh.items():
        if key not in cr_by_key:
            bh_miss += len(cards)
    counts["bh_no_cr"] = bh_miss
    counts["bh_total"] = len(bh_cards)
    counts["cr_keys"] = len(cr_by_key)

    out = {
        "syncedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": SOURCE,
        "currency": "JPY",
        "note": (
            "Dry-run only — not enriched. "
            f"Match key: pack_code + number/setSize + rarity. "
            f"Kept ¥{MIN_YEN}–<{MAX_YEN}. "
            "Skipped 未開封/開封/非日本語/PSA. Modern packs = sets in Beehive buylist."
        ),
        "counts": dict(counts),
        "multiple": multiple,
        "uniqueSample": unique[:30],
        "noBhSample": no_bh[:30],
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print("--- summary ---")
    for k, v in counts.most_common():
        print(f"  {k}: {v}")
    print(f"unique enrichable keys: {len(unique)}")
    print(f"multiple CR prices (list below / in file): {len(multiple)}")
    print(f"CR modern keys with no Beehive row: {len(no_bh)}")
    print(f"wrote {OUT}")

    print("\n=== MULTIPLE prices (same set+number+rarity) ===")
    for e in multiple[:80]:
        yen = ", ".join(f"¥{y}" for y in e["buyYen"])
        extras = " | ".join(x or "(blank)" for x in e["extras"])
        print(f"{e['printId']} {e['rarity']}  {yen}")
        print(f"  extras: {extras}")
        print(f"  names: {', '.join(e['names'])}")
        if e["bhTitles"]:
            print(f"  bh: {e['bhTitles'][0]}")


if __name__ == "__main__":
    main()
