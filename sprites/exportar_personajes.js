// Exporta las hojas de sprites de todos los personajes elegibles: sprites/personajes/<nombre>_{movimiento,disparo,dano_muerte}.png (+ .json)
// Mismo formato que las hojas de Isaac (isaac_movimiento.png, etc.). Abre el juego en Chrome/Edge sin ventana y llama a exportarHojasPersonaje().
// Uso:  node sprites/exportar_personajes.js            (todos menos Isaac Soldado, que ya tiene las suyas)
//       node sprites/exportar_personajes.js judas      (sólo uno)
const { spawn } = require('child_process');
const fs = require('fs'), path = require('path'), os = require('os');

const DIR = path.join(__dirname, 'personajes'), GAME = path.join(__dirname, '..', 'isaac_verde.html');
const PORT = 9336;
const slug = n => n.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '');

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
const anim = (rows, frames, fps, loop) => Object.fromEntries(rows.map((n, i) => [n, { row: i, frames: frames[i] ?? frames[0], fps: fps[i] ?? fps[0], loop: loop[i] ?? loop[0] }]));
const SHEETS = {
  movimiento: { key: 'move', columns: 8, rows: 8, animations: anim(['idle_down', 'idle_up', 'idle_left', 'idle_right', 'walk_down', 'walk_up', 'walk_left', 'walk_right'],
    [4, 4, 4, 4, 8, 8, 8, 8], [6, 6, 6, 6, 12, 12, 12, 12], [true]) },
  disparo: { key: 'shoot', columns: 6, rows: 6, fireFrame: 2, animations: anim(['shoot_down', 'shoot_up', 'shoot_left', 'shoot_right', 'tear', 'tear_splash'],
    [6, 6, 6, 6, 4, 6], [18, 18, 18, 18, 10, 20], [false, false, false, false, true, false]) },
  dano_muerte: { key: 'hurt', columns: 10, rows: 5, animations: anim(['hurt_down', 'hurt_up', 'hurt_left', 'hurt_right', 'death'],
    [4, 4, 4, 4, 10], [14, 14, 14, 14, 8], [false]) },
};

(async () => {
  const only = process.argv[2];
  fs.mkdirSync(DIR, { recursive: true });
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'personajes-'));
  const browser = spawn(findBrowser(), ['--headless=new', `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`,
    '--allow-file-access-from-files', '--force-device-scale-factor=1', 'about:blank'], { stdio: 'ignore' });
  try {
    let page;
    for (let i = 0; i < 50 && !page; i++) {
      await sleep(200);
      try { page = (await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json()).find(t => t.type === 'page'); } catch {}
    }
    if (!page) throw new Error('El navegador no respondió');
    const cdp = await connect(page.webSocketDebuggerUrl);
    await cdp.send('Runtime.enable');
    await cdp.send('Page.navigate', { url: 'file:///' + GAME.split(path.sep).join('/') });
    await sleep(1500);
    const chars = await evaluate(cdp, `CHARS.map(c => ({ name: c.name, ref: c.ref, tear: c.tear || 'tear' }))`);
    const list = chars.map((c, i) => ({ ...c, i, file: slug(c.name) })).filter(c => only ? c.file.includes(slug(only)) : c.i > 0);
    if (!list.length) throw new Error('No hay personaje que se llame así. Personajes: ' + chars.map(c => slug(c.name)).join(', '));
    const index = [];
    for (const c of list) {
      await evaluate(cdp, `(window.__h = exportarHojasPersonaje(${c.i}), true)`);
      for (const [suf, sp] of Object.entries(SHEETS)) {
        const len = await evaluate(cdp, `__h.${sp.key}.length`);
        let b64 = '';
        for (let i = 0; i < len; i += 1 << 20) b64 += await evaluate(cdp, `__h.${sp.key}.slice(${i}, ${i + (1 << 20)})`);
        const img = `${c.file}_${suf}.png`;
        fs.writeFileSync(path.join(DIR, img), Buffer.from(b64.split(',')[1], 'base64'));
        const json = { image: img, character: c.name, homenaje: c.ref, frameWidth: 160, frameHeight: 160, columns: sp.columns, rows: sp.rows,
          pivot: { x: 80, y: 150, note: 'punto de los pies dentro de cada cuadro' }, ...(sp.fireFrame ? { fireFrame: sp.fireFrame, projectile: c.tear } : {}), animations: sp.animations };
        fs.writeFileSync(path.join(DIR, `${c.file}_${suf}.json`), JSON.stringify(json, null, 2));
      }
      index.push({ name: c.name, file: c.file, projectile: c.tear });
      console.log('listo → sprites/personajes/' + c.file + '_*.png');
    }
    if (!only) fs.writeFileSync(path.join(DIR, 'personajes.json'), JSON.stringify(index, null, 2));
    cdp.close();
  } finally {
    browser.kill();
    await sleep(500);
    try { fs.rmSync(profile, { recursive: true, force: true }); } catch {}
  }
})().catch(e => { console.error(e.message || e); process.exit(1); });
