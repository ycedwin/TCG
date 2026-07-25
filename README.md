# One Piece Price Checker

Static site in `docs/` — check One Piece singles prices from [Beehive TCG](https://beehivetcg.com) (HKD).

## Enable GitHub Pages

1. **Settings → Pages**
2. Source: **Deploy from a branch**
3. Branch: `main` · Folder: `/docs` → **Save**

Site: https://ycedwin.github.io/TCG/

## Edit the site

Change files under `docs/` and push. No Node / build step.

- `docs/index.html` — page
- `docs/styles.css` — styles
- `docs/main.js` / `docs/beehive.js` — logic
- `docs/data/catalog.json` — bundled prices (or use **Refresh prices** in the app)
