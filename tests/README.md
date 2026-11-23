# 測試

1. `supabase/tests/`：只用 PostgreSQL 檢查權限與統計（psql 執行）。
2. `store.e2e.mjs`：本機 PostgreSQL + PostgREST（Supabase 的 API 引擎）+ ES256 金鑰，
   用官方 supabase-js 以不同隊員身分實際讀寫，檢查資料層 `js/store.js`。
   設定見 `postgrest.conf.example`（jwt-secret 指向測試用的公鑰 JWKS）。
3. `browser.e2e.cjs`：用 Playwright 開真的瀏覽器跑新網站（LIFF 與 Worker 以模擬取代），
   檢查綁定流程、三個分頁、幹部權限、分隊之間互相看不到。
