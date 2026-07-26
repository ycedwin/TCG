#!/usr/bin/env python3
"""Match sell prices from markdown dumps of cardrush-pokemon.jp product-list.

Dump format (one listing per line), as returned by WebFetch:
  メガリザードンXex【MUR】{116/080} [M2] 218,000円(税込) 在庫数 22枚

Put dumps in scripts/.cache/cardrush-pkm-sell-md/*.md then run this.
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
BH = ROOT / "docs/data/pkmjp-buylist.json"
REVIEW = ROOT / "docs/data/cardrush-pkm-sell-review.json"
MD_DIR = ROOT / "scripts/.cache/cardrush-pkm-sell-md"
SELL_SEARCH = "https://www.cardrush-pokemon.jp/product-list"

# import shared match helpers
sys.path.insert(0, str(ROOT / "scripts"))
from enrich_cardrush_pkm_sell import (  # noqa: E402
    SKIP_RE,
    TITLE_RE,
    EXTRA_RE,
    allowed_extra,
    card_hay,
    filter_for_card,
    norm_model,
    norm_name,
    pick_hits,
    rarity_aliases,
)

LINE_RE = re.compile(
    r"(?:☆SALE☆)?(.+?)【([^】]+)】\{([^}]+)\}\s*\[([^\]]+)\]\s*([\d,]+)円"
)


def parse_md(text: str) -> list[dict]:
    out: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or SKIP_RE.search(line):
            continue
        m = LINE_RE.search(line)
        if not m:
            continue
        name_raw, rarity, model, set_code, yen = m.groups()
        # TITLE_RE-style extra split
        raw = f"{name_raw}【{rarity}】{{{model}}}"
        if line.startswith("☆SALE☆"):
            raw = "☆SALE☆" + raw
        em = EXTRA_RE.match(name_raw.strip())
        base = (em.group(1) if em else name_raw).strip()
        extra = (em.group(2) if em and em.group(2) else "").strip()
        set_u = set_code.strip().upper()
        if set_u in ("その他", "OTHER", "-", "サプライ", "デッキ販売"):
            continue
        model_n = norm_model(model)
        out.append(
            {
                "name": base,
                "extra": extra,
                "rarity": (rarity or "").strip() or "-",
                "model": model_n,
                "set": set_u,
                "sellYen": int(yen.replace(",", "")),
                "url": (
                    f"{SELL_SEARCH}?keyword="
                    f"{quote(set_u + ' ' + model_n)}&num=100"
                ),
                "raw": raw,
                "sale": line.startswith("☆SALE☆"),
            }
        )
    return out


def load_all_listings() -> list[dict]:
    if not MD_DIR.exists():
        return []
    all_items: list[dict] = []
    seen: set[tuple] = set()
    for path in sorted(MD_DIR.glob("*.md")):
        for it in parse_md(path.read_text(encoding="utf-8")):
            key = (it["set"], it["model"], it["rarity"], it["name"], it["extra"], it["sellYen"])
            if key in seen:
                continue
            seen.add(key)
            all_items.append(it)
    return all_items


def main() -> None:
    listings = load_all_listings()
    print(f"md listings={len(listings)} from {MD_DIR}")
    data = json.loads(BH.read_text(encoding="utf-8"))
    cards = data["cards"]

    by_set_model: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for it in listings:
        by_set_model[(it["set"], it["model"])].append(it)

    unique = none = ambiguous = 0
    review: list[dict] = []

    for c in cards:
        c.pop("sellYenCardrush", None)
        c.pop("sellUrlCardrush", None)
        c.pop("sellMatchCardrush", None)

        set_u = (c.get("set") or "").upper()
        model = norm_model(f"{c.get('number')}/{c.get('setSize')}")
        pool = by_set_model.get((set_u, model), [])
        hits = filter_for_card(pool, c) if pool else []
        picked = pick_hits(hits, card_hay(c)) if hits else []

        if len(picked) == 1:
            c["sellYenCardrush"] = picked[0]["sellYen"]
            c["sellUrlCardrush"] = picked[0]["url"]
            c["sellMatchCardrush"] = "unique"
            unique += 1
        elif len(picked) == 0:
            c["sellYenCardrush"] = 0
            c["sellUrlCardrush"] = None
            c["sellMatchCardrush"] = "none"
            none += 1
        else:
            c["sellMatchCardrush"] = "ambiguous"
            ambiguous += 1
            review.append(
                {
                    "printId": c.get("printId"),
                    "name": c.get("name"),
                    "rarity": c.get("rarity"),
                    "candidates": [
                        {
                            "sellYen": h["sellYen"],
                            "url": h["url"],
                            "raw": h["raw"],
                            "extra": h.get("extra"),
                        }
                        for h in sorted(picked, key=lambda x: x["sellYen"])
                    ],
                }
            )

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    data["cardrushSell"] = {
        "syncedAt": now,
        "source": SELL_SEARCH,
        "counts": {"unique": unique, "none": none, "ambiguous": ambiguous},
        "via": "markdown-dump",
    }
    BH.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    REVIEW.write_text(
        json.dumps(
            {"syncedAt": now, "count": len(review), "items": review},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"unique={unique} none={none} ambiguous={ambiguous}")


if __name__ == "__main__":
    main()
