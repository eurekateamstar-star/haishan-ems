import { createClient } from '@supabase/supabase-js';
import { SignJWT, importJWK } from 'jose';
import fs from 'node:fs';
import * as S from '../js/store.js';
const priv = JSON.parse(fs.readFileSync('priv.json'));
const key = await importJWK(priv, 'ES256');
const tokenFor = (sub) => new SignJWT({ role: 'authenticated' }).setProtectedHeader({ alg: 'ES256', kid: 'k1' })
  .setSubject(sub).setAudience('authenticated').setIssuedAt().setExpirationTime('1h').sign(key);
const clientFor = async (sub) => { const t = await tokenFor(sub);
  return createClient('http://localhost:3002', 'sb_publishable_test', { accessToken: async () => t }); };
const ok = (c, m) => console.log((c ? '✅' : '❌') + ' ' + m);
const { db, collection, doc, query, where, onSnapshot, getDocs, getDoc, addDoc, setDoc, updateDoc, deleteDoc } = S;

// ---- 一般隊員 王佩瑾
let sb = await clientFor('U_member');
console.log('my_binding:', JSON.stringify((await sb.rpc('my_binding')).data));
S.initStore(sb, 1);
let membersSnap; onSnapshot(collection(db, 'members'), (s) => membersSnap = s);
let fin; onSnapshot(doc(db, 'finance', 'squad_fund'), (s) => fin = s);
await new Promise(r => setTimeout(r, 800));
ok(membersSnap.size === 3, `隊員清單 3 人（實際 ${membersSnap.size}）`);
const me = membersSnap.docs.find(d => d.data().姓名 === '王佩瑾').data();
ok(me.is_admin === false && me.uid === 'line' && me.birthday === undefined, '王佩瑾：非幹部、已綁定、讀不到生日');
const hist = JSON.parse(fin.data().cash_history);
ok(hist.length === 2 && hist[1].balance === 4680, `零用金餘額 4680（實際 ${hist[1]?.balance}）`);

await addDoc(collection(db, 'shifts'), { name: '王佩瑾', start: '17', end: '21', date: '2026-11-25', timestamp: new Date() });
let shifts = await getDocs(collection(db, 'shifts'));
ok(shifts.size === 1 && shifts.docs[0].data().name === '王佩瑾' && shifts.docs[0].data().start === '17', '自己排班寫入並讀回');
try { await addDoc(collection(db, 'shifts'), { name: '郭允昊', start: '17', end: '21', date: '2026-11-25' }); ok(false, '幫別人排班應被拒'); }
catch (e) { ok(/row-level security/.test(e.message), '幫別人排班被拒：' + e.message.slice(0, 50)); }

const rec = await addDoc(collection(db, 'assistance_records'), { userName: '王佩瑾', date: '2026-10-30', shiftStart: '13:00', shiftEnd: '18:00',
  recordType: '急救護-救護勤務', timestamp: 'x', cases: [
    { caseStart: '15:27', caseEnd: '16:27', district: '板橋區', address: '中正路433巷23號3樓', caseType: '急病', description: '左側偏癱', rescuedCount: 1 },
    { caseStart: '16:58', caseEnd: '17:59', district: '板橋區', address: '長江路一段11號6樓', caseType: '緊急救援', description: '', rescuedCount: 0 }] });
let r1 = (await getDoc(doc(db, 'assistance_records', rec.id))).data();
ok(r1.cases.length === 2 && r1.cases[0].caseStart === '15:27' && r1.shiftEnd === '18:00' && r1.userName === '王佩瑾', '協勤紀錄含 2 件案件寫入並讀回');
await updateDoc(doc(db, 'assistance_records', rec.id), { date: '2026-10-30', shiftStart: '13:00', shiftEnd: '19:00',
  cases: [{ caseStart: '15:27', caseEnd: '16:27', district: '板橋區', address: 'x', caseType: '急病', description: '', rescuedCount: 1 }] });
r1 = (await getDoc(doc(db, 'assistance_records', rec.id))).data();
ok(r1.cases.length === 1 && r1.shiftEnd === '19:00', '修改協勤紀錄（改時間、刪一件案件）');
const q = await getDocs(query(collection(db, 'members'), where('姓名', '==', '郭允昊')));
ok(q.size === 1, 'where 查詢');
try { await updateDoc(doc(db, 'members', '00000000-0000-0000-0000-00000000000c'), { duty_title: '隊長' });
  const after = (await getDocs(query(collection(db, 'members'), where('姓名', '==', '郭允昊')))).docs[0].data();
  ok(after.duty_title === '隊員', '一般隊員改別人職稱無效'); } catch (e) { ok(true, '一般隊員改別人職稱被拒'); }

// ---- 幹部 劉奕昕
sb = await clientFor('U_admin'); S.initStore(sb, 1);
const t = await addDoc(collection(db, 'official_tasks'), { title: '耶誕城開城', date: '2026-11-13', startTime: '17:00', endTime: '22:00',
  location: '新北歡樂耶誕城', note: '', quota: 1, category: '', priceAdult: 0, priceChild: 0, creator: '劉奕昕', timestamp: new Date() });
await addDoc(collection(db, 'registrations'), { taskId: t.id, userName: '王佩瑾', type: 'duty', status: '出席', timestamp: new Date() });
const regs = await getDocs(collection(db, 'registrations'));
ok(regs.size === 1 && regs.docs[0].data().userName === '王佩瑾' && regs.docs[0].data().type === 'duty', '幹部發布公差並幫隊員報名');
const mid = '00000000-0000-0000-0000-00000000000b';
await updateDoc(doc(db, 'members', mid), { duty_title: '小隊長', medal_志工菁英: '113年', hist_93: 120, hist_94: '', leave_month: ['2026-12'], password: 'x' });
const m2 = (await getDocs(query(collection(db, 'members'), where('姓名', '==', '王佩瑾')))).docs[0].data();
ok(m2.duty_title === '小隊長' && m2.medal_志工菁英 === '113年' && m2.hist_93 === 120 && Array.isArray(m2.leave_month), '幹部修改隊員：職稱、獎章、歷年時數、請假月份');
await updateDoc(doc(db, 'members', mid), { is_admin: true });
ok((await getDocs(query(collection(db, 'members'), where('姓名', '==', '王佩瑾')))).docs[0].data().is_admin === true, '設為幹部');
await setDoc(doc(db, 'members', '新人甲'), { password: 'A123', id_no: 'A123', birthday: '2001-02-03', duty_group: '第三小隊', duty_title: '隊員', duty_count: 0, is_suspended: false, is_admin: false, join_date: '2026-11-23' });
ok((await getDocs(query(collection(db, 'members'), where('姓名', '==', '新人甲')))).size === 1, '新增隊員（含生日）');
await deleteDoc(doc(db, 'official_tasks', t.id));
ok((await getDocs(collection(db, 'registrations'))).size === 0, '刪除公差連同報名一起刪除');

// ---- 板橋幹部看不到海山
sb = await clientFor('U_bq'); S.initStore(sb, 1);
ok((await getDocs(collection(db, 'members'))).size === 0 && (await getDocs(collection(db, 'assistance_records'))).size === 0, '板橋幹部讀不到海山資料');
process.exit(0);
