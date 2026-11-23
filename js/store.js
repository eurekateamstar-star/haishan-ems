// =====================================================================
// 資料層：讓沿用自舊平台的畫面邏輯，繼續用 Firestore 式的呼叫
//   collection / doc / query / where / orderBy / limit
//   onSnapshot / getDocs / getDoc / addDoc / setDoc / updateDoc / deleteDoc
// 但實際讀寫 Supabase，而且只讀「目前分隊」的資料（資料庫 RLS 也會擋）。
//
// 資料欄位對照（畫面用的名稱 ↔ 資料庫欄位）：
//   members:            姓名↔name, is_admin↔role, medal_*↔medals, hist_*↔historic_hours, 其他↔extra
//   shifts:             name(姓名)↔member_id, start↔start_hour, end↔end_hour
//   official_tasks /
//   meeting_tasks:      ↔ tasks(kind = duty / meeting)
//   registrations:      taskId↔task_id, userName↔member_id
//   assistance_records: userName↔member_id, cases[]↔assistance_cases（寫入走 save_assistance）
//   finance/squad_fund: ↔ fund_entries（唯讀，產生 cash_history）
// =====================================================================

let sb = null;          // Supabase client
let squadId = null;     // 目前分隊
const cache = {};       // collectionName -> [{ id, data }]
const listeners = [];   // { ref, cb }
let membersRows = [];   // 目前分隊的隊員（供姓名 ↔ id 對照）

export function initStore(client, currentSquadId) {
  sb = client;
  squadId = currentSquadId;
  for (const k of Object.keys(cache)) delete cache[k];
}
export function setSquad(id) { squadId = id; for (const k of Object.keys(cache)) delete cache[k]; return refreshAll(); }
export const db = { __store: true };

// ---------------------------------------------------------------------
// 參考物件
// ---------------------------------------------------------------------
export const collection = (_db, name) => ({ kind: 'collection', name, filters: [], order: null, max: null });
export const doc = (_db, name, id) => ({ kind: 'doc', name, id: id == null ? null : String(id) });
export const where = (field, op, value) => ({ type: 'where', field, op, value });
export const orderBy = (field, dir = 'asc') => ({ type: 'orderBy', field, dir });
export const limit = (n) => ({ type: 'limit', n });
export const query = (ref, ...clauses) => {
  const q = { ...ref, filters: [...(ref.filters || [])] };
  for (const c of clauses) {
    if (c.type === 'where') q.filters.push(c);
    else if (c.type === 'orderBy') q.order = c;
    else if (c.type === 'limit') q.max = c.n;
  }
  return q;
};

// ---------------------------------------------------------------------
// 讀取：每個集合整包載入目前分隊的資料到記憶體（一個分隊約幾十人，量不大）
// ---------------------------------------------------------------------
const EMPTY_COLLECTIONS = new Set(['push_logs', 'system_news', 'mohw_records']);
const pad = (n) => String(n).padStart(2, '0');
const hhmm = (t) => (t ? String(t).slice(0, 5) : '');
const memberName = (id) => membersRows.find((m) => m.id === id)?.name || '';
const memberIdByName = (name) => membersRows.find((m) => m.name === name)?.id || null;
const check = ({ data, error }) => { if (error) throw new Error(error.message); return data; };

function memberToDoc(r) {
  const d = {
    姓名: r.name, squad_id: r.squad_id, duty_group: r.duty_group || '', duty_title: r.duty_title || '隊員',
    role: r.role, is_admin: r.role === 'squad_admin' || r.role === 'super_admin',
    is_super_admin: r.role === 'super_admin', is_suspended: r.is_suspended,
    join_date: r.join_date || '', emt_level: r.emt_level || '', emt_expiry: r.emt_expiry || '',
    honor_expiry: r.honor_expiry || '', duty_count: r.duty_count || 0, sort_order: r.sort_order,
    uid: r.bound_at ? 'line' : '', line_display_name: r.line_display_name || '', line_picture_url: r.line_picture_url || '',
    ...(r.extra || {}),
  };
  for (const [k, v] of Object.entries(r.medals || {})) d['medal_' + k.replace(/[- \n]+/g, '')] = v;
  for (const [k, v] of Object.entries(r.historic_hours || {})) d['hist_' + k] = v;
  return d;
}

// 生日、LINE userId 不可讀，所以要明確列出欄位
const MEMBER_READ_COLS = 'id, squad_id, name, duty_group, duty_title, role, is_suspended, join_date, emt_level, emt_expiry, ' +
  'honor_expiry, duty_count, medals, historic_hours, sort_order, line_display_name, line_picture_url, bound_at, extra';

const LOADERS = {
  async members() {
    membersRows = check(await sb.from('members').select(MEMBER_READ_COLS).eq('squad_id', squadId).order('sort_order').order('name'));
    return membersRows.map((r) => ({ id: r.id, data: memberToDoc(r) }));
  },
  async shifts() {
    const rows = check(await sb.from('shifts').select('*').eq('squad_id', squadId));
    return rows.map((r) => ({ id: r.id, data: {
      name: memberName(r.member_id), start: r.start_hour, end: r.end_hour, date: r.date, timestamp: r.created_at, ...(r.extra || {}) } }));
  },
  async official_tasks() { return loadTasks('duty'); },
  async meeting_tasks() { return loadTasks('meeting'); },
  async registrations() {
    const rows = check(await sb.from('registrations').select('*, tasks!inner(squad_id, kind)').eq('tasks.squad_id', squadId));
    return rows.map((r) => ({ id: r.id, data: {
      taskId: r.task_id, userName: memberName(r.member_id), type: r.tasks.kind === 'duty' ? 'duty' : 'meeting',
      status: r.status, diet: r.diet, plusAdult: r.plus_adult, plusChild: r.plus_child,
      breakdown: r.breakdown, finalPrice: r.final_price, timestamp: r.updated_at, ...(r.extra || {}) } }));
  },
  async assistance_records() {
    const rows = check(await sb.from('assistance_records').select('*, assistance_cases(*)').eq('squad_id', squadId)
      .order('date', { ascending: false }));
    return rows.map((r) => ({ id: r.id, data: {
      userName: memberName(r.member_id), date: r.date, shiftStart: hhmm(r.shift_start), shiftEnd: hhmm(r.shift_end),
      recordType: r.record_type, timestamp: r.created_at, ...(r.extra || {}),
      ...(r.assistance_cases?.length ? { cases: [...r.assistance_cases].sort((a, b) => a.seq - b.seq).map((c) => ({
        caseStart: hhmm(c.case_start), caseEnd: hhmm(c.case_end), district: c.district || '', address: c.address || '',
        caseType: c.case_type || '', description: c.description || '', rescuedCount: c.rescued_count || 0 })) } : {}),
    } }));
  },
  async finance() {
    const rows = check(await sb.from('fund_entries').select('*').eq('squad_id', squadId).order('date').order('created_at'));
    let balance = 0;
    const history = rows.map((r) => { balance += (r.income || 0) - (r.expense || 0);
      return { id: r.id, date: r.date, item: r.item, income: r.income, expense: r.expense, note: r.note || '', balance }; });
    return [{ id: 'squad_fund', data: { cash_history: JSON.stringify(history) } }];
  },
};

async function loadTasks(kind) {
  const rows = check(await sb.from('tasks').select('*').eq('squad_id', squadId).eq('kind', kind));
  return rows.map((r) => ({ id: r.id, data: {
    title: r.title, date: r.date, startTime: r.start_time || '', endTime: r.end_time || '', location: r.location || '',
    note: r.note || '', quota: r.quota, category: r.category || (kind === 'meeting' ? '一般會議' : ''),
    priceAdult: r.price_adult, priceChild: r.price_child, creator: memberName(r.created_by), timestamp: r.created_at,
    ...(r.extra || {}) } }));
}

async function load(name, force = false) {
  if (!force && cache[name]) return cache[name];
  if (EMPTY_COLLECTIONS.has(name) || name.startsWith('training_data_') || !LOADERS[name] || squadId == null) {
    cache[name] = [];
  } else {
    if (name !== 'members' && !membersRows.length && LOADERS.members) cache.members = await LOADERS.members();
    cache[name] = await LOADERS[name]();
  }
  return cache[name];
}

// ---------------------------------------------------------------------
// 快照物件（模仿 Firestore）
// ---------------------------------------------------------------------
const docSnap = (item, id) => ({
  id: item ? item.id : id,
  exists: () => !!item,
  data: () => (item ? { ...item.data } : undefined),
});
const querySnap = (items) => {
  const docs = items.map((i) => docSnap(i));
  return { docs, empty: docs.length === 0, size: docs.length, forEach: (fn) => docs.forEach(fn) };
};
function applyQuery(items, ref) {
  let out = items.filter((i) => ref.filters.every((f) => {
    const v = i.data[f.field];
    switch (f.op) {
      case '==': return v === f.value;
      case '!=': return v !== f.value;
      case '>': return v > f.value;
      case '>=': return v >= f.value;
      case '<': return v < f.value;
      case '<=': return v <= f.value;
      case 'in': return (f.value || []).includes(v);
      case 'array-contains': return Array.isArray(v) && v.includes(f.value);
      default: return true;
    }
  }));
  if (ref.order) {
    const { field, dir } = ref.order;
    out = [...out].sort((a, b) => String(a.data[field] ?? '').localeCompare(String(b.data[field] ?? '')) * (dir === 'desc' ? -1 : 1));
  }
  if (ref.max) out = out.slice(0, ref.max);
  return out;
}

export async function getDocs(ref) { return querySnap(applyQuery(await load(ref.name), ref)); }
export async function getDoc(ref) { const items = await load(ref.name); return docSnap(items.find((i) => i.id === ref.id), ref.id); }

function emit(name) {
  for (const l of listeners) {
    if (l.ref.name !== name) continue;
    const items = cache[name] || [];
    try {
      l.cb(l.ref.kind === 'doc' ? docSnap(items.find((i) => i.id === l.ref.id), l.ref.id) : querySnap(applyQuery(items, l.ref)));
    } catch (e) { console.error('onSnapshot callback 錯誤', e); }
  }
}

export function onSnapshot(ref, cb, onError) {
  const l = { ref, cb };
  listeners.push(l);
  load(ref.name).then(() => emit(ref.name)).catch((e) => {
    console.error('讀取失敗', ref.name, e); onError?.(e);
    if (squadId != null) window.dispatchEvent(new CustomEvent('store-error', { detail: ref.name + '：' + e.message }));
  });
  return () => { const i = listeners.indexOf(l); if (i >= 0) listeners.splice(i, 1); };
}

export async function refresh(name) {
  if (name === 'members' || name === 'shifts' || name === 'registrations' || name === 'assistance_records') {
    cache.members = await LOADERS.members(); emit('members');
  }
  if (name !== 'members') { await load(name, true); emit(name); }
  // 隊員姓名變了，排班 / 報名 / 協勤的顯示名稱也要更新
  if (name === 'members') for (const n of ['shifts', 'registrations', 'assistance_records']) if (cache[n]) { await load(n, true); emit(n); }
  // 刪除公差 / 會議時，資料庫會一併刪掉報名
  if ((name === 'official_tasks' || name === 'meeting_tasks') && cache.registrations) { await load('registrations', true); emit('registrations'); }
}
export async function refreshAll() {
  const names = [...new Set(listeners.map((l) => l.ref.name))];
  cache.members = await LOADERS.members(); emit('members');
  for (const n of names) if (n !== 'members') { await load(n, true); emit(n); }
}

// ---------------------------------------------------------------------
// 寫入
// ---------------------------------------------------------------------
const MEMBER_COLS = ['squad_id', 'birthday', 'duty_group', 'duty_title', 'is_suspended', 'join_date', 'emt_level',
  'emt_expiry', 'honor_expiry', 'duty_count', 'sort_order'];
const IGNORED_MEMBER_FIELDS = new Set(['password', 'id_no', 'email', 'uid', 'pushSubscription', 'id', 'is_super_admin',
  'line_display_name', 'line_picture_url', 'timestamp']);
const dateOrNull = (v) => (v ? String(v).slice(0, 10) : null);

async function memberPatch(data, current) {
  const row = {}; const extra = { ...(current?.extra || {}) };
  const medals = { ...(current?.medals || {}) }; const hist = { ...(current?.historic_hours || {}) };
  let medalsTouched = false; let histTouched = false; let extraTouched = false;
  for (const [k, v] of Object.entries(data)) {
    if (k === '姓名' || k === 'name') row.name = String(v).trim();
    else if (k === 'is_admin') { if (current?.role !== 'super_admin') row.role = v ? 'squad_admin' : 'member'; }
    else if (k === 'role') row.role = v;
    else if (k.startsWith('medal_')) { medalsTouched = true; const key = k.slice(6); if (v) medals[key] = String(v); else delete medals[key]; }
    else if (k.startsWith('hist_')) { histTouched = true; const key = k.slice(5); if (v === '' || v == null) delete hist[key]; else hist[key] = Number(v); }
    else if (MEMBER_COLS.includes(k)) row[k] = ['join_date', 'emt_expiry', 'honor_expiry', 'birthday'].includes(k) ? dateOrNull(v) : v;
    else if (!IGNORED_MEMBER_FIELDS.has(k)) { extraTouched = true; extra[k] = v; }
  }
  if (medalsTouched) row.medals = medals;
  if (histTouched) row.historic_hours = hist;
  if (extraTouched) row.extra = extra;
  return row;
}

const SHIFT_COLS = { start: 'start_hour', end: 'end_hour', date: 'date' };
const TASK_COLS = { title: 'title', date: 'date', startTime: 'start_time', endTime: 'end_time', location: 'location',
  note: 'note', quota: 'quota', category: 'category', priceAdult: 'price_adult', priceChild: 'price_child' };
const REG_COLS = { status: 'status', diet: 'diet', plusAdult: 'plus_adult', plusChild: 'plus_child',
  breakdown: 'breakdown', finalPrice: 'final_price' };
const SKIP = new Set(['timestamp', 'id', 'creator', 'type']);

function mapRow(data, cols, extraBase = {}) {
  const row = {}; const extra = { ...extraBase }; let extraTouched = false;
  for (const [k, v] of Object.entries(data)) {
    if (cols[k]) row[cols[k]] = (k === 'quota' || k === 'priceAdult' || k === 'priceChild') ? (Number(v) || 0) : v;
    else if (!SKIP.has(k) && k !== 'name' && k !== 'userName' && k !== 'taskId') { extra[k] = v; extraTouched = true; }
  }
  if (extraTouched) row.extra = extra;
  return row;
}

async function writeAssistance(id, data) {
  const current = id ? (cache.assistance_records || []).find((i) => i.id === id)?.data : null;
  const merged = { ...(current || {}), ...data };
  const memberId = memberIdByName(merged.userName);
  const record = { id: id || '', member_id: memberId || '', date: merged.date,
    shift_start: merged.shiftStart, shift_end: merged.shiftEnd };
  const cases = (merged.cases || []).map((c) => ({
    case_start: c.caseStart ?? c.startTime ?? '', case_end: c.caseEnd ?? c.endTime ?? '', district: c.district || '',
    address: c.address || '', case_type: c.caseType ?? c.type ?? '', description: c.description || '',
    rescued_count: Number(c.rescuedCount) || 0 }));
  return check(await sb.rpc('save_assistance', { p_record: record, p_cases: cases }));
}

// 修改時保留原本 extra 裡的其他欄位
async function updateWithExtra(table, id, data, cols) {
  let row = mapRow(data, cols);
  if (row.extra) {
    const cur = check(await sb.from(table).select('extra').eq('id', id).maybeSingle());
    row = mapRow(data, cols, cur?.extra || {});
  }
  if (Object.keys(row).length) check(await sb.from(table).update(row).eq('id', id));
}

export async function addDoc(ref, data) {
  let id;
  switch (ref.name) {
    case 'shifts': {
      const member_id = memberIdByName(data.name);
      if (!member_id) throw new Error('找不到隊員：' + data.name);
      id = check(await sb.from('shifts').insert({ squad_id: squadId, member_id, ...mapRow(data, SHIFT_COLS) }).select('id').single()).id;
      break;
    }
    case 'official_tasks': case 'meeting_tasks': {
      const kind = ref.name === 'official_tasks' ? 'duty' : 'meeting';
      id = check(await sb.from('tasks').insert({ squad_id: squadId, kind, created_by: memberIdByName(data.creator),
        ...mapRow(data, TASK_COLS) }).select('id').single()).id;
      break;
    }
    case 'registrations': {
      const member_id = memberIdByName(data.userName);
      if (!member_id) throw new Error('找不到隊員：' + data.userName);
      id = check(await sb.from('registrations').upsert({ task_id: data.taskId, member_id, ...mapRow(data, REG_COLS) },
        { onConflict: 'task_id,member_id' }).select('id').single()).id;
      break;
    }
    case 'assistance_records': id = await writeAssistance(null, data); break;
    case 'members': {
      const row = await memberPatch(data, null);
      id = check(await sb.from('members').insert({ squad_id: squadId, ...row }).select('id').single()).id;
      break;
    }
    default: throw new Error('新系統不支援寫入：' + ref.name);
  }
  await refresh(ref.name);
  return { id };
}

// setDoc 只用在新增隊員（舊平台以姓名當文件 id）
export async function setDoc(ref, data) {
  if (ref.name !== 'members') throw new Error('新系統不支援 setDoc：' + ref.name);
  const row = await memberPatch({ 姓名: ref.id, ...data }, null);
  check(await sb.from('members').insert({ squad_id: squadId, ...row }));
  await refresh('members');
}

export async function updateDoc(ref, data) {
  switch (ref.name) {
    case 'members': {
      const current = membersRows.find((m) => m.id === ref.id);
      const row = await memberPatch(data, current);
      if (Object.keys(row).length) check(await sb.from('members').update(row).eq('id', ref.id));
      break;
    }
    case 'shifts': await updateWithExtra('shifts', ref.id, data, SHIFT_COLS); break;
    case 'official_tasks': case 'meeting_tasks': await updateWithExtra('tasks', ref.id, data, TASK_COLS); break;
    case 'registrations': await updateWithExtra('registrations', ref.id, data, REG_COLS); break;
    case 'assistance_records': await writeAssistance(ref.id, data); break;
    default: throw new Error('新系統不支援修改：' + ref.name);
  }
  await refresh(ref.name);
}

export async function deleteDoc(ref) {
  const table = { members: 'members', shifts: 'shifts', official_tasks: 'tasks', meeting_tasks: 'tasks',
    registrations: 'registrations', assistance_records: 'assistance_records' }[ref.name];
  if (!table) throw new Error('新系統不支援刪除：' + ref.name);
  check(await sb.from(table).delete().eq('id', ref.id));
  await refresh(ref.name);
}

// 給畫面用：目前分隊的隊員原始資料（含 id、role）
export const currentMembersRows = () => membersRows;
export const currentSquadId = () => squadId;
