# 海賊王卡價查詢（One Piece Card Price Checker）

靜態網站：從 [Beehive 皇巢](https://beehivetcg.com) 同步 One Piece 單卡港幣價格，可離線使用。

## 功能

- 依系列瀏覽（OP / EB / PRB / Promo）
- 以**珍貴度（rarity）**分組顯示
- 搜尋卡號（如 `OP16-065`、`065`）或角色名（日文，如 `ルフィ`）
- 價格單位：HKD
- PWA：連線時更新 `catalog.json`，離線讀快取；圖片延遲載入並快取縮圖

## 本機開發

需要 Node.js 18+。

```bash
npm install
npm run sync          # 從 Beehive 抓取最新價格
npm run test:parse    # 標題解析自檢
npm run dev           # http://localhost:5173
npm run build         # 產出 dist/
```

## GitHub Pages 部署

1. 推送到 GitHub repository
2. **Settings → Pages → Build and deployment**
   - Source: **GitHub Actions**（建議），或
   - Source: **Deploy from a branch**，選 `gh-pages` / `main` 的 `/dist`（需先 build）
3. 若用 Actions 部署靜態站，可另加 Pages workflow；最簡做法：開啟 Pages 指向 `main` 的 `/docs` 或使用下方建議的 `deploy` workflow（可選）

建議流程：

```bash
npm run sync
npm run build
# 將 dist 內容部署到 Pages
```

或在 repository 啟用本專案的 sync workflow 後，於本機 / CI 再 `npm run build` 部署。

若 repository 名稱不是根網域，Vite 已設 `base: './'`，相對路徑可正常運作。

## 自動同步價格

[`.github/workflows/sync.yml`](.github/workflows/sync.yml) 每天執行一次（亦可在 Actions 手動 **Run workflow**）：

1. 執行 `node scripts/sync.mjs`
2. 若 [`public/data/catalog.json`](public/data/catalog.json) 有變更則 commit + push

部署站台另見 [`.github/workflows/pages.yml`](.github/workflows/pages.yml)（push 到 `main`/`master` 時 build + GitHub Pages）。

資料來源為 Shopify 公開 API：

`https://beehivetcg.com/collections/<slug>/products.json`

系列清單見 [`scripts/sets.json`](scripts/sets.json)。

## 注意

- 角色名依 Beehive 標題為**日文**；繁中介面，搜尋請用日文名或卡號
- 不含庫存狀態
- 價格以 Beehive 網站為準；本站僅供查詢
- 圖片使用 Shopify CDN 縮圖（`width=240`），不會把圖檔提交進 git

## 授權

個人／非商業查詢用途。卡圖與價格資料屬原站／版權方所有。
