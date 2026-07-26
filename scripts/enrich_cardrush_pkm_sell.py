#!/usr/bin/env python3
"""Match Card Rush Pokemon sell prices onto docs/data/pkmjp-buylist.json.

Source: https://www.cardrush-pokemon.jp/product-list
Search key: SET + number/size (e.g. "M2 116/080") — same idea as OP sell.
Match: set + card number (+ rarity/name when needed).
Keep: clean JP only (in or out of stock).
Skip: 〔状態…〕, PSA/鑑定, sealed/オリパ/サプライ, non-JP.
Rules:
  - prefer blank / ノーマル仕様 / アンリミ extras (specials only if title asks)
  - prefer non-☆SALE☆ when both match
  - unique → sellYenCardrush + sellUrlCardrush
  - none → sellYenCardrush = 0
  - still ambiguous → leave unset; write review list
"""

from __future__ import annotations

import json
import re
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from curl_cffi import requests

ROOT = Path(__file__).resolve().parents[1]
BH = ROOT / "docs/data/pkmjp-buylist.json"
REVIEW = ROOT / "docs/data/cardrush-pkm-sell-review.json"
CACHE_DIR = ROOT / "scripts/.cache/cardrush-pkm-sell-kw"
SELL_SEARCH = "https://www.cardrush-pokemon.jp/product-list"

SKIP_RE = re.compile(
    r"^〔|PSA|ARS|BGS|鑑定|状態|"
    r"英語|中国|Asia|ASIA|France|フランス|"
    r"未開封|開封|デッキ販売|オリパ|サプライ|詰め合わせ|ピンバッジ|プレイマット|ダメカン"
)
TITLE_RE = re.compile(r"^(?:☆SALE☆)?(.+?)【([^】]+)】\{([^}]+)\}$")
EXTRA_RE = re.compile(r"^(.*?)(?:\(([^()]*)\))?$")
CLEAN_EXTRA = {"", "ノーマル仕様", "アンリミ"}

RARITY_ALIASES = {
    "D": ["D", "-"],
    "-": ["-", "D", "CP"],
    "A": ["A", "AR"],
    "AR": ["AR", "A"],
    "CP": ["CP", "-"],
    "U": ["U", "Ｕ"],
    "Ｕ": ["U", "Ｕ"],
}


def norm_model(mn: str) -> str:
    mn = (mn or "").strip()
    m = re.fullmatch(r"(\d+)/(\d+|[A-Za-z0-9-]+)", mn)
    if not m:
        return mn
    left, right = m.group(1), m.group(2)
    if right.isdigit():
        return f"{int(left):03d}/{int(right):03d}"
    return f"{int(left):03d}/{right}"


def norm_name(name: str) -> str:
    s = (name or "").replace("＆", "&").replace("　", "").replace("?", "").strip()
    s = re.sub(r"[\[\(（/／:：]", "|", s)
    s = re.sub(r"[\]\)）]", "", s)
    s = re.sub(r"\|[A-Za-z][A-Za-z ].*$", "", s)
    return re.sub(r"\s+", "", s)


def rarity_aliases(rarity: str) -> list[str]:
    r = (rarity or "").strip() or "-"
    r = {"Ｕ": "U", "Ａ": "A"}.get(r, r)
    return RARITY_ALIASES.get(r, [r])


def strip_tags(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s or "").strip()


def search_url(keyword: str, page: int = 1) -> str:
    url = f"{SELL_SEARCH}?keyword={quote(keyword)}&num=100"
    if page > 1:
        url += f"&page={page}"
    return url


def last_page(html: str) -> int:
    pages = {1}
    for n in re.findall(r"[?&]page=(\d+)", html):
        pages.add(int(n))
    for n in re.findall(r"to_last_page[^>]*>\s*(\d+)", html):
        pages.add(int(n))
    return max(pages)


def parse_listings(html: str) -> list[dict]:
    out: list[dict] = []
    for block in re.split(r'<li class="list_item_cell', html)[1:]:
        alt_m = re.search(r'alt="([^"]+)"', block)
        price_m = re.search(r'class="figure">([\d,]+)円', block)
        pid_m = re.search(r'data-product-id="(\d+)"', block)
        set_m = re.search(
            r'class="model_number_value"[^>]*>(.*?)</span>\s*<span class="bracket">\]',
            block,
            re.S,
        )
        if not (alt_m and price_m and pid_m and set_m):
            continue
        raw = alt_m.group(1).strip()
        if SKIP_RE.search(raw):
            continue
        m = TITLE_RE.match(raw)
        if not m:
            continue
        name_raw, rarity, model = m.group(1), m.group(2), m.group(3)
        em = EXTRA_RE.match(name_raw.strip())
        base = (em.group(1) if em else name_raw).strip()
        extra = (em.group(2) if em and em.group(2) else "").strip()
        set_code = strip_tags(set_m.group(1)).upper()
        if not set_code or set_code in ("その他", "OTHER", "-"):
            continue
        out.append(
            {
                "name": base,
                "extra": extra,
                "rarity": (rarity or "").strip() or "-",
                "model": norm_model(model),
                "set": set_code,
                "sellYen": int(price_m.group(1).replace(",", "")),
                "url": f"https://www.cardrush-pokemon.jp/product/{pid_m.group(1)}",
                "raw": raw,
                "sale": raw.startswith("☆SALE☆"),
            }
        )
    return out


def warm(session: requests.Session) -> None:
    session.get(
        "https://www.cardrush-pokemon.jp/", impersonate="chrome131", timeout=30
    )
    time.sleep(0.2)


def get_html(session: requests.Session, url: str, retries: int = 4) -> str:
    last = ""
    for attempt in range(retries):
        r = session.get(url, impersonate="chrome131", timeout=60)
        last = r.text
        if r.status_code == 403 or "403 Forbidden" in last:
            time.sleep(5 * (attempt + 1))
            warm(session)
            continue
        if "Just a moment" not in last:
            return last
        warm(session)
        time.sleep(1.2 * (attempt + 1))
    raise RuntimeError(f"blocked/challenge for {url} status-ish len={len(last)}")


def fetch_keyword(session: requests.Session, keyword: str, sleep_s: float = 0.25) -> list[dict]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^\w.\-]+", "_", keyword)[:180] or "empty"
    cache = CACHE_DIR / f"{safe}.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))

    listings: list[dict] = []
    page = 1
    known_last = 1
    while page <= known_last and page <= 20:
        html = get_html(session, search_url(keyword, page))
        time.sleep(sleep_s)
        known_last = max(known_last, last_page(html))
        cells = html.count("list_item_cell")
        if cells == 0:
            break
        listings.extend(parse_listings(html))
        if page >= known_last and cells >= 100:
            known_last = page + 1
        page += 1

    seen: set[str] = set()
    uniq: list[dict] = []
    for it in listings:
        if it["url"] in seen:
            continue
        seen.add(it["url"])
        uniq.append(it)

    cache.write_text(json.dumps(uniq, ensure_ascii=False), encoding="utf-8")
    return uniq


def set_shapes(set_code: str) -> list[str]:
    s = (set_code or "").strip()
    if not s:
        return []
    out: list[str] = []
    for cand in (s, s.upper(), s.lower(), s[:-1].upper() + s[-1].lower() if len(s) > 1 else s):
        if cand and cand not in out:
            out.append(cand)
    return out


def search_keywords_for(c: dict) -> list[str]:
    num, size = c.get("number"), c.get("setSize")
    if not num or not size:
        return []
    model = f"{num}/{size}"
    kws: list[str] = []
    for s in set_shapes(c.get("set") or ""):
        kw = f"{s} {model}"
        if kw not in kws:
            kws.append(kw)
    # printId as stored (often already correct)
    pid = (c.get("printId") or "").strip()
    if pid and pid not in kws:
        kws.insert(0, pid)
    return kws


def allowed_extra(extra: str, hay: str) -> bool:
    e = extra or ""
    t = hay or ""
    if e in CLEAN_EXTRA:
        return True
    if re.search(r"エラー", e) and "エラー" not in t:
        return False
    if re.search(r"ミラー", e) and "ミラー" not in t:
        return False
    if "1ED" in e and "1ED" not in t and "1st" not in t.lower():
        return False
    if re.search(r"RR仕様", e) and "キラ" not in t and "RR" not in t:
        return False
    if re.search(r"SA仕様|SR仕様", e) and not re.search(r"SA|SR仕様", t):
        return False
    return e in t


def pick_hits(hits: list[dict], hay: str) -> list[dict]:
    cand = [h for h in hits if allowed_extra(h.get("extra") or "", hay)]
    if not cand:
        return []
    normal = [h for h in cand if not h.get("sale")]
    if normal:
        cand = normal

    def tier(extra: str) -> int:
        if extra == "":
            return 0
        if extra == "ノーマル仕様":
            return 1
        if extra == "アンリミ":
            return 2
        return 3

    best_tier = min(tier(h.get("extra") or "") for h in cand)
    cand = [h for h in cand if tier(h.get("extra") or "") == best_tier]
    by_price = {h["sellYen"]: h for h in cand}
    return list(by_price.values())


def card_hay(c: dict) -> str:
    return " ".join(
        x
        for x in (
            c.get("title"),
            c.get("name"),
            c.get("cardrushName"),
            c.get("hareruyaName"),
        )
        if x
    )


def filter_for_card(listings: list[dict], c: dict) -> list[dict]:
    set_u = (c.get("set") or "").upper()
    model = norm_model(f"{c.get('number')}/{c.get('setSize')}")
    names = [
        n
        for n in (c.get("cardrushName"), c.get("name"), c.get("hareruyaName"))
        if n
    ] or [""]
    rars = set(rarity_aliases(c.get("rarity") or ""))

    # exact set+model+rarity+name
    for name in names:
        nn = norm_name(name)
        hits = [
            it
            for it in listings
            if it["set"] == set_u
            and it["model"] == model
            and it["rarity"] in rars
            and norm_name(it["name"]) == nn
        ]
        if hits:
            return hits

    # set+model+rarity
    hits = [
        it
        for it in listings
        if it["set"] == set_u and it["model"] == model and it["rarity"] in rars
    ]
    if hits:
        return hits

    # set+model only
    return [it for it in listings if it["set"] == set_u and it["model"] == model]


def main() -> None:
    data = json.loads(BH.read_text(encoding="utf-8"))
    cards: list[dict] = data["cards"]

    by_kw: dict[str, list[dict]] = defaultdict(list)
    # one primary keyword per card (first shape); fetch fallbacks only if empty
    primary: dict[int, list[str]] = {}
    for i, c in enumerate(cards):
        kws = search_keywords_for(c)
        primary[i] = kws
        if kws:
            by_kw[kws[0]].append(c)

    print(f"cards={len(cards)} primary keywords={len(by_kw)}")

    session = requests.Session()
    warm(session)

    listings_by_kw: dict[str, list[dict]] = {}
    keys = sorted(by_kw)
    for n, kw in enumerate(keys, 1):
        try:
            listings_by_kw[kw] = fetch_keyword(session, kw)
        except Exception as e:
            print(f"  warn {kw}: {e}")
            listings_by_kw[kw] = []
        if n % 100 == 0 or n == len(keys):
            print(f"  fetched {n}/{len(keys)} keywords")

    unique = none = ambiguous = 0
    review: list[dict] = []

    for i, c in enumerate(cards):
        c.pop("sellYenCardrush", None)
        c.pop("sellUrlCardrush", None)
        c.pop("sellMatchCardrush", None)

        kws = primary.get(i) or []
        listings: list[dict] = []
        for kw in kws:
            if kw not in listings_by_kw:
                try:
                    listings_by_kw[kw] = fetch_keyword(session, kw)
                except Exception:
                    listings_by_kw[kw] = []
            listings = listings_by_kw.get(kw) or []
            # keep if any row matches this set (avoid empty wrong-case hits)
            set_u = (c.get("set") or "").upper()
            if any(it["set"] == set_u for it in listings):
                break
            listings = []

        hits = filter_for_card(listings, c) if listings else []
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
                    "fullNumber": c.get("fullNumber"),
                    "name": c.get("name"),
                    "rarity": c.get("rarity"),
                    "buyYenCardrush": c.get("buyYenCardrush"),
                    "candidates": [
                        {
                            "sellYen": h["sellYen"],
                            "url": h["url"],
                            "raw": h["raw"],
                            "extra": h.get("extra"),
                            "set": h["set"],
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
    }
    note = data.get("note") or ""
    if "Sell(cardrush)" not in note:
        data["note"] = (
            note
            + " Sell(cardrush) from cardrush-pokemon.jp (clean JP; "
            "ambiguous left unset — see cardrush-pkm-sell-review.json)."
        ).strip()

    BH.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    REVIEW.write_text(
        json.dumps(
            {
                "syncedAt": now,
                "count": len(review),
                "note": (
                    "Multiple clean JP sell listings after preferring "
                    "normal/non-SALE. Pick one; set sellYenCardrush/sellUrlCardrush."
                ),
                "items": review,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {BH.name}: unique={unique} none={none} ambiguous={ambiguous}")
    print(f"wrote {REVIEW.name}: {len(review)} items")

    m2 = next(
        c
        for c in cards
        if c.get("printId") == "M2 116/080" and c.get("rarity") == "MUR"
    )
    assert m2.get("sellMatchCardrush") == "unique" and (m2.get("sellYenCardrush") or 0) > 0
    assert all(
        c.get("sellMatchCardrush") in ("unique", "none", "ambiguous") for c in cards
    )
    assert sum(1 for c in cards if c.get("sellMatchCardrush") == "ambiguous") == len(
        review
    )
    # spot-check the pagination miss from set-crawl
    m4 = next(c for c in cards if c.get("printId") == "M4 120/083")
    assert m4.get("sellMatchCardrush") == "unique" and (m4.get("sellYenCardrush") or 0) > 0
    print(
        "self-check ok",
        "M2",
        m2.get("sellYenCardrush"),
        "M4",
        m4.get("sellYenCardrush"),
    )


if __name__ == "__main__":
    main()
