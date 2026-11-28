// =====================================================================
// LINE LIFF 登入 → Worker 換成 Supabase 憑證 → 建立 Supabase client
// =====================================================================
import { createClient } from 'https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.45.4/+esm';

let cfg = null;
let token = null;       // { access_token, expires_at }
let profile = null;     // { name, picture }
let refreshing = null;

// 登入後要回到哪個網址：預設是目前網址；預覽頁會指定回正式首頁（LINE 只接受登記過的網址）
const loginRedirect = () => (cfg && cfg.loginRedirect ? new URL(cfg.loginRedirect, location.href).href : location.href);

const SKEW = 120; // 到期前 2 分鐘就換新
const now = () => Math.floor(Date.now() / 1000);

function loadCached() {
  try {
    const t = JSON.parse(sessionStorage.getItem('ems_token') || 'null');
    if (t && t.expires_at - SKEW > now()) token = t;
    profile = JSON.parse(sessionStorage.getItem('ems_profile') || 'null');
  } catch (_) { /* 無痕模式等情況讀不到就算了 */ }
}
function saveCached() {
  try {
    sessionStorage.setItem('ems_token', JSON.stringify(token));
    sessionStorage.setItem('ems_profile', JSON.stringify(profile));
  } catch (_) {}
}

async function exchange() {
  const idToken = window.liff.getIDToken();
  if (!idToken) throw Object.assign(new Error('LINE 登入憑證不存在'), { needLogin: true });
  const res = await fetch(cfg.workerUrl.replace(/\/$/, '') + '/auth/line', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ idToken }),
  });
  const data = await res.json().catch(() => ({}));
  if (res.status === 401) throw Object.assign(new Error(data.message || 'LINE 登入已過期'), { needLogin: true });
  if (!res.ok || !data.ok) throw new Error(data.message || '登入失敗（' + res.status + '）');
  token = { access_token: data.access_token, expires_at: data.expires_at };
  profile = data.profile || profile;
  saveCached();
}

// 給 supabase-js 用：每次請求前取得有效的憑證
export async function getAccessToken() {
  if (token && token.expires_at - SKEW > now()) return token.access_token;
  if (!refreshing) refreshing = exchange().finally(() => { refreshing = null; });
  try { await refreshing; }
  catch (e) {
    if (e.needLogin) { window.liff.login({ redirectUri: loginRedirect() }); await new Promise(() => {}); }
    throw e;
  }
  return token.access_token;
}

// 啟動：回傳 { sb, profile }；若需要跳轉到 LINE 登入，會直接跳轉
export async function startAuth(config) {
  cfg = config;
  if (!window.liff) throw new Error('LIFF SDK 載入失敗，請確認網路後重新整理');
  await window.liff.init({ liffId: cfg.liffId });
  if (!window.liff.isLoggedIn()) {
    window.liff.login({ redirectUri: loginRedirect() });
    await new Promise(() => {}); // 等待跳轉
  }
  loadCached();
  await getAccessToken();
  if (!profile?.name) {
    try { const p = await window.liff.getProfile(); profile = { name: p.displayName, picture: p.pictureUrl || '' }; saveCached(); } catch (_) {}
  }
  const sb = createClient(cfg.supabaseUrl, cfg.supabaseKey, { accessToken: getAccessToken });
  return { sb, profile };
}

export function logout() {
  try { sessionStorage.removeItem('ems_token'); sessionStorage.removeItem('ems_profile'); } catch (_) {}
  token = null;
  if (window.liff?.isLoggedIn?.()) window.liff.logout();
}

export const lineProfile = () => profile;
