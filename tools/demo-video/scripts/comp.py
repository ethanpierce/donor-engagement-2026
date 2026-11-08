"""Compositor: framed app window on brand plate, camera zoom, spotlight + thin ring, frosted lower-third, scene cards."""
import json, math, os, subprocess, hashlib
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont
from overlays import path_of, lt_spec, card_spec, badge_spec

W, H, FPS = 1920, 1080, 30
DEEP = np.array([30, 9, 87], np.float32); VIOLET = np.array([94, 40, 210], np.float32); LIME = np.array([179, 229, 27], np.float32)
YY, XX = np.mgrid[0:H, 0:W].astype(np.float32)
# Set by configure(): segment cache dir, photo plates dir, optional font for covers.
CFG = dict(seg=None, plates=None, cover_font=None)
def configure(seg_dir, plates_dir, cover_font=None):
    CFG.update(seg=seg_dir, plates=plates_dir, cover_font=cover_font); os.makedirs(seg_dir, exist_ok=True)

# ---------- easing ----------
def clamp(x, a=0., b=1.): return a if x < a else b if x > b else x
def ease_io(x): x = clamp(x); return 4 * x ** 3 if x < .5 else 1 - (-2 * x + 2) ** 3 / 2
def ease_out(x): x = clamp(x); return 1 - (1 - x) ** 3

# ---------- SDF ----------
def sdf(rect, r, roi=None):
    """Signed distance to a rounded rect (x0,y0,x1,y1) in screen px over the full frame (or ROI slice)."""
    x0, y0, x1, y1 = rect
    cx, cy, hw, hh = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2
    r = min(r, hw, hh)
    X, Y = (XX, YY) if roi is None else (XX[roi], YY[roi])
    qx = np.abs(X - cx) - hw + r; qy = np.abs(Y - cy) - hh + r
    return np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - r

def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1); return t * t * (3 - 2 * t)

# ---------- plates ----------
def plate(name):
    """Photo plate (1920x1080 PNG in the plates dir). Falls back to a violet gradient when the file is missing."""
    f = os.path.join(CFG['plates'] or '', f'{name}.png')
    if os.path.exists(f): return cv2.resize(cv2.cvtColor(cv2.imread(f), cv2.COLOR_BGR2RGB), (W, H)).astype(np.float32)
    g = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
    return np.broadcast_to(VIOLET * (1 - g) + DEEP * g, (H, W, 3)).copy()
_PL = {}
def plate_c(name):
    if name not in _PL: _PL[name] = plate(name)
    return _PL[name]

# ---------- source frames ----------
def frames(src, a, b, fps=30):
    """Decode src from a to b at fps (default 30), returns list of RGB uint8 arrays."""
    w, h = probe_size(src)
    p = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{a:.3f}', '-i', src, '-t', f'{b - a:.3f}', '-vf', f'fps={fps:.6f}',
                        '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True, check=True).stdout
    n = len(p) // (w * h * 3)
    return [np.frombuffer(p, np.uint8, w * h * 3, i * w * h * 3).reshape(h, w, 3) for i in range(max(n, 1))] if n else [frame_at(src, a)]
def frame_at(src, t):
    w, h = probe_size(src)
    p = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{t:.3f}', '-i', src, '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                       capture_output=True, check=True).stdout
    return np.frombuffer(p[:w * h * 3], np.uint8).reshape(h, w, 3)
_SZ = {}
def probe_size(src):
    if src not in _SZ:
        o = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height', '-of', 'csv=p=0', src],
                           capture_output=True, text=True).stdout.strip().split(',')
        _SZ[src] = (int(o[0]), int(o[1]))
    return _SZ[src]

# bubble detection (same color rules as the v2 editor, source coords)
def bubbles(im, xr=(470, 1425), yr=(100, 830)):
    a = im[yr[0]:yr[1], xr[0]:xr[1]:2].astype(np.int32); r, g, b = a[..., 0], a[..., 1], a[..., 2]
    kinds = {'bot': (r >= 233) & (r <= 244) & (g >= 224) & (g <= 234) & (b >= 235) & (b <= 247) & (b > g + 4),
             'me': (r >= 226) & (r <= 236) & (g >= 234) & (g <= 244) & (b >= 246),
             'white': (r >= 252) & (g >= 252) & (b >= 252)}
    out = []
    for k, m in kinds.items():
        cnt = m.sum(1); cur = None; gap = 0
        for i in range(m.shape[0]):
            y = yr[0] + i
            if cnt[i] >= 120:
                xs = np.nonzero(m[i])[0]; x0, x1 = xr[0] + 2 * xs[0], xr[0] + 2 * xs[-1]
                cur = [x0, y, x1, y] if cur is None else [min(cur[0], x0), cur[1], max(cur[2], x1), y]; gap = 0
            elif cur is not None:
                gap += 1
                if gap > 22:
                    if cur[3] - cur[1] > 24: out.append((k, cur))
                    cur = None
        if cur is not None and cur[3] - cur[1] > 24: out.append((k, cur))
    out.sort(key=lambda o: o[1][1]); return out
def bub(src, t, k, idx):
    bs = [b for kk, b in bubbles(frame_at(src, t)) if kk == k]
    if not bs: raise SystemExit(f'no {k} bubble in {src} at {t}')
    return tuple(bs[idx])

def apply_covers(im, covers):
    """Paint over small distracting UI strings in source pixels. Each cover: {"rect": [x0,y0,x1,y1], "fill": "white",
    "text": optional replacement, "color": [r,g,b]}."""
    if not covers: return im
    p = Image.fromarray(im); d = ImageDraw.Draw(p)
    font = ImageFont.truetype(CFG['cover_font'], 15) if CFG['cover_font'] else ImageFont.load_default()
    for c in covers:
        r = c['rect']; d.rectangle(tuple(r), fill=c.get('fill', 'white'))
        if c.get('text'): d.text((r[0] + 4, (r[1] + r[3]) / 2), c['text'], font=font, fill=tuple(c.get('color', (96, 96, 100))), anchor='lm')
    return np.asarray(p)

# ---------- layouts ----------
LAYOUT = {
    # kind: (window rect in layout px, source crop (w,h), radius, zmax)
    'desk': dict(win=(168, 45, 168 + 1584, 45 + 990), crop=(1440, 900), r=16, zmax=1.08),
    'gh': dict(win=(160, 95, 160 + 1600, 95 + 890), crop=(1280, 712), r=16, zmax=1.10),
    'desk1920': dict(win=(96, 54, 96 + 1728, 54 + 972), crop=(1920, 1080), r=16, zmax=1.08),   # app recorded at 1920x1080
    'phone': dict(win=(830, 60, 830 + 468, 60 + 960), crop=(780, 1600), r=38, zmax=1.0),
    # Large or near-square source (e.g. a 2404x2258 screen recording): each beat shows a source "view" [cx, cy, w]
    # in source px (height follows the window aspect); the view eases between beats. No zoom on top of it.
    'pan': dict(win=(160, 40, 160 + 1600, 40 + 1000), crop=(1600, 1000), r=16, zmax=1.0, pan=True),
}
_BG = {}
def background(kind):
    """Layout-space background at 2x: blurred, darkened violet plate + soft window shadow (+ device bezel for phone)."""
    if kind in _BG: return _BG[kind]
    L = LAYOUT[kind]; S = 2
    pl = cv2.GaussianBlur(plate_c('skyline'), (0, 0), 6)
    pl = pl * 0.62 + DEEP * 0.38
    g = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
    pl = pl * (1 - 0.25 * g) + DEEP * 0.25 * g
    big = cv2.resize(pl, (W * S, H * S), interpolation=cv2.INTER_CUBIC)
    Yb, Xb = np.mgrid[0:H * S, 0:W * S].astype(np.float32) / S
    def sd(rect, r):
        x0, y0, x1, y1 = rect; cx, cy, hw, hh = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2
        qx = np.abs(Xb - cx) - hw + r; qy = np.abs(Yb - cy) - hh + r
        return np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - r
    x0, y0, x1, y1 = L['win']
    if kind == 'phone':
        bz = 16; dev = (x0 - bz, y0 - bz, x1 + bz, y1 + bz)
        sh = sd((dev[0], dev[1] + 26, dev[2], dev[3] + 26), L['r'] + bz)
        a = (1 - smooth(-30, 60, sh))[..., None] * 0.55; big = big * (1 - a) + np.array([10, 2, 34], np.float32) * a
        d = sd(dev, L['r'] + bz); a = (1 - smooth(-0.8, 0.8, d))[..., None]
        big = big * (1 - a) + np.array([16, 12, 26], np.float32) * a
        edge = np.clip(1.2 - np.abs(d + 1.5), 0, 1)[..., None] * 0.28; big = big * (1 - edge) + 255 * edge
    else:
        sh = sd((x0, y0 + 22, x1, y1 + 22), L['r'])
        a = (1 - smooth(-24, 56, sh))[..., None] * 0.5; big = big * (1 - a) + np.array([10, 2, 34], np.float32) * a
    _BG[kind] = big.astype(np.float32); return _BG[kind]

# ---------- camera ----------
FOCUS_Y = 455   # screen y where a focus centre sits (leaves room for the lower-third)
def cam_for(kind, rects, zoom=True):
    L = LAYOUT[kind]
    if not rects: return (1.0, W / 2, H / 2)
    lr = [to_layout(kind, r) for r in rects]
    x0 = min(r[0] for r in lr); y0 = min(r[1] for r in lr); x1 = max(r[2] for r in lr); y1 = max(r[3] for r in lr)
    fw, fh = x1 - x0, y1 - y0
    z = 1.0 if not zoom else clamp(min(0.6 * W / max(fw, 1), 0.66 * H / max(fh, 1)), 1.0, L['zmax'])
    if z < 1.04: z = 1.0
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2 + (H / 2 - FOCUS_Y) / z
    # keep the whole app window (sidebar, header, navigation) in frame when it fits
    wx0, wy0, wx1, wy1 = L['win']; hw, hh = W / 2 / z, H / 2 / z
    if wx1 - wx0 <= 2 * hw: cx = clamp(cx, wx1 - hw, wx0 + hw)
    if wy1 - wy0 <= 2 * hh: cy = clamp(cy, wy1 - hh, wy0 + hh)
    return clamp_cam((z, cx, cy))
def clamp_cam(c):
    z, cx, cy = c; hw, hh = W / 2 / z, H / 2 / z
    return (z, clamp(cx, hw, W - hw), clamp(cy, hh, H - hh))
def lerp_cam(a, b, t):
    z = math.exp(math.log(a[0]) * (1 - t) + math.log(b[0]) * t)
    return clamp_cam((z, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t))
def to_layout(kind, r):
    L = LAYOUT[kind]; x0, y0, x1, y1 = L['win']; s = (x1 - x0) / L['crop'][0]
    return (x0 + r[0] * s, y0 + r[1] * s, x0 + r[2] * s, y0 + r[3] * s)
def to_screen(cam, r):
    z, cx, cy = cam
    return ((r[0] - cx) * z + W / 2, (r[1] - cy) * z + H / 2, (r[2] - cx) * z + W / 2, (r[3] - cy) * z + H / 2)

# ---------- lower-third ----------
_LT = {}
def lt_img(spec):
    k = json.dumps(spec, sort_keys=True)
    if k not in _LT:
        base = path_of(spec); im = cv2.imread(base + '.png', cv2.IMREAD_UNCHANGED)
        rgba = cv2.cvtColor(im, cv2.COLOR_BGRA2RGBA).astype(np.float32); meta = json.load(open(base + '.json'))
        _LT[k] = (rgba, meta)
    return _LT[k]
MARGIN_X, MARGIN_B, MARGIN_T = 72, 58, 52
def lt_body(meta, corner):
    bw, bh = meta['bw'], meta['bh']
    x = MARGIN_X if corner[1] == 'l' else W - MARGIN_X - bw
    y = H - MARGIN_B - bh if corner[0] == 'b' else MARGIN_T
    return (x, y, x + bw, y + bh)
def overlap(a, b):
    return max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
# Source-pixel areas the caption should not cover: sidebar (incl. bottom navigation) and the room header + tabs.
PROTECT = {'desk': [(0, 0, 410, 900), (410, 0, 1440, 105)], 'desk1920': [(0, 0, 252, 1080), (252, 0, 1920, 130)], 'gh': [(0, 0, 1280, 64)], 'phone': [], 'pan': []}
def pick_corner(meta, focus_screen, prev, protect_screen=()):
    order = ([prev] if prev else []) + ['br', 'bl', 'tr', 'tl']
    best = None
    for c in order:
        body = lt_body(meta, c); body = (body[0] - 24, body[1] - 24, body[2] + 24, body[3] + 24)
        sc = 20 * sum(overlap(body, f) for f in focus_screen) + sum(overlap(body, p) for p in protect_screen)
        if best is None or sc < best[0]: best = (sc, c)
    return best[1]

def blur_frame(fr, sigma):
    return cv2.GaussianBlur(fr, (0, 0), sigma)

def draw_lt(fr, spec, corner, alpha, rise):
    if alpha <= 0.003: return fr
    rgba, meta = lt_img(spec)
    bx0, by0, bx1, by1 = lt_body(meta, corner); by0 += rise; by1 += rise
    ox, oy = int(round(bx0 - meta['bx'])), int(round(by0 - meta['by']))
    h, w = rgba.shape[:2]
    # frosted backdrop under the card body
    x0, y0, x1, y1 = max(0, ox), max(0, oy), min(W, ox + w), min(H, oy + h)
    roi = (slice(y0, y1), slice(x0, x1))
    d = sdf((bx0, by0, bx1, by1), meta['r'], roi)
    m = (1 - smooth(-1, 1, d))[..., None] * alpha
    sub = fr[roi]; bl = cv2.GaussianBlur(sub, (0, 0), 14)
    sub = sub * (1 - m) + bl * m
    o = rgba[y0 - oy:y1 - oy, x0 - ox:x1 - ox]; a = o[..., 3:4] / 255 * alpha
    fr[roi] = sub * (1 - a) + o[..., :3] * a
    return fr

# ---------- spotlight ----------
def spotlight(fr, blurred, rects, a):
    if a <= 0.003 or not rects: return fr
    d = None
    for r in rects:
        r = (r[0] - 10, r[1] - 10, r[2] + 10, r[3] + 10)
        di = sdf(r, 14); d = di if d is None else np.minimum(d, di)
    dim = (smooth(-1, 12, d) * a)[..., None]
    outside = blurred * 0.70 + DEEP * 0.30
    fr = fr * (1 - dim) + outside * dim
    ring = np.clip(1.4 - np.abs(d - 0.5), 0, 1)[..., None] * (0.85 * a)
    glow = (np.exp(-np.maximum(d, 0) / 5) * (d > -0.5))[..., None] * (0.08 * a)
    fr = fr * (1 - ring) + LIME * ring
    fr = fr + (LIME - fr) * glow
    return fr

# ---------- speed badge ----------
def draw_badge(fr, spec, win, a):
    """Small "4x speed" pill at the top-right corner inside the app window (screen rect win)."""
    if a <= 0.003: return fr
    o = lt_img(spec)[0]; h, w = o.shape[:2]
    x, y = int(round(win[2] - w - 6)), int(round(win[1] + 4))
    x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
    o = o[y0 - y:y1 - y, x0 - x:x1 - x]; al = o[..., 3:4] / 255 * a
    fr[y0:y1, x0:x1] = fr[y0:y1, x0:x1] * (1 - al) + o[..., :3] * al
    return fr

# ---------- pan layout ----------
def view_rect(v, sw, sh, cw, ch):
    """[cx, cy, w] in source px -> (x0, y0, w), kept inside the source when it fits."""
    cx, cy, w = v; h = w * ch / cw
    x0 = clamp(cx - w / 2, 0, sw - w) if w <= sw else cx - w / 2
    y0 = clamp(cy - h / 2, 0, sh - h) if h <= sh else cy - h / 2
    return (x0, y0, w)
def default_view(rects, sw, sh):
    """Full source width, centred on the focus (or on the source)."""
    if not rects: return (sw / 2, sh / 2, sw)
    return (sw / 2, (min(r[1] for r in rects) + max(r[3] for r in rects)) / 2, sw)
def view_map(v, r, cw):
    x0, y0, w = v; s = cw / w
    return ((r[0] - x0) * s, (r[1] - y0) * s, (r[2] - x0) * s, (r[3] - y0) * s)
def view_crop(im, v, cw, ch):
    x0, y0, w = v; s = cw / w
    M = np.float32([[s, 0, -x0 * s], [0, s, -y0 * s]])
    return cv2.warpAffine(im, M, (cw, ch), flags=cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

# ---------- encoder ----------
class Enc:
    def __init__(s, out):
        s.p = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                                '-c:v', 'libx264', '-preset', 'medium', '-crf', '14', '-pix_fmt', 'yuv420p', out], stdin=subprocess.PIPE)
        s.n = 0
    def put(s, fr): s.p.stdin.write(np.clip(fr, 0, 255).astype(np.uint8).tobytes()); s.n += 1
    def close(s): s.p.stdin.close(); s.p.wait()

# ---------- items ----------
def key(*a): return hashlib.md5(json.dumps(a, sort_keys=True, default=str).encode()).hexdigest()[:12]
VERSION = 'v4.4'

def render_card(item, out):
    """item: dict(kind='card', spec, dur, plate)"""
    spec = item['spec']; n = int(round(item['dur'] * FPS))
    base = path_of(spec); txt = cv2.cvtColor(cv2.imread(base + '.png', cv2.IMREAD_UNCHANGED), cv2.COLOR_BGRA2RGBA).astype(np.float32)
    meta = json.load(open(base + '.json')); ls = meta['layers']
    bands = []
    for i, (a, b) in enumerate(ls):
        top = 0 if i == 0 else (ls[i - 1][1] + a) // 2
        bot = H if i == len(ls) - 1 else (b + ls[i + 1][0]) // 2
        bands.append((top, bot))
    pl = plate_c(item.get('plate', 'skyline'))
    g = np.linspace(-1, 1, W, dtype=np.float32)[None, :] ** 2 + np.linspace(-1, 1, H, dtype=np.float32)[:, None] ** 2
    vig = np.clip(g * 0.32, 0, 0.4)[..., None]
    e = Enc(out)
    for i in range(n):
        t = i / FPS
        z = 1.06 - 0.06 * ease_out(t / item['dur']) if item.get('kb', True) else 1.0
        M = np.float32([[z, 0, W / 2 * (1 - z)], [0, z, H / 2 * (1 - z)]])
        fr = cv2.warpAffine(pl, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        fr = fr * (1 - vig) + DEEP * vig
        for j, (top, bot) in enumerate(bands):
            st = 0.10 + 0.08 * j; p = ease_out((t - st) / 0.32)
            if p <= 0: continue
            dy = int(round(18 * (1 - p)))
            lay = txt[top:bot]; a = lay[..., 3:4] / 255 * p
            y0, y1 = top + dy, min(H, bot + dy); lay = lay[:y1 - y0]; a = a[:y1 - y0]
            fr[y0:y1] = fr[y0:y1] * (1 - a) + lay[..., :3] * a
        e.put(fr)
    e.close(); return n / FPS

def beat_frames(src, b):
    """Returns list of source frames for a beat at output rate."""
    N = int(round(b['dur'] * FPS))
    if b.get('freeze') is not None:
        return [frame_at(src, b['freeze'])] * N
    a, bb = b['a'], b['b']
    sp = max(b.get('minsp', 1.0), (bb - a) * FPS / max(N, 1))   # speed-up that fits the range into the beat
    fs = frames(src, a, bb, FPS / sp)                              # decode only the frames that are shown
    out = fs[:N]
    out += [out[-1]] * (N - len(out))
    return out

def resolve_focus(src, b):
    f = b.get('focus')
    if f is None: return []
    if isinstance(f, list): return [tuple(x) for x in f]
    if f[0] == 'bub':
        t = b['freeze'] if b.get('freeze') is not None else b['b'] - 0.05
        return [bub(src, t, f[1], f[2])]
    return [tuple(f)]

def render_shot(item, out):
    """item: dict(kind='shot', layout, src, eb, who, beats=[dict(freeze|a,b,sp,hold, cap, focus, zoom, covers, who)])"""
    kind = item['layout']; L = LAYOUT[kind]; src = item['src']
    bg = background(kind); x0, y0, x1, y1 = L['win']; cw, ch = L['crop']
    pre = (x1 - x0) / cw   # source px -> layout px
    e = Enc(out)
    pan = L.get('pan'); sw, sh = probe_size(src) if pan else (cw, ch); prev_view = None; prev_badge = None
    prev_cam = None; prev_rects = []; prev_lt = None; prev_corner = None; T = 0.0; cum = 0.0
    for bi, b in enumerate(item['beats']):
        # carry frame rounding across beats, so many short beats do not drift from the planned shot length
        cum += b['dur']; nb = int(round(cum * FPS)) - int(round(T * FPS))
        fs = beat_frames(src, dict(b, dur=nb / FPS)); n = len(fs)
        rects_src = resolve_focus(src, b)
        if pan:
            view = view_rect(b.get('view') or default_view(rects_src, sw, sh), sw, sh, cw, ch)
            vstart = prev_view or view; vmove = 0.8 if vstart != view else 0.0
            rects_v = [view_map(view, r, cw) for r in rects_src]
        else: rects_v = rects_src; vmove = 0.0
        target = cam_for(kind, rects_v, b.get('zoom', True))
        if prev_cam is None:
            start = (1.0, W / 2, H / 2) if target[0] > 1.04 else clamp_cam((target[0] * 0.975, target[1], target[2]))
        else: start = prev_cam
        lr = [to_layout(kind, r) for r in rects_v]
        badge = badge_spec(b['badge']) if b.get('badge') else None
        spec = lt_spec(b.get('eb', item['eb']), b['cap'], b.get('who', item['who']))
        _, meta = lt_img(spec)
        corner = pick_corner(meta, [to_screen(target, r) for r in lr], prev_corner, [to_screen(target, to_layout(kind, p)) for p in PROTECT[kind]])
        same_lt = prev_lt is not None and prev_lt[0] == spec and prev_lt[1] == corner
        morph = not pan and bool(prev_rects) and bool(lr) and len(prev_rects) == len(lr)
        move = 0.75 if start != target else 0.0
        frz = b.get('freeze') is not None
        for i in range(n):
            t = i / FPS
            cam = lerp_cam(start, target, ease_io(t / move)) if move else target
            if frz and t > move:   # slow drift on stills
                cam = clamp_cam((cam[0] * (1 + 0.010 * (t - move) / max(0.1, b['dur'])), cam[1], cam[2]))
            z, cx, cy = cam
            if pan:
                v = tuple(vstart[j] + (view[j] - vstart[j]) * ease_io(t / vmove) for j in range(3)) if vmove else view
                src_fr = view_crop(apply_covers(fs[i], b.get('covers')), v, cw, ch)
                lr = [to_layout(kind, view_map(v, r, cw)) for r in rects_src]
            else: src_fr = apply_covers(fs[i], b.get('covers'))[:ch, :cw]
            # app layer
            if kind == 'phone':
                s0 = cv2.resize(src_fr, (x1 - x0, y1 - y0), interpolation=cv2.INTER_AREA); k = 1.0
            else: s0 = src_fr; k = pre
            M = np.float32([[k * z, 0, (x0 - cx) * z + W / 2], [0, k * z, (y0 - cy) * z + H / 2]])
            app = cv2.warpAffine(s0, M, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE).astype(np.float32)
            Mb = np.float32([[z / 2, 0, -cx * z + W / 2], [0, z / 2, -cy * z + H / 2]])
            fr = cv2.warpAffine(bg, Mb, (W, H), flags=cv2.INTER_LINEAR)
            win = to_screen(cam, L['win'])
            wm = (1 - smooth(-0.7, 0.7, sdf(win, L['r'] * z)))[..., None]
            fr = fr * (1 - wm) + app * wm
            # spotlight
            if lr and morph:
                p = ease_io(t / max(move, 0.4)); cur = [tuple(pa[j] + (pb[j] - pa[j]) * p for j in range(4)) for pa, pb in zip(prev_rects, lr)]
                fr = spotlight(fr, blur_frame(fr, 1.1), [to_screen(cam, r) for r in cur], 1.0)
            else:
                if prev_rects and t < 0.15:
                    fr = spotlight(fr, blur_frame(fr, 1.1), [to_screen(cam, r) for r in prev_rects], 1 - t / 0.15)
                sa = ease_out((t - vmove - (0.15 if prev_rects else 0.12)) / 0.22)   # pan: after the view settles
                if lr and sa > 0: fr = spotlight(fr, blur_frame(fr, 1.1), [to_screen(cam, r) for r in lr], sa)
            # speed badge (sped-up range), fades out at the start of the next beat
            if badge: fr = draw_badge(fr, badge, win, 1.0 if prev_badge == badge else ease_out(t / 0.2))
            elif prev_badge and t < 0.15: fr = draw_badge(fr, prev_badge, win, 1 - t / 0.15)
            # lower-third
            if same_lt: fr = draw_lt(fr, spec, corner, 1.0, 0)
            else:
                if prev_lt is not None and t < 0.15: fr = draw_lt(fr, prev_lt[0], prev_lt[1], 1 - t / 0.15, 0)
                st = 0.25 if prev_lt is None else 0.06
                p = ease_out((t - st) / 0.24)
                fr = draw_lt(fr, spec, corner, p, (1 - p) * 12)
            e.put(fr)
        b['_t0'] = T; T += n / FPS; b['_t1'] = T
        prev_cam = cam; prev_rects = lr; prev_lt = (spec, corner); prev_corner = corner; prev_badge = badge
        if pan: prev_view = view
    e.close(); return T

def render_item(item):
    cache = os.path.join(CFG['seg'], f"{item['kind']}_{key(VERSION, {k: v for k, v in item.items() if not k.startswith('_')})}.mp4")
    meta = cache + '.json'
    if not os.path.exists(meta):
        cv2.setNumThreads(2)
        d = render_card(item, cache) if item['kind'] == 'card' else render_shot(item, cache)
        bt = [[b['_t0'], b['_t1']] for b in item.get('beats', [])]
        json.dump(dict(dur=d, beats=bt), open(meta, 'w'))
    return cache, json.load(open(meta))
