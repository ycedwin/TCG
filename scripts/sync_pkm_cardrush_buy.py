#!/usr/bin/env python3
"""Enrich pkmjp-buylist.json with Card Rush buy yen; add clean CR-only cards."""

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
REVIEW = ROOT / "docs/data/cardrush-pkm-buy-review.json"
SOURCE = "https://cardrush.media/pokemon/buying_prices"

MIN_YEN = 200
MAX_YEN = 300_000  # exclusive
CLEAN_EXTRA = {"", "ノーマル仕様", "アンリミ"}

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
    mn = (mn or "").strip()
    m = re.fullmatch(r"(\d+)/(\d+|[A-Za-z0-9-]+)", mn)
    if not m:
        return mn
    left, right = m.group(1), m.group(2)
    if right.isdigit():
        return f"{int(left):03d}/{int(right):03d}"
    return f"{int(left):03d}/{right}"


def parse_model(mn: str) -> tuple[str, str] | None:
    mn = (mn or "").strip()
    m = re.fullmatch(r"(\d+)/(\d+|[A-Za-z0-9-]+)", mn)
    if not m:
        return None
    left, right = m.group(1), m.group(2)
    number = f"{int(left):03d}"
    set_size = f"{int(right):03d}" if right.isdigit() else right
    return number, set_size


def norm_name(name: str) -> str:
    # ponytail: BH [x] / HR （x） / CR /x / spaces are the same subtitle form.
    s = (name or "").replace("＆", "&").replace("　", "").replace("?", "").strip()
    s = re.sub(r"[\[\(（/／:：]", "|", s)
    s = re.sub(r"[\]\)）]", "", s)
    s = re.sub(r"\|[A-Za-z][A-Za-z ].*$", "", s)
    return re.sub(r"\s+", "", s)


def rarity_aliases(rarity: str) -> list[str]:
    """Try sibling rarity codes when looking up CR (D≈-, A≈AR, CP≈-)."""
    r = (rarity or "").strip() or "-"
    r = {"Ｕ": "U", "Ａ": "A"}.get(r, r)
    aliases = {
        "D": ["D", "-"],
        "-": ["-", "D", "CP"],
        "A": ["A", "AR"],
        "AR": ["AR", "A"],
        "CP": ["CP", "-"],
        "U": ["U", "Ｕ"],
        "Ｕ": ["U", "Ｕ"],
    }
    return aliases.get(r, [r])


def match_key(set_code: str, model: str, rarity: str, name: str) -> tuple[str, str, str, str]:
    return (
        (set_code or "").upper(),
        norm_model(model),
        (rarity or "").strip() or "-",
        norm_name(name),
    )


def load_cr_items() -> list[dict]:
    if CACHE.exists():
        raw = json.loads(CACHE.read_text(encoding="utf-8"))
        print(f"cache hit · {len(raw['items'])} CR items")
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
    return all_items


def allowed_extra(extra: str, title: str) -> bool:
    """Keep blank/normal unless Beehive title clearly asks for a special."""
    e = extra or ""
    t = title or ""
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
    return True


def pick_row(rows: list[dict], title: str) -> dict | None:
    cand = [r for r in rows if allowed_extra(r["extra"], title)]
    if not cand:
        return None

    def rank(r: dict) -> tuple:
        e = r["extra"] or ""
        if e == "":
            tier = 0
        elif e == "ノーマル仕様":
            tier = 1
        elif e == "アンリミ":
            tier = 2
        else:
            tier = 3
        return (tier, len(e), -r["buyYen"])

    return sorted(cand, key=rank)[0]


def cr_image(it: dict) -> str:
    op = it.get("ocha_product") or {}
    return (op.get("image_source") or "").strip()


def main() -> None:
    data = json.loads(BH.read_text(encoding="utf-8"))
    # Refresh CR-only rows each run (like a clean re-add).
    before = len(data["cards"])
    cards = [
        c
        for c in data["cards"]
        if c.get("source") != "cardrush"
        or c.get("buyHkd") is not None
        or c.get("buyYenHareruya") is not None
    ]
    counts: Counter[str] = Counter()
    counts["stripped_cr_only"] = before - len(cards)

    cr_by_key: dict[tuple[str, str, str, str], list[dict]] = defaultdict(list)
    clean_best: dict[tuple[str, str, str, str], dict] = {}

    for it in load_cr_items():
        amount = int(it.get("amount") or 0)
        if amount < MIN_YEN or amount >= MAX_YEN:
            continue
        if SKIP_RE.search(hay(it)):
            continue
        pack = (it.get("pack_code") or "").strip().upper()
        mn = it.get("model_number") or ""
        if not pack or pack in ("その他", "OTHER") or mn.strip() in ("", "-", "旧裏"):
            continue
        parsed = parse_model(mn)
        if not parsed:
            continue
        number, set_size = parsed
        extra = (it.get("extra_difference") or "").strip()
        key = match_key(pack, f"{number}/{set_size}", it.get("rarity") or "", it.get("name") or "")
        row = {
            "id": it.get("id"),
            "buyYen": amount,
            "extra": extra,
            "name": (it.get("name") or "").strip(),
            "set": pack,
            "number": number,
            "setSize": set_size,
            "rarity": (it.get("rarity") or "").strip() or "-",
            "image": cr_image(it),
            "packName": it.get("pack_name") or "",
        }
        cr_by_key[key].append(row)
        if extra in CLEAN_EXTRA:
            prev = clean_best.get(key)
            if prev is None or pick_row([prev, row], "") is row:
                clean_best[key] = row

    unresolved: list[dict] = []
    existing_keys: set[tuple[str, str, str, str]] = set()
    existing_print_ids: set[str] = set()

    for c in cards:
        counts["existing"] += 1
        c.pop("buyYenCardrush", None)
        c.pop("cardrushId", None)
        c.pop("cardrushExtra", None)
        c.pop("cardrushName", None)

        pid = c.get("printId") or ""
        if pid:
            existing_print_ids.add(pid)

        names = [
            n
            for n in (c.get("name"), c.get("hareruyaName"))
            if n
        ] or [""]
        rows = None
        for name in names:
            for rar in rarity_aliases(c.get("rarity") or ""):
                key = match_key(
                    c.get("set") or "",
                    f"{c.get('number')}/{c.get('setSize')}",
                    rar,
                    name,
                )
                existing_keys.add(key)
                rows = cr_by_key.get(key)
                if rows:
                    break
            if rows:
                break
        existing_keys.add(
            match_key(
                c.get("set") or "",
                f"{c.get('number')}/{c.get('setSize')}",
                c.get("rarity") or "",
                c.get("name") or "",
            )
        )
        if not rows:
            counts["no_cr"] += 1
            continue
        title = c.get("title") or ""
        picked = pick_row(rows, title)
        if picked is None:
            counts["skipped_special"] += 1
            unresolved.append(
                {
                    "fullNumber": c.get("fullNumber"),
                    "title": title,
                    "extras": [r["extra"] for r in rows],
                    "buyYen": [r["buyYen"] for r in rows],
                    "reason": "only special extras; title does not ask",
                }
            )
            continue
        c["buyYenCardrush"] = picked["buyYen"]
        c["cardrushId"] = picked["id"]
        if picked["name"]:
            c["cardrushName"] = picked["name"]
        if picked["extra"]:
            c["cardrushExtra"] = picked["extra"]
        counts["matched"] += 1
        if len(rows) > 1:
            counts["resolved_multi"] += 1

    # Add clean CR-only (≥¥200), same idea as Hareruya-only.
    added = 0
    for key, row in clean_best.items():
        if key in existing_keys:
            continue
        set_code, model, rarity, _ = key
        number, set_size = row["number"], row["setSize"]
        full = f"{set_code}-{number}"
        print_id = f"{set_code} {number}/{set_size}"
        # ponytail: don't re-add when print already present under another rarity/name.
        if print_id in existing_print_ids:
            counts["skipped_existing_print"] += 1
            continue
        title = f"{print_id} {row['name']} {rarity}"
        cards.append(
            {
                "set": set_code,
                "number": number,
                "setSize": set_size,
                "fullNumber": full,
                "printId": print_id,
                "name": row["name"],
                "nameEn": "",
                "rarity": rarity,
                "buyHkd": None,
                "buyYenCardrush": row["buyYen"],
                "cardrushId": row["id"],
                "cardrushName": row["name"],
                **({"cardrushExtra": row["extra"]} if row["extra"] else {}),
                "url": "",
                "image": row["image"],
                "title": title,
                "source": "cardrush",
                "setName": row["packName"],
            }
        )
        added += 1
        existing_keys.add(key)
        existing_print_ids.add(print_id)
    counts["added_cr_only"] = added

    cards.sort(
        key=lambda c: (
            -(c.get("buyHkd") or 0),
            -(c.get("buyYenHareruya") or 0),
            -(c.get("buyYenCardrush") or 0),
            c.get("fullNumber") or "",
            c.get("rarity") or "",
        )
    )
    data["cards"] = cards

    rarity_order: list[str] = []
    seen_r: set[str] = set()
    for c in cards:
        r = c.get("rarity") or "?"
        if r not in seen_r:
            seen_r.add(r)
            rarity_order.append(r)
    data["rarityOrder"] = rarity_order

    data["cardrush"] = {
        "syncedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": SOURCE,
        "currency": "JPY",
        "note": (
            f"CR buy enrich + CR-only add. Key=set+number/setSize+rarity+name "
            f"(＆=&; []/（）/ unified). "
            f"¥{MIN_YEN}–<{MAX_YEN}. Prefer blank/ノーマル/アンリミ unless title asks "
            f"for ミラー/エラー/1ED/etc. CR-only = clean extras only."
        ),
        "addRule": (
            f"buyYen>={MIN_YEN} + buyYen<{MAX_YEN} + clean extra "
            f"(blank/ノーマル仕様/アンリミ) + not already on list"
        ),
        "counts": dict(counts) | {"totalCards": len(cards)},
    }

    BH.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    REVIEW.write_text(
        json.dumps(
            {
                "syncedAt": data["cardrush"]["syncedAt"],
                "note": "Leftovers after enrich (should be empty or tiny).",
                "counts": data["cardrush"]["counts"],
                "unresolved": unresolved,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(json.dumps(data["cardrush"]["counts"], indent=2, ensure_ascii=False))
    print(f"wrote {BH}")
    print(f"review {REVIEW} · unresolved {len(unresolved)}")

    # ponytail: smoke checks (prices move — only require a positive CR buy match)
    def must_cr_buy(pred, label: str) -> None:
        hits = [c for c in cards if pred(c)]
        assert hits, f"{label}: not found"
        yen = hits[0].get("buyYenCardrush")
        assert yen is not None and yen > 0, f"{label}: no CR buy ({hits[0].get('printId')})"

    must_cr_buy(
        lambda c: c.get("fullNumber") == "SV8-132" and c.get("rarity") == "SAR",
        "SV8-132 SAR",
    )
    must_cr_buy(
        lambda c: c.get("fullNumber") == "M2A-223" and c.get("rarity") == "MA",
        "M2A-223 MA",
    )
    cr_only = [c for c in cards if c.get("source") == "cardrush"]
    assert added == len(cr_only) and added > 500, (added, len(cr_only))
    must_cr_buy(
        lambda c: c.get("printId") == "CP5 017/036" and c.get("name") == "ミュウ",
        "CP5 017/036 ミュウ",
    )
    must_cr_buy(
        lambda c: c.get("printId") == "SV1A 100/073" and c.get("rarity") == "SAR",
        "SV1A 100/073 SAR",
    )
    assert all(
        MIN_YEN <= c["buyYenCardrush"] < MAX_YEN
        for c in cards
        if c.get("buyYenCardrush") is not None
    )
    print("self-check ok", f"cr_only={len(cr_only)}")

    enrich = ROOT / "scripts/sync_pkm_names.py"
    if enrich.exists():
        subprocess.check_call(["python3", str(enrich)])


if __name__ == "__main__":
    main()
