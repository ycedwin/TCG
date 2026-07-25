import { defineConfig } from "vite";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  base: "./",
  publicDir: "public",
  build: {
    outDir: "docs",
    emptyOutDir: true,
  },
  plugins: [
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["favicon.svg"],
      manifest: {
        name: "海賊王卡價查詢",
        short_name: "OP卡價",
        description: "One Piece 卡牌價格查詢（Beehive）",
        theme_color: "#0b1e33",
        background_color: "#071525",
        display: "standalone",
        lang: "zh-Hant",
        start_url: "./",
        icons: [
          {
            src: "favicon.svg",
            sizes: "any",
            type: "image/svg+xml",
            purpose: "any maskable",
          },
        ],
      },
      workbox: {
        globPatterns: ["**/*.{js,css,html,svg,ico,json}"],
        runtimeCaching: [
          {
            urlPattern: /\/data\/catalog\.json$/,
            handler: "NetworkFirst",
            options: {
              cacheName: "catalog-json",
              networkTimeoutSeconds: 8,
              expiration: { maxEntries: 2, maxAgeSeconds: 60 * 60 * 24 * 30 },
            },
          },
          {
            urlPattern: /^https:\/\/cdn\.shopify\.com\/.*/i,
            handler: "CacheFirst",
            options: {
              cacheName: "card-images",
              expiration: {
                maxEntries: 2000,
                maxAgeSeconds: 60 * 60 * 24 * 30,
              },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
        ],
      },
    }),
  ],
});
