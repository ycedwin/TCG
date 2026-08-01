#!/usr/bin/env python3
"""Fetch Card Rush OP buying list → docs/data/cardrush-op-buy.json (new rows only)."""

from __future__ import annotations

import json
import re
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/data/cardrush-op-buy.json"
SOURCE = "https://cardrush.media/onepiece/buying_prices"

MIN_YEN = 200
MAX_YEN = 300_000  # exclusive

# Skip condition/graded, sealed/opened, non-JP. Keep 金文字 + art variants.
SKIP_RE = re.compile(
    r"状態|PSA|ARS|BGS|鑑定|未開封|開封|"
    r"英語版|中国版|英語|中国|Asia|ASIA|France|フランス|ドジャース|GREVIN"
)
SET_RE = re.compile(r"^([A-Za-z]+\d*)")


def curl(url: str) -> str:
    return subprocess.check_output(
        ["curl", "-sL", "-A", "Mozilla/5.0", "--max-time", "90", url],
        text=True,
    )


def page_url(page: int, limit: int = 100) -> str:
    return (
        f"{SOURCE}?"
        f"displayMode={quote('リスト')}&limit={limit}&page={page}"
        "&sort%5Bkey%5D=amount&sort%5Border%5D=desc"
        "&associations%5B%5D=ocha_product"
        "&to_json_option%5Bexcept%5D%5B%5D=original_image_source"
        "&to_json_option%5Bexcept%5D%5B%5D=created_at"
        "&to_json_option%5Binclude%5D%5Bocha_product%5D%5Bonly%5D%5B%5D=id"
        "&to_json_option%5Binclude%5D%5Bocha_product%5D%5Bmethods%5D%5B%5D=image_source"
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


def is_don(it: dict) -> bool:
    # Only DON!! resource cards — not ドンキホーテ・…
    name = it.get("name") or ""
    return "ドン!!" in name


def model_and_set(it: dict) -> tuple[str, str]:
    if is_don(it):
        return "don", "don"
    mn = (it.get("model_number") or "").strip()
    if mn in ("", "-"):
        return mn or "-", "-"
    # Keep full model as-is (incl. OP05-119[OP11] / OP01-120(PRB01版))
    m = SET_RE.match(mn)
    set_code = m.group(1).upper() if m else mn
    return mn, set_code


def full_name(name: str, extra: str) -> str:
    name = (name or "").strip()
    extra = (extra or "").strip()
    return f"{name}({extra})" if extra else name


def keep(it: dict) -> bool:
    amount = int(it.get("amount") or 0)
    if amount < MIN_YEN or amount >= MAX_YEN:
        return False
    name = it.get("name") or ""
    if name.startswith("〔"):
        return False
    if SKIP_RE.search(hay(it)):
        return False
    return True


def to_card(it: dict) -> dict:
    name = (it.get("name") or "").strip()
    extra = (it.get("extra_difference") or "").strip()
    model, set_code = model_and_set(it)
    img = ((it.get("ocha_product") or {}).get("image_source") or "").strip()
    return {
        "id": it.get("id"),
        "name": name,
        "fullName": full_name(name, extra),
        "extra": extra,
        "rarity": (it.get("rarity") or "").strip() or "-",
        "modelNumber": model,
        "set": set_code,
        "buyYen": int(it["amount"]),
        "image": img or None,
        "url": SOURCE,
    }


def main() -> None:
    items, last = fetch_page(1)
    all_items = list(items)
    print(f"page 1/{last}: {len(all_items)}")
    for p in range(2, last + 1):
        batch, _ = fetch_page(p)
        all_items.extend(batch)
        print(f"page {p}/{last}: +{len(batch)} (total {len(all_items)})")

    counts: Counter[str] = Counter()
    cards: list[dict] = []
    for it in all_items:
        counts["fetched"] += 1
        amount = int(it.get("amount") or 0)
        if amount < MIN_YEN or amount >= MAX_YEN:
            counts["price"] += 1
            continue
        if (it.get("name") or "").startswith("〔") or SKIP_RE.search(hay(it)):
            counts["skip"] += 1
            continue
        if not keep(it):
            counts["skip"] += 1
            continue
        cards.append(to_card(it))
        counts["kept"] += 1

    cards.sort(key=lambda c: (-c["buyYen"], c["modelNumber"], c["fullName"]))

    out = {
        "syncedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": SOURCE,
        "currency": "JPY",
        "note": (
            "Card Rush OP buy-only rows. "
            f"Kept buy>={MIN_YEN} and buy<{MAX_YEN}. "
            "Skipped 状態/PSA/開封/未開封/非日本語. Kept art variants + 金文字. "
            "New records only — do not merge into Beehive catalog."
        ),
        "counts": dict(counts),
        "cards": cards,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUT} · kept {len(cards)}")

    # ponytail: one assert self-check — floor/ceiling + don + 金文字 kept
    assert cards, "expected some cards"
    assert all(MIN_YEN <= c["buyYen"] < MAX_YEN for c in cards)
    assert any(c["modelNumber"] == "don" for c in cards), "expected don rows"
    assert all(
        "ドン!!" in c["name"] for c in cards if c["modelNumber"] == "don"
    ), "false don (character names with ドン)"
    assert any("金文字" in c["fullName"] for c in cards), "expected 金文字 kept"
    assert not any(
        re.search(r"未開封|開封|英語|中国|PSA|状態", c["fullName"]) for c in cards
    ), "dirty rows leaked"
    print("self-check ok")


if __name__ == "__main__":
    main()
