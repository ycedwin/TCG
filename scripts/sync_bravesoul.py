#!/usr/bin/env python3
"""Parse Brave Soul OP回收表 sheet → bravesoul.json (+ unmatched)."""

from __future__ import annotations

import csv
import json
import re
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "docs/data/catalog.json"
OUT = ROOT / "docs/data/bravesoul.json"
OUT_UNMATCHED = ROOT / "docs/data/bravesoul-unmatched.json"
SHEET_CSV = (
    "https://docs.google.com/spreadsheets/d/e/"
    "2PACX-1vQ0tls6zT7uuQQB4m0guPEJ0GQ1NkBM5bL2vyiRbBBvWx8AJd3XYU73N2mGZ_g84Cy7GyxqHrHH_UZ8/"
    "pub?gid=1278494821&single=true&output=csv"
)
SHEET_HTML = (
    "https://docs.google.com/spreadsheets/d/e/"
    "2PACX-1vQ0tls6zT7uuQQB4m0guPEJ0GQ1NkBM5bL2vyiRbBBvWx8AJd3XYU73N2mGZ_g84Cy7GyxqHrHH_UZ8/"
    "pubhtml?gid=1278494821&single=true"
)
MIN_UNMATCHED_PRICE = 5
PAGE_MIN_SELL = 50

CARD_RE = re.compile(
    r"^\s*((?:OP|EB|ST)\d{2}|PRB\d{2}|P)-(\d{2,3})\b(.*)$",
    re.I,
)
PRICE_RE = re.compile(r"^\$?\s*([\d,]+(?:\.\d+)?)\s*$")

MANGA = {"P-RP", "P-SRP", "P-SECP", "SP", "SP-金", "SP-銀"}
PARALLEL = {
    "P-SR",
    "P-R",
    "P-SEC",
    "P-L",
    "P-UC",
    "P-C",
    "P-P",
    "P-特殊閃版",
    "R-特殊閃版",
    "UC-特殊閃版",
    "C-特殊閃版",
    "P-有紋",
    "R-有紋",
    "UC-有紋",
    "C-有紋",
}
LEADER = {"L", "P-L"}
NORMAL = {"SR", "SEC", "R", "UC", "C", "L", "TR"}
SP_SET = {"SP", "SP-金", "SP-銀"}
PROMO = {"P", "Promo", "P-P"}


def fetch_rows() -> list[list[str]]:
    raw = subprocess.check_output(
        ["curl", "-sL", "-A", "Mozilla/5.0", SHEET_CSV],
        text=True,
    )
    return list(csv.reader(raw.splitlines()))


def parse_price(s: str) -> float | None:
    s = (s or "").strip().replace(",", "")
    if not s or "@" in s:  # skip bulk 0.1@
        return None
    m = PRICE_RE.match(s)
    return float(m.group(1)) if m else None


def is_section_header(s: str) -> bool:
    s = (s or "").strip()
    if not s or CARD_RE.match(s) or parse_price(s) is not None:
        return False
    if s in {"R", "UC", "C", "SR", "SEC", "L", "SP", "ST", "P-", "P"}:
        return True
    if re.search(r"回收|更新|金枠", s):
        return False  # notes, not rarity sections
    return True


def bucket_for(section: str, suffix: str) -> set[str] | None:
    text = f"{section} {suffix}"
    if re.search(r"中国版|中國版", text):
        return None
    if re.search(r"未開封", text):
        return None

    suf = suffix or ""
    sec = section or ""

    if re.search(r"異圖|异图", suf):
        return set(PARALLEL)
    if re.search(r"漫畫|漫画", suf):
        return set(MANGA)
    if re.search(r"\bSP\b", suf, re.I):
        if re.search(r"金", suf):
            return {"SP-金"}
        if re.search(r"銀|银", suf):
            return {"SP-銀"}
        if re.search(r"漫畫|漫画", sec):
            return set(MANGA)
        return set(SP_SET)

    if re.search(r"異圖|异图", sec):
        return set(PARALLEL)
    if re.search(r"LEADER", sec, re.I) or re.search(r"LEADER", suf, re.I):
        return set(LEADER)
    if re.search(r"Promo|PROMO", sec, re.I) or re.search(r"Promo", suf, re.I):
        return set(PROMO)
    if re.search(r"普畫|普圖|普图", sec):
        return set(NORMAL)
    if re.search(r"漫畫|漫画", sec) or (
        re.search(r"\bSP\b", sec, re.I)
        and re.search(r"金銀|金银|手配|背景|漫画|漫畫", sec)
    ):
        return set(MANGA)
    if sec.strip() in {"R", "UC", "C", "SR", "SEC", "L", "SP"}:
        return {sec.strip()}
    if sec.strip() in {"P-", "P"} or re.search(r"^P-", sec):
        return set(PROMO)
    if sec.strip() == "ST":
        return set(MANGA) | set(PARALLEL) | set(LEADER) | set(NORMAL) | set(SP_SET)
    return set(PARALLEL) | set(MANGA) | set(LEADER) | set(NORMAL) | set(SP_SET) | set(
        PROMO
    )


def resolve_card(cands: list[dict], section: str, suffix: str, bucket: set[str] | None):
    if bucket is not None:
        cands = [c for c in cands if (c.get("rarity") or "") in bucket]
    if not cands:
        return None
    if len(cands) == 1:
        return cands[0]

    text = f"{section} {suffix}"
    # 異圖 → parallel only (not manga)
    if re.search(r"異圖|异图", text):
        filt = [c for c in cands if (c.get("rarity") or "") in PARALLEL]
        cands = filt or cands
    # 漫畫 / 金銀 SP
    if re.search(r"金銀|金银", section):
        filt = [c for c in cands if (c.get("rarity") or "") in SP_SET]
        cands = filt or cands
        if re.search(r"金", suffix) and not re.search(r"銀|银", suffix):
            g = [c for c in cands if c.get("rarity") == "SP-金"]
            if g:
                return g[0]
        if re.search(r"銀|银", suffix):
            s = [c for c in cands if c.get("rarity") == "SP-銀"]
            if s:
                return s[0]
    elif re.search(r"漫畫|漫画", text) or (
        re.search(r"\bSP\b", section, re.I) and re.search(r"手配|背景", section)
    ):
        filt = [c for c in cands if (c.get("rarity") or "") in MANGA]
        # prefer secret/manga parallels over plain SP
        prefer = [c for c in filt if c.get("rarity") in {"P-SECP", "P-SRP", "P-RP"}]
        cands = prefer or filt or cands
    if re.search(r"LEADER", text, re.I):
        pl = [c for c in cands if c.get("rarity") == "P-L"]
        if pl:
            return pl[0]
        l = [c for c in cands if c.get("rarity") == "L"]
        if l:
            return l[0]
    if re.search(r"普畫|普圖|普图", section):
        filt = [c for c in cands if (c.get("rarity") or "") in NORMAL]
        cands = filt or cands

    if len(cands) == 1:
        return cands[0]
    # still ambiguous — do not guess
    return None


def parse_entries(rows: list[list[str]]) -> list[dict]:
    section = ""
    skip_section = False
    entries: list[dict] = []
    i = 0
    while i < len(rows):
        r = rows[i]
        texts = [(j, (c or "").strip()) for j, c in enumerate(r) if (c or "").strip()]
        if (
            len(texts) == 1
            and is_section_header(texts[0][1])
            and parse_price(texts[0][1]) is None
            and not CARD_RE.match(texts[0][1])
        ):
            section = texts[0][1]
            skip_section = bool(re.search(r"中国版|中國版", section))
            i += 1
            continue

        cards = []
        for j, c in enumerate(r):
            s = (c or "").strip()
            m = CARD_RE.match(s)
            if not m:
                continue
            fn = f"{m.group(1).upper()}-{m.group(2).zfill(3)}"
            suf = (m.group(3) or "").strip()
            cards.append((j, fn, suf, s))

        if cards and i + 1 < len(rows):
            pr = rows[i + 1]
            prices = []
            ok = True
            for j, fn, suf, raw in cards:
                p = parse_price(pr[j] if j < len(pr) else "")
                if p is None:
                    ok = False
                    break
                prices.append(p)
            if ok:
                if not skip_section:
                    for (j, fn, suf, raw), price in zip(cards, prices):
                        if re.search(r"中国版|中國版", f"{section} {suf} {raw}"):
                            continue
                        if re.search(r"未開封", f"{section} {suf} {raw}"):
                            continue
                        bucket = bucket_for(section, suf)
                        if bucket is None:
                            continue
                        entries.append(
                            {
                                "fullNumber": fn,
                                "buyHkd": price,
                                "section": section,
                                "suffix": suf,
                                "raw": raw,
                                "bucket": sorted(bucket),
                            }
                        )
                i += 2
                continue
        i += 1
    return entries


def main() -> None:
    rows = fetch_rows()
    entries = parse_entries(rows)
    cat = json.loads(CATALOG.read_text(encoding="utf-8"))
    page_cards = [
        c
        for c in cat.get("cards") or []
        if c.get("priceHkd") is not None and c["priceHkd"] > PAGE_MIN_SELL
    ]
    by_num: dict[str, list] = defaultdict(list)
    for c in page_cards:
        fn = (
            f"{c['set']}-{c['number']}"
            if c.get("set") and c.get("number")
            else (c.get("fullNumber") or "")
        )
        if fn and fn != "DON!!":
            by_num[fn].append(c)

    matched: dict[str, dict] = {}
    unmatched: list[dict] = []
    ambiguous = 0

    for e in entries:
        cands = by_num.get(e["fullNumber"]) or []
        bucket = set(e["bucket"]) if e.get("bucket") else None
        hit = resolve_card(cands, e["section"], e["suffix"], bucket)
        if hit:
            key = f"{e['fullNumber']}|{hit.get('rarity') or ''}"
            prev = matched.get(key)
            # keep higher buy offer if duplicate
            if not prev or e["buyHkd"] > prev["buyHkd"]:
                matched[key] = {
                    "buyHkd": e["buyHkd"],
                    "fullNumber": e["fullNumber"],
                    "rarity": hit.get("rarity") or "",
                    "section": e["section"],
                    "name": e["raw"],
                    "source": "bravesoul",
                }
            continue
        # on-page number exists but rarity unresolved
        if cands:
            ambiguous += 1
            if e["buyHkd"] > MIN_UNMATCHED_PRICE:
                unmatched.append(
                    {
                        "fullNumber": e["fullNumber"],
                        "rarity": None,
                        "buyHkd": e["buyHkd"],
                        "section": e["section"],
                        "name": e["raw"],
                        "reason": "ambiguous_or_rarity_mismatch",
                        "pageRarities": sorted({c.get("rarity") for c in cands}),
                        "source": "bravesoul",
                    }
                )
            continue
        # not on our page
        if e["buyHkd"] > MIN_UNMATCHED_PRICE:
            unmatched.append(
                {
                    "fullNumber": e["fullNumber"],
                    "rarity": None,
                    "buyHkd": e["buyHkd"],
                    "section": e["section"],
                    "name": e["raw"],
                    "reason": "not_on_page",
                    "source": "bravesoul",
                }
            )

    # dedupe unmatched by number+section+price keep max
    uniq = {}
    for u in unmatched:
        k = (u["fullNumber"], u.get("section"), u["buyHkd"], u.get("reason"))
        uniq[k] = u
    unmatched_sorted = sorted(
        uniq.values(),
        key=lambda x: (-(x["buyHkd"] or 0), x.get("fullNumber") or ""),
    )

    out = {
        "syncedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": SHEET_HTML,
        "currency": "HKD",
        "match": "cardNumber + rarity bucket from sheet section",
        "note": "buyHkd is Brave Soul trade-in price. Skipped 中国版 and 未開封.",
        "counts": {
            "sheetEntries": len(entries),
            "matchedKeys": len(matched),
            "unmatched": len(unmatched_sorted),
            "ambiguousSkipped": ambiguous,
        },
        "byKey": {
            k: {
                "buyHkd": v["buyHkd"],
                "name": v["name"],
                "section": v["section"],
                "source": "bravesoul",
            }
            for k, v in matched.items()
        },
    }
    OUT.write_text(
        json.dumps(out, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    OUT_UNMATCHED.write_text(
        json.dumps(
            {
                "note": (
                    "Brave Soul sheet cards with buyHkd > $5 not cleanly matched "
                    "to a card on our page (number+rarity). Skipped 中国版 / 未開封. "
                    "Not added to the app yet."
                ),
                "syncedAt": out["syncedAt"],
                "source": SHEET_HTML,
                "count": len(unmatched_sorted),
                "cards": unmatched_sorted,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps(out["counts"], indent=2))
    print(f"wrote {OUT}")
    print(f"wrote {OUT_UNMATCHED}")


if __name__ == "__main__":
    main()
