# 海山救護義消平台（多分隊版）

從 eurekateamstar-star.github.io 拆出「首頁、排班、協勤」三個功能，改成 29 個分隊共用的系統。

## 架構

| 部分 | 使用 | 說明 |
| --- | --- | --- |
| 網頁 | GitHub Pages | 單一 `index.html`（Vue 3），LINE 內透過 LIFF 開啟 |
| 登入 | LINE LIFF | 首次登入：選分隊＋姓名，輸入生日驗證後綁定 |
| 驗證中繼 | Cloudflare Worker | 驗證 LIFF 憑證，簽發 Supabase 可接受的 JWT |
| 資料庫 | Supabase（PostgreSQL） | 依分隊隔離資料（RLS），統計與排名在資料庫計算 |

## 權限

- **隊員**：讀自己分隊的資料；寫自己的排班、協勤紀錄、報名。
- **分隊幹部（squad_admin）**：管理自己分隊的隊員、公差會議、零用金，可修改分隊內所有紀錄。
- **系統管理員（super_admin）**：所有分隊；只有系統管理員能指派系統管理員或調動分隊。
- 生日與 LINE userId 前端讀不到；綁定只能透過 `bind_member()`，24 小時內猜錯 5 次就鎖住。

## 資料庫

- 結構：`supabase/schema.sql`（Supabase SQL Editor 貼上執行）
- 測試：`supabase/tests/`（本機 PostgreSQL 模擬不同身分，檢查權限與統計）

```bash
psql -d 測試資料庫 -f supabase/tests/supabase_stub.sql
psql -d 測試資料庫 -f supabase/schema.sql
psql -d 測試資料庫 -f supabase/tests/test.sql
```
