-- =====================================================================
-- 003：隊員身分證字號（綁定 LINE 時與生日一起核對本人）
-- 使用方式：Supabase → SQL Editor → 貼上 → Run（只要執行一次）
--
-- 保護方式：
--   * 前端「讀不到」這個欄位（跟生日一樣，沒有開放 select 權限）
--   * 只有分隊幹部能寫入（members_update / members_insert 原本就只允許幹部）
--   * 幹部要看某位隊員的生日、身分證，走 member_secret() 函式，函式裡再檢查一次是不是該分隊幹部
-- =====================================================================
alter table members add column if not exists id_number text;

grant update (id_number) on members to authenticated;   -- 寫入：還是受 members_update 政策限制（只有幹部）

-- 幹部讀取某位隊員的生日、身分證字號（隊員本人與其他人都讀不到）
create or replace function public.member_secret(p_member_id uuid) returns jsonb
language plpgsql stable security definer set search_path = public as $$
declare v members;
begin
  select * into v from members where id = p_member_id;
  if v.id is null or not can_admin_squad(v.squad_id) then
    return jsonb_build_object('ok', false, 'message', '沒有權限');
  end if;
  return jsonb_build_object('ok', true, 'birthday', v.birthday, 'id_number', v.id_number);
end $$;
revoke all on function public.member_secret(uuid) from public, anon;
grant execute on function public.member_secret(uuid) to authenticated;

-- 綁定：有登錄身分證字號的隊員，要生日＋身分證字號都對；還沒登錄身分證的，照舊只核對生日
drop function if exists public.bind_member(uuid, date, text, text);
create or replace function public.bind_member(p_member_id uuid, p_birthday date,
                                              p_display_name text default null, p_picture_url text default null,
                                              p_id_number text default null)
returns jsonb
language plpgsql security definer set search_path = public as $$
declare
  v_line text := jwt_line_user_id();
  v_fails int;
  v_member members;
  v_need_id boolean;
  v_ok boolean;
begin
  if v_line is null then
    return jsonb_build_object('ok', false, 'message', '請先用 LINE 登入');
  end if;
  if exists (select 1 from members where line_user_id = v_line) then
    return jsonb_build_object('ok', false, 'message', '這個 LINE 帳號已經綁定過了');
  end if;

  select count(*) into v_fails from bind_attempts
  where line_user_id = v_line and not success and created_at > now() - interval '24 hours';
  if v_fails >= 5 then
    return jsonb_build_object('ok', false, 'message', '驗證失敗次數過多，請 24 小時後再試，或請分隊幹部協助');
  end if;

  select * into v_member from members where id = p_member_id for update;
  if v_member.id is null or v_member.is_suspended or v_member.line_user_id is not null then
    return jsonb_build_object('ok', false, 'message', '這位隊員無法綁定，請聯絡分隊幹部');
  end if;
  if v_member.birthday is null then
    return jsonb_build_object('ok', false, 'message', '這位隊員尚未登錄生日，請聯絡分隊幹部');
  end if;

  v_need_id := coalesce(nullif(trim(v_member.id_number), ''), '') <> '';
  if v_need_id and coalesce(trim(p_id_number), '') = '' then
    return jsonb_build_object('ok', false, 'message', '請輸入身分證字號', 'need_id', true);
  end if;
  v_ok := v_member.birthday = p_birthday
          and (not v_need_id or upper(trim(v_member.id_number)) = upper(trim(p_id_number)));
  if not v_ok then
    insert into bind_attempts (line_user_id, member_id, success) values (v_line, p_member_id, false);
    return jsonb_build_object('ok', false, 'need_id', v_need_id, 'message',
      case when v_fails >= 4 then (case when v_need_id then '生日或身分證字號' else '生日' end) || '不正確，已達 5 次上限，請 24 小時後再試，或請分隊幹部協助'
           else format('%s不正確（還可以再試 %s 次）', case when v_need_id then '生日或身分證字號' else '生日' end, 4 - v_fails) end);
  end if;

  update members set line_user_id = v_line,
                     line_display_name = left(p_display_name, 100),
                     line_picture_url = left(p_picture_url, 500),
                     bound_at = now()
  where id = p_member_id;
  insert into bind_attempts (line_user_id, member_id, success) values (v_line, p_member_id, true);
  return jsonb_build_object('ok', true, 'member_id', p_member_id, 'name', v_member.name);
end $$;
revoke all on function public.bind_member(uuid, date, text, text, text) from public, anon;
grant execute on function public.bind_member(uuid, date, text, text, text) to authenticated;
