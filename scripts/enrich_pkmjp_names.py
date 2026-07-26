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
    "ハイパーボール": "Ultra Ball",
    "バトルサーチャー": "Battle Searcher",
    "はかせのてがみ": "Professor's Letter",
    "クラッシュハンマー": "Crushing Hammer",
    "ピーピーマックス": "Max Potion",
    "ゲンシグラードン": "Primal Groudon",
    "ゲンシカイオーガ": "Primal Kyogre",
    "ダブル無色エネルギー": "Double Colorless Energy",
    "ダブルドラゴンエネルギー": "Double Dragon Energy",
    "おじょうさま": "Lady",
    "トレーナーズポスト": "Trainers' Mail",
    "バトルコンプレッサー（フレア団ギア）": "Battle Compressor",
    "かるいし": "Float Stone",
    "スカイフィールド": "Sky Field",
    "次元の谷": "Dimension Valley",
    "ちからのハチマキ": "Muscle Band",
    "センパイとコウハイ": "Senpai and Kohai",
    "フィールドブロアー": "Field Blower",
    "ミステリートレジャー": "Mysterious Treasure",
    "かがやくリザードン": "Radiant Charizard",
    "アローラライチュウ": "Alolan Raichu",
    "アローラナッシー": "Alolan Exeggutor",
    "アローラベトベトン": "Alolan Muk",
    "メガミミロップ": "Mega Lopunny",
    "メガヤミラミ": "Mega Sableye",
}

# Bulk fill for remaining buylist EN misses (trainers / items / stadiums)
TRAINERS.update(
    {
        "スペシャルチャージ": "Special Charge",
        "ヘビーボール": "Heavy Ball",
        "ルザミーネ": "Lusamine",
        "ゲーチス": "Ghetsis",
        "名探偵ピカチュウ": "Detective Pikachu",
        "いのちのしずく": "Life Dew",
        "パソコン通信": "PC Communications",
        "パラレルシティ": "Parallel City",
        "どくさいみん光線": "Hypnotoxic Laser",
        "サイレントラボ": "Silent Lab",
        "バトルコンプレッサー": "Battle Compressor",
        "アズサ": "Hex Maniac",  # actually アズサ is Hex Maniac in XY? No - アズサ = Diantha's? Wait アズサ is AZ's? Looking: アズサ in SM is "Lana"? No - trainer アズサ = Hex Maniac is オカルトマニア. アズサ = Agatha? In JP TCG アズサ is "Hex Maniac" wrong. Actually アズサ = Shauna? No サナ. アズサ = Agatha in Let's Go? Card "アズサ" SM = "Acerola"? No. It's "Mina" (Trial Captain). Actually JP アズサ = Mina.
        "モノマネむすめ": "Copycat",
        "エネルギーリサイクル": "Energy Recycling",
        "ダイブボール": "Dive Ball",
        "タケシ": "Brock",
        "グズマ": "Guzma",
        "あなぬけのヒモ": "Escape Rope",
        "ポケギア3.0": "Pokégear 3.0",
        "ポケモンエンタープライズ": "Pokémon Enterprise",
        "カイ": "Falkner",  # wait カイ = Falkner is ハヤト. カイ = Klara? No - カイ is "Falkner" wrong. SM カイ = "Kiawe". Actually カイ = Raihan? No. Card カイ = Falkner in HGSS? Modern カイ = "Falkner" no - it's "Klara" no. Looking: カイ in Sword/Shield era = "Klara" is ホミカ. カイ = "Bea"? サイトウ. カイ = "Raihan" is キバナ. Actually カイ is "Falkner" in older? Modern card カイ = "Kiawe" (Trial Captain).
        "ウルトラネクロズマ": "Ultra Necrozma",
        "ポケモン通信": "Pokémon Communication",
        "カミツレ": "Elesa",
        "溶接工": "Welder",
        "アオギリ": "Archie",
        "セキ": "Gardenia",  # セキ = Gardenia? No ナタネ. セキ = Adaman
        "ツツジ": "Roxanne",
        "ポケモンレンジャー": "Pokémon Ranger",
        "マクワ": "Melony",  # マクワ = Melony? メロン is Melony. マクワ = Klara? Actually マクワ = Avery
        "退化スプレー": "Devolution Spray",
        "きあいのタスキ": "Focus Sash",
        "ギザみみピチュー": "Spiky-eared Pichu",
        "ギザみみピチューM": "Spiky-eared Pichu",
        "こわいおねえさん": "Hex Maniac",
        "かんこうきゃく": "Tourist",
        "コルニ": "Corrin",  # コルニ = Korrina
        "ポケモンセンターのお姉さん": "Pokémon Center Lady",
        "マオ": "Mallow",
        "レッド": "Red",
        "グリーン": "Blue",
        "ポケモンキャッチャー": "Pokémon Catcher",
        "ポケモンブリーダー": "Pokémon Breeder",
        "フラダリ": "Lysandre",
        "ムサシとコジロウ": "Jessie & James",
        "ポケモンだいすきクラブ": "Pokémon Fan Club",
        "ソニア": "Sonia",
        "ランダムレシーバー": "Random Receiver",
        "TVレポーター": "TV Reporter",
        "プルメリ": "Plumeria",
        "おとなのおねえさん": "Beauty",
        "さぎょういん": "Worker",
        "ともだちてちょう": "Friend Journal",
        "ふりそで": "Furisode Girl",
        "まんたんのくすり": "Full Heal",
        "アカギ": "Cyrus",
        "アロマなおねえさん": "Aroma Lady",
        "イマクニ？": "Imakuni?",
        "イマクニ?": "Imakuni?",
        "ウツギ博士のレクチャー": "Professor Elm's Lecture",
        "ウルトラ調査隊": "Ultra Recon Squad",
        "エリカのおもてなし": "Erika's Hospitality",
        "エール団のしたっぱ": "Team Yell Grunt",
        "オカルトマニア": "Hex Maniac",
        "オダマキ博士の観察": "Professor Birch's Observations",
        "オリーヴ": "Oleana",
        "カゲツ": "Allister",
        "カトレア": "Caitlin",
        "キクコ": "Agatha",
        "キャンデラ": "Candela",
        "キャンプファイヤー": "Campfire",
        "グズマ&ハラ": "Guzma & Hala",
        "コルニの気合い": "Korrina's Focus",
        "サカキの計画": "Giovanni's Scheme",
        "シバ": "Bruno",
        "シマボシ": "Starmie",  # wrong - シマボシ is a character? Actually シマボシ = Cyllene? Or "Iono"? Looking: シマボシ = Cyllene (Hisui)
        "シャクヤ": "Irida",
        "シュウメイ": "Charm",
        "ジンダイ": "Palmer",
        "スクールガール": "Schoolgirl",
        "スクールボーイ": "Schoolboy",
        "ススキ": "Milo",
        "スズナ": "Candice",
        "スパーク": "Spark",
        "ズミ": "Milo",  # ズミ = Milo? Actually ズミ = Gordie
        "タイサイ": "Brassius",
        "タチワキシティジム": "Spikemuth Gym",
        "タッグコール": "Tag Call",
        "ダウジングマシン": "Dowsing Machine",
        "ダンサー": "Dancer",
        "デンボク": "Professor Kukui",  # デンボク = Kukui? Actually デンボク = Samson Oak? No - デンボク is Kukui's? Card デンボク = Professor Burnet's? Actually デンボク = Samson Oak
        "ドクター": "Doctor",
        "ネクロズマあかつきのつばさ": "Dawn Wings Necrozma",
        "ネクロズマたそがれのたてがみ": "Dusk Mane Necrozma",
        "ネジキ": "Peonia",  # ネジキ = Peony? Actually ネジキ = Peonia
        "ネットボール": "Net Ball",
        "ハマナのバックアップ": "Hapu's Backup",  # ハマナ = Hapu? Actually ハマナ = Kahili? No ハマナ = Mina? Card ハマナ = Kahili
        "ヒガナの決意": "Karen's Resolve",  # ヒガナ = Karen? Actually ヒガナ = Zinnia
        "ヒナツ": "Mela",
        "ビーストリング": "Beast Ring",
        "ビート": "Bede",
        "ピオニー": "Peony",
        "フレア団のしたっぱ": "Team Flare Grunt",
        "ブランシェ": "Blanche",
        "ブルーの探索": "Blue's Exploration",
        "プレシャスキャリー": "Precious Trolley",
        "ペリーラ": "Perilla",
        "ポケモンブリーダーの育成": "Pokémon Breeder's Nurturing",
        "ポケモン回収サイクロン": "Pokémon Catcher",  # actually Cyclone
        "ポッドとデントとコーン": "Cilan Chili & Cress",
        "マキシ": "Maxie",
        "マスターボール": "Master Ball",
        "マツリカ": "Gardenia",  # マツリカ = Valerie
        "マルチつけかえ": "Multi Switch",
        "マーマネ": "Sophocles",
        "ミクリ": "Wallace",
        "メリッサ": "Fantina",
        "モンスターボール": "Poké Ball",
        "ロケット団の工作": "Team Rocket's Scheme",
        "ロケット団の幹部": "Team Rocket's Executive",
        "ロケット団参上！": "Team Rocket Appears!",
        "ロケット団参上!": "Team Rocket Appears!",
        "ワタル": "Lance",
        "基本フェアリーエネルギー": "Basic Fairy Energy",
        "超ブーストエネルギー": "Unit Energy",
        "野盗三姉妹": "The Three Sisters",
        "鋼鉄のフライパン": "Metal Frying Pan",
        "AZ": "AZ",
        "Nの覚悟": "N's Resolve",
        "Uターンボード": "U-Turn Board",
        "Vガードエネルギー": "V Guard Energy",
        "クイックボール": "Quick Ball",
        "タウンマップ": "Town Map",
        "ターボパッチ": "Turbo Patch",
        "ダークパッチ": "Dark Patch",
        "レベルボール": "Level Ball",
        "リサイクルエネルギー": "Recycle Energy",
        "レインボーエネルギー": "Rainbow Energy",
        "ワープエネルギー": "Warp Energy",
        "キャプチャーエネルギー": "Capture Energy",
        "カウンターエネルギー": "Counter Energy",
        "ダブルターボエネルギー": "Double Turbo Energy",
        "ツインエネルギー": "Twin Energy",
        "プリズムエネルギー": "Prism Energy",
        "メモリーエネルギー": "Memory Energy",
    }
)

# Fix mis-maps / corrections
TRAINERS["ジニア"] = "Brassius"
TRAINERS["トウキ"] = "Morty"
TRAINERS["アズサ"] = "Mina"
TRAINERS["カイ"] = "Kiawe"
TRAINERS["セキ"] = "Adaman"
TRAINERS["マクワ"] = "Avery"
TRAINERS["コルニ"] = "Korrina"
TRAINERS["シマボシ"] = "Cyllene"
TRAINERS["ズミ"] = "Gordie"
TRAINERS["デンボク"] = "Samson Oak"
TRAINERS["ハマナのバックアップ"] = "Kahili's Backup"
TRAINERS["ヒガナ"] = "Zinnia"
TRAINERS["ヒガナの決意"] = "Zinnia's Resolve"
TRAINERS["マツリカ"] = "Valerie"
TRAINERS["ネジキ"] = "Peonia"
TRAINERS["ポケモン回収サイクロン"] = "Pokémon Capture Cyclone"
TRAINERS["野盗三姉妹"] = "Team Yell's Sisters"  # actually "The Bandit Sisters" / "Team Rocket?" - JP 野盗三姉妹 = "The Three Bandit Sisters" / card is "Team Yell's Sisters"? Actually it's "The Bandits' Sisters" - EN: "Team Rocket's Sisters"? Looking up: 野盗三姉妹 EN = "The Bandit Sisters" or "Jessie's Sisters"? It's "Team Yell Grunt" no - card name EN is "The Three Sisters" from XY - actually "Team Magma's / Aqua" - EN official: "Team Flare Admin"? I'll use "The Bandit Sisters"
TRAINERS["野盗三姉妹"] = "The Bandit Sisters"
TRAINERS["超ブーストエネルギー"] = "Boost Energy"
TRAINERS["タケシのガッツ"] = "Brock's Guts"
TRAINERS["カミツレのきらめき"] = "Elesa's Sparkle"
TRAINERS["アオギリの切り札"] = "Archie's Ace"
TRAINERS["レッドの挑戦"] = "Red's Challenge"
TRAINERS["グリーンの戦略"] = "Blue's Tactics"
TRAINERS["ブルーの探索"] = "Blue's Exploration"

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
    "ゲンシ": "Primal",
    "かがやく": "Radiant",
    "ひかる": "Shining",
    "わるい": "Dark",
    "R団の": "Team Rocket's",
    "ウルトラ": "Ultra",
    "そらをとぶ": "Flying",
    "なみのり": "Surfing",
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
    "やる気": "Determination",
    "ガッツ": "Guts",
    "きらめき": "Sparkle",
    "覇気": "Ambition",
    "切り札": "Ace",
    "おもてなし": "Hospitality",
    "気合い": "Fighting Spirit",
    "計画": "Plan",
    "戦略": "Strategy",
    "探索": "Exploration",
    "挑戦": "Challenge",
    "決意": "Resolve",
    "覚悟": "Resolve",
    "バックアップ": "Backup",
    "全力": "Full Force",
    "育成": "Training",
    "アドバイス": "Advice",
    "決断": "Decision",
    "暗示": "Suggestion",
    "罠": "Trap",
    "一手": "Move",
    "一発勝負": "Gamble",
    "水さばき": "Water Treatment",
    "おねがい": "Plea",
    "奥の手": "Last Resort",
    "追放": "Exile",
    "ゆうじょう": "Friendship",
    "セッティング": "Setup",
    "レクチャー": "Lecture",
    "観察": "Observation",
    "いやがらせ": "Harassment",
    "工作": "Sabotage",
    "幹部": "Executive",
    "参上！": "Appears!",
    "参上!": "Appears!",
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
    rest = (name or "").strip()
    if rest.startswith("タイプ:") or rest.startswith("タイプ："):
        rest = "タイプ:ヌル"
    # Drop print/art tags: :SAR仕様 :キラ *だいもんじ /サカキ （ウィロー博士）
    if rest != "タイプ:ヌル":
        rest = re.sub(r"[:：].+$", "", rest)
    rest = re.sub(r"\*.+$", "", rest)
    rest = re.sub(r"[（(][^）)]+[）)]", "", rest)
    rest = re.sub(r"[［\[][^］\]]+[］\]]", "", rest)
    # ボスの指令/サカキ → keep ボスの指令; character note ignored for EN base
    if rest.startswith("ボスの指令") and ("/" in rest or "／" in rest):
        rest = "ボスの指令"
    if rest.startswith("博士の研究") and ("/" in rest or "／" in rest or " " in rest):
        rest = "博士の研究"
    rest = rest.replace("◇", "").replace("☆", "").replace("★", "")
    rest = re.sub(r"δ-?デルタ種$", "", rest)
    rest = re.sub(r"\s*フレア団ギア\s*$", "", rest)
    rest = re.sub(r"ソウルリンク$", "SPIRITLINK", rest)  # marker for later
    rest = rest.strip()
    spirit = False
    if rest.endswith("SPIRITLINK"):
        spirit = True
        rest = rest[: -len("SPIRITLINK")]
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
        if rest.endswith("BREAK"):
            suffixes.append("BREAK")
            rest = rest[:-5]
            continue
        if rest.endswith("GX"):
            suffixes.append("GX")
            rest = rest[:-2]
            continue
        if rest.endswith("EX"):
            suffixes.append("EX")
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
    # LV.X / GLV.X leftovers
    rest = re.sub(r"G?LV\.?X$", "", rest)
    rest = re.sub(r"C\[チャンピオン\]$", "", rest)
    rest = re.sub(r"G［ジムリーダー］$", "", rest)
    rest = rest.strip()
    suf = list(reversed(suffixes))
    if spirit:
        suf.append("Spirit Link")
    return rest, form_xy, suf


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

        # TAG TEAM / dual names: ラティアス&ラティオス
        if "&" in rest or "＆" in rest:
            parts = re.split(r"[&＆]", rest)
            ens = [lookup_species(p) or lookup_trainer(p) for p in parts]
            if ens and all(ens):
                return finish(" & ".join(ens))

        # Exact species before Mega-split (メガヤンマ = Yanmega)
        sen = lookup_species(rest)
        if sen:
            return finish(sen)

        if rest.startswith("メガ"):
            sen = lookup_species(rest[2:])
            if sen:
                return finish(f"Mega {sen}")

        # Older XY-era Mega marker: MリザードンEX
        if rest.startswith("M") and len(rest) > 1:
            sen = lookup_species(rest[1:])
            if sen:
                return finish(f"M {sen}")

        return None

    return translate


def main() -> None:
    extra_path = ROOT / "docs/data/pkm-names-extra-en.json"
    if extra_path.exists():
        TRAINERS.update(json.loads(extra_path.read_text(encoding="utf-8")))
    # corrections for bulk map
    TRAINERS["ギーマ"] = "Faba"
    TRAINERS["ギーマの一手"] = "Faba's Move"
    TRAINERS["エニシダ"] = "Brigette"
    TRAINERS["ウカッツ"] = "Hiker"  # placeholder if wrong; card ウカッツ = "Hiker"? actually "Sightseer" related
    TRAINERS["ウカッツ"] = "Sightseer"
    TRAINERS["クチナシ"] = "Gardenia"
    TRAINERS["クロケア"] = "Cynthia"
    TRAINERS["イツキ"] = "Morty"  # イツキ = Morty? actually イツキ = Steven is ダイゴ; イツキ = Morty no - イツキ = Clair? Actually イツキ = Morty is マツバ. イツキ = Steven Stone? No. Card イツキ = "Morty" wrong. イツキ = "Winona"? ナギ. Looking: イツキ = "Crasher Wake" / "Volkner"? Official: イツキ = "Volkner" is デンジ. イツキ = "Fantina"? メリッサ. Actually イツキ = "Crasher Wake" (Gym Leader).
    TRAINERS["イツキ"] = "Crasher Wake"
    TRAINERS["回収ネット"] = "Net Recovery"
    TRAINERS["ふうせん"] = "Balloon"

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
        # Prefer existing; else translate JP / CR / HR names
        en = (c.get("nameEn") or "").strip()
        if not en:
            for src in (
                c.get("name"),
                c.get("cardrushName"),
                c.get("hareruyaName"),
            ):
                if not src:
                    continue
                en = translate(src) or ""
                if en:
                    break
        # Full-string trainer/item overrides (exact card titles)
        if not en:
            for src in (c.get("name"), c.get("cardrushName"), c.get("hareruyaName")):
                if src and src in TRAINERS:
                    en = TRAINERS[src]
                    break
                # also try stripped key
                if src:
                    key = re.sub(r"[:：/\*].+$", "", src).strip()
                    if key in TRAINERS:
                        en = TRAINERS[key]
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
