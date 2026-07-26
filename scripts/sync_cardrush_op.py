#!/usr/bin/env python3
"""Fetch Card Rush OP sell prices; match catalog by card number + rarity (+ image when ties)."""

from __future__ import annotations

import json
import re
import struct
import subprocess
import time
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "docs/data/catalog.json"
OUT = ROOT / "docs/data/cardrush-op.json"
BASE = "https://www.cardrush-op.jp/product-list"
PER_PAGE = 100
# Hamming distance on 8x8 aHash (0..64). Above this → fall back to cheapest.
IMG_MAX_DIST = 28

# Our Beehive rarity → Card Rush 【rarity】
RARITY_TO_CR = {
    "C": "C",
    "UC": "UC",
    "R": "R",
    "SR": "SR",
    "P-SR": "SR/P",
    "P-SRP": "SR/P",
    "SEC": "SEC",
    "P-SEC": "SEC/P",
    "P-SECP": "SEC/P",
    "SP": "SP",
    "L": "L",
    "P-L": "L/P",
    "P": "P",
    "TR": "TR",
}

TITLE_RE = re.compile(r"【([^】]+)】\{([^}]+)\}")
CODE_RE = re.compile(r"^([A-Za-z]+\d*)-(\d+)(?:\[.*\])?$")
SKIP_RE = re.compile(
    r"状態|PSA|ARS|BGS|未開封|☆SALE☆|SALE☆|鑑定済|デッキ販売|未開封BOX|未開封パック"
)
CACHE_DIR = Path("/tmp/cardrush_op_hash")


def curl(url: str) -> str:
    return subprocess.check_output(
        ["curl", "-sL", "-A", "Mozilla/5.0", "--max-time", "60", url],
        text=True,
    )


def is_clean_title(name: str) -> bool:
    if not name:
        return False
    if name.startswith("〔") or name.startswith("["):
        return False
    return SKIP_RE.search(name) is None


def norm_card_no(code: str) -> str | None:
    """OP01-121[OP05] → OP01-121 (ignore reprint set suffix)."""
    code = (code or "").strip()
    m = CODE_RE.match(code)
    if not m:
        return None
    setc, num = m.group(1).upper(), m.group(2)
    return f"{setc}-{int(num):03d}" if num.isdigit() else f"{setc}-{num}"


def parse_products(html: str) -> list[dict]:
    parts = re.split(r'<div class="item_data" data-product-id="', html)[1:]
    rows: list[dict] = []
    for part in parts:
        pid = part.split('"', 1)[0]
        m_item = re.search(r'class="item_name"[^>]*>(.*?)</p>', part, re.S)
        if not m_item:
            continue
        name = unescape(re.sub(r"<[^>]+>", "", m_item.group(1)))
        name = re.sub(r"\s+", " ", name).strip()
        m = TITLE_RE.search(name)
        if not m:
            continue
        rar_cr, code_raw = m.group(1).strip(), m.group(2).strip()
        card_no = norm_card_no(code_raw)
        if not card_no:
            continue
        if not is_clean_title(name):
            continue
        m_price = re.search(r"([\d,]+)\s*円", part)
        if not m_price:
            continue
        m_img = re.search(r'<img[^>]+src="([^"]+)"', part)
        rows.append(
            {
                "id": pid,
                "title": name,
                "rarityCr": rar_cr,
                "cardNo": card_no,
                "sellYen": int(m_price.group(1).replace(",", "")),
                "image": m_img.group(1) if m_img else "",
                "url": f"https://www.cardrush-op.jp/product/{pid}",
            }
        )
    return rows


def fetch_all() -> list[dict]:
    # Discover last page from page 1 pager links (&amp; in HTML entities)
    q = urlencode({"num": PER_PAGE, "page": 1})
    html = curl(f"{BASE}?{q}")
    pages = {int(x) for x in re.findall(r"(?:[?&]|&amp;)page=(\d+)", html)}
    last = max(pages) if pages else 1
    print(f"pages 1..{last}")
    all_rows = parse_products(html)
    print(f"page 1: {len(all_rows)} clean")
    for page in range(2, last + 1):
        q = urlencode({"num": PER_PAGE, "page": page})
        batch = parse_products(curl(f"{BASE}?{q}"))
        all_rows.extend(batch)
        if page % 10 == 0 or page == last:
            print(f"page {page}: +{len(batch)} (total clean {len(all_rows)})")
        time.sleep(0.12)
    return all_rows


def download(url: str, dest: Path) -> bool:
    if not url:
        return False
    if dest.exists() and dest.stat().st_size > 0:
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.check_call(
            [
                "curl",
                "-sL",
                "-A",
                "Mozilla/5.0",
                "--max-time",
                "45",
                "-o",
                str(dest),
                url,
            ],
            stdout=subprocess.DEVNULL,
        )
        return dest.exists() and dest.stat().st_size > 0
    except Exception:
        return False


def ahash(path: Path, size: int = 8) -> int | None:
    """Average hash via macOS sips → BMP (no Pillow)."""
    bmp = path.with_suffix(f".{size}.bmp")
    try:
        subprocess.check_call(
            [
                "sips",
                "-z",
                str(size),
                str(size),
                "-s",
                "format",
                "bmp",
                str(path),
                "--out",
                str(bmp),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return None
    data = bmp.read_bytes()
    if len(data) < 40:
        return None
    off = struct.unpack_from("<I", data, 10)[0]
    w, h = struct.unpack_from("<ii", data, 18)
    bpp = struct.unpack_from("<H", data, 28)[0]
    top_down = h < 0
    h = abs(h)
    if w <= 0 or h <= 0 or bpp not in (24, 32):
        return None
    row = ((bpp * w + 31) // 32) * 4
    pixels: list[int] = []
    for y in range(h):
        src_y = y if top_down else (h - 1 - y)
        row_off = off + src_y * row
        for x in range(w):
            if bpp == 32:
                b, g, r = data[row_off + 4 * x : row_off + 4 * x + 3]
            else:
                b, g, r = data[row_off + 3 * x : row_off + 3 * x + 3]
            pixels.append((r + g + b) // 3)
    avg = sum(pixels) / len(pixels)
    bits = 0
    for i, p in enumerate(pixels):
        if p >= avg:
            bits |= 1 << i
    return bits


def ham(a: int, b: int) -> int:
    return (a ^ b).bit_count()


def pick_best(card_img: str, candidates: list[dict], hash_cache: dict) -> dict:
    if len(candidates) == 1:
        return candidates[0]
    # Prefer image match when Beehive art is available
    bee_hash = None
    if card_img:
        bee_path = CACHE_DIR / f"bee_{abs(hash(card_img)) & 0xFFFFFFFF:x}.img"
        if download(card_img, bee_path):
            if bee_path not in hash_cache:
                hash_cache[bee_path] = ahash(bee_path)
            bee_hash = hash_cache[bee_path]

    best = None
    best_dist = 999
    if bee_hash is not None:
        for c in candidates:
            if not c.get("image"):
                continue
            cr_path = CACHE_DIR / f"cr_{c['id']}.img"
            if not download(c["image"], cr_path):
                continue
            if cr_path not in hash_cache:
                hash_cache[cr_path] = ahash(cr_path)
            h = hash_cache[cr_path]
            if h is None:
                continue
            d = ham(bee_hash, h)
            if d < best_dist:
                best_dist = d
                best = c
        if best is not None and best_dist <= IMG_MAX_DIST:
            return best

    # Fallback: cheapest clean listing
    return min(candidates, key=lambda c: c["sellYen"])


def self_check() -> None:
    assert norm_card_no("OP01-121[OP05]") == "OP01-121"
    assert norm_card_no("OP01-121") == "OP01-121"
    assert is_clean_title("ヤマト【SEC】{OP01-121} [ヤマト]")
    assert not is_clean_title("〔状態A-〕ヤマト【SEC】{OP01-121}")
    assert not is_clean_title("〔PSA10鑑定済〕ヤマト【SEC】{OP01-121}")
    assert not is_clean_title("ヤマト(未開封)【SR】{OP16-032}")
    assert RARITY_TO_CR["P-SEC"] == "SEC/P"
    print("self-check ok")


def main() -> None:
    self_check()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    products = fetch_all()
    # Index: (cardNo, crRarity) → candidates
    idx: dict[tuple[str, str], list[dict]] = {}
    for p in products:
        key = (p["cardNo"], p["rarityCr"])
        idx.setdefault(key, []).append(p)

    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    cards = catalog.get("cards") or []
    by_key: dict[str, dict] = {}
    hash_cache: dict = {}
    matched = 0
    multi = 0
    img_picked = 0

    # Unique catalog keys (same reprint may appear in OP01 + PRB01)
    seen: set[str] = set()
    for card in cards:
        fn = card.get("fullNumber") or ""
        rar = card.get("rarity") or ""
        our_key = f"{fn}|{rar}"
        if not fn or not rar or our_key in seen:
            continue
        seen.add(our_key)
        cr_rar = RARITY_TO_CR.get(rar)
        if not cr_rar:
            continue
        cands = idx.get((fn, cr_rar)) or []
        if not cands:
            # try unpadded? already normalized
            continue
        if len(cands) > 1:
            multi += 1
            cheapest = min(cands, key=lambda c: c["sellYen"])
            best = pick_best(card.get("image") or "", cands, hash_cache)
            used_img = best["id"] != cheapest["id"]
            if used_img:
                img_picked += 1
            matched_by = "image" if used_img else "cheapest"
        else:
            best = cands[0]
            matched_by = "unique"
        matched += 1
        by_key[our_key] = {
            "sellYen": best["sellYen"],
            "url": best["url"],
            "title": best["title"],
            "productId": best["id"],
            "rarityCr": best["rarityCr"],
            "matchedBy": matched_by,
        }

    out = {
        "syncedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": BASE,
        "currency": "JPY",
        "match": "fullNumber + rarity (CR 【 】); ignore [set] suffix; skip 状態/PSA/ARS/BGS/未開封/SALE; image aHash on ties",
        "counts": {
            "cleanProducts": len(products),
            "indexedKeys": len(idx),
            "catalogKeys": len(seen),
            "matched": matched,
            "multiCandidateKeys": multi,
            "imageOverrodeCheapest": img_picked,
        },
        "byKey": by_key,
    }
    OUT.write_text(
        json.dumps(out, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(json.dumps(out["counts"], indent=2, ensure_ascii=False))
    # spot-check Yamato
    for k in ("OP01-121|SEC", "OP01-121|P-SEC", "OP01-121|SP"):
        print(k, by_key.get(k))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
