// Graba las peleas contra Baldi, Dr. Fetus y el Diablo jugadas por un bot: video/pelea_baldi.mp4, video/pelea_dr_fetus.mp4 y video/pelea_diablo.mp4
// Abre el juego en Chrome/Edge sin ventana, entra al cuarto del jefe y un bot juega la pelea completa.
// Uso:  node video/grabar_jefes_nuevos.js [baldi|fetus|devil]  (sin nada graba Baldi y Dr. Fetus)
//       node video/grabar_jefes_nuevos.js fetus --probar       (sin video: juega a toda velocidad y dice cómo le fue al bot)
// Necesita Google Chrome o Microsoft Edge, y ffmpeg (en el PATH o con: pip install imageio-ffmpeg)
const { spawn, execFileSync } = require('child_process');
const fs = require('fs'), path = require('path'), os = require('os');

const DIR = __dirname, GAME = path.join(DIR, '..', 'isaac_verde.html');
const OUT = { baldi: 'pelea_baldi.mp4', fetus: 'pelea_dr_fetus.mp4', devil: 'pelea_diablo.mp4' };
const PORT = 9335;

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

// los bots: Baldi (responde, salta la cuerda y recorre la escuela) y Meat Boy (simula sus saltos para planear)
const BOTS = `(() => {
  // ---------- Baldi ----------
  const wrapA = a => Math.atan2(Math.sin(a), Math.cos(a));
  window.__balBot = u => {
    u.noDie = true; // en el video Baldi no te mata
    u.botW = (u.botW || 0) + 1;
    const press = c => { u.botW = 0; balKey(c); };
    if (u.phase !== 'maze') u.botIn = null;
    if (u.phase === 'talk') { const b = u.bub; if (b && b.n >= b.lines[b.i].length && u.botW > 55) press('Enter'); }
    else if (u.phase === 'math') {
      const m = u.m; if (m.res || u.botW < 70) return;
      const want = m.q.glitch ? 1 : m.q.opts.indexOf(m.q.ans);
      if (m.sel !== want) { if (u.botW % 14 === 0) balKey((m.sel ^ want) & 1 ? 'ArrowRight' : 'ArrowDown'); }
      else if (u.botW > 120) press('Enter');
    } else if (u.phase === 'rope') {
      const r = u.r; if (r.wait || r.jy || r.jv) return;
      const cyc = Math.floor(r.ang / BAL_TAU), left = (BAL_TAU * (cyc + 1) - r.ang) / r.spd;
      if (left <= 18 && r.botCyc !== cyc) {
        r.botCyc = cyc;
        if (!u.botMissed && r.jumps === 2) { u.botMissed = true; return; } // falla una vez a propósito
        balJump();
      }
    } else if (u.phase === 'maze') {
      const z = u.z, w = z.w, px = Math.floor(z.x), py = Math.floor(z.y), d = balBfs(z, px, py);
      const goals = z.open ? z.exits.filter(e => !e.done).map(e => [e.x, e.y]) : z.notes.filter(n => !n.got).map(n => [Math.floor(n.x), Math.floor(n.y)]);
      let g = goals[0]; for (const q of goals) if (d[q[1] * w + q[0]] >= 0 && (d[g[1] * w + g[0]] < 0 || d[q[1] * w + q[0]] < d[g[1] * w + g[0]])) g = q;
      let [cx, cy] = g;
      while (d[cy * w + cx] > 1) { for (const [dx, dy] of DIR4) { const nx = cx + dx, ny = cy + dy; if (nx >= 0 && ny >= 0 && nx < w && ny < z.h && d[ny * w + nx] === d[cy * w + cx] - 1) { cx = nx; cy = ny; break; } } }
      let tx = cx + 0.5, ty = cy + 0.5;
      if (cx !== px && Math.abs(z.y - (py + 0.5)) > 0.12) { tx = px + 0.5; ty = py + 0.5; } // primero al centro del pasillo
      else if (cy !== py && Math.abs(z.x - (px + 0.5)) > 0.12) { tx = px + 0.5; ty = py + 0.5; }
      const da = wrapA(Math.atan2(ty - z.y, tx - z.x) - z.a);
      u.botIn = { l: da < -0.05, r: da > 0.05, u: Math.abs(da) < 0.45, d: false };
    }
  };
  // ---------- Meat Boy ----------
  const S = (c, row) => [c * FT, row * FT - 11], P = (c, row) => [c * FT, row * FT];
  const WP = {
    tower: [S(11.5, 63), S(8.5, 60), S(12.8, 57), S(17.2, 57), S(22.5, 54), S(17.5, 51), S(9.5, 48), S(6, 48), S(3, 45), P(2.5, 37), P(2.5, 33), S(8, 35),
      S(16, 32), S(19.5, 32), S(24.5, 29), S(19.5, 26), S(13.2, 23), S(9, 23), S(5.5, 20), S(10, 17), S(14, 17), S(18, 14), S(26.5, 11),
      S(20.5, 8), S(13.5, 5), P(12, 1)],
    lab: [S(5, 14), S(11.5, 11), S(4.5, 8), S(11.5, 11), S(18, 11), S(25.5, 8), S(17.5, 11), S(14.5, 11)],
  };
  const OPTS = [[-1, 0], [0, 0], [1, 0], [-1, 1], [0, 1], [1, 1]].map(([x, j]) => ({ x, j: !!j }));
  window.__fetBot = f => {
    f.noDie = true; // en el video morir no quita corazones (pero sí se ve)
    if (f.phase === 'card') { f.botIn = null; if (f.pt > 60) fetKey('Enter'); return; }
    if (!['tower', 'lab', 'free'].includes(f.phase)) { f.botIn = null; return; }
    const m = f.m, key = f.lab ? 'lab' : 'tower';
    if (f.botKey !== key) { f.botKey = key; f.botWp = 0; f.botStuck = 0; f.botCp = 0; f.botWpCp = 0; }
    if (f.cp !== f.botCp) { f.botCp = f.cp; f.botWpCp = f.botWp; } // al morir vuelve a la ruta desde el punto de control
    if (m.dead) { f.botIn = { x: 0, j: false }; f.botWp = f.botWpCp; f.botStuck = 0; return; }
    const cx = m.x + m.w / 2, cy = m.y + m.h / 2;
    let wp;
    if (f.phase === 'free') wp = [f.lab.fetus.x, f.lab.fetus.y];
    else {
      const list = f.L.wp || WP[key];
      while (f.botWp < list.length - 1 && Math.hypot(cx - list[f.botWp][0], cy - list[f.botWp][1]) < 26) { f.botWp++; f.botStuck = 0; }
      if (key === 'lab' && f.botWp >= list.length - 1 && f.lab.btn.every(b => b)) { f.botIn = { x: 0, j: false }; return; }
      wp = list[f.botWp];
    }
    if (++f.botStuck > 1500 && f.botWp < (f.L.wp || WP[key]).length - 1) { f.botWp++; f.botStuck = 0; } // si se atora mucho, sigue con el siguiente
    if (f.botIn && f.t % 2) return;
    let best = null, bs = 1e12;
    for (const a of OPTS) for (const b of OPTS) for (const c of OPTS) {
      const s = { ...m }; let sc = 1e9;
      for (let k = 0; k < 30; k++) {
        fetStep(s, k < 10 ? a : k < 20 ? b : c, f.L);
        if (fetDanger(f, s, k + 1)) { sc = 1e7 - k * 1000; break; }
        const d = Math.hypot(s.x + s.w / 2 - wp[0], s.y + s.h / 2 - wp[1]) + k * 0.4;
        if (d < sc) sc = d;
      }
      if (f.botIn && a.x === f.botIn.x && a.j === f.botIn.j) sc -= 0.5;
      if (sc < bs) { bs = sc; best = a; }
    }
    f.botIn = best;
  };
  // ---------- Cuphead contra el Diablo ----------
  const COPTS = [{ x: -1 }, { x: 0 }, { x: 1 }, { x: -1, j: 1 }, { x: 0, j: 1 }, { x: 1, j: 1 }, { x: 0, down: 1 }, { x: -1, dash: 1 }, { x: 1, dash: 1 }]
    .map(o => ({ x: o.x, j: !!o.j, down: !!o.down, dash: !!o.dash, up: false, shoot: false, ex: false }));
  window.__dvlBot = d => {
    d.noDie = true; // en el video los golpes se ven pero no quitan corazones
    if (d.phase === 'card') { d.botIn = null; if (d.pt > 60) dvlKey('Enter'); return; }
    const c = d.c, hb = dvlBossHb(d);
    const aim = Math.round(Math.atan2(hb.y - (c.y - 30), hb.x - c.x) / (Math.PI / 4)) * (Math.PI / 4); // 8 direcciones, como en Cuphead
    const fire = { shoot: d.phase === 'fight', ex: d.cards >= 1 && d.t % 90 === 0, aim };
    if (!['ready', 'fight', 'ko'].includes(d.phase)) { d.botIn = { ...DV_NOINP }; return; }
    // parry: si hay algo rosa muy cerca y está en el aire, vuelve a saltar
    const b = dvlBox(c), pinkNear = !c.ground && c.parryOk && d.haz.some(h => h.pink && dvlCircs(h, d, 0).some(([x, y, r]) => dvlBoxHit(b, x, y, r + 10)));
    if (d.botPlan && d.t % 3) { d.botIn = { ...d.botPlan, ...fire, j: pinkNear ? !c.jh : d.botPlan.j }; return; }
    const plats = d.floor ? null : d.plats.filter(q => q.st === 0);
    let pref = d.floor ? 480 + Math.sign(c.x - 480 || 1) * 170 : plats.length ? plats.reduce((a, q) => Math.abs(q.x - hb.x * 0.3 - c.x * 0.7) < Math.abs(a.x - hb.x * 0.3 - c.x * 0.7) ? q : a).x : 480;
    let best = null, bs = 1e12;
    for (const a of COPTS) for (const b2 of COPTS) {
      if (b2.dash && a.dash) continue;
      const s = { ...c }; let sc = 0, hit = false;
      for (let k = 0; k < 26; k++) {
        dvlStep(s, k < 10 ? a : b2, d, k + 1);
        if (dvlDanger(d, s, k + 1)) { sc = 1e7 - k * 2e5; hit = true; break; }
      }
      if (!hit) {
        sc = Math.abs(s.x - pref) * 0.6 + (a.j ? 6 : 0) + (a.dash ? 10 : 0) + (a.down ? 4 : 0);
        if (!d.floor && !s.ground && s.y > 470) sc += 3e5; // no caerse al abismo
      }
      if (d.botPlan && a.x === d.botPlan.x && a.j === d.botPlan.j && a.down === d.botPlan.down) sc -= 3;
      if (sc < bs) { bs = sc; best = a; }
    }
    d.botPlan = best;
    d.botIn = { ...best, ...fire, j: pinkNear ? !c.jh : best.j };
  };
  return true;
})()`;

async function openGame(port) {
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'grabar-jefes-'));
  const browser = spawn(findBrowser(), ['--headless=new', `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`,
    '--autoplay-policy=no-user-gesture-required', '--allow-file-access-from-files', '--window-size=960,576',
    '--force-device-scale-factor=1', '--disable-background-timer-throttling', '--disable-renderer-backgrounding',
    '--disable-backgrounding-occluded-windows', 'about:blank'], { stdio: 'ignore' });
  let page;
  for (let i = 0; i < 50 && !page; i++) {
    await sleep(200);
    try { page = (await (await fetch(`http://127.0.0.1:${port}/json/list`)).json()).find(t => t.type === 'page'); } catch {}
  }
  if (!page) { browser.kill(); throw new Error('El navegador no respondió'); }
  const cdp = await connect(page.webSocketDebuggerUrl);
  await cdp.send('Runtime.enable');
  await cdp.send('Page.navigate', { url: 'file:///' + GAME.replace(/\\/g, '/') });
  await sleep(500);
  await evaluate(cdp, `new Promise(r => { const f = () => typeof SPR !== 'undefined' && Object.keys(SPR).length >= Object.keys(SPRITE_FILES).length ? r(true) : setTimeout(f, 100); f(); })`);
  await evaluate(cdp, BOTS);
  const close = async () => { cdp.close(); browser.kill(); await sleep(500); try { fs.rmSync(profile, { recursive: true, force: true }); } catch {} };
  return { cdp, close, profile };
}
const STATUS = `dvl ? 'diablo ' + dvl.phase + ' fase' + dvl.stage + ' vida ' + Math.round(dvl.hp) + ' golpes ' + dvl.hits + ' parries ' + dvl.parries : bal ? 'baldi ' + bal.phase + (bal.z ? ' ' + bal.z.got + '/7' : '') : fet ? 'fetus ' + fet.phase + ' wp' + fet.botWp + ' muertes ' + fet.deaths + ' y' + Math.round(fet.m.y) : bossIntro ? 'intro' : 'fin'`;

async function grabar(type, probar) {
  const { cdp, close, profile } = await openGame(PORT);
  try {
    // empieza una partida y entra al cuarto del jefe
    await evaluate(cdp, `(async () => {
      grabando = true; initAudio(); if (AC.state !== 'running') await AC.resume();
      selIdx = 0; startGame(); stopMusic(); msgT = 0;
      floorBoss = '${type}'; p.x = CX; p.y = BOT - 60; p.face = 'T';
      await new Promise(r => setTimeout(r, 700));
      ${probar ? '' : `const audio = AC.createMediaStreamDestination(); master.connect(audio);
      const stream = new MediaStream([...cv.captureStream(60).getVideoTracks(), ...audio.stream.getAudioTracks()]);
      const rec = new MediaRecorder(stream, { mimeType: 'video/webm;codecs=vp9,opus', videoBitsPerSecond: 5e6 });
      window.__parts = []; window.__done = new Promise(r => rec.onstop = r);
      rec.ondataavailable = e => __parts.push(e.data);
      rec.start(1000); window.__rec = rec;
      await new Promise(r => setTimeout(r, 300));`}
      cur = Object.values(rooms).find(r => r.type === 'boss'); enterRoom();
      return true;
    })()`);
    if (probar) { // a toda velocidad, sin dibujar
      if (process.env.PASO) await evaluate(cdp, 'window.__paso = ' + process.env.PASO);
      for (let i = 0; i < 400; i++) {
        const st = await evaluate(cdp, `(() => { for (let k = 0; k < (window.__paso || 600); k++) { update(); if (state !== 'play') break; } return ${STATUS}; })()`);
        console.log(`[${(i + 1) * 10}s] ${st}`);
        if (process.env.FOTOS) { // capturas para revisar cómo se ve
          await sleep(80);
          const shot = await cdp.send('Page.captureScreenshot', { format: 'jpeg', quality: 70 });
          fs.writeFileSync(path.join(process.env.FOTOS, `${type}_${String(i).padStart(3, '0')}.jpg`), Buffer.from(shot.result.data, 'base64'));
        }
        if (st === 'fin') break;
      }
      return;
    }
    process.stdout.write(`Grabando la pelea contra ${type}`);
    for (let i = 0; i < 1200; i++) { // hasta que termina la pelea (máx. 10 min)
      await sleep(500);
      const st = await evaluate(cdp, STATUS);
      if (i % 20 === 0) process.stdout.write(` [${st}]`);
      if (st === 'fin') break;
    }
    await sleep(6000); // el jefe revienta y aparece la trampilla
    const b64len = await evaluate(cdp, `(async () => { __rec.stop(); await __done; master.disconnect();
      const buf = new Uint8Array(await new Blob(__parts).arrayBuffer()); let s = '';
      for (let i = 0; i < buf.length; i += 0x8000) s += String.fromCharCode.apply(null, buf.subarray(i, i + 0x8000));
      window.__b64 = btoa(s); return __b64.length; })()`);
    let b64 = '';
    for (let i = 0; i < b64len; i += 1 << 20) b64 += await evaluate(cdp, `__b64.slice(${i}, ${i + (1 << 20)})`);
    const webm = path.join(profile, type + '.webm'), out = path.join(DIR, OUT[type]);
    fs.writeFileSync(webm, Buffer.from(b64, 'base64'));
    execFileSync(findFfmpeg(), ['-y', '-loglevel', 'error', '-i', webm, '-r', '60', '-c:v', 'libx264', '-preset', 'medium', '-crf', '21',
      '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', out]);
    console.log('\nlisto → ' + path.relative(path.join(DIR, '..'), out));
  } finally { await close(); }
}

(async () => {
  const args = process.argv.slice(2), probar = args.includes('--probar');
  const types = args.filter(a => OUT[a]);
  for (const t of types.length ? types : ['baldi', 'fetus']) await grabar(t, probar);
})().catch(e => { console.error(e.message || e); process.exit(1); });
