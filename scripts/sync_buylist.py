#!/usr/bin/env python3
"""Fetch Beehive OPCG buylist; match sell catalog by card number + rarity."""

from __future__ import annotations

import json
import re
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "docs/data/catalog.json"
OUT_MATCHED = ROOT / "docs/data/buylist.json"
OUT_UNMATCHED = ROOT / "docs/data/buylist-unmatched.json"
CATEGORY = 1599
CARD_RE = re.compile(
    r"(?<![A-Z0-9])((?:OP|EB|ST)\d{2}|PRB\d{2}|P)-(\d{3})(?!\d)",
    re.I,
)
# Prefer longer rarity tokens first
RARITY_TOKEN_RE = re.compile(
    r"\b("
    r"P-SECP|P-SRP|P-SEC|P-SR|P-RP|P-R|P-UC|P-C|P-L|P-P|"
    r"SP-金|SP-銀|SP|SEC|SR|UC|C|R|L|TR|DON|"
    r"P"
    r")\b"
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


def parse_number(name: str) -> str | None:
    s = name.replace("＿", "-").replace("_", "-").replace("&#8211;", "-")
    matches = list(CARD_RE.finditer(s))
    if not matches:
        return None
    m = matches[-1]
    return f"{m.group(1).upper()}-{m.group(2)}"


def attr_rarity(p: dict) -> str:
    for a in p.get("attributes") or []:
        if a.get("taxonomy") == "pa_rarity":
            terms = a.get("terms") or []
            if terms:
                return (terms[0].get("name") or "").strip()
    return ""


def normalize_buy_rarity(name: str, attr: str) -> str:
    n = (
        name.replace("&#8211;", "–")
        .replace("–", "-")
        .replace("—", "-")
        .replace("－", "-")
    )
    is_don_card = "ドン!!" in n or "ドン！！" in n or re.search(
        r"ドン!!?\s*カード", n
    )

    if is_don_card:
        if "金邊" in n or attr in ("DON-金邊", "- 金邊", "金邊"):
            return "DON-金邊"
        if "有紋" in n or attr == "DON-有紋":
            return "DON-有紋"
        return "DON"

    # SP gold / silver from title (attr is often just SP)
    if re.search(r"\bSP\s*-\s*金\b", n) or re.search(r"\bSP\s*金\b", n):
        return "SP-金"
    if re.search(r"\bSP\s*-\s*銀\b", n) or re.search(r"\bSP\s*銀\b", n):
        return "SP-銀"

    a = (attr or "").strip()
    if a and a not in ("-", "?", "- 金邊", "金邊", "One Piece 大量回收"):
        # Don't trust attr DON unless it's actually a DON card
        if a.startswith("DON"):
            pass
        else:
            return a

    m = RARITY_TOKEN_RE.search(n)
    return m.group(1) if m else (a if a not in ("-", "?") else "")


def price_of(p: dict) -> float:
    prices = p.get("prices") or {}
    minor = int(prices.get("currency_minor_unit") or 2)
    return int(prices.get("price") or 0) / (10**minor)


def sell_key(card: dict) -> tuple[str, str] | None:
    if card.get("set") and card.get("number"):
        fn = f"{card['set']}-{card['number']}"
    else:
        fn = card.get("fullNumber") or ""
    if not fn or fn == "DON!!":
        return None
    rar = (card.get("rarity") or "").strip()
    if not rar:
        return None
    return fn, rar


def main() -> None:
    allp = fetch_all()
    cat = json.loads(CATALOG.read_text(encoding="utf-8"))

    sell_keys: dict[tuple[str, str], list] = defaultdict(list)
    for c in cat.get("cards") or []:
        k = sell_key(c)
        if k:
            sell_keys[k].append(c)

    matched: dict[str, dict] = {}
    unmatched: list[dict] = []
    skipped = 0

    for p in allp:
        name = p.get("name") or ""
        if re.search(r"Test for WooCommerce|大量回收", name, re.I):
            skipped += 1
            continue
        text = (p.get("add_to_cart") or {}).get("text") or ""
        paused = "暫停回收" in text
        fn = parse_number(name)
        rar = normalize_buy_rarity(name, attr_rarity(p))
        list_price = price_of(p)
        # 暫停回收 → buy/trade-in price treated as $0
        buy_hkd = 0.0 if paused else list_price

        row = {
            "fullNumber": fn,
            "rarity": rar,
            "buyHkd": buy_hkd,
            "buyPaused": paused,
            "listPriceHkd": list_price,
            "name": name.replace("&#8211;", "–"),
            "url": p.get("permalink") or "",
        }

        if not fn or not rar:
            unmatched.append(row)
            continue

        key = f"{fn}|{rar}"
        if (fn, rar) in sell_keys:
            prev = matched.get(key)
            if not prev:
                matched[key] = row
            elif prev["buyPaused"] and not paused:
                matched[key] = row
            elif prev["buyPaused"] == paused and list_price > prev["listPriceHkd"]:
                matched[key] = row
        else:
            unmatched.append(row)

    out = {
        "syncedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": "https://beehivetcgbuylist.com/product-category/opcg/",
        "currency": "HKD",
        "match": "cardNumber + rarity",
        "note": "buyHkd is Beehive trade-in (buy) price. buyHkd=0 when 暫停回收.",
        "counts": {
            "fetched": len(allp),
            "skipped": skipped,
            "matchedKeys": len(matched),
            "unmatched": len(unmatched),
            "pausedMatched": sum(1 for v in matched.values() if v["buyPaused"]),
        },
        # compact lookup: "OP01-016|P-RP" -> { buyHkd, buyPaused }
        "byKey": {
            k: {
                "buyHkd": v["buyHkd"],
                "buyPaused": v["buyPaused"],
                "name": v["name"],
            }
            for k, v in matched.items()
        },
    }
    OUT_MATCHED.write_text(
        json.dumps(out, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    unmatched_sorted = sorted(
        unmatched,
        key=lambda x: (-(x["listPriceHkd"] or 0), x.get("fullNumber") or "", x["name"]),
    )
    OUT_UNMATCHED.write_text(
        json.dumps(
            {
                "note": (
                    "Buylist rows with no matching card number+rarity on our page. "
                    "buyHkd is Beehive trade-in price (0 if 暫停回收). Add later if needed."
                ),
                "syncedAt": out["syncedAt"],
                "count": len(unmatched_sorted),
                "cards": [
                    {
                        "fullNumber": r["fullNumber"],
                        "rarity": r["rarity"],
                        "buyHkd": r["buyHkd"],
                        "buyPaused": r["buyPaused"],
                        "name": r["name"],
                        "url": r["url"],
                    }
                    for r in unmatched_sorted
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps(out["counts"], indent=2))
    print(f"wrote {OUT_MATCHED}")
    print(f"wrote {OUT_UNMATCHED} ({len(unmatched_sorted)})")


if __name__ == "__main__":
    main()
