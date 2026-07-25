#!/usr/bin/env python3
"""Match Hareruya2 buy prices onto our Pokemon JP buylist cards."""

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
# Beehive sometimes uses A for illustration rares that Hareruya lists as AR
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


def is_mirror_title(title: str, rarity: str) -> bool:
    t = title or ""
    return (
        "ミラー" in t
        or ":" in (rarity or "")
        or "-M]" in t
        or "-EM]" in t
        or "エネルギーミラー" in t
    )


def build_index(products: list[dict]) -> dict[tuple[str, str, str], list[dict]]:
    idx: dict[tuple[str, str, str], list[dict]] = {}
    for p in products:
        m = TITLE_RE.match(p.get("title") or "")
        if not m:
            continue
        d = m.groupdict()
        set_raw = d["set"].split("-")[0]
        key = (norm_set(set_raw), norm_num(d["num"]), norm_rar(d["rarity"]))
        row = {
            "id": p.get("id"),
            "buyYen": int(p.get("buy_price") or 0),
            "sellYen": int(p.get("sell_price") or 0),
            "name": d["name"],
            "title": p.get("title") or "",
            "image": p.get("image_url") or "",
            "mirror": is_mirror_title(p.get("title") or "", d["rarity"]),
            "isPickup": bool(p.get("is_pickup")),
        }
        idx.setdefault(key, []).append(row)
    return idx


def pick_best(hits: list[dict]) -> dict | None:
    if not hits:
        return None
    primary = [h for h in hits if not h["mirror"]] or hits
    return max(primary, key=lambda h: (h["buyYen"], 1 if h["isPickup"] else 0))


def main() -> None:
    raw = json.loads(curl(HR_URL))
    products = raw.get("products") or []
    idx = build_index(products)

    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    cards = data.get("cards") or []
    matched = 0
    name_hints = 0

    for c in cards:
        setc = norm_set(c.get("set") or "")
        num = f"{int(c['number']):03d}/{int(c['setSize']):03d}"
        rar = norm_rar(c.get("rarity") or "")
        hits: list[dict] = []
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
        # Prefer Hareruya JP name when ours is empty/odd
        if best["name"] and (not c.get("name") or c["name"] != best["name"]):
            if not c.get("name"):
                c["name"] = best["name"]
        # Hint for English enrich: keep hareruyaName even if nameEn exists
        if not c.get("nameEn") and best["name"]:
            name_hints += 1

    data["hareruya"] = {
        "syncedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": HR_URL,
        "page": "https://www.hareruya2.com/en/pages/buying-list",
        "match": "set + number/size + rarity",
        "counts": {
            "hareruyaProducts": len(products),
            "indexedKeys": len(idx),
            "matchedCards": matched,
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

    # Re-run English enrich (uses name / can use hareruyaName)
    enrich = ROOT / "scripts/enrich_pkmjp_names.py"
    if enrich.exists():
        subprocess.check_call(["python3", str(enrich)])


if __name__ == "__main__":
    main()
