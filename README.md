# 海賊王卡價查詢（One Piece Card Price Checker）

靜態網站：從 [Beehive 皇巢](https://beehivetcg.com) 查 One Piece 單卡港幣價格，可離線使用。

## 功能

- 依系列瀏覽（OP / EB / PRB / Promo）
- 以**珍貴度（rarity）**分組顯示
- 搜尋卡號（如 `OP16-065`、`065`）或角色名（日文，如 `ルフィ`）
- **更新價格**按鈕：連線時直接向 Beehive 抓最新價，存進瀏覽器本機快取
- 離線時使用本機快取／內建資料
- 價格單位：HKD

## 本機開發

需要 Node.js 18+。

```bash
npm install
npm run test:parse
npm run dev           # http://localhost:5173
npm run build         # 產出 dist/
```

可選：預先產生內建 `catalog.json`（網站首次部署用；日常更新用網頁按鈕即可）：

```bash
npm run sync
```

## GitHub Pages

1. 推送到 GitHub
2. **Settings → Pages → Source → GitHub Actions**
3. 部署 workflow：[`.github/workflows/pages.yml`](.github/workflows/pages.yml)（只負責建置／上架，**不會**自動同步價格）

站台：`https://<user>.github.io/<repo>/`

## 注意

- 角色名依 Beehive 標題為**日文**
- 不含庫存狀態
- 「更新價格」約需數十秒（全部系列）；請保持連線
- 圖片使用 Shopify CDN 縮圖，不提交進 git

## 授權

個人／非商業查詢用途。卡圖與價格資料屬原站／版權方所有。
