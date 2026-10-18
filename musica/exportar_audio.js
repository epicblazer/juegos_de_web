// Exporta toda la música del juego a musica/*.mp3 y los sonidos especiales a sonidos/*.mp3
// El juego sintetiza todo el audio en vivo; esto lo graba con el mismo código (exportarAudio de isaac_verde.html).
// Uso:  node musica/exportar_audio.js
// Necesita Google Chrome o Microsoft Edge, y ffmpeg (en el PATH o con: pip install imageio-ffmpeg)
const { spawn, execFileSync } = require('child_process');
const fs = require('fs'), path = require('path'), os = require('os');

const ROOT = path.join(__dirname, '..'), GAME = path.join(ROOT, 'isaac_verde.html');
const MUS_DIR = path.join(ROOT, 'musica'), SFX_DIR = path.join(ROOT, 'sonidos');
const PORT = 9337;

// nombre en el juego → nombre del archivo (los numeros ordenan la carpeta)
const MUSICA = {
  title: '01_menu_y_creditos', floor: '02_pisos_sotano_y_cuevas', eerie: '03_pisos_profundos', bright: '04_mundos_alegres_y_angel', retro: '05_arena_retro',
  boss: '10_jefe_monstro', dukeFlies: '11_jefe_duque_de_las_moscas', gurdy: '12_jefe_gurdy', peep: '13_jefe_peep', widow: '14_jefe_la_viuda',
  kingSlime: '16_jefe_rey_slime', kingBoo: '17_jefe_rey_boo', mothership: '18_jefe_nave_nodriza', koopa: '19_jefe_rey_koopa',
  eggman: '20_jefe_dr_huevon', dragon: '21_jefe_dragon_del_fin', ghostKing: '22_jefe_rey_fantasma', brain: '23_jefe_cerebro_madre', ridley: '24_jefe_ridley',
  wither: '25_jefe_wither', ganon: '26_jefe_ganon', sans: '27_jefe_sans', satan: '28_jefe_satanas', final: '29_jefe_final_isaac_oscuro',
};
const SONIDOS = {
  shoot: 'disparo_lagrima', fire: 'disparo_fuego', sword: 'espada', ringS: 'anillo', block: 'bloqueo', laser: 'laser', splash: 'lagrima_choca', hit: 'golpe_a_enemigo',
  kill: 'enemigo_muere', hurt: 'jugador_herido', death: 'jugador_muere', enemyShot: 'disparo_enemigo', arrow: 'flecha', orb: 'orbe', hiss: 'creeper_mecha', boom: 'explosion',
  squish: 'slime', ghost: 'fantasma', teleport: 'teletransporte', summon: 'invocar', slash: 'cuchillazo', parry: 'parada', throw: 'lanzar', sniper: 'francotirador',
  flame: 'lanzallamas', bump: 'rebote', drop: 'bomba_cae', select: 'menu_elegir', doorClose: 'puerta_cierra', doorOpen: 'puerta_abre', heart: 'corazon',
  item: 'objeto_conseguido', star: 'super_estrella', stomp: 'pisoton', bigStomp: 'pisoton_gigante', spit: 'escupir', jump: 'salto', roar: 'rugido', screech: 'chillido',
  brimstone: 'rayo_infernal', laugh: 'risa_boo', bossDie: 'jefe_muere', win: 'victoria', retroOn: 'modo_retro', devilDoor: 'puerta_diablo', angelDoor: 'puerta_angel',
  devilEnter: 'cuarto_diablo', angelEnter: 'cuarto_angel', devilBuy: 'pacto_diablo', shield: 'escudo_divino', floor: 'bajar_de_piso', start: 'empezar_partida',
  vsSlam: 'presentacion_vs', swoosh: 'barrido', stamp: 'sello', whistle: 'silbido_artilleria', rumble: 'temblor', knock: 'tocan_la_puerta', heartbeat: 'latido',
  thud: 'golpe_seco', sitDown: 'sentarse', chirp: 'pajaritos', drone: 'zumbido_grave', glitch: 'interferencia', question: 'pregunta', surprise: 'sorpresa',
  blip: 'texto', blipLow: 'texto_grave', clink: 'esposas', engine: 'motor',
  // pelea de Sans (estilo Undertale)
  utVoice: 'sans_voz', utText: 'sans_texto', utMove: 'sans_menu_mover', utOk: 'sans_menu_elegir', utEnc: 'sans_encuentro',
  utHurt: 'sans_alma_herida', utDing: 'sans_alma_azul', utSlam: 'sans_golpe_pared', utBone: 'sans_huesos_salen', gbCharge: 'sans_blaster_carga',
  gbFire: 'sans_blaster_dispara', utHit: 'sans_golpe_final', utHeal: 'sans_curarse', utCrack: 'sans_corazon_se_rompe', utShatter: 'sans_corazon_en_pedazos',
};

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

(async () => {
  const ffmpeg = findFfmpeg(), profile = fs.mkdtempSync(path.join(os.tmpdir(), 'audio-'));
  fs.mkdirSync(MUS_DIR, { recursive: true }); fs.mkdirSync(SFX_DIR, { recursive: true });
  const browser = spawn(findBrowser(), ['--headless=new', `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`,
    '--allow-file-access-from-files', 'about:blank'], { stdio: 'ignore' });
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
    // avisa si el juego tiene música o sonidos sin nombre de archivo aquí
    const [mus, sfx] = await evaluate(cdp, `[Object.keys(MUSIC), Object.keys(SFX)]`);
    const alias = ['monstro', 'darkIsaac']; // son la misma canción que 'boss' y 'final'
    for (const k of mus) if (!MUSICA[k] && !alias.includes(k)) MUSICA[k] = 'otra_' + k;
    for (const k of sfx) if (!SONIDOS[k]) SONIDOS[k] = k;
    const jobs = [...Object.entries(MUSICA).map(([k, n]) => ['music', k, path.join(MUS_DIR, n + '.mp3')]),
      ...Object.entries(SONIDOS).map(([k, n]) => ['sfx', k, path.join(SFX_DIR, n + '.mp3')])];
    for (const [kind, key, out] of jobs) {
      // el WAV se trae en pedazos: un mensaje muy grande traba la conexión con el navegador
      const len = await evaluate(cdp, `exportarAudio(${JSON.stringify(kind)}, ${JSON.stringify(key)}).then(s => (window.__wav = s).length)`);
      let b64 = '';
      for (let i = 0; i < len; i += 1 << 20) b64 += await evaluate(cdp, `window.__wav.slice(${i}, ${i + (1 << 20)})`);
      const wav = path.join(profile, key + '.wav');
      fs.writeFileSync(wav, Buffer.from(b64, 'base64'));
      execFileSync(ffmpeg, ['-y', '-loglevel', 'error', '-i', wav, '-c:a', 'libmp3lame', '-b:a', kind === 'music' ? '192k' : '160k', out]);
      console.log('listo → ' + path.relative(ROOT, out));
    }
    cdp.close();
  } finally {
    browser.kill();
    await sleep(500);
    try { fs.rmSync(profile, { recursive: true, force: true }); } catch {}
  }
})().catch(e => { console.error(e.message || e); process.exit(1); });
