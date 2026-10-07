"""Python port of the generator logic of fishdraw (parameters, outlines, fins, head, eye).

Original: fishdraw.js, https://github.com/LingDong-/fishdraw
Copyright (c) 2021 Lingdong Huang. MIT License, full text in LICENSE.fishdraw
next to this file. This is a derivative work and keeps that notice.

PORTED (same maths, same constants, same order of draws):
  * the xorshift PRNG `rand`, `str_to_seed` (seed string -> state), the p5-style
    Perlin `noise`, `choice`, `rndtri`, `default_params`, `generate_params`
    (bit-identical to the JS for any seed string: see test_fishdraw.py goldens);
  * the body outline curves (`body_curve_type` 0 and 1, 32 samples each side);
  * the fin generators `fin_a` and `fin_b` (root curve, free edge, rays) for the
    dorsal, pectoral ("wing"), pelvic, anal and tail fins, the four dorsal /
    pelvic / anal / tail / wing type variants, the finlet types, `resample`;
  * the head outline (`fish_head`: three noisy curves from nose to the body
    seam), the eye placement and size clamp, the jaw/mouth hinge points;
  * the pattern predicates (dots, dorsal marbling, stripes, speckle) as
    functions of drawing-space (x, y), used here to colour 3D faces.

REPLACED / NOT PORTED (they only exist to draw hatching on a plotter):
  * hatch shading, vein, squama (scale) line meshes, the polygon boolean
    clipper, SVG / PostScript output, Hershey text, binomen;
  * `fish_body_a..d` and `fish_lip`/`fish_teeth`/`fish_jaw`/`barbel` line art:
    scale_type / lips / teeth are left in the parameter set and unused in 3D,
    and their `rand()` draws are therefore NOT replayed. Consequence: the
    params, body curves and head curves match the JS exactly; fin ray jitter
    and the dorsal/wing/... `deviate()` draws continue from this port's own
    stream, so fins are deterministic and in the JS's family but not identical
    to a JS run.
  * the JS keeps `perlin` in a global that survives between fishes; here every
    fish builds its own table from its own stream (a fish never depends on
    which fish was drawn before it).

PRNG: xorshift32 (13, 17, 5 variant of the JS) with int32 wraparound emulated
exactly. State is a signed int32 like JS `jsr`. Same seed string, same fish,
on any machine; nothing here touches `random`, time or `hash()`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

PI = math.pi


def _i32(v: int) -> int:
    v &= 0xFFFFFFFF
    return v - 0x100000000 if v & 0x80000000 else v


def str_to_seed(s: str) -> int:
    n = 1
    for i, ch in enumerate(s):
        x = ord(ch) + 1
        n = _i32(n ^ _i32(x << (7 + (i % 5))))
        n = _i32(n ^ _i32(n << 17))
        n = _i32(n ^ (n >> 13))
        n = _i32(n ^ _i32(n << 5))
        n = (n & 0xFFFFFFFF) % 4294967295
    return n


class Rng:
    """The JS `rand()` (xorshift with signed int32 state), one instance per fish."""

    def __init__(self, seed: int):
        self.s = _i32(seed)

    def rand(self) -> float:
        s = self.s
        s = _i32(s ^ _i32(s << 17))
        s = _i32(s ^ (s >> 13))
        s = _i32(s ^ _i32(s << 5))
        self.s = s
        return (s & 0xFFFFFFFF) / 4294967295

    def deviate(self, n: float) -> float:
        return self.rand() * 2 * n - n

    def choice(self, opts, percs=None):
        if not percs:
            percs = [1] * len(opts)
        total = sum(percs)
        r = self.rand() * total
        s = 0
        for o, p in zip(opts, percs):
            s += p
            if r <= s:
                return o
        return None  # JS falls off the end the same way

    def rndtri(self, a: float, b: float, c: float) -> float:
        s0 = (b - a) / 2
        s1 = (c - b) / 2
        s = s0 + s1
        r = self.rand() * s
        if r < s0:
            return a + math.sqrt(2 * r * (b - a))
        return c - math.sqrt(2 * (s - r) * (c - b))


# ---------------------------------------------------------------- noise

_PYB, _PY, _PZB, _PZ, _PSIZE = 4, 16, 8, 256, 4095


class Noise:
    """p5.js noise(): 4 octaves, table of 4096 draws from the fish's own Rng, built on first use."""

    def __init__(self, rng: Rng):
        self.rng = rng
        self.table = None

    @staticmethod
    def _cos(i: float) -> float:
        return 0.5 * (1.0 - math.cos(i * PI))

    def __call__(self, x: float, y: float = 0.0, z: float = 0.0) -> float:
        if self.table is None:
            self.table = [self.rng.rand() for _ in range(_PSIZE + 1)]
        p = self.table
        x, y, z = abs(x), abs(y), abs(z)
        xi, yi, zi = int(math.floor(x)), int(math.floor(y)), int(math.floor(z))
        xf, yf, zf = x - xi, y - yi, z - zi
        r = 0.0
        ampl = 0.5
        for _ in range(4):
            of = xi + (yi << _PYB) + (zi << _PZB)
            rxf, ryf = self._cos(xf), self._cos(yf)
            n1 = p[of & _PSIZE]
            n1 += rxf * (p[(of + 1) & _PSIZE] - n1)
            n2 = p[(of + _PY) & _PSIZE]
            n2 += rxf * (p[(of + _PY + 1) & _PSIZE] - n2)
            n1 += ryf * (n2 - n1)
            of += _PZ
            n2 = p[of & _PSIZE]
            n2 += rxf * (p[(of + 1) & _PSIZE] - n2)
            n3 = p[(of + _PY) & _PSIZE]
            n3 += rxf * (p[(of + _PY + 1) & _PSIZE] - n3)
            n2 += ryf * (n3 - n2)
            n1 += self._cos(zf) * (n2 - n1)
            r += n1 * ampl
            ampl *= 0.5
            xi <<= 1
            xf *= 2
            yi <<= 1
            yf *= 2
            zi <<= 1
            zf *= 2
            if xf >= 1.0:
                xi += 1
                xf -= 1
            if yf >= 1.0:
                yi += 1
                yf -= 1
            if zf >= 1.0:
                zi += 1
                zf -= 1
        return r


# ---------------------------------------------------------------- params


def default_params() -> dict:
    return dict(
        body_curve_type=0, body_curve_amount=0.85, body_length=350, body_height=90,
        scale_type=1, scale_scale=1, pattern_type=3, pattern_scale=1,
        dorsal_texture_type=1, dorsal_type=0, dorsal_length=100, dorsal_start=8, dorsal_end=27,
        wing_texture_type=0, wing_type=0, wing_start=6, wing_end=6, wing_y=0.7,
        wing_length=130, wing_width=10,
        pelvic_start=9, pelvic_end=14, pelvic_length=85, pelvic_type=0, pelvic_texture_type=0,
        anal_start=19, anal_end=29, anal_length=50, anal_type=0, anal_texture_type=0,
        tail_type=0, tail_length=75, finlet_type=0, neck_type=0, nose_height=0,
        mouth_size=8, head_length=30, head_texture_amount=60,
        has_moustache=1, moustache_length=10, has_beard=0, has_teeth=1,
        teeth_length=8, teeth_space=3.5, beard_length=30,
        eye_type=1, eye_size=10, jaw_size=1, jaw_open=1,
    )  # fmt: skip


def generate_params(rng: Rng) -> dict:
    a = default_params()
    r, ch, tri = rng, rng.choice, rng.rndtri
    a["body_curve_type"] = ch([0, 1])
    a["body_curve_amount"] = tri(0.5, 0.85, 0.98)
    a["body_length"] = tri(200, 350, 420)
    a["body_height"] = tri(45, 90, 150)
    a["scale_type"] = ch([0, 1, 2, 3])
    a["scale_scale"] = tri(0.8, 1, 1.5)
    a["pattern_type"] = ch([0, 1, 2, 3, 4])
    a["pattern_scale"] = tri(0.5, 1, 2)
    a["dorsal_texture_type"] = ch([0, 1])
    a["dorsal_type"] = ch([0, 1])
    a["dorsal_length"] = tri(30, 90, 180)
    if a["dorsal_type"] == 0:
        a["dorsal_start"] = int(tri(7, 8, 15))
        a["dorsal_end"] = int(tri(20, 27, 28))
    else:
        a["dorsal_start"] = int(tri(11, 12, 16))
        a["dorsal_end"] = int(tri(19, 21, 24))
    a["wing_texture_type"] = ch([0, 1])
    a["wing_type"] = ch([0, 1])
    a["wing_length"] = tri(40, 130, 200) if a["wing_type"] == 0 else tri(40, 150, 350)
    if a["wing_texture_type"] == 0:
        a["wing_width"] = tri(7, 10, 20)
        a["wing_y"] = tri(0.45, 0.7, 0.85)
    else:
        a["wing_width"] = tri(20, 30, 50)
        a["wing_y"] = tri(0.45, 0.65, 0.75)
    a["wing_start"] = int(tri(5, 6, 8))
    a["wing_end"] = int(tri(5, 6, 8))
    a["pelvic_texture_type"] = ch([0, 1]) if a["dorsal_texture_type"] else 0
    a["pelvic_type"] = ch([0, 1])
    a["pelvic_length"] = tri(30, 85, 140)
    if a["pelvic_type"] == 0:
        a["pelvic_start"] = int(tri(7, 9, 11))
        a["pelvic_end"] = int(tri(13, 14, 15))
    else:
        a["pelvic_start"] = int(tri(7, 9, 12))
        a["pelvic_end"] = a["pelvic_start"] + 2
    a["anal_texture_type"] = ch([0, 1]) if a["dorsal_texture_type"] else 0
    a["anal_type"] = ch([0, 1])
    a["anal_length"] = tri(20, 50, 80)
    a["anal_start"] = int(tri(16, 19, 23))
    a["anal_end"] = int(tri(25, 29, 31))
    a["tail_type"] = ch([0, 1, 2, 3, 4, 5])
    a["tail_length"] = tri(50, 75, 180)
    a["finlet_type"] = ch([0, 1, 2, 3])
    a["neck_type"] = ch([0, 1])
    a["nose_height"] = tri(-50, 0, 35)
    a["head_length"] = tri(20, 30, 35)
    a["mouth_size"] = int(tri(6, 8, 11))
    a["head_texture_amount"] = int(tri(30, 60, 160))
    a["has_moustache"] = ch([0, 0, 0, 1])
    a["has_beard"] = ch([0, 0, 0, 0, 0, 1])
    a["moustache_length"] = int(tri(10, 20, 40))
    a["beard_length"] = int(tri(20, 30, 50))
    a["eye_type"] = ch([0, 1])
    a["eye_size"] = tri(8, 10, 28)
    a["jaw_size"] = tri(0.7, 1, 1.4)
    a["has_teeth"] = ch([0, 1, 1])
    a["teeth_length"] = tri(5, 8, 15)
    a["teeth_space"] = tri(3, 3.5, 6)
    del r
    return a


# ---------------------------------------------------------------- geometry helpers


def lerp(a, b, t):
    return a * (1 - t) + b * t


def lerp2d(p, q, t):
    return [p[0] * (1 - t) + q[0] * t, p[1] * (1 - t) + q[1] * t]


def dist(p, q):
    return math.hypot(q[0] - p[0], q[1] - p[1])


def bean(x: float) -> float:
    return (0.25 - (x - 0.5) ** 2) ** 0.5 * (2.6 + 2.4 * x**1.5) * 0.542


def _spow(a: float, b: float) -> float:
    return math.copysign(1.0, a) * abs(a) ** b if a else 0.0


def _isect_circ_line(cx, cy, r, x0, y0, x1, y1):
    dx, dy = x1 - x0, y1 - y0
    fx, fy = x0 - cx, y0 - cy
    a = dx * dx + dy * dy
    b = 2 * (fx * dx + fy * dy)
    c = fx * fx + fy * fy - r * r
    disc = b * b - 4 * a * c
    if disc < 0 or a == 0:
        return None
    disc = math.sqrt(disc)
    t0 = (-b - disc) / (2 * a)
    if 0 <= t0 <= 1:
        return t0
    t = (-b + disc) / (2 * a)
    if t > 1 or t < 0:
        return None
    return t


def resample(polyline, step):
    """JS `resample`: points `step` apart along a polyline, ends kept."""
    if len(polyline) < 2:
        return [list(p) for p in polyline]
    poly = [list(p) for p in polyline]
    out = [list(poly[0])]
    i = 0
    while i < len(poly) - 1:
        a, b = poly[i], poly[i + 1]
        dx, dy = b[0] - a[0], b[1] - a[1]
        d = math.sqrt(dx * dx + dy * dy)
        if d == 0:
            i += 1
            continue
        n = int(d / step)
        rest = (n * step) / d
        rpx = a[0] * (1 - rest) + b[0] * rest
        rpy = a[1] * (1 - rest) + b[1] * rest
        for j in range(1, n + 1):
            t = j / n
            out.append([a[0] * (1 - t) + rpx * t, a[1] * (1 - t) + rpy * t])
        nxt = None
        for j in range(i + 2, len(poly)):
            bb, cc = poly[j - 1], poly[j]
            if bb[0] == cc[0] and bb[1] == cc[1]:
                continue
            t = _isect_circ_line(rpx, rpy, step, bb[0], bb[1], cc[0], cc[1])
            if t is None:
                continue
            q = [bb[0] * (1 - t) + cc[0] * t, bb[1] * (1 - t) + cc[1] * t]
            out.append(q)
            poly[j - 1] = q
            nxt = j - 1
            break
        if nxt is None:
            break
        i = nxt
    if len(out) > 1:
        lx, ly = out[-1]
        mx, my = poly[-1]
        if math.sqrt((mx - lx) ** 2 + (my - ly) ** 2) < step * 0.5:
            out.pop()
    out.append(list(poly[-1]))
    return out


def arc_resample(poly, m):
    """`m` points evenly spaced by arc length, ends kept (used by the 3D lift)."""
    if len(poly) < 2:
        return [list(poly[0])] * m if poly else []
    cum = [0.0]
    for p, q in zip(poly, poly[1:]):
        cum.append(cum[-1] + dist(p, q))
    total = cum[-1] or 1e-9
    out = []
    j = 0
    for k in range(m):
        d = total * k / (m - 1)
        while j < len(poly) - 2 and cum[j + 1] < d:
            j += 1
        seg = (cum[j + 1] - cum[j]) or 1e-9
        out.append(lerp2d(poly[j], poly[j + 1], min(1.0, max(0.0, (d - cum[j]) / seg))))
    return out


def pt_seg_dist(p, p0, p1):
    x, y = p
    x1, y1 = p0
    x2, y2 = p1
    c, d = x2 - x1, y2 - y1
    len_sq = c * c + d * d
    param = ((x - x1) * c + (y - y1) * d) / len_sq if len_sq else -1
    if param < 0:
        xx, yy = x1, y1
    elif param > 1:
        xx, yy = x2, y2
    else:
        xx, yy = x1 + param * c, y1 + param * d
    return math.hypot(x - xx, y - yy)


# ---------------------------------------------------------------- patterns


def _poissondisk(rng: Rng, W, H, r, samples):
    w = r / 1.4142135624
    r2 = r * r
    cols, rows = int(W / w), int(H / w)
    grid = [-1] * (cols * rows)
    pos = [W / 2.0, H / 2.0]
    samples.append(pos)
    active = []
    for i, s in enumerate(samples):
        grid[int(s[0] / w) + int(s[1] / w) * cols] = i
        active.append(s)
    while active:
        ridx = int(rng.rand() * len(active))
        pos = active[ridx]
        found = 0
        for _ in range(30):
            sr = r + rng.rand() * r
            sa = 6.2831853072 * rng.rand()
            sx, sy = pos[0] + sr * math.cos(sa), pos[1] + sr * math.sin(sa)
            col, row = int(sx / w), int(sy / w)
            if 0 < col < cols - 1 and 0 < row < rows - 1 and grid[col + row * cols] == -1:
                ok = True
                for i in (-1, 0, 1):
                    for j in (-1, 0, 1):
                        nbr = grid[(row + i) * cols + col + j]
                        if nbr != -1:
                            ddx, ddy = sx - samples[nbr][0], sy - samples[nbr][1]
                            if ddx * ddx + ddy * ddy < r2:
                                ok = False
                if ok:
                    found = 1
                    grid[row * cols + col] = len(samples)
                    samples.append([sx, sy])
                    active.append([sx, sy])
        if not found:
            active.pop(ridx)
    return samples


def pattern_func(a: dict, rng: Rng, noise: Noise):
    """The JS pattern predicates as f(x, y) -> bool in drawing space; None for no pattern."""
    t = a["pattern_type"]
    if t == 1:
        scale = a["pattern_scale"]
        samples = _poissondisk(rng, 500, 300, 20 * scale, [])
        rs = [(rng.rand() * 5 + 10) * scale for _ in samples]

        def dots(x, y):
            for (sx, sy), r in zip(samples, rs):
                if math.hypot(x - sx, y - sy) < r:
                    dx, dy = x - sx, y - sy
                    g = math.exp(-0.5 * (dx / r * 2) ** 2) * math.exp(-0.5 * (dy / r * 2) ** 2)
                    if g * noise(x, y, 999) > 0.2:
                        return True
            return False

        return dots
    if t == 2:
        return lambda x, y: noise(x * 0.1, y * 0.1) * max(0.35, (y - 10) / 280) < 0.2
    if t == 3:
        def stripes(x, y):
            dx = noise(x * 0.01, y * 0.01) * 30
            return int((x + dx) / (30 * a["pattern_scale"])) % 2 == 1

        return stripes
    if t == 4:
        # the JS scatters small dots with rand(); here a noise threshold (no stream use)
        return lambda x, y: noise(x * 0.35, y * 0.35, 5) > 0.66
    return None


# ---------------------------------------------------------------- fins


@dataclass
class Fin:
    """One fin in drawing space: `root` on the body, `tip` the free edge (same direction), `rays` the ray lines."""

    kind: str
    root: list
    tip: list
    rays: list = field(default_factory=list)
    outline: list = field(default_factory=list)


def _angles(curve):
    angs = []
    n = len(curve)
    for i in range(n):
        if i == 0:
            angs.append(math.atan2(curve[1][1] - curve[0][1], curve[1][0] - curve[0][0]) - PI / 2)
        elif i == n - 1:
            angs.append(math.atan2(curve[i][1] - curve[i - 1][1], curve[i][0] - curve[i - 1][0]) - PI / 2)
        else:
            a0 = math.atan2(curve[i - 1][1] - curve[i][1], curve[i - 1][0] - curve[i][0])
            a1 = math.atan2(curve[i + 1][1] - curve[i][1], curve[i + 1][0] - curve[i][0])
            while a1 > a0:
                a1 -= PI * 2
            a1 += PI * 2
            angs.append((a0 + a1) / 2)
    return angs


def fin_a(rng, noise, kind, curve, ang0, ang1, func, clip_root=False, curv0=0.0, curv1=0.0, softness=10.0) -> Fin:
    """JS fin_a: a ruffled membrane; one ray per root sample, free edge = the ray tips."""
    angs = _angles(curve)
    n = len(curve)
    out0, out1 = [], []
    out2 = out3 = []
    for i in range(n):
        t = i / (n - 1)
        a = angs[i] + lerp(ang0, ang1, t)
        w = func(t)
        x0, y0 = curve[i]
        p = resample([[x0, y0], [x0 + math.cos(a) * w, y0 + math.sin(a) * w]], 3)
        for j in range(len(p)):
            s = j / (len(p) - 1)
            ss = math.sqrt(s)
            x, y = p[j]
            cv = lerp(curv0, curv1, t) * math.sin(s * PI)
            p[j][0] += noise(x * 0.1, y * 0.1, 3) * ss * softness + math.cos(a - PI / 2) * cv
            p[j][1] += noise(x * 0.1, y * 0.1, 4) * ss * softness + math.sin(a - PI / 2) * cv
        if i == 0:
            out2 = p
        elif i == n - 1:
            out3 = p[::-1]
        else:
            out0.append(p[-1])
            lo = int(rng.rand() * 4) if clip_root else 0
            hi = max(2, int(len(p) * (rng.rand() * 0.5 + 0.5)))
            q = p[lo:hi]
            if q:
                out1.append(q)
    out0 = resample(out0, 3)
    for pt in out0:
        x, y = pt
        pt[0] += (noise(x * 0.1, y * 0.1) * 6 - 3) * (softness / 10)
        pt[1] += (noise(x * 0.1, y * 0.1) * 6 - 3) * (softness / 10)
    tip = [out2[-1]] + out0 + [out3[0]]
    outline = out2 + out0 + out3 + [list(c) for c in curve[::-1]]
    return Fin(kind, [list(c) for c in curve], tip, out1, outline)


def fin_b(rng, noise, kind, curve, ang0, ang1, func) -> Fin:
    """JS fin_b: spined fin. The ray tips are the free edge; the hatch between spines is not ported."""
    angs = _angles(curve)
    n = len(curve)
    tip = []
    for i in range(n):
        t = i / (n - 1)
        a = angs[i] + lerp(ang0, ang1, t)
        w = func(t)
        tip.append([curve[i][0] + math.cos(a) * w, curve[i][1] + math.sin(a) * w])
    rays = [[list(curve[i]), tip[i]] for i in range(n)]
    return Fin(kind, [list(c) for c in curve], tip, rays, tip + [list(c) for c in curve[::-1]])


def finlet_teeth(curve, h, direction=1):
    """JS finlet: every third root sample throws a spike. Returns [(base_a, tip, base_b)] triangles."""
    angs = _angles(curve)
    tris = []
    for i in range(len(curve)):
        if (i + 1) % 3:
            continue
        t = i / (len(curve) - 1)
        w = h * ((1 - t * 0.5) if direction > 0 else (0.5 + t * 0.5))
        x0, y0 = curve[i]
        tip = [x0 + math.cos(angs[i]) * w, y0 + math.sin(angs[i]) * w]
        a = curve[max(i - 1, 0)]
        b = curve[min(i + 1, len(curve) - 1)]
        tris.append((list(a), tip, list(b)))
    return tris


def fin_adipose(noise, curve, dx, dy, r):
    """JS fin_adipose outline: a rounded bump over the root. Returns the bump polyline (root end to root end)."""
    n = 20
    x0, y0 = curve[len(curve) // 2]
    x, y = x0 + dx, y0 + dy
    x1, y1 = curve[0]
    x2, y2 = curve[-1]
    d1, d2 = dist((x, y), (x1, y1)), dist((x, y), (x2, y2))
    a1 = math.acos(min(1.0, r / d1))
    a2 = math.acos(min(1.0, r / d2))
    a01 = math.atan2(y1 - y, x1 - x) + a1
    a02 = math.atan2(y2 - y, x2 - x) - a2 - PI * 2
    while a02 < a01:
        a02 += PI * 2
    out = [[x1, y1]]
    for i in range(n):
        a = lerp(a01, a02, i / (n - 1))
        out.append([x + math.cos(a) * r, y + math.sin(a) * r])
    out.append([x2, y2])
    out = resample(out, 3)
    for i, pt in enumerate(out):
        s = math.sin(i / (len(out) - 1) * PI)
        px, py = pt
        pt[0] += (noise(px * 0.01, py * 0.01) - 0.5) * s * 50
        pt[1] += (noise(px * 0.01, py * 0.01) - 0.5) * s * 50
    return out


# ---------------------------------------------------------------- head


@dataclass
class Head:
    top: list  # nose -> top seam point
    bottom: list  # nose -> bottom seam point
    seam: list  # top seam -> bottom seam (the gill line)
    nose: tuple
    eye: tuple  # (x, y, radius, type)
    jaw_hinge: tuple
    jaw_tip: tuple
    mouth_corner: tuple


def fish_head(noise, x0, y0, x1, y1, x2, y2, a) -> Head:
    n = 20
    c0, c1, c2 = [], [], []
    for i in range(n):
        t = i / (n - 1)
        ang = PI / 2 * t
        x = x1 - _spow(math.cos(ang), 1.5) * (x1 - x0)
        y = y0 - _spow(math.sin(ang), 1.5) * (y0 - y1)
        dx = (noise(x * 0.01, y * 0.01, 9) * 40 - 20) * (1.01 - t)
        dy = (noise(x * 0.01, y * 0.01, 8) * 40 - 20) * (1.01 - t)
        c0.append([x + dx, y + dy])
    for i in range(n):
        t = i / (n - 1)
        ang = PI / 2 * t
        x = x2 - _spow(math.cos(ang), 0.8) * (x2 - x0)
        y = y0 + _spow(math.sin(ang), 1.5) * (y2 - y0)
        dx = (noise(x * 0.01, y * 0.01, 9) * 40 - 20) * (1.01 - t)
        dy = (noise(x * 0.01, y * 0.01, 8) * 40 - 20) * (1.01 - t)
        c1.insert(0, [x + dx, y + dy])
    ang = math.atan2(y2 - y1, x2 - x1)
    for i in range(1, n - 1):
        t = i / (n - 1)
        p = lerp2d((x1, y1), (x2, y2), t)
        s = _spow(math.sin(t * PI), 0.5)
        r = noise(t * 2, 1.2) * s * 20
        c2.append([p[0] + math.cos(ang - PI / 2) * r, p[1] + math.sin(ang - PI / 2) * r])

    par = (0.475, 0.375)
    ex = x0 * par[0] + x1 * par[1] + x2 * (1 - par[0] - par[1])
    ey = y0 * par[0] + y1 * par[1] + y2 * (1 - par[0] - par[1])
    d0 = pt_seg_dist((ex, ey), (x0, y0), (x1, y1))
    d1 = pt_seg_dist((ex, ey), (x0, y0), (x2, y2))
    if d0 < a["eye_size"] and d1 < a["eye_size"]:
        a["eye_size"] = min(d0, d1)
    elif d0 < a["eye_size"]:
        ang = math.atan2(y1 - y0, x1 - x0) + PI / 2
        ex = x0 * 0.5 + x1 * 0.5 + math.cos(ang) * a["eye_size"]
        ey = y0 * 0.5 + y1 * 0.5 + math.sin(ang) * a["eye_size"]

    jaw_pt0 = c1[18 - a["mouth_size"]]
    jaw_l = dist(jaw_pt0, c1[18]) * a["jaw_size"]
    jaw_ang0 = math.atan2(c1[18][1] - jaw_pt0[1], c1[18][0] - jaw_pt0[0])
    jaw_ang = jaw_ang0 - (a["has_teeth"] * 0.5 + 0.5) * a["jaw_open"] * PI / 4
    jaw_pt1 = (jaw_pt0[0] + math.cos(jaw_ang) * jaw_l, jaw_pt0[1] + math.sin(jaw_ang) * jaw_l)
    return Head(c0, c1, c2, (x0, y0), (ex, ey, a["eye_size"], a["eye_type"]), tuple(jaw_pt0), jaw_pt1, tuple(c1[18]))


# ---------------------------------------------------------------- the fish


@dataclass
class Drawing:
    params: dict
    curve0: list  # back line, nose end first, drawing space (y down)
    curve1: list  # belly line
    head: Head
    fins: list
    pattern: object  # f(x, y) -> bool, or None
    finlets: list  # [(a, tip, b)] triangles, median plane
    adipose: list  # bump polyline or []


def body_curves(a, noise, n=32):
    c0, c1 = [], []
    if a["body_curve_type"] == 0:
        s = a["body_curve_amount"]
        for k, sink in ((1, c0), (2, c1)):
            for i in range(n):
                t = i / (n - 1)
                x = 225 + (t - 0.5) * a["body_length"]
                h = (math.sin(t * PI) * lerp(0.5, 1, noise(t * 2, k)) * s + (1 - s)) * a["body_height"]
                sink.append([x, 150 - h if k == 1 else 150 + h])
    else:
        for k, sink in ((1, c0), (2, c1)):
            for i in range(n):
                t = i / (n - 1)
                x = 225 + (t - 0.5) * a["body_length"]
                h = lerp(1 - a["body_curve_amount"], 1, lerp(0, 1, noise(t * 1.2, k)) * bean(1 - t)) * a["body_height"]
                sink.append([x, 150 - h if k == 1 else 150 + h])
    return c0, c1


def draw(a: dict, rng: Rng) -> Drawing:
    """The fish() of the JS, minus the plotter line art: curves, fins, head, pattern."""
    noise = Noise(rng)
    c0, c1 = body_curves(a, noise)
    pat = pattern_func(a, rng, noise)
    fins = []

    # dorsal
    if a["dorsal_type"] == 0:
        a0, a1, cv = 0.2 + rng.deviate(0.05), 0.3 + rng.deviate(0.05), 0
        dl = a["dorsal_length"]
        f = lambda t: (0.3 + noise(t * 3) * 0.7) * dl * math.sin(t * PI) ** 0.5  # noqa: E731
    else:
        a0, a1, cv = 0.6 + rng.deviate(0.05), 0.3 + rng.deviate(0.05), a["dorsal_length"] / 8
        dl = a["dorsal_length"]
        f = lambda t: dl * ((t - 1) ** 2 * 0.5 + (1 - t) * 0.5)  # noqa: E731
    seg = c0[a["dorsal_start"] : a["dorsal_end"]]
    if a["dorsal_texture_type"] == 0:
        fins.append(fin_a(rng, noise, "dorsal", resample(seg, 5), a0, a1, f, False, cv, 0))
    else:
        fins.append(fin_b(rng, noise, "dorsal", resample(seg, 15), a0, a1, f))

    # pectoral ("wing"), drawn on the flank: a short vertical root
    pt = lerp2d(c0[a["wing_start"]], c1[a["wing_end"]], a["wing_y"])
    root = [[pt[0], lerp(pt[1] - a["wing_width"] / 2, pt[1] + a["wing_width"] / 2, i / 9)] for i in range(10)]
    wl = a["wing_length"]
    if a["wing_type"] == 0:
        a0, a1, soft, cv = -0.4 + rng.deviate(0.05), 0.4 + rng.deviate(0.05), 10, 0
        f = lambda t: (40 + (20 + noise(t * 3) * 70) * math.sin(t * PI) ** 0.5) / 130 * wl  # noqa: E731
    else:
        a0, a1, soft, cv = 0 + rng.deviate(0.05), 0.4 + rng.deviate(0.05), 5, wl / 25
        f = lambda t: wl * (1 - t * 0.95)  # noqa: E731
    if a["wing_texture_type"] == 0:
        fins.append(fin_a(rng, noise, "pectoral", resample(root, 1.5), a0, a1, f, True, cv, 0, soft))
    else:
        fins.append(fin_b(rng, noise, "pectoral", resample(root, 4), a0, a1, f))

    # pelvic, on the belly line
    pl = a["pelvic_length"]
    if a["pelvic_type"] == 0:
        a0, a1 = -0.8 + rng.deviate(0.05), -0.5 + rng.deviate(0.05)
        f = lambda t: (10 + (15 + noise(t * 3) * 60) * math.sin(t * PI) ** 0.5) / 85 * pl  # noqa: E731
    else:
        a0, a1 = -0.9 + rng.deviate(0.05), -0.3 + rng.deviate(0.05)
        f = lambda t: (t * 0.5 + 0.5) * pl  # noqa: E731
    seg = c1[a["pelvic_start"] : a["pelvic_end"]][::-1]
    step = 2 if a["pelvic_type"] else (5 if a["pelvic_texture_type"] == 0 else 15)
    seg = resample(seg, step)
    if a["pelvic_texture_type"] == 0:
        fins.append(fin_a(rng, noise, "pelvic", seg, a0, a1, f))
    else:
        fins.append(fin_b(rng, noise, "pelvic", seg, a0, a1, f))

    # anal
    al = a["anal_length"]
    a0, a1 = -0.4 + rng.deviate(0.05), -0.4 + rng.deviate(0.05)
    if a["anal_type"] == 0:
        f = lambda t: (10 + (10 + noise(t * 3) * 30) * math.sin(t * PI) ** 0.5) / 50 * al  # noqa: E731
    else:
        f = lambda t: al * (t * t * 0.8 + 0.2)  # noqa: E731
    seg = c1[a["anal_start"] : a["anal_end"]][::-1]
    if a["anal_texture_type"] == 0:
        fins.append(fin_a(rng, noise, "anal", resample(seg, 5), a0, a1, f))
    else:
        fins.append(fin_b(rng, noise, "anal", resample(seg, 15), a0, a1, f))

    # tail
    r4 = dist(c0[-2], c1[-2])
    n4 = max(min(int(r4 / 1.5), 20), 8)
    d4 = r4 / n4
    tl = a["tail_length"]
    tt = a["tail_type"]
    if tt == 0:
        rt = resample([c0[-1], c1[-1]], d4)
        tail = fin_a(rng, noise, "tail", rt, -0.6, 0.6, lambda t: (75 - (10 + noise(t * 3) * 10) * math.sin(3 * t * PI - PI)) / 75 * tl, True)
    elif tt == 1:
        rt = resample([c0[-2], c1[-2]], d4)
        tail = fin_a(rng, noise, "tail", rt, -0.6, 0.6, lambda t: tl * (math.sin(t * PI) * 0.5 + 0.5), True)
    elif tt == 2:
        rt = resample([c0[-1], c1[-1]], d4 * 0.7)
        cv = tl / 8
        tail = fin_a(rng, noise, "tail", rt, -0.6, 0.6, lambda t: (abs(math.cos(PI * t)) * 0.8 + 0.2) * tl, True, cv, -cv)
    elif tt == 3:
        rt = resample([c0[-2], c1[-2]], d4)
        tail = fin_a(rng, noise, "tail", rt, -0.6, 0.6, lambda t: (1 - math.sin(t * PI) * 0.3) * tl, True)
    elif tt == 4:
        rt = resample([c0[-2], c1[-2]], d4)
        tail = fin_a(rng, noise, "tail", rt, -0.6, 0.6, lambda t: (1 - math.sin(t * PI) * 0.6) * (1 - t * 0.45) * tl, True)
    else:
        rt = resample([c0[-2], c1[-2]], d4)
        tail = fin_a(rng, noise, "tail", rt, -0.6, 0.6, lambda t: (1 - math.sin(t * PI) ** 0.4 * 0.55) * tl, True)
    fins.append(tail)

    finlets, adipose = [], []
    ft = a["finlet_type"]
    if ft == 1:
        finlets += finlet_teeth(resample(c0[a["dorsal_end"] : -2], 5), 5)
        fc = resample(c1[a["anal_end"] : -2][::-1], 5)
        if len(fc) > 1:
            finlets += finlet_teeth(fc, 5)
    elif ft == 2:
        adipose = fin_adipose(noise, resample(c0[27:30], 5), 20, -5, 6)
    elif ft == 3:
        seg = resample(c0[a["dorsal_end"] + 2 : -3], 5)
        if len(seg) > 2:
            dl = a["dorsal_length"] * 0.6
            fins.append(fin_a(rng, noise, "finlet", seg, 0.2, 0.3, lambda t: (0.3 + noise(t * 3) * 0.7) * dl * math.sin(t * PI) ** 0.5))

    if a["neck_type"] == 0:
        head = fish_head(noise, 50 - a["head_length"], 150 + a["nose_height"], *c0[6], *c1[5], a)
    else:
        head = fish_head(noise, 50 - a["head_length"], 150 + a["nose_height"], *c0[5], *c1[6], a)
    return Drawing(a, c0, c1, head, fins, pat, finlets, adipose)


def fish_drawing(seed: str, overrides: dict | None = None) -> Drawing:
    """Seed string -> params (as the JS main()) -> drawing. `overrides` is applied after generate_params."""
    rng = Rng(str_to_seed(seed))
    a = generate_params(rng)
    if overrides:
        a.update(overrides)
    return draw(a, rng)
