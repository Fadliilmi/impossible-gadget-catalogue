#!/usr/bin/env python3
"""LOOPCELL - the self-charging power bank.

Renders a catalogue photograph of an impossible gadget to /output/entry.png:
a sleek manufactured power bank whose USB-C cable loops out of its output
port and back into its own input port, charging itself forever. One
accessory only: a smartphone lying beside it, battery full.

Pure Python 3.13 standard library (no PIL, no network). Deterministic:
the same bytes come out of every run.
"""
import math
import os
import random
import struct
import zlib

W = 1024
H = 1024
OUT = os.environ.get("ENTRY_OUTPUT", "/output/entry.png")

rows = [bytearray(W * 3) for _ in range(H)]


def _row_bytes(rgb, n):
    return bytes(rgb) * n


def blend_span(y, x0, x1, rgb, alpha):
    """Blend a horizontal span toward rgb with the given alpha."""
    if y < 0 or y >= H or alpha <= 0.0:
        return
    x0 = max(0, int(x0))
    x1 = min(W, int(x1))
    if x1 <= x0:
        return
    row = rows[y]
    ia = 1.0 - alpha
    r, g, b = rgb
    for x in range(x0, x1):
        i = x * 3
        row[i] = int(row[i] * ia + r * alpha)
        row[i + 1] = int(row[i + 1] * ia + g * alpha)
        row[i + 2] = int(row[i + 2] * ia + b * alpha)


def lighten_span(y, x0, x1, alpha):
    """Blend a horizontal span toward white (studio light)."""
    if y < 0 or y >= H or alpha <= 0.0:
        return
    x0 = max(0, int(x0))
    x1 = min(W, int(x1))
    if x1 <= x0:
        return
    row = rows[y]
    ia = 1.0 - alpha
    for x in range(x0, x1):
        i = x * 3
        row[i] = int(row[i] * ia + 255 * alpha)
        row[i + 1] = int(row[i + 1] * ia + 255 * alpha)
        row[i + 2] = int(row[i + 2] * ia + 255 * alpha)


def fill_rect(x0, y0, x1, y1, rgb):
    x0 = max(0, int(x0))
    x1 = min(W, int(x1))
    y0 = max(0, int(y0))
    y1 = min(H, int(y1))
    if x1 <= x0 or y1 <= y0:
        return
    blob = bytes(rgb) * (x1 - x0)
    for y in range(y0, y1):
        rows[y][x0 * 3:x1 * 3] = blob


def rrect(x0, y0, x1, y1, r, c_top, c_bot):
    """Rounded rectangle with a vertical gradient."""
    for y in range(int(y0), int(y1)):
        t = (y - y0) / max(1, (y1 - y0 - 1))
        cr = int(c_top[0] + (c_bot[0] - c_top[0]) * t)
        cg = int(c_top[1] + (c_bot[1] - c_top[1]) * t)
        cb = int(c_top[2] + (c_bot[2] - c_top[2]) * t)
        if y - y0 < r:
            dy = r - (y - y0)
            dx = int(math.sqrt(max(0, r * r - dy * dy)))
            xa, xb = x0 + r - dx, x1 - r + dx
        elif y1 - 1 - y < r:
            dy = r - (y1 - 1 - y)
            dx = int(math.sqrt(max(0, r * r - dy * dy)))
            xa, xb = x0 + r - dx, x1 - r + dx
        else:
            xa, xb = x0, x1
        xa = max(0, int(xa))
        xb = min(W, int(xb))
        if xb > xa:
            rows[y][xa * 3:xb * 3] = bytes((cr, cg, cb)) * (xb - xa)


def ellipse_fade(cx, cy, rx, ry, alpha, rgb):
    """Soft ellipse, alpha fading to zero at the rim."""
    for y in range(int(cy - ry), int(cy + ry) + 1):
        dy = (y - cy) / ry
        if abs(dy) >= 1:
            continue
        hw = int(rx * math.sqrt(1 - dy * dy))
        a = alpha * (1 - dy * dy)
        blend_span(y, cx - hw, cx + hw, rgb, a)


def disc(cx, cy, r, rgb, alpha=1.0):
    cx = int(cx)
    cy = int(cy)
    r = int(r)
    for y in range(cy - r, cy + r + 1):
        if y < 0 or y >= H:
            continue
        dy = y - cy
        hw = int(math.sqrt(max(0, r * r - dy * dy)))
        xa = max(0, cx - hw)
        xb = min(W, cx + hw)
        if xb <= xa:
            continue
        if alpha >= 1.0:
            rows[y][xa * 3:xb * 3] = bytes(rgb) * (xb - xa)
        else:
            blend_span(y, xa, xb, rgb, alpha)


def poly_fill(pts, rgb):
    ys = [p[1] for p in pts]
    for y in range(int(min(ys)), int(max(ys)) + 1):
        if y < 0 or y >= H:
            continue
        xs = []
        n = len(pts)
        for i in range(n):
            x1, y1 = pts[i]
            x2, y2 = pts[(i + 1) % n]
            if (y1 <= y < y2) or (y2 <= y < y1):
                xs.append(x1 + (y - y1) * (x2 - x1) / (y2 - y1))
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            xa = max(0, int(xs[k]))
            xb = min(W, int(xs[k + 1]))
            if xb > xa:
                rows[y][xa * 3:xb * 3] = bytes(rgb) * (xb - xa)


def catmull(points, samples_per_seg=26):
    pts = [points[0]] + list(points) + [points[-1]]
    out = []
    for i in range(len(pts) - 3):
        p0, p1, p2, p3 = pts[i], pts[i + 1], pts[i + 2], pts[i + 3]
        for j in range(samples_per_seg):
            t = j / samples_per_seg
            t2 = t * t
            t3 = t2 * t
            x = 0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t
                       + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                       + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
            y = 0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t
                       + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                       + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
            out.append((x, y))
    out.append(points[-1])
    return out


# 5x7 bitmap font for the product labels.
FONT = {
    'A': ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    'C': ("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    'E': ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    'F': ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    'G': ("01110", "10001", "10000", "10111", "10001", "10001", "01111"),
    'H': ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    'I': ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    'L': ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    'M': ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    'N': ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    'O': ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    'P': ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    'R': ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    'S': ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    'T': ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    'U': ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    '2': ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
    '0': ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    '1': ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    '%': ("11001", "11010", "00010", "00100", "01000", "01011", "10011"),
    '-': ("00000", "00000", "00000", "01110", "00000", "00000", "00000"),
    ' ': ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
}


def text_width(text, s):
    return len(text) * 6 * s - s


def draw_text(x, y, s, text, rgb):
    cx = int(x)
    for ch in text:
        g = FONT.get(ch, FONT[' '])
        for gy in range(7):
            bits = g[gy]
            for gx in range(5):
                if bits[gx] == '1':
                    for yy in range(int(y) + gy * s, int(y) + (gy + 1) * s):
                        if 0 <= yy < H:
                            xa = max(0, cx + gx * s)
                            xb = min(W, cx + (gx + 1) * s)
                            if xb > xa:
                                rows[yy][xa * 3:xb * 3] = bytes(rgb) * (xb - xa)
        cx += 6 * s
    return cx - s


# ---- 1. Studio backdrop: vertical gradient + soft key light ----
top = (245, 246, 248)
bot = (214, 217, 223)
for y in range(H):
    t = y / (H - 1)
    r = int(top[0] + (bot[0] - top[0]) * t)
    g = int(top[1] + (bot[1] - top[1]) * t)
    b = int(top[2] + (bot[2] - top[2]) * t)
    rows[y][:] = bytes((r, g, b)) * W
for _dy in range(-260, 261, 4):
    yy = 360 + _dy
    if 0 <= yy < H:
        hw = int(520 * math.sqrt(max(0.0, 1 - (_dy / 300.0) ** 2))) if abs(_dy) < 300 else 0
        a = 0.10 * (1 - abs(_dy) / 300.0)
        lighten_span(yy, 512 - hw, 512 + hw, a)

# ---- 2. Floor shadows ----
ellipse_fade(425, 596, 300, 36, 0.20, (38, 40, 48))
ellipse_fade(425, 590, 240, 24, 0.16, (38, 40, 48))
ellipse_fade(860, 664, 125, 19, 0.18, (38, 40, 48))

# ---- 3. The cable: loops from the output port back to the input ----
cable_pts = [(678, 445), (715, 500), (722, 610), (700, 710), (620, 785),
             (480, 808), (330, 798), (210, 745), (150, 645), (135, 520),
             (172, 445)]
path = catmull(cable_pts)
for (px, py) in path:
    disc(px, py, 13, (56, 61, 70))
for idx, (px, py) in enumerate(path):
    disc(px - 4, py - 5, 4, (148, 156, 168), 0.45)

# ---- 4. The power bank: manufactured silver-white slab ----
rrect(166, 326, 684, 584, 48, (228, 230, 234), (246, 247, 249))
rrect(170, 330, 680, 580, 46, (252, 253, 255), (226, 228, 232))
# top edge highlight + bottom shade
blend_span(332, 200, 650, (255, 255, 255), 0.55)
blend_span(333, 200, 650, (255, 255, 255), 0.35)
for yy in range(566, 580):
    blend_span(yy, 200, 650, (150, 154, 162), 0.10 + (yy - 566) * 0.012)
# side shading: soft left light, right shade (applied by the gradient)
# USB-C ports (dark insets on both ends)
rrect(170, 424, 186, 466, 6, (28, 30, 36), (28, 30, 36))
rrect(664, 424, 680, 466, 6, (28, 30, 36), (28, 30, 36))
# connector plugs where the cable meets the ports
rrect(652, 430, 700, 460, 8, (196, 200, 206), (168, 172, 180))
rrect(150, 430, 198, 460, 8, (196, 200, 206), (168, 172, 180))

# ---- 5. Display: glowing readout on the bank ----
rrect(248, 366, 602, 450, 18, (14, 18, 24), (14, 18, 24))
rrect(252, 370, 598, 446, 15, (18, 24, 32), (12, 16, 22))
bolt = [(382, 384), (354, 384), (368, 406), (350, 406),
        (378, 438), (370, 412), (388, 412)]
poly_fill(bolt, (255, 210, 62))
draw_text(414, 390, 4, "100%", (125, 255, 155))

# ---- 6. Product labels (text belongs to the product only) ----
draw_text(425 - text_width("SELF-CHARGING", 2) // 2, 468, 2,
          "SELF-CHARGING", (96, 102, 112))
draw_text(425 - text_width("LOOPCELL", 4) // 2, 500, 4,
          "LOOPCELL", (42, 46, 54))
draw_text(425 - text_width("20000 MAH", 2) // 2, 544, 2,
          "20000 MAH", (110, 116, 126))

# ---- 7. The one accessory: a smartphone, battery full ----
rrect(756, 496, 964, 654, 28, (22, 25, 31), (22, 25, 31))
rrect(760, 500, 960, 650, 26, (30, 34, 41), (18, 21, 27))
rrect(774, 514, 946, 636, 18, (238, 244, 255), (206, 223, 255))
# battery icon, full
bx, by = 806, 540
fill_rect(bx, by, bx + 92, by + 34, (40, 46, 56))
fill_rect(bx + 4, by + 4, bx + 88, by + 30, (238, 244, 255))
fill_rect(bx + 4, by + 4, bx + 88, by + 30, (76, 200, 110))
fill_rect(bx + 92, by + 10, bx + 100, by + 24, (40, 46, 56))
draw_text(860 - text_width("100%", 3) // 2, 592, 3, "100%", (40, 46, 56))

# ---- 8. Subtle deterministic grain (studio texture, keeps PNG small) ----
rng = random.Random(20261121)
for _ in range(5000):
    gx = rng.randrange(W)
    gy = rng.randrange(H)
    i = gx * 3
    d = rng.choice((-4, -3, 3, 4))
    for c in range(3):
        v = rows[gy][i + c] + d
        rows[gy][i + c] = 0 if v < 0 else 255 if v > 255 else v

# ---- 9. Encode PNG (stdlib zlib) and write it ----
raw = b"".join(b"\x00" + bytes(r) for r in rows)


def _chunk(typ, payload):
    out = struct.pack(">I", len(payload)) + typ + payload
    return out + struct.pack(">I", zlib.crc32(typ + payload) & 0xFFFFFFFF)


png = (b"\x89PNG\r\n\x1a\n"
       + _chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
       + _chunk(b"IDAT", zlib.compress(raw, 9))
       + _chunk(b"IEND", b""))

parent = os.path.dirname(OUT)
if parent:
    os.makedirs(parent, exist_ok=True)
with open(OUT, "wb") as f:
    f.write(png)
print("wrote %s %d bytes 1024x1024" % (OUT, len(png)))
