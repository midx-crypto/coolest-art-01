#!/usr/bin/env python3
"""coolest-art-01: "The Sky Whale".

A fully procedural, deterministic painting (Python stdlib only, no network,
no model, no randomness from the environment): a colossal whale swims
through a burning sunset sky above a tiny sleeping city, watched by one
small figure on a rooftop. Writes /output/entry.png (or
$MAKEFUN_OUTPUT_DIR/entry.png), 512x512 PNG.

Idea: a fresh concept the house anchors never show, drawn as a bold flat
poster - one huge unmistakable silhouette, warm rim light, a single clear
focal shape that still reads at 300px wide.
"""
import math
import os
import struct
import zlib

W = H = 512
OUT = os.path.join(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"), "entry.png")

# --- deterministic PRNG (splitmix64, fixed seed) ---------------------------
_state = [0x51AB3E7719C42D05]


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


def catmull(points, samples=10):
    """Smooth closed/open curve through control points (Catmull-Rom)."""
    pts = [points[0]] + list(points) + [points[-1]]
    out = []
    for i in range(len(pts) - 3):
        p0, p1, p2, p3 = pts[i], pts[i + 1], pts[i + 2], pts[i + 3]
        for j in range(samples):
            t = j / samples
            t2, t3 = t * t, t * t * t
            x = 0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t
                       + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                       + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
            y = 0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t
                       + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                       + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
            out.append((x, y))
    out.append(points[-1])
    return out


def xform(points, cx, cy, ang_deg, tx, ty):
    """Rotate points about (cx, cy) by ang_deg, then translate to (tx, ty)."""
    a = math.radians(ang_deg)
    ca, sa = math.cos(a), math.sin(a)
    out = []
    for (x, y) in points:
        dx, dy = x - cx, y - cy
        out.append((tx + dx * ca - dy * sa, ty + dx * sa + dy * ca))
    return out


def bend(points, arch=32, x0=0, x1=390):
    """Arch the whale like a leaping breach: middle rises, head and tail stay."""
    return [(x, y - arch * math.sin(math.pi * (x - x0) / (x1 - x0)))
            for (x, y) in points]


def wpts(points, dx=0, dy=0):
    """Whale-local points -> frame points (bend, rotate, translate)."""
    return xform(bend(points), WXC, WYC, ANG, WTX + dx, WTY + dy)


# --- sky: vertical gradient --------------------------------------------------
STOPS = [
    (0.00, (8, 10, 42)),     # deep indigo
    (0.28, (30, 26, 78)),    # indigo
    (0.50, (96, 40, 112)),   # violet
    (0.66, (198, 64, 104)),  # magenta
    (0.80, (255, 118, 58)),  # burning orange
    (1.00, (255, 176, 92)),  # horizon glow
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

# --- stars (only in the dark upper sky) --------------------------------------
for _ in range(150):
    x = int(rrange(0, W))
    y = int(rrange(0, 170))
    b = rrange(0.3, 1.0) * max(0.15, 1.0 - y / 220.0)
    col = (int(255 * b), int(240 * b), int(220 * b))
    px(x, y, col, b)
    if rnd() < 0.05:
        line(x - 3, y, x + 3, y, col, 0.6 * b)
        line(x, y - 3, x, y + 3, col, 0.6 * b)

# --- low sun, half-sunk behind the skyline -----------------------------------
for r in range(58, 0, -2):
    disc(398, 428, r, (255, 196, 110), 0.05)
disc(398, 428, 26, (255, 214, 130))
disc(398, 428, 26, (255, 170, 80), 0.35)


def cloud(cx, cy, s, col, alpha=0.85):
    """A flat soft cloud: a row of overlapping squashed discs."""
    for (dx, dy, r) in [(-2.2, 0.15, 1.0), (-1.1, -0.15, 1.25), (0.0, -0.25, 1.45),
                        (1.1, -0.1, 1.2), (2.2, 0.2, 0.95), (-0.4, 0.3, 1.1),
                        (0.9, 0.32, 1.0), (-1.7, 0.3, 0.9), (1.7, 0.3, 0.85)]:
        ex, ey = cx + dx * s, cy + dy * s
        rx, ry = int(r * s), int(r * s * 0.34)
        for ddy in range(-ry, ry + 1):
            half = int(rx * math.sqrt(max(0, 1 - (ddy * ddy) / float(ry * ry))))
            hline(int(ey + ddy), int(ex - half), int(ex + half), col, alpha)


# high clouds, lit pink by the sunset
cloud(120, 118, 26, (226, 130, 158), 0.42)
cloud(430, 96, 20, (214, 116, 158), 0.4)
cloud(255, 78, 16, (200, 110, 160), 0.35)
# low warm clouds hugging the horizon
cloud(90, 392, 30, (255, 150, 96), 0.6)
cloud(300, 408, 24, (255, 164, 110), 0.55)
cloud(470, 386, 18, (250, 140, 100), 0.5)

# --- the whale ---------------------------------------------------------------
# Local coords: head at left (x=0), tail at right (x~370), body ~110 tall.
# Drawn rotated -16 deg so the head dives low-left and the tail rises high-right.
TOP = [(2, -10), (30, -32), (72, -44), (122, -50), (176, -50),
       (226, -44), (262, -34), (292, -20), (304, -8)]
BOT = [(304, -8), (296, 6), (268, 18), (228, 28), (180, 34),
       (130, 34), (86, 28), (48, 14), (18, 4), (2, 8)]
BODY = catmull(TOP, 10) + catmull(BOT, 10)
# tail flukes: swept-back lobes, deep notch, concave trailing edges
FLUKE = catmull([(294, -12), (330, -34), (368, -56), (392, -60), (362, -30),
                 (336, -6), (360, 16), (384, 44), (392, 52), (358, 34),
                 (326, 12), (296, 4)], 8)
# pectoral fin, shorter and thicker, swept down-back from the belly
FIN = catmull([(144, 32), (164, 52), (184, 78), (196, 88), (184, 92),
               (162, 66), (146, 42)], 8)
# small dorsal fin on the rear back
DORSAL = catmull([(250, -42), (262, -56), (272, -38), (260, -40)], 6)

RIM = (255, 172, 96)   # warm rim light
INK = (22, 16, 50)     # whale body, deep indigo-violet
WXC, WYC = 180, 0       # whale local centre
WTX, WTY = 252, 262     # where the whale sits in the frame
ANG = -7


def draw_whale(dx, dy, color):
    """Draw body + flukes + fin + dorsal shifted by (dx, dy) in the colour."""
    body = wpts(BODY, dx, dy)
    fluke = wpts(FLUKE, dx, dy)
    fin = wpts(FIN, dx, dy)
    dorsal = wpts(DORSAL, dx, dy)
    poly(fluke, color)
    poly(fin, color)
    poly(dorsal, color)
    poly(body, color)


draw_whale(0, -3, RIM)    # rim-light copy peeking out along the top edge
draw_whale(0, 0, INK)     # body on top, shifted down so the rim shows above
# belly sheen: a soft warm band hugging the lower body
BELLY = catmull([(60, 16), (110, 30), (170, 36), (230, 30), (272, 16),
                 (250, 26), (180, 34), (110, 28)], 8)
poly(wpts(BELLY), (150, 96, 140), 0.30)
# mouth line, nearly level along the lower jaw, curving up at the back
_m1, _m2, _m3 = wpts([(10, 4), (45, 8), (78, 4)])
line(int(_m1[0]), int(_m1[1]), int(_m2[0]), int(_m2[1]), (230, 170, 150), 0.45)
line(int(_m2[0]), int(_m2[1]), int(_m3[0]), int(_m3[1]), (230, 170, 150), 0.45)
# eye: warm dot with a dark pupil
ex, ey = wpts([(58, -12)])[0]
disc(int(ex), int(ey), 5, (255, 208, 128))
disc(int(ex) + 1, int(ey), 2, (20, 12, 40))
# blowhole spout: a classic V - two bright diverging streams of droplets
bx, by = wpts([(104, -48)])[0]
bx, by = int(bx), int(by)
disc(bx, by - 2, 6, (255, 230, 195), 0.30)   # glow at the blowhole
for base_a in (-1.95, -1.15):
    for i in range(42):
        d = rrange(6, 58)
        a = base_a + rrange(-0.08, 0.08)
        sx = int(bx + math.cos(a) * d * 0.6)
        sy = int(by + math.sin(a) * d)
        px(sx, sy, (255, 242, 214), max(0.35, 0.95 - d / 60.0))
        px(sx + 1, sy, (255, 242, 214), 0.7)
        if rnd() < 0.3:
            px(sx, sy + 1, (255, 242, 214), 0.6)

# --- birds -------------------------------------------------------------------
for (bx0, by0, s) in [(150, 168, 7), (178, 150, 6), (205, 172, 5),
                      (392, 210, 6), (420, 188, 5), (88, 210, 5)]:
    line(bx0 - s, by0, bx0, by0 - int(s * 0.55), (26, 16, 52), 0.9)
    line(bx0, by0 - int(s * 0.55), bx0 + s, by0, (26, 16, 52), 0.9)

# --- city skyline ------------------------------------------------------------
CITY = (14, 9, 32)
x = -6
while x < W + 6:
    bw = int(rrange(16, 42))
    bh = int(rrange(18, 66))
    if rnd() < 0.14:  # a tower with a spire
        bh = int(rrange(72, 104))
    poly([(x, H), (x, H - bh), (x + bw, H - bh), (x + bw, H)], CITY)
    if bh > 70:  # spire + warning light
        line(x + bw // 2, H - bh, x + bw // 2, H - bh - 16, CITY)
        disc(x + bw // 2, H - bh - 17, 2, (255, 80, 70))
    # lit windows
    for wy in range(H - bh + 6, H - 6, 9):
        for wx in range(x + 4, x + bw - 3, 8):
            if rnd() < 0.34:
                px(wx, wy, (255, 196, 110), rrange(0.5, 0.95))
                px(wx + 1, wy, (255, 196, 110), 0.5)
    x += bw + int(rrange(2, 9))

# --- the watcher: one small figure on a rooftop, arm raised ------------------
# a tall rooftop jutting from the lower-left corner, so the figure reads
poly([(0, 512), (0, 452), (112, 452), (112, 512)], (10, 7, 26))
poly([(112, 452), (112, 446), (146, 446), (146, 512), (112, 512)], (10, 7, 26))
for r in range(20, 0, -2):
    disc(58, 448, r, (255, 150, 80), 0.05)   # faint warm glow around the figure
FX, FY = 58, 450
FINK = (8, 5, 20)
disc(FX, FY - 19, 4, FINK)                                  # head
poly([(FX - 4, FY - 15), (FX + 4, FY - 15), (FX + 5, FY), (FX - 5, FY)], FINK)
line(FX - 3, FY, FX - 5, FY + 11, FINK)                     # legs
line(FX + 3, FY, FX + 5, FY + 11, FINK)
line(FX + 4, FY - 12, FX + 14, FY - 20, FINK)               # raised arm
disc(FX + 15, FY - 21, 2, (255, 200, 120), 0.95)            # tiny warm hand

# --- vignette + grain ---------------------------------------------------------
for y in range(H):
    dy = (y - H / 2) / (H / 2)
    for x in range(W):
        dx = (x - W / 2) / (W / 2)
        d = math.sqrt(dx * dx + dy * dy)
        if d > 0.85:
            px(x, y, (5, 4, 18), min(0.32, (d - 0.85) * 1.2))
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
