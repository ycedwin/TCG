#!/usr/bin/env python3
"""Add English character names (nameEn) to Pokemon JP buylist cards."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "docs/data/pkmjp-buylist.json"
OUT_MAP = ROOT / "docs/data/pkm-names-jp-en.json"

TRAINERS = {
    "ナンジャモ": "Iono",
    "リーリエ": "Lillie",
    "シロナ": "Cynthia",
    "ヒビキ": "Ethan",
    "サザレ": "Lacey",
    "キハダ": "Giacomo",
    "ボタン": "Penny",
    "オモダカ": "Clavell",
    "ゼイユ": "Carmine",
    "スグリ": "Drayton",
    "アカマツ": "Briar",
    "ブライア": "Briar",
    "ブリアー": "Briar",
    "ブリア": "Briar",
    "ベル": "Bianca",
    "メイ": "May",
    "カスミ": "Misty",
    "グラジオ": "Gladion",
    "マツバ": "Will",
    "ルチア": "Lisia",
    "メロン": "Melony",
    "セレナ": "Serena",
    "マリィ": "Marnie",
    "サイトウ": "Bea",
    "ルリナ": "Nessa",
    "ネズ": "Piers",
    "ダンデ": "Leon",
    "キバナ": "Raihan",
    "アスナ": "Klara",
    "クララ": "Klara",
    "サナ": "Shauna",
    "カルネ": "Diantha",
    "ペパー": "Arven",
    "ピーニャ": "Ortega",
    "ミモザ": "Miriam",
    "エリカ": "Erika",
    "スイレン": "Lana",
    "トウコ": "Hilda",
    "カリン": "Karen",
    "グルーシャ": "Grusha",
    "カシオペア": "Cassiopeia",
    "ネルケ": "Clive",
    "カナリィ": "Canary",
    "ミカン": "Jasmine",
    "フヨウ": "Falkner",
    "サカキ": "Giovanni",
    "ビワ": "Poppy",
    "ポピー": "Poppy",
    "タロ": "Lacey",
    "アセロラ": "Acerola",
    "セイボリー": "Amarys",
    "チリ": "Crispin",
    "リップ": "Cyrano",
    "フトゥー博士": "Professor Turo",
    "オーリム博士": "Professor Sada",
    "ヒカリ": "Dawn",
    "サワロ": "Hassel",
    "ネモ": "Nemona",
    "ロケット団": "Team Rocket",
    "サビ組": "Team Star",
    "パラソルおねえさん": "Parasol Lady",
    "マスタード": "Mustard",
    "N": "N",
    "リコ": "Liko",
    "ロイ": "Roy",
    "ハプウ": "Hapu",
    "フウロ": "Skyla",
    "モミ": "Cheryl",
    "トウキ": "Morty",
    "アイリス": "Iris",
    "ジニア": "Briar",  # fallback; ジニア is Briar? actually ジニア = Giacomo no - ジニア is Brassius
    "カキツバタ": "Brassius",
    "マチス": "Lt. Surge",
    "ネリネ": "Amarys",
    "ユカリ": "Gardenia",
    "メロコ": "Mela",
    "オルティガ": "Atticus",
    "ユウリ": "Gloria",
    "アクロマ": "Colress",
    "ナタネ": "Gardenia",
    "シアノ": "Lacey",
    "ミツル": "Wally",
    "ダイゴ": "Steven",
    "ラムダ": "Petrel",
    "アテナ": "Ariana",
    "ランス": "Proton",
    "ジャッジマン": "Judge",
    "サーファー": "Surf Enthusiast",
    "パルデアの学生": "Student",
    "ガラルの仲間たち": "Friends in Galar",
    "ボスの指令": "Boss's Orders",
    "博士の研究": "Professor's Research",
    "ネストボール": "Nest Ball",
    "なかよしポフィン": "Buddy-Buddy Poffin",
    "学習装置": "Exp. Share",
    "すごいつりざお": "Super Rod",
    "カウンターキャッチャー": "Counter Catcher",
    "力の砂時計": "Power Hourglass",
    "ゼロの大空洞": "Area Zero Underdepths",
    "いちげきエネルギー": "Single Strike Energy",
    "れんげきエネルギー": "Rapid Strike Energy",
    "うねりの扇": "Rescue Carrier",
    "暗号マニアの解読": "Cryptomaniac's Decoding",
    "グラビティーマウンテン": "Gravity Mountain",
    "ポケモンいれかえ": "Switch",
    "アンフェアスタンプ": "Unfair Stamp",
    "大地の器": "Earthen Vessel",
    "夜のタンカ": "Night Stretcher",
    "ふしぎなアメ": "Rare Candy",
    "基本闘エネルギー": "Basic Fighting Energy",
    "基本炎エネルギー": "Basic Fire Energy",
    "基本水エネルギー": "Basic Water Energy",
    "基本草エネルギー": "Basic Grass Energy",
    "基本雷エネルギー": "Basic Lightning Energy",
    "基本超エネルギー": "Basic Psychic Energy",
    "基本悪エネルギー": "Basic Darkness Energy",
    "基本鋼エネルギー": "Basic Metal Energy",
    "MCの盛り上げ": "Hometown Mulligan",
    "シトロン": "Clemont",
    "アオキ": "Kieran",
    "アポロ": "Archer",
    "アンズ": "Janine",
    "クセロシキ": "Cyrus",
    "オニオン": "Allister",
    "ナナミ": "Lana",
    "マサキ": "Bill",
    "パルデアの仲間たち": "Friends in Paldea",
    "ルミナスエネルギー": "Luminous Energy",
    "ネオアッパーエネルギー": "Neo Upper Energy",
    "リバーサルエネルギー": "Reversal Energy",
    "ジェットエネルギー": "Jet Energy",
    "活力の壺": "Earthen Vessel",
    "改造ハンマー": "Enhanced Hammer",
    "スーパーエネルギー回収": "Super Energy Retrieval",
    "ボウルタウン": "Town Store",
    # Remaining buylist misses (trainers / items / forms)
    "ムク": "Muku",
    "ホミカ": "Klara",
    "チェレン": "Cheren",
    "ローズ": "Rose",
    "シキミ": "Shauna",
    "ヒョウタ": "Roark",
    "マコモ": "Shauntal",
    "ハヤト": "Falkner",
    "ハッサク": "Ramos",
    "ピュール": "Tulip",
    "ザクロ": "Grimsley",
    "ポプラ": "Opal",
    "ヤロー": "Milo",
    "ハイダイ": "Piers",
    "ドラセナ": "Drasna",
    "ウォロ": "Ghetsis",
    "マスター": "Master",
    "クラウン": "Crown",
    "クラベル": "Clavell",
    "カエデ": "Billie",
    "ライム": "Geeta",
    "センリ": "Norman",
    "ゴヨウ": "Cilan",
    "セイジ": "Sage",
    "レホール": "Rika",
    "ホップ": "Hop",
    "タラゴン": "Tarragon",
    "ジプソ": "Gypso",
    "マチエール": "Matière",
    "バーベナ": "Verbena",
    "ヘレナ": "Helena",
    "バーベナとヘレナ": "Verbena & Helena",
    "ソッド": "Sod",
    "シルディ": "Sildy",
    "ソッドとシルディ": "Sod & Sildy",
    "スター団": "Team Star",
    "ポリゴンZ": "Porygon-Z",
    "緊急ボード": "Emergency Board",
    "シークレットボックス": "Secret Box",
    "カウンターゲイン": "Counter Gain",
    "スパイクエネルギー": "Sparkling Energy",
    "ハッコウシティ": "Levincia",
    "ビーチコート": "Beach Court",
    "勇気のおまもり": "Hero's Charm",
    "探検家の先導": "Explorer's Guidance",
    "冒険家の発見": "Adventurer's Discovery",
    "とりつかい": "Bird Keeper",
    "ボールガイ": "Ball Guy",
    "カブ": "Kabu",
    "コック": "Cook",
    "怖いお兄さん": "Scary Man",
    "ひふきやろう": "Firebreather",
    "からておうの稽古": "Black Belt's Training",
    "ポケパッド": "PokéPad",
    "ワンダーパッチ": "Wonder Patch",
    "エネルギー回収": "Energy Retrieval",
    "スペシャルレッドカード": "Special Red Card",
    "プリズムタワー": "Prism Tower",
    "アイアンディフェンダー": "Iron Defender",
    "エネルギーつけかえ": "Energy Switch",
    "ダークベル": "Dark Bell",
    "ごうかいボム": "Big Bomb",
    "ゴージャスマント": "Luxury Mantle",
    "偉大な大樹": "Grand Tree",
    "リッチエネルギー": "Rich Energy",
    "シトロンの機転": "Clemont's Quick Wit",
    "アオキの手際": "Kieran's Skill",
    "アクロマの実験": "Colress's Experiment",
    "アンズの秘技": "Janine's Secret Technique",
    "クセロシキのたくらみ": "Cyrus's Conspiracy",
    "ナナミの手助け": "Lana's Aid",
    "マサキの転送": "Bill's Transfer",
    "ホミカの演奏": "Klara's Performance",
    "チェレンの気くばり": "Cheren's Care",
    "AZの安らぎ": "AZ's Serenity",
    "スター団のしたっぱ": "Team Star Grunt",
    "ホップのウールー": "Hop's Wooloo",
    "ポワルン たいようのすがた": "Castform Sunny Form",
    "ポリゴンＺ": "Porygon-Z",
}

# Fix mis-maps
TRAINERS["ジニア"] = "Brassius"
TRAINERS["トウキ"] = "Morty"

FORMS = {
    "みどりのめん": "Teal Mask",
    "いどのめん": "Wellspring Mask",
    "かまどのめん": "Hearthflame Mask",
    "いしずえのめん": "Cornerstone Mask",
    "アカツキ": "Bloodmoon",
    "れんげきのかた": "Rapid Strike Style",
    "いちげきのかた": "Single Strike Style",
    "たいようのすがた": "Sunny Form",
    "あまみずのすがた": "Rainy Form",
    "ゆきぐものすがた": "Snowy Form",
}

# Leading form tokens glued to species
LEAD_FORMS = {
    "はくば": "Ice Rider",
    "こくば": "Shadow Rider",
    "オリジン": "Origin Forme",
}

TITLES = {
    "決心": "Determination",
    "冒険": "Adventure",
    "まごころ": "Sincerity",
    "確信": "Conviction",
    "したっぱ": "Grunt",
    "元気": "Spirit",
    "決戦": "Showdown",
    "アピール": "Appeal",
    "はげまし": "Encouragement",
    "招待": "Invitation",
    "筋書き": "Plan",
    "お世話": "Care",
    "信念": "Conviction",
    "まなざし": "Gaze",
    "カリスマ": "Charisma",
    "いたずら": "Prank",
    "シナリオ": "Scenario",
    "指令": "Orders",
    "予感": "Premonition",
    "闘志": "Fighting Spirit",
    "取引": "Transaction",
    "思いやり": "Compassion",
    "気迫": "Vitality",
    "執念": "Obsession",
    "活気": "Energy",
    "機転": "Quick Wit",
    "手際": "Skill",
    "実験": "Experiment",
    "秘技": "Secret Technique",
    "たくらみ": "Conspiracy",
    "手助け": "Aid",
    "転送": "Transfer",
    "演奏": "Performance",
    "気くばり": "Care",
    "安らぎ": "Serenity",
    "発見": "Discovery",
    "先導": "Guidance",
    "稽古": "Training",
}

PREFIXES = [
    ("ガラル", "Galarian"),
    ("パルデア", "Paldean"),
    ("ヒスイ", "Hisuian"),
    ("アローラ", "Alolan"),
    ("ホワイト", "White"),
    ("ブラック", "Black"),
    ("れんげき", "Rapid Strike"),
    ("いちげき", "Single Strike"),
]


def curl(url: str) -> str:
    return subprocess.check_output(
        ["curl", "-sL", "-A", "Mozilla/5.0", "--max-time", "60", url],
        text=True,
    )


def load_species() -> dict[str, str]:
    csv = curl(
        "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv/pokemon_species_names.csv"
    )
    from collections import defaultdict

    by_id: dict[str, dict[str, str]] = defaultdict(dict)
    for line in csv.strip().splitlines()[1:]:
        parts = line.split(",")
        if len(parts) < 3:
            continue
        sid, lang, name = parts[0], parts[1], parts[2]
        if lang in ("9", "11", "1"):
            by_id[sid][lang] = name
    out: dict[str, str] = {}
    for m in by_id.values():
        en = m.get("9")
        ja = m.get("11") or m.get("1")
        if en and ja:
            out[ja] = en
    return out


def strip_suffixes(name: str) -> tuple[str, str, list[str]]:
    suffixes: list[str] = []
    rest = name
    while True:
        if rest.endswith("VMAX"):
            suffixes.append("VMAX")
            rest = rest[:-4]
            continue
        if rest.endswith("VSTAR"):
            suffixes.append("VSTAR")
            rest = rest[:-5]
            continue
        if rest.endswith("V-UNION"):
            suffixes.append("V-UNION")
            rest = rest[:-7]
            continue
        if rest.endswith("GX"):
            suffixes.append("GX")
            rest = rest[:-2]
            continue
        if rest.endswith("ex"):
            suffixes.append("ex")
            rest = rest[:-2]
            continue
        if rest.endswith("V"):
            suffixes.append("V")
            rest = rest[:-1]
            continue
        break
    form_xy = ""
    if rest.endswith("X") or rest.endswith("Y"):
        form_xy = rest[-1]
        rest = rest[:-1]
    return rest, form_xy, list(reversed(suffixes))


def make_translator(species: dict[str, str]):
    species_sorted = sorted(species.items(), key=lambda x: -len(x[0]))
    trainers_sorted = sorted(TRAINERS.items(), key=lambda x: -len(x[0]))
    forms_sorted = sorted(FORMS.items(), key=lambda x: -len(x[0]))
    lead_sorted = sorted(LEAD_FORMS.items(), key=lambda x: -len(x[0]))

    def lookup_species(token: str) -> str | None:
        for jp, en in species_sorted:
            if token == jp:
                return en
        return None

    def lookup_trainer(token: str) -> str | None:
        for jp, en in trainers_sorted:
            if token == jp:
                return en
        return None

    def translate(name: str) -> str | None:
        rest, form_xy, suffixes = strip_suffixes(name.strip())

        def finish(base: str) -> str:
            bits = [base]
            if form_xy:
                bits.append(form_xy)
            bits.extend(suffixes)
            return " ".join(bits)

        t = lookup_trainer(rest)
        if t:
            return finish(t)

        # 博士の研究[アララギ博士]
        m = re.match(r"博士の研究\[(.+)\]$", rest)
        if m:
            return "Professor's Research"

        m = re.match(r"ボスの指令\[(.+)\]$", rest)
        if m:
            return "Boss's Orders"

        if "の" in rest:
            left, right = rest.split("の", 1)
            left_en = lookup_trainer(left) or lookup_species(left)
            if left_en and right in TITLES:
                return f"{left_en}'s {TITLES[right]}"
            pre: list[str] = []
            r = right
            for jp, en in PREFIXES:
                if r.startswith(jp):
                    pre.append(en)
                    r = r[len(jp) :]
                    break
            right_en = lookup_species(r) or lookup_trainer(r)
            if left_en and right_en:
                mid = " ".join(pre + [right_en])
                return finish(f"{left_en}'s {mid}")

        for fjp, fen in forms_sorted:
            if rest.endswith(fjp):
                head = rest[: -len(fjp)]
                sen = lookup_species(head)
                if sen:
                    # Bloodmoon Ursaluna reads better as form first
                    if fjp == "アカツキ":
                        return finish(f"{fen} {sen}")
                    return finish(f"{sen} {fen}")

        if " " in rest:
            a_jp, b_jp = rest.split(" ", 1)
            a = lookup_trainer(a_jp) or lookup_species(a_jp)
            b = FORMS.get(b_jp) or lookup_trainer(b_jp) or lookup_species(b_jp)
            if a and b:
                return finish(f"{a} {b}")

        for jp, en in lead_sorted:
            if rest.startswith(jp):
                sen = lookup_species(rest[len(jp) :])
                if sen:
                    return finish(f"{en} {sen}")

        for jp, en in PREFIXES:
            if rest.startswith(jp):
                sen = lookup_species(rest[len(jp) :])
                if sen:
                    return finish(f"{en} {sen}")

        # Exact species before Mega-split (メガヤンマ = Yanmega)
        sen = lookup_species(rest)
        if sen:
            return finish(sen)

        if rest.startswith("メガ"):
            sen = lookup_species(rest[2:])
            if sen:
                return finish(f"Mega {sen}")

        return None

    return translate


def main() -> None:
    species = load_species()
    translate = make_translator(species)

    OUT_MAP.write_text(
        json.dumps(
            {
                "species": species,
                "trainers": TRAINERS,
                "forms": FORMS,
                "leadForms": LEAD_FORMS,
                "titles": TITLES,
                "prefixes": dict(PREFIXES),
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )

    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    ok = miss = 0
    for c in data.get("cards") or []:
        # Prefer existing; else translate Beehive name, then Hareruya JP name
        en = (c.get("nameEn") or "").strip()
        if not en:
            en = translate(c.get("name") or "") or ""
        if not en and c.get("hareruyaName"):
            en = translate(c["hareruyaName"]) or ""
        # Full-string trainer/item overrides (exact card titles)
        if not en:
            for src in (c.get("name"), c.get("hareruyaName")):
                if src and src in TRAINERS:
                    en = TRAINERS[src]
                    break
        c["nameEn"] = en or ""
        if en:
            ok += 1
        else:
            miss += 1

    CATALOG.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"nameEn ok={ok} miss={miss} wrote {CATALOG}")
    print(f"wrote {OUT_MAP}")


if __name__ == "__main__":
    main()
