#!/usr/bin/env python3
"""Fetch Beehive Pokemon JP buylist (category pkmjp) into a buy-only catalog."""

from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/data/pkmjp-buylist.json"
CATEGORY = 1451
MIN_BUY_HKD = 5
# M5 111/081 ムク SR (回收)
CARD_RE = re.compile(
    r"^([A-Za-z0-9]+)\s+(\d{1,3})/(\d{1,3})\s+(.+?)\s+(\S+)\s*\(回收\)\s*$"
)


def curl(url: str) -> str:
    return subprocess.check_output(
        ["curl", "-sL", "-A", "Mozilla/5.0", url],
        text=True,
    )


def fetch_all() -> list[dict]:
    allp: list[dict] = []
    page = 1
    while True:
        url = (
            "https://beehivetcgbuylist.com/wp-json/wc/store/v1/products"
            f"?category={CATEGORY}&per_page=100&page={page}"
        )
        batch = json.loads(curl(url))
        allp.extend(batch)
        print(f"page {page}: {len(batch)} (total {len(allp)})")
        if len(batch) < 100:
            break
        page += 1
    return allp


def attr_rarity(p: dict) -> str:
    for a in p.get("attributes") or []:
        if a.get("taxonomy") == "pa_rarity":
            terms = a.get("terms") or []
            if terms:
                return (terms[0].get("name") or "").strip()
    return ""


def price_of(p: dict) -> float:
    prices = p.get("prices") or {}
    minor = int(prices.get("currency_minor_unit") or 2)
    return int(prices.get("price") or 0) / (10**minor)


def image_of(p: dict) -> str:
    imgs = p.get("images") or []
    if not imgs:
        return ""
    src = (imgs[0].get("src") or "").strip()
    # Unwrap WordPress.com Photon CDN → origin file for clearer enlarge
    # https://i0.wp.com/host/path?fit=... → https://host/path
    if "://i" in src and ".wp.com/" in src:
        try:
            from urllib.parse import urlparse

            path = urlparse(src).path.lstrip("/")
            if "/" in path:
                return "https://" + path
        except Exception:
            pass
    return src.split("?", 1)[0] if src else ""


def parse_card(name: str, attr: str) -> dict | None:
    n = (
        name.replace("&#8211;", "-")
        .replace("–", "-")
        .replace("—", "-")
        .replace("－", "-")
        .strip()
    )
    m = CARD_RE.match(n)
    if not m:
        return None
    set_code = m.group(1).upper()
    number = m.group(2).zfill(3) if len(m.group(2)) < 3 else m.group(2)
    set_size = m.group(3).zfill(3) if len(m.group(3)) < 3 else m.group(3)
    card_name = m.group(4).strip()
    rarity = (attr or m.group(5) or "").strip()
    if not rarity or rarity in ("-", "?"):
        return None
    return {
        "set": set_code,
        "number": number,
        "setSize": set_size,
        "fullNumber": f"{set_code}-{number}",
        "printId": f"{set_code} {number}/{set_size}",
        "name": card_name,
        "rarity": rarity,
    }


def main() -> None:
    allp = fetch_all()
    cards: list[dict] = []
    skipped = {"bulk": 0, "paused": 0, "cheap": 0, "parse": 0}

    for p in allp:
        name = p.get("name") or ""
        if re.search(r"Test for WooCommerce|大量回收|任何", name, re.I):
            skipped["bulk"] += 1
            continue
        text = (p.get("add_to_cart") or {}).get("text") or ""
        if "暫停回收" in text:
            skipped["paused"] += 1
            continue
        buy_hkd = price_of(p)
        if buy_hkd < MIN_BUY_HKD:
            skipped["cheap"] += 1
            continue
        parsed = parse_card(name, attr_rarity(p))
        if not parsed:
            skipped["parse"] += 1
            continue
        cards.append(
            {
                **parsed,
                "buyHkd": buy_hkd,
                "url": p.get("permalink") or "",
                "image": image_of(p),
                "title": name.replace("&#8211;", "–"),
            }
        )

    # Dedupe by set+number+rarity; keep higher buy price
    by_key: dict[str, dict] = {}
    for c in cards:
        key = f"{c['fullNumber']}|{c['rarity']}"
        prev = by_key.get(key)
        if not prev or c["buyHkd"] > prev["buyHkd"]:
            by_key[key] = c
    cards = sorted(
        by_key.values(),
        key=lambda c: (-c["buyHkd"], c["fullNumber"], c["rarity"]),
    )

    rarity_order = []
    seen = set()
    for c in cards:
        r = c["rarity"]
        if r not in seen:
            seen.add(r)
            rarity_order.append(r)

    out = {
        "syncedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": "https://beehivetcgbuylist.com/product-category/pkmjp/",
        "currency": "HKD",
        "note": f"Buy-only Pokemon JP. Skipped buy<{MIN_BUY_HKD} and 暫停回收.",
        "counts": {
            "fetched": len(allp),
            **skipped,
            "kept": len(cards),
        },
        "rarityOrder": rarity_order,
        "cards": cards,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(out, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(json.dumps(out["counts"], indent=2, ensure_ascii=False))
    print(f"wrote {OUT}")
    # English names, then Hareruya JPY buy prices
    enrich = ROOT / "scripts/enrich_pkmjp_names.py"
    if enrich.exists():
        subprocess.check_call(["python3", str(enrich)])
    hr = ROOT / "scripts/sync_hareruya_buylist.py"
    if hr.exists():
        subprocess.check_call(["python3", str(hr)])
    cr = ROOT / "scripts/enrich_cardrush_pkm_buy.py"
    if cr.exists():
        subprocess.check_call(["python3", str(cr)])
    cr_sell = ROOT / "scripts/enrich_cardrush_pkm_sell.py"
    if cr_sell.exists():
        # needs curl_cffi (Frameworks 3.14 on this machine)
        py = "/Library/Frameworks/Python.framework/Versions/3.14/bin/python3"
        subprocess.check_call([py if Path(py).exists() else "python3", str(cr_sell)])


if __name__ == "__main__":
    main()
