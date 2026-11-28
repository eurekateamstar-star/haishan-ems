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
rep_between('    <script>\n        const FCM_VAPID_KEY', '    <style>', '''    <style>[v-cloak]{display:none !important;}</style>
    <script charset="utf-8" src="https://static.line-scdn.net/liff/edge/2/sdk.js"></script>
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
                <div v-cloak v-else-if="binding && binding.status === 'suspended'" class="bg-rose-50 border border-rose-200 rounded-2xl p-6 text-center">
                    <i class="fa-solid fa-user-lock text-3xl text-rose-400 mb-3"></i>
                    <p class="text-sm font-black text-rose-600">{{ binding.name }} 的帳號已停用</p>
                    <p class="text-[11px] font-bold text-rose-400 mt-2">請聯絡分隊幹部</p>
                </div>

                <!-- 狀態 3：第一次使用，綁定隊員身分 -->
                <div v-cloak v-else-if="binding && binding.status === 'unbound'" class="space-y-3 text-left">
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
                <div v-cloak v-else class="text-center space-y-4">
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
                // 手機網路慢時，隊員名單偶爾還沒到：再同步一次
                if (!members.value.some(m => m.姓名 === b.name)) {
                    await new Promise(r => setTimeout(r, 1200));
                    await Store.refreshAll();
                }
                if (!members.value.some(m => m.姓名 === b.name)) {
                    showAppAlert('error', '隊員資料讀取不完整', `已登入為 ${b.name}，但隊員名單沒有載入（目前 ${members.value.length} 人）。請關掉後重新開啟；若仍如此，請把這個畫面截圖給管理員。`);
                }
                executeSystemLogin(b.name);
                authLoading.value = false;
                // 圖文選單的按鈕會帶 ?page=schedule / assistance，直接開到那一頁
                const page = new URLSearchParams(location.search).get('page');
                if (['dashboard', 'schedule', 'assistance'].includes(page)) currPage.value = page;
            };
            window.addEventListener('store-error', (e) => showAppAlert('error', '資料讀取失敗', e.detail));
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
# 5d. iPhone 的 LINE 內建瀏覽器沒有 navigator.serviceWorker，直接取用會讓整段初始化中斷
# ---------------------------------------------------------------------
s = s.replace("navigator.serviceWorker.controller", "navigator.serviceWorker?.controller")
s = s.replace("navigator.serviceWorker.ready", "navigator.serviceWorker?.ready")
s = s.replace("navigator.serviceWorker.register", "navigator.serviceWorker?.register")

# ---------------------------------------------------------------------
# 6. 回傳給畫面的變數
# ---------------------------------------------------------------------
rep(' authLoading, googleUser, isBoundGoogleUser, loginWithGoogle, bindAndLogin, unbindGoogleAccount,',
    ' authLoading, googleUser, isBoundGoogleUser, loginWithGoogle, bindAndLogin, unbindGoogleAccount,'
    ' binding, lineProfileRef, squads, bindableMembers, bindForm, bindLoading, loadBindable, bootLine,'
    ' isSuperAdmin, currentSquadName, currentSquadIdRef, switchSquad, myRole,')

# ---------------------------------------------------------------------
# 6c. 提示 / 確認視窗在 Vue 啟動前先隱藏，避免開啟時閃出紅色錯誤框與 {{ }} 原始碼
# ---------------------------------------------------------------------
for _k in ('appAlert', 'appConfirm'):
    rep(f'<div class="bottom-sheet-overlay" :class="{{ active: {_k}.show }}"', f'<div v-cloak class="bottom-sheet-overlay" :class="{{ active: {_k}.show }}"')
    rep(f'<div class="bottom-sheet" :class="{{ active: {_k}.show }}"', f'<div v-cloak class="bottom-sheet" :class="{{ active: {_k}.show }}"')

# ---------------------------------------------------------------------
# 6d. 主控台：推播訂閱燈號 / Google 綁定 → LINE 頭貼與 LINE 綁定狀態
# ---------------------------------------------------------------------
LINE_AVATAR = lambda m, size, rounded: (
    f'<img v-if="{m}.line_picture_url" :src="{m}.line_picture_url" referrerpolicy="no-referrer" '
    f'class="{size} {rounded} object-cover shadow-sm border-2" :class="{m}.is_suspended ? \'border-slate-200 grayscale\' : \'border-[#06C755]\'" alt="">')

# 九宮格：右上角燈號
rep('''                <span v-else class="w-2.5 h-2.5 rounded-full shadow-sm" :class="m.hasSub ? 'bg-emerald-400' : 'bg-rose-400'"></span>
                <span v-if="m.hasBind && !m.is_suspended" class="w-3 h-3 rounded-full bg-blue-500 text-white flex items-center justify-center shadow-sm" style="font-size: 7px;"><i class="fa-brands fa-google"></i></span>''',
'''                <span v-else-if="m.hasBind" class="w-4 h-4 rounded-full bg-[#06C755] text-white flex items-center justify-center shadow-sm" style="font-size: 9px;" title="LINE 已綁定"><i class="fa-brands fa-line"></i></span>
                <span v-else class="text-[8px] bg-slate-100 text-slate-400 px-1 py-0.5 rounded font-black border border-slate-200">未綁定</span>''')

# 九宮格：頭像
rep('''            <div class="w-12 h-12 rounded-full flex items-center justify-center text-lg font-black shadow-sm mb-2"
                 :class="m.is_suspended ? 'bg-slate-200 text-slate-500' : (m.hasSub ? 'bg-blue-100 text-blue-600' : 'bg-white text-slate-400 border border-slate-200')">
                {{ m.姓名.charAt(0) }}
            </div>''',
'''            <div class="mb-2">
                ''' + LINE_AVATAR('m', 'w-12 h-12', 'rounded-full') + '''
                <div v-else class="w-12 h-12 rounded-full flex items-center justify-center text-lg font-black shadow-sm"
                     :class="m.is_suspended ? 'bg-slate-200 text-slate-500' : (m.hasBind ? 'bg-green-50 text-[#06C755] border border-green-200' : 'bg-white text-slate-300 border border-dashed border-slate-300')">
                    {{ m.姓名.charAt(0) }}
                </div>
            </div>''')

# 人員面板：頭像
rep('''                        <div class="w-12 h-12 rounded-[16px] flex items-center justify-center text-xl font-black shadow-sm"
                             :class="adminSelectedMember.hasSub ? 'bg-blue-50 text-blue-600 border border-blue-100' : 'bg-rose-50 text-rose-600 border border-rose-100'">
                            {{ adminSelectedMember.姓名.charAt(0) }}
                        </div>''',
'''                        ''' + LINE_AVATAR('adminSelectedMember', 'w-12 h-12', 'rounded-[16px]') + '''
                        <div v-else class="w-12 h-12 rounded-[16px] flex items-center justify-center text-xl font-black shadow-sm"
                             :class="adminSelectedMember.hasBind ? 'bg-green-50 text-[#06C755] border border-green-200' : 'bg-slate-50 text-slate-400 border border-slate-200'">
                            {{ adminSelectedMember.姓名.charAt(0) }}
                        </div>''')

# 人員面板：狀態列（拿掉推播，只留 LINE 綁定）
rep_between('''                        <span class="push-indicator" :class="adminSelectedMember.hasSub ? 'push-ok' : 'push-fail'">''',
'''                    </div>

                    <!-- 本週活動 -->''',
'''                        <span v-if="adminSelectedMember.hasBind" class="push-indicator bg-green-50 text-[#06C755] border border-green-200">
                            <i class="fa-brands fa-line" style="font-size:11px"></i> LINE 已綁定<template v-if="adminSelectedMember.line_display_name">：{{ adminSelectedMember.line_display_name }}</template>
                        </span>
                        <span v-else class="push-indicator bg-slate-200 text-slate-500">
                            <i class="fa-brands fa-line" style="font-size:11px"></i> LINE 未綁定
                        </span>
                        <span v-if="adminSelectedMember.bound_at" class="text-[10px] font-bold text-slate-400">綁定於 {{ String(adminSelectedMember.bound_at).slice(0, 10) }}</span>
''')

# 人員面板：拿掉推播按鈕
rep_between('''                        <p class="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-1 px-1">通知與設定</p>
                        <div class="flex gap-2">''',
'''                        <button @click="openAdminEditMember(adminSelectedMember); isAdminMemberMenuOpen = false"''',
'''                        <p class="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-1 px-1">設定</p>
''')

# 編輯隊員：Google 綁定區 → LINE 綁定
rep('''            <span><i class="fa-brands fa-google mr-1 text-red-500"></i>Google 帳號綁定</span>''',
    '''            <span><i class="fa-brands fa-line mr-1 text-[#06C755]"></i>LINE 帳號綁定</span>''')
rep('''                <div v-if="adminEditForm.email" class="flex justify-between items-center bg-white border border-slate-200 p-2.5 rounded-xl">
                    <div class="flex flex-col overflow-hidden mr-2">
                        <span class="text-[9px] font-black text-slate-400 uppercase">已綁定帳號</span>
                        <span class="text-sm font-bold text-slate-700 truncate">{{ adminEditForm.email }}</span>
                    </div>''',
'''                <div v-if="adminEditForm.uid" class="flex justify-between items-center bg-white border border-slate-200 p-2.5 rounded-xl">
                    <div class="flex items-center gap-2 overflow-hidden mr-2">
                        <img v-if="adminEditForm.line_picture_url" :src="adminEditForm.line_picture_url" referrerpolicy="no-referrer" class="w-9 h-9 rounded-full object-cover border-2 border-[#06C755] shrink-0" alt="">
                        <div class="flex flex-col overflow-hidden">
                            <span class="text-[9px] font-black text-slate-400 uppercase">已綁定 LINE</span>
                            <span class="text-sm font-bold text-slate-700 truncate">{{ adminEditForm.line_display_name || '（未提供名稱）' }}</span>
                        </div>
                    </div>''')
rep('''<span class="text-xs font-bold">尚未綁定任何 Google 帳號</span>''',
    '''<span class="text-xs font-bold">尚未綁定 LINE，隊員第一次登入時用生日驗證綁定</span>''')
rep('''                    uid:          m.uid || '',
''', '''                    uid:          m.uid || '',
                    line_display_name: m.line_display_name || '',
                    line_picture_url:  m.line_picture_url || '',
''')
rep('''                        adminEditForm.value.email = '';
''', '''                        adminEditForm.value.email = '';
                        adminEditForm.value.line_display_name = '';
                        adminEditForm.value.line_picture_url = '';
''')

# 統計卡與篩選
rep('''                                    <div class="admin-stat-label">已訂閱推播</div>
                                    <div class="admin-stat-value text-emerald-600">{{ adminStats.subCount }}</div>''',
'''                                    <div class="admin-stat-label">LINE 已綁定</div>
                                    <div class="admin-stat-value text-[#06C755]">{{ adminStats.subCount }}</div>''')
rep('''                                    <div class="admin-stat-label">未訂閱</div>''', '''                                    <div class="admin-stat-label">尚未綁定</div>''')
rep('''                                    <div class="admin-stat-label">昨日推播失敗</div>
                                    <div class="admin-stat-value text-amber-500">{{ adminStats.failCount }}</div>''',
'''                                    <div class="admin-stat-label">停用</div>
                                    <div class="admin-stat-value text-slate-500">{{ adminStats.failCount }}</div>''')
rep('''                subCount:     adminMembersData.value.filter(m => m.hasSub).length,
                noSubCount:   adminMembersData.value.filter(m => !m.hasSub).length,''',
'''                subCount:     adminMembersData.value.filter(m => m.hasBind && !m.is_suspended).length,
                noSubCount:   adminMembersData.value.filter(m => !m.hasBind && !m.is_suspended).length,''')
rep('''                failCount:    adminMembersData.value.filter(m => m.pushResult === 'fail').length,''',
    '''                failCount:    adminMembersData.value.filter(m => m.is_suspended).length,''')
rep('''                { key: 'nosub',    label: '未訂閱' },
                { key: 'hasact',   label: '本周有活動' },
                { key: 'pushfail', label: '昨日失敗' },
                { key: 'pushok',   label: '昨日成功' },''',
'''                { key: 'nosub',    label: '未綁定' },
                { key: 'pushok',   label: '已綁定' },
                { key: 'hasact',   label: '本周有活動' },''')
rep('''                    if (adminFilter.value === 'nosub')    return !m.hasSub;''', '''                    if (adminFilter.value === 'nosub')    return !m.hasBind && !m.is_suspended;''')
rep('''                    if (adminFilter.value === 'pushok')   return m.pushResult === 'sent';''', '''                    if (adminFilter.value === 'pushok')   return m.hasBind;''')


# 主控台：推播已移除，標題與按鈕跟著調整
rep('''<h3 class="text-xl font-black text-slate-800">推播主控台</h3>''', '''<h3 class="text-xl font-black text-slate-800">隊員主控台</h3>''')
rep('''    <button @click="openBatchPushModal" class="flex-1 py-3.5 rounded-2xl bg-slate-800 text-white font-black text-[13px] shadow-lg shadow-slate-200 active:scale-[0.98] transition-all flex items-center justify-center gap-2">
        <i class="fa-solid fa-bullhorn"></i>
        自訂群體推播
    </button>
    <button @click="openAddMemberModal" class="shrink-0 w-[52px] rounded-2xl''',
'''    <button @click="openAddMemberModal" class="flex-1 py-3.5 gap-2 text-[13px] rounded-2xl''')
rep('''        <i class="fa-solid fa-user-plus text-lg"></i>
    </button>''', '''        <i class="fa-solid fa-user-plus text-lg"></i> 新增隊員
    </button>''')
rep('''>PUSH NOTIFICATION ADMIN</p>''', '''>MEMBER ADMIN</p>''')
rep('''推播紀錄依昨日 <span class="font-black text-slate-600">push_logs</span> 判斷。''', '''右上角綠色 LINE 標記代表已綁定。''')

# ---------------------------------------------------------------------
# 6e. 救護分頁（取代舊網站的「常訓」iframe）：救護手冊、單項技術、藥物小卡
#     直接寫在新網站裡，不再嵌入 Regular（Regular 會讀舊 Firestore 的隊員資料）
# ---------------------------------------------------------------------
# 藥物小卡 PDF：先找新網站自己的 assets/medications.pdf，沒有就讀舊的 Firebase Storage 公開檔
MED_PDF_FIREBASE = 'https://firebasestorage.googleapis.com/v0/b/star-c5e91.firebasestorage.app/o/medications.pdf?alt=media'

rep('''        .tab-item { flex: 0 0 auto; display: flex; flex-direction: column; align-items: center; cursor: pointer; }''',
'''        .tab-item { flex: 0 0 auto; display: flex; flex-direction: column; align-items: center; cursor: pointer; }
        /* 救護分頁 */
        .rescue-body { flex: 1; overflow-y: auto; -webkit-overflow-scrolling: touch; padding-bottom: calc(90px + var(--safe-bottom)); }
        .book-scene { perspective: 1200px; }
        .book-body { box-shadow: 1px 0px 0px #fff, 2px 0px 0px #cbd5e1, 3px 0px 0px #fff, 4px 0px 0px #94a3b8, 5px 0px 0px #fff, 6px 0px 0px #64748b, 12px 15px 30px rgba(0,0,0,0.18); transform-style: preserve-3d; }
        .book-cover { transform-origin: left center; transition: transform 0.4s ease-out, box-shadow 0.4s ease-out; transform: translateZ(1px); }
        .book-scene:active .book-cover, .book-scene:hover .book-cover { transform: rotateY(-25deg) translateZ(1px); box-shadow: 15px 10px 25px rgba(0,0,0,0.25); }
        .pdf-slider { display: flex; overflow-x: auto; overflow-y: hidden; scroll-snap-type: x mandatory; -webkit-overflow-scrolling: touch; width: 100%; scrollbar-width: none; }
        .pdf-slider::-webkit-scrollbar { display: none; }
        .pdf-page-container { flex: 0 0 100%; scroll-snap-align: center; display: flex; justify-content: center; align-items: flex-start; }
        .canvas-wrapper { width: 100%; padding-bottom: 112%; position: relative; overflow: hidden; background: #fff; border-top: 1px solid #e2e8f0; border-bottom: 1px solid #e2e8f0; box-shadow: 0 4px 15px rgba(0,0,0,0.03); }
        .canvas-wrapper canvas { position: absolute; top: 50%; left: 50%; width: 102%; height: auto; transform: translate(-50%, -50%); }''')

BOOK = lambda key, title, color, ebook: f'''
                <div v-show="activeRescueTab === '{key}'" class="fade-in flex flex-col pt-6 px-6">
                    <div class="text-center mb-6">
                        <h2 class="text-lg font-black text-slate-800 tracking-wider">內政部消防署 <span class="{color}">{title}</span></h2>
                        <p class="text-[11px] font-bold text-slate-400 mt-1"><i class="fa-solid fa-hand-pointer mr-1"></i>點擊下方掀開書本</p>
                    </div>
                    <div class="flex flex-col items-center pt-2 pb-8">
                        <a href="https://ebook.nfa.gov.tw/{ebook}/mobile/index.html#p=1" target="_blank" rel="noopener noreferrer" class="book-scene relative block w-[85%] max-w-[340px]">
                            <div class="book-body relative w-full bg-[#f8fafc] border-l-[3px] border-slate-400 aspect-[1/1.4] rounded-sm">
                                <div class="book-cover absolute inset-0 w-full h-full bg-white z-10 overflow-hidden border border-slate-100 rounded-sm">
                                    <img src="https://ebook.nfa.gov.tw/{ebook}/files/mobile/1.jpg" alt="{title}封面" class="w-full h-full object-cover block" loading="lazy">
                                </div>
                            </div>
                        </a>
                    </div>
                </div>'''

rep('''        <!-- 協勤登記頁面 (與 dashboard / schedule 同級切換) -->''',
'''        <!-- 救護頁面：救護手冊、單項技術、藥物小卡 -->
        <div v-else-if="currPage === 'rescue'" class="dashboard-wrapper fade-in">
            <div class="tabs-section">
                <div class="tabs-scroll-container">
                    <div v-for="tab in rescueTabs" :key="tab.id" @click="activeRescueTab = tab.id" class="tab-item">
                        <div class="w-14 h-14 rounded-2xl flex items-center justify-center mb-2 shadow-sm transition-all" :class="activeRescueTab === tab.id ? tab.activeClass : 'bg-white text-slate-300 border border-slate-100'"><i :class="tab.icon" class="text-xl"></i></div>
                        <span class="text-[11px] font-black" :class="activeRescueTab === tab.id ? tab.textColor : 'text-slate-400'">{{ tab.name }}</span>
                    </div>
                </div>
            </div>
            <div class="rescue-body" @touchstart.passive="onRescueTouchStart" @touchend="onRescueTouchEnd">'''
+ BOOK('manual', '救護手冊', 'text-emerald-500', '1140527')
+ BOOK('skill', '單項技術', 'text-orange-500', '1140526') + '''
                <div v-show="activeRescueTab === 'medication'" class="fade-in flex flex-col w-full">
                    <div class="flex justify-between items-center pt-4 pb-2 px-6">
                        <h2 class="text-xl font-black text-slate-800 tracking-wider">藥物小卡</h2>
                        <div v-if="medTotalPages > 0" class="bg-red-100 text-red-600 px-3 py-1 rounded-full text-xs font-black shadow-sm font-num">{{ medCurrentPage }} / {{ medTotalPages }}</div>
                    </div>
                    <div v-if="medPdfLoading" class="min-h-[300px] flex flex-col items-center justify-center">
                        <i class="fa-solid fa-spinner fa-spin text-3xl text-red-400 mb-3"></i>
                        <p class="text-sm font-black text-slate-400 tracking-widest">繪製小卡中...</p>
                    </div>
                    <div v-else-if="medPdfError" class="min-h-[300px] flex flex-col items-center justify-center gap-3 px-6 text-center">
                        <i class="fa-solid fa-triangle-exclamation text-3xl text-slate-300"></i>
                        <p class="text-sm font-black text-slate-400">藥物小卡載入失敗</p>
                        <button @click="loadMedPdf(true)" class="px-5 py-2.5 rounded-xl bg-red-500 text-white text-sm font-black active:scale-95">重新載入</button>
                    </div>
                    <div v-show="!medPdfLoading && !medPdfError" class="pdf-slider" @scroll="onMedSliderScroll">
                        <div v-for="n in medTotalPages" :key="n" class="pdf-page-container">
                            <div class="canvas-wrapper"><canvas :id="'med-canvas-' + n"></canvas></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- 協勤登記頁面 (與 dashboard / schedule 同級切換) -->''')

# 底部導覽列：協勤後面加「救護」
rep('''<span class="text-[13px] font-black mt-1">協勤</span></div>''',
    '''<span class="text-[13px] font-black mt-1">協勤</span></div>
                <div @click="currPage='rescue'" :class="currPage === 'rescue' ? 'text-blue-600' : 'text-slate-300'" class="nav-item cursor-pointer"><i class="fa-solid fa-briefcase-medical text-xl"></i><span class="text-[13px] font-black mt-1">救護</span></div>''')

# ?page=rescue 也可以直接打開
rep("if (['dashboard', 'schedule', 'assistance'].includes(page)) currPage.value = page;",
    "if (['dashboard', 'schedule', 'assistance', 'rescue'].includes(page)) currPage.value = page;")

# 程式：分頁狀態、左右滑動切換、藥物小卡 PDF（第一次打開救護頁才下載 pdf.js 與 PDF）
rep('''            return {
                isAdmin, currPage,''', '''            // ===== 救護分頁 =====
            const rescueTabs = [
                { id: 'manual',     name: '救護手冊', icon: 'fa-solid fa-book-medical', activeClass: 'bg-emerald-500 text-white shadow-md', textColor: 'text-emerald-500' },
                { id: 'skill',      name: '單項技術', icon: 'fa-solid fa-kit-medical',  activeClass: 'bg-orange-500 text-white shadow-md',  textColor: 'text-orange-500' },
                { id: 'medication', name: '藥物小卡', icon: 'fa-solid fa-pills',        activeClass: 'bg-red-500 text-white shadow-md',     textColor: 'text-red-500' },
            ];
            const activeRescueTab = ref('manual');
            let rescueTouchX = 0, rescueTouchY = 0;
            const onRescueTouchStart = (e) => { rescueTouchX = e.changedTouches[0].screenX; rescueTouchY = e.changedTouches[0].screenY; };
            const onRescueTouchEnd = (e) => {
                if (e.target.closest('.pdf-slider')) return; // 藥物小卡左右滑是翻頁
                const dx = e.changedTouches[0].screenX - rescueTouchX, dy = e.changedTouches[0].screenY - rescueTouchY;
                if (Math.abs(dx) <= Math.abs(dy) || Math.abs(dx) < 50) return;
                const i = rescueTabs.findIndex(t => t.id === activeRescueTab.value);
                const j = dx < 0 ? Math.min(i + 1, rescueTabs.length - 1) : Math.max(i - 1, 0);
                activeRescueTab.value = rescueTabs[j].id;
            };

            const MED_PDF_URLS = ['./assets/medications.pdf', ''' + repr(MED_PDF_FIREBASE) + '''];
            const medTotalPages = ref(0), medCurrentPage = ref(1), medPdfLoading = ref(false), medPdfError = ref(false);
            let pdfjsPromise = null, medPdfDoc = null;
            const loadPdfJs = () => pdfjsPromise || (pdfjsPromise = new Promise((resolve, reject) => {
                if (window.pdfjsLib) return resolve(window.pdfjsLib);
                const sc = document.createElement('script');
                sc.src = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js';
                sc.onload = () => { window.pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js'; resolve(window.pdfjsLib); };
                sc.onerror = () => { pdfjsPromise = null; reject(new Error('pdf.js 載入失敗')); };
                document.head.appendChild(sc);
            }));
            const loadMedPdf = async (retry = false) => {
                if (medPdfLoading.value || (medTotalPages.value > 0 && !retry)) return;
                medPdfLoading.value = true; medPdfError.value = false;
                try {
                    const pdfjs = await loadPdfJs();
                    let pdf = medPdfDoc;
                    for (const url of (pdf ? [] : MED_PDF_URLS)) {
                        try { pdf = await pdfjs.getDocument(url).promise; break; } catch (e) { console.warn('藥物小卡讀取失敗', url, e); }
                    }
                    if (!pdf) throw new Error('找不到藥物小卡 PDF');
                    medPdfDoc = pdf;
                    medTotalPages.value = pdf.numPages;
                    await nextTick();
                    for (let i = 1; i <= pdf.numPages; i++) {
                        try {
                            const page = await pdf.getPage(i);
                            const canvas = document.getElementById('med-canvas-' + i);
                            if (canvas) {
                                const viewport = page.getViewport({ scale: 1.8 });
                                canvas.width = viewport.width; canvas.height = viewport.height;
                                await page.render({ canvasContext: canvas.getContext('2d'), viewport }).promise;
                            }
                        } catch (e) { console.warn('第 ' + i + ' 頁繪製失敗', e); }
                        if (i === Math.min(2, pdf.numPages)) medPdfLoading.value = false;
                        await new Promise(r => setTimeout(r, 60));
                    }
                } catch (e) {
                    console.warn(e);
                    medTotalPages.value = 0; medPdfError.value = true;
                } finally {
                    medPdfLoading.value = false;
                }
            };
            const onMedSliderScroll = (e) => { const w = e.target.offsetWidth; if (w > 0) medCurrentPage.value = Math.round(e.target.scrollLeft / w) + 1; };
            // 進入救護頁就在背景準備藥物小卡；切換頁面時畫布會重建，所以回來時重新繪製
            watch(currPage, (p, old) => {
                if (p === 'rescue' && !medPdfLoading.value) { medTotalPages.value = 0; medCurrentPage.value = 1; nextTick(() => loadMedPdf()); }
            });

            return {
                rescueTabs, activeRescueTab, onRescueTouchStart, onRescueTouchEnd,
                medTotalPages, medCurrentPage, medPdfLoading, medPdfError, loadMedPdf, onMedSliderScroll,
                isAdmin, currPage,''')

# ---------------------------------------------------------------------
# 7. 程式檔加上版本號，避免手機快取到「新網頁 + 舊程式」
# ---------------------------------------------------------------------
import time as _time
_ver = _time.strftime('%Y%m%d%H%M')
s = s.replace("from './js/store.js'", f"from './js/store.js?v={_ver}'")
s = s.replace("from './js/auth.js'", f"from './js/auth.js?v={_ver}'")

open(out_path, 'w', encoding='utf-8').write(s)
print('OK', out_path, len(s))
