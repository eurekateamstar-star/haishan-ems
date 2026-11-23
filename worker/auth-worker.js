// =====================================================================
// 海山救護系統：LINE LIFF 登入 → Supabase 登入憑證（Cloudflare Worker）
//
// 流程：網頁用 LIFF 取得 LINE ID token → 傳到這裡 → 向 LINE 驗證
//       → 用匯入 Supabase 的同一把 ES256 私鑰簽發 JWT（sub = LINE userId）
//       → 網頁拿這個 JWT 存取 Supabase，資料庫用 RLS 判斷身分
//
// Cloudflare Worker 的「設定 → 變數和機密」：
//   LINE_CHANNEL_ID        （一般變數）LINE Login 頻道的 Channel ID
//   SUPABASE_URL           （一般變數）https://xxxx.supabase.co
//   SUPABASE_JWT_PRIVATE_KEY（機密 Secret）金鑰工具產生的私鑰 JWK（整段 JSON）
// =====================================================================

const ALLOWED_ORIGINS = ['https://eurekateamstar-star.github.io'];
const TOKEN_TTL_SECONDS = 60 * 60; // 1 小時，到期前網頁會自動換新

const corsHeaders = (origin) => ({
  'Access-Control-Allow-Origin': ALLOWED_ORIGINS.includes(origin) ? origin : ALLOWED_ORIGINS[0],
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
  'Vary': 'Origin',
});

const json = (obj, status, origin) =>
  new Response(JSON.stringify(obj), {
    status,
    headers: { ...corsHeaders(origin), 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' },
  });

const b64url = (input) => {
  const bytes = typeof input === 'string' ? new TextEncoder().encode(input) : new Uint8Array(input);
  let s = '';
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
};

// 私鑰只解析一次，留在記憶體
let keyCache = null;
async function getSigningKey(env) {
  if (keyCache) return keyCache;
  const jwk = JSON.parse(env.SUPABASE_JWT_PRIVATE_KEY);
  if (jwk.kty !== 'EC' || jwk.crv !== 'P-256' || !jwk.d) throw new Error('SUPABASE_JWT_PRIVATE_KEY 不是 ES256 私鑰');
  const key = await crypto.subtle.importKey(
    'jwk', { kty: 'EC', crv: 'P-256', x: jwk.x, y: jwk.y, d: jwk.d, ext: true },
    { name: 'ECDSA', namedCurve: 'P-256' }, false, ['sign']);

  // 找出 Supabase 給這把金鑰的 kid：到 JWKS 裡找公鑰 x、y 相同的那一把
  let kid = jwk.kid || null;
  try {
    const res = await fetch(`${env.SUPABASE_URL}/auth/v1/.well-known/jwks.json`);
    if (res.ok) {
      const { keys = [] } = await res.json();
      const match = keys.find((k) => k.x === jwk.x && k.y === jwk.y);
      if (match?.kid) kid = match.kid;
    }
  } catch (_) { /* 抓不到就用 JWK 裡的 kid */ }
  if (!kid) throw new Error('找不到金鑰的 kid，請確認已把公鑰匯入 Supabase');

  keyCache = { key, kid };
  return keyCache;
}

async function signJwt(env, payload) {
  const { key, kid } = await getSigningKey(env);
  const header = { alg: 'ES256', typ: 'JWT', kid };
  const input = `${b64url(JSON.stringify(header))}.${b64url(JSON.stringify(payload))}`;
  const sig = await crypto.subtle.sign({ name: 'ECDSA', hash: 'SHA-256' }, key, new TextEncoder().encode(input));
  return `${input}.${b64url(sig)}`; // WebCrypto 的 ECDSA 簽章本來就是 JWS 要的 r||s 格式
}

export default {
  async fetch(request, env) {
    const origin = request.headers.get('Origin') || '';
    if (request.method === 'OPTIONS') return new Response(null, { status: 204, headers: corsHeaders(origin) });

    const url = new URL(request.url);
    if (request.method !== 'POST' || url.pathname !== '/auth/line') {
      return json({ ok: false, message: 'Not found' }, 404, origin);
    }
    if (!ALLOWED_ORIGINS.includes(origin)) return json({ ok: false, message: '來源不允許' }, 403, origin);
    if (!env.LINE_CHANNEL_ID || !env.SUPABASE_URL || !env.SUPABASE_JWT_PRIVATE_KEY) {
      return json({ ok: false, message: 'Worker 尚未設定完成' }, 500, origin);
    }

    try {
      const { idToken } = await request.json();
      if (!idToken || typeof idToken !== 'string' || idToken.length > 4096) {
        return json({ ok: false, message: '缺少 LINE 登入憑證' }, 400, origin);
      }

      // 1. 向 LINE 驗證 ID token（同時檢查簽章、到期時間、是不是發給我們的頻道）
      const verify = await fetch('https://api.line.me/oauth2/v2.1/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ id_token: idToken, client_id: env.LINE_CHANNEL_ID }),
      });
      const profile = await verify.json();
      if (!verify.ok || !profile.sub) {
        return json({ ok: false, message: 'LINE 登入已過期，請重新登入', detail: profile.error_description }, 401, origin);
      }

      // 2. 簽發 Supabase JWT
      const now = Math.floor(Date.now() / 1000);
      const accessToken = await signJwt(env, {
        iss: new URL(request.url).origin,
        sub: profile.sub,
        aud: 'authenticated',
        role: 'authenticated',
        iat: now,
        exp: now + TOKEN_TTL_SECONDS,
      });

      return json({
        ok: true,
        access_token: accessToken,
        expires_at: now + TOKEN_TTL_SECONDS,
        profile: { name: profile.name || '', picture: profile.picture || '' },
      }, 200, origin);
    } catch (err) {
      return json({ ok: false, message: '系統錯誤：' + err.message }, 500, origin);
    }
  },
};
