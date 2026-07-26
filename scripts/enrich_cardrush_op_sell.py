#!/usr/bin/env python3
"""Match Card Rush sell prices onto docs/data/cardrush-op-buy.json.

Match key: fullName + rarity + modelNumber (exact).
Skip: condition (〔状態…〕), PSA/鑑定, sealed/opened, non-JP.
Rules:
  - unique clean hit → sellYen + sellUrl
  - no hit → sellYen = 0
  - multiple hits → do NOT set price; write review list for manual pick
"""

from __future__ import annotations

import json
import re
import subprocess
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
BUY_JSON = ROOT / "docs/data/cardrush-op-buy.json"
REVIEW_JSON = ROOT / "docs/data/cardrush-op-sell-review.json"
CACHE_DIR = ROOT / "scripts/.cache/cardrush-sell"
SELL_SEARCH = "https://www.cardrush-op.jp/product-list"

SKIP_RE = re.compile(
    r"^〔|PSA|ARS|BGS|鑑定|状態|"
    r"英語|中国|Asia|ASIA|France|フランス|ドジャース|GREVIN|English|China|"
    r"未開封|開封|デッキ販売"
)
TITLE_RE = re.compile(r"^(?:☆SALE☆)?(.+?)【([^】]+)】\{([^}]+)\}$")
PAGE_RE = re.compile(r"[?&]page=(\d+)|product-list/(\d+)\?")


def curl(url: str) -> str:
    return subprocess.check_output(
        ["curl", "-sL", "-A", "Mozilla/5.0", "--max-time", "60", url],
        text=True,
    )


def search_url(keyword: str, page: int = 1) -> str:
    q = quote(keyword, safe="")
    url = f"{SELL_SEARCH}?keyword={q}&num=100"
    if page > 1:
        url += f"&page={page}"
    return url


def parse_listings(html: str) -> list[dict]:
    out: list[dict] = []
    for block in re.split(r'<li class="list_item_cell', html)[1:]:
        alt_m = re.search(r'alt="([^"]+)"', block)
        price_m = re.search(r'class="figure">([\d,]+)円', block)
        pid_m = re.search(r'data-product-id="(\d+)"', block)
        if not (alt_m and price_m and pid_m):
            continue
        raw = alt_m.group(1).strip()
        if SKIP_RE.search(raw):
            continue
        m = TITLE_RE.match(raw)
        if not m:
            continue
        out.append(
            {
                "fullName": m.group(1),
                "rarity": m.group(2),
                "modelNumber": m.group(3),
                "sellYen": int(price_m.group(1).replace(",", "")),
                "url": f"https://www.cardrush-op.jp/product/{pid_m.group(1)}",
                "raw": raw,
            }
        )
    return out


def max_page(html: str) -> int:
    pages = {1}
    for a, b in PAGE_RE.findall(html):
        n = a or b
        if n.isdigit():
            pages.add(int(n))
    # also 「135» style pager links with page=
    for n in re.findall(r"[?&]page=(\d+)", html):
        pages.add(int(n))
    return max(pages)


def fetch_keyword(keyword: str, sleep_s: float = 0.15) -> list[dict]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    # ponytail: filename-safe cache key; ceiling = collision if two kws normalize same
    safe = re.sub(r"[^\w.\-]+", "_", keyword)[:180] or "empty"
    cache = CACHE_DIR / f"{safe}.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))

    html = curl(search_url(keyword, 1))
    time.sleep(sleep_s)
    listings = parse_listings(html)
    last = max_page(html)
    for p in range(2, last + 1):
        html = curl(search_url(keyword, p))
        time.sleep(sleep_s)
        listings.extend(parse_listings(html))

    # de-dupe by product url
    seen: set[str] = set()
    uniq: list[dict] = []
    for it in listings:
        if it["url"] in seen:
            continue
        seen.add(it["url"])
        uniq.append(it)

    cache.write_text(json.dumps(uniq, ensure_ascii=False), encoding="utf-8")
    return uniq


def search_keyword_for(card: dict) -> str:
    if card.get("modelNumber") == "don" or "ドン!!" in (card.get("name") or ""):
        return card["fullName"]
    return card["modelNumber"]


def match_key(c: dict) -> tuple[str, str, str]:
    return (c["fullName"], c["rarity"], c["modelNumber"])


def main() -> None:
    data = json.loads(BUY_JSON.read_text(encoding="utf-8"))
    cards: list[dict] = data["cards"]

    by_kw: dict[str, list[dict]] = defaultdict(list)
    for c in cards:
        by_kw[search_keyword_for(c)].append(c)

    print(f"buy cards={len(cards)} search keywords={len(by_kw)}")

    # keyword → listings
    listings_by_kw: dict[str, list[dict]] = {}
    for i, kw in enumerate(sorted(by_kw), 1):
        listings_by_kw[kw] = fetch_keyword(kw)
        if i % 50 == 0 or i == len(by_kw):
            print(f"  fetched {i}/{len(by_kw)} keywords")

    unique = ambiguous = none = 0
    review: list[dict] = []

    for c in cards:
        # clear previous enrich fields
        c.pop("sellYen", None)
        c.pop("sellUrl", None)
        c.pop("sellMatch", None)

        kw = search_keyword_for(c)
        listings = listings_by_kw.get(kw) or []
        key = match_key(c)
        hits = [x for x in listings if match_key(x) == key]
        # Prefer normal listing when ☆SALE☆ + normal both match after strip
        if len(hits) > 1:
            normal = [h for h in hits if not str(h.get("raw", "")).startswith("☆SALE☆")]
            if len(normal) == 1:
                hits = normal

        if len(hits) == 1:
            c["sellYen"] = hits[0]["sellYen"]
            c["sellUrl"] = hits[0]["url"]
            c["sellMatch"] = "unique"
            unique += 1
        elif len(hits) == 0:
            c["sellYen"] = 0
            c["sellUrl"] = None
            c["sellMatch"] = "none"
            none += 1
        else:
            # leave price unset for manual review
            c["sellMatch"] = "ambiguous"
            ambiguous += 1
            review.append(
                {
                    "buyId": c.get("id"),
                    "fullName": c["fullName"],
                    "rarity": c["rarity"],
                    "modelNumber": c["modelNumber"],
                    "buyYen": c["buyYen"],
                    "candidates": [
                        {
                            "sellYen": h["sellYen"],
                            "url": h["url"],
                            "raw": h["raw"],
                        }
                        for h in sorted(hits, key=lambda x: x["sellYen"])
                    ],
                }
            )

    data["sellSyncedAt"] = (
        datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )
    data["sellSource"] = SELL_SEARCH
    data["sellCounts"] = {
        "unique": unique,
        "none": none,
        "ambiguous": ambiguous,
    }
    note = data.get("note") or ""
    if "Sell prices" not in note:
        data["note"] = (
            note
            + " Sell prices from cardrush-op.jp (clean JP only; "
            "ambiguous matches left unset — see cardrush-op-sell-review.json)."
        ).strip()

    BUY_JSON.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    REVIEW_JSON.write_text(
        json.dumps(
            {
                "syncedAt": data["sellSyncedAt"],
                "count": len(review),
                "note": (
                    "Multiple clean JP sell listings matched the same "
                    "fullName+rarity+modelNumber. Pick one; then set sellYen/sellUrl."
                ),
                "items": review,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        f"wrote {BUY_JSON.name}: unique={unique} none={none} ambiguous={ambiguous}"
    )
    print(f"wrote {REVIEW_JSON.name}: {len(review)} items")

    # ponytail: smallest check — Hancock gold alt unique + no dirty sellMatch
    h = next(
        c
        for c in cards
        if c["modelNumber"] == "OP07-038"
        and "金文字/アニメイラスト" in c["fullName"]
    )
    assert h.get("sellMatch") == "unique" and (h.get("sellYen") or 0) > 0
    assert all(c.get("sellMatch") in ("unique", "none", "ambiguous") for c in cards)
    assert sum(1 for c in cards if c.get("sellMatch") == "ambiguous") == len(review)
    print("self-check ok")


if __name__ == "__main__":
    main()
