# Arma el tráiler súper exagerado de The Binding of Epic: videos_publisidad/publicidad_the_binding_of_epic.mp4
# Usa los videos de video/, los sprites de sprites/, la música de musica/, los sonidos de sonidos/
# y los dibujos de objetos que saca exportar_objetos.js (videos_publisidad/recursos/objetos/).
# Uso:  node videos_publisidad/exportar_objetos.js   (sólo la primera vez)
#       python videos_publisidad/hacer_publicidad.py
# Necesita: pip install pillow numpy imageio-ffmpeg
import json, math, os, random, subprocess, wave
from functools import lru_cache

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

FF = imageio_ffmpeg.get_ffmpeg_exe()
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(HERE, 'publicidad_the_binding_of_epic.mp4')
W, H, FPS, SR = 1280, 720, 30, 44100
IMPACT, BLACK = 'C:/Windows/Fonts/impact.ttf', 'C:/Windows/Fonts/ariblk.ttf'
random.seed(7)


# ---------------------------------------------------------------- utilidades de imagen
@lru_cache(maxsize=None)
def font(path, size):
    return ImageFont.truetype(path, size)


@lru_cache(maxsize=1024)
def text_img(s, size, fill='#ffffff', stroke=6, sc='#000000', fp=IMPACT, glow=None):
    f = font(fp, size)
    bb = ImageDraw.Draw(Image.new('L', (1, 1))).textbbox((0, 0), s, font=f, stroke_width=stroke)
    pad = 40 if glow else 10
    im = Image.new('RGBA', (bb[2] - bb[0] + pad * 2, bb[3] - bb[1] + pad * 2), (0, 0, 0, 0))
    pos = (pad - bb[0], pad - bb[1])
    if glow:
        g = Image.new('RGBA', im.size, (0, 0, 0, 0))
        ImageDraw.Draw(g).text(pos, s, font=f, fill=glow, stroke_width=stroke + 6, stroke_fill=glow)
        im = Image.alpha_composite(im, g.filter(ImageFilter.GaussianBlur(14)))
    ImageDraw.Draw(im).text(pos, s, font=f, fill=fill, stroke_width=stroke, stroke_fill=sc)
    return im


def put(base, im, cx, cy, scale=1.0, alpha=1.0, rot=0):
    """Pega una imagen RGBA centrada en (cx, cy)."""
    if scale != 1:
        im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.BILINEAR)
    if rot:
        im = im.rotate(rot, Image.BILINEAR, expand=True)
    if alpha < 1:
        im = im.copy()
        im.putalpha(im.getchannel('A').point(lambda v: int(v * max(0, alpha))))
    base.paste(im, (int(cx - im.width / 2), int(cy - im.height / 2)), im)


def slam(k, frames=6, big=2.6):
    """Escala para el efecto de 'golpe' de un texto que cae: grande -> normal."""
    if k < 0:
        return 0
    return 1 + (big - 1) * max(0, 1 - k / frames) ** 2


def say(base, s, size, cx, cy, k, fill='#ffffff', glow=None, fp=IMPACT, stroke=6, big=2.6, shake=0, maxw=None):
    if k < 0:
        return
    if maxw and text_img(s, size, fill, stroke, '#000000', fp, glow).width > maxw:  # achica los textos largos
        size = int(size * maxw / text_img(s, size, fill, stroke, '#000000', fp, glow).width)
    dx = random.uniform(-shake, shake) if shake else 0
    dy = random.uniform(-shake, shake) if shake else 0
    put(base, text_img(s, size, fill, stroke, '#000000', fp, glow), cx + dx, cy + dy, slam(k, big=big), min(1, 0.35 + k / 3))


_vig = None


def vignette(img, power=1.0):
    global _vig
    if _vig is None:
        y, x = np.mgrid[0:H, 0:W]
        d = np.sqrt(((x - W / 2) / (W / 2)) ** 2 + ((y - H / 2) / (H / 2)) ** 2)
        v = np.clip(1.15 - 0.55 * d ** 2, 0, 1)
        _vig = v
    v = 1 - (1 - _vig) * power
    a = (np.asarray(img, np.float32) * v[..., None]).clip(0, 255).astype(np.uint8)
    return Image.fromarray(a)


def fx(img, zoom=1.0, shake=0.0, flash=0.0, tint=None, tint_a=0.0, chroma=0, dark=0.0, vig=0.7):
    if shake:
        zoom = max(zoom, 1 + shake * 2.4 / W)
    if zoom != 1:
        cw, ch = W / zoom, H / zoom
        cx = W / 2 + random.uniform(-shake, shake)
        cy = H / 2 + random.uniform(-shake, shake)
        cx = min(max(cx, cw / 2), W - cw / 2)
        cy = min(max(cy, ch / 2), H - ch / 2)
        img = img.crop((int(cx - cw / 2), int(cy - ch / 2), int(cx + cw / 2), int(cy + ch / 2))).resize((W, H), Image.BILINEAR)
    if chroma:
        r, g, b = img.split()
        img = Image.merge('RGB', (ImageChops.offset(r, chroma, 0), g, ImageChops.offset(b, -chroma, 0)))
    if tint and tint_a:
        img = Image.blend(img, Image.new('RGB', (W, H), tint), tint_a)
    if dark:
        img = Image.blend(img, Image.new('RGB', (W, H), 'black'), dark)
    if vig:
        img = vignette(img, vig)
    if flash > 0:
        img = Image.blend(img, Image.new('RGB', (W, H), 'white'), min(1, flash))
    return img


@lru_cache(maxsize=16)
def rays_base(c1, c2, n=18):
    S = 1700
    im = Image.new('RGB', (S, S), c1)
    d = ImageDraw.Draw(im)
    for i in range(n):
        a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 0.5) / n
        d.polygon([(S / 2, S / 2), (S / 2 + S * math.cos(a0), S / 2 + S * math.sin(a0)),
                   (S / 2 + S * math.cos(a1), S / 2 + S * math.sin(a1))], fill=c2)
    return im


def rays(c1, c2, ang):
    im = rays_base(c1, c2).rotate(ang, Image.BILINEAR)
    S = im.width
    return im.crop(((S - W) // 2, (S - H) // 2, (S - W) // 2 + W, (S - H) // 2 + H))


def bars(img, h=56):
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, W, h), fill='black')
    d.rectangle((0, H - h, W, H), fill='black')


class Embers:
    """Chispas que suben (para las partes de fuego)."""

    def __init__(self, n=70, col=(255, 120, 30)):
        self.p = [[random.uniform(0, W), random.uniform(0, H), random.uniform(1, 4), random.uniform(1.5, 5)] for _ in range(n)]
        self.col = col

    def draw(self, img):
        d = ImageDraw.Draw(img)
        for q in self.p:
            q[1] -= q[3]
            q[0] += math.sin(q[1] * 0.02) * 1.2
            if q[1] < -10:
                q[0], q[1] = random.uniform(0, W), H + 10
            r = q[2]
            d.ellipse((q[0] - r, q[1] - r, q[0] + r, q[1] + r), fill=self.col)


def danger(img, level, k, x=40, y=H - 118):
    """Medidor de NIVEL DE PELIGRO que se llena."""
    put(img, text_img('NIVEL DE PELIGRO', 26, '#ffffff', 4, '#000', BLACK), x + 150, y, 1)
    d = ImageDraw.Draw(img)
    filled = min(level, k / 2.0)
    for i in range(10):
        col = (90, 220, 70) if i < 3 else (240, 210, 40) if i < 6 else (255, 120, 20) if i < 8 else (240, 30, 30)
        bx = x + i * 31
        d.rectangle((bx, y + 22, bx + 25, y + 58), fill=(20, 20, 20), outline='black', width=3)
        if i < filled:
            d.rectangle((bx + 3, y + 25, bx + 22, y + 55), fill=col)
    if filled >= level:
        lbl = f'{level}/10'
        col = '#ff3030' if level >= 9 else '#ffd030' if level >= 6 else '#80ff60'
        put(img, text_img(lbl, 48, col, 5), x + 360, y + 38, 1 + (0.25 * math.sin(k * 0.9) if level == 10 else 0))


def stamp(img, s, k, cx, cy, col='#ff2020', rot=-12, size=90):
    """Sello tipo 'APROBADO' que cae girado."""
    if k < 0:
        return
    t = text_img(s, size, col, 8, '#200000')
    put(img, t, cx, cy, slam(k, 5, 3.2), min(1, 0.4 + k / 3), rot)


# ---------------------------------------------------------------- videos
def clip(name, start, dur):
    """Cuadros (PIL RGB 1280x720) de video/<name>.mp4 desde 'start' durante 'dur' segundos."""
    n = round(dur * FPS)
    path = os.path.join(ROOT, 'video', name + '.mp4')
    cmd = [FF, '-loglevel', 'error', '-ss', str(start), '-i', path, '-t', str(dur + 0.2), '-an',
           '-vf', f'fps={FPS},scale={W}:768,crop={W}:{H}', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-']
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    sz, last, out = W * H * 3, None, []
    for _ in range(n):
        b = p.stdout.read(sz)
        if len(b) == sz:
            last = Image.frombytes('RGB', (W, H), b)
        out.append(last if last is not None else Image.new('RGB', (W, H)))
    p.kill()
    p.wait()
    return out


# ---------------------------------------------------------------- sprites
def sheet_frame(path, fw, col, row, size):
    im = sheet(path)
    return im.crop((col * fw, row * fw, col * fw + fw, row * fw + fw)).resize((size, size), Image.LANCZOS)


@lru_cache(maxsize=None)
def sheet(path):
    return Image.open(path).convert('RGBA')


SOLDADOS = [  # nombre, archivo de sprites, especialidad (como en el juego)
    ('ISAAC SOLDADO', 'isaac', 'TODOTERRENO'), ('DEMONIO', 'demonio', 'FUEGO INFERNAL'),
    ('ALMA PERDIDA', 'alma_perdida', 'VELOCIDAD'), ('JUDAS', 'judas', 'DAÑO'),
    ('MAGDALENA', 'magdalena', 'RESISTENCIA'), ('COMANDO CUCHILLO', 'comando_cuchillo', 'CUERPO A CUERPO'),
    ('GRANADERO', 'granadero', 'EXPLOSIVOS'), ('FRANCOTIRADOR', 'francotirador', 'PRECISIÓN'),
    ('LANZALLAMAS', 'lanzallamas', 'FUEGO'), ('MÉDICO', 'medico', 'APOYO'),
    ('ESCOPETERO', 'escopetero', 'ESCOPETA'), ('AMETRALLADOR', 'ametrallador', 'AMETRALLADORA'),
    ('PARACAIDISTA', 'paracaidista', 'VELOCIDAD'), ('RADIOOPERADOR', 'radiooperador', 'COMUNICACIONES'),
    ('INGENIERO', 'ingeniero', 'REBOTES'), ('EXPLORADOR', 'explorador', 'ARCO'),
    ('TANQUISTA', 'tanquista', 'BLINDADO'), ('MARINERO', 'marinero', 'AGUA A PRESIÓN'),
    ('ESPÍA', 'espia', 'SIGILO'),
]


def soldier_path(f):
    return os.path.join(ROOT, 'sprites', 'isaac_movimiento.png' if f == 'isaac' else f'personajes/{f}_movimiento.png')


JEFES_HOJAS = ['monstro', 'duque_moscas', 'gurdy', 'peep', 'rey_slime', 'viuda', 'rey_boo', 'nave_nodriza', 'rey_koopa',
               'baldi', 'ridley', 'dr_huevon', 'dr_fetus', 'wither', 'ganon', 'dragon_fin', 'rey_fantasma',
               'cerebro_madre', 'sans', 'diablo', 'flowey', 'satanas']


def boss_img(n, size):
    return sheet_frame(os.path.join(ROOT, 'sprites', f'jefe_{n}.png'), 256, 0, 0, size)


# ---------------------------------------------------------------- línea de tiempo
class Timeline:
    def __init__(self, path):
        self.f = 0
        self.sfx, self.music = [], []
        self.p = subprocess.Popen([FF, '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
                                   '-r', str(FPS), '-i', '-', '-c:v', 'libx264', '-preset', 'medium', '-crf', '18',
                                   '-pix_fmt', 'yuv420p', path], stdin=subprocess.PIPE)

    @property
    def t(self):
        return self.f / FPS

    def emit(self, img):
        self.p.stdin.write(img.convert('RGB').tobytes())
        self.f += 1
        if self.f % 150 == 0:
            print(f'  {self.t:5.1f} s', flush=True)

    def snd(self, name, gain=1.0, dt=0.0):
        self.sfx.append((name, self.t + dt, gain))

    def mus(self, track, at, dur, src=0.0, gain=0.75, fi=0.05, fo=0.4):
        self.music.append((track, at, dur, src, gain, fi, fo))

    def close(self):
        self.p.stdin.close()
        self.p.wait()


# ---------------------------------------------------------------- escenas
def intro(tl):
    """Negro, latidos y texto amenazante."""
    tl.snd('zumbido_grave', 0.9)
    lines = [('EN LO MÁS PROFUNDO DEL SÓTANO...', 0, 2.0), ('UN SOLDADO VERDE', 2.0, 1.6), ('VA A LLORAR... ¡¡BALAS!!', 3.6, 1.6)]
    for i in range(round(5.2 * FPS)):
        t = i / FPS
        if i % 24 == 0:
            tl.snd('latido', 0.9)
        pulse = 0.5 + 0.5 * math.sin(t * math.pi * 2.5)
        img = Image.new('RGB', (W, H), (int(40 * pulse), 0, 0))
        img = vignette(img, 1.0)
        for s, a, d in lines:
            if a <= t < a + d:
                k = i - round(a * FPS)
                fade = min(1, (a + d - t) * 4)
                col = '#ff3b3b' if 'BALAS' in s else '#e8e8e8'
                put(img, text_img(s, 64 if 'BALAS' in s else 52, col, 5, '#000', IMPACT, '#600000' if 'BALAS' in s else None),
                    W / 2, H / 2, slam(k, 5, 1.6), fade * min(1, k / 4 + 0.2))
                if k == 0 and 'BALAS' in s:
                    tl.snd('disparo_lagrima', 1.0)
                    tl.snd('golpe_seco', 0.8)
        tl.emit(img)


def title(tl, big=False):
    """El título cae con explosión sobre la pantalla de inicio del juego."""
    fr = clip('gameplay_isaac', 0.2, 3.2)
    tl.snd('explosion', 1.0)
    tl.snd('rugido', 0.6)
    emb = Embers(80)
    for i, f in enumerate(fr):
        img = fx(f, zoom=1.25 - i * 0.003, shake=max(0, 22 - i * 0.8), flash=max(0, 1 - i / 6), dark=0.35)
        emb.draw(img)
        say(img, 'THE BINDING', 120, W / 2, H / 2 - 95, i, '#f4f4f4', '#ff4000', shake=max(0, 6 - i * 0.2))
        say(img, 'OF EPIC', 170, W / 2, H / 2 + 45, i - 5, '#7dff4a', '#1a8a00', shake=max(0, 8 - i * 0.2), big=3.2)
        if i == 5:
            tl.snd('pisoton_gigante', 1.0)
        say(img, '—  EDICIÓN SOLDADO VERDE  —', 34, W / 2, H / 2 + 175, i - 18, '#ffd84a', fp=BLACK, stroke=4, big=1.4)
        tl.emit(img)


def boss_wall(tl):
    """Pared de jefes que aparecen de golpe: '¡¡22 JEFES!!'."""
    imgs = [boss_img(n, 170) for n in JEFES_HOJAS]
    pos = [(110 + (j % 11) * 106, 200 + (j // 11) * 230 + (j % 2) * 40) for j in range(len(imgs))]
    n = round(3.4 * FPS)
    for i in range(n):
        img = rays((40, 0, 0), (75, 6, 6), i * 0.8)
        shown = min(len(imgs), i // 2 + 1)
        if i % 2 == 0 and i // 2 < len(imgs):
            tl.snd('golpe_a_enemigo', 0.5)
        for j in range(shown):
            k = i - j * 2
            put(img, imgs[j], *pos[j], slam(k, 4, 1.8))
        img = fx(img, shake=6 if i < 50 else 3, flash=0.6 if i == 46 else 0)
        if i >= 46:
            if i == 46:
                tl.snd('explosion', 0.9)
            say(img, '¡¡+20 JEFES!!', 160, W / 2, H / 2 - 10, i - 46, '#ffe040', '#ff2000', shake=5, big=3.5)
            say(img, 'DE TUS JUEGOS FAVORITOS... ¡¡Y CON HAMBRE!!', 36, W / 2, H / 2 + 105, i - 54, '#ffffff', fp=BLACK, stroke=4, big=1.3)
        tl.emit(img)


def section_card(tl, top, main, sub, c1, c2, txt, glow, dur=1.8, snd='presentacion_vs'):
    tl.snd(snd, 1.0)
    n = round(dur * FPS)
    for i in range(n):
        img = rays(c1, c2, i * 1.5)
        img = fx(img, shake=max(0, 14 - i), flash=max(0, 0.9 - i / 5))
        say(img, top, 44, W / 2, H / 2 - 120, i, '#ffffff', fp=BLACK, stroke=5, big=1.6)
        say(img, main, 120, W / 2, H / 2, i - 3, txt, glow, shake=3, big=3)
        if sub:
            say(img, sub, 38, W / 2, H / 2 + 115, i - 14, '#ffffff', fp=BLACK, stroke=4, big=1.3)
        tl.emit(img)


def boss_fight(tl, name, lvl, tags, clips, snd, theme, stamp_txt=None, beat=0.5):
    """Varios cortes de una pelea con nombre, medidor de peligro y textos exagerados."""
    hard = lvl >= 8
    tl.snd(snd, 1.0)
    emb = Embers(50, (255, 90, 20)) if hard else None
    k = 0
    total = sum(round(d * FPS) for _, _, d in clips)
    for ci, (vid, st, d) in enumerate(clips):
        frames = clip(vid, st, d)
        if ci:
            tl.snd('golpe_seco', 0.7)
        for j, f in enumerate(frames):
            t = tl.t
            pulse = math.exp(-((t / beat) % 1) * 6)
            img = fx(f, zoom=1.03 + 0.05 * pulse, shake=(5 + 6 * pulse) if hard else 2,
                     flash=max(0, 0.7 - j / 4) if j < 4 else 0, chroma=int(5 * pulse) if hard else 0,
                     tint=theme, tint_a=0.10 if hard else 0.0)
            if emb:
                emb.draw(img)
            bars(img, 50)
            say(img, name, 96, 40 + text_img(name, 96).width / 2 - 20, 130, k, '#ffffff', theme, shake=2 if hard else 0, big=2.2)
            tag = tags[min(len(tags) - 1, k * len(tags) // total)]
            ktag = k - (k * len(tags) // total) * (total // len(tags))
            say(img, tag, 44, W / 2, H - 150, ktag - 4, '#ffe040', fp=BLACK, stroke=5, big=1.5)
            danger(img, lvl, k)
            if stamp_txt and k > total - 26:
                if k == total - 25:
                    tl.snd('sello', 1.0)
                stamp(img, stamp_txt, k - (total - 25), W - 300, 260, '#ff2020' if hard else '#40e040')
            tl.emit(img)
            k += 1


def easy_part(tl):
    section_card(tl, 'PRIMERO...', 'LAS MÁS FÁCILES', '(...O ESO CREES)', (0, 70, 20), (0, 110, 35), '#a0ff70', '#00a000', 2.0)
    m0 = tl.t
    boss_fight(tl, 'MONSTRO', 3, ['EL EXAMEN DE LOS RECLUTAS', 'SALTA... Y TE APLASTA'],
               [('presentacion_jefes', 1.4, 2.1), ('presentacion_jefes', 4.3, 1.4)], 'pisoton', (40, 200, 40), '¡PAN COMIDO!')
    boss_fight(tl, 'DUQUE DE LAS MOSCAS', 3, ['HUELE HORRIBLE', 'MANDA A SUS MOSCAS'],
               [('gameplay_isaac', 36, 1.6), ('gameplay_isaac', 39.5, 1.6)], 'zumbido_grave', (40, 200, 40), '¡FACILÍSIMO!')
    boss_fight(tl, 'BALDI', 6, ['SÓLO SON SUMAS...', 'SALTA LA CUERDA...'],
               [('pelea_baldi', 9.5, 1.8), ('pelea_baldi', 20.5, 1.5)], 'pregunta', (40, 200, 40))
    tl.mus('10_jefe_monstro', m0, tl.t - m0, 0, 0.7, 0.05, 0.05)
    # ...hasta que Baldi te atrapa
    tl.snd('chillido', 1.0)
    tl.snd('golpe_seco', 1.0)
    for j, f in enumerate(clip('pelea_baldi', 151.5, 1.7)):
        img = fx(f, zoom=1.1 + j * 0.012, shake=16, tint=(255, 0, 0), tint_a=0.35, chroma=8, flash=0.8 if j < 3 else 0)
        say(img, '¡¡¡TE ATRAPÉ!!!', 150, W / 2, H / 2, j, '#ff2a2a', '#000000', shake=8, big=3.5)
        tl.emit(img)


def warmup(tl):
    """Glitch: 'ESO FUE EL CALENTAMIENTO'."""
    tl.snd('interferencia', 1.0)
    tl.snd('zumbido_grave', 1.0)
    n = round(2.8 * FPS)
    noise_k = 0
    for i in range(n):
        img = Image.new('RGB', (W, H), 'black')
        if i < 10 or random.random() < 0.15:
            a = (np.random.rand(H // 4, W // 4) * 120).astype(np.uint8)
            img = Image.fromarray(a).resize((W, H), Image.NEAREST).convert('RGB')
            noise_k += 1
        if i < 42:
            say(img, 'ESO FUE SÓLO EL CALENTAMIENTO', 70, W / 2, H / 2, i - 8, '#ffffff', big=1.3, shake=2)
        else:
            if i == 42:
                tl.snd('explosion', 1.0)
                tl.snd('rugido', 0.9)
            say(img, 'AHORA...', 60, W / 2, H / 2 - 90, i - 42, '#ffffff', big=2)
            say(img, 'LO IMPOSIBLE', 150, W / 2, H / 2 + 30, i - 46, '#ff2a2a', '#ff6000', shake=7, big=3.5)
        img = fx(img, shake=8 if i >= 42 else 2, chroma=10 if (i % 7 < 2) else 0, flash=0.9 if i == 42 else 0, vig=0.4)
        tl.emit(img)


def hard_part(tl):
    m0 = tl.t
    section_card(tl, 'LAS BATALLAS', 'MÁS DIFÍCILES', 'QUE HAYAS VISTO EN TU VIDA', (60, 0, 0), (110, 0, 0), '#ff3030', '#ff9000', 1.8, 'presentacion_vs')
    R = (255, 40, 0)
    boss_fight(tl, 'DR. FETUS', 8, ['UNA TORRE INFINITA', '¡¡LLENA DE SIERRAS!!'],
               [('pelea_dr_fetus', 29, 1.8), ('pelea_dr_fetus', 153, 1.7)], 'pisoton_gigante', R)
    boss_fight(tl, 'CEREBRO MADRE', 9, ['EL SER MÁS INTELIGENTE', '¡¡DEL SÓTANO!!'],
               [('gameplay_isaac', 110.5, 1.8), ('gameplay_isaac', 114, 1.5)], 'laser', R)
    boss_fight(tl, 'SANS', 10, ['VAS A PASAR', 'UN MAL RATO', '¡¡GASTER BLASTERS!!'],
               [('pelea_sans', 35, 1.5), ('pelea_sans', 85.5, 1.5), ('pelea_sans', 106.3, 1.5)], 'sans_blaster_dispara', R, '¡IMPOSIBLE!')
    tl.snd('sans_blaster_carga', 0.8, -3.0)
    boss_fight(tl, 'EL DIABLO', 10, ['EL CASINO DEL INFIERNO', 'NUNCA PIERDE', '¡¡3 FORMAS!!'],
               [('pelea_diablo', 0.4, 1.4), ('pelea_diablo', 27, 1.5), ('pelea_diablo', 141, 1.6)], 'rayo_infernal', R, '¡IMPOSIBLE!')
    boss_fight(tl, 'FLOWEY', 10, ['TU MEJOR AMIGO...', '¡¡SE ROBA 6 ALMAS!!', 'Y CARGA SU PARTIDA'],
               [('pelea_flowey', 0.6, 1.3), ('pelea_flowey', 6.2, 0.5), ('pelea_flowey', 41, 1.5), ('pelea_flowey', 115, 1.6)],
               'interferencia', R, '¡¡IMPOSIBLE!!')
    tl.mus('28_jefe_satanas', m0, tl.t - m0, 0, 0.85, 0.02, 0.3)


def item_card(tl, it, n_frames, bg1, bg2):
    icon = Image.open(os.path.join(HERE, 'recursos', 'objetos', it['file'])).convert('RGBA')
    tl.snd('orbe', 0.8)
    for i in range(n_frames):
        img = rays(bg1, bg2, tl.f * 2.0)
        img = fx(img, shake=max(0, 8 - i * 2), flash=max(0, 0.5 - i / 4), vig=0.8)
        put(img, icon, W / 2, H / 2 - 50, slam(i, 4, 2.2) * (1 + 0.04 * math.sin(i * 0.6)), 1, math.sin(i * 0.4) * 6)
        say(img, it['name'].upper(), 74, W / 2, H - 170, i - 1, '#ffffff', '#000000', big=1.6)
        say(img, it['desc'], 34, W / 2, H - 100, i - 3, '#ffe040', fp=BLACK, stroke=4, big=1.2)
        tl.emit(img)


def items_part(tl):
    m0 = tl.t
    data = json.load(open(os.path.join(HERE, 'recursos', 'objetos', 'objetos.json'), encoding='utf8'))
    normal = [d for d in data if d['kind'] == 'normal']
    diablo = [d for d in data if d['kind'] == 'diablo']
    angel = [d for d in data if d['kind'] == 'angel']
    section_card(tl, 'ARMATE HASTA LOS DIENTES', '¡¡30 OBJETOS!!', 'CADA UNO CAMBIA TU PARTIDA', (90, 60, 0), (150, 100, 0), '#ffe040', '#ff8000', 1.7, 'objeto_conseguido')
    for j, f in enumerate(clip('gameplay_isaac', 9.3, 2.0)):
        img = fx(f, zoom=1.15 + j * 0.01, shake=3)
        say(img, '¡AGÁRRALOS TODOS!', 80, W / 2, 150, j - 4, '#ffe040', '#ff6000', big=2)
        tl.emit(img)
    for it in [normal[i] for i in (0, 3, 6, 7, 8, 9, 10, 12, 13, 15)]:
        item_card(tl, it, 11, (60, 40, 10), (100, 70, 20))
    # el cuarto del Diablo
    tl.snd('puerta_diablo', 1.0)
    for j, f in enumerate(clip('gameplay_isaac', 29.3, 1.8)):
        img = fx(f, zoom=1.2, shake=6, tint=(255, 0, 0), tint_a=0.15, flash=max(0, 0.8 - j / 4))
        say(img, 'PACTOS CON EL DIABLO', 90, W / 2, 140, j - 2, '#ff3030', '#000000', shake=3, big=2.4)
        say(img, 'PAGA CON TU VIDA...', 40, W / 2, H - 140, j - 10, '#ffffff', fp=BLACK, stroke=4)
        tl.emit(img)
    for it in diablo[:4]:
        item_card(tl, it, 10, (50, 0, 0), (100, 0, 0))
    # el cuarto del Ángel
    tl.snd('puerta_angel', 1.0)
    for j, f in enumerate(clip('gameplay_isaac', 53.5, 1.8)):
        img = fx(f, zoom=1.2, shake=3, tint=(255, 240, 160), tint_a=0.12, flash=max(0, 0.9 - j / 4))
        say(img, 'REGALOS DEL ÁNGEL', 90, W / 2, 140, j - 2, '#fff2a0', '#c08000', big=2.4)
        tl.emit(img)
    for it in angel[:4]:
        item_card(tl, it, 10, (150, 130, 70), (210, 190, 110))
    # todos los objetos de golpe
    icons = [Image.open(os.path.join(HERE, 'recursos', 'objetos', d['file'])).convert('RGBA').resize((112, 112), Image.LANCZOS) for d in data]
    tl.snd('explosion', 0.8)
    for i in range(round(2.0 * FPS)):
        img = rays((40, 30, 0), (75, 55, 0), i * 2)
        for j, ic in enumerate(icons):
            put(img, ic, 100 + (j % 10) * 120, 140 + (j // 10) * 140, slam(i - j // 3, 3, 2))
        img = fx(img, shake=4)
        say(img, '¡¡30 OBJETOS!!', 110, W / 2, H - 110, i - 14, '#ffe040', '#ff4000', shake=3, big=3)
        tl.emit(img)
    tl.mus('05_arena_retro', m0, tl.t - m0, 0, 0.75, 0.02, 0.2)


def soldiers_part(tl):
    m0 = tl.t
    section_card(tl, 'ELIGE A TU HÉROE', '¡¡19 SOLDADOS!!', 'CADA UNO CON SU ARMA', (0, 50, 10), (20, 90, 30), '#7dff4a', '#008000', 1.6, 'esposas')
    cols = [(30, 90, 30), (90, 30, 30), (30, 50, 110), (100, 80, 20), (70, 30, 100)]
    for si, (name, f, ref) in enumerate(SOLDADOS):
        path = soldier_path(f)
        c = cols[si % len(cols)]
        tl.snd('menu_elegir', 0.9)
        for i in range(10):
            img = rays(c, tuple(min(255, v + 45) for v in c), tl.f * 2)
            img = fx(img, shake=max(0, 6 - i), flash=max(0, 0.4 - i / 5), vig=0.8)
            spr = sheet_frame(path, 160, (tl.f // 2) % 8, 4, 440)
            put(img, spr, W / 2 - 230, H / 2 + 10, slam(i, 3, 1.6))
            say(img, name, 88, W / 2 + 250, H / 2 - 40, i - 1, '#ffffff', '#000000', big=1.2, maxw=560)
            say(img, ref, 40, W / 2 + 230, H / 2 + 50, i - 3, '#ffe040', fp=BLACK, stroke=4, big=1.2)
            say(img, f'{si + 1}/19', 36, W - 120, 90, 0, '#ffffff', fp=BLACK, stroke=4)
            tl.emit(img)
    # todos juntos marchando
    tl.snd('victoria', 0.7)
    for i in range(round(3.0 * FPS)):
        img = rays((10, 40, 10), (25, 70, 25), i)
        for j, (_, f, _) in enumerate(SOLDADOS):
            row = j // 10
            x = 80 + (j % 10) * 125 + row * 60
            y = 300 + row * 190
            spr = sheet_frame(soldier_path(f), 160, (i // 2 + j) % 8, 4, 190)
            put(img, spr, x, y + (math.sin(i * 0.5 + j) * 4), slam(i - j, 3, 1.8))
        img = fx(img, shake=3)
        say(img, '¡¡EL PELOTÓN VERDE!!', 100, W / 2, 110, i - 18, '#7dff4a', '#006000', shake=2, big=2.6)
        tl.emit(img)
    tl.mus('40_nivel_colinas_verdes', m0, tl.t - m0, 0, 0.75, 0.02, 0.4)


def rival_part(tl):
    """El rival mortal: ???, Isaac Oscuro."""
    # silencio, latidos
    lines = [('PERO TODOS ESOS JEFES...', 0, 1.9), ('...LE TIENEN MIEDO A UNO SOLO', 1.9, 2.2)]
    for i in range(round(4.1 * FPS)):
        t = i / FPS
        if i % 20 == 0:
            tl.snd('latido', 1.0)
        pulse = math.exp(-((i % 20) / 20) * 5)
        img = vignette(Image.new('RGB', (W, H), (int(70 * pulse), 0, 0)), 1)
        for s, a, d in lines:
            if a <= t < a + d:
                k = i - round(a * FPS)
                if k == 0:
                    tl.snd('texto_grave', 1.0)
                put(img, text_img(s, 60, '#e0e0e0', 5), W / 2, H / 2, 1 + k * 0.003, min(1, k / 6) * min(1, (a + d - t) * 4))
        tl.emit(img)
    m0 = tl.t
    # la tarjeta VS de ???
    tl.snd('presentacion_vs', 1.0)
    tl.snd('explosion', 0.8)
    for j, f in enumerate(clip('presentacion_jefes', 7.8, 2.8)):
        img = fx(f, zoom=1.05 + j * 0.004, shake=10 if j < 15 else 4, flash=max(0, 1 - j / 5), chroma=6 if j % 9 < 2 else 0)
        say(img, 'AMENAZA MÁXIMA', 100, W / 2, 110, j - 6, '#ff2020', '#000000', shake=4, big=2.6)
        tl.emit(img)
    # el sprite gigante con ojos rojos
    tl.snd('rugido', 1.0)
    tl.snd('temblor', 1.0)
    di = sheet(os.path.join(ROOT, 'sprites', 'jefe_isaac_oscuro.png'))
    emb = Embers(90, (255, 30, 30))
    for i in range(round(3.4 * FPS)):
        img = rays((20, 0, 0), (55, 0, 0), -i * 1.2)
        emb.draw(img)
        fr = di.crop(((i // 3 % 8) * 256, 0, (i // 3 % 8) * 256 + 256, 256))
        sc = 1.4 + i * 0.02
        glow = Image.new('RGBA', (360, 360), (0, 0, 0, 0))
        ImageDraw.Draw(glow).ellipse((60, 60, 300, 300), fill=(255, 0, 0, int(140 + 80 * math.sin(i * 0.5))))
        put(img, glow.filter(ImageFilter.GaussianBlur(40)), W / 2, H / 2 + 30, sc)
        put(img, fr, W / 2, H / 2 + 30, sc)
        img = fx(img, shake=10, chroma=4 if i % 10 < 3 else 0, flash=max(0, 0.8 - i / 5))
        say(img, 'EL RIVAL MORTAL', 120, W / 2, 100, i - 10, '#ff2020', '#ff8000', shake=5, big=3)
        if i == 10:
            tl.snd('explosion', 1.0)
        say(img, '???', 90, W / 2, H - 90, i - 30, '#ffffff', '#ff0000', shake=6, big=2)
        tl.emit(img)
    # gameplay contra él, cada vez más rojo
    caps = ['SE PARECE A TI...', 'LLORA COMO TÚ...', 'NUNCA SE RINDE...', '...¿ERES TÚ?']
    cuts = [('gameplay_isaac', 121, 1.5), ('gameplay_isaac', 128, 1.5), ('gameplay_isaac', 132.5, 1.5), ('gameplay_isaac', 136.5, 1.6)]
    for ci, (v, st, d) in enumerate(cuts):
        tl.snd('texto_grave', 1.0)
        tl.snd('golpe_seco', 0.8)
        for j, f in enumerate(clip(v, st, d)):
            img = fx(f, zoom=1.12 + j * 0.006, shake=6 + ci * 2, tint=(255, 0, 0), tint_a=0.18 + ci * 0.06,
                     chroma=3 + ci * 2, flash=max(0, 0.7 - j / 4))
            bars(img, 70)
            say(img, caps[ci], 96 if ci == 3 else 80, W / 2, H - 150, j - 2, '#ff3030' if ci == 3 else '#ffffff', '#000000', shake=ci * 2, big=1.8)
            tl.emit(img)
    # '???' final con glitch
    tl.snd('interferencia', 1.0)
    tl.snd('explosion', 1.0)
    for i in range(round(1.4 * FPS)):
        img = Image.new('RGB', (W, H), (20, 0, 0))
        fr = di.crop((0, 0, 256, 256))
        put(img, fr, W / 2 + random.uniform(-15, 15), H / 2, 2.6)
        img = fx(img, shake=14, chroma=14 if i % 4 < 2 else 0, flash=max(0, 1 - i / 4))
        say(img, '???', 220, W / 2, H / 2 + 200, i, '#ff0000', '#000000', shake=10, big=2)
        tl.emit(img)
    tl.mus('29_jefe_final_isaac_oscuro', m0, tl.t - m0, 0, 0.9, 0.02, 0.3)


def finale(tl):
    m0 = tl.t
    cuts = [('pelea_sans', 36), ('pelea_diablo', 64), ('pelea_flowey', 42.5), ('pelea_dr_fetus', 292), ('gameplay_isaac', 62),
            ('gameplay_isaac', 72), ('pelea_diablo', 112), ('gameplay_isaac', 100), ('pelea_sans', 108), ('pelea_flowey', 125),
            ('gameplay_isaac', 113), ('pelea_baldi', 30), ('gameplay_isaac', 50), ('pelea_diablo', 145), ('gameplay_isaac', 133)]
    for ci, (v, st) in enumerate(cuts):
        if ci % 2 == 0:
            tl.snd('golpe_seco', 0.8)
        for j, f in enumerate(clip(v, st, 0.3)):
            img = fx(f, zoom=1.15, shake=12, flash=0.6 if j == 0 else 0, chroma=6 if j < 2 else 0)
            tl.emit(img)
    tl.snd('explosion', 1.0)
    tl.snd('rugido', 0.7)
    emb = Embers(100)
    lines = [('¿TIENES LO QUE HAY QUE TENER?', 0), ('4 DIFICULTADES: CIVIL · RECLUTA · SOLDADO · VETERANO', 32), ('¡¡JUEGA YA EN TU NAVEGADOR!!', 56)]
    n = round(6.0 * FPS)
    for i in range(n):
        img = rays((25, 50, 10), (45, 85, 20), i * 0.7)
        emb.draw(img)
        fr = sheet_frame(soldier_path('isaac'), 160, (i // 3) % 4, 0, 330)
        put(img, fr, 190, 215, slam(i, 5, 2) * 0.8)
        dr = di_frame(i)
        put(img, dr, W - 190, 205, slam(i - 3, 5, 2))
        say(img, 'THE BINDING', 100, W / 2, 150, i, '#ffffff', '#ff4000', big=3)
        say(img, 'OF EPIC', 140, W / 2, 265, i - 3, '#7dff4a', '#008000', shake=3 if i < 30 else 1, big=3.4)
        for s, a in lines:
            size = 52 if s.startswith('¡¡') else 40 if s.startswith('¿') else 28
            y = {0: 395, 32: 455, 56: 535}[a]
            if i == a and a:
                tl.snd('pisoton', 0.9)
            say(img, s, size, W / 2, y, i - a, '#ffe040' if a == 56 else '#ffffff', '#ff2000' if a == 56 else None, fp=BLACK, stroke=5, big=1.6)
        img = fx(img, shake=max(1, 16 - i), flash=max(0, 1 - i / 5), dark=max(0, (i - (n - 15)) / 15))
        tl.emit(img)
    tl.mus('28_jefe_satanas', m0, tl.t - m0, 30, 0.85, 0.02, 1.2)


def di_frame(i):
    di = sheet(os.path.join(ROOT, 'sprites', 'jefe_isaac_oscuro.png'))
    c = (i // 3) % 8
    return di.crop((c * 256, 0, c * 256 + 256, 256))


# ---------------------------------------------------------------- audio
@lru_cache(maxsize=None)
def load_audio(path):
    raw = subprocess.run([FF, '-loglevel', 'error', '-i', path, '-f', 's16le', '-ac', '2', '-ar', str(SR), '-'],
                         capture_output=True).stdout
    return np.frombuffer(raw, np.int16).reshape(-1, 2).astype(np.float32) / 32768


def mix_audio(tl, path):
    total = int(tl.t * SR) + SR
    buf = np.zeros((total, 2), np.float32)

    def add(a, at):
        s = int(at * SR)
        if s >= total:
            return
        a = a[:total - s]
        buf[s:s + len(a)] += a

    for track, at, dur, src, gain, fi, fo in tl.music:
        a = load_audio(os.path.join(ROOT, 'musica', track + '.mp3'))
        n = int(dur * SR)
        seg = a[int(src * SR):int(src * SR) + n]
        if len(seg) < n:  # si la canción es más corta, se repite
            seg = np.concatenate([seg] + [a] * (n // max(1, len(a)) + 1))[:n]
        env = np.ones(len(seg), np.float32)
        nfi, nfo = int(fi * SR), int(fo * SR)
        if nfi:
            env[:nfi] = np.linspace(0, 1, nfi)
        if nfo:
            env[-nfo:] *= np.linspace(1, 0, nfo)
        add(seg * env[:, None] * gain, at)
    for name, at, gain in tl.sfx:
        add(load_audio(os.path.join(ROOT, 'sonidos', name + '.mp3')) * gain, at)
    buf = np.tanh(buf * 1.2) / np.tanh(1.2)
    with wave.open(path, 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((buf * 32000).astype(np.int16).tobytes())


# ---------------------------------------------------------------- todo junto
def main():
    tmp_v, tmp_a = OUT + '.video.mp4', OUT + '.audio.wav'
    tl = Timeline(tmp_v)
    print('Armando la publicidad...')
    intro(tl)
    m0 = tl.t
    title(tl)
    boss_wall(tl)
    tl.mus('21_jefe_dragon_del_fin', m0, tl.t - m0, 0, 0.8, 0.02, 0.1)
    easy_part(tl)
    warmup(tl)
    hard_part(tl)
    items_part(tl)
    soldiers_part(tl)
    rival_part(tl)
    finale(tl)
    tl.close()
    print(f'Video: {tl.t:.1f} s. Mezclando el audio...')
    mix_audio(tl, tmp_a)
    subprocess.run([FF, '-y', '-loglevel', 'error', '-i', tmp_v, '-i', tmp_a, '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
                    '-shortest', '-movflags', '+faststart', OUT], check=True)
    os.remove(tmp_v)
    os.remove(tmp_a)
    print('listo: videos_publisidad/' + os.path.basename(OUT))


if __name__ == '__main__':
    main()
