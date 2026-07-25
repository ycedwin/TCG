# 海賊王卡價查詢

純靜態網站（`docs/`），查 [Beehive](https://beehivetcg.com) One Piece 單卡港幣價格。

## 啟用 GitHub Pages

1. **Settings → Pages**
2. Source：**Deploy from a branch**
3. Branch：`main` · Folder：`/docs` → **Save**

站台：https://ycedwin.github.io/TCG/

## 改網站

直接改 `docs/` 裡的檔案，push 即可。無需 Node / build。

- `docs/index.html` — 頁面
- `docs/styles.css` — 樣式
- `docs/main.js` / `docs/beehive.js` — 邏輯
- `docs/data/catalog.json` — 內建價格（也可在網頁按「更新價格」）
