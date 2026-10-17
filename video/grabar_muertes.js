// Graba en esta carpeta la cinemática de muerte de cada jefe: muerte_<jefe>.mp4
// Abre el juego en Chrome/Edge sin ventana, llama a grabarMuerte() de isaac_verde.html y convierte con ffmpeg.
// Uso:  node video/grabar_muertes.js            (todos los jefes)
//       node video/grabar_muertes.js koopa      (sólo uno)
// Necesita Google Chrome o Microsoft Edge, y ffmpeg (en el PATH o con: pip install imageio-ffmpeg)
const { spawn, execFileSync } = require('child_process');
const fs = require('fs'), path = require('path'), os = require('os');

const DIR = __dirname, GAME = path.join(DIR, '..', 'isaac_verde.html');
const JEFES = { monstro: 'monstro', dukeFlies: 'duque_moscas', darkIsaac: 'isaac_oscuro', koopa: 'rey_koopa',
  dragon: 'dragon_fin', eggman: 'dr_huevon', ghostKing: 'rey_fantasma', brain: 'cerebro_madre',
  gurdy: 'gurdy', peep: 'peep', widow: 'viuda', momFoot: 'pie_mama', satan: 'satanas', kingSlime: 'rey_slime',
  kingBoo: 'rey_boo', mothership: 'nave_nodriza', ridley: 'ridley', wither: 'wither', ganon: 'ganon', sans: 'sans',
  baldi: 'baldi', fetus: 'dr_fetus', devil: 'diablo' };
const PORT = 9333;

function findBrowser() {
  const list = ['C:/Program Files/Google/Chrome/Application/chrome.exe', 'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', 'C:/Program Files/Microsoft/Edge/Application/msedge.exe'];
  const b = list.find(f => fs.existsSync(f));
  if (!b) throw new Error('No encontré Chrome ni Edge');
  return b;
}
function findFfmpeg() {
  try { execFileSync('ffmpeg', ['-version'], { stdio: 'ignore' }); return 'ffmpeg'; } catch {}
  return execFileSync('python', ['-c', 'import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())']).toString().trim();
}
const sleep = ms => new Promise(r => setTimeout(r, ms));

// cliente mínimo del protocolo de DevTools
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
  const ffmpeg = findFfmpeg(), profile = fs.mkdtempSync(path.join(os.tmpdir(), 'grabar-'));
  const browser = spawn(findBrowser(), ['--headless=new', `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`,
    '--autoplay-policy=no-user-gesture-required', '--allow-file-access-from-files', '--window-size=960,576',
    '--force-device-scale-factor=1', '--disable-background-timer-throttling', '--disable-renderer-backgrounding',
    '--disable-backgrounding-occluded-windows', 'about:blank'], { stdio: 'ignore' });
  try {
    let page;
    for (let i = 0; i < 50 && !page; i++) {
      await sleep(200);
      try { page = (await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json()).find(t => t.type === 'page'); } catch {}
    }
    if (!page) throw new Error('El navegador no respondió');
    const cdp = await connect(page.webSocketDebuggerUrl);
    await cdp.send('Runtime.enable');
    for (const type of types) {
      await cdp.send('Page.navigate', { url: 'file:///' + GAME.replace(/\\/g, '/') });
      await sleep(500);
      await evaluate(cdp, `new Promise(r => { const f = () => typeof SPR !== 'undefined' && Object.keys(SPR).length >= Object.keys(SPRITE_FILES).length ? r(true) : setTimeout(f, 100); f(); })`);
      process.stdout.write(`Grabando ${JEFES[type]}... `);
      // se lanza la grabación y se va preguntando; el video se trae en pedazos
      await evaluate(cdp, `window.__rec = null; grabarMuerte(${JSON.stringify(type)}).then(s => window.__rec = s, e => window.__rec = 'ERROR ' + e); true`);
      let len = 0;
      for (let i = 0; i < 120 && !len; i++) { await sleep(500); len = await evaluate(cdp, `window.__rec ? window.__rec.length : 0`); }
      if (!len) throw new Error('la grabación no terminó');
      let b64 = '';
      for (let i = 0; i < len; i += 1 << 20) b64 += await evaluate(cdp, `window.__rec.slice(${i}, ${i + (1 << 20)})`);
      if (b64.startsWith('ERROR')) throw new Error(b64);
      const webm = path.join(profile, type + '.webm'), mp4 = path.join(DIR, `muerte_${JEFES[type]}.mp4`);
      fs.writeFileSync(webm, Buffer.from(b64, 'base64'));
      execFileSync(ffmpeg, ['-y', '-loglevel', 'error', '-i', webm, '-r', '60', '-c:v', 'libx264', '-preset', 'slow', '-crf', '18',
        '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', mp4]);
      console.log('listo → ' + path.relative(path.join(DIR, '..'), mp4));
    }
    cdp.close();
  } finally {
    browser.kill();
    await sleep(500);
    try { fs.rmSync(profile, { recursive: true, force: true }); } catch {}
  }
})().catch(e => { console.error(e.message || e); process.exit(1); });
