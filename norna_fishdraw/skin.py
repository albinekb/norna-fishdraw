"""Pixel-art skins: a 64x32 body texture and a 32x16 fin texture per fish, stdlib only.

Body texture (planar side view): u runs nose -> tail root, v back (0) -> belly (1),
shared by both flanks. It paints the back/flank/belly ramp from the palette, a gill
line, the species pattern (bars, blotches, spots, stars, glow band), a lateral line
and a scale grid (offset rows of 3-px arcs: lighter lower rim, darker left edge)
that fades toward belly, head and tail root. Fin texture: u across the rays, v root
(0) -> free edge (1): membrane ramp, ray lines, pale rim.

Stdlib only (lists, math, zlib). Everything is a pure function of (Skin, palette): the same
inputs give the same pixels. `Skin.seed` drives the port's xorshift `Rng`, so the layout varies per catch.
"""

from __future__ import annotations

import math
import struct
import zlib
from dataclasses import dataclass, replace

from .fishdraw_port import Rng

BW, BH = 64, 32
FW, FH = 32, 16
_BAYER = ((0 / 4 - 0.375, 2 / 4 - 0.375), (3 / 4 - 0.375, 1 / 4 - 0.375))


@dataclass(frozen=True)
class Skin:
    kind: str = "plain"  # plain | bars | blotch | spots | stars | ghost
    seed: int = 1
    bars: int = 6
    density: float = 1.0  # spots / stars per unit, blotch coverage scale
    lateral: bool = True
    scales: float = 1.0  # 0 = smooth skin
    aspect: float = 0.3  # body depth / length: sets the scale cell height
    tint: tuple = (0.0, 0.0, 0.0)  # per-catch additive tint, in 0..1 units

    def varied(self, seed: int, rnd) -> "Skin":
        """Per-catch variation inside the species range; `rnd()` is a 0..1 stream."""
        return replace(
            self,
            seed=seed,
            bars=max(3, self.bars + int(rnd() * 3) - 1) if self.kind == "bars" else self.bars,
            density=self.density * (0.7 + 0.6 * rnd()),
            tint=tuple((rnd() - 0.5) * 0.12 for _ in range(3)),
        )


class _R:
    def __init__(self, seed):
        self.r = Rng(seed or 1)

    def uniform(self, a, b):
        return a + (b - a) * self.r.rand()

    def integers(self, a, b):  # [a, b)
        return a + int(self.r.rand() * (b - a))

    def choice(self, opts):
        return opts[int(self.r.rand() * len(opts)) % len(opts)]


def _rgb(h):
    h = h.lstrip("#")
    return [int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4)]


def _mix(a, b, t):
    return [a[i] * (1 - t) + b[i] * t for i in range(3)]


def _clip(x, lo=0.0, hi=1.0):
    return lo if x < lo else hi if x > hi else x


def _grid(h, w, f):
    return [[f(x, y) for x in range(w)] for y in range(h)]


def _finish(img, tint):
    return [[[round(_clip(c + tint[i]) * 255) for i, c in enumerate(px)] + [255] for px in row] for row in img]


def body_texture(skin: Skin, pal: dict):
    """-> BH rows of BW [r, g, b, a] ints."""
    rng = _R(skin.seed)
    H, W = BH, BW
    back, flank, belly = _rgb(pal["back"]), _rgb(pal["flank"]), _rgb(pal["belly"])
    accent = _rgb(pal["accent"])
    dark = [c * 0.8 for c in back]

    def ramp(x, y):
        t = (y + 0.5) / H
        up, dn = _clip(t / 0.3), _clip((t - 0.55) / 0.3)
        top = _mix(back, flank, up)
        c = _mix(top, belly, dn)
        d = _BAYER[y % 2][x % 2] * 0.035
        return [round((v + d) * 7.0) / 7.0 for v in c]

    img = _grid(H, W, ramp)
    uu = lambda x: (x + 0.5) / W  # noqa: E731
    vv = lambda y: (y + 0.5) / H  # noqa: E731

    def blend(x, y, col, a=1.0):
        p = img[y][x]
        img[y][x] = [p[i] * (1 - a) + col[i] * a for i in range(3)]

    def in_flank(x, y):
        return 0.1 < vv(y) < 0.88 and 0.14 < uu(x) < 0.97

    k = skin.kind
    if k == "bars":
        n = skin.bars
        for i in range(n):
            cu = 0.24 + 0.7 * (i + 0.5) / n + rng.uniform(-0.015, 0.015)
            top, bot = rng.uniform(0.08, 0.2), rng.uniform(0.7, 0.86)
            wid = rng.choice([1.5, 2.0, 2.5]) / W
            ph = rng.uniform(0, 6)
            for y in range(H):
                wob = round(math.sin(vv(y) * 9 + ph) * 0.012, 4)
                if not top < vv(y) < bot:
                    continue
                for x in range(W):
                    if abs(uu(x) - cu - wob) < wid and uu(x) > 0.18:
                        blend(x, y, accent, 0.9)
    elif k in ("blotch", "ghost"):
        g = [[rng.uniform(0, 1) for _ in range(9)] for _ in range(5)]
        big = _grid(H, W, lambda x, y: g[min(y // 8, 4)][min(x // 8, 8)])
        sm = _grid(H, W, lambda x, y: sum(big[min(max(y + dy, 0), H - 1)][min(max(x + dx, 0), W - 1)] for dy in (-1, 0, 1) for dx in (-1, 0, 1)) / 9.0)
        if k == "blotch":
            cov = _clip(0.3 * skin.density, 0.08, 0.5)
            vals = sorted(v for r in sm for v in r)
            thr = vals[min(len(vals) - 1, int((1 - cov) * len(vals)))]
            for y in range(H):
                for x in range(W):
                    if sm[y][x] > thr and in_flank(x, y):
                        blend(x, y, accent, 0.75)
        else:
            ph = rng.uniform(0, 6)
            glow = [_clip(c * 0.5 + 0.5) for c in accent]
            for y in range(H):
                for x in range(W):
                    band = round(math.exp(-(((vv(y) - 0.45) / 0.14) ** 2)) * (0.65 + 0.35 * math.sin(uu(x) * 17 + ph)), 3)
                    p = img[y][x]
                    img[y][x] = [round((p[i] + band * (glow[i] - p[i]) * 0.85) * 9.0) / 9.0 for i in range(3)]
    elif k in ("spots", "stars"):
        n = int(26 * skin.density) if k == "spots" else int(34 * skin.density)
        for _ in range(n):
            x, y = rng.integers(10, W - 2), rng.integers(4, H - 6)
            if k == "spots":
                for dy in (0, 1):
                    for dx in (0, 1):
                        blend(x + dx, y + dy, accent, 0.9)
            else:
                img[y][x] = list(accent)
        if k == "stars":
            for _ in range(max(2, int(4 * skin.density))):
                x, y = rng.integers(14, W - 4), rng.integers(6, H - 8)
                for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
                    img[y + dy][x + dx] = list(accent)
    if skin.lateral:
        row = int(0.46 * H)
        for x in range(int(0.2 * W), int(0.93 * W)):
            if x % 2 == 0:
                img[row][x] = [c * 0.72 for c in img[row][x]]
    gx = int(0.19 * W)
    for y in range(6, 25):
        blend(gx, y, dark, 0.55)
    if skin.scales > 0:
        cw = 3
        ch = int(_clip(round(cw * 0.5 / max(skin.aspect, 0.05)), 2, 4))
        for y in range(H):
            ri, yy = y // ch, y % ch
            for x in range(W):
                xx = (x + (cw // 2) * (ri % 2)) % cw
                fade = _clip(1 - abs(vv(y) - 0.42) / 0.5) * _clip((uu(x) - 0.2) / 0.1) * _clip((0.97 - uu(x)) / 0.08)
                if fade * skin.scales <= 0.3:
                    continue
                p = img[y][x]
                if yy == ch - 1:
                    img[y][x] = [_clip(c * 1.1 + 0.02) for c in p]
                elif xx == 0:
                    img[y][x] = [c * 0.9 for c in p]
    return _finish(img, skin.tint)


def fin_texture(skin: Skin, pal: dict):
    """-> FH rows of FW [r, g, b, a] ints."""
    rng = _R((skin.seed ^ 0x5F1D) or 1)
    H, W = FH, FW
    fin, flank = _rgb(pal["fin"]), _rgb(pal["flank"])

    def px(y, x):
        v = (y + 0.5) / H
        k = _clip(v * 3)
        c = [flank[i] * (1 - k * 0.8) * 0.4 + fin[i] * (0.6 + 0.4 * k) for i in range(3)]
        if v < 0.2:
            c = [t * 0.82 for t in c]
        if y >= H - 2:
            c = [_clip(t * 1.18 + 0.04) for t in c]
        if x % 4 == 1:
            c = [t * 0.78 for t in c]
        return c

    img = _grid(H, W, lambda x, y: px(y, x))
    if skin.kind in ("spots", "stars", "bars"):
        acc = _rgb(pal["accent"])
        for _ in range(5):
            x, y = rng.integers(0, W), rng.integers(3, H - 3)
            img[y][x] = [acc[i] * 0.8 + img[y][x][i] * 0.2 for i in range(3)]
    return _finish(img, [t * 0.5 for t in skin.tint])


def png_bytes(rows) -> bytes:
    """Rows of [r, g, b, a] ints -> PNG (filter 0, one IDAT, zlib level 9)."""
    h, w = len(rows), len(rows[0])
    raw = b"".join(b"\0" + bytes(c for px in row for c in px) for row in rows)

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")


def png_decode(data: bytes):
    """Inverse of png_bytes (filter 0 only): rows of [r, g, b, a], for tests."""
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    w, h = struct.unpack(">II", data[16:24])
    i, idat = 8, b""
    while i < len(data):
        n = struct.unpack(">I", data[i : i + 4])[0]
        if data[i + 4 : i + 8] == b"IDAT":
            idat += data[i + 8 : i + 8 + n]
        i += 12 + n
    raw = zlib.decompress(idat)
    stride = w * 4 + 1
    return [[list(raw[y * stride + 1 + x * 4 : y * stride + 5 + x * 4]) for x in range(w)] for y in range(h)]
