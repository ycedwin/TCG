import { parseTitle } from "../src/beehive.js";
import assert from "node:assert/strict";

const cases = [
  ["OP16-065 サカズキ P-SRP", { fullNumber: "OP16-065", name: "サカズキ", rarity: "P-SRP" }],
  ["【OP16】EB04-054 バーソロミュー・くま SP", { fullNumber: "EB04-054", name: "バーソロミュー・くま", rarity: "SP" }],
  ["【PRB01】OP01-016 ナミ P-RP", { fullNumber: "OP01-016", name: "ナミ", rarity: "P-RP" }],
  ["【PROMO】OP01-013 サンジ R", { fullNumber: "OP01-013", name: "サンジ", rarity: "R" }],
  ["EB01-061 Mr.2・ボン・クレー（ベンサム） P-SEC", { fullNumber: "EB01-061", name: "Mr.2・ボン・クレー（ベンサム）", rarity: "P-SEC" }],
  ["OP05-119 モンキー・D・ルフィ P-SECP", { fullNumber: "OP05-119", name: "モンキー・D・ルフィ", rarity: "P-SECP" }],
  ["【OP16】ドン!!カード(インペルダウン) - 金邊", { fullNumber: "", name: "ドン!!カード(インペルダウン)", rarity: "DON-金邊" }],
  ["【OP16】ドン!!カード(インペルダウン) -", { fullNumber: "", name: "ドン!!カード(インペルダウン)", rarity: "DON" }],
  ["【PRB01】【PRB01】OP03-055 ゴムゴムの大槌 C - 特殊閃版", { fullNumber: "OP03-055", name: "ゴムゴムの大槌", rarity: "C-特殊閃版" }],
  ["【OP11】OP05-119 モンキー・D・ルフィ SP - 金", { fullNumber: "OP05-119", name: "モンキー・D・ルフィ", rarity: "SP-金" }],
  ["[OP02]ドン!!カード(この戦争を終わらせに来た!!!) -", { fullNumber: "", name: "ドン!!カード(この戦争を終わらせに来た!!!)", rarity: "DON" }],
  ["One Piece Card Game EB02-006 Promo", { fullNumber: "EB02-006", name: "EB02-006", rarity: "Promo" }],
  ["【PRB01】P-014 コビー P", { fullNumber: "P-014", name: "コビー", rarity: "P" }],
];

for (const [title, expect] of cases) {
  const got = parseTitle(title);
  assert.equal(got.fullNumber, expect.fullNumber, `${title} fullNumber`);
  assert.equal(got.name, expect.name, `${title} name`);
  assert.equal(got.rarity, expect.rarity, `${title} rarity`);
}

console.log(`parse-selfcheck: ${cases.length} cases ok`);
