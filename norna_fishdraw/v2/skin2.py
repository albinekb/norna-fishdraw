"""Skins for v2 fish: v1's pixel-art textures (64x32 body, 32x16 fin) carried over, plus more pattern families.

v1 kinds (plain, bars, blotch, spots, stars, ghost) come straight from `skin.py`. The new families paint over a plain
v1 body: stripes (lateral bands), rosettes (rings of accent round a darker eye), eyespots (a few large ocelli),
mottle (fine two-tone grain), gradient (strong counter-shading and a head-to-tail fade). The body UV is the v1 one:
u nose to tail along the spine station, v back (0) to belly (1), the same on both flanks, so the texture and the scale
grid land on the v2 lattice as they did on v1's loft.
"""

from __future__ import annotations

import math

from ..fishdraw_port import Rng
from ..skin import BH, BW, Skin, body_texture, fin_texture, png_bytes


V1_KINDS = {"plain", "bars", "blotch", "spots", "stars", "ghost"}
NEW_KINDS = ("stripes", "rosettes", "eyespot", "mottle", "gradient")


def skin_of(g: dict, kind: str | None = None) -> Skin:
    s = g["skin"]
    k = kind or s["kind"]
    return Skin(
        kind=k if k in V1_KINDS else "plain",
        seed=s["seed"],
        bars=s.get("bars", 6),
        density=s.get("density", 1.0),
        lateral=bool(s.get("lateral", True)),
        scales=s.get("scales", 1.0),
        aspect=max(0.05, g["body"].get("height", 0.2)),
        tint=tuple(s.get("tint", (0.0, 0.0, 0.0))),
    )


def _rgb(h):
    h = h.lstrip("#")
    return [int(h[i : i + 2], 16) for i in (0, 2, 4)]


def _mix(a, b, t):
    return [round(a[i] * (1 - t) + b[i] * t) for i in range(3)]


def _put(img, x, y, col, a):
    if 0 <= y < BH and 0 <= x < BW:
        p = img[y][x]
        img[y][x] = [*_mix(p[:3], col, a), 255]


def body_pixels(g: dict, palette: dict, kind: str | None = None):
    """-> BH rows of BW [r, g, b, a] ints for the genome's skin."""
    k = kind or g["skin"]["kind"]
    img = [row[:] for row in body_texture(skin_of(g, k), palette)]
    if k in V1_KINDS:
        return img
    rng = Rng(g["skin"]["seed"] ^ 0x2B2B or 1)
    acc, flank, back = _rgb(palette["accent"]), _rgb(palette["flank"]), _rgb(palette["back"])
    dens = g["skin"].get("density", 1.0)
    if k == "stripes":
        n = max(3, g["skin"].get("bars", 5) // 1)
        for i in range(n):
            v = 0.16 + 0.62 * (i + 0.5) / n + rng.rand() * 0.02
            y0 = int(v * BH)
            for x in range(int(0.2 * BW), BW - 1):
                wob = round(math.sin(x * 0.35 + i * 1.7) * 0.6)
                for dy in (0, 1):
                    _put(img, x, y0 + int(wob) + dy, acc, 0.85)
    elif k == "rosettes":
        for _ in range(int(9 * dens)):
            cx, cy = 12 + int(rng.rand() * (BW - 16)), 6 + int(rng.rand() * (BH - 14))
            for a in range(10):
                ang = a / 10 * 2 * math.pi
                _put(img, cx + round(math.cos(ang) * 2.4), cy + round(math.sin(ang) * 2.0), acc, 0.9)
            _put(img, cx, cy, [c * 0.55 for c in flank], 0.8)
    elif k == "eyespot":
        for _ in range(1 + int(dens > 1.0)):
            cx, cy = BW - 14 - int(rng.rand() * 14), 8 + int(rng.rand() * (BH - 18))
            for y in range(-4, 5):
                for x in range(-4, 5):
                    d = math.hypot(x, y)
                    if d < 4.2:
                        _put(img, cx + x, cy + y, [20, 20, 28] if d > 2.8 else acc if d > 1.4 else [250, 250, 240], 0.95)
    elif k == "mottle":
        for _ in range(int(150 * dens)):
            x, y = int(rng.rand() * BW), int(rng.rand() * BH)
            shade = [c * (0.62 if rng.rand() < 0.6 else 1.25) for c in flank]
            _put(img, x, y, [max(0, min(255, round(c))) for c in shade], 0.55)
            _put(img, x + 1, y, [max(0, min(255, round(c))) for c in shade], 0.4)
    elif k == "gradient":
        for y in range(BH):
            t = y / (BH - 1)
            for x in range(BW):
                u = x / (BW - 1)
                col = _mix(back, acc, 0.35 * u)
                a = max(0.0, 0.45 - t * 0.9) + 0.12 * u
                _put(img, x, y, col, a)
    return img


def fin_pixels(g: dict, palette: dict):
    return fin_texture(skin_of(g), palette)


def glow_mask(g: dict, palette: dict):
    """Emissive texture rows: the glow colour where a star-pattern body differs from the plain one, black elsewhere."""
    a = body_texture(skin_of(g, "stars"), palette)
    b = body_texture(skin_of(g, "plain"), palette)
    glow = _rgb(palette.get("glow", "#66ffe0"))
    out = []
    for ra, rb in zip(a, b):
        out.append([glow + [255] if pa[:3] != pb[:3] else [0, 0, 0, 255] for pa, pb in zip(ra, rb)])
    return out


def png_of(rows) -> bytes:
    return png_bytes(rows)
