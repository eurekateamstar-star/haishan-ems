-- =====================================================================
-- 002：各資料表加上 extra 欄位，存放舊平台有、但沒有獨立欄位的資料
--      （例如請假月份、報名時的其他選項）
-- 使用方式：Supabase → SQL Editor → 貼上 → Run（只要執行一次）
-- =====================================================================
alter table members            add column if not exists extra jsonb not null default '{}';
alter table tasks              add column if not exists extra jsonb not null default '{}';
alter table registrations      add column if not exists extra jsonb not null default '{}';
alter table shifts             add column if not exists extra jsonb not null default '{}';
alter table assistance_records add column if not exists extra jsonb not null default '{}';

grant select (extra), update (extra) on members to authenticated;
