# Genera sprites/jefes_muerte.png: una fila de 12 cuadros (256x256) por jefe con su animación de muerte.
# Usa los cuadros de cada hoja de jefe (idle, daño, etc.) y les agrega efectos dibujados por código.
# Uso:  python generar_muertes_jefes.py        (necesita: pip install pillow numpy)
import math, os, json
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

DIR = os.path.dirname(os.path.abspath(__file__))
F, COLS, FPS = 256, 12, 10
PX, PY = 128, 140          # pivote (centro del cuerpo), igual que en las hojas de jefes
DT = 1 / FPS
OUT = (28, 16, 12, 255)    # color del contorno que usan los sprites
ORDER = ['monstro', 'duque_moscas', 'isaac_oscuro', 'rey_koopa', 'dragon_fin', 'dr_huevon', 'rey_fantasma', 'cerebro_madre',
         'gurdy', 'peep', 'viuda', 'pie_mama', 'satanas', 'rey_slime', 'rey_boo', 'nave_nodriza', 'ridley', 'wither', 'ganon', 'sans',
         'baldi', 'dr_fetus', 'diablo', 'flowey']

# ------------------------------------------------------------------ utilidades de imagen
def load(n): return Image.open(os.path.join(DIR, f'jefe_{n}.png')).convert('RGBA')
def fr(sheet, r, c): return sheet.crop((c * F, r * F, c * F + F, r * F + F))
def blank(): return Image.new('RGBA', (F, F), (0, 0, 0, 0))
def arr(img): return np.asarray(img).astype(np.float32)
def img(a): return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), 'RGBA')

def xform(im, s=1.0, sy=None, rot=0.0, dx=0.0, dy=0.0, px=PX, py=PY):
    """escala sobre (px,py), rota (grados, horario) y desplaza"""
    sx, sy = s, s if sy is None else sy
    t = math.radians(rot); c, sn = math.cos(t), math.sin(t)
    a, b, d, e = c / sx, sn / sx, -sn / sy, c / sy
    ox, oy = px + dx, py + dy
    m = (a, b, px - a * ox - b * oy, d, e, py - d * ox - e * oy)
    return im.convert('RGBa').transform((F, F), Image.AFFINE, m, resample=Image.BICUBIC).convert('RGBA')

def tint(im, rgb, k):
    a = arr(im); a[..., :3] = a[..., :3] * (1 - k) + np.array(rgb, np.float32) * k; return img(a)
def fade(im, k):
    a = arr(im); a[..., 3] *= k; return img(a)
def gray(im, k):
    a = arr(im); g = a[..., :3].mean(-1, keepdims=True); a[..., :3] = a[..., :3] * (1 - k) + g * k; return img(a)
def masked(im, m):
    a = arr(im); a[..., 3] *= m; return img(a)
def blur(im, r): return im.convert('RGBa').filter(ImageFilter.GaussianBlur(r)).convert('RGBA')
def comp(base, *tops):
    for t in tops: base.alpha_composite(t)
    return base

def edgefade(im, m=14):
    """apaga suavemente lo que se acerque al borde del cuadro: nada queda cortado en línea recta"""
    k = np.minimum(np.arange(F) / m, 1.0); k = np.minimum(k, k[::-1])
    a = arr(im); a[..., 3] *= k[None, :] * k[:, None]; return img(a)

YY, XX = np.mgrid[0:F, 0:F].astype(np.float32)
def ellmask(cx, cy, rx, ry, soft=2.0):
    d = np.sqrt(((XX - cx) / rx) ** 2 + ((YY - cy) / ry) ** 2)
    return np.clip((1 - d) * min(rx, ry) / soft, 0, 1)

def smooth_noise(seed, cell=10):
    rng = np.random.default_rng(seed)
    n = F // cell + 2
    small = Image.fromarray((rng.random((n, n)) * 255).astype(np.uint8), 'L')
    big = np.asarray(small.resize((n * cell, n * cell), Image.BICUBIC)).astype(np.float32)[:F, :F] / 255
    return np.clip(big * 0.8 + rng.random((F, F)) * 0.2, 0, 1)

# ------------------------------------------------------------------ capa de dibujo con antialias (supermuestreo)
class Layer:
    def __init__(s, ss=3):
        s.ss = ss; s.im = Image.new('RGBA', (F * ss, F * ss), (0, 0, 0, 0)); s.d = ImageDraw.Draw(s.im)
    def _p(s, pts): return [(x * s.ss, y * s.ss) for x, y in pts]
    def ell(s, x, y, rx, ry=None, fill=None, outline=None, w=0):
        ry = rx if ry is None else ry; k = s.ss
        s.d.ellipse([(x - rx) * k, (y - ry) * k, (x + rx) * k, (y + ry) * k], fill=fill, outline=outline, width=max(0, round(w * k)))
    def poly(s, pts, fill=None, outline=None, w=0):
        s.d.polygon(s._p(pts), fill=fill, outline=outline, width=max(0, round(w * s.ss)) if outline else 0)
    def line(s, pts, fill, w):
        s.d.line(s._p(pts), fill=fill, width=max(1, round(w * s.ss)), joint='curve')
    def get(s, b=0):
        out = s.im.convert('RGBa').resize((F, F), Image.LANCZOS)
        if b: out = out.filter(ImageFilter.GaussianBlur(b))
        return out.convert('RGBA')

def soft(puffs, b):
    """humo / brillos: cada nube se compone por separado (se mezclan bien) y luego se difumina"""
    L = blank()
    for x, y, rx, ry, col, al in puffs:
        p = Layer(1); p.ell(x, y, rx, ry, fill=col[:3] + (int(255 * al),)); L.alpha_composite(p.get())
    return blur(L, b)

def glow(x, y, r, col, al):
    """resplandor redondo (destello de explosión) que se desvanece hacia afuera"""
    a = np.zeros((F, F, 4), np.float32); a[..., :3] = col
    d = np.sqrt((XX - x) ** 2 + (YY - y) ** 2) / r
    a[..., 3] = 255 * al * np.clip(1 - d, 0, 1) ** 1.6
    return img(a)

def star(L, x, y, r, n, col, rot=0, inner=0.45, outline=None, w=0):
    pts = []
    for i in range(n * 2):
        rr = r if i % 2 == 0 else r * inner; t = rot + i * math.pi / n
        pts.append((x + math.cos(t) * rr, y + math.sin(t) * rr))
    L.poly(pts, fill=col, outline=outline, w=w)

# ------------------------------------------------------------------ partículas con física (vista cenital: z = altura)
def particles(seed, n, x, y, speed=(60, 220), vz=(90, 220), **kw):
    rng = np.random.default_rng(seed); out = []
    for i in range(n):
        a = rng.uniform(0, 2 * math.pi); s = rng.uniform(*speed)
        p = dict(x=x + rng.uniform(-10, 10), y=y + rng.uniform(-10, 10), vx=math.cos(a) * s, vy=math.sin(a) * s * 0.75,
                 vz=rng.uniform(*vz), spin=rng.uniform(-900, 900), k=rng.random(), i=i)
        p.update({k: (v(rng) if callable(v) else v) for k, v in kw.items()})
        out.append(p)
    return out

def ballistic(p, t, g=1100):
    tl = 2 * p['vz'] / g; tt = min(t, tl)
    h = max(0.0, p['vz'] * tt - g * tt * tt / 2)
    gx, gy = p['x'] + p['vx'] * tt, p['y'] + p['vy'] * tt
    # nunca salir del cuadro
    dx, dy = gx - PX, gy - PY - 20; d = math.hypot(dx, dy)
    if d > 100: gx, gy = PX + dx / d * 100, PY + 20 + dy / d * 100
    return gx, gy - h, h, t >= tl

# ------------------------------------------------------------------ grietas y fragmentos
def crack_paths(seed, cx, cy, n, length, jag=9, branch=True):
    rng = np.random.default_rng(seed); paths = []
    for i in range(n):
        a = i * 2 * math.pi / n + rng.uniform(-0.4, 0.4); pts = [(cx, cy)]; x, y = cx, cy
        steps = int(length / 10)
        for k in range(steps):
            a += rng.uniform(-0.6, 0.6) * 0.6; st = rng.uniform(7, 13)
            x += math.cos(a) * st + rng.uniform(-jag, jag) * 0.3; y += math.sin(a) * st + rng.uniform(-jag, jag) * 0.3
            pts.append((x, y))
            if branch and k == steps // 2:
                b = a + rng.choice([-1, 1]) * rng.uniform(0.6, 1.0); bx, by = x, y; bp = [(x, y)]
                for _ in range(steps // 2):
                    b += rng.uniform(-0.4, 0.4); bx += math.cos(b) * 9; by += math.sin(b) * 9; bp.append((bx, by))
                paths.append(bp)
        paths.append(pts)
    return paths

def draw_cracks(L, paths, frac, col, w):
    for pts in paths:
        k = max(2, int(len(pts) * frac))
        if frac > 0: L.line(pts[:k], col, w)

def make_shards(im, n, seed, region=None):
    rng = np.random.default_rng(seed)
    a = arr(im); A = a[..., 3] > 10
    if region is not None: A &= region > 0.5
    ys, xs = np.nonzero(A)
    idx = rng.choice(len(xs), n, replace=False); sx, sy = xs[idx].astype(np.float32), ys[idx].astype(np.float32)
    lab = ((XX[..., None] - sx) ** 2 + (YY[..., None] - sy) ** 2).argmin(-1)
    out = []
    for k in range(n):
        m = (lab == k) & A
        if m.sum() < 20: continue
        yy, xx = np.nonzero(m); cx, cy = xx.mean(), yy.mean()
        b = a.copy(); b[..., 3] = np.where(m, b[..., 3], 0)
        dx, dy = cx - PX, cy - PY; d = math.hypot(dx, dy) or 1
        out.append(dict(im=img(b), cx=cx, cy=cy, ux=dx / d, uy=dy / d, sp=rng.uniform(0.7, 1.3), rot=rng.uniform(-260, 260)))
    return out

def draw_shards(base, shards, t, speed, al=1.0, g=0.0):
    for s in shards:
        d = speed * t * s['sp']
        im = xform(s['im'], rot=s['rot'] * t, dx=s['ux'] * d, dy=s['uy'] * d + g * t * t, px=s['cx'], py=s['cy'])
        base.alpha_composite(fade(im, al) if al < 1 else im)
    return base

def shake(i, amp): return (amp if i % 2 else -amp)

# ==================================================================== JEFES
def monstro():
    S = load('monstro'); idle, scream, white, red = fr(S, 0, 0), fr(S, 1, 7), fr(S, 3, 0), fr(S, 3, 1)
    POP = 7
    chunks = particles(1, 11, PX, PY, speed=(90, 280), vz=(140, 260), r=lambda g: g.uniform(7, 13))
    for p in chunks:  # salen de toda la superficie del cuerpo, no de un punto
        p['x'] += p['vx'] / 280 * 45; p['y'] += p['vy'] / 280 * 40
    drops = particles(2, 26, PX, PY, speed=(120, 320), vz=(80, 200), r=lambda g: g.uniform(2.5, 5))
    teeth = particles(3, 5, PX, PY + 15, speed=(60, 200), vz=(160, 260))
    eye = particles(4, 1, PX - 10, PY - 25, speed=(140, 160), vz=(250, 251))[0]
    frames = []
    for i in range(COLS):
        f = blank()
        if i == 0: comp(f, white)                                                    # golpe final
        elif i == 1: comp(f, xform(red, 1.06, 0.92))                                 # se aplasta
        elif i < POP:                                                                # grita y se hincha
            k = (i - 2) / (POP - 3)
            body = tint(scream, (200, 40, 40), 0.15 + 0.45 * k)
            if i == POP - 1: body = tint(body, (255, 245, 235), 0.55)
            comp(f, xform(body, 1.04 + 0.24 * k, 1.0 + 0.2 * k, rot=shake(i, 3 + 3 * k), dx=shake(i, 2 + 3 * k)))
            if i >= 4:  # gotas de sudor de sangre
                L = Layer()
                for j in range(i - 2):
                    a = j * 2.1 + i * 0.3; r = 62 + 20 * k
                    L.ell(PX + math.cos(a) * r, PY + math.sin(a) * r * 0.9, 3.2, 4.2, fill=(160, 20, 20, 255), outline=OUT, w=1)
                comp(f, L.get())
        else:                                                                        # ¡revienta!
            t = (i - POP) * DT + 0.03
            if i <= POP + 1: comp(f, glow(PX, PY, 95 - 25 * (i - POP), (255, 210, 160), 0.85 - 0.35 * (i - POP)))
            if i == POP: comp(f, soft([(PX, PY, 70, 62, (180, 30, 30), 0.85), (PX, PY, 40, 36, (255, 230, 200), 0.9)], 4))
            L = Layer(); al = 1.0 if i < COLS - 2 else 0.55
            for p in drops:
                x, y, h, landed = ballistic(p, t)
                if landed: L.ell(x, y, p['r'] * 1.4, p['r'] * 0.8, fill=(120, 10, 10, int(255 * al)))
                else: L.ell(x, y, p['r'], fill=(170, 20, 20, int(255 * al)))
            for p in chunks:
                x, y, h, landed = ballistic(p, t)
                r = p['r']; sq = 0.75 if landed else 1.0
                L.ell(x, y, r * (2 - sq), r * sq, fill=(190, 135, 125, int(255 * al)), outline=OUT[:3] + (int(255 * al),), w=1.5)
                L.ell(x - r * 0.25, y - r * 0.25, r * 0.4, r * 0.3, fill=(150, 40, 40, int(200 * al)))
            for p in teeth:
                x, y, h, landed = ballistic(p, t); a = math.radians(p['spin'] * min(t, 0.4))
                pts = [(x + math.cos(a + q) * 6, y + math.sin(a + q) * 6) for q in (0, 2.3, 4.0)]
                L.poly(pts, fill=(250, 245, 230, int(255 * al)), outline=OUT, w=1)
            x, y, h, landed = ballistic(eye, t)                                       # un ojo sale rodando
            if landed: x += (t - 0.45) * 60
            L.ell(x, y, 9, fill=(250, 250, 250, int(255 * al)), outline=OUT, w=1.5); L.ell(x + 3, y + 1, 4, fill=(20, 15, 15, int(255 * al)))
            comp(f, L.get())
        frames.append(f)
    return frames, POP

def duque_moscas():
    S = load('duque_moscas'); idle, white, red = fr(S, 0, 0), fr(S, 3, 0), fr(S, 3, 1)
    POP = 7
    flies = particles(10, 22, PX, PY, speed=(90, 200), vz=(0, 1))
    guts = particles(11, 14, PX, PY, speed=(70, 220), vz=(120, 240), r=lambda g: g.uniform(5, 11))
    def fly(L, x, y, k, flap, al):
        a = int(255 * al)
        L.ell(x - 8, y - 7 - flap, 8, 5, fill=(220, 225, 235, int(170 * al)), outline=(60, 60, 70, a), w=1)
        L.ell(x + 8, y - 7 - flap, 8, 5, fill=(220, 225, 235, int(170 * al)), outline=(60, 60, 70, a), w=1)
        L.ell(x, y, 7.5, 6.5, fill=(25, 25, 28, a)); L.ell(x - 3, y - 1.5, 2, fill=(220, 40, 40, a)); L.ell(x + 3, y - 1.5, 2, fill=(220, 40, 40, a))
    frames = []
    for i in range(COLS):
        f = blank()
        if i == 0: comp(f, white)
        elif i == 1: comp(f, red)
        elif i < POP:                                         # las moscas de dentro empujan: se hincha y tiembla
            k = (i - 2) / (POP - 3)
            body = tint(idle, (150, 40, 30), 0.15 + 0.4 * k)
            if i == POP - 1: body = tint(body, (255, 240, 220), 0.5)
            comp(f, xform(body, 1.03 + 0.2 * k, 1.0 + 0.16 * k, dx=shake(i, 2 + 3 * k), rot=shake(i, 2 + 2 * k)))
            L = Layer()
            for j in range(i - 2):                            # algunas moscas ya se escapan
                p = flies[j]; d = 55 + 22 * (i - 2 - j)
                fly(L, PX + p['vx'] / 200 * d, PY + p['vy'] / 200 * d, j, 2 * (i % 2), 1)
            comp(f, L.get())
        else:                                                  # revienta en un enjambre
            t = (i - POP) * DT + 0.04
            if i <= POP + 1: comp(f, glow(PX, PY, 90 - 20 * (i - POP), (255, 220, 170), 0.8 - 0.35 * (i - POP)))
            puffs = [(PX + math.cos(j) * 30 * (1 + t * 3), PY + math.sin(j) * 24 * (1 + t * 3), 30 + 40 * t, 26 + 34 * t, (110, 80, 50), max(0, 0.75 - t * 1.4)) for j in range(6)]
            comp(f, soft(puffs, 5))
            L = Layer(); al = 1.0 if i < COLS - 1 else 0.5
            for p in guts:
                x, y, h, landed = ballistic(p, t); r = p['r']
                L.ell(x, y, r * (1.3 if landed else 1), r * (0.7 if landed else 1), fill=(100, 70, 40, int(255 * al)), outline=OUT, w=1.2)
            for p in flies:
                d = 30 + t * math.hypot(p['vx'], p['vy']) * 1.1
                x, y = PX + p['vx'] / 200 * d + math.sin(t * 20 + p['i']) * 4, PY + p['vy'] / 200 * d - t * 30
                fa = np.clip(1 - (math.hypot(x - PX, y - PY) - 70) / 45, 0, 1) * al
                if fa > 0.02: fly(L, x, y, p['i'], 2 * ((i + p['i']) % 2), fa)
            comp(f, L.get())
        frames.append(f)
    return frames, POP

def isaac_oscuro():
    S = load('isaac_oscuro'); idle, white, red = fr(S, 0, 0), fr(S, 3, 0), fr(S, 3, 1)
    POP = 6
    cracks = crack_paths(20, PX + 2, PY - 20, 7, 90)
    shards = make_shards(idle, 26, 21)
    a = arr(idle); redm = (a[..., 0] > 200) & (a[..., 1] < 110) & (a[..., 3] > 200)
    eyes_m = (redm & (YY < 134)).astype(np.float32)
    eyes = img(np.where(eyes_m[..., None] > 0, a, 0))
    frames = []
    for i in range(COLS):
        f = blank()
        if i == 0: comp(f, white)
        elif i == 1: comp(f, red)
        elif i < POP:                                         # se agrieta como un espejo y sale luz
            k = (i - 1) / (POP - 2)
            comp(f, xform(tint(idle, (255, 220, 200), 0.1 * k), 1.0, rot=shake(i, 2), dx=shake(i, 2)))
            G = Layer(); draw_cracks(G, cracks, k, (255, 200, 170, 255), 7); comp(f, fade(G.get(3), 0.9))
            L = Layer(); draw_cracks(L, cracks, k, (255, 250, 235, 255), 2.2); comp(f, L.get())
            if i == POP - 1: comp(f, glow(PX, PY - 20, 110, (255, 220, 200), 0.55))
        else:                                                  # estalla en fragmentos; sólo quedan los ojos
            t = (i - POP) * DT + 0.05
            if i <= POP + 1: comp(f, glow(PX, PY - 20, 115 - 30 * (i - POP), (255, 225, 205), 0.9 - 0.4 * (i - POP)))
            if i < POP + 5: draw_shards(f, shards, t, 260, al=max(0, 1 - t * 2.0), g=120)
            ek = 1.0 if i < 9 else [0.8, 0.5, 0.25][i - 9]                     # los ojos se apagan y se cierran
            e = xform(eyes, 1.0, 1.0 if i < 9 else [0.7, 0.4, 0.15][i - 9], dy=-6 * min(t, 0.3) * 3, py=PY - 20)
            comp(f, fade(glow(PX, PY - 20 - 6 * min(t, 0.3) * 3, 60, (255, 40, 40), 0.35 * ek), 1))
            comp(f, fade(tint(e, (60, 0, 0), 1 - ek), ek))
        frames.append(f)
    return frames, POP

def rey_koopa():
    S = load('rey_koopa'); white, red = fr(S, 3, 0), fr(S, 3, 1)
    dizzy = [fr(S, 4, 2), fr(S, 4, 3)]; shell = [fr(S, 2, c) for c in range(8)]; idle = fr(S, 0, 0)
    POP = 9
    cr = crack_paths(30, PX, PY, 3, 50, branch=False)
    split = np.clip((XX - (PX + 4 * np.sin(YY / 9))) * 1.0 + 0.5, 0, 1)   # corte en zigzag
    frames = []
    def stars(L, i, n=3, r=26, y=PY - 82):
        for j in range(n):
            a = i * 0.9 + j * 2 * math.pi / n
            star(L, PX + math.cos(a) * r * 1.4, y + math.sin(a) * r * 0.4, 7, 5, (255, 220, 60, 255), rot=a, outline=OUT, w=1)
    for i in range(COLS):
        f = blank()
        if i == 0: comp(f, white)
        elif i == 1: comp(f, red)
        elif i < 5:                                            # mareado: tambalea con estrellas
            comp(f, xform(dizzy[i % 2], 1.0, rot=[-8, 7, -5][i - 2], dy=[0, 0, 4][i - 2]))
            L = Layer(); stars(L, i); comp(f, L.get())
        elif i == 5:                                           # se mete en el caparazón (¡puf!)
            comp(f, xform(idle, 0.82, 0.7, dy=12))
            comp(f, fade(shell[0], 0.6))
            comp(f, soft([(PX + math.cos(j * 1.05) * 62, PY + 10 + math.sin(j * 1.05) * 40, 20, 16, (235, 235, 230), 0.8) for j in range(6)], 3))
        elif i < POP:                                          # el caparazón gira cada vez más lento y se raja
            comp(f, xform(shell[(i - 5) * 2 % 8], 1.0, rot=(i - 5) * 25))
            L = Layer(); draw_cracks(L, cr, (i - 5) / 3, OUT, 2.4); comp(f, L.get())
            comp(f, soft([(PX + math.cos(j * 2.1 + i) * 66, PY + 55, 14, 9, (220, 210, 190), 0.5) for j in range(3)], 3))
        else:                                                  # se parte en dos
            t = (i - POP) * DT + 0.05
            base = xform(shell[6], 1.0, rot=100)
            L0 = Layer(); draw_cracks(L0, cr, 1, OUT, 2.4); base = comp(base, L0.get())
            al = 1.0 if i < COLS - 1 else 0.6
            comp(f, fade(xform(masked(base, 1 - split), rot=-120 * t, dx=-150 * t, dy=25 * t), al))
            comp(f, fade(xform(masked(base, split), rot=120 * t, dx=150 * t, dy=25 * t), al))
            comp(f, soft([(PX, PY + 20, 50 + 30 * t, 26, (230, 225, 210), max(0, 0.7 - t * 2.2))], 6))
            L = Layer(); stars(L, i, 3, 20 + 30 * t, PY - 40 - 40 * t); comp(f, fade(L.get(), max(0, 1 - t * 2.5)))
        frames.append(f)
    return frames, POP

def dragon_fin():
    S = load('dragon_fin'); white, red = fr(S, 3, 0), fr(S, 3, 1); wing = [fr(S, 0, c) for c in range(8)]
    POP = 6
    nz = smooth_noise(40, 9)
    rng = np.random.default_rng(41); beams = [(rng.uniform(0, 2 * math.pi), rng.uniform(0.6, 1.0)) for _ in range(9)]
    motes = particles(42, 30, PX, PY, speed=(10, 70), vz=(0, 1))
    frames = []
    def rays(n, length, al):
        L = blank()
        for a, w in beams[:n]:
            ly = Layer(1); half = 0.07 * w
            ly.poly([(PX, PY), (PX + math.cos(a - half) * length, PY + math.sin(a - half) * length), (PX + math.cos(a + half) * length, PY + math.sin(a + half) * length)], fill=(255, 235, 255, 255))
            ray = arr(ly.get()); ray[..., 3] *= np.clip(1 - np.sqrt((XX - PX) ** 2 + (YY - PY) ** 2) / length, 0, 1) * al
            L.alpha_composite(img(ray))
        return blur(L, 2)
    for i in range(COLS):
        f = blank()
        if i == 0: comp(f, white)
        elif i == 1: comp(f, red)
        elif i < POP:                                     # aletea sin control y le salen rayos de luz
            k = (i - 2) / (POP - 3)
            comp(f, rays(2 + i * 2, 80 + 30 * k, 0.6 + 0.3 * k))
            comp(f, xform(tint(wing[(i * 3) % 8], (230, 150, 255), 0.15 + 0.35 * k), 1.0 + 0.06 * k, rot=shake(i, 5)))
            comp(f, glow(PX + 50, PY, 40, (220, 120, 255), 0.4 + 0.4 * k))
        else:                                             # se deshace en polvo morado
            t = (i - POP) / (COLS - POP - 1)
            if i < COLS - 2: comp(f, rays(9, 115, 0.9 * (1 - t)))
            body = arr(tint(wing[i % 8], (210, 120, 255), 0.5 + 0.3 * t))
            th = 0.08 + t * 0.95
            keep = nz > th
            edge = (nz > th) & (nz < th + 0.08)
            body[..., :3] = np.where(edge[..., None], [255, 200, 255], body[..., :3])
            body[..., 3] *= keep
            comp(f, xform(img(body), 1.0 + 0.08 * t))
            L = Layer()
            for p in motes:
                d = (i - POP + 1) * 9 * (0.5 + p['k']); x = p['x'] + p['vx'] / 70 * d * 3; y = p['y'] + p['vy'] / 70 * d * 3 - d * 1.5
                a = 1 - t * 0.9 if p['i'] < 10 + (i - POP) * 4 else 0
                if a > 0: L.ell(x, y, 2 + 2 * p['k'], fill=(200, 110, 255, int(255 * a)))
            comp(f, L.get(1))
        frames.append(f)
    return frames, POP

def dr_huevon():
    S = load('dr_huevon'); idle, white, red = fr(S, 0, 0), fr(S, 3, 0), fr(S, 3, 1)
    POP = 7
    doc = masked(idle, np.clip((123 - YY) / 3, 0, 1))                     # el doctor sin la nave
    debris = particles(50, 14, PX, PY + 10, speed=(80, 260), vz=(150, 280), w=lambda g: g.uniform(6, 12))
    rng = np.random.default_rng(51)
    frames = []
    def sparks(L, i, n):
        for j in range(n):
            x = PX + rng.uniform(-60, 60); y = PY + rng.uniform(-5, 25)
            star(L, x, y, rng.uniform(5, 9), 4, (255, 240, 120, 255), rot=rng.uniform(0, 3), inner=0.3)
    for i in range(COLS):
        f = blank()
        if i == 0: comp(f, white)
        elif i == 1: comp(f, red)
        elif i < POP:                                     # la nave falla: humo, chispas, se ladea y cae
            k = (i - 2) / (POP - 3)
            sm = [(PX - 30 + j * 25, PY + 10 - j * 6 - 18 * k * j, 14 + 6 * j + 8 * k, 12 + 5 * j, (60, 60, 60), 0.75) for j in range(1 + i // 2)]
            comp(f, soft(sm, 4))
            body = tint(idle, (40, 30, 30), 0.25 * k)
            if i == POP - 1: body = tint(body, (255, 245, 230), 0.6)
            comp(f, xform(body, 1.0 - 0.04 * k, rot=[0, 7, -9, 12, 16][i - 2], dx=shake(i, 2), dy=6 * k))
            L = Layer()
            sparks(L, i, 2 + i)
            if i >= 4:
                for j in range(i - 3): L.ell(PX - 40 + j * 30, PY + 12, 8, 6, fill=(255, 140, 30, 230))
            comp(f, L.get())
        else:                                             # explota; el doctor sale volando chamuscado
            t = (i - POP) * DT + 0.04
            fire = max(0, 1 - t * 2.5)
            comp(f, soft([(PX + math.cos(j * 1.3) * 30 * (1 + t * 3), PY + 10 + math.sin(j * 1.3) * 22 * (1 + t * 3), 30 + 50 * t, 26 + 40 * t, (55, 50, 50), max(0, 0.8 - t * 1.1)) for j in range(6)], 6))
            if fire > 0:
                comp(f, glow(PX, PY + 5, 115, (255, 170, 60), 0.9 * fire))
                comp(f, soft([(PX + math.cos(j * 1.05) * 34 * (1 + t * 2), PY + 5 + math.sin(j * 1.05) * 26 * (1 + t * 2), 30 + 20 * t, 26 + 16 * t, (255, 140 + 20 * (j % 3), 40), fire) for j in range(6)]
                             + [(PX, PY + 5, 40, 34, (255, 245, 190), fire)], 4))
            L = Layer(); al = 1.0 if i < COLS - 1 else 0.5
            for p in debris:
                x, y, h, landed = ballistic(p, t); w = p['w']; a = math.radians(p['spin'] * min(t, 0.5))
                pts = [(x + math.cos(a + q) * w * (1 if q < 3 else 0.6), y + math.sin(a + q) * w * 0.7) for q in (0, 1.4, 3.1, 4.5)]
                L.poly(pts, fill=(170, 170, 180, int(255 * al)), outline=OUT, w=1.2)
            comp(f, L.get())
            if i >= POP + 1:                              # escapa hacia arriba y se aleja
                u = (i - POP - 1) / (COLS - POP - 2)
                d = tint(doc, (40, 30, 25), 0.35)
                comp(f, fade(xform(d, 1 - 0.55 * u, rot=-25 * u, dx=40 * u, dy=-30 - 25 * u, py=95), 1 - 0.85 * u ** 2))
        frames.append(f)
    return frames, POP

def rey_fantasma():
    S = load('rey_fantasma'); idle = fr(S, 0, 0); old = [fr(S, 4, c) for c in range(4)]
    POP = 6
    a = arr(idle); gold = ((a[..., 0] > 200) & (a[..., 1] > 150) & (a[..., 2] < 90)).astype(np.uint8) * 255
    gm = np.asarray(Image.fromarray(gold, 'L').filter(ImageFilter.MaxFilter(5))).astype(np.float32) / 255
    body_red = (a[..., 0] > 170) & (a[..., 1] < 90) & (a[..., 2] < 90)
    crown = masked(idle, gm * (~body_red) * (YY < 76))
    frames = []
    def eyes(L, x, y, look, al):
        A = int(255 * al)
        for s in (-1, 1):
            L.ell(x + s * 13, y, 9, 11, fill=(255, 255, 255, A), outline=OUT[:3] + (A,), w=1.5)
            L.ell(x + s * 13 + look * 4, y + 2, 4.5, 5.5, fill=(40, 60, 230, A))
    for i in range(COLS):
        f = blank()
        if i < 4: comp(f, xform(old[i], 1.0 + 0.03 * (i % 2), 1.0 - 0.03 * (i % 2), dx=shake(i, 3)))   # asustado, parpadea azul
        elif i < POP:                                          # se encoge de miedo antes de reventar
            k = i - 3
            comp(f, xform(old[1 + 2 * (i % 2)], 1.0 + 0.12 * k, 1.0 - 0.14 * k, dy=8 * k, py=200))
        else:
            t = (i - POP) * DT
            comp(f, soft([(PX + math.cos(j * 1.25) * 28 * (1 + t * 3), PY + math.sin(j * 1.25) * 22 * (1 + t * 3), 36 + 30 * t, 32 + 26 * t, (190, 160, 255), max(0, 0.9 - t * 1.5)) for j in range(5)] + [(PX, PY, 60, 55, (215, 200, 255), max(0, 0.9 - t * 2.2))], 5))
            # la corona salta y cae al suelo con un rebote
            T = i - POP
            cy = [-18, -36, -6, 122, 106, 122][T]; cr = [0, -80, -190, -335, -350, -342][T]; cx = [-4, -10, -18, -26, -30, -32][T]
            comp(f, xform(crown, 1.0, rot=cr, dx=cx, dy=cy, px=128, py=60))
            # los ojos huyen
            L = Layer(); ex, ey = PX + [0, 10, 30, 52, 74, 90][min(T, 5)], PY - 10 - [0, 4, 10, 18, 26, 32][min(T, 5)]
            ea = [1, 1, 1, 0.8, 0.45, 0][min(T, 5)]
            if ea > 0: eyes(L, ex, ey, 1, ea)
            comp(f, L.get())
        frames.append(f)
    return frames, POP

def cerebro_madre():
    S = load('cerebro_madre'); idle, cracked, white, red = fr(S, 0, 0), fr(S, 2, 0), fr(S, 3, 0), fr(S, 3, 1)
    POP = 5
    bm = ellmask(128, 136, 70, 54)
    brain = masked(idle, bm)
    jar = masked(cracked, (1 - bm) * (YY < 192))
    base = masked(idle, (YY >= 192).astype(np.float32))
    shards = make_shards(jar, 22, 60)
    cr = crack_paths(61, 150, 100, 6, 70)
    drops = particles(62, 18, PX, PY + 40, speed=(60, 200), vz=(60, 160), r=lambda g: g.uniform(3, 7))
    frames = []
    for i in range(COLS):
        f = blank()
        if i == 0: comp(f, white)
        elif i == 1: comp(f, red)
        elif i < POP:                                      # el frasco se raja y gotea
            k = (i - 1) / (POP - 2)
            comp(f, xform(cracked, 1.0, dx=shake(i, 2)))
            L = Layer(); draw_cracks(L, cr, k, (235, 250, 255, 255), 2); comp(f, L.get())
            L = Layer()
            for j in range(i - 1): L.ell(PX - 30 + j * 28, PY + 62 + 6 * j, 4, 6, fill=(120, 230, 90, 240), outline=OUT, w=1)
            comp(f, L.get())
        else:                                              # estalla el vidrio, se derrama el líquido y el cerebro se marchita
            t = (i - POP) * DT + 0.04; u = (i - POP) / (COLS - POP - 1)
            puddle = min(1, t * 3)
            comp(f, soft([(PX, PY + 62, 40 + 55 * puddle, 12 + 14 * puddle, (90, 200, 70), 0.8 * (1 - 0.4 * u))], 2))
            comp(f, base)
            L = Layer()
            for p in drops:
                x, y, h, landed = ballistic(p, t)
                if not landed: L.ell(x, y, p['r'], fill=(130, 235, 100, 240), outline=OUT, w=1)
            comp(f, L.get())
            sq = 1 - 0.38 * u
            br = tint(gray(brain, 0.5 * u), (90, 60, 70), 0.35 * u)
            comp(f, xform(br, 1 - 0.22 * u, sq, dy=18 * min(1, t * 4), py=190 - 0))
            if u > 0.35:                                   # el ojo se cierra
                L = Layer(); ey = 145 + 18 * min(1, t * 4) - (145 - 190) * (1 - sq) * -1
                ey = 190 - (190 - 145) * sq + 18 * min(1, t * 4)
                ex = PX - 1
                L.ell(ex, ey, 21 * (1 - 0.22 * u), 13 * sq, fill=(150, 100, 115, 255), outline=OUT, w=1.5)
                L.line([(ex - 16, ey + 2), (ex, ey + 5), (ex + 16, ey + 2)], OUT, 1.6)
                comp(f, L.get())
            if i < COLS - 1: draw_shards(f, shards, t, 300, al=max(0, 1 - t * 2.2), g=200)
            if i == POP: comp(f, glow(PX, PY, 100, (230, 255, 240), 0.6))
            if i == COLS - 1: f = fade(f, 0.85)
        frames.append(f)
    return frames, POP

# ==================================================================== JEFES NUEVOS (hojas exportadas con sprites/exportar_jefes.js)
def swell(body, i, pop, col, s=0.24):
    """tiembla y se hincha antes de reventar (cuadros 2..pop-1)"""
    k = (i - 2) / max(1, pop - 3)
    b = tint(body, col, 0.15 + 0.45 * k)
    if i == pop - 1: b = tint(b, (255, 245, 235), 0.55)
    return xform(b, 1.03 + s * k, 1.0 + s * 0.8 * k, rot=shake(i, 2 + 3 * k), dx=shake(i, 2 + 3 * k))

def gore(t, chunks, drops, chunk_col, drop_col, al=1.0):
    """trozos y gotas que salen volando y caen al suelo"""
    L = Layer()
    for p in drops:
        x, y, h, landed = ballistic(p, t)
        L.ell(x, y, p['r'] * (1.4 if landed else 1), p['r'] * (0.8 if landed else 1), fill=drop_col + (int(255 * al),))
    for p in chunks:
        x, y, h, landed = ballistic(p, t); r = p['r']; sq = 0.75 if landed else 1.0
        L.ell(x, y, r * (2 - sq), r * sq, fill=chunk_col + (int(255 * al),), outline=OUT[:3] + (int(255 * al),), w=1.5)
    return L.get()

def fly_bug(L, x, y, flap, al):
    a = int(255 * al)
    for s in (-1, 1): L.ell(x + s * 8, y - 7 - flap, 8, 5, fill=(220, 225, 235, int(170 * al)), outline=(60, 60, 70, a), w=1)
    L.ell(x, y, 7.5, 6.5, fill=(25, 25, 28, a)); L.ell(x - 3, y - 1.5, 2, fill=(220, 40, 40, a)); L.ell(x + 3, y - 1.5, 2, fill=(220, 40, 40, a))

def dissolve(body, nz, th, edge):
    """se deshace como polvo: desaparece donde el ruido es menor que th, con borde brillante"""
    a = arr(body); keep = nz > th; rim = (nz > th) & (nz < th + 0.08)
    a[..., :3] = np.where(rim[..., None], edge, a[..., :3]); a[..., 3] *= keep
    return img(a)

def motes(L, ps, i, pop, col, up=1.5, spread=3, al=1.0):
    for p in ps:
        d = (i - pop + 1) * 9 * (0.5 + p['k']); x = p['x'] + p['vx'] / 70 * d * spread; y = p['y'] + p['vy'] / 70 * d * spread - d * up
        if al > 0: L.ell(x, y, 2 + 2 * p['k'], fill=col + (int(255 * al),))

def boom(f, i, pop, col=(255, 210, 160), r=95):
    if i <= pop + 1: comp(f, glow(PX, PY, r - 25 * (i - pop), col, 0.85 - 0.35 * (i - pop)))

def gurdy():
    S = load('gurdy'); idle, white, red = fr(S, 0, 0), fr(S, 3, 0), fr(S, 3, 1)
    POP = 7
    chunks = particles(101, 14, PX, PY, speed=(90, 280), vz=(140, 260), r=lambda g: g.uniform(7, 13))
    drops = particles(102, 24, PX, PY, speed=(120, 320), vz=(80, 200), r=lambda g: g.uniform(3, 6))
    flies = particles(103, 12, PX, PY, speed=(90, 200), vz=(0, 1))
    frames = []
    for i in range(COLS):
        f = blank()
        if i == 0: comp(f, white)
        elif i == 1: comp(f, red)
        elif i < POP:                                   # las pústulas se inflan y empiezan a reventar
            comp(f, swell(idle, i, POP, (220, 60, 60), 0.1))
            if i >= 4:
                L = Layer()
                for j, (x, y) in enumerate([(41, 140), (210, 122), (83, 71), (188, 176), (56, 179)][:i - 3]):
                    L.ell(x, y, 10 + 3 * (i - 4), fill=(255, 240, 150, 230)); L.ell(x, y, 5, fill=(255, 255, 220, 255))
                comp(f, blur(L.get(), 1))
        else:                                           # revienta en carne, pus y moscas
            t = (i - POP) * DT + 0.03; boom(f, i, POP, (255, 220, 170), 110)
            al = 1.0 if i < COLS - 2 else 0.55
            comp(f, gore(t, chunks, drops, (200, 110, 100), (220, 190, 60), al))
            L = Layer()
            for p in flies:
                d = 30 + t * 220; x, y = PX + p['vx'] / 200 * d, PY + p['vy'] / 200 * d - t * 40
                fa = np.clip(1 - (math.hypot(x - PX, y - PY) - 70) / 45, 0, 1) * al
                if fa > 0.02: fly_bug(L, x, y, 2 * ((i + p['i']) % 2), fa)
            comp(f, L.get())
        frames.append(f)
    return frames, POP

def peep():
    S = load('peep'); idle, cry, white, red = fr(S, 0, 0), fr(S, 1, 3), fr(S, 3, 0), fr(S, 3, 1)
    POP = 7
    drops = particles(111, 30, PX, PY, speed=(120, 320), vz=(80, 220), r=lambda g: g.uniform(3, 7))
    eyes = particles(112, 2, PX, PY - 20, speed=(150, 170), vz=(260, 280))
    eyes[0]['vx'], eyes[1]['vx'] = -abs(eyes[0]['vx']), abs(eyes[1]['vx'])
    frames = []
    for i in range(COLS):
        f = blank()
        if i == 0: comp(f, white)
        elif i == 1: comp(f, red)
        elif i < POP:                                   # llora a mares y se hincha
            comp(f, swell(cry, i, POP, (240, 200, 40)))
            L = Layer()
            for j in range(2 * (i - 1)):
                a = j * 1.3 + i * 0.4; L.ell(PX + math.cos(a) * 70, PY + 30 + math.sin(a) * 20, 3.5, 4.5, fill=(120, 180, 255, 230))
            comp(f, L.get())
        else:                                           # ¡splash! un charco amarillo y los ojos salen rodando
            t = (i - POP) * DT + 0.03; boom(f, i, POP, (255, 240, 170))
            pud = min(1, t * 3); al = 1.0 if i < COLS - 2 else 0.55
            comp(f, soft([(PX, PY + 40, 40 + 50 * pud, 14 + 14 * pud, (230, 200, 40), 0.75 * al)], 3))
            comp(f, gore(t, [], drops, (0, 0, 0), (235, 205, 50), al))
            L = Layer()
            for e in eyes:
                x, y, h, landed = ballistic(e, t)
                if landed: x += math.copysign((t - 0.48) * 50, e['vx'])
                L.ell(x, y, 11, fill=(250, 250, 250, int(255 * al)), outline=OUT, w=1.5); L.ell(x + math.copysign(4, e['vx']), y + 1, 5, fill=(20, 15, 15, int(255 * al)))
            comp(f, L.get())
        frames.append(f)
    return frames, POP

def viuda():
    S = load('viuda'); idle, white, red = fr(S, 2, 0), fr(S, 3, 0), fr(S, 3, 1)
    POP = 7
    nz = smooth_noise(121, 8)
    spiders = particles(122, 10, PX, PY, speed=(80, 160), vz=(0, 1))
    frames = []
    for i in range(COLS):
        f = blank()
        if i == 0: comp(f, white)
        elif i == 1: comp(f, red)
        elif i < POP:                                   # se da vuelta panza arriba y patalea
            k = (i - 2) / (POP - 3)
            comp(f, xform(tint(idle, (120, 60, 120), 0.3 * k), 1.0, 1.0 - 0.25 * k, rot=180 * min(1, k * 1.6) + shake(i, 6), dy=10 * k))
        else:                                           # se hace polvo oscuro y huyen las arañitas
            t = (i - POP) / (COLS - POP - 1)
            body = xform(tint(idle, (90, 50, 90), 0.45), 1.0, 0.75, rot=180, dy=10)
            comp(f, soft([(PX, PY + 10, 60 + 40 * t, 40 + 26 * t, (40, 25, 45), 0.7 * (1 - t))], 6))
            comp(f, dissolve(body, nz, 0.1 + t * 0.95, [200, 120, 220]))
            L = Layer(); al = 1 - t * 0.7
            for p in spiders:
                d = 20 + (i - POP + 1) * 22; x, y = PX + p['vx'] / 160 * d, PY + 20 + p['vy'] / 160 * d
                if math.hypot(x - PX, y - PY - 20) > 105: continue
                for s in (-1, 1):
                    for q in range(3): L.line([(x, y), (x + s * 7, y - 4 + q * 4 + (i % 2) * 2), (x + s * 10, y + q * 4)], (20, 12, 20, int(255 * al)), 1.4)
                L.ell(x, y, 5, 4, fill=(30, 20, 30, int(255 * al)))
            comp(f, L.get())
        frames.append(f)
    return frames, POP

def pie_mama():
    S = load('pie_mama'); idle, white, red = fr(S, 0, 0), fr(S, 3, 0), fr(S, 3, 1)
    POP = 6
    dust = particles(131, 14, PX, PY + 40, speed=(40, 140), vz=(0, 1))
    frames = []
    for i in range(COLS):
        f = blank()
        if i == 0: comp(f, white)
        elif i == 1: comp(f, red)
        elif i < POP:                                   # los dedos se encogen de dolor y tiembla
            k = (i - 2) / (POP - 3)
            comp(f, xform(tint(idle, (200, 60, 60), 0.4 * k), 1.0 - 0.05 * k, 1.0 + 0.05 * k, rot=shake(i, 4), dx=shake(i, 3)))
        else:                                           # se retira hacia arriba dejando una nube de polvo
            t = (i - POP) / (COLS - POP - 1)
            puffs = [(p['x'] + p['vx'] * t * 0.9, p['y'] + p['vy'] * t * 0.5, 16 + 20 * t, 10 + 12 * t, (160, 140, 120), 0.8 * (1 - t)) for p in dust]
            comp(f, soft(puffs, 4))
            comp(f, fade(xform(idle, 1.0 - 0.3 * t, dy=-190 * t * t - 20 * t), 1 - t ** 1.5))
        frames.append(f)
    return frames, POP

def satanas():
    S = load('satanas'); idle, white, red = fr(S, 0, 0), fr(S, 3, 0), fr(S, 3, 1)
    POP = 6
    cracks = crack_paths(141, PX, PY - 20, 8, 95)
    nz = smooth_noise(142, 9)
    embers = particles(143, 34, PX, PY, speed=(10, 70), vz=(0, 1))
    frames = []
    for i in range(COLS):
        f = blank()
        if i == 0: comp(f, white)
        elif i == 1: comp(f, red)
        elif i < POP:                                   # se agrieta con luz del infierno
            k = (i - 1) / (POP - 2)
            comp(f, xform(tint(idle, (255, 120, 40), 0.15 * k), 1.0, rot=shake(i, 3), dx=shake(i, 2)))
            G = Layer(); draw_cracks(G, cracks, k, (255, 140, 40, 255), 8); comp(f, fade(G.get(3), 0.9))
            L = Layer(); draw_cracks(L, cracks, k, (255, 240, 180, 255), 2.5); comp(f, L.get())
        else:                                           # arde y se deshace en ceniza y brasas
            t = (i - POP) / (COLS - POP - 1); boom(f, i, POP, (255, 150, 60), 120)
            body = tint(idle, (60, 20, 10), 0.5 + 0.4 * t)
            comp(f, dissolve(body, nz, 0.08 + t * 0.95, [255, 180, 60]))
            L = Layer(); motes(L, embers, i, POP, (255, 120, 30), al=1 - t * 0.8); comp(f, L.get(1))
        frames.append(f)
    return frames, POP

def rey_slime():
    S = load('rey_slime'); idle, white, red = fr(S, 0, 0), fr(S, 3, 0), fr(S, 3, 1)
    POP = 6
    cm = np.clip((101 - YY) / 3, 0, 1)                                     # la corona es todo lo que está sobre la gelatina
    crown, body = masked(idle, cm), masked(idle, 1 - cm)
    blobs = particles(151, 10, PX, PY + 20, speed=(80, 200), vz=(120, 220), r=lambda g: g.uniform(6, 11))
    frames = []
    for i in range(COLS):
        f = blank()
        if i == 0: comp(f, white)
        elif i == 1: comp(f, red)
        elif i < POP:                                   # tiembla como gelatina
            k = (i - 2) / (POP - 3); w = 0.12 * (1 if i % 2 else -1) * (1 - 0.3 * k)
            comp(f, xform(idle, 1.0 + w, 1.0 - w, py=172))
        else:                                           # se derrite en un charco; la corona cae y rebota
            t = (i - POP) * DT; u = (i - POP) / (COLS - POP - 1)
            comp(f, soft([(PX, PY + 32, 70 + 30 * u, 18 + 6 * u, (50, 100, 220), 0.85 * (1 - 0.4 * u))], 3))
            comp(f, fade(xform(body,1.0 + 0.6 * u, max(0.08, 1 - 0.95 * u), py=172), 1 - 0.6 * u))
            L = Layer(); al = 1 - 0.5 * u
            for p in blobs:
                x, y, h, landed = ballistic(p, t + 0.02)
                L.ell(x, y, p['r'] * (1.4 if landed else 1), p['r'] * (0.7 if landed else 1), fill=(70, 130, 240, int(230 * al)), outline=(12, 34, 96, int(255 * al)), w=1.2)
            comp(f, L.get())
            T = i - POP; cy = [-20, -40, -10, 52, 40, 52][T]; cr = [0, -60, -150, -260, -250, -255][T]
            comp(f, xform(crown, 1.0, rot=cr, dx=[0, 6, 14, 22, 26, 28][T], dy=cy, px=PX, py=84))
        frames.append(f)
    return frames, POP

def rey_boo():
    S = load('rey_boo'); shy = [fr(S, 1, c) for c in range(4)]; idle = fr(S, 0, 0)
    POP = 6
    a = arr(idle); gold = ((a[..., 0] > 180) & (a[..., 1] > 140) & (a[..., 2] < 110) & (YY < 90)).astype(np.uint8) * 255
    crown = masked(idle, np.asarray(Image.fromarray(gold, 'L').filter(ImageFilter.MaxFilter(7))).astype(np.float32) / 255)
    frames = []
    for i in range(COLS):
        f = blank()
        if i < 4: comp(f, xform(tint(shy[i], (150, 170, 255), 0.25 * (i % 2)), 1.0 + 0.03 * (i % 2), 1.0 - 0.03 * (i % 2), dx=shake(i, 3)))  # avergonzado, tiembla
        elif i < POP: comp(f, fade(xform(shy[1], 1.0 + 0.1 * (i - 3), 1.0 - 0.12 * (i - 3)), 1 - 0.25 * (i - 3)))
        else:                                           # se esfuma en humo; la corona cae
            t = (i - POP) * DT
            comp(f, soft([(PX + math.cos(j * 1.25) * 28 * (1 + t * 3), PY + math.sin(j * 1.25) * 22 * (1 + t * 3), 36 + 30 * t, 32 + 26 * t, (235, 235, 250), max(0, 0.9 - t * 1.5)) for j in range(5)]
                         + [(PX, PY, 60, 55, (250, 250, 255), max(0, 0.9 - t * 2.2))], 5))
            T = i - POP
            comp(f, xform(crown, 1.0, rot=[0, -80, -190, -335, -350, -342][T], dx=[-4, -10, -18, -26, -30, -32][T], dy=[-18, -36, -6, 112, 96, 112][T], px=128, py=60))
        frames.append(f)
    return frames, POP

def nave_nodriza():
    S = load('nave_nodriza'); idle, white, red = fr(S, 0, 0), fr(S, 3, 0), fr(S, 3, 1)
    POP = 7
    debris = particles(161, 14, PX, PY + 10, speed=(80, 260), vz=(150, 280), w=lambda g: g.uniform(6, 12))
    rng = np.random.default_rng(162)
    frames = []
    for i in range(COLS):
        f = blank()
        if i == 0: comp(f, white)
        elif i == 1: comp(f, red)
        elif i < POP:                                   # echa humo y chispas, se ladea
            k = (i - 2) / (POP - 3)
            comp(f, soft([(PX - 40 + j * 30, PY - 10 - 16 * k * j, 14 + 6 * j, 12 + 5 * j, (60, 60, 60), 0.75) for j in range(1 + i // 2)], 4))
            body = tint(idle, (40, 30, 30), 0.25 * k)
            if i == POP - 1: body = tint(body, (255, 245, 230), 0.6)
            comp(f, xform(body, 1.0, rot=[0, 8, -10, 13, 18][i - 2], dx=shake(i, 3), dy=8 * k))
            L = Layer()
            for j in range(2 + i): star(L, PX + rng.uniform(-70, 70), PY + rng.uniform(-10, 20), rng.uniform(5, 9), 4, (160, 255, 140, 255), rot=rng.uniform(0, 3), inner=0.3)
            comp(f, L.get())
        else:                                           # explota; el marciano escapa volando
            t = (i - POP) * DT + 0.04; fire = max(0, 1 - t * 2.5)
            comp(f, soft([(PX + math.cos(j * 1.3) * 34 * (1 + t * 3), PY + math.sin(j * 1.3) * 20 * (1 + t * 3), 30 + 50 * t, 24 + 36 * t, (55, 55, 60), max(0, 0.8 - t * 1.1)) for j in range(6)], 6))
            if fire > 0:
                comp(f, glow(PX, PY, 120, (180, 255, 150), 0.9 * fire))
                comp(f, soft([(PX + math.cos(j * 1.05) * 40 * (1 + t * 2), PY + math.sin(j * 1.05) * 22 * (1 + t * 2), 30 + 20 * t, 24 + 14 * t, (255, 160, 60), fire) for j in range(6)], 4))
            L = Layer(); al = 1.0 if i < COLS - 1 else 0.5
            for p in debris:
                x, y, h, landed = ballistic(p, t); w = p['w']; a = math.radians(p['spin'] * min(t, 0.5))
                L.poly([(x + math.cos(a + q) * w, y + math.sin(a + q) * w * 0.6) for q in (0, 1.4, 3.1, 4.5)], fill=(180, 180, 195, int(255 * al)), outline=OUT, w=1.2)
            if i >= POP + 1:                            # el marciano verde huye hacia arriba
                u = (i - POP - 1) / (COLS - POP - 2); x, y = PX + 30 * u, PY - 40 - 60 * u
                aa = int(255 * (1 - 0.8 * u * u))
                L.ell(x, y, 13, 11, fill=(124, 252, 0, aa), outline=OUT[:3] + (aa,), w=1.5); L.ell(x - 5, y - 1, 2.5, 4, fill=(0, 0, 0, aa)); L.ell(x + 5, y - 1, 2.5, 4, fill=(0, 0, 0, aa))
                L.line([(x - 6, y - 9), (x - 10, y - 18)], (124, 252, 0, aa), 2); L.line([(x + 6, y - 9), (x + 10, y - 18)], (124, 252, 0, aa), 2)
            comp(f, L.get())
        frames.append(f)
    return frames, POP

def ridley():
    S = load('ridley'); white, red = fr(S, 3, 0), fr(S, 3, 1); wing = [fr(S, 1, c) for c in range(8)]
    POP = 6
    nz = smooth_noise(171, 9)
    ems = particles(172, 32, PX, PY, speed=(10, 70), vz=(0, 1))
    frames = []
    for i in range(COLS):
        f = blank()
        if i == 0: comp(f, white)
        elif i == 1: comp(f, red)
        elif i < POP:                                   # aletea desesperado echando chispas de fuego
            k = (i - 2) / (POP - 3)
            comp(f, xform(tint(wing[(i * 3) % 8], (255, 140, 60), 0.15 + 0.35 * k), 1.0 + 0.05 * k, rot=shake(i, 6)))
            comp(f, glow(PX + 55, PY, 40, (255, 140, 40), 0.4 + 0.4 * k))
        else:                                           # se deshace en brasas
            t = (i - POP) / (COLS - POP - 1)
            comp(f, dissolve(tint(wing[i % 8], (120, 40, 20), 0.4 + 0.4 * t), nz, 0.08 + t * 0.95, [255, 170, 60]))
            L = Layer(); motes(L, ems, i, POP, (255, 140, 40), al=1 - t * 0.8); comp(f, L.get(1))
        frames.append(f)
    return frames, POP

def wither():
    S = load('wither'); idle, white, red = fr(S, 1, 0), fr(S, 3, 0), fr(S, 3, 1)
    POP = 6
    cracks = crack_paths(181, PX, PY - 30, 7, 85)
    shards = make_shards(idle, 24, 182)
    frames = []
    for i in range(COLS):
        f = blank()
        if i == 0: comp(f, white)
        elif i == 1: comp(f, red)
        elif i < POP:                                   # se raja con luz blanca
            k = (i - 1) / (POP - 2)
            comp(f, xform(idle, 1.0 + 0.04 * k, rot=shake(i, 2), dx=shake(i, 3)))
            G = Layer(); draw_cracks(G, cracks, k, (200, 220, 255, 255), 7); comp(f, fade(G.get(3), 0.9))
            L = Layer(); draw_cracks(L, cracks, k, (255, 255, 255, 255), 2.2); comp(f, L.get())
            if i == POP - 1: comp(f, glow(PX, PY - 30, 110, (230, 240, 255), 0.6))
        else:                                           # estalla en bloques y deja la estrella del Nether
            t = (i - POP) * DT + 0.05; boom(f, i, POP, (230, 240, 255), 120)
            if i < COLS - 1: draw_shards(f, shards, t, 240, al=max(0, 1 - t * 1.6), g=260)
            comp(f, soft([(PX + math.cos(j) * 40 * (1 + t * 2), PY - 10 + math.sin(j) * 30 * (1 + t * 2), 30 + 30 * t, 26 + 20 * t, (30, 30, 30), max(0, 0.7 - t * 1.2)) for j in range(6)], 6))
            u = (i - POP) / (COLS - POP - 1); sy = PY - 30 + 30 * u
            comp(f, glow(PX, sy, 50 + 10 * math.sin(i), (220, 240, 255), 0.7))
            L = Layer(); star(L, PX, sy, 16, 4, (240, 250, 255, 255), rot=i * 0.4, inner=0.35, outline=(120, 150, 200, 255), w=1); comp(f, L.get())
        frames.append(f)
    return frames, POP

def ganon():
    S = load('ganon'); idle, white, red = fr(S, 0, 0), fr(S, 3, 0), fr(S, 3, 1)
    POP = 7
    cracks = crack_paths(191, PX, PY - 10, 7, 80)
    stone = tint(gray(idle, 1.0), (150, 145, 135), 0.4)
    shards = make_shards(stone, 28, 192)
    frames = []
    for i in range(COLS):
        f = blank()
        if i == 0: comp(f, white)
        elif i == 1: comp(f, red)
        elif i < POP:                                   # se convierte en piedra de abajo hacia arriba
            k = (i - 2) / (POP - 3)
            line = 230 - 190 * k
            m = np.clip((YY - line) / 12 + 0.5, 0, 1)
            stone = tint(gray(idle, 1.0), (150, 145, 135), 0.4)
            body = comp(masked(idle, 1 - m), masked(stone, m))
            comp(f, xform(body, 1.0, dx=shake(i, 1.5)))
            L = Layer(); draw_cracks(L, cracks, max(0, k - 0.4) / 0.6, (60, 55, 50, 255), 2); comp(f, L.get())
        else:                                           # la estatua se desmorona
            t = (i - POP) * DT + 0.03
            if i == POP:
                comp(f, stone); L = Layer(); draw_cracks(L, cracks, 1, (40, 35, 30, 255), 2.5); comp(f, L.get())
            else:
                draw_shards(f, shards, t, 90, al=1.0 if i < COLS - 1 else 0.6, g=600)
                comp(f, soft([(PX + (j - 2) * 30, PY + 70, 30 + 30 * t, 14 + 6 * t, (170, 160, 150), max(0, 0.8 - t)) for j in range(5)], 4))
        frames.append(f)
    return frames, POP

def sans():
    S = load('sans'); idle, white, red = fr(S, 0, 0), fr(S, 3, 0), fr(S, 3, 1)
    POP = 5
    nz = smooth_noise(201, 6)
    dust = particles(202, 40, PX, PY - 10, speed=(10, 60), vz=(0, 1))
    frames = []
    for i in range(COLS):
        f = blank()
        if i == 0: comp(f, white)
        elif i == 1: comp(f, red)
        elif i < POP: comp(f, xform(idle, 1.0, rot=shake(i, 2)))   # se queda quieto... sonríe
        else:                                           # se hace polvo de abajo hacia arriba, como en su juego
            t = (i - POP) / (COLS - POP - 1)
            body = tint(idle, (230, 230, 230), 0.4 + 0.5 * t)
            th = np.clip((YY - (230 - 200 * t)) / 40, 0, 1) * 0.6 + nz * 0.4
            a = arr(body); a[..., 3] *= (th < 0.55); comp(f, img(a))
            L = Layer(); motes(L, dust, i, POP, (200, 200, 205), up=1.2, spread=2, al=1 - t * 0.6); comp(f, L.get(1))
        frames.append(f)
    return frames, POP

def glitch(im, k, seed):
    """falla de computadora: franjas corridas de lado y los colores separados"""
    rng = np.random.default_rng(seed); a = arr(im); out = a.copy(); y = 0
    while y < F:
        h = int(rng.integers(3, 14)); dx = int(rng.normal(0, 22 * k)) if rng.random() < 0.35 + 0.5 * k else 0
        out[y:y + h] = np.roll(a[y:y + h], dx, axis=1); y += h
    d = int(2 + 7 * k); r = np.roll(out, -d, axis=1); b = np.roll(out, d, axis=1)
    res = out.copy(); res[..., 0] = np.maximum(out[..., 0] * 0.3, r[..., 0]); res[..., 2] = np.maximum(out[..., 2] * 0.3, b[..., 2])
    res[..., 3] = np.maximum.reduce([out[..., 3], r[..., 3] * 0.8, b[..., 3] * 0.8])
    res[1::3, :, :3] *= 0.8                                   # rayitas de pantalla vieja
    return img(res)

def baldi():
    S = load('baldi'); angry, white, red = fr(S, 1, 0), fr(S, 3, 0), fr(S, 3, 1)
    POP = 6
    rng = np.random.default_rng(211)
    cells = rng.random((F // 8 + 1, F // 8 + 1))
    blocks = np.kron(cells, np.ones((8, 8)))[:F, :F]          # la estática se lo come en cuadritos
    frames = []
    for i in range(COLS):
        f = blank()
        if i == 0: comp(f, white)
        elif i == 1: comp(f, red)
        elif i < POP:                                         # se descompone como el problema imposible: falla, tiembla, se separa en colores
            k = (i - 1) / (POP - 2)
            comp(f, glitch(xform(angry, 1.0, rot=shake(i, 2), dx=shake(i, 3)), k, 212 + i))
            if i == POP - 1: comp(f, glow(PX, PY - 40, 110, (190, 255, 200), 0.45))
        else:                                                 # se deshace en estática, de cuadrito en cuadrito
            t = (i - POP) / (COLS - POP - 1)
            if i == POP: comp(f, glow(PX, PY - 40, 120, (220, 255, 225), 0.8))
            body = glitch(angry, 1.0, 230 + i)
            a = arr(body); keep = blocks > 0.15 + 0.85 * t
            noise = np.random.default_rng(240 + i).random((F, F)) * 255
            st = a.copy(); st[..., 0] = st[..., 1] = st[..., 2] = noise; st[..., 3] = a[..., 3] * (blocks > 0.15 + 0.85 * t - 0.12) * (1 - t * 0.5)
            a[..., 3] *= keep * (1 - t * 0.6)
            comp(f, img(st), img(a))
        frames.append(f)
    return frames, POP

def dr_fetus():
    S = load('dr_fetus'); idle, white, red = fr(S, 0, 0), fr(S, 3, 0), fr(S, 3, 1)
    crack = [fr(S, 4, c) for c in (1, 3, 5, 6)]; broken = fr(S, 4, 7)
    POP = 6
    JX, JY = PX, 150                                          # el frasco
    jar = ellmask(JX, JY - 10, 46, 62)
    shards = make_shards(fr(S, 4, 6), 26, 221, region=jar)
    smoke = particles(222, 14, JX, JY, speed=(30, 90), vz=(0, 1))
    sparks = particles(223, 18, JX, JY, speed=(120, 300), vz=(60, 180))
    baby = dict(x=JX, y=JY, vx=70, vy=-40, vz=330, spin=600, k=0.5, i=0)
    frames = []
    for i in range(COLS):
        f = blank()
        if i == 0: comp(f, white)
        elif i == 1: comp(f, red)
        elif i < POP:                                         # el frasco se raja más y más
            body = crack[i - 2]
            if i == POP - 1: body = tint(body, (255, 245, 230), 0.4)
            comp(f, xform(body, 1.0, rot=shake(i, 2 + i), dx=shake(i, 2 + i)))
        else:                                                 # ¡revienta! vidrios, chispas, humo, el cuerpo se cae y el fetito sale volando
            t = (i - POP) * DT + 0.03; u = (i - POP) / (COLS - POP - 1)
            boom(f, i, POP, (255, 230, 190), 110)
            comp(f, soft([(JX + math.cos(j * 1.3) * 30 * (1 + u * 2), JY - 20 - 40 * u + math.sin(j * 1.3) * 18, 22 + 26 * u, 18 + 20 * u, (60, 60, 66), max(0, 0.75 - u * 0.8)) for j in range(6)], 5))
            comp(f, fade(xform(broken, 1.0, 1.0 - 0.25 * u, rot=12 * u, dy=40 * u, py=227), max(0.0, 1 - max(0, u - 0.55) * 2.2)))
            if i < COLS - 1: draw_shards(f, shards, t, 230, al=max(0, 1 - t * 1.5), g=500)
            L = Layer(); al = max(0.0, 1 - u * 1.3)
            for q in sparks:
                x, y, h, landed = ballistic(q, t)
                if not landed and al > 0: L.ell(x, y, 2.4, fill=(255, 200, 80, int(255 * al)))
            x, y, h, landed = ballistic(baby, t, g=700)             # el fetito sale volando dando vueltas
            a = math.radians(baby['spin'] * t)
            L.ell(x, y, 12, fill=(244, 169, 164, 255), outline=(17, 17, 17, 255), w=2)
            ex, ey = math.cos(a) * 4.5, math.sin(a) * 4.5
            L.ell(x - ex, y - ey, 1.8, fill=(17, 17, 17, 255)); L.ell(x + ex, y + ey, 3.6, outline=(17, 17, 17, 255), w=1.6)
            L.ell(x + math.cos(a + 1.6) * 9, y + math.sin(a + 1.6) * 9, 6, 4.5, fill=(244, 169, 164, 255), outline=(17, 17, 17, 255), w=1.5)
            comp(f, L.get())
        frames.append(f)
    return frames, POP

def diablo():
    S = load('diablo'); idle, white, red = fr(S, 0, 0), fr(S, 3, 0), fr(S, 3, 1)
    laugh = fr(S, 1, 2)
    POP = 6
    FY = 197                                                  # sus pezuñas (ahí queda el charco)
    INK = (14, 10, 16)
    drops = particles(251, 22, PX, PY - 20, speed=(60, 200), vz=(150, 330))
    sparks = particles(252, 16, PX, PY - 40, speed=(120, 280), vz=(80, 200))
    rng = np.random.default_rng(253); drips = [(rng.uniform(PX - 30, PX + 30), rng.uniform(0.6, 1.4), rng.uniform(3, 6)) for _ in range(9)]
    frames = []
    for i in range(COLS):
        f = blank()
        if i == 0: comp(f, white)
        elif i == 1: comp(f, red)
        elif i < POP:                                         # A KNOCKOUT!: tiembla, se estira y se va poniendo negro como tinta
            k = (i - 2) / (POP - 3)
            body = tint(laugh if i % 2 else idle, INK, 0.35 + 0.5 * k)
            comp(f, xform(body, 1.0 - 0.05 * k, 1.0 + 0.08 * k, rot=shake(i, 2 + i), dx=shake(i, 3), py=FY))
            if i == POP - 1: comp(f, glow(PX, PY - 30, 110, (255, 230, 190), 0.5))
        else:                                                 # ¡SPLASH! se derrite en un charco de tinta que salpica
            t = (i - POP) * DT + 0.03; u = (i - POP) / (COLS - POP - 1)
            boom(f, i, POP, (255, 225, 170), 105)
            pud = Layer(); pud.ell(PX, FY, 30 + 50 * min(1, u * 2), 7 + 6 * min(1, u * 2), fill=INK + (int(255 * max(0, 1 - max(0, u - 0.6) * 2.4)),)); comp(f, pud.get(1))
            if u < 0.85:                                      # el cuerpo se escurre hacia el charco
                body = tint(idle, INK, 0.9)
                comp(f, fade(xform(body, 1.0 + 0.6 * u, max(0.05, 1 - 1.05 * u), py=FY), max(0.0, 1 - u * 0.9)))
            L = Layer(); al = max(0.0, 1 - u * 1.2)
            for x, sp, r in drips:                            # chorreones de tinta
                y0 = FY - 140 * (1 - u); y1 = min(FY, y0 + 40 * sp * u + 20)
                if al > 0 and u < 0.85: L.line([(x, y0), (x, y1)], fill=INK + (int(255 * al),), w=r)
            for q in drops:                                   # gotas de tinta que salen volando
                x, y, h, landed = ballistic(q, t)
                if al > 0: L.ell(x, y, 4 if not landed else 6, 4 if not landed else 2.5, fill=INK + (int(255 * al),))
            for q in sparks:
                x, y, h, landed = ballistic(q, t)
                if not landed and u < 0.5: L.ell(x, y, 2.4, fill=(255, 200, 90, int(255 * (1 - u * 2))))
            comp(f, L.get())
        frames.append(f)
    return frames, POP

def flowey():
    S = load('flowey'); idle, white, red = fr(S, 0, 0), fr(S, 3, 0), fr(S, 3, 1)
    evil, wilt = fr(S, 1, 0), fr(S, 4, 0)
    POP = 6
    nz = smooth_noise(261, 6)
    petals = particles(262, 12, PX, PY - 40, speed=(40, 140), vz=(120, 260))
    dust = particles(263, 36, PX, PY - 10, speed=(10, 60), vz=(0, 1))
    frames = []
    for i in range(COLS):
        f = blank()
        if i == 0: comp(f, white)
        elif i == 1: comp(f, red)
        elif i < POP:                                         # pone su cara malvada... y se va marchitando, temblando
            body = evil if i < 4 else wilt
            comp(f, xform(body, 1.0, rot=shake(i, 2 + i), dx=shake(i, 2)))
        else:                                                 # se le caen los pétalos y se hace polvo, como los monstruos de su juego
            t = (i - POP) * DT + 0.03; u = (i - POP) / (COLS - POP - 1)
            if i == POP: comp(f, glow(PX, PY - 40, 90, (255, 245, 200), 0.6))
            body = tint(wilt, (230, 230, 230), 0.4 + 0.5 * u)
            th = np.clip((YY - (230 - 200 * u)) / 40, 0, 1) * 0.6 + nz * 0.4
            a = arr(body); a[..., 3] *= (th < 0.55); comp(f, img(a))
            L = Layer()
            for q in petals:
                x, y, h, landed = ballistic(q, t, g=500)
                al = max(0.0, 1 - u * 1.1)
                if al > 0: L.ell(x, y, 7, 4 if not landed else 3, fill=(255, 216, 0, int(255 * al)), outline=(40, 30, 0, int(255 * al)), w=1.2)
            motes(L, dust, i, POP, (220, 220, 220), up=1.2, spread=2, al=1 - u * 0.6)
            comp(f, L.get(1))
        frames.append(f)
    return frames, POP

BOSSES = {'monstro': monstro, 'duque_moscas': duque_moscas, 'isaac_oscuro': isaac_oscuro, 'rey_koopa': rey_koopa,
          'dragon_fin': dragon_fin, 'dr_huevon': dr_huevon, 'rey_fantasma': rey_fantasma, 'cerebro_madre': cerebro_madre,
          'gurdy': gurdy, 'peep': peep, 'viuda': viuda, 'pie_mama': pie_mama, 'satanas': satanas, 'rey_slime': rey_slime,
          'rey_boo': rey_boo, 'nave_nodriza': nave_nodriza, 'ridley': ridley, 'wither': wither, 'ganon': ganon, 'sans': sans,
          'baldi': baldi, 'dr_fetus': dr_fetus, 'diablo': diablo, 'flowey': flowey}


if __name__ == '__main__':
    sheet = Image.new('RGBA', (F * COLS, F * len(ORDER)), (0, 0, 0, 0)); meta = {}
    for r, n in enumerate(ORDER):
        frames, pop = BOSSES[n]()
        for c, im in enumerate(frames): sheet.alpha_composite(edgefade(im), (c * F, r * F))
        meta[n] = {'row': r, 'frames': COLS, 'fps': FPS, 'loop': False, 'pop': pop}
        print('ok', n)
    sheet.save(os.path.join(DIR, 'jefes_muerte.png'), optimize=True)
    with open(os.path.join(DIR, 'jefes_muerte.json'), 'w', encoding='utf-8') as fh:
        json.dump({'image': 'jefes_muerte.png', 'frameWidth': F, 'frameHeight': F, 'columns': COLS, 'rows': len(ORDER),
                   'pivot': {'x': PX, 'y': PY, 'note': 'centro del cuerpo, igual que en las hojas de cada jefe'},
                   'note': "Una fila por jefe. 'pop' = cuadro en que el jefe revienta: ahí van la sacudida, el sonido y la mancha en el suelo.",
                   'bosses': meta}, fh, ensure_ascii=False, indent=2)
