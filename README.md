# One Piece / Pokémon JP Price Checker

Static site in `docs/` — GitHub Pages.

Site: https://ycedwin.github.io/TCG/

## Enable GitHub Pages

1. **Settings → Pages**
2. Source: **Deploy from a branch**
3. Branch: `main` · Folder: `/docs` → **Save**

## Edit the site

Change files under `docs/` and push. No Node / build step.

- `docs/index.html` — One Piece
- `docs/pokemon.html` — Pokémon JP
- `docs/styles.css` — styles
- `docs/main.js` / `docs/beehive.js` / `docs/pokemon.js` — logic
- `docs/data/` — catalogs / buylists

## Refresh prices (option 1 — buy side, skip slow CR sell)

Run from the repo root. Then commit + push `docs/data/` to deploy.

Script names encode **game + source + buy/sell**.

### One Piece

```bash
cd /Users/edwinyim/Documents/one_piece
python3 scripts/sync_op_beehive_buy.py      # Beehive buy (HKD)
python3 scripts/sync_op_cardrush_buy.py     # Card Rush buy (JPY)
```

Beehive **sell** (shop) → browser **Refresh prices** on the OP page.

Optional Card Rush sell (slow):

```bash
/Library/Frameworks/Python.framework/Versions/3.14/bin/python3 scripts/sync_op_cardrush_sell.py
```

### Pokémon JP

```bash
cd /Users/edwinyim/Documents/one_piece
python3 scripts/sync_pkm_buy.py --skip-sell
# runs: Beehive buy + names + Hareruya buy + Card Rush buy
# keeps existing Card Rush sell + tier fields (matched by printId)
```

Individual PKM scripts (if you only need one source):

| Script | Refreshes |
|--------|-----------|
| `sync_pkm_buy.py` | Orchestrates all PKM **buy** sources (+ names); `--skip-sell` skips CR sell |
| `sync_pkm_names.py` | English names only |
| `sync_pkm_hareruya_buy.py` | Hareruya buy (JPY) |
| `sync_pkm_cardrush_buy.py` | Card Rush buy (JPY) |
| `sync_pkm_cardrush_sell.py` | Card Rush sell (JPY, slow) |

Optional Card Rush sell (slow; needs `curl_cffi`):

```bash
/Library/Frameworks/Python.framework/Versions/3.14/bin/python3 scripts/sync_pkm_cardrush_sell.py --missing-only --bust-cache
```

### Deploy after sync

```bash
git add docs/data
git status
git commit -m "Refresh buy prices"
git push origin main
```
