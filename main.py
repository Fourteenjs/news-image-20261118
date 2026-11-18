#!/usr/bin/env python3
"""The World in One Page -- Wednesday 18 November 2026.
make.fun news-image-20261118, round 1. A pure-stdlib (Python 3.13) program:
it draws the whole front page itself -- real serif typography from a
subsetted Liberation Serif vector font (fonts.bin, generated from the
system font by a dev tool; the entry only reads the binary), a Natural
Earth land mask (map.bin), vector pictograms, and a pinned world map --
and writes it to /output/entry.png. No network, no timestamps, no
randomness: two runs write byte-identical files.

Design follows the winning front-page pattern (dark navy masthead with
the date in huge cream serif, two illustrated lead stories, twelve
illustrated story tiles, a world map with numbered pins, and an "ALSO
ON" list running to forty stories), with three improvements over our
17 Nov round 2: richer lead illustrations (a full Gulf map-scene and a
collapsed Kerch arch with debris, smoke and the rail span still
standing), bigger tile art bands (~44% of tile height, as in the
17 Nov #2 entry), and 3x supersampled glyph rasterisation for crisper
small text. Every story carries a flag, a region and a location.
"""
import math
import os
import struct
import sys
import zlib

W, H = 1024, 1024

# ---------------------------------------------------------------- palette
PAPER = (244, 239, 228)
INK = (26, 26, 26)
NAVY = (16, 31, 60)
NAVY2 = (24, 46, 88)
CREAM = (244, 236, 214)
GOLD = (201, 162, 39)
GOLD_LT = (226, 196, 96)
RED = (178, 34, 34)
RED_DK = (139, 26, 26)
BLUE = (38, 84, 138)
TEAL = (31, 122, 110)
GREEN = (52, 120, 62)
ORANGE = (196, 102, 26)
GREY = (110, 110, 104)
GREY_LT = (200, 196, 184)
SEA = (168, 196, 214)
SEA_DK = (90, 130, 165)
SAND = (216, 201, 163)
SAND_DK = (196, 176, 128)
SKY = (208, 224, 234)

TOPIC = {
    "war": (178, 34, 34),
    "politics": (38, 84, 138),
    "economy": (52, 120, 62),
    "health": (31, 122, 110),
    "disaster": (196, 102, 26),
}
TOPIC_TINT = {
    "war": (243, 222, 218),
    "politics": (220, 232, 243),
    "economy": (222, 238, 222),
    "health": (218, 238, 233),
    "disaster": (247, 232, 214),
}
TOPIC_LABEL = {
    "war": "WAR & SECURITY",
    "politics": "POLITICS",
    "economy": "ECONOMY & TECH",
    "health": "HEALTH & CLIMATE",
    "disaster": "DISASTER",
}

# -------------------------------------------------------------------- flags
# Tiny flag icons, drawn as ops in a 30x20 space and scaled to any box:
# ("rect", x0, y0, x1, y1, colour), ("disc", cx, cy, r, colour),
# ("tri", [(x, y), ...], colour). Simplified but recognisable at 14-34 px.
_W = (255, 255, 255)
_BK = (20, 20, 20)
FLAGS = {
    "ukraine": [("rect", 0, 0, 30, 10, (0, 91, 172)),
                ("rect", 0, 10, 30, 20, (255, 213, 0))],
    "iran": [("rect", 0, 0, 30, 7, (0, 122, 61)),
             ("rect", 0, 7, 30, 13, _W),
             ("rect", 0, 13, 30, 20, (218, 0, 0)),
             ("disc", 15, 10, 2, (218, 0, 0))],
    "bahrain": [("rect", 0, 0, 10, 20, _W),
                ("rect", 10, 0, 30, 20, (206, 17, 38)),
                ("tri", [(10, 0), (16, 2), (10, 4)], _W),
                ("tri", [(10, 4), (16, 6), (10, 8)], _W),
                ("tri", [(10, 8), (16, 10), (10, 12)], _W),
                ("tri", [(10, 12), (16, 14), (10, 16)], _W),
                ("tri", [(10, 16), (16, 18), (10, 20)], _W)],
    "kuwait": [("rect", 0, 0, 30, 7, (0, 122, 61)),
               ("rect", 0, 7, 30, 13, _W),
               ("rect", 0, 13, 30, 20, (206, 17, 38)),
               ("tri", [(0, 0), (12, 10), (0, 20)], _BK)],
    "usa": [("rect", 0, 0, 30, 20, _W),
            ("rect", 0, 0, 30, 3, (178, 34, 52)),
            ("rect", 0, 6, 30, 9, (178, 34, 52)),
            ("rect", 0, 11, 30, 14, (178, 34, 52)),
            ("rect", 0, 17, 30, 20, (178, 34, 52)),
            ("rect", 0, 0, 12, 11, (60, 59, 110)),
            ("disc", 3, 3, 1, _W), ("disc", 8, 3, 1, _W),
            ("disc", 3, 8, 1, _W), ("disc", 8, 8, 1, _W)],
    "uk": [("rect", 0, 0, 30, 20, (0, 36, 125)),
           ("tri", [(0, 0), (8, 0), (30, 20), (22, 20)], _W),
           ("tri", [(30, 0), (22, 0), (0, 20), (8, 20)], _W),
           ("rect", 13, 0, 17, 20, _W),
           ("rect", 0, 8, 30, 12, _W),
           ("rect", 14, 0, 16, 20, (200, 16, 46)),
           ("rect", 0, 9, 30, 11, (200, 16, 46))],
    "russia": [("rect", 0, 0, 30, 7, _W),
               ("rect", 0, 7, 30, 13, (0, 57, 166)),
               ("rect", 0, 13, 30, 20, (213, 43, 30))],
    "japan": [("rect", 0, 0, 30, 20, _W),
              ("disc", 15, 10, 5, (188, 0, 45))],
    "drc": [("rect", 0, 0, 30, 20, (0, 127, 214)),
            ("tri", [(0, 20), (0, 11), (30, 0), (30, 9)], (206, 17, 38)),
            ("disc", 7, 5, 2, (247, 210, 0))],
    "mongolia": [("rect", 0, 0, 10, 20, (196, 42, 51)),
                 ("rect", 10, 0, 20, 20, (0, 94, 184)),
                 ("rect", 20, 0, 30, 20, (196, 42, 51)),
                 ("disc", 5, 10, 2.5, (255, 213, 0))],
    "turkey": [("rect", 0, 0, 30, 20, (227, 10, 23)),
               ("disc", 12, 10, 5, _W),
               ("disc", 13.5, 10, 4, (227, 10, 23)),
               ("disc", 20, 10, 1.5, _W)],
    "india": [("rect", 0, 0, 30, 7, (255, 153, 51)),
              ("rect", 0, 7, 30, 13, _W),
              ("rect", 0, 13, 30, 20, (19, 136, 38)),
              ("disc", 15, 10, 2.5, (6, 32, 119))],
    "france": [("rect", 0, 0, 10, 20, (0, 85, 164)),
               ("rect", 10, 0, 20, 20, _W),
               ("rect", 20, 0, 30, 20, (239, 65, 53))],
    "spain": [("rect", 0, 0, 30, 5, (198, 12, 48)),
              ("rect", 0, 5, 30, 15, (255, 201, 0)),
              ("rect", 0, 15, 30, 20, (198, 12, 48))],
    "bangladesh": [("rect", 0, 0, 30, 20, (0, 106, 78)),
                   ("disc", 13, 10, 5.5, (244, 42, 65))],
    "germany": [("rect", 0, 0, 30, 7, _BK),
                ("rect", 0, 7, 30, 13, (221, 0, 0)),
                ("rect", 0, 13, 30, 20, (255, 206, 0))],
    "philippines": [("rect", 0, 0, 30, 10, (0, 56, 168)),
                    ("rect", 0, 10, 30, 20, (206, 17, 38)),
                    ("tri", [(0, 0), (12, 10), (0, 20)], _W),
                    ("disc", 5, 10, 1.5, (252, 209, 22))],
    "israel": [("rect", 0, 0, 30, 20, _W),
               ("rect", 0, 2, 30, 5, (0, 56, 184)),
               ("rect", 0, 15, 30, 18, (0, 56, 184)),
               ("disc", 15, 10, 2.5, (0, 56, 184)),
               ("disc", 15, 10, 1.2, _W)],
    "serbia": [("rect", 0, 0, 30, 7, (196, 42, 51)),
               ("rect", 0, 7, 30, 13, (12, 64, 148)),
               ("rect", 0, 13, 30, 20, _W)],
    "moldova": [("rect", 0, 0, 10, 20, (0, 70, 173)),
                ("rect", 10, 0, 20, 20, (255, 210, 0)),
                ("rect", 20, 0, 30, 20, (205, 0, 0))],
    "czechia": [("rect", 0, 0, 30, 10, _W),
                ("rect", 0, 10, 30, 20, (215, 20, 26)),
                ("tri", [(0, 0), (15, 10), (0, 20)], (17, 71, 151))],
    "palestine": [("rect", 0, 0, 30, 7, _BK),
                  ("rect", 0, 7, 30, 13, _W),
                  ("rect", 0, 13, 30, 20, (0, 122, 61)),
                  ("tri", [(0, 0), (10, 10), (0, 20)], (238, 42, 43))],
    "kenya": [("rect", 0, 0, 30, 6, _BK),
              ("rect", 0, 6, 30, 8, _W),
              ("rect", 0, 8, 30, 12, (187, 18, 36)),
              ("rect", 0, 12, 30, 14, _W),
              ("rect", 0, 14, 30, 20, (0, 122, 61)),
              ("disc", 15, 10, 2, (187, 18, 36))],
    "australia": [("rect", 0, 0, 30, 20, (0, 0, 139)),
                  ("rect", 0, 0, 15, 10, (0, 0, 139)),
                  ("rect", 0, 4, 15, 6, _W),
                  ("rect", 7, 0, 9, 10, _W),
                  ("disc", 22, 6, 1, _W), ("disc", 25, 14, 1, _W),
                  ("disc", 19, 15, 1, _W)],
    "brazil": [("rect", 0, 0, 30, 20, (0, 156, 59)),
               ("tri", [(15, 2), (28, 10), (15, 18), (2, 10)], (255, 223, 0)),
               ("disc", 15, 10, 3.5, (0, 39, 118))],
    "singapore": [("rect", 0, 0, 30, 10, (239, 51, 64)),
                  ("rect", 0, 10, 30, 20, _W),
                  ("disc", 9, 5, 3, _W),
                  ("disc", 10, 5, 2.5, (239, 51, 64)),
                  ("disc", 14, 3, 0.8, _W)],
    "canada": [("rect", 0, 0, 8, 20, (255, 0, 0)),
               ("rect", 8, 0, 22, 20, _W),
               ("rect", 22, 0, 30, 20, (255, 0, 0)),
               ("disc", 15, 10, 2.5, (255, 0, 0))],
    "china": [("rect", 0, 0, 30, 20, (222, 0, 0)),
              ("disc", 6, 5, 1.8, (255, 222, 0)),
              ("disc", 12, 3, 1, (255, 222, 0)),
              ("disc", 13, 7, 1, (255, 222, 0))],
    "eu": [("rect", 0, 0, 30, 20, (0, 51, 153)),
           ("disc", 15, 4, 1, (255, 204, 0)),
           ("disc", 20, 7, 1, (255, 204, 0)),
           ("disc", 20, 13, 1, (255, 204, 0)),
           ("disc", 15, 16, 1, (255, 204, 0)),
           ("disc", 10, 13, 1, (255, 204, 0)),
           ("disc", 10, 7, 1, (255, 204, 0))],
    "switzerland": [("rect", 0, 0, 30, 20, (218, 0, 0)),
                    ("rect", 13, 4, 17, 16, _W),
                    ("rect", 8, 8, 22, 12, _W)],
    "south_africa": [("rect", 0, 0, 30, 10, (222, 0, 0)),
                     ("rect", 0, 10, 30, 20, (0, 51, 153)),
                     ("tri", [(0, 0), (30, 10), (0, 20)], (0, 122, 61)),
                     ("tri", [(0, 3), (11, 10), (0, 17)], _BK)],
    "guinea": [("rect", 0, 0, 10, 20, (206, 17, 38)),
               ("rect", 10, 0, 20, 20, (249, 211, 0)),
               ("rect", 20, 0, 30, 20, (0, 148, 69))],
    "haiti": [("rect", 0, 0, 30, 10, (0, 32, 159)),
              ("rect", 0, 10, 30, 20, (210, 16, 52)),
              ("rect", 12, 7, 18, 13, _W)],
    "vatican": [("rect", 0, 0, 15, 20, (255, 215, 0)),
                ("rect", 15, 0, 30, 20, _W),
                ("disc", 22, 10, 2, (206, 17, 38))],
    "rwanda": [("rect", 0, 0, 30, 10, (0, 167, 223)),
               ("rect", 0, 10, 30, 15, (255, 210, 0)),
               ("rect", 0, 15, 30, 20, (0, 122, 61)),
               ("disc", 24, 5, 2.5, (255, 210, 0))],
    "yemen": [("rect", 0, 0, 30, 7, (206, 17, 38)),
              ("rect", 0, 7, 30, 13, _W),
              ("rect", 0, 13, 30, 20, _BK)],
    "estonia": [("rect", 0, 0, 30, 7, (0, 114, 206)),
                ("rect", 0, 7, 30, 13, _BK),
                ("rect", 0, 13, 30, 20, _W)],
    "png": [("tri", [(0, 0), (30, 0), (0, 20)], (206, 17, 38)),
            ("tri", [(0, 20), (30, 0), (30, 20)], _BK),
            ("disc", 21, 6, 2, (255, 210, 0)),
            ("disc", 8, 14, 1, _W), ("disc", 13, 17, 1, _W)],
    "fiji": [("rect", 0, 0, 30, 20, (104, 191, 232)),
             ("rect", 0, 0, 15, 10, (0, 36, 125)),
             ("rect", 6, 0, 9, 10, _W),
             ("rect", 0, 4, 15, 6, _W),
             ("disc", 23, 11, 2, (255, 210, 0))],
    "italy": [("rect", 0, 0, 10, 20, (0, 146, 70)),
              ("rect", 10, 0, 20, 20, _W),
              ("rect", 20, 0, 30, 20, (205, 0, 0))],
    "south_korea": [("rect", 0, 0, 30, 20, _W),
                    ("disc", 15, 8, 3.5, (205, 0, 0)),
                    ("disc", 15, 12, 3.5, (0, 56, 147)),
                    ("rect", 3, 3, 8, 5, _BK),
                    ("rect", 22, 3, 27, 5, _BK),
                    ("rect", 3, 15, 8, 17, _BK),
                    ("rect", 22, 15, 27, 17, _BK)],
    "cook_islands": [("rect", 0, 0, 30, 20, (0, 47, 108)),
                     ("rect", 0, 0, 15, 10, (0, 36, 125)),
                     ("rect", 6, 0, 9, 10, _W),
                     ("rect", 0, 4, 15, 6, _W),
                     ("disc", 22, 6, 1, _W), ("disc", 25, 11, 1, _W),
                     ("disc", 22, 15, 1, _W), ("disc", 19, 11, 1, _W)],
    "un": [("rect", 0, 0, 30, 20, (91, 146, 196)),
           ("disc", 15, 10, 6, _W),
           ("disc", 15, 10, 4, (91, 146, 196))],
}


def draw_flag(cv, name, x, y, w, h):
    """Draw a flag from FLAGS into the box (x, y, w, h), with a thin
    border so light flags read on paper."""
    ops = FLAGS.get(name)
    if not ops:
        return
    sx = w / 30.0
    sy = h / 20.0
    for op in ops:
        if op[0] == "rect":
            _, x0, y0, x1, y1, c = op
            cv.fill_rect(int(round(x + x0 * sx)), int(round(y + y0 * sy)),
                         max(1, int(round((x1 - x0) * sx))),
                         max(1, int(round((y1 - y0) * sy))), c)
        elif op[0] == "disc":
            _, cx, cy, r, c = op
            cv.circle(int(round(x + cx * sx)), int(round(y + cy * sy)),
                      max(1, int(round(r * (sx + sy) / 2))), c)
        elif op[0] == "tri":
            _, pts, c = op
            cv.poly([(x + px * sx, y + py * sy) for (px, py) in pts], c)
    cv.fill_rect(x, y, w, 1, (120, 116, 108))
    cv.fill_rect(x, y + h - 1, w, 1, (120, 116, 108))
    cv.fill_rect(x, y, 1, h, (120, 116, 108))
    cv.fill_rect(x + w - 1, y, 1, h, (120, 116, 108))


# ------------------------------------------------------------------- canvas
class Canvas:
    def __init__(self, w, h, bg):
        self.w = w
        self.h = h
        self.px = bytearray(w * h * 3)
        self.fill_rect(0, 0, w, h, bg)

    def _off(self, x, y):
        return (y * self.w + x) * 3

    def set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            o = self._off(x, y)
            self.px[o] = c[0]
            self.px[o + 1] = c[1]
            self.px[o + 2] = c[2]

    def blend(self, x, y, c, a):
        """Alpha-blend colour c (a = 0..255) over the pixel at x, y."""
        if a <= 0 or not (0 <= x < self.w and 0 <= y < self.h):
            return
        o = self._off(x, y)
        if a >= 255:
            self.px[o] = c[0]
            self.px[o + 1] = c[1]
            self.px[o + 2] = c[2]
            return
        ia = 255 - a
        self.px[o] = (c[0] * a + self.px[o] * ia) // 255
        self.px[o + 1] = (c[1] * a + self.px[o + 1] * ia) // 255
        self.px[o + 2] = (c[2] * a + self.px[o + 2] * ia) // 255

    def fill_rect(self, x, y, w, h, c):
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.w, x + w)
        y1 = min(self.h, y + h)
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes(c) * (x1 - x0)
        for yy in range(y0, y1):
            o = self._off(x0, yy)
            self.px[o:o + len(row)] = row

    def hline(self, x, y, w, c, t=1):
        self.fill_rect(x, y - t // 2, w, t, c)

    def vline(self, x, y, h, c, t=1):
        self.fill_rect(x - t // 2, y, t, h, c)

    def line(self, x0, y0, x1, y1, c, t=1):
        """Bresenham line with round caps of thickness t."""
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        r = max(0, t // 2)
        while True:
            if r:
                self.circle(x0, y0, r, c)
            else:
                self.set(x0, y0, c)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def circle(self, cx, cy, r, c):
        if r <= 0:
            self.set(cx, cy, c)
            return
        for yy in range(cy - r, cy + r + 1):
            dyy = yy - cy
            dx = int((r * r - dyy * dyy) ** 0.5)
            self.fill_rect(cx - dx, yy, 2 * dx + 1, 1, c)

    def ring(self, cx, cy, r, c, t=1):
        for yy in range(cy - r - 1, cy + r + 2):
            dyy = yy - cy
            for xx in range(cx - r - 1, cx + r + 2):
                dxx = xx - cx
                d = (dxx * dxx + dyy * dyy) ** 0.5
                if abs(d - r) <= t / 2.0 + 0.4:
                    self.set(xx, yy, c)

    def poly(self, pts, c):
        """Fill a polygon (even-odd scanline fill). pts: [(x, y), ...]."""
        if len(pts) < 3:
            return
        edges = []
        n = len(pts)
        miny = min(p[1] for p in pts)
        maxy = max(p[1] for p in pts)
        for i in range(n):
            x0, y0 = pts[i]
            x1, y1 = pts[(i + 1) % n]
            if y0 == y1:
                continue
            edges.append((x0, y0, x1, y1))
        for yy in range(int(miny), int(maxy) + 1):
            yc = yy + 0.5
            xs = []
            for (x0, y0, x1, y1) in edges:
                if (y0 <= yc < y1) or (y1 <= yc < y0):
                    xs.append(x0 + (yc - y0) * (x1 - x0) / (y1 - y0))
            xs.sort()
            for i in range(0, len(xs) - 1, 2):
                xa = int(xs[i] + 0.5)
                xb = int(xs[i + 1] + 0.5)
                if xb > xa:
                    self.fill_rect(xa, yy, xb - xa, 1, c)

    def polyline(self, pts, c, t=1):
        for i in range(len(pts) - 1):
            self.line(int(pts[i][0]), int(pts[i][1]),
                      int(pts[i + 1][0]), int(pts[i + 1][1]), c, t)


# -------------------------------------------------------------- PNG writer
def _png_chunk(typ, data):
    out = struct.pack(">I", len(data)) + typ + data
    out += struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)
    return out


def write_png(cv, path):
    w, h = cv.w, cv.h
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    raw = bytearray()
    stride = w * 3
    for y in range(h):
        row = bytes(cv.px[y * stride:(y + 1) * stride])
        prev = bytes(cv.px[(y - 1) * stride:y * stride]) if y else bytes(stride)
        best = None
        # filter 0 (none), 1 (sub), 2 (up): pick smallest abs-sum.
        for f in (0, 1, 2):
            if f == 0:
                fb = row
            elif f == 1:
                b = bytearray(row)
                for i in range(stride - 1, 2, -1):
                    b[i] = (b[i] - b[i - 3]) & 0xFF
                fb = bytes(b)
            else:
                fb = bytes((row[i] - prev[i]) & 0xFF for i in range(stride))
            score = sum(v if v < 128 else 256 - v for v in fb)
            if best is None or score < best[0]:
                best = (score, f, fb)
        raw.append(best[1])
        raw += best[2]
    comp = zlib.compress(bytes(raw), 9)
    png = b"\x89PNG\r\n\x1a\n"
    png += _png_chunk(b"IHDR", ihdr)
    png += _png_chunk(b"IDAT", comp)
    png += _png_chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


# ------------------------------------------------------------ vector fonts
# fonts.bin (VFNT1): subsetted Liberation Serif Regular + Bold, quadratic
# outlines as (x, y, on-curve) points in font units. Loaded here, then
# rasterised in pure Python with supersampling for smooth edges.
# SS = 3 (up from 2 in the 17 Nov round 2): measured -- glyph raster
# stays fast (whole page still a few seconds, far under the 60 s wall)
# and small text is visibly smoother; output stays byte-deterministic.
SS = 3


class Font:
    def __init__(self, name, upm, asc, desc, glyphs):
        self.name = name
        self.upm = upm
        self.asc = asc
        self.desc = desc
        self.glyphs = glyphs  # cp -> (advance, contours); contour = [(x,y,on)]


def load_fonts(path):
    with open(path, "rb") as f:
        d = f.read()
    assert d[:5] == b"VFNT1", "bad font file"
    n = d[5]
    o = 6
    fonts = {}
    for _ in range(n):
        nl = d[o]
        o += 1
        name = d[o:o + nl].decode("ascii")
        o += nl
        upm, asc, desc, ng = struct.unpack_from("<HhhH", d, o)
        o += 8
        glyphs = {}
        for _g in range(ng):
            cp, adv, nc = struct.unpack_from("<IHB", d, o)
            o += 7
            contours = []
            for _c in range(nc):
                np_, = struct.unpack_from("<H", d, o)
                o += 2
                pts = []
                for _p in range(np_):
                    x, y, fl = struct.unpack_from("<hhB", d, o)
                    o += 5
                    pts.append((x, y, fl))
                contours.append(pts)
            glyphs[cp] = (adv, contours)
        fonts[name] = Font(name, upm, asc, desc, glyphs)
    return fonts


def _flatten_contour(contour, scale):
    """One TTF contour -> polygon points in px (y down), glyph origin (0,0)
    on the baseline. Quadratic segments are subdivided for smoothness."""
    pts = [(x, y, on) for (x, y, on) in contour]
    if not pts:
        return []
    # Find the first on-curve point; rotate so it starts the contour.
    start = None
    for i, p in enumerate(pts):
        if p[2]:
            start = i
            break
    if start is None:
        # All off-curve: implied on-curve point between last and first.
        mx = (pts[-1][0] + pts[0][0]) / 2.0
        my = (pts[-1][1] + pts[0][1]) / 2.0
        pts = [(mx, my, 1)] + pts
        start = 0
    rot = pts[start:] + pts[:start]
    # Build segments: ("L", x, y) or ("Q", cx, cy, ex, ey) in font units.
    segs = []
    m = len(rot)
    i = 1
    while i < m:
        x, y, on = rot[i]
        if on:
            segs.append(("L", x, y))
            i += 1
        else:
            if i + 1 < m:
                nx, ny, non = rot[i + 1]
                if non:
                    segs.append(("Q", x, y, nx, ny))
                    i += 2
                else:
                    segs.append(("Q", x, y, (x + nx) / 2.0, (y + ny) / 2.0))
                    i += 1
            else:
                segs.append(("Q", x, y, rot[0][0], rot[0][1]))
                i += 1
    # Walk the segments, emitting px points (y down).
    out = [(rot[0][0] * scale, -rot[0][1] * scale)]
    cx, cy = rot[0][0], rot[0][1]
    for s in segs:
        if s[0] == "L":
            out.append((s[1] * scale, -s[2] * scale))
            cx, cy = s[1], s[2]
        else:
            _, qx, qy, ex, ey = s
            span = max(abs(qx - cx), abs(qy - cy), abs(ex - cx), abs(ey - cy))
            k = max(3, min(20, int(span * scale / 1.5) + 1))
            for j in range(1, k + 1):
                t = j / k
                u = 1.0 - t
                x = u * u * cx + 2 * u * t * qx + t * t * ex
                y = u * u * cy + 2 * u * t * qy + t * t * ey
                out.append((x * scale, -y * scale))
            cx, cy = ex, ey
    return out


_GLYPH_CACHE = {}


def render_glyph(font, cp, size):
    """Rasterise one glyph at `size` px (SS x supersampled). Returns
    (alpha_bytes, w, h, ox, oy, advance_px) where (ox, oy) is the bitmap's
    top-left relative to the pen position on the baseline, in final px."""
    key = (font.name, round(size, 2), cp)
    hit = _GLYPH_CACHE.get(key)
    if hit is not None:
        return hit
    adv, contours = font.glyphs.get(cp, font.glyphs.get(ord("?"), (0, [])))
    adv_px = adv * size / font.upm
    if not contours:
        res = (b"", 0, 0, 0, 0, adv_px)
        _GLYPH_CACHE[key] = res
        return res
    ss = SS
    scale = size / font.upm * ss
    polys = []
    minx = miny = 1e18
    maxx = maxy = -1e18
    for contour in contours:
        poly = _flatten_contour(contour, scale)
        if len(poly) < 3:
            continue
        polys.append(poly)
        for (x, y) in poly:
            minx = min(minx, x)
            maxx = max(maxx, x)
            miny = min(miny, y)
            maxy = max(maxy, y)
    if not polys:
        res = (b"", 0, 0, 0, 0, adv_px)
        _GLYPH_CACHE[key] = res
        return res
    bx0 = int(minx // 1)
    by0 = int(miny // 1)
    bx1 = int(maxx // 1) + 1
    by1 = int(maxy // 1) + 1
    w2 = bx1 - bx0
    h2 = by1 - by0
    mask = bytearray(w2 * h2)
    # One even-odd scanline fill over the edges of ALL contours together:
    # a glyph's inner contours are holes, so they must punch through the
    # outer contour in the same pass (filling each contour separately
    # would fill the holes solid).
    edges = []
    for poly in polys:
        n = len(poly)
        for i in range(n):
            x0, y0 = poly[i]
            x1, y1 = poly[(i + 1) % n]
            if y0 != y1:
                edges.append((x0, y0, x1, y1))
    for yy in range(h2):
        yc = by0 + yy + 0.5
        xs = []
        for (x0, y0, x1, y1) in edges:
            if (y0 <= yc < y1) or (y1 <= yc < y0):
                xs.append(x0 + (yc - y0) * (x1 - x0) / (y1 - y0))
        xs.sort()
        for i in range(0, len(xs) - 1, 2):
            xa = max(0, int(xs[i] + 0.5) - bx0)
            xb = min(w2, int(xs[i + 1] + 0.5) - bx0)
            if xb > xa:
                row = yy * w2
                mask[row + xa:row + xb] = b"\xff" * (xb - xa)
    # Box-downsample ss x ss -> 8-bit alpha.
    w = (w2 + ss - 1) // ss
    h = (h2 + ss - 1) // ss
    alpha = bytearray(w * h)
    for yy in range(h):
        for xx in range(w):
            s = 0
            cnt = 0
            for dy in range(ss):
                y2 = yy * ss + dy
                if y2 >= h2:
                    continue
                for dx in range(ss):
                    x2 = xx * ss + dx
                    if x2 >= w2:
                        continue
                    s += mask[y2 * w2 + x2]
                    cnt += 1
            alpha[yy * w + xx] = (s * 255) // (255 * cnt) if cnt else 0
    ox = int(round(bx0 / ss))
    oy = int(round(by0 / ss))
    res = (bytes(alpha), w, h, ox, oy, adv_px)
    _GLYPH_CACHE[key] = res
    return res


def text_width(font, size, text, tracking=0.0):
    w = 0.0
    for ch in text:
        cp = ord(ch)
        adv, _ = font.glyphs.get(cp, font.glyphs.get(ord("?"), (0, [])))
        w += adv * size / font.upm + tracking
    if text:
        w -= tracking
    return w


def draw_text(cv, font, size, x, y_base, text, color, tracking=0.0,
              align="left"):
    """Draw text with the baseline at y_base. x is the left edge (or the
    centre / right edge when align is center / right). Returns width."""
    w = text_width(font, size, text, tracking)
    if align == "center":
        x = x - w / 2.0
    elif align == "right":
        x = x - w
    pen = x
    for ch in text:
        cp = ord(ch)
        alpha, gw, gh, ox, oy, adv = render_glyph(font, cp, size)
        if gw and gh:
            dx = int(round(pen)) + ox
            dy = int(round(y_base)) + oy
            for yy in range(gh):
                row = yy * gw
                for xx in range(gw):
                    a = alpha[row + xx]
                    if a:
                        cv.blend(dx + xx, dy + yy, color, a)
        pen += adv + tracking
    return w


def wrap_text(font, size, text, max_w, tracking=0.0):
    """Greedy word wrap. Returns a list of lines (each fits max_w)."""
    words = text.split(" ")
    lines = []
    cur = ""
    for word in words:
        trial = word if not cur else cur + " " + word
        if text_width(font, size, trial, tracking) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


# ------------------------------------------------------------- pictograms
# Each pictogram draws inside a box (x, y, w, h) in ink + one accent.
# Flat vector style, readable at tile size (~240x56).
def _cos(a):
    return math.cos(a)


def _sin(a):
    return math.sin(a)


def _flag(cv, x, y, w, h, c1, c2):
    cv.vline(x, y, h, INK, 2)
    cv.poly([(x + 2, y), (x + w, y + h // 4), (x + 2, y + h // 2)], c1)
    cv.poly([(x + 2, y + h // 2), (x + w, y + h * 3 // 4),
             (x + 2, y + h)], c2)


def pic_tanker(cv, x, y, w, h, ink, acc):
    my = y + h * 3 // 5
    cv.poly([(x + 4, my), (x + w - 8, my), (x + w - 20, my + h // 4),
             (x + 14, my + h // 4)], ink)
    cv.fill_rect(x + w // 4, my - h // 4, w // 8, h // 4, acc)
    cv.fill_rect(x + w // 2, my - h // 3, w // 10, h // 3, ink)
    # Blast burst above the funnel: this is a strike, not a calm ship.
    bx, by = x + w * 3 // 4, my - h // 3 - 4
    cv.circle(bx, by, 5, (230, 120, 30))
    cv.circle(bx, by, 2, (255, 200, 60))
    cv.circle(bx - 8, by + 4, 3, (120, 120, 115))
    cv.circle(bx + 7, by - 5, 3, (120, 120, 115))
    cv.hline(x, y + h - 4, w, SEA_DK, 2)
    cv.hline(x + w // 5, y + h - 1, w // 2, SEA_DK, 1)


def pic_flags(cv, x, y, w, h, ink, acc):
    _flag(cv, x + 2, y + 8, 20, 20, RED, (255, 255, 255))
    _flag(cv, x + 34, y + 8, 20, 20, RED, GOLD)
    _flag(cv, x + 66, y + 8, 20, 20, (255, 255, 255), BLUE)
    cv.hline(x + 2, y + h - 6, w - 4, ink, 2)


def pic_globe(cv, x, y, w, h, ink, acc):
    """APEC: a globe with meridians and a small flag on top."""
    cx, cy = x + w // 2, y + h // 2 + 2
    r = h // 2 - 6
    cv.circle(cx, cy, r, (168, 196, 214))
    cv.ring(cx, cy, r, ink, 2)
    cv.ring(cx, cy, r // 2, ink, 1)
    cv.hline(cx - r, cy, 2 * r, ink, 1)
    cv.vline(cx, cy - r, 2 * r, ink, 1)
    # Land dots: the 21 APEC members, suggested not plotted.
    cv.circle(cx - r // 2, cy - r // 3, 3, acc)
    cv.circle(cx + r // 3, cy + r // 4, 3, acc)
    cv.circle(cx + r // 2, cy - r // 2, 2, acc)
    _flag(cv, cx + r - 4, cy - r - 6, 14, 12, RED, GOLD)


def pic_ship(cv, x, y, w, h, ink, acc):
    """Quad maritime surveillance: a grey naval vessel with radar mast
    and a dotted patrol track."""
    my = y + h * 3 // 5
    cv.poly([(x + 4, my), (x + w - 6, my), (x + w - 16, my + h // 4),
             (x + 12, my + h // 4)], (90, 96, 104))
    cv.fill_rect(x + w // 3, my - h // 4, w // 4, h // 4, ink)
    cv.vline(x + w // 2, my - h // 2, h // 4, ink, 2)
    cv.circle(x + w // 2, my - h // 2, 3, acc)
    cv.line(x + w // 2, my - h // 2, x + w // 2 + 8, my - h // 2 - 4, acc, 1)
    # Dotted patrol track arcing over the ship.
    for k in range(6):
        cv.circle(x + 8 + k * 12, y + 6 + (k % 2) * 3, 1, acc)
    cv.hline(x, y + h - 4, w, SEA_DK, 2)
    cv.hline(x + w // 5, y + h - 1, w // 2, SEA_DK, 1)


def pic_chart_down(cv, x, y, w, h, ink, acc):
    cv.vline(x + 6, y + 4, h - 8, ink, 2)
    cv.hline(x + 6, y + h - 6, w - 12, ink, 2)
    pts = [(x + 10, y + 8), (x + w // 3, y + 14), (x + w // 2, y + 10),
           (x + w * 2 // 3, y + h - 12), (x + w - 10, y + h - 8)]
    cv.polyline(pts, acc, 3)
    cv.poly([(x + w - 10, y + h - 8), (x + w - 18, y + h - 14),
             (x + w - 16, y + h - 4)], acc)
    # Gold coins: money lost on the slide.
    cv.circle(x + w - 16, y + 10, 7, (201, 162, 39))
    cv.ring(x + w - 16, y + 10, 4, (139, 105, 20), 1)
    cv.circle(x + w - 30, y + 16, 5, (226, 196, 96))
    cv.ring(x + w - 30, y + 16, 3, (139, 105, 20), 1)


def pic_jet(cv, x, y, w, h, ink, acc):
    def jet(jx, jy, s, c):
        cv.poly([(jx, jy), (jx + 26 * s, jy + 6 * s), (jx, jy + 10 * s)], c)
        cv.poly([(jx + 8 * s, jy + 2 * s), (jx + 16 * s, jy - 6 * s),
                 (jx + 18 * s, jy + 2 * s)], c)
        cv.poly([(jx + 8 * s, jy + 8 * s), (jx + 16 * s, jy + 16 * s),
                 (jx + 18 * s, jy + 8 * s)], c)
    jet(x + 4, y + 4, 1.3, ink)
    jet(x + w // 2 + 2, y + h // 2 - 2, 1.3, acc)
    # Interception burst behind the second jet.
    cv.circle(x + w - 10, y + 8, 4, (230, 120, 30))
    cv.circle(x + w - 10, y + 8, 2, (255, 200, 60))


def pic_virus(cv, x, y, w, h, ink, acc):
    cx, cy = x + w // 2, y + h // 2
    r = h // 4
    for k in range(8):
        ang = k * 3.14159 / 4
        x1 = int(cx + r * 0.9 * _cos(ang))
        y1 = int(cy + r * 0.9 * _sin(ang))
        x2 = int(cx + (r + 7) * _cos(ang))
        y2 = int(cy + (r + 7) * _sin(ang))
        cv.line(x1, y1, x2, y2, acc, 2)
        cv.circle(x2, y2, 2, acc)
    cv.circle(cx, cy, r, ink)
    cv.circle(cx - 3, cy - 3, 2, PAPER)
    cv.circle(cx + 4, cy + 3, 2, PAPER)
    cv.circle(cx + 1, cy - 5, 1, PAPER)


def pic_parliament(cv, x, y, w, h, ink, acc):
    """Parliament building: pediment + dome + columns + steps."""
    cx = x + w // 2
    cv.circle(cx, y + 8, 5, acc)
    cv.poly([(x + 8, y + 14), (cx, y + 4), (x + w - 8, y + 14)], ink)
    cv.fill_rect(x + 8, y + 14, w - 16, 3, ink)
    for k in range(4):
        px = x + 14 + k * (w - 28) // 3
        cv.fill_rect(px, y + 18, 5, h - 26, ink)
    cv.fill_rect(x + 8, y + h - 8, w - 16, 3, ink)
    cv.fill_rect(x + 4, y + h - 4, w - 8, 2, ink)


def pic_tv(cv, x, y, w, h, ink, acc):
    """Television, off air: outline set + dark screen + slash."""
    cv.fill_rect(x + 10, y + 8, w - 20, h - 16, (30, 30, 34))
    cv.hline(x + 10, y + 8, w - 20, ink, 2)
    cv.hline(x + 10, y + h - 8, w - 20, ink, 2)
    cv.vline(x + 10, y + 8, h - 16, ink, 2)
    cv.vline(x + w - 10, y + 8, h - 16, ink, 2)
    cv.line(x + 14, y + 12, x + w - 14, y + h - 12, acc, 3)
    cv.line(x + w // 2 - 6, y + h - 8, x + w // 2 - 3, y + h - 2, ink, 2)
    cv.line(x + w // 2 + 6, y + h - 8, x + w // 2 + 3, y + h - 2, ink, 2)


def pic_cyclone(cv, x, y, w, h, ink, acc):
    cx, cy = x + w // 2, y + h // 2
    pts = []
    for i in range(0, 60):
        t = i / 60.0
        ang = t * 3.14159 * 5
        r = 4 + t * (h // 2 - 4)
        pts.append((cx + r * _cos(ang), cy + r * _sin(ang)))
    cv.polyline(pts, acc, 2)
    cv.circle(cx, cy, 3, ink)


def pic_cyclone2(cv, x, y, w, h, ink, acc):
    """Second cyclone, mirrored spiral (southern hemisphere spins the
    other way) with rain bands, so the two storm tiles differ."""
    cx, cy = x + w // 2 - 6, y + h // 2
    pts = []
    for i in range(0, 60):
        t = i / 60.0
        ang = -t * 3.14159 * 5
        r = 4 + t * (h // 2 - 4)
        pts.append((cx + r * _cos(ang), cy + r * _sin(ang)))
    cv.polyline(pts, acc, 2)
    cv.circle(cx, cy, 3, ink)
    # Rain bands sweeping in from the right.
    for k, (rx, ry) in enumerate([(x + w - 18, y + 8), (x + w - 12, y + 20),
                                  (x + w - 20, y + 30)]):
        cv.line(rx, ry, rx - 8, ry + 8, SEA_DK, 2)
    # Small island below the eye, as in the Cook Islands story.
    cv.poly([(cx - 8, y + h - 8), (cx + 8, y + h - 8),
             (cx + 4, y + h - 14), (cx - 4, y + h - 14)], SAND_DK)


def pic_megaphone(cv, x, y, w, h, ink, acc):
    mx, my, mw, mh = x + w // 4, y + 8, w // 2, h - 14
    cv.poly([(mx, my + mh // 3), (mx + mw, my),
             (mx + mw, my + mh), (mx, my + mh * 2 // 3)], acc)
    cv.fill_rect(mx - 8, my + mh // 3, 8, mh // 3, ink)
    cv.line(mx + mw + 4, my + 4, mx + mw + 10, my, ink, 2)
    cv.line(mx + mw + 4, my + mh // 2, mx + mw + 10, my + mh // 2, ink, 2)
    cv.line(mx + mw + 4, my + mh - 4, mx + mw + 10, my + mh, ink, 2)


def pic_crowd(cv, x, y, w, h, ink, acc):
    for k, (px, s, c) in enumerate(
            [(x + 12, 1.0, ink), (x + w // 2, 1.15, acc),
             (x + w - 22, 1.0, ink)]):
        cv.circle(px, y + 12, int(6 * s), c)
        cv.poly([(px - 10, y + h - 4), (px + 10, y + h - 4),
                 (px + 7, y + 20), (px - 7, y + 20)], c)


def pic_medcross(cv, x, y, w, h, ink, acc):
    cx, cy = x + w // 2, y + h // 2
    cv.ring(cx, cy, h // 2 - 3, ink, 2)
    cv.fill_rect(cx - 3, cy - 10, 6, 20, acc)
    cv.fill_rect(cx - 10, cy - 3, 20, 6, acc)


def pic_money(cv, x, y, w, h, ink, acc):
    """Banknotes + coins: the economy/market pictogram."""
    for k, (bx, by) in enumerate([(x + 6, y + 14), (x + 16, y + 8)]):
        cv.fill_rect(bx, by, w // 2, h // 2, (52, 120, 62))
        cv.hline(bx, by, w // 2, ink, 1)
        cv.hline(bx, by + h // 2, w // 2, ink, 1)
        cv.vline(bx, by, h // 2, ink, 1)
        cv.vline(bx + w // 2, by, h // 2, ink, 1)
        cv.circle(bx + w // 4, by + h // 4, 5, (226, 238, 222))
        cv.ring(bx + w // 4, by + h // 4, 3, (52, 120, 62), 1)
    cv.circle(x + w - 14, y + h - 12, 7, (201, 162, 39))
    cv.ring(x + w - 14, y + h - 12, 4, (139, 105, 20), 1)
    cv.circle(x + w - 26, y + h - 8, 5, (226, 196, 96))
    cv.ring(x + w - 26, y + h - 8, 3, (139, 105, 20), 1)


def pic_mushroom(cv, x, y, w, h, ink, acc):
    """Mushroom cloud (nuclear blast). In the library for war stories
    about nuclear weapons; NOT used on this page -- none of the day's
    war stories is a nuclear detonation, and drawing one would be
    false imagery. War tiles here use the relevant weapon instead."""
    cx = x + w // 2
    cv.poly([(cx - 5, y + h - 4), (cx + 5, y + h - 4),
             (cx + 3, y + h // 2), (cx - 3, y + h // 2)], (120, 120, 115))
    cv.circle(cx - 12, y + 12, 7, acc)
    cv.circle(cx, y + 6, 9, acc)
    cv.circle(cx + 12, y + 12, 7, acc)
    cv.circle(cx - 6, y + 16, 6, (230, 120, 30))
    cv.circle(cx + 6, y + 16, 6, (230, 120, 30))
    cv.circle(cx, y + h - 8, 8, (140, 140, 135))


def pic_rocket(cv, x, y, w, h, ink, acc):
    """Space pictogram: rocket climbing, flame below."""
    cx = x + w // 2
    cv.poly([(cx, y + 4), (cx + 7, y + h // 2), (cx - 7, y + h // 2)], ink)
    cv.circle(cx, y + 14, 3, PAPER)
    cv.poly([(cx - 7, y + h // 2 - 4), (cx - 13, y + h - 10),
             (cx - 7, y + h - 6)], acc)
    cv.poly([(cx + 7, y + h // 2 - 4), (cx + 13, y + h - 10),
             (cx + 7, y + h - 6)], acc)
    cv.poly([(cx - 3, y + h // 2), (cx + 3, y + h // 2),
             (cx + 5, y + h - 4), (cx - 5, y + h - 4)], (230, 120, 30))
    cv.circle(cx - 14, y + 8, 1, ink)
    cv.circle(cx + 16, y + 16, 1, ink)


def pic_chip(cv, x, y, w, h, ink, acc):
    """Technology pictogram: microchip."""
    cx, cy = x + w // 2, y + h // 2
    s = h // 3
    cv.fill_rect(cx - s, cy - s, 2 * s, 2 * s, ink)
    cv.fill_rect(cx - s // 2, cy - s // 2, s, s, acc)
    for k in range(-1, 2):
        cv.hline(cx - s - 6, cy + k * s // 2, 6, ink, 2)
        cv.hline(cx + s, cy + k * s // 2, 6, ink, 2)
        cv.vline(cx + k * s // 2, cy - s - 6, 6, ink, 2)
        cv.vline(cx + k * s // 2, cy + s, 6, ink, 2)


def pic_ball(cv, x, y, w, h, ink, acc):
    """Sport pictogram: football."""
    cx, cy = x + w // 2, y + h // 2
    r = h // 3
    cv.circle(cx, cy, r, PAPER)
    cv.ring(cx, cy, r, ink, 2)
    cv.poly([(cx, cy - 5), (cx + 5, cy - 1), (cx + 3, cy + 5),
             (cx - 3, cy + 5), (cx - 5, cy - 1)], ink)
    for (dx, dy) in [(-8, -8), (8, -8), (-10, 4), (10, 4), (0, 10)]:
        cv.line(cx, cy, cx + dx, cy + dy, ink, 1)


def pic_plane(cv, x, y, w, h, ink, acc):
    """Migration/travel pictogram: passenger plane over a map pin."""
    cv.poly([(x + 6, y + 12), (x + w - 10, y + 20), (x + 6, y + 26)], ink)
    cv.poly([(x + 18, y + 14), (x + 30, y + 2), (x + 32, y + 14)], acc)
    cv.poly([(x + 18, y + 24), (x + 30, y + 36), (x + 32, y + 24)], acc)
    cv.circle(x + w - 12, y + h - 8, 5, acc)
    cv.circle(x + w - 12, y + h - 8, 2, PAPER)


def pic_planedown(cv, x, y, w, h, ink, acc):
    """A transport plane diving, with a smoke trail and a burst: the
    Kemerovo crash, drawn as the event it was, not a calm flight."""
    cx, cy = x + w // 2, y + h // 2 - 4
    # Smoke trail arcing in from the upper left.
    for k, (sx, sy, sr) in enumerate([(x + 6, y + 8, 3), (x + 16, y + 12, 4),
                                      (x + 28, y + 18, 5)]):
        cv.circle(sx, sy, sr, (140, 140, 135))
    # Plane nose-down: fuselage, wings, tail.
    cv.poly([(cx - 22, cy - 6), (cx + 18, cy + 12), (cx + 12, cy + 18),
             (cx - 26, cy + 2)], ink)
    cv.poly([(cx - 4, cy - 2), (cx + 2, cy - 16), (cx + 8, cy - 2)], acc)
    cv.poly([(cx - 4, cy + 8), (cx + 2, cy + 20), (cx + 8, cy + 8)], acc)
    cv.poly([(cx - 26, cy - 2), (cx - 34, cy - 12), (cx - 28, cy + 2)], ink)
    # Impact burst below.
    cv.circle(cx + 22, cy + 20, 5, (230, 120, 30))
    cv.circle(cx + 22, cy + 20, 2, (255, 200, 60))
    cv.circle(cx + 14, cy + 24, 3, (120, 120, 115))


PICTO = {
    "tanker": pic_tanker,
    "flags": pic_flags,
    "globe": pic_globe,
    "ship": pic_ship,
    "chart": pic_chart_down,
    "jet": pic_jet,
    "virus": pic_virus,
    "parliament": pic_parliament,
    "tv": pic_tv,
    "cyclone": pic_cyclone,
    "cyclone2": pic_cyclone2,
    "megaphone": pic_megaphone,
    "crowd": pic_crowd,
    "medcross": pic_medcross,
    "money": pic_money,
    # Category library (used by the category system; a tile takes the
    # pictogram of its story's category, never a generic decoration):
    "mushroom": pic_mushroom,  # war/nuclear (unused here: no such story)
    "rocket": pic_rocket,      # space
    "chip": pic_chip,          # technology
    "ball": pic_ball,          # sport
    "plane": pic_plane,        # migration/travel
    "planedown": pic_planedown,  # disaster: aircraft crash
}


# -------------------------------------------------------- lead illustrations
def draw_bridge(cv, fonts, x, y, w, h):
    """Kerch Bridge, 18 Nov: the main road arch has fallen -- a gap in
    the deck, the span tilted into the strait, smoke and fire at the
    strike point, debris in the water, and the rail span still standing
    behind it. A patrol boat works the water on the right."""
    cv.fill_rect(x, y, w, h, SKY)
    sea_y = y + h * 3 // 5
    cv.fill_rect(x, sea_y, w, h - (sea_y - y), SEA_DK)
    cv.hline(x, sea_y + 8, w, SEA, 2)
    cv.hline(x + w // 6, sea_y + 16, w // 2, SEA, 1)
    cv.hline(x + w // 3, sea_y + 24, w // 3, SEA, 1)
    # Rail span, still standing: a thin deck above the road deck.
    cv.hline(x + 4, sea_y - 16, w - 8, (90, 84, 72), 2)
    for px in range(x + 30, x + w - 20, 44):
        cv.vline(px, sea_y - 16, 10, (90, 84, 72), 1)
    # Towers: portal frames with a fan of stay cables (not a cross).
    for tx in (x + w // 6, x + w * 5 // 6):
        cv.vline(tx - 5, y + 10, sea_y - y - 10, INK, 2)
        cv.vline(tx + 5, y + 10, sea_y - y - 10, INK, 2)
        cv.hline(tx - 5, y + 10, 10, INK, 3)
        for k in range(4):
            cv.line(tx, y + 12, tx - 34 + k * 8, sea_y, INK, 1)
            cv.line(tx, y + 12, tx + 34 - k * 8, sea_y, INK, 1)
    # Road deck: left and right, with a gap in the middle.
    gap0 = x + w // 2 - 26
    gap1 = x + w // 2 + 26
    cv.hline(x + 4, sea_y - 6, gap0 - x - 4, INK, 4)
    cv.hline(gap1, sea_y - 6, x + w - 4 - gap1, INK, 4)
    # Fallen span, tilted into the water.
    cv.poly([(gap0 + 2, sea_y - 4), (gap1 - 6, sea_y - 4),
             (gap1 - 22, sea_y + 16), (gap0 - 8, sea_y + 16)], (90, 84, 72))
    # Debris chunks floating by the fallen span.
    cv.fill_rect(gap0 - 16, sea_y + 10, 10, 3, (70, 64, 54))
    cv.fill_rect(gap1 + 4, sea_y + 14, 12, 3, (70, 64, 54))
    cv.fill_rect(gap0 + 8, sea_y + 22, 8, 3, (90, 84, 72))
    # Smoke plume + fire burst at the strike point.
    cv.circle(x + w // 2 - 10, sea_y - 26, 10, (120, 120, 115))
    cv.circle(x + w // 2 + 8, sea_y - 34, 8, (140, 140, 135))
    cv.circle(x + w // 2 - 2, sea_y - 40, 6, (160, 160, 155))
    cv.circle(x + w // 2, sea_y - 14, 5, (230, 120, 30))
    cv.circle(x + w // 2, sea_y - 14, 2, (255, 200, 60))
    # Patrol boat on the right, under the standing span.
    bx = x + w - 96
    cv.poly([(bx, sea_y + 20), (bx + 44, sea_y + 20),
             (bx + 36, sea_y + 28), (bx + 8, sea_y + 28)], INK)
    cv.fill_rect(bx + 16, sea_y + 12, 12, 8, INK)
    cv.vline(bx + 22, sea_y + 4, 8, INK, 1)
    # Drone dots, upper left.
    cv.circle(x + w // 4, y + 12, 2, INK)
    cv.circle(x + w // 4 + 14, y + 18, 2, INK)
    cv.circle(x + w // 4 + 26, y + 10, 2, INK)
    serif = fonts["serif"]
    draw_text(cv, serif, 9, x + 8, sea_y - 12, "CRIMEA", (70, 70, 66))
    draw_text(cv, serif, 9, x + w - 52, sea_y - 12, "RUSSIA", (70, 70, 66))
    draw_text(cv, serif, 9, x + 8, y + h - 8, "KERCH STRAIT",
              (220, 232, 240))


def draw_gulf(cv, fonts, x, y, w, h):
    """The Gulf on 18 Nov, as a map-scene: Iran along the top, the sea
    running diagonally, Arabia below; Bahrain and Qeshm marked; dotted
    drone tracks arcing in from Iran toward Bahrain and Kuwait; a vessel
    burning in Hormuz; a US carrier with jets in the lower sea."""
    cv.fill_rect(x, y, w, h, SAND)
    # Sea: a diagonal band; Arabia below it.
    cv.poly([(x, y + h * 2 // 5), (x + w, y + h // 5),
             (x + w, y + h * 43 // 50), (x, y + h * 49 // 50)], SEA)
    cv.poly([(x, y + h * 49 // 50), (x + w, y + h * 43 // 50),
             (x + w, y + h), (x, y + h)], SAND_DK)
    cv.poly([(x, y + h * 2 // 5), (x + w // 3, y + h // 2),
             (x + w // 4, y + h * 49 // 50), (x, y + h * 49 // 50)], SEA_DK)
    # Qeshm island, in the sea near the right.
    qx, qy = x + w * 3 // 5, y + h * 3 // 5
    cv.poly([(qx, qy), (qx + w // 5, qy - 8), (qx + w // 4, qy + 2),
             (qx + w // 10, qy + 8)], SAND_DK)
    # Bahrain island, small, in the sea left of centre.
    bx, by = x + w // 4, y + h * 3 // 4
    cv.poly([(bx - 8, by), (bx, by - 6), (bx + 8, by),
             (bx, by + 6)], SAND_DK)
    cv.ring(bx, by, 7, RED, 1)
    # Drone track: dotted arc from Iran down to Bahrain.
    for k in range(9):
        t = k / 8.0
        dx = int(bx + 14 + t * w * 0.28)
        dy = int(by - 6 - t * t * h * 0.5 - t * h * 0.08)
        cv.circle(dx, dy, 2, RED)
    # Second track: Iran toward Kuwait, upper left.
    kx, ky = x + w // 8, y + h // 3
    for k in range(6):
        t = k / 5.0
        dx = int(kx + 26 + t * w * 0.2)
        dy = int(ky - 4 - t * t * h * 0.35)
        cv.circle(dx, dy, 2, ORANGE)
    cv.circle(kx, ky, 3, ORANGE)
    # Interceptor burst over Bahrain.
    cv.circle(bx, by - 14, 4, (230, 120, 30))
    cv.circle(bx, by - 14, 2, (255, 200, 60))
    # Vessel hit in Hormuz, far right in the sea.
    vx, vy = x + w - 92, y + h // 2 + 6
    cv.poly([(vx, vy), (vx + 52, vy), (vx + 44, vy + 8),
             (vx + 8, vy + 8)], INK)
    cv.fill_rect(vx + 12, vy - 8, 8, 8, INK)
    cv.circle(vx + 26, vy - 14, 6, (230, 120, 30))
    cv.circle(vx + 26, vy - 14, 2, (255, 200, 60))
    cv.circle(vx + 16, vy - 20, 5, (120, 120, 115))
    cv.circle(vx + 34, vy - 22, 4, (140, 140, 135))
    # US carrier in the lower sea, with two jets above it.
    cx, cy = x + w // 2 - 34, y + h - 18
    cv.fill_rect(cx - 34, cy, 68, 5, (90, 96, 104))
    cv.fill_rect(cx + 8, cy - 8, 14, 8, (90, 96, 104))
    cv.poly([(cx - 56, cy - 18), (cx - 34, cy - 14), (cx - 56, cy - 10)],
            INK)
    cv.poly([(cx + 30, cy - 22), (cx + 52, cy - 18), (cx + 30, cy - 14)],
            INK)
    serif = fonts["serif"]
    draw_text(cv, serif, 10, x + w // 2 - 12, y + 14, "IRAN", INK)
    draw_text(cv, serif, 9, x + 92, y + 24, "KUWAIT", (70, 70, 66))
    draw_text(cv, serif, 8, bx - 24, by - 18, "BAHRAIN", RED_DK)
    draw_text(cv, serif, 9, qx + w // 5 - 6, qy + 16, "QESHM", INK)
    draw_text(cv, serif, 9, x + w - 62, y + h - 26, "HORMUZ", INK)
    draw_text(cv, serif, 9, x + 8, y + h - 10, "GULF", (30, 70, 110))
    draw_text(cv, serif, 8, x + w - 160, y + h - 8, "SAUDI ARABIA",
              (70, 64, 54))


# ------------------------------------------------------------------ stories
# Verified against reporting of 18 Nov 2026 (research, 18 Nov). Items
# marked with a dagger were first reported on 17 Nov (No. 22: 16 Nov)
# and are worded without an 18 Nov date claim; the footer says so.
LEADS = [
    {"n": 1, "topic": "war", "flag": "iran", "flag2": "bahrain",
     "kicker": "MIDDLE EAST · GULF WAR · STRAIT OF HORMUZ",
     "headline": "Iran hits back at Gulf bases as war widens",
     "deck": "Iran fires drones at US bases in Bahrain and Kuwait; a "
             "vessel is hit in Hormuz — 1 crew missing, 11 hurt. A "
             "third US carrier arrives.",
     "art": "gulf"},
    {"n": 2, "topic": "war", "flag": "ukraine",
     "kicker": "EUROPE · UKRAINE WAR · KERCH STRAIT",
     "headline": "Kerch Bridge partially collapses",
     "deck": "Ukraine's drones and missiles destroy the bridge's main "
             "road arch; the span crumbles into the Kerch Strait. Two "
             "killed; rail still standing.",
     "art": "bridge"},
]

TILES = [
    {"n": 3, "topic": "politics", "picto": "flags", "flag": "china",
     "kicker": "ASIA · POLITICS · SHENZHEN",
     "headline": "Xi hosts Putin before Trump summit",
     "deck": "Xi hosts Putin in Shenzhen; the first Trump–Xi–Putin "
             "trilateral meets Thursday."},
    {"n": 4, "topic": "politics", "picto": "globe", "flag": "china",
     "kicker": "ASIA · ECONOMY · SHENZHEN",
     "headline": "APEC opens in Shenzhen",
     "deck": "33rd APEC leaders' meeting, 18–19 Nov; trade, AI and "
             "supply chains top the agenda."},
    {"n": 5, "topic": "politics", "picto": "ship", "flag": "philippines",
     "kicker": "ASIA · SECURITY · MANILA",
     "headline": "Quad unveils new Manila plan",
     "deck": "Joint maritime surveillance, a first P-8/P-3C exercise "
             "in 2027, US$85m AI Accelerator."},
    {"n": 6, "topic": "health", "picto": "virus", "flag": "drc",
     "kicker": "AFRICA · HEALTH · DR CONGO",
     "headline": "Ebola kills three in four toddlers",
     "deck": "Nearly 3 in 4 under-5s with Ebola die; the outbreak tops "
             "11,000 cases and 5,400 deaths."},
    {"n": 7, "topic": "health", "picto": "medcross", "flag": "usa",
     "kicker": "NORTH AMERICA · HEALTH · WASHINGTON",
     "headline": "US loses measles-free status †",
     "deck": "PAHO: US, Mexico and Bolivia lose measles status; US: "
             "5,412 cases in 2026, 10 deaths."},
    {"n": 8, "topic": "politics", "picto": "megaphone", "flag": "spain",
     "kicker": "EUROPE · LABOUR · MADRID",
     "headline": "Spain stops in general strike",
     "deck": "Nationwide strike disrupts ports and car factories in "
             "the cost-of-living row over pay."},
    {"n": 9, "topic": "health", "picto": "cyclone2", "flag": "cook_islands",
     "kicker": "OCEANIA · CLIMATE · COOK ISLANDS",
     "headline": "Cyclone Xavier bears down on Cook Islands",
     "deck": "Category 5 Xavier nears the Northern Cook Islands, "
             "gusts 315 km/h; shelters open."},
    {"n": 10, "topic": "health", "picto": "cyclone", "flag": "india",
     "kicker": "ASIA · CLIMATE · BAY OF BENGAL",
     "headline": "Cyclone Akvan crawls toward Andhra",
     "deck": "Akvan strengthens over the Bay of Bengal, crawling at "
             "3 km/h; landfall expected ~20 Nov."},
    {"n": 11, "topic": "economy", "picto": "chip", "flag": "usa",
     "kicker": "US · TECH · SANTA CLARA",
     "headline": "Nvidia: Huang will not return as CEO",
     "deck": "Board says it will not reinstate Jensen Huang; Q3 "
             "revenue US$115.8bn (+103%)."},
    {"n": 12, "topic": "politics", "picto": "parliament", "flag": "usa",
     "kicker": "US · POLITICS · ANCHORAGE",
     "headline": "Peltola flips Alaska, Democrats 56–44 †",
     "deck": "AP calls Alaska for Peltola over Sullivan; Democrats "
             "take the Senate 56–44."},
    {"n": 13, "topic": "disaster", "picto": "planedown", "flag": "russia",
     "kicker": "EUROPE · DISASTER · KEMEROVO",
     "headline": "Russian military plane crashes, 19 dead",
     "deck": "An An-12 transport crashes near Kemerovo, Siberia, "
             "killing all 19 on board."},
    {"n": 14, "topic": "economy", "picto": "money", "flag": "germany",
     "kicker": "EUROPE · BANKING · FRANKFURT",
     "headline": "Deutsche Bank leak sinks shares †",
     "deck": "Leak of 15m+ files published Tue; shares fell 5–6%; "
             "Malaysia reviews 1MDB-linked files."},
]

# (number, one line, first-reported-17-Nov?, flag)
ALSO = [
    (15, "NSA's classified network goes down", True, "usa"),
    (16, "Waymo halts highway driverless rides", False, "usa"),
    (17, "US tightens AI-chip rules in SE Asia", False, "usa"),
    (18, "Anthropic prices IPO at $70–78", False, "usa"),
    (19, "UK inflation hits 3.6%, a 12-month high", False, "uk"),
    (20, "Global stocks fall on Gulf fear", False, "un"),
    (21, "EU speeds green-energy permits", False, "eu"),
    (22, "Five EU states plan Rwanda return hub", True, "rwanda"),
    (23, "UK sanctions West Bank settlement firms", False, "uk"),
    (24, "Kahana elected Knesset speaker, 66–52", True, "israel"),
    (25, "Houthis press toward Aden", False, "yemen"),
    (26, "Asif Merchant gets 27 years for Iran plot", True, "usa"),
    (27, "Gaza baby dies of cold as tents flood", True, "palestine"),
    (28, "Prague crowds defend free media", False, "czechia"),
    (29, "Estonia plans Russia border closure", False, "estonia"),
    (30, "Twin quakes shake PNG and Romania", False, "png"),
    (31, "Fiji declares drought disaster", False, "fiji"),
    (32, "COP31 deadlocked on fossil fuels", False, "turkey"),
    (33, "Coral reefs face extinction by 2075", False, "un"),
    (34, "Isolated Awa group emerges from Amazon", False, "brazil"),
    (35, "Dhoni retires from IPL", True, "india"),
    (36, "India–Pakistan share guard of honour", True, "bangladesh"),
    (37, "Zverev reaches ATP Finals semis", False, "italy"),
    (38, "Cricket Australia opens sandpapergate forum", False, "australia"),
    (39, "'Human' is Word of the Year", False, "uk"),
    (40, "US, Korea warn on Java flaw", True, "south_korea"),
]

# Map pins: (story number, latitude, longitude, topic, dx, dy jitter px).
# Jitters separate pins that would otherwise overlap (Shenzhen x2, Manila).
PINS = [
    (1, 45.3, 36.5, "war", -3, -7),
    (2, 26.2, 50.6, "war", -5, -6),
    (3, 22.5, 114.1, "politics", -8, -8),
    (4, 22.5, 114.1, "politics", 10, -6),
    (5, 14.6, 121.0, "politics", -2, 8),
    (6, 1.0, 29.9, "health", 0, 0),
    (7, 38.9, -77.0, "health", 0, 0),
    (8, 40.4, -3.7, "politics", -6, 6),
    (9, -10.4, -161.0, "health", 0, 0),
    (10, 16.0, 82.0, "health", 0, 0),
    (11, 37.35, -121.95, "economy", 0, 0),
    (12, 61.2, -149.9, "politics", 0, 0),
    (13, 55.4, 86.1, "disaster", 0, 0),
    (14, 50.1, 8.7, "economy", 4, -4),
]


def load_map(path):
    with open(path, "rb") as f:
        d = f.read()
    w, h = struct.unpack_from("<HH", d, 0)
    return w, h, d[4:]


def map_is_land(mw, mh, bits, lon, lat):
    px = int((lon + 180.0) / 360.0 * mw)
    py = int((90.0 - lat) / 180.0 * mh)
    px = max(0, min(mw - 1, px))
    py = max(0, min(mh - 1, py))
    i = py * mw + px
    return (bits[i // 8] >> (i % 8)) & 1


# ------------------------------------------------------------------ layout
def draw_masthead(cv, fonts):
    serif = fonts["serif"]
    bold = fonts["serif-bold"]
    cv.fill_rect(16, 16, 992, 102, NAVY)
    cv.fill_rect(16, 118, 992, 2, GOLD)
    draw_text(cv, bold, 13, 28, 40, "THE WORLD IN ONE PAGE", GOLD_LT,
              tracking=3.0)
    draw_text(cv, bold, 13, 996, 40, "40 STORIES · 6 CONTINENTS · ONE DAY",
              GOLD_LT, tracking=2.0, align="right")
    draw_text(cv, bold, 56, 28, 104, "Wednesday 18 November 2026", CREAM)


def draw_lead(cv, fonts, x, y, w, h, lead):
    serif = fonts["serif"]
    bold = fonts["serif-bold"]
    cv.fill_rect(x, y, w, h, (250, 246, 236))
    cv.hline(x, y, w, INK, 1)
    cv.hline(x, y + h - 1, w, INK, 1)
    cv.vline(x, y, h, INK, 1)
    cv.vline(x + w - 1, y, h, INK, 1)
    cv.fill_rect(x, y, w, 3, TOPIC[lead["topic"]])
    illo_h = 104
    if lead["art"] == "bridge":
        draw_bridge(cv, fonts, x + 1, y + 4, w - 2, illo_h)
    else:
        draw_gulf(cv, fonts, x + 1, y + 4, w - 2, illo_h)
    # Country flag(s) in the illustration's top-left corner: the actor
    # first, then the location's flag when it differs (lead 1: Iran +
    # Bahrain).
    draw_flag(cv, lead["flag"], x + 8, y + 10, 34, 22)
    if lead.get("flag2"):
        draw_flag(cv, lead["flag2"], x + 48, y + 10, 34, 22)
    tx = x + 12
    tw = w - 24
    draw_text(cv, bold, 9, tx, y + 126,
              "%d · %s" % (lead["n"], lead["kicker"]), RED, tracking=1.0)
    lines = wrap_text(bold, 23, lead["headline"], tw)
    yy = y + 150
    for ln in lines[:2]:
        draw_text(cv, bold, 23, tx, yy, ln, INK)
        yy += 27
    dlines = wrap_text(serif, 11, lead["deck"], tw)
    yy = y + 192
    for ln in dlines[:2]:
        draw_text(cv, serif, 11, tx, yy, ln, (70, 70, 66))
        yy += 13


def draw_tile(cv, fonts, x, y, w, h, tile):
    serif = fonts["serif"]
    bold = fonts["serif-bold"]
    cv.fill_rect(x, y, w, h, (250, 246, 236))
    cv.hline(x, y, w, GREY_LT, 1)
    cv.hline(x, y + h - 1, w, GREY_LT, 1)
    cv.vline(x, y, h, GREY_LT, 1)
    cv.vline(x + w - 1, y, h, GREY_LT, 1)
    band_h = 56
    cv.fill_rect(x + 1, y + 1, w - 2, band_h, TOPIC_TINT[tile["topic"]])
    # Country flag, top-left of the band; story number, top-right.
    draw_flag(cv, tile["flag"], x + 8, y + 8, 30, 20)
    PICTO[tile["picto"]](cv, x + w // 2 - 46, y + 2, 92, 52,
                         INK, TOPIC[tile["topic"]])
    cx, cy = x + w - 13, y + 13
    cv.circle(cx, cy, 10, RED)
    num = str(tile["n"])
    nw = text_width(bold, 11, num)
    draw_text(cv, bold, 11, cx - nw / 2.0, cy + 4, num, CREAM)
    tx = x + 10
    tw = w - 20
    draw_text(cv, bold, 8, tx, y + 70, tile["kicker"],
              TOPIC[tile["topic"]], tracking=0.5)
    lines = wrap_text(bold, 13, tile["headline"], tw)
    yy = y + 86
    for ln in lines[:2]:
        draw_text(cv, bold, 13, tx, yy, ln, INK)
        yy += 15
    dlines = wrap_text(serif, 9, tile["deck"], tw)
    yy = y + 114
    for ln in dlines[:2]:
        draw_text(cv, serif, 9, tx, yy, ln, (70, 70, 66))
        yy += 11


def draw_map_panel(cv, fonts, x, y, w, h, mapdata):
    serif = fonts["serif"]
    bold = fonts["serif-bold"]
    mw, mh, bits = mapdata
    cv.fill_rect(x, y, w, h, (250, 246, 236))
    cv.hline(x, y, w, INK, 1)
    cv.hline(x, y + h - 1, w, INK, 1)
    cv.vline(x, y, h, INK, 1)
    cv.vline(x + w - 1, y, h, INK, 1)
    draw_text(cv, bold, 11, x + 10, y + 18,
              "WHERE IT HAPPENED · NUMBERS MATCH STORIES", INK, tracking=0.5)
    mx, my, mw2, mh2 = x + 10, y + 26, w - 20, 150
    lat_top, lat_bot = 84.0, -58.0
    # Ocean, then graticule, then land sampled from the mask.
    cv.fill_rect(mx, my, mw2, mh2, (214, 228, 238))
    for lon in range(-180, 181, 30):
        gx = mx + int((lon + 180) / 360.0 * mw2)
        cv.vline(gx, my, mh2, (232, 240, 246), 1)
    for lat in range(-60, 91, 30):
        gy = my + int((lat_top - lat) / (lat_top - lat_bot) * mh2)
        cv.hline(mx, gy, mw2, (232, 240, 246), 1)
    for sy in range(mh2):
        lat = lat_top - (sy + 0.5) / mh2 * (lat_top - lat_bot)
        row = my + sy
        run = None
        for sx in range(mw2):
            lon = -180.0 + (sx + 0.5) / mw2 * 360.0
            land = map_is_land(mw, mh, bits, lon, lat)
            if land and run is None:
                run = sx
            elif not land and run is not None:
                cv.fill_rect(mx + run, row, sx - run, 1, SAND)
                run = None
        if run is not None:
            cv.fill_rect(mx + run, row, mw2 - run, 1, SAND)
    # Numbered pins.
    for (n, lat, lon, topic, dx, dy) in PINS:
        px = mx + int((lon + 180.0) / 360.0 * mw2) + dx
        py = my + int((lat_top - lat) / (lat_top - lat_bot) * mh2) + dy
        cv.circle(px, py, 7, TOPIC[topic])
        cv.ring(px, py, 7, PAPER, 1)
        num = str(n)
        nw = text_width(bold, 8, num)
        draw_text(cv, bold, 8, px - nw / 2.0, py + 3, num, CREAM)
    # Legend, two rows (five topics now that DISASTER joins the set).
    for ly, topics in ((y + h - 42, ("war", "politics", "economy")),
                       (y + h - 26, ("health", "disaster"))):
        lx = x + 10
        for topic in topics:
            cv.circle(lx + 5, ly, 4, TOPIC[topic])
            lx += 12
            twd = draw_text(cv, serif, 9, lx, ly + 3, TOPIC_LABEL[topic],
                            INK)
            lx += int(twd) + 16


def draw_also(cv, fonts, x, y, w, h):
    serif = fonts["serif"]
    bold = fonts["serif-bold"]
    cv.fill_rect(x, y, w, h, (250, 246, 236))
    cv.hline(x, y, w, INK, 1)
    cv.hline(x, y + h - 1, w, INK, 1)
    cv.vline(x, y, h, INK, 1)
    cv.vline(x + w - 1, y, h, INK, 1)
    draw_text(cv, bold, 11, x + 10, y + 18,
              "ALSO ON WEDNESDAY 18 NOVEMBER · 15–40", INK, tracking=0.5)
    col_w = (w - 20 - 8) // 2
    for i, (n, text, old, flag) in enumerate(ALSO):
        col = i // 13
        row = i % 13
        ix = x + 10 + col * (col_w + 8)
        iy = y + 30 + row * 15
        draw_flag(cv, flag, ix, iy - 2, 14, 10)
        num = "%d" % n
        nw = draw_text(cv, bold, 11, ix + 18, iy + 9, num, RED)
        label = text + ("†" if old else "")
        draw_text(cv, serif, 11, ix + 18 + nw + 5, iy + 9, label, INK)


def draw_footer(cv, fonts):
    serif = fonts["serif"]
    text = ("Covering Wednesday 18 November 2026.  † First reported 17 "
            "November 2026 (No. 22: 16 November).  Disputed claims are "
            "attributed.  Sources: AP, Reuters, AFP, BBC, Al Jazeera, "
            "CNN, UN News.  Original drawings.")
    draw_text(cv, serif, 8.5, W // 2, 1006, text, (90, 86, 76),
              align="center")


def check_fits(fonts):
    """Build-time layout check: every headline/deck must fit its allotted
    lines and every ALSO line its column. Prints warnings; never changes
    the image, so determinism is unaffected."""
    serif = fonts["serif"]
    bold = fonts["serif-bold"]
    bad = 0
    for lead in LEADS:
        if len(wrap_text(bold, 23, lead["headline"], 464)) > 2:
            print("CHECK lead %d headline wraps >2 lines" % lead["n"],
                  file=sys.stderr)
            bad += 1
        if len(wrap_text(serif, 11, lead["deck"], 464)) > 2:
            print("CHECK lead %d deck wraps >2 lines" % lead["n"],
                  file=sys.stderr)
            bad += 1
    for tile in TILES:
        if text_width(bold, 8, tile["kicker"], 0.5) > 222:
            print("CHECK tile %d kicker too wide" % tile["n"],
                  file=sys.stderr)
            bad += 1
        if len(wrap_text(bold, 13, tile["headline"], 222)) > 2:
            print("CHECK tile %d headline wraps >2 lines" % tile["n"],
                  file=sys.stderr)
            bad += 1
        if len(wrap_text(serif, 9, tile["deck"], 222)) > 2:
            print("CHECK tile %d deck wraps >2 lines" % tile["n"],
                  file=sys.stderr)
            bad += 1
    col_w = (604 - 20 - 8) // 2
    for (n, text, old, flag) in ALSO:
        label = text + ("†" if old else "")
        num_w = text_width(bold, 11, str(n))
        if 18 + num_w + 5 + text_width(serif, 11, label) > col_w:
            print("CHECK also %d line too wide" % n, file=sys.stderr)
            bad += 1
    if bad == 0:
        print("check: all headlines, decks and ALSO lines fit")


def build():
    here = os.path.dirname(os.path.abspath(__file__))
    fonts = load_fonts(os.path.join(here, "fonts.bin"))
    mapdata = load_map(os.path.join(here, "map.bin"))
    check_fits(fonts)
    cv = Canvas(W, H, PAPER)
    draw_masthead(cv, fonts)
    draw_lead(cv, fonts, 16, 126, 488, 210, LEADS[0])
    draw_lead(cv, fonts, 520, 126, 488, 210, LEADS[1])
    for i, tile in enumerate(TILES):
        col = i % 4
        row = i // 4
        draw_tile(cv, fonts, 16 + col * 250, 344 + row * 136, 242, 128, tile)
    draw_map_panel(cv, fonts, 16, 756, 380, 234, mapdata)
    draw_also(cv, fonts, 404, 756, 604, 234)
    draw_footer(cv, fonts)
    return cv


def main():
    cv = build()
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output"
    path = None
    try:
        os.makedirs(out_dir, exist_ok=True)
        cand = os.path.join(out_dir, "entry.png")
        size = write_png(cv, cand)
        path = cand
    except OSError:
        here = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(here, "entry.png")
        size = write_png(cv, path)
    print("wrote %s (%d bytes, %dx%d)" % (path, size, W, H))


if __name__ == "__main__":
    main()
