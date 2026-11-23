#!/usr/bin/env python3
"""
把舊平台 (eurekateamstar-star.github.io/index.html) 轉成新系統的 index.html。

  python3 tools/port_from_old.py <舊 index.html> <輸出 index.html>

做的事：
  - Firebase → js/store.js（Firestore 式呼叫，背後是 Supabase）
  - Google 登入 → LINE LIFF 登入 + 生日驗證綁定（js/auth.js）
  - 拿掉常訓、考核分頁；拿掉 Cloud Run 手機推播
每一處替換都會檢查「剛好出現一次」，舊檔改版對不上時會直接報錯，不會默默產生壞檔。
"""
import sys

src_path, out_path = sys.argv[1], sys.argv[2]
s = open(src_path, encoding='utf-8').read()


def rep(old, new, count=1):
    global s
    n = s.count(old)
    if n != count:
        raise SystemExit(f'找不到預期的內容（出現 {n} 次，應為 {count} 次）：\n{old[:200]}')
    s = s.replace(old, new)


def rep_between(start, end, new, keep_end=True):
    """把 start（含）到 end（不含，keep_end=True）之間換成 new。"""
    global s
    a = s.find(start)
    if a < 0 or s.count(start) != 1:
        raise SystemExit(f'起點不唯一或找不到：{start[:120]}')
    b = s.find(end, a + len(start))
    if b < 0:
        raise SystemExit(f'終點找不到：{end[:120]}')
    if not keep_end:
        b += len(end)
    s = s[:a] + new + s[b:]


# ---------------------------------------------------------------------
# 1. <head>：標題、LIFF SDK、設定值、停用推播
# ---------------------------------------------------------------------
rep('<title>海山救護義消平台</title>', '<title>救護義消協勤平台</title>')
rep_between('    <script>\n        const FCM_VAPID_KEY', '    <style>', '''    <script charset="utf-8" src="https://static.line-scdn.net/liff/edge/2/sdk.js"></script>
    <script>
        // ===== 新系統設定 =====
        window.APP_CONFIG = {
            liffId: "2012765865-adJrZdwg",
            workerUrl: "https://haishan-ems-auth.eurekateamstar.workers.dev",
            supabaseUrl: "https://avyexuqgddrpvcwaddaa.supabase.co",
            supabaseKey: "sb_publishable_qdR5PjP0SZOZG-H1Tn-Llg_G0vEWpfN"
        };
        const FCM_VAPID_KEY = "";
        const LINE_WORKER_URL = "";   // LINE 群組通知：之後再加
        // 手機推播已停用：舊程式呼叫推播的地方一律回傳「未發送」，AI 解析改用本機解析
        const CLOUD_RUN_URL = "https://push-disabled.invalid/";
        (function () {
            const realFetch = window.fetch.bind(window);
            window.fetch = (input, init) => {
                const url = typeof input === 'string' ? input : (input && input.url) || '';
                if (url.startsWith(CLOUD_RUN_URL)) {
                    if (url.includes('ai-parse')) return Promise.resolve(new Response('{}', { status: 503 }));
                    return Promise.resolve(new Response(JSON.stringify({ ok: false, success: false, disabled: true,
                        error: '新系統未啟用手機推播', stats: { success: 0, failure: 0, total: 0 } }),
                        { status: 200, headers: { 'Content-Type': 'application/json' } }));
                }
                return realFetch(input, init);
            };
        })();
    </script>
''')
rep('<link rel="manifest" href="manifest.json">', '')

# ---------------------------------------------------------------------
# 2. 登入畫面：LINE 登入 + 選分隊/姓名 + 生日
# ---------------------------------------------------------------------
rep('''                    <h1 class="text-3xl font-black tracking-tight text-slate-800">HAISHAN EMS</h1>
                    <p class="text-[10px] text-blue-600 font-black tracking-[0.1em] uppercase mt-1">VOLUNTEER AI PLATFORM</p>
                    <p class="text-[15px] text-slate-500 font-bold mt-1 tracking-wider">海山救護義消智慧平台</p>''',
    '''                    <h1 class="text-3xl font-black tracking-tight text-slate-800">EMS PLATFORM</h1>
                    <p class="text-[10px] text-blue-600 font-black tracking-[0.1em] uppercase mt-1">NEW TAIPEI EMS VOLUNTEERS</p>
                    <p class="text-[15px] text-slate-500 font-bold mt-1 tracking-wider">救護義消協勤平台</p>''')

rep_between('                <!-- 狀態 1：檢查登入狀態中 (自動秒登入) -->', '            </div>\n        </div>\n    </div>\n\n    <!-- 登入後 -->', '''                <!-- 狀態 1：LINE 登入中 -->
                <div v-if="authLoading" class="text-center py-8">
                    <i class="fa-solid fa-spinner fa-spin text-4xl text-blue-500 mb-4"></i>
                    <p class="text-sm font-black text-slate-500">LINE 登入中...</p>
                </div>

                <!-- 狀態 2：帳號已停用 -->
                <div v-else-if="binding && binding.status === 'suspended'" class="bg-rose-50 border border-rose-200 rounded-2xl p-6 text-center">
                    <i class="fa-solid fa-user-lock text-3xl text-rose-400 mb-3"></i>
                    <p class="text-sm font-black text-rose-600">{{ binding.name }} 的帳號已停用</p>
                    <p class="text-[11px] font-bold text-rose-400 mt-2">請聯絡分隊幹部</p>
                </div>

                <!-- 狀態 3：第一次使用，綁定隊員身分 -->
                <div v-else-if="binding && binding.status === 'unbound'" class="space-y-3 text-left">
                    <div class="bg-emerald-50 p-3 rounded-xl border border-emerald-100 mb-2 flex items-center gap-3">
                        <img v-if="lineProfileRef?.picture" :src="lineProfileRef.picture" class="w-9 h-9 rounded-full" alt="">
                        <div><p class="text-[10px] font-black text-emerald-600">已用 LINE 登入</p><p class="text-xs font-bold text-slate-700">{{ lineProfileRef?.name }}</p></div>
                    </div>
                    <p class="text-xs font-black text-rose-500"><i class="fa-solid fa-circle-exclamation mr-1"></i>第一次使用，請綁定你的隊員身分</p>

                    <div class="relative flex items-center">
                        <i class="fa-solid fa-people-group absolute left-4 text-slate-400 z-20"></i>
                        <select v-model="bindForm.squadId" @change="loadBindable" class="med-input w-full p-4 appearance-none text-slate-700 bg-white relative z-10" style="padding-left: 3.5rem !important;">
                            <option value="" disabled>選擇分隊</option>
                            <option v-for="sq in squads" :key="sq.id" :value="sq.id">{{ sq.name }}</option>
                        </select>
                        <i class="fa-solid fa-chevron-down absolute right-4 text-slate-300 pointer-events-none z-20"></i>
                    </div>

                    <div class="relative flex items-center">
                        <i class="fa-solid fa-user-doctor absolute left-4 text-slate-400 z-20"></i>
                        <select v-model="bindForm.memberId" :disabled="!bindForm.squadId" class="med-input w-full p-4 appearance-none text-slate-700 bg-white relative z-10 disabled:opacity-50" style="padding-left: 3.5rem !important;">
                            <option value="" disabled>{{ bindForm.squadId && bindableMembers.length === 0 ? '此分隊沒有可綁定的人員' : '選擇姓名' }}</option>
                            <option v-for="m in bindableMembers" :key="m.id" :value="m.id">{{ m.name }}{{ m.duty_group ? '（' + m.duty_group + '）' : '' }}</option>
                        </select>
                        <i class="fa-solid fa-chevron-down absolute right-4 text-slate-300 pointer-events-none z-20"></i>
                    </div>

                    <div>
                        <label class="text-[11px] font-black text-slate-400 ml-1">生日（驗證身分用）</label>
                        <input v-model="bindForm.birthday" type="date" class="med-input w-full p-4 font-bold bg-white mt-1">
                    </div>

                    <button @click="bindAndLogin" :disabled="bindLoading" class="med-btn w-full py-4 mt-2 transition-all tracking-widest text-[15px] font-black shadow-lg shadow-blue-200 disabled:opacity-60">
                        <i v-if="bindLoading" class="fa-solid fa-spinner fa-spin mr-2"></i>驗證並綁定
                    </button>
                    <p class="text-[10px] font-bold text-slate-400 text-center leading-relaxed">找不到自己的名字、或已被綁定，請聯絡分隊幹部</p>
                </div>

                <!-- 狀態 4：登入失敗 -->
                <div v-else class="text-center space-y-4">
                    <p class="text-sm font-bold text-slate-500">無法登入，請確認網路後重試</p>
                    <button @click="bootLine" class="med-btn w-full py-4 font-black">重新登入</button>
                </div>
''')

# ---------------------------------------------------------------------
# 3. 拿掉常訓、考核分頁與底部按鈕
# ---------------------------------------------------------------------
rep_between('<!-- 常訓分頁 (修正版) -->', '<!-- ===== 匯出報表選擇選項 Modal ===== -->', '')
a = s.find("<div @click=\"currPage='regular';expandCards()\"")
b = s.find("</div>\n        </nav>", a)
if a < 0 or b < 0:
    raise SystemExit('找不到常訓/考核按鈕')
s = s[:a] + s[b:]
s = s.replace("<div class=\"flex justify-around items-center h-full px-4\">", "<div class=\"flex justify-around items-center h-full px-4\">", 1)

# 頁首顯示分隊名稱；系統管理員可切換分隊
rep('''<div><p class="text-[10px] text-slate-400 font-bold tracking-wider uppercase mb-0.5">Welcome Back</p>''',
    '''<div><p class="text-[10px] text-slate-400 font-bold tracking-wider uppercase mb-0.5">
            <template v-if="isSuperAdmin">
                <select :value="currentSquadIdRef" @change="switchSquad($event.target.value)" class="bg-transparent font-black text-blue-600 normal-case tracking-normal text-[11px] outline-none">
                    <option v-for="sq in squads" :key="sq.id" :value="sq.id">{{ sq.name }}分隊</option>
                </select>
            </template>
            <template v-else>{{ currentSquadName ? currentSquadName + '分隊' : 'Welcome Back' }}</template>
        </p>''')

# ---------------------------------------------------------------------
# 4. 模組開頭：Firebase → store.js / auth.js
# ---------------------------------------------------------------------
rep_between('    import { initializeApp } from "https://www.gstatic.com/firebasejs/10.7.1/firebase-app.js";',
            '    const { createApp, ref, computed, onMounted, nextTick, watch } = Vue;', '''    import * as Store from './js/store.js';
    import { db, collection, doc, query, where, orderBy, limit, onSnapshot, getDocs, getDoc, addDoc, setDoc, updateDoc, deleteDoc } from './js/store.js';
    import { startAuth, logout as lineLogout } from './js/auth.js';

    // 舊程式還會呼叫到的 Firebase 名稱，留空殼避免出錯
    const auth = { currentUser: null };
    const signOut = async () => {};
    const subscribeFCM = () => {};

''')

# ---------------------------------------------------------------------
# 5. 登入流程
# ---------------------------------------------------------------------
rep('''                subscribeFCM(name);
                getDocs(collection(db, "assistance_records")).then(snap => {
                    const allRecs = snap.docs.map(d => ({ id: d.id, ...d.data() }));
                    allAssistanceRecords.value = allRecs.sort((a, b) => new Date(b.date) - new Date(a.date) || String(b.timestamp).localeCompare(String(a.timestamp)));
                    myAssistanceRecords.value = allRecs.filter(r => r.userName === loginUserName.value)
                        .sort((a, b) => new Date(b.date) - new Date(a.date) || String(b.timestamp).localeCompare(String(a.timestamp)));
                });
            };''', '''                myAssistanceRecords.value = allAssistanceRecords.value.filter(r => r.userName === name);
            };

            // ===== LINE 登入與綁定 =====
            const binding = ref(null);
            const lineProfileRef = ref(null);
            const squads = ref([]);
            const bindableMembers = ref([]);
            const bindForm = ref({ squadId: '', memberId: '', birthday: '' });
            const bindLoading = ref(false);
            const currentSquadIdRef = ref(null);
            const myRole = ref('member');
            const isSuperAdmin = computed(() => myRole.value === 'super_admin');
            const currentSquadName = computed(() => squads.value.find(s => s.id === currentSquadIdRef.value)?.name || '');
            let sbClient = null;

            const loadSquads = async () => {
                const { data } = await sbClient.from('squads').select('id, name').order('sort_order').order('id');
                squads.value = data || [];
            };
            const enterApp = async (b) => {
                myRole.value = b.role;
                currentSquadIdRef.value = b.squad_id;
                Store.initStore(sbClient, b.squad_id);
                await Store.refreshAll();
                executeSystemLogin(b.name);
                authLoading.value = false;
            };
            const bootLine = async () => {
                authLoading.value = true;
                binding.value = null;
                try {
                    const { sb, profile } = await startAuth(window.APP_CONFIG);
                    sbClient = sb;
                    lineProfileRef.value = profile;
                    const { data, error } = await sb.rpc('my_binding');
                    if (error) throw new Error(error.message);
                    binding.value = data;
                    await loadSquads();
                    if (data.status === 'bound') { await enterApp(data); return; }
                } catch (e) {
                    console.error(e);
                    showAppAlert('error', '登入失敗', e.message);
                }
                authLoading.value = false;
            };
            const loadBindable = async () => {
                bindForm.value.memberId = '';
                bindableMembers.value = [];
                if (!bindForm.value.squadId) return;
                const { data, error } = await sbClient.rpc('list_bindable_members', { p_squad_id: Number(bindForm.value.squadId) });
                if (error) return showAppAlert('error', '讀取失敗', error.message);
                bindableMembers.value = data || [];
            };
            const switchSquad = async (id) => {
                currentSquadIdRef.value = Number(id);
                await Store.setSquad(Number(id));
            };
            // 每次回到 App 或每 2 分鐘重新同步一次（取代 Firebase 的即時同步）
            document.addEventListener('visibilitychange', () => {
                if (document.visibilityState === 'visible' && currPage.value !== 'login' && sbClient) Store.refreshAll().catch(() => {});
            });
            setInterval(() => { if (document.visibilityState === 'visible' && currPage.value !== 'login' && sbClient) Store.refreshAll().catch(() => {}); }, 120000);''')

rep_between('let authTimer = setTimeout(() => {', '    // 👇👇👇 監聽黑色提示框的點擊事件 👇👇👇', '''bootLine();

''')

rep_between('            const isBoundGoogleUser = computed(() =>', '         const hasAutoShownNews = ref(false);', '''            const isBoundGoogleUser = computed(() => false);

''')

rep_between('       const loginWithGoogle = async () => {', '            const expandCards = () =>', '''       const loginWithGoogle = () => bootLine();

            const bindAndLogin = async () => {
                const f = bindForm.value;
                if (!f.squadId) return showAppAlert('error', '資料不全', '請選擇分隊。');
                if (!f.memberId) return showAppAlert('error', '資料不全', '請選擇你的姓名。');
                if (!f.birthday) return showAppAlert('error', '資料不全', '請輸入生日。');
                bindLoading.value = true;
                try {
                    const { data, error } = await sbClient.rpc('bind_member', {
                        p_member_id: f.memberId, p_birthday: f.birthday,
                        p_display_name: lineProfileRef.value?.name || null, p_picture_url: lineProfileRef.value?.picture || null
                    });
                    if (error) throw new Error(error.message);
                    if (!data.ok) { bindLoading.value = false; return showAppAlert('error', '綁定失敗', data.message); }
                    const { data: b } = await sbClient.rpc('my_binding');
                    binding.value = b;
                    authLoading.value = true;
                    await enterApp(b);
                } catch (e) {
                    showAppAlert('error', '系統錯誤', e.message);
                } finally {
                    bindLoading.value = false;
                }
            };

            const logout = async () => {
                showAppConfirm('登出', '確定要登出嗎？下次開啟需要重新用 LINE 登入。', () => {
                    lineLogout();
                    currPage.value = 'login';
                    loginUserName.value = '';
                    hasAutoShownNews.value = false;
                    location.reload();
                });
            };
''')

# 解除綁定：改成解除 LINE 綁定
rep_between('            const unbindGoogleAccount = async () => {', '            const confirmCancelSub = ', '''            const unbindGoogleAccount = async () => {
                const m = adminEditTarget.value;
                if (!m) return;
                showAppConfirm('解除 LINE 綁定', `確定要解除 ${m.姓名} 的 LINE 綁定嗎？\\n解除後，對方下次登入要重新用生日驗證綁定。`, async () => {
                    adminActionLoading.value = 'unbind';
                    try {
                        const { data, error } = await sbClient.rpc('unbind_member', { p_member_id: m.id });
                        if (error) throw new Error(error.message);
                        if (!data.ok) throw new Error(data.message);
                        await Store.refresh('members');
                        adminEditForm.value.uid = '';
                        adminEditForm.value.email = '';
                        showAppAlert('success', '解除成功', `已解除 ${m.姓名} 的 LINE 綁定`);
                    } catch (e) {
                        showAppAlert('error', '錯誤', '解除綁定失敗：' + e.message);
                    } finally {
                        adminActionLoading.value = '';
                    }
                });
            };
''')

# ---------------------------------------------------------------------
# 5b. 寫死的海山人名排序 → 改用資料庫的 sort_order（store 已依 sort_order、姓名排好）
# ---------------------------------------------------------------------
import re as _re
_n = len(_re.findall(r"const NAME_ORDER = \[[^\]]*\];", s))
if _n != 1: raise SystemExit(f'NAME_ORDER 出現 {_n} 次')
s = _re.sub(r"const NAME_ORDER = \[[^\]]*\];", "const NAME_ORDER = []; // 依資料庫 sort_order 排序", s)
_n = len(_re.findall(r"const EXPORT_NAME_ORDER = \[[^\]]*\];", s))
if _n != 1: raise SystemExit(f'EXPORT_NAME_ORDER 出現 {_n} 次')
s = _re.sub(r"const EXPORT_NAME_ORDER = \[[^\]]*\];", "const EXPORT_NAME_ORDER = members.value.map(m => m.姓名); // 依資料庫 sort_order", s)

# ---------------------------------------------------------------------
# 5c. 「劉奕昕 = 最高管理員」改成看資料庫的 super_admin 角色；海山字樣改成目前分隊名稱
# ---------------------------------------------------------------------
rep("                if (loginUserName.value === '劉奕昕') return true;", "                if (isSuperAdmin.value) return true;")
s = s.replace("m.is_admin || m.姓名 === '劉奕昕'", "m.is_admin || m.is_super_admin")
s = s.replace("adminSelectedMember.姓名 === '劉奕昕'", "adminSelectedMember.is_super_admin")
s = s.replace("if (m.姓名 === '劉奕昕')", "if (m.is_super_admin)")
rep("newTask.value.title = `海山${t.mo}月份", "newTask.value.title = `${currentSquadName.value}${t.mo}月份")
rep("newTask.value.location = '海山分隊';", "newTask.value.location = currentSquadName.value + '分隊';")
s = s.replace("`海山救護義消", "`${currentSquadName.value}救護義消")
s = s.replace("新北市政府消防局海山義消救護分隊", "新北市政府消防局${currentSquadName.value}義消救護分隊")
s = s.replace("🚨 海山救護義消 — ${typeLabel}發佈", "🚨 ${currentSquadName.value}救護義消 — ${typeLabel}發佈")
s = s.replace("`海山義消_", "`${currentSquadName.value}義消_")
s = s.replace("第一大隊海山分隊${minguoYear}", "${currentSquadName.value}分隊${minguoYear}")
s = s.replace("海山分隊${minguoYear}", "${currentSquadName.value}分隊${minguoYear}")

# ---------------------------------------------------------------------
# 6. 回傳給畫面的變數
# ---------------------------------------------------------------------
rep(' authLoading, googleUser, isBoundGoogleUser, loginWithGoogle, bindAndLogin, unbindGoogleAccount,',
    ' authLoading, googleUser, isBoundGoogleUser, loginWithGoogle, bindAndLogin, unbindGoogleAccount,'
    ' binding, lineProfileRef, squads, bindableMembers, bindForm, bindLoading, loadBindable, bootLine,'
    ' isSuperAdmin, currentSquadName, currentSquadIdRef, switchSquad, myRole,')

open(out_path, 'w', encoding='utf-8').write(s)
print('OK', out_path, len(s))
