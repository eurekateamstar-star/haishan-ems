#!/usr/bin/env python3
"""
把舊平台「?export=1」匯出的 JSON，轉成新系統可以直接執行的 SQL。

  python3 -I tools/import_haishan.py <海山資料匯出.json> <輸出.sql> [分隊名稱=海山]

產生的 SQL 貼到 Supabase SQL Editor 執行即可，整份在同一個交易裡：成功就全部寫入，失敗就全部不寫。
可以重複執行：會先清掉該分隊的排班、公差會議、報名、協勤、零用金，再重新匯入；
隊員用「分隊 + 姓名」比對，已存在就更新資料（不會動 LINE 綁定與系統管理員身分）。
不會匯入：舊密碼、身分證字號、Google 帳號、推播訂閱。
"""
import json, re, sys, uuid, datetime

src, out_path = sys.argv[1], sys.argv[2]
SQUAD = sys.argv[3] if len(sys.argv) > 3 else '海山'
data = json.load(open(src, encoding='utf-8'))

SENSITIVE = {'password', 'id_no', 'email', 'uid', 'pushSubscription', 'id'}
MEMBER_COLS = {'姓名', 'birthday', 'duty_group', 'duty_title', 'join_date', 'emt_level', 'emt_expiry',
               'honor_expiry', 'duty_count', 'is_admin', 'is_suspended'}
stats = {k: 0 for k in ['members', 'shifts', 'tasks', 'registrations', 'records', 'cases', 'fund', 'skipped']}
warnings = []


def q(v):
    """SQL 字串常值（NULL 安全）"""
    if v is None:
        return 'null'
    return "'" + str(v).replace("'", "''") + "'"


def qj(v):
    return q(json.dumps(v, ensure_ascii=False)) + '::jsonb'


def norm_date(v):
    """2026/1/5、2026-01-05、115/01/05、2026-01-05T.. → 2026-01-05；無法辨識回傳 None"""
    if v is None:
        return None
    s = str(v).strip()
    if not s or s in ('無', '----/--/--'):
        return None
    m = re.match(r'^(\d{2,4})[/\-.年](\d{1,2})[/\-.月](\d{1,2})', s)
    if not m:
        return None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if y < 1911:
        y += 1911
    try:
        return datetime.date(y, mo, d).isoformat()
    except ValueError:
        return None


def norm_time(v):
    if v is None:
        return None
    s = str(v).strip()
    m = re.match(r'^(\d{1,2})[:：]?(\d{2})$', s)
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    if h > 24 or mi > 59:
        return None
    return f'{h:02d}:{mi:02d}'


def num(v, default=0):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def medal_key(k):
    """medal_新北市\\n 銅-600H、medal_新北市銅 → 新北市銅；medal_志工菁英 → 志工菁英"""
    k = k[len('medal_'):]
    k = re.sub(r'[\s\-]+', '', k)
    k = re.sub(r'\d+H$', '', k)
    return k


squad_sql = f"(select id from squads where name = {q(SQUAD)})"
member_ref = lambda name: f"(select id from members where squad_id = {squad_sql} and name = {q(name)})"

lines = [
    '-- 由 tools/import_haishan.py 產生：' + SQUAD + '分隊資料匯入',
    'begin;',
    f"insert into squads (name, sort_order) values ({q(SQUAD)}, 1) on conflict (name) do nothing;",
    # 重複執行時先清掉舊的匯入
    f"delete from shifts where squad_id = {squad_sql};",
    f"delete from tasks where squad_id = {squad_sql};",          # 報名會跟著刪除
    f"delete from assistance_records where squad_id = {squad_sql};",  # 案件會跟著刪除
    f"delete from fund_entries where squad_id = {squad_sql};",
]

# ---------------------------------------------------------------------
# 隊員
# ---------------------------------------------------------------------
member_names = set()
for order, m in enumerate(data.get('members', [])):
    name = (m.get('姓名') or '').strip()
    if not name:
        stats['skipped'] += 1
        continue
    member_names.add(name)
    medals, hist, extra = {}, {}, {}
    for k, v in m.items():
        if k.startswith('medal_'):
            key = medal_key(k)
            if v not in (None, '', '無') and not medals.get(key):
                medals[key] = str(v).strip()
        elif re.fullmatch(r'hist_\d+', k):
            if v not in (None, ''):
                try:
                    hist[k[5:]] = float(v)
                except ValueError:
                    pass
        elif k not in SENSITIVE and k not in MEMBER_COLS:
            extra[k] = v
    birthday = norm_date(m.get('birthday'))
    if not birthday:
        warnings.append(f'{name}：沒有生日，暫時無法用 LINE 綁定')
    role = 'squad_admin' if m.get('is_admin') is True else 'member'
    lines.append(
        'insert into members (squad_id, name, birthday, duty_group, duty_title, role, is_suspended, join_date, '
        'emt_level, emt_expiry, honor_expiry, duty_count, medals, historic_hours, sort_order, extra) values ('
        f"{squad_sql}, {q(name)}, {q(birthday)}, {q(m.get('duty_group'))}, {q(m.get('duty_title') or '隊員')}, "
        f"{q(role)}, {'true' if m.get('is_suspended') is True else 'false'}, {q(norm_date(m.get('join_date')))}, "
        f"{q(m.get('emt_level'))}, {q(norm_date(m.get('emt_expiry')))}, {q(norm_date(m.get('honor_expiry')))}, "
        f"{num(m.get('duty_count'))}, {qj(medals)}, {qj(hist)}, {order + 1}, {qj(extra)}) "
        'on conflict (squad_id, name) do update set birthday = excluded.birthday, duty_group = excluded.duty_group, '
        'duty_title = excluded.duty_title, '
        "role = case when members.role = 'super_admin' then members.role else excluded.role end, "
        'is_suspended = excluded.is_suspended, join_date = excluded.join_date, emt_level = excluded.emt_level, '
        'emt_expiry = excluded.emt_expiry, honor_expiry = excluded.honor_expiry, duty_count = excluded.duty_count, '
        'medals = excluded.medals, historic_hours = excluded.historic_hours, sort_order = excluded.sort_order, '
        'extra = excluded.extra;')
    stats['members'] += 1


def known_member(name, what):
    if name in member_names:
        return True
    stats['skipped'] += 1
    warnings.append(f'{what}：找不到隊員「{name}」，略過')
    return False


# ---------------------------------------------------------------------
# 排班
# ---------------------------------------------------------------------
for s in data.get('shifts', []):
    name, d = s.get('name'), norm_date(s.get('date'))
    if not d or not known_member(name, f'排班 {s.get("date")}'):
        continue
    lines.append(f"insert into shifts (squad_id, member_id, date, start_hour, end_hour) values ("
                 f"{squad_sql}, {member_ref(name)}, {q(d)}, {q(str(s.get('start', '')))}, {q(str(s.get('end', '')))});")
    stats['shifts'] += 1

# ---------------------------------------------------------------------
# 公差 / 會議
# ---------------------------------------------------------------------
TASK_KNOWN = {'id', 'title', 'date', 'startTime', 'endTime', 'location', 'note', 'quota', 'category',
              'priceAdult', 'priceChild', 'creator', 'timestamp'}
task_ids = {}  # 舊 id → (新 uuid, kind)
for coll, kind in (('official_tasks', 'duty'), ('meeting_tasks', 'meeting')):
    for t in data.get(coll, []):
        d = norm_date(t.get('date'))
        if not d:
            stats['skipped'] += 1
            warnings.append(f'{coll}「{t.get("title")}」：日期無法辨識，略過')
            continue
        new_id = str(uuid.uuid4())
        task_ids[t['id']] = (new_id, kind)
        extra = {k: v for k, v in t.items() if k not in TASK_KNOWN}
        creator = t.get('creator')
        lines.append(
            'insert into tasks (id, squad_id, kind, category, title, date, start_time, end_time, location, note, '
            'quota, price_adult, price_child, created_by, extra) values ('
            f"{q(new_id)}, {squad_sql}, {q(kind)}, {q(t.get('category'))}, {q(t.get('title') or '未命名')}, {q(d)}, "
            f"{q(t.get('startTime'))}, {q(t.get('endTime'))}, {q(t.get('location'))}, {q(t.get('note'))}, "
            f"{num(t.get('quota'))}, {num(t.get('priceAdult'))}, {num(t.get('priceChild'))}, "
            f"{member_ref(creator) if creator in member_names else 'null'}, {qj(extra)});")
        stats['tasks'] += 1

# ---------------------------------------------------------------------
# 報名
# ---------------------------------------------------------------------
REG_KNOWN = {'id', 'taskId', 'userName', 'type', 'status', 'diet', 'plusAdult', 'plusChild', 'breakdown',
             'finalPrice', 'timestamp'}
seen_reg = set()
for r in data.get('registrations', []):
    if r.get('taskId') not in task_ids:
        stats['skipped'] += 1
        continue  # 任務已被刪除的舊報名
    name = r.get('userName')
    if not known_member(name, '報名'):
        continue
    key = (r['taskId'], name)
    if key in seen_reg:  # 舊資料偶有重複報名，只留一筆
        stats['skipped'] += 1
        continue
    seen_reg.add(key)
    extra = {k: v for k, v in r.items() if k not in REG_KNOWN}
    lines.append(
        'insert into registrations (task_id, member_id, status, diet, plus_adult, plus_child, breakdown, final_price, extra) values ('
        f"{q(task_ids[r['taskId']][0])}, {member_ref(name)}, {q(r.get('status') or '出席')}, {q(r.get('diet'))}, "
        f"{num(r.get('plusAdult'))}, {num(r.get('plusChild'))}, "
        f"{qj(r['breakdown']) if r.get('breakdown') is not None else 'null'}, "
        f"{num(r['finalPrice']) if r.get('finalPrice') not in (None, '') else 'null'}, {qj(extra)});")
    stats['registrations'] += 1

# ---------------------------------------------------------------------
# 協勤紀錄與案件
# ---------------------------------------------------------------------
for r in data.get('assistance_records', []):
    name, d = r.get('userName'), norm_date(r.get('date'))
    ss, se = norm_time(r.get('shiftStart')), norm_time(r.get('shiftEnd'))
    if not d or not ss or not se:
        stats['skipped'] += 1
        warnings.append(f'協勤 {name} {r.get("date")}：日期或時段無法辨識，略過')
        continue
    if not known_member(name, f'協勤 {r.get("date")}'):
        continue
    cases = r.get('cases') or []
    if not cases and r.get('caseType'):  # 相容最早期一筆一案件的格式
        cases = [{'caseStart': r.get('caseStart'), 'caseEnd': r.get('caseEnd'), 'district': r.get('district'),
                  'address': r.get('address'), 'caseType': r.get('caseType'), 'description': r.get('description'),
                  'rescuedCount': r.get('rescuedCount')}]
    rid = str(uuid.uuid4())
    rtype = '急救護-救護勤務' if cases else (r.get('recordType') or '待命協勤')
    ts = r.get('timestamp')
    created = None
    if isinstance(ts, str):
        m = re.match(r'^(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})[ T](\d{1,2}):(\d{2})(?::(\d{2}))?', ts)
        if m:
            created = f'{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d} {int(m.group(4)):02d}:{m.group(5)}:{m.group(6) or "00"}+08'
    lines.append(
        'insert into assistance_records (id, squad_id, member_id, date, shift_start, shift_end, record_type, created_at) values ('
        f"{q(rid)}, {squad_sql}, {member_ref(name)}, {q(d)}, {q(ss)}, {q(se)}, {q(rtype)}, "
        f"{q(created) + '::timestamptz' if created else 'now()'});")
    stats['records'] += 1
    for i, c in enumerate(cases):
        lines.append(
            'insert into assistance_cases (record_id, seq, case_start, case_end, district, address, case_type, description, rescued_count) values ('
            f"{q(rid)}, {i + 1}, {q(norm_time(c.get('caseStart')))}, {q(norm_time(c.get('caseEnd')))}, "
            f"{q(c.get('district'))}, {q(c.get('address'))}, {q(c.get('caseType'))}, {q(c.get('description'))}, "
            f"{num(c.get('rescuedCount'))});")
        stats['cases'] += 1

# ---------------------------------------------------------------------
# 零用金：舊的 cash_history 有每筆收支與結餘
# ---------------------------------------------------------------------
fin = data.get('finance') or {}
hist = fin.get('cash_history')
if isinstance(hist, str):
    try:
        hist = json.loads(hist)
    except json.JSONDecodeError:
        hist = []
for e in sorted(hist or [], key=lambda e: str(e.get('date', ''))):
    d = norm_date(e.get('date'))
    if not d:
        stats['skipped'] += 1
        continue
    item = e.get('item') or e.get('desc') or e.get('description') or e.get('name') or e.get('title') or '（未命名）'
    lines.append(
        'insert into fund_entries (squad_id, date, item, income, expense, note) values ('
        f"{squad_sql}, {q(d)}, {q(item)}, {num(e.get('income'))}, {num(e.get('expense'))}, {q(e.get('note') or e.get('remark'))});")
    stats['fund'] += 1

lines.append('commit;')
lines.append('select ' + ', '.join(f"{v} as {k}" for k, v in stats.items()) + ';')
open(out_path, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')

print('筆數：', json.dumps(stats, ensure_ascii=False))
print('提醒：')
for w in warnings[:40]:
    print('  -', w)
if len(warnings) > 40:
    print(f'  …另外還有 {len(warnings) - 40} 則')
