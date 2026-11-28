const { chromium } = require('playwright'); const fs = require('fs');
(async () => {
  const { SignJWT, importJWK } = await import('jose');
  const key = await importJWK(JSON.parse(fs.readFileSync('priv.json')), 'ES256');
  const vue = fs.readFileSync('node_modules/vue/dist/vue.global.prod.js', 'utf8');
  const sbjs = fs.readFileSync('supabase.esm.js', 'utf8');
  const tw = fs.readFileSync('node_modules/@tailwindcss/browser/dist/index.global.js', 'utf8');
  const pdfjs = fs.readFileSync('node_modules/pdfjs-dist/build/pdf.min.js', 'utf8');
  const pdfw = fs.readFileSync('node_modules/pdfjs-dist/build/pdf.worker.min.js', 'utf8');
  const medpdf = fs.readFileSync('med_test.pdf');
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 420, height: 900 }, hasTouch: true });
  const page = await ctx.newPage(); const errors = []; const hits = [];
  page.on('pageerror', e => errors.push('pageerror: ' + e.message));
  page.on('console', m => { if (m.type() === 'error') errors.push('console: ' + m.text()); });
  await page.route('**/*', async (route) => {
    const url = route.request().url();
    if (url.includes('cdn.tailwindcss.com')) return route.fulfill({ body: tw, contentType: 'application/javascript' });
    if (url.includes('unpkg.com/vue')) return route.fulfill({ body: vue, contentType: 'application/javascript' });
    if (url.includes('cdn.jsdelivr.net/npm/@supabase')) return route.fulfill({ body: sbjs, contentType: 'application/javascript' });
    if (url.includes('pdf.worker.min.js')) return route.fulfill({ body: pdfw, contentType: 'application/javascript', headers: { 'access-control-allow-origin': '*' } });
    if (url.includes('pdf.min.js')) return route.fulfill({ body: pdfjs, contentType: 'application/javascript' });
    if (url.includes('firebasestorage.googleapis.com')) { hits.push(url); return route.fulfill({ body: medpdf, contentType: 'application/pdf', headers: { 'access-control-allow-origin': '*' } }); }
    if (url.includes('ebook.nfa.gov.tw')) { hits.push(url); return route.fulfill({ status: 200, body: '' }); }
    if (url.includes('static.line-scdn.net/liff')) return route.fulfill({ contentType: 'application/javascript', body:
      `window.liff={init:async()=>{},isLoggedIn:()=>true,getIDToken:()=>'id-U_admin_haishan',getProfile:async()=>({displayName:'LINE使用者',pictureUrl:''}),login(){},logout(){}};` });
    if (url.endsWith('/auth/line')) {
      const t = await new SignJWT({ role: 'authenticated' }).setProtectedHeader({ alg: 'ES256', kid: 'k1' }).setSubject('U_admin_haishan').setAudience('authenticated').setIssuedAt().setExpirationTime('1h').sign(key);
      return route.fulfill({ contentType: 'application/json', body: JSON.stringify({ ok: true, access_token: t, expires_at: Math.floor(Date.now()/1000)+3600, profile: { name: 'LINE使用者', picture: '' } }) });
    }
    if (url.startsWith('https://avyexuqgddrpvcwaddaa.supabase.co/')) {
      const r = await route.fetch({ url: url.replace('https://avyexuqgddrpvcwaddaa.supabase.co', 'http://localhost:3002') });
      return route.fulfill({ response: r, headers: { ...r.headers(), 'access-control-allow-origin': '*' } });
    }
    if (url.startsWith('http://localhost:8088/')) return route.continue();
    return route.fulfill({ status: 200, body: '' });
  });
  const R = (c, m) => console.log((c ? '✅ ' : '❌ ') + m);
  await page.goto('http://localhost:8088/index.html');
  await page.waitForFunction(() => document.querySelector('header')?.innerText.includes('劉奕昕'), null, { timeout: 20000 });
  const navTxt = await page.innerText('nav');
  R(/首頁[\s\S]*排班[\s\S]*協勤[\s\S]*救護/.test(navTxt) && !navTxt.includes('常訓') && !navTxt.includes('考核'), '底部導覽：首頁 / 排班 / 協勤 / 救護，沒有常訓、考核');
  await page.click('nav >> text=救護'); await page.waitForTimeout(800);
  let body = await page.innerText('main, body');
  R(body.includes('救護手冊') && body.includes('單項技術') && body.includes('藥物小卡') && !body.includes('常訓資料'), '救護頁只有三個內頁，沒有常訓資料');
  R(body.includes('內政部消防署') && await page.locator('a[href*="1140527"]').isVisible(), '預設打開救護手冊（消防署電子書 1140527）');
  await page.screenshot({ path: '/tmp/r1.png' });
  await page.click('.tab-item >> text=單項技術'); await page.waitForTimeout(400);
  R(await page.locator('a[href*="1140526"]').isVisible(), '單項技術顯示消防署電子書 1140526');
  await page.screenshot({ path: '/tmp/r2.png' });
  await page.click('.tab-item >> text=藥物小卡');
  await page.waitForFunction(() => document.querySelectorAll('canvas[id^=med-canvas-]').length === 3, null, { timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(1500);
  const drawn = await page.evaluate(() => [...document.querySelectorAll('canvas[id^=med-canvas-]')].map(c => { const d = c.getContext('2d').getImageData(c.width/2|0, c.height/2|0, 1, 1).data; return c.width > 0 && (d[0] + d[1] + d[2]) > 0; }));
  R(drawn.length === 3 && drawn.every(Boolean), '藥物小卡 3 頁都畫出來（本機沒有 PDF 時改讀 Firebase Storage）');
  body = await page.innerText('body'); R(body.includes('1 / 3'), '頁碼顯示 1 / 3');
  await page.screenshot({ path: '/tmp/r3.png' });
  await page.evaluate(() => { const s = document.querySelector('.pdf-slider'); s.scrollLeft = s.offsetWidth; }); await page.waitForTimeout(500);
  R((await page.innerText('body')).includes('2 / 3'), '左右滑動翻頁，頁碼變 2 / 3');
  await page.click('nav >> text=首頁'); await page.waitForTimeout(500); await page.click('nav >> text=救護'); await page.waitForTimeout(500);
  await page.click('.tab-item >> text=藥物小卡'); await page.waitForTimeout(1500);
  const redrawn = await page.evaluate(() => [...document.querySelectorAll('canvas[id^=med-canvas-]')].filter(c => c.width > 0).length);
  R(redrawn === 3 && hits.filter(h => h.includes('firebasestorage')).length === 1, '離開再回來會重畫，PDF 只下載一次');
  await page.goto('http://localhost:8088/index.html?page=rescue'); await page.waitForTimeout(4000);
  R(await page.locator('a[href*="1140527"]').isVisible(), '?page=rescue 直接打開救護頁');
  R(errors.filter(e => !/404|Failed to load resource/.test(e)).length === 0, '沒有程式錯誤' + (errors.length ? '：' + errors.slice(0, 4).join(' | ') : ''));
  await browser.close();
})().catch(e => { console.log('TEST CRASH', e); process.exit(1); });
