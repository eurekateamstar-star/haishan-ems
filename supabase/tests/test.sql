\set ON_ERROR_STOP 0
\pset pager off
-- 測試資料（以 postgres 身分）
insert into squads (name, sort_order) values ('海山', 1), ('板橋', 2);
insert into members (id, squad_id, name, birthday, duty_title, role, line_user_id) values
  ('00000000-0000-0000-0000-00000000000a', 1, '劉奕昕', '1990-01-02', '幹事', 'squad_admin', 'U_admin_haishan'),
  ('00000000-0000-0000-0000-00000000000b', 1, '王佩瑾', '1995-05-05', '隊員', 'member', 'U_member_haishan'),
  ('00000000-0000-0000-0000-00000000000c', 1, '郭允昊', '1998-08-08', '隊員', 'member', null),
  ('00000000-0000-0000-0000-00000000000d', 2, '板橋甲', '1980-03-03', '分隊長', 'squad_admin', 'U_admin_banqiao');

create or replace function as_user(line text) returns void language plpgsql as $$
begin
  perform set_config('request.jwt.claims', json_build_object('sub', line, 'role', 'authenticated')::text, false);
end $$;
grant execute on function as_user(text) to authenticated;

\echo '===== 1. 未綁定的 LINE 帳號 ====='
select as_user('U_new_person');
set role authenticated;
select my_binding() as "狀態(應 unbound)";
select name from list_bindable_members(1::smallint);   -- 應只有 郭允昊
select bind_member('00000000-0000-0000-0000-00000000000c', '1998-01-01') as "錯的生日";
select bind_member('00000000-0000-0000-0000-00000000000c', '1998-08-08', '允昊') as "對的生日";
select my_binding() as "狀態(應 bound)";
select count(*) as "未綁定的人應讀不到別分隊(應0)" from members where squad_id = 2;
reset role;

\echo '===== 2. 一般隊員 王佩瑾（海山） ====='
select as_user('U_member_haishan');
set role authenticated;
select count(*) as "讀海山隊員(應3)" from members where squad_id = 1;
select count(*) as "讀板橋隊員(應0)" from members where squad_id = 2;
\echo '-- 讀生日應被拒絕：'
select birthday from members limit 1;
\echo '-- 自己排班（應成功）：'
insert into shifts (squad_id, member_id, date, start_hour, end_hour) values (1, '00000000-0000-0000-0000-00000000000b', '2026-11-25', '17', '21');
\echo '-- 幫別人排班（應被拒）：'
insert into shifts (squad_id, member_id, date, start_hour, end_hour) values (1, '00000000-0000-0000-0000-00000000000c', '2026-11-25', '17', '21');
\echo '-- 排到別的分隊（應被拒）：'
insert into shifts (squad_id, member_id, date, start_hour, end_hour) values (2, '00000000-0000-0000-0000-00000000000b', '2026-11-25', '17', '21');
\echo '-- 發布公差（應被拒）：'
insert into tasks (squad_id, kind, title, date) values (1, 'duty', '測試', '2026-12-01');
\echo '-- 改自己的職稱（應更新 0 筆）：'
update members set role = 'super_admin' where id = '00000000-0000-0000-0000-00000000000b';
\echo '-- 寫協勤紀錄 + 跨午夜案件：'
select save_assistance('{"date":"2026-10-30","shift_start":"13:00","shift_end":"18:00"}',
  '[{"case_start":"15:27","case_end":"16:27","case_type":"急病","rescued_count":1},
    {"case_start":"23:40","case_end":"00:30","case_type":"OHCA"},
    {"case_start":"16:58","case_end":"17:59","case_type":"PUA:OHCA"}]') is not null as "存檔成功";
select save_assistance('{"date":"2026-10-31","shift_start":"08:00","shift_end":"12:00"}') is not null as "待命協勤存檔";
\echo '-- 幫別分隊的人寫紀錄（應被拒）：'
select save_assistance('{"member_id":"00000000-0000-0000-0000-00000000000d","date":"2026-10-30","shift_start":"13:00","shift_end":"18:00"}');
select name, hours, case_hours, case_count, rescued_count, case_type_counts from squad_ranking(1::smallint) where case_count > 0;
select my_year_stats(2026) as "首頁統計";
select count(*) as "讀板橋排名(應0人)" from squad_ranking(2::smallint);
reset role;

\echo '===== 3. 海山幹部 劉奕昕 ====='
select as_user('U_admin_haishan');
set role authenticated;
insert into tasks (squad_id, kind, title, date, quota) values (1, 'duty', '耶誕城開城', '2026-12-13', 1);
select count(*) as "海山公差(應1)" from tasks;
\echo '-- 發布到板橋（應被拒）：'
insert into tasks (squad_id, kind, title, date) values (2, 'duty', '越權', '2026-12-01');
\echo '-- 把隊員升系統管理員（應被拒）：'
update members set role = 'super_admin' where id = '00000000-0000-0000-0000-00000000000b';
\echo '-- 把隊員調到板橋（應被拒）：'
update members set squad_id = 2 where id = '00000000-0000-0000-0000-00000000000b';
\echo '-- 停權自己（應被拒）：'
update members set is_suspended = true where id = '00000000-0000-0000-0000-00000000000a';
\echo '-- 正常改職稱（應成功）：'
update members set duty_title = '小隊長' where id = '00000000-0000-0000-0000-00000000000b';
select name, duty_title from members where id = '00000000-0000-0000-0000-00000000000b';
\echo '-- 新增隊員時偷塞 LINE id（應被清空）：'
insert into members (squad_id, name, birthday, line_user_id) values (1, '新人', '2000-01-01', 'U_hijack');
reset role;
select name, line_user_id is null as "新人 line 已清空" from members where name = '新人';

\echo '===== 4. 板橋幹部改海山資料（應更新 0 筆） ====='
select as_user('U_admin_banqiao');
set role authenticated;
update members set duty_title = '被改了' where squad_id = 1;
delete from shifts where squad_id = 1;
reset role;
select count(*) as "海山排班仍在(應1)" from shifts;
select count(*) as "沒人被改(應0)" from members where duty_title = '被改了';

\echo '===== 5. 猜生日上限 ====='
select as_user('U_guesser');
set role authenticated;
select bind_member('00000000-0000-0000-0000-00000000000c', '2000-01-01');
reset role;
update members set line_user_id = null where name = '郭允昊';   -- 讓郭允昊可再被綁，用來測猜測次數
set role authenticated;
select bind_member('00000000-0000-0000-0000-00000000000c', ('2000-01-0'||g)::date)::text from generate_series(1,6) g;
reset role;
