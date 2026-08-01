#!/usr/bin/env python3
"""Match Hareruya2 buy prices onto our Pokemon JP cards; add missing ≥¥200."""

from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "docs/data/pkmjp-buylist.json"
HR_URL = "https://api.corp.hareruyamtg.com/user_data/hareruya2/json/products_all.json"
TITLE_RE = re.compile(
    r"^(?P<name>.+?)\((?P<rarity>[^)]+)\)\{(?P<type>[^}]*)\}"
    r"〈(?P<num>[^〉]+)〉\[(?P<set>[^\]]+)\]"
)
# Same series the Hareruya buying-list UI shows under「すべて」
VALID_SERIES = {
    "MEGAシリーズ",
    "スカーレット&バイオレットシリーズ",
    "ソード&シールドシリーズ",
    "サン&ムーンシリーズ",
    "XYシリーズ",
    "BWシリーズ",
}
MIN_BUY_YEN_ADD = 200
RARITY_ALIASES = {
    "A": ["A", "AR"],
    "AR": ["AR", "A"],
}


def curl(url: str) -> str:
    return subprocess.check_output(
        ["curl", "-sL", "-A", "Mozilla/5.0", "--max-time", "120", url],
        text=True,
    )


def norm_set(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", s or "").upper()


def norm_num(num: str) -> str:
    if "/" not in num:
        return num
    a, b = num.split("/", 1)
    if a.isdigit() and b.isdigit():
        return f"{int(a):03d}/{int(b):03d}"
    return num


def norm_rar(r: str) -> str:
    r = (r or "").split(":")[0].strip()
    return r.upper() if r.isascii() else r


def norm_series(s: str) -> str:
    return str(s or "").replace("＆", "&")


def clean_name(name: str) -> str:
    # Drop trailing art tags glued in Hareruya titles: :SA :SR etc.
    return re.sub(r":[A-Za-z0-9]+$", "", (name or "").strip())


def is_mirror_title(title: str, rarity: str) -> bool:
    t = title or ""
    return (
        "ミラー" in t
        or ":" in (rarity or "")
        or "-M]" in t
        or "-EM]" in t
        or "エネルギーミラー" in t
    )


def parse_product(p: dict) -> dict | None:
    m = TITLE_RE.match(p.get("title") or "")
    if not m:
        return None
    d = m.groupdict()
    if not re.match(r"^\d+/\d+$", d["num"]):
        return None
    set_raw = d["set"].split("-")[0]
    setc = norm_set(set_raw)
    num = norm_num(d["num"])
    rar = norm_rar(d["rarity"])
    a, b = num.split("/")
    return {
        "id": p.get("id"),
        "buyYen": int(p.get("buy_price") or 0),
        "sellYen": int(p.get("sell_price") or 0),
        "name": clean_name(d["name"]),
        "title": p.get("title") or "",
        "image": p.get("image_url") or "",
        "series": p.get("series_name") or "",
        "setName": p.get("set_name") or "",
        "set": setc,
        "number": a,
        "setSize": b,
        "fullNumber": f"{setc}-{a}",
        "printId": f"{setc} {a}/{b}",
        "rarity": rar,
        "mirror": is_mirror_title(p.get("title") or "", d["rarity"]),
        "isPickup": bool(p.get("is_pickup")),
        "key": (setc, num, rar),
    }


def build_index(products: list[dict]) -> dict[tuple[str, str, str], list[dict]]:
    idx: dict[tuple[str, str, str], list[dict]] = {}
    for p in products:
        row = parse_product(p)
        if not row:
            continue
        idx.setdefault(row["key"], []).append(row)
    return idx


def pick_best(hits: list[dict]) -> dict | None:
    if not hits:
        return None
    primary = [h for h in hits if not h["mirror"]] or hits
    return max(primary, key=lambda h: (h["buyYen"], 1 if h["isPickup"] else 0))


def card_key(c: dict) -> tuple[str, str, str] | None:
    try:
        setc = norm_set(c.get("set") or "")
        num = f"{int(c['number']):03d}/{int(c['setSize']):03d}"
        rar = norm_rar(c.get("rarity") or "")
        return setc, num, rar
    except Exception:
        return None


def main() -> None:
    raw = json.loads(curl(HR_URL))
    products = raw.get("products") or []
    idx = build_index(products)

    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    cards = data.get("cards") or []
    existing_keys: set[tuple[str, str, str]] = set()
    matched = 0
    name_hints = 0

    for c in cards:
        key = card_key(c)
        if key:
            existing_keys.add(key)
        hits: list[dict] = []
        if key:
            setc, num, rar = key
            for alias in RARITY_ALIASES.get(rar, [rar]):
                hits.extend(idx.get((setc, num, alias)) or [])
        best = pick_best(hits)
        if not best:
            c.pop("buyYenHareruya", None)
            c.pop("hareruyaName", None)
            c.pop("hareruyaId", None)
            continue
        matched += 1
        c["buyYenHareruya"] = best["buyYen"]
        c["hareruyaName"] = best["name"]
        c["hareruyaId"] = best["id"]
        if not c.get("name"):
            c["name"] = best["name"]
        if not c.get("nameEn") and best["name"]:
            name_hints += 1

    # Add Hareruya-only cards (≥¥200, same series filter as their UI)
    added = 0
    candidates: dict[tuple[str, str, str], dict] = {}
    for p in products:
        buy = int(p.get("buy_price") or 0)
        sell = int(p.get("sell_price") or 0)
        if buy < MIN_BUY_YEN_ADD:
            continue
        if sell >= 500_000:
            continue
        if norm_series(p.get("series_name")) not in VALID_SERIES:
            continue
        row = parse_product(p)
        if not row or row["mirror"]:
            continue
        if row["key"] in existing_keys:
            continue
        prev = candidates.get(row["key"])
        if not prev or row["buyYen"] > prev["buyYen"]:
            candidates[row["key"]] = row

    for row in candidates.values():
        cards.append(
            {
                "set": row["set"],
                "number": row["number"],
                "setSize": row["setSize"],
                "fullNumber": row["fullNumber"],
                "printId": row["printId"],
                "name": row["name"],
                "nameEn": "",
                "rarity": row["rarity"],
                "buyHkd": None,
                "buyYenHareruya": row["buyYen"],
                "hareruyaName": row["name"],
                "hareruyaId": row["id"],
                "url": "",
                "image": row["image"],
                "title": row["title"],
                "source": "hareruya",
                "series": row["series"],
                "setName": row["setName"],
            }
        )
        added += 1
        existing_keys.add(row["key"])

    # Sort: Beehive HKD first by price, then Hareruya yen
    cards.sort(
        key=lambda c: (
            -(c.get("buyHkd") or 0),
            -(c.get("buyYenHareruya") or 0),
            c.get("fullNumber") or "",
            c.get("rarity") or "",
        )
    )
    data["cards"] = cards

    # Refresh rarity order from current cards
    rarity_order = []
    seen_r = set()
    for c in cards:
        r = c.get("rarity") or "?"
        if r not in seen_r:
            seen_r.add(r)
            rarity_order.append(r)
    data["rarityOrder"] = rarity_order

    data["hareruya"] = {
        "syncedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": HR_URL,
        "page": "https://www.hareruya2.com/en/pages/buying-list",
        "match": "set + number/size + rarity",
        "addRule": f"page series + buyYen>={MIN_BUY_YEN_ADD} + sellYen<500000 + not already on page",
        "counts": {
            "hareruyaProducts": len(products),
            "indexedKeys": len(idx),
            "matchedExisting": matched,
            "addedHareruyaOnly": added,
            "unmappedNeedingEn": name_hints,
            "totalCards": len(cards),
        },
    }
    CATALOG.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(json.dumps(data["hareruya"]["counts"], indent=2))
    print(f"wrote {CATALOG}")

    enrich = ROOT / "scripts/sync_pkm_names.py"
    if enrich.exists():
        subprocess.check_call(["python3", str(enrich)])


if __name__ == "__main__":
    main()
