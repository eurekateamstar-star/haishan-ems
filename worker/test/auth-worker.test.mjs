import w from '../auth-worker.js';
import { jwtVerify, importJWK } from 'jose';
const kp = await crypto.subtle.generateKey({ name: 'ECDSA', namedCurve: 'P-256' }, true, ['sign', 'verify']);
const priv = await crypto.subtle.exportKey('jwk', kp.privateKey);
const pub = await crypto.subtle.exportKey('jwk', kp.publicKey);
globalThis.fetch = async (url, o) => {
  if (url.includes('jwks.json')) return new Response(JSON.stringify({ keys: [{ ...pub, kid: 'supabase-kid-123', alg: 'ES256' }] }));
  if (url.includes('api.line.me')) {
    const p = new URLSearchParams(o.body);
    if (p.get('id_token') !== 'good' || p.get('client_id') !== '2009000000') return new Response(JSON.stringify({ error: 'invalid_request', error_description: 'IdToken expired.' }), { status: 400 });
    return new Response(JSON.stringify({ sub: 'U1234', name: '劉奕昕', picture: 'https://p' }));
  }
};
const env = { LINE_CHANNEL_ID: '2009000000', SUPABASE_URL: 'https://x.supabase.co', SUPABASE_JWT_PRIVATE_KEY: JSON.stringify(priv) };
const call = (body, origin = 'https://eurekateamstar-star.github.io', path = '/auth/line') =>
  w.fetch(new Request('https://auth.example.workers.dev' + path, { method: 'POST', headers: { Origin: origin }, body: JSON.stringify(body) }), env);
let r = await call({ idToken: 'good' }); let j = await r.json();
console.log('good:', r.status, j.ok, j.profile);
const { payload, protectedHeader } = await jwtVerify(j.access_token, await importJWK({ ...pub, alg: 'ES256' }), { audience: 'authenticated' });
console.log('verified header:', protectedHeader, 'payload:', payload.sub, payload.role, payload.exp - payload.iat);
r = await call({ idToken: 'expired' }); console.log('expired:', r.status, (await r.json()).message);
r = await call({ idToken: 'good' }, 'https://evil.example'); console.log('bad origin:', r.status);
r = await call({ idToken: 'good' }, undefined, '/other'); console.log('bad path:', r.status);
