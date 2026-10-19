// Exporta los dibujos de todos los objetos del juego (normales, del Diablo y del Ángel) a videos_publisidad/recursos/objetos/
// Uso: node videos_publisidad/exportar_objetos.js
const { spawn } = require('child_process');
const fs = require('fs'), path = require('path'), os = require('os');

const DIR = path.join(__dirname, 'recursos', 'objetos'), GAME = path.join(__dirname, '..', 'isaac_verde.html');
const PORT = 9336;
function findBrowser() {
  const list = ['C:/Program Files/Google/Chrome/Application/chrome.exe', 'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', 'C:/Program Files/Microsoft/Edge/Application/msedge.exe'];
  const b = list.find(f => fs.existsSync(f));
  if (!b) throw new Error('No encontré Chrome ni Edge');
  return b;
}
const sleep = ms => new Promise(r => setTimeout(r, ms));
function connect(url) {
  const ws = new WebSocket(url), pending = new Map();
  let id = 0;
  ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
  const send = (method, params = {}) => new Promise(r => { pending.set(++id, r); ws.send(JSON.stringify({ id, method, params })); });
  return new Promise(r => ws.onopen = () => r({ send, close: () => ws.close() }));
}
async function evaluate(cdp, expression) {
  const m = await cdp.send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
  if (m.error || m.result.exceptionDetails) throw new Error(JSON.stringify(m.error || m.result.exceptionDetails));
  return m.result.result.value;
}
// dibuja cada objeto en grande (escala 8) en un lienzo aparte usando drawItemIcon del juego
const EXPORT = `(() => {
  const out = [], old = ctx;
  for (const [kind, list] of [['normal', ITEMS], ['diablo', DEVIL_ITEMS], ['angel', ANGEL_ITEMS]]) for (const it of list) {
    const c = document.createElement('canvas'); c.width = c.height = 320;
    ctx = c.getContext('2d');
    drawItemIcon(it.name, 160, 160, 8);
    out.push({ name: it.name, desc: it.desc, kind, color: it.color, png: c.toDataURL('image/png') });
  }
  ctx = old;
  return out;
})()`;

(async () => {
  fs.mkdirSync(DIR, { recursive: true });
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'objetos-'));
  const browser = spawn(findBrowser(), ['--headless=new', `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`,
    '--allow-file-access-from-files', '--window-size=960,576', 'about:blank'], { stdio: 'ignore' });
  try {
    let page;
    for (let i = 0; i < 50 && !page; i++) {
      await sleep(200);
      try { page = (await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json()).find(t => t.type === 'page'); } catch {}
    }
    if (!page) throw new Error('El navegador no respondió');
    const cdp = await connect(page.webSocketDebuggerUrl);
    await cdp.send('Runtime.enable');
    await cdp.send('Page.navigate', { url: 'file:///' + GAME.replace(/\\/g, '/') });
    await sleep(1500);
    const items = await evaluate(cdp, EXPORT);
    const lista = items.map((it, i) => {
      const file = `objeto_${String(i).padStart(2, '0')}.png`;
      fs.writeFileSync(path.join(DIR, file), Buffer.from(it.png.split(',')[1], 'base64'));
      return { file, name: it.name, desc: it.desc, kind: it.kind, color: it.color };
    });
    fs.writeFileSync(path.join(DIR, 'objetos.json'), JSON.stringify(lista, null, 2));
    console.log(`listo → ${lista.length} objetos en videos_publisidad/recursos/objetos/`);
    cdp.close();
  } finally {
    browser.kill();
    await sleep(500);
    try { fs.rmSync(profile, { recursive: true, force: true }); } catch {}
  }
})().catch(e => { console.error(e.message || e); process.exit(1); });
