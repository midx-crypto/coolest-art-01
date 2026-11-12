#!/usr/bin/env python3
"""coolest-art-01: "The Watcher of the Ringed Giant".

A fully procedural, deterministic painting (Python stdlib only, no network,
no model, no randomness from the environment): a lone astronaut stands on a
dark ridge beneath a huge banded ringed planet, over a burning orange horizon.
Writes /output/entry.png (or $MAKEFUN_OUTPUT_DIR/entry.png), 512x512 PNG.
"""
import math
import os
import struct
import zlib

W = H = 512
OUT = os.path.join(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"), "entry.png")

# --- deterministic PRNG (splitmix64, fixed seed) ---------------------------
_state = [0x9E3779B97F4A7C15]


def rnd():
    _state[0] = (_state[0] + 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF
    z = _state[0]
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & 0xFFFFFFFFFFFFFFFF
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & 0xFFFFFFFFFFFFFFFF
    return ((z ^ (z >> 31)) & 0xFFFFFFFFFFFFFFFF) / 18446744073709551616.0


def rrange(a, b):
    return a + (b - a) * rnd()


# --- canvas -----------------------------------------------------------------
fb = [bytearray(W * 3) for _ in range(H)]


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def px(x, y, c, alpha=1.0):
    if 0 <= x < W and 0 <= y < H:
        i = x * 3
        row = fb[y]
        if alpha >= 1.0:
            row[i], row[i + 1], row[i + 2] = c
        else:
            row[i] = int(row[i] + (c[0] - row[i]) * alpha)
            row[i + 1] = int(row[i + 1] + (c[1] - row[i + 1]) * alpha)
            row[i + 2] = int(row[i + 2] + (c[2] - row[i + 2]) * alpha)


def hline(y, x0, x1, c, alpha=1.0):
    if y < 0 or y >= H:
        return
    x0 = max(0, int(x0))
    x1 = min(W - 1, int(x1))
    if x1 < x0:
        return
    row = fb[y]
    if alpha >= 1.0:
        for x in range(x0, x1 + 1):
            i = x * 3
            row[i], row[i + 1], row[i + 2] = c
    else:
        for x in range(x0, x1 + 1):
            i = x * 3
            row[i] = int(row[i] + (c[0] - row[i]) * alpha)
            row[i + 1] = int(row[i + 1] + (c[1] - row[i + 1]) * alpha)
            row[i + 2] = int(row[i + 2] + (c[2] - row[i + 2]) * alpha)


def disc(cx, cy, r, c, alpha=1.0):
    for dy in range(-r, r + 1):
        half = int(math.sqrt(max(0, r * r - dy * dy)))
        hline(cy + dy, cx - half, cx + half, c, alpha)


def ellipse_band(cx, cy, rx, ry, w, c, alpha=1.0, top_only=False, bot_only=False):
    """Ring between outer ellipse (rx,ry) and inner ellipse (rx-w, ry-w*ry/rx)."""
    for dy in range(-ry, ry + 1):
        y = cy + dy
        if top_only and y >= cy:
            continue
        if bot_only and y < cy:
            continue
        t = 1.0 - (dy * dy) / float(ry * ry)
        if t <= 0:
            continue
        xo = rx * math.sqrt(t)
        ri = max(1.0, ry - w * ry / rx)
        ti = 1.0 - (dy * dy) / float(ri * ri)
        xi = (rx - w) * math.sqrt(ti) if ti > 0 else 0.0
        hline(y, cx - xo, cx - xi, c, alpha)
        hline(y, cx + xi, cx + xo, c, alpha)


def poly(points, c, alpha=1.0):
    ys = [p[1] for p in points]
    for y in range(max(0, int(min(ys))), min(H - 1, int(max(ys)) + 1)):
        xs = []
        n = len(points)
        for i in range(n):
            x1, y1 = points[i]
            x2, y2 = points[(i + 1) % n]
            if (y1 <= y < y2) or (y2 <= y < y1):
                xs.append(x1 + (y - y1) * (x2 - x1) / (y2 - y1))
        xs.sort()
        for i in range(0, len(xs) - 1, 2):
            hline(y, xs[i], xs[i + 1], c, alpha)


def line(x0, y0, x1, y1, c, alpha=1.0):
    n = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
    for i in range(n + 1):
        t = i / max(1, n)
        px(int(x0 + (x1 - x0) * t), int(y0 + (y1 - y0) * t), c, alpha)


# --- sky: vertical gradient --------------------------------------------------
STOPS = [
    (0.00, (7, 11, 36)),    # deep indigo
    (0.30, (27, 31, 75)),   # indigo
    (0.52, (91, 42, 110)),  # violet
    (0.68, (193, 68, 106)),  # magenta
    (0.80, (255, 122, 61)),  # burning orange
    (1.00, (255, 170, 90)),  # horizon glow
]
for y in range(H):
    t = y / (H - 1)
    for i in range(len(STOPS) - 1):
        if STOPS[i][0] <= t <= STOPS[i + 1][0]:
            f = (t - STOPS[i][0]) / (STOPS[i + 1][0] - STOPS[i][0])
            col = lerp(STOPS[i][1], STOPS[i + 1][1], f)
            break
    else:
        col = STOPS[-1][1]
    row = fb[y]
    for x in range(W):
        row[x * 3], row[x * 3 + 1], row[x * 3 + 2] = col

# --- stars -------------------------------------------------------------------
for _ in range(240):
    x = int(rrange(0, W))
    y = int(rrange(0, 330))
    b = rrange(0.35, 1.0)
    # fade stars out toward the bright horizon
    b *= max(0.15, 1.0 - y / 420.0)
    col = (int(255 * b), int(240 * b), int(220 * b))
    px(x, y, col, b)
    if rnd() < 0.06:  # sparkle cross
        line(x - 3, y, x + 3, y, col, 0.7 * b)
        line(x, y - 3, x, y + 3, col, 0.7 * b)

# --- shooting star -----------------------------------------------------------
for i in range(46):
    t = i / 45.0
    px(int(88 + i * 2.1), int(52 + i * 1.05), (255, 230, 190), (1 - t) * 0.9)
    px(int(88 + i * 2.1), int(53 + i * 1.05), (255, 200, 140), (1 - t) * 0.5)
disc(186, 103, 2, (255, 244, 214))

# --- ringed planet -----------------------------------------------------------
PCX, PCY, PR = 332, 148, 92
# halo
for r in range(PR + 46, PR, -2):
    disc(PCX, PCY, r, (255, 190, 130), 0.03)
# back half of the ring (behind the planet)
ellipse_band(PCX, PCY, 168, 44, 26, (232, 196, 138), 0.92, top_only=True)
ellipse_band(PCX, PCY, 168, 44, 7, (120, 84, 66), 0.85, top_only=True)
# planet disc with bands
BANDS = [
    (0.00, (250, 214, 164)),
    (0.16, (238, 178, 128)),
    (0.30, (250, 222, 178)),
    (0.44, (198, 110, 82)),
    (0.58, (247, 203, 150)),
    (0.72, (226, 158, 116)),
    (0.86, (250, 226, 186)),
    (1.00, (240, 190, 140)),
]
for dy in range(-PR, PR + 1):
    t = (dy + PR) / (2.0 * PR)
    for i in range(len(BANDS) - 1):
        if BANDS[i][0] <= t <= BANDS[i + 1][0]:
            f = (t - BANDS[i][0]) / (BANDS[i + 1][0] - BANDS[i][0])
            col = lerp(BANDS[i][1], BANDS[i + 1][1], f)
            break
    # wobble the bands a touch
    wob = int(3 * math.sin(dy * 0.11))
    half = int(math.sqrt(max(0, PR * PR - dy * dy)))
    # shade the night side on the left
    shade = 0.72 + 0.28 * (0.5 + 0.5 * math.sin(math.atan2(dy, half) + 0.6))
    col = tuple(int(v * shade) for v in col)
    hline(PCY + dy, PCX - half + wob, PCX + half + wob, col)
# terminator shadow: soft dark crescent on the lower-left limb
for dy in range(-PR, PR + 1):
    half = int(math.sqrt(max(0, PR * PR - dy * dy)))
    for dx in range(-half, -half // 3):
        d = math.sqrt(dx * dx + dy * dy) / PR
        if d > 0.62:
            px(PCX + dx, PCY + dy, (40, 26, 60), 0.35 * (d - 0.62) / 0.38)
# front half of the ring (in front of the planet)
ellipse_band(PCX, PCY, 168, 44, 26, (240, 206, 150), 0.95, bot_only=True)
ellipse_band(PCX, PCY, 168, 44, 7, (126, 88, 68), 0.9, bot_only=True)
# crisp rim light on the planet's upper edge
for a in range(200, 341, 2):
    th = math.radians(a)
    px(int(PCX + PR * math.cos(th)), int(PCY - PR * math.sin(th)),
       (255, 236, 200), 0.8)

# --- mountains ---------------------------------------------------------------
def ridge(base_y, amp, seed_off, color, snow=False):
    pts = [(0, H)]
    x = 0
    # seeded jagged ridge via smoothed random walk
    vals = []
    v = 0.0
    for i in range(33):
        v += rrange(-1, 1)
        v *= 0.72
        vals.append(v)
    peaks = []
    for i in range(33):
        x = i * (W / 32.0)
        y = base_y - amp * (0.45 + 0.55 * (vals[i] + 1.6) / 3.2)
        pts.append((x, y))
        peaks.append((x, y))
    pts.append((W, H))
    poly(pts, color)
    if snow:
        for (x, y) in peaks:
            if rnd() < 0.75:
                s = rrange(9, 18)
                poly([(x - s, y + s * 0.55), (x, y), (x + s, y + s * 0.55)],
                     (244, 238, 250), 0.95)


ridge(392, 46, 0, (58, 32, 84))          # far ridge, violet
ridge(430, 62, 1, (24, 14, 44), snow=True)  # near ridge, near-black + snow

# --- ground glow + astronaut -------------------------------------------------
for r in range(42, 0, -2):
    disc(150, 442, r, (255, 140, 70), 0.06)
# astronaut silhouette on the near ridge (facing the planet), ~1.35x
AX, AY = 150, 440
INK = (12, 8, 24)
S = 1.35
def _ax(dx, dy):
    return int(AX + dx * S), int(AY + dy * S)
disc(*_ax(0, -35), int(9 * S), INK)                    # helmet
disc(*_ax(3, -36), int(4 * S), (255, 170, 100), 0.9)  # visor glint
poly([_ax(-8, -26), _ax(8, -26), _ax(9, 3), _ax(-9, 3)], INK)  # torso
poly([_ax(-9, 3), _ax(-3, 3), _ax(-5, 22), _ax(-10, 22)], INK)  # left leg
poly([_ax(3, 3), _ax(9, 3), _ax(10, 22), _ax(5, 22)], INK)  # right leg
poly([_ax(-12, -24), _ax(-7, -24), _ax(-7, -3), _ax(-12, -3)], INK)  # backpack
line(*_ax(-8, -16), *_ax(-20, -8), INK)   # left arm
line(*_ax(8, -16), *_ax(20, -11), INK)   # right arm, raised toward planet

# --- vignette + grain ---------------------------------------------------------
for y in range(H):
    for x in (0, 1, W - 2, W - 1):
        pass
for y in range(H):
    dy = (y - H / 2) / (H / 2)
    for x in range(W):
        dx = (x - W / 2) / (W / 2)
        d = math.sqrt(dx * dx + dy * dy)
        if d > 0.85:
            px(x, y, (5, 4, 18), min(0.35, (d - 0.85) * 1.2))
for _ in range(9000):
    x = int(rrange(0, W))
    y = int(rrange(0, H))
    v = rrange(-5, 5)
    row = fb[y]
    i = x * 3
    row[i] = max(0, min(255, int(row[i] + v)))
    row[i + 1] = max(0, min(255, int(row[i + 1] + v)))
    row[i + 2] = max(0, min(255, int(row[i + 2] + v)))


# --- PNG encode ---------------------------------------------------------------
def chunk(typ, data):
    c = struct.pack(">I", len(data)) + typ + data
    return c + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)


raw = b"".join(b"\x00" + bytes(row) for row in fb)
png = (b"\x89PNG\r\n\x1a\n"
       + chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
       + chunk(b"IDAT", zlib.compress(raw, 9))
       + chunk(b"IEND", b""))
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "wb") as f:
    f.write(png)
print(f"wrote {OUT} {len(png)} bytes {W}x{H}")
