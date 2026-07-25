# 海賊王卡價查詢（One Piece Card Price Checker）

靜態網站：從 [Beehive 皇巢](https://beehivetcg.com) 查 One Piece 單卡港幣價格，可離線使用。

## 功能

- 依系列瀏覽（OP / EB / PRB / Promo）
- 以**珍貴度（rarity）**分組顯示
- 搜尋卡號（如 `OP16-065`、`065`）
- **更新價格**按鈕：連線時向 Beehive 抓最新價，存進瀏覽器本機快取
- 離線時使用本機快取／內建資料
- 價格單位：HKD

## 本機開發

```bash
npm install
npm run dev
npm run build   # 產出 docs/（GitHub Pages 用）
```

## 啟用 GitHub Pages（無 Actions）

建置結果放在 `docs/`，用 branch 直接託管：

1. 打開 repo：**Settings → Pages**
2. **Source** 選 **Deploy from a branch**
3. Branch：`main`，Folder：`/docs`
4. 按 **Save**

約 1 分鐘後開啟：`https://ycedwin.github.io/TCG/`

之後改程式時在本機跑 `npm run build`，再 commit / push `docs/` 即可更新網站。

## 注意

- 不含庫存狀態
- 「更新價格」約需數十秒（全部系列）
- 圖片使用 Shopify CDN 縮圖

## 授權

個人／非商業查詢用途。卡圖與價格資料屬原站／版權方所有。
