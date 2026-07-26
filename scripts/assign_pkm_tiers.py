#!/usr/bin/env python3
"""Assign Bulbapedia 2025 visit-rank tiers to Pokemon JP cards.

Only Pokémon species cards get a tier (S/A/B/C). Trainers/items/energy/etc. cleared.
Source: Bulbapedia most→least visited Pokémon articles in 2025 (1025 species).

Cuts (rank 1 = most visited):
  S: 1–20
  A: 21–100
  B: 101–250
  C: 251–1025
"""

from __future__ import annotations

import json
import re
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BH = ROOT / "docs/data/pkmjp-buylist.json"
TIERS_OUT = ROOT / "docs/data/pkm-species-tiers.json"
CSV_CACHE = ROOT / "scripts/.cache/pokemon_species_names.csv"
BULBA = Path(
    "/Users/edwinyim/.cursor/projects/Users-edwinyim-Documents-one-piece/uploads/"
    "Bulbapedia_Most_and_least_visited_Pok_mon_articles_in_2025-0.md"
)

CUTS = {"S": 20, "A": 100, "B": 250, "C": 1025}


def ensure_species_csv() -> str:
    if CSV_CACHE.exists() and CSV_CACHE.stat().st_size > 1000:
        return CSV_CACHE.read_text(encoding="utf-8")
    CSV_CACHE.parent.mkdir(parents=True, exist_ok=True)
    url = "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv/pokemon_species_names.csv"
    data = subprocess.check_output(
        ["curl", "-sL", "-A", "Mozilla/5.0", "--max-time", "60", url],
        text=True,
    )
    CSV_CACHE.write_text(data, encoding="utf-8")
    return data


def load_species_maps() -> tuple[dict[str, str], dict[str, str]]:
    """Return (ja→en, en_lower→en_canonical)."""
    from collections import defaultdict

    csv = ensure_species_csv()
    by_id: dict[str, dict[str, str]] = defaultdict(dict)
    for line in csv.strip().splitlines()[1:]:
        parts = line.split(",")
        if len(parts) < 3:
            continue
        sid, lang, name = parts[0], parts[1], parts[2]
        if lang in ("9", "11", "1"):
            by_id[sid][lang] = name
    ja_en: dict[str, str] = {}
    en_canon: dict[str, str] = {}
    for m in by_id.values():
        en = m.get("9")
        ja = m.get("11") or m.get("1")
        if en and ja:
            ja_en[ja] = en
            en_canon[en.lower()] = en
    return ja_en, en_canon


def parse_bulba_ranks(text: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for m in re.finditer(r"^\|\s*(\d+)\s*\|\s*\[([^\]]+)\]", text, re.M):
        out[m.group(2).strip()] = int(m.group(1))
    return out


def tier_for_rank(rank: int) -> str:
    if rank <= CUTS["S"]:
        return "S"
    if rank <= CUTS["A"]:
        return "A"
    if rank <= CUTS["B"]:
        return "B"
    return "C"


def strip_combat(name: str) -> str:
    s = name or ""
    s = re.sub(r"[:：/\*].+$", "", s)
    s = re.sub(r"[（(][^）)]+[）)]", "", s)
    for suf in ("VMAX", "VSTAR", "V-UNION", "BREAK", "GX", "EX", "ex", "V"):
        if s.endswith(suf):
            s = s[: -len(suf)]
    s = re.sub(r"^(?:メガ|Mega\s+)", "", s, flags=re.I)
    s = re.sub(r"^M(?=[A-Zア-ン])", "", s)
    s = re.sub(r"\s+[XY]$", "", s, flags=re.I)
    s = re.sub(r"[XY]$", "", s)
    # Trainer's / Owner's Pokémon
    s = re.sub(r"^[^']+'s\s+", "", s, flags=re.I)
    s = re.sub(r"^.+の", "", s)
    s = s.replace("◇", "").replace("☆", "").replace("★", "")
    return s.strip()


def build_en_re(names: list[str]) -> re.Pattern[str]:
    # longest first so "Mr. Mime" wins over shorter fragments
    parts = []
    for n in sorted(names, key=len, reverse=True):
        if len(n) <= 2:
            continue
        p = re.escape(n).replace(r"\'", r"['’]?").replace(r"\ ", r"[\s\-]+")
        parts.append(p)
    return re.compile(rf"(?<![A-Za-z])(?:{'|'.join(parts)})(?![A-Za-z])", re.I)


def build_ja_re(names: list[str]) -> re.Pattern[str]:
    parts = [re.escape(n) for n in sorted(names, key=len, reverse=True) if len(n) >= 2]
    return re.compile("|".join(parts))


def find_species(
    card: dict,
    en_re: re.Pattern[str],
    ja_re: re.Pattern[str],
    ja_en: dict[str, str],
    en_canon: dict[str, str],
    rank_en: dict[str, int],
) -> str | None:
    texts: list[str] = []
    for k in ("nameEn", "name", "cardrushName", "hareruyaName"):
        v = (card.get(k) or "").strip()
        if v:
            texts.append(v)
            texts.append(strip_combat(v))

    for t in texts:
        m = en_re.search(t)
        if m:
            hit = m.group(0)
            # normalize spaced/hyphen variants back to canon
            key = re.sub(r"[\s\-]+", " ", hit.lower())
            if key in en_canon:
                return en_canon[key]
            # try collapsing spaces for Type: Null etc.
            for en, canon in en_canon.items():
                if en.replace(" ", "") == key.replace(" ", "").replace("-", ""):
                    return canon
            return en_canon.get(hit.lower(), hit)

    for t in texts:
        m = ja_re.search(t)
        if m:
            en = ja_en[m.group(0)]
            if en in rank_en or en.lower() in en_canon:
                return en_canon.get(en.lower(), en)
    return None


def main() -> None:
    ranks = parse_bulba_ranks(BULBA.read_text(encoding="utf-8"))
    print(f"bulba ranks={len(ranks)}", flush=True)
    ja_en, en_canon = load_species_maps()
    # only species that appear in Bulba list (and JP that map to them)
    ranked_en = [n for n in ranks if n.lower() in en_canon or n in ranks]
    # use Bulba spelling as canon when present
    for n, r in ranks.items():
        en_canon.setdefault(n.lower(), n)
    ja_ranked = {ja: en for ja, en in ja_en.items() if en in ranks or en.lower() in {x.lower() for x in ranks}}
    en_re = build_en_re(list(ranks.keys()))
    ja_re = build_ja_re(list(ja_ranked.keys()))
    print(f"matchers en={en_re.pattern.count('|')+1} ja={len(ja_ranked)}", flush=True)

    data = json.loads(BH.read_text(encoding="utf-8"))
    cards = data["cards"]
    by_tier: dict[str, list[str]] = {"S": [], "A": [], "B": [], "C": []}
    seen_species: set[str] = set()

    assigned = skipped = 0
    for c in cards:
        c.pop("tier", None)
        c.pop("tierRank", None)
        sp = find_species(c, en_re, ja_re, ja_ranked, en_canon, ranks)
        if not sp:
            skipped += 1
            continue
        rank = ranks.get(sp)
        if rank is None:
            # case fold
            rank = next((r for n, r in ranks.items() if n.lower() == sp.lower()), None)
        if rank is None:
            skipped += 1
            continue
        tier = tier_for_rank(rank)
        c["tier"] = tier
        c["tierRank"] = rank
        assigned += 1
        if sp not in seen_species:
            seen_species.add(sp)
            by_tier[tier].append(sp)

    for t in by_tier:
        by_tier[t].sort(key=lambda n: ranks.get(n, 9999))

    meta = {
        "source": "https://bulbapedia.bulbagarden.net/wiki/Bulbapedia:Most_and_least_visited_Pok%C3%A9mon_articles_in_2025",
        "note": "Visit popularity 2025. Trainers/items/energy get no tier.",
        "cuts": CUTS,
        "speciesCount": len(ranks),
        "tiers": by_tier,
    }
    TIERS_OUT.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    BH.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    print(
        f"assigned={assigned} skipped(non-pkm/unmatched)={skipped} "
        f"species_used={len(seen_species)}",
        flush=True,
    )
    print("card tiers", Counter(c.get("tier") for c in cards if c.get("tier")), flush=True)

    # spot-check
    for want in (
        "Mega Charizard X ex",
        "Iono",
        "Basic Fire Energy",
        "Boss's Orders",
        "Iono's Bellibolt ex",
        "Pikachu",
        "Eevee",
    ):
        hits = [c for c in cards if (c.get("nameEn") or "") == want][:1]
        if hits:
            h = hits[0]
            print(f"  check {want!r} → tier={h.get('tier')} rank={h.get('tierRank')}", flush=True)


if __name__ == "__main__":
    main()
