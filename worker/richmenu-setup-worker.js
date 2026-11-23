// =====================================================================
// 一次性工具：設定「新北市救護義消」官方帳號的圖文選單
//
// 使用方式：
//   1. Cloudflare 建一個 Worker（例如 ems-richmenu），貼上這份程式，Deploy
//   2. 設定 → 變數和機密 → 新增「機密 (Secret)」LINE_TOKEN
//      = 新北市救護義消（Messaging API 頻道）的 Channel access token
//   3. 用瀏覽器打開  https://<worker 網址>/?confirm=yes
//   4. 看到「完成」就好；之後可以把這個 Worker 刪掉
// =====================================================================

const LIFF = 'https://liff.line.me/2012765865-adJrZdwg';
const IMAGE_URL = 'https://raw.githubusercontent.com/eurekateamstar-star/haishan-ems/main/assets/richmenu.png';
const MENU_NAME = 'ems-system-menu';

const richMenu = {
  size: { width: 2500, height: 843 },
  selected: true,               // 預設展開
  name: MENU_NAME,
  chatBarText: '開啟系統',
  areas: [
    { bounds: { x: 0,    y: 0, width: 833, height: 843 }, action: { type: 'uri', label: '首頁', uri: LIFF } },
    { bounds: { x: 833,  y: 0, width: 834, height: 843 }, action: { type: 'uri', label: '排班', uri: LIFF + '?page=schedule' } },
    { bounds: { x: 1667, y: 0, width: 833, height: 843 }, action: { type: 'uri', label: '協勤', uri: LIFF + '?page=assistance' } },
  ],
};

const page = (title, lines, ok) => new Response(
  `<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
   <title>${title}</title><body style="font-family:system-ui,sans-serif;padding:24px;line-height:1.7;max-width:640px;margin:auto">
   <h2 style="color:${ok ? '#059669' : '#b91c1c'}">${title}</h2><pre style="white-space:pre-wrap;background:#f1f5f9;padding:12px;border-radius:8px">${
     lines.map((l) => String(l).replace(/[<&]/g, (c) => ({ '<': '&lt;', '&': '&amp;' }[c]))).join('\n')}</pre></body>`,
  { status: ok ? 200 : 500, headers: { 'Content-Type': 'text/html; charset=utf-8' } });

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.searchParams.get('confirm') !== 'yes') {
      return page('圖文選單設定工具', ['網址後面加上 ?confirm=yes 才會執行。'], true);
    }
    if (!env.LINE_TOKEN) return page('尚未設定 LINE_TOKEN', ['請先在 Worker 的「變數和機密」新增機密 LINE_TOKEN。'], false);

    const log = [];
    const auth = { Authorization: `Bearer ${env.LINE_TOKEN}` };
    const call = async (method, u, body, headers = {}) => {
      const res = await fetch(u, { method, headers: { ...auth, ...headers }, body });
      const text = await res.text();
      if (!res.ok) throw new Error(`${method} ${u.replace('https://', '')} → ${res.status} ${text.slice(0, 300)}`);
      return text ? JSON.parse(text) : {};
    };

    try {
      // 1. 先刪掉這個工具以前建的同名選單（重跑也不會越積越多）
      const { richmenus = [] } = await call('GET', 'https://api.line.me/v2/bot/richmenu/list');
      for (const m of richmenus.filter((m) => m.name === MENU_NAME)) {
        await call('DELETE', `https://api.line.me/v2/bot/richmenu/${m.richMenuId}`);
        log.push('刪除舊選單 ' + m.richMenuId);
      }

      // 2. 建立選單
      const { richMenuId } = await call('POST', 'https://api.line.me/v2/bot/richmenu',
        JSON.stringify(richMenu), { 'Content-Type': 'application/json' });
      log.push('建立選單 ' + richMenuId);

      // 3. 上傳圖片
      const img = await fetch(IMAGE_URL);
      if (!img.ok) throw new Error('下載選單圖片失敗：' + img.status);
      await call('POST', `https://api-data.line.me/v2/bot/richmenu/${richMenuId}/content`,
        await img.arrayBuffer(), { 'Content-Type': 'image/png' });
      log.push('上傳圖片完成');

      // 4. 設為所有好友的預設選單
      await call('POST', `https://api.line.me/v2/bot/user/all/richmenu/${richMenuId}`);
      log.push('已設為預設選單');

      return page('✅ 完成', [...log, '', '回到 LINE 聊天室，關掉再重開，就會看到底部選單。', '這個 Worker 之後可以刪掉。'], true);
    } catch (e) {
      return page('❌ 設定失敗', [...log, '', e.message], false);
    }
  },
};
