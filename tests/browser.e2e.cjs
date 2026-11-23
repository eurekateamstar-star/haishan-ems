const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
(async () => {
  const { SignJWT, importJWK } = await import('jose');
  const key = await importJWK(JSON.parse(fs.readFileSync('priv.json')), 'ES256');
  const vue = fs.readFileSync('node_modules/vue/dist/vue.global.prod.js', 'utf8');
  const sbjs = fs.readFileSync('supabase.esm.js', 'utf8');
  const browser = await chromium.launch();
  const results = [];
  const ok = (c, m) => { results.push((c ? '✅ ' : '❌ ') + m); };

  async function open(sub) {
    const ctx = await browser.newContext({ viewport: { width: 420, height: 900 } });
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', e => errors.push('pageerror: ' + e.message));
    page.on('console', m => { if (m.type() === 'error') errors.push('console: ' + m.text()); });
    await page.addInitScript((s) => { window.__SUB = s; }, sub);
    await page.route('**/*', async (route) => {
      const url = route.request().url();
      if (url.includes('unpkg.com/vue')) return route.fulfill({ body: vue, contentType: 'application/javascript' });
      if (url.includes('cdn.jsdelivr.net/npm/@supabase')) return route.fulfill({ body: sbjs, contentType: 'application/javascript' });
      if (url.includes('static.line-scdn.net/liff')) return route.fulfill({ contentType: 'application/javascript', body:
        `window.liff={init:async()=>{},isLoggedIn:()=>true,getIDToken:()=>'id-'+window.__SUB,getProfile:async()=>({displayName:'LINE使用者',pictureUrl:''}),login(){},logout(){}};` });
      if (url.endsWith('/auth/line')) {
        const { idToken } = JSON.parse(route.request().postData());
        const t = await new SignJWT({ role: 'authenticated' }).setProtectedHeader({ alg: 'ES256', kid: 'k1' })
          .setSubject(idToken.replace(/^id-/, '')).setAudience('authenticated').setIssuedAt().setExpirationTime('1h').sign(key);
        return route.fulfill({ contentType: 'application/json', body: JSON.stringify({ ok: true, access_token: t, expires_at: Math.floor(Date.now()/1000)+3600, profile: { name: 'LINE使用者', picture: '' } }) });
      }
      if (url.startsWith('https://avyexuqgddrpvcwaddaa.supabase.co/')) {
        const r = await route.fetch({ url: url.replace('https://avyexuqgddrpvcwaddaa.supabase.co', 'http://localhost:3002') });
        return route.fulfill({ response: r, headers: { ...r.headers(), 'access-control-allow-origin': '*' } });
      }
      if (url.startsWith('http://localhost:8088/')) return route.continue();
      return route.fulfill({ status: 200, body: '' }); // tailwind、字型等外部資源略過
    });
    await page.goto('http://localhost:8088/index.html');
    return { page, ctx, errors };
  }

  // ---- A. 新使用者綁定
  {
    const { page, ctx, errors } = await open('U_new');
    await page.waitForSelector('text=第一次使用', { timeout: 15000 });
    ok(true, 'A1 未綁定的 LINE 帳號看到綁定畫面');
    await page.selectOption('select >> nth=0', { label: '海山' });
    await page.waitForFunction(() => [...document.querySelectorAll('select')[1].options].some(o => o.text.includes('郭允昊')));
    const names = await page.$$eval('select >> nth=1', s => [...s[0].options].map(o => o.text));
    ok(names.some(n => n.includes('郭允昊')) && !names.some(n => n.includes('王佩瑾')), 'A2 只列出未綁定的人：' + names.slice(1).join('、'));
    await page.selectOption('select >> nth=1', { index: 1 });
    await page.fill('input[type=date]', '1998-01-01');
    await page.click('text=驗證並綁定');
    await page.waitForSelector('text=生日不正確', { timeout: 10000 });
    ok(true, 'A3 生日錯誤被擋下');
    await page.evaluate(() => { const b = [...document.querySelectorAll('button')].find(b => /確定|知道|關閉|OK/.test(b.textContent)); b && b.click(); });
    await page.fill('input[type=date]', '1998-08-08');
    await page.click('text=驗證並綁定');
    await page.waitForFunction(() => document.querySelector('header')?.textContent.includes('郭允昊'), null, { timeout: 15000 });
    ok(true, 'A4 生日正確，綁定後進入首頁，頁首顯示郭允昊');
    ok(errors.length === 0, 'A5 沒有程式錯誤' + (errors.length ? '：' + errors.slice(0, 3).join(' | ') : ''));
    await ctx.close();
  }

  // ---- B. 已綁定隊員
  {
    const { page, ctx, errors } = await open('U_member');
    await page.waitForFunction(() => document.querySelector('header')?.textContent.includes('王佩瑾'), null, { timeout: 15000 });
    const head = await page.innerText('header');
    ok(head.includes('海山分隊'), 'B1 已綁定直接進入，頁首顯示「海山分隊」與王佩瑾');
    await page.click('nav >> text=排班');
    await page.waitForTimeout(800);
    const body1 = await page.innerText('body');
    ok(body1.includes('王佩瑾') && /17\s*-\s*21/.test(body1), 'B2 排班頁看到自己的班 17-21');
    ok(body1.includes('耶誕城開城'), 'B3 看得到海山的公差「耶誕城開城」');
    await page.click('nav >> text=協勤');
    await page.waitForTimeout(800);
    const body2 = await page.innerText('body');
    ok(!body2.includes('全隊紀錄'), 'B4 一般隊員看不到「全隊紀錄」（和舊平台相同，只給幹部）');
    const navText = await page.innerText('nav');
    ok(!navText.includes('常訓') && !navText.includes('考核') && navText.includes('首頁'), 'B5 底部只剩首頁、排班、協勤');
    ok(errors.length === 0, 'B6 沒有程式錯誤' + (errors.length ? '：' + errors.slice(0, 3).join(' | ') : ''));
    await ctx.close();
  }

  // ---- D. 海山幹部
  {
    const { page, ctx, errors } = await open('U_admin');
    await page.waitForFunction(() => document.querySelector('header')?.innerText.includes('劉奕昕'), null, { timeout: 15000 });
    await page.click('nav >> text=協勤'); await page.waitForTimeout(800);
    await page.click('text=全隊紀錄'); await page.waitForTimeout(800);
    const body = await page.innerText('body');
    ok(body.includes('中正路433巷23號3樓') && body.includes('OHCA'), 'D1 幹部的全隊紀錄看得到協勤案件');
    await page.click('text=時數排名'); await page.waitForTimeout(800);
    const rank = await page.innerText('body');
    ok(rank.includes('劉奕昕') && /\b5\b/.test(rank), 'D2 時數排名有劉奕昕 5 小時');
    await page.click('nav >> text=排班'); await page.waitForTimeout(600);
    await page.click('text=主控台').catch(() => {}); await page.waitForTimeout(800);
    const panel = await page.innerText('body');
    ok(panel.includes('郭允昊') && panel.includes('王佩瑾'), 'D3 主控台列出海山隊員');
    ok(errors.length === 0, 'D4 沒有程式錯誤' + (errors.length ? '：' + errors.slice(0, 3).join(' | ') : ''));
    await ctx.close();
  }

  // ---- C. 板橋幹部看不到海山
  {
    const { page, ctx, errors } = await open('U_bq');
    await page.waitForFunction(() => document.querySelector('header')?.textContent.includes('板橋甲'), null, { timeout: 15000 });
    await page.click('nav >> text=排班'); await page.waitForTimeout(800);
    const body = await page.innerText('body');
    ok(!body.includes('耶誕城開城') && !body.includes('王佩瑾'), 'C1 板橋分隊看不到海山的公差與隊員');
    ok(errors.length === 0, 'C2 沒有程式錯誤' + (errors.length ? '：' + errors.slice(0, 3).join(' | ') : ''));
    await ctx.close();
  }
  console.log(results.join('\n'));
  await browser.close();
})().catch(e => { console.error('TEST CRASH', e); process.exit(1); });
