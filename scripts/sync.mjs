#!/usr/bin/env node
/**
 * Optional: seed public/data/catalog.json from Beehive (for first deploy / offline bundle).
 * Day-to-day updates use the site「更新價格」button.
 */
import { readFileSync, writeFileSync, mkdirSync, copyFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { buildCatalog } from "../src/beehive.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");
const SETS_SRC = join(__dirname, "sets.json");
const SETS_PUBLIC = join(ROOT, "public", "data", "sets.json");
const OUT_PATH = join(ROOT, "public", "data", "catalog.json");

async function main() {
  mkdirSync(dirname(OUT_PATH), { recursive: true });
  copyFileSync(SETS_SRC, SETS_PUBLIC);
  const sets = JSON.parse(readFileSync(SETS_SRC, "utf8"));
  const catalog = await buildCatalog(sets, {
    onProgress: ({ index, total, code }) => {
      process.stdout.write(`\rSync ${code} (${index}/${total})…   `);
    },
  });
  writeFileSync(OUT_PATH, JSON.stringify(catalog), "utf8");
  console.log(
    `\nWrote ${catalog.cards.length} cards → ${OUT_PATH} (${catalog.sets.length} sets)`,
  );
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
