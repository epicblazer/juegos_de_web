// Exporta las hojas de sprites de los jefes que el juego dibuja por código: sprites/jefe_<nombre>.png
// Abre el juego en Chrome/Edge sin ventana y llama a exportarHojaJefe() de isaac_verde.html.
// Uso:  node sprites/exportar_jefes.js            (todos)
//       node sprites/exportar_jefes.js sans       (sólo uno)
const { spawn } = require('child_process');
const fs = require('fs'), path = require('path'), os = require('os');

const DIR = __dirname, GAME = path.join(DIR, '..', 'isaac_verde.html');
const JEFES = { gurdy: 'gurdy', peep: 'peep', widow: 'viuda', momFoot: 'pie_mama', satan: 'satanas', kingSlime: 'rey_slime',
  kingBoo: 'rey_boo', mothership: 'nave_nodriza', ridley: 'ridley', wither: 'wither', ganon: 'ganon', sans: 'sans' };
const PORT = 9335;

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

(async () => {
  const only = process.argv[2], types = only ? [only] : Object.keys(JEFES);
  if (types.some(t => !JEFES[t])) throw new Error('Jefes válidos: ' + Object.keys(JEFES).join(', '));
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'exportar-'));
  const browser = spawn(findBrowser(), ['--headless=new', `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`,
    '--allow-file-access-from-files', '--window-size=960,576', '--force-device-scale-factor=1', 'about:blank'], { stdio: 'ignore' });
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
    await sleep(1200);
    for (const type of types) {
      const url = await evaluate(cdp, `exportarHojaJefe(${JSON.stringify(type)})`);
      const out = path.join(DIR, `jefe_${JEFES[type]}.png`);
      fs.writeFileSync(out, Buffer.from(url.split(',')[1], 'base64'));
      console.log('listo → sprites/' + path.basename(out));
    }
    cdp.close();
  } finally {
    browser.kill();
    await sleep(500);
    try { fs.rmSync(profile, { recursive: true, force: true }); } catch {}
  }
})().catch(e => { console.error(e.message || e); process.exit(1); });
