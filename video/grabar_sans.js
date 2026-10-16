// Graba la pelea contra Sans (estilo Undertale) jugada por un bot: video/pelea_sans.mp4
// Abre el juego en Chrome/Edge sin ventana, entra al cuarto del jefe con Sans y un bot esquiva los ataques.
// Uso:  node video/grabar_sans.js
// Necesita Google Chrome o Microsoft Edge, y ffmpeg (en el PATH o con: pip install imageio-ffmpeg)
const { spawn, execFileSync } = require('child_process');
const fs = require('fs'), path = require('path'), os = require('os');

const DIR = __dirname, GAME = path.join(DIR, '..', 'isaac_verde.html'), OUT = path.join(DIR, 'pelea_sans.mp4');
const PORT = 9334;

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

// el bot: elige el menú de cada turno y esquiva probando cada dirección unos cuadros hacia adelante
const BOT = `(() => {
  const PLAN = [0, 1, 2, 3, 0, 2, 0, 1, 0, 0]; // LUCHAR, ACTUAR, OBJETO, PIEDAD...
  const DIRS = [[0,0],[1,0],[-1,0],[0,1],[0,-1],[1,1],[1,-1],[-1,1],[-1,-1]];
  let prev = 0;
  window.__utBot = u => {
    u.noDie = true; // en el video el alma no se rompe
    u.botW = (u.botW || 0) + 1;
    const press = c => { u.botW = 0; utKey(c); };
    if (u.phase === 'talk') { const b = u.bub; if (b && b.n >= b.lines[b.i].length && u.botW > 45) press('Enter'); }
    else if (u.phase === 'result') { if (u.textN >= u.text.length && u.botW > 60) press('Enter'); }
    else if (u.phase === 'menu') {
      const want = u.sleep ? 0 : PLAN[Math.min(u.turn - 1, PLAN.length - 1)];
      if (u.botW > 40 && u.botW % 16 === 0) { if (u.btn !== want) { utKey(u.btn < want ? 'ArrowRight' : 'ArrowLeft'); } else if (u.botW > 80) press('Enter'); }
    } else if (u.phase === 'list') { if (u.botW > 45) press('Enter'); }
    else if (u.phase === 'aim') { if (Math.abs(u.aimX - 480) < 6) press('Enter'); }
    if (u.phase !== 'attack' && u.phase !== 'talk') { u.botIn = null; return; }
    if (u.botIn && u.t % (window.__botEvery || 1)) return; // __botEvery/__botLook: bot más "humano" (reacciona más lento)
    const [cx, cy] = utMid(u.box);
    let best = 0, bestS = 1e9;
    DIRS.forEach(([dx, dy], i) => {
      const inp = { l: dx < 0, r: dx > 0, u: dy < 0, d: dy > 0 }, s = { ...u.soul };
      let sc = 0;
      for (let k = 1; k <= (window.__botLook || 22); k++) {
        utSoulStep(s, inp, u.box);
        for (const o of u.objs) if (utHit(o, s.x, s.y, o.t + k, s.moved)) sc += 30 - k;
      }
      if (s.mode === 'red') sc += Math.hypot(s.x - cx, s.y - cy) * 0.02;
      if (s.mode === 'blue' && (dx || dy)) sc += 0.3; // si no hay peligro, mejor quieto
      if (i === prev) sc -= 0.5;
      if (sc < bestS) { bestS = sc; best = i; }
    });
    prev = best;
    const [dx, dy] = DIRS[best];
    u.botIn = { l: dx < 0, r: dx > 0, u: dy < 0, d: dy > 0 };
  };
  return true;
})()`;

(async () => {
  const ffmpeg = findFfmpeg(), profile = fs.mkdtempSync(path.join(os.tmpdir(), 'grabar-sans-'));
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
    await cdp.send('Page.navigate', { url: 'file:///' + GAME.replace(/\\/g, '/') });
    await sleep(500);
    await evaluate(cdp, `new Promise(r => { const f = () => typeof SPR !== 'undefined' && Object.keys(SPR).length >= Object.keys(SPRITE_FILES).length ? r(true) : setTimeout(f, 100); f(); })`);
    await evaluate(cdp, BOT);
    // empieza una partida y se para frente a la puerta del cuarto de Sans
    await evaluate(cdp, `(async () => {
      grabando = true; initAudio(); if (AC.state !== 'running') await AC.resume();
      selIdx = 0; startGame(); stopMusic(); msgT = 0;
      floorBoss = 'sans';
      p.x = CX; p.y = BOT - 60; p.face = 'T';
      await new Promise(r => setTimeout(r, 700));
      const audio = AC.createMediaStreamDestination(); master.connect(audio);
      const stream = new MediaStream([...cv.captureStream(60).getVideoTracks(), ...audio.stream.getAudioTracks()]);
      const rec = new MediaRecorder(stream, { mimeType: 'video/webm;codecs=vp9,opus', videoBitsPerSecond: 4e6 });
      window.__parts = []; window.__done = new Promise(r => rec.onstop = r);
      rec.ondataavailable = e => __parts.push(e.data);
      rec.start(1000); window.__rec = rec;
      await new Promise(r => setTimeout(r, 300));
      cur = Object.values(rooms).find(r => r.type === 'boss'); enterRoom();
      return true;
    })()`);
    process.stdout.write('Grabando la pelea contra Sans');
    for (let i = 0; i < 900; i++) { // hasta que termina la batalla (máx. 7.5 min)
      await sleep(500);
      const st = await evaluate(cdp, `ut ? ut.phase + ' ' + ut.turn : 'fin'`);
      if (i % 20 === 0) process.stdout.write(` [${st}]`);
      if (st === 'fin') break;
    }
    await sleep(6000); // la muerte de Sans en el cuarto y la trampilla
    const b64len = await evaluate(cdp, `(async () => { __rec.stop(); await __done; master.disconnect();
      const buf = new Uint8Array(await new Blob(__parts).arrayBuffer()); let s = '';
      for (let i = 0; i < buf.length; i += 0x8000) s += String.fromCharCode.apply(null, buf.subarray(i, i + 0x8000));
      window.__b64 = btoa(s); return __b64.length; })()`);
    let b64 = '';
    for (let i = 0; i < b64len; i += 1 << 20) b64 += await evaluate(cdp, `__b64.slice(${i}, ${i + (1 << 20)})`);
    const webm = path.join(profile, 'sans.webm');
    fs.writeFileSync(webm, Buffer.from(b64, 'base64'));
    execFileSync(ffmpeg, ['-y', '-loglevel', 'error', '-i', webm, '-r', '60', '-c:v', 'libx264', '-preset', 'medium', '-crf', '20',
      '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', OUT]);
    console.log('\nlisto → ' + path.relative(path.join(DIR, '..'), OUT));
    cdp.close();
  } finally {
    browser.kill();
    await sleep(500);
    try { fs.rmSync(profile, { recursive: true, force: true }); } catch {}
  }
})().catch(e => { console.error(e.message || e); process.exit(1); });
