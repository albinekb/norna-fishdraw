"""3D lift of a fishdraw drawing: lofted body, thin double-sided fins, eyes.

The 2D drawing is a side view (nose left, back up, y down). Frame out (glTF,
metres, matching the game's held fish): +Z nose,
+Y back, X the flank normal; origin at the centre of the fish's bounding box.

  * body: `STATIONS` elliptical rings along the spine. The silhouette (head
    outline + back/belly curves) gives each ring's vertical extent; the ring's
    lateral thickness is that height times the species `flat` ratio
    (width / depth). One `flank` material, textured by skin.py: planar
    side-view UVs, u nose -> tail root, v back -> belly, same on both flanks.
    Fins carry UVs too (u across the rays, v root -> free edge).
  * dorsal, anal, tail and finlets lie in the median plane (a vertical tail);
    pectoral and pelvic fins are a pair rooted on the flank / belly and
    splayed outward. Each fin is a strip from its root curve to its free edge
    (the fin_a / fin_b ray tips); the tips zig-zag sideways a little so the
    rays read as ridges. Single layer, double-sided material.
  * eyes: a ball with a dark cap on the outward pole, one each side.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .fishdraw_port import Drawing, arc_resample, dist

STATIONS = 18
SIDES = 8
M_FIN = {"dorsal": 7, "tail": 9, "pectoral": 5, "pelvic": 4, "anal": 6, "finlet": 5}


@dataclass
class Look:
    """What the 2D drawing does not say: real size, thickness, colours, features."""

    length_m: float
    flat: float  # lateral thickness / dorsoventral height
    palette: dict  # back flank belly fin accent iris pupil -> '#rrggbb'
    features: tuple = ()
    skin: object = None  # skin.Skin: drives the body and fin textures; None = plain


@dataclass
class Mesh:
    tris: dict = field(default_factory=dict)  # material -> [(a, b, c)] xyz tuples
    uvs: dict = field(default_factory=dict)  # material -> [(ua, ub, uc)] (u, v) tuples; only textured materials

    def add(self, mat, a, b, c, out=None, uv=None):
        """Add a triangle; with `out` (a reference point inside the solid) wind it outward. `uv` is (ua, ub, uc)."""
        if out is not None:
            n = _cross(_sub(b, a), _sub(c, a))
            ctr = ((a[0] + b[0] + c[0]) / 3 - out[0], (a[1] + b[1] + c[1]) / 3 - out[1], (a[2] + b[2] + c[2]) / 3 - out[2])
            # a face edge-on to `out` (dot ~ 0, e.g. the zero-radius nose ring) keeps its winding: a 1-ulp
            # sign flip there swapped two vertices between platforms
            if _dot(n, ctr) < -1e-9 * math.sqrt(_dot(n, n) * _dot(ctr, ctr)):
                b, c = c, b
                if uv:
                    uv = (uv[0], uv[2], uv[1])
        self.tris.setdefault(mat, []).append((a, b, c))
        if uv:
            self.uvs.setdefault(mat, []).append(tuple(uv))

    def count(self):
        return sum(len(v) for v in self.tris.values())

    def bounds(self):
        pts = [p for v in self.tris.values() for t in v for p in t]
        return tuple(min(p[i] for p in pts) for i in range(3)), tuple(max(p[i] for p in pts) for i in range(3))

    def shift(self, d):
        self.tris = {m: [tuple((p[0] - d[0], p[1] - d[1], p[2] - d[2]) for p in t) for t in v] for m, v in self.tris.items()}


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


class _Profile:
    """Piecewise-linear lookup over sorted (x, y) points."""

    def __init__(self, pts):
        pts = sorted((p[0], p[1]) for p in pts)
        xs, ys = [], []
        for x, y in pts:
            if xs and x - xs[-1] < 1e-6:
                continue
            xs.append(x)
            ys.append(y)
        self.xs, self.ys = xs, ys

    def __call__(self, x):
        xs, ys = self.xs, self.ys
        if x <= xs[0]:
            return ys[0]
        if x >= xs[-1]:
            return ys[-1]
        lo, hi = 0, len(xs) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if xs[mid] <= x:
                lo = mid
            else:
                hi = mid
        t = (x - xs[lo]) / (xs[hi] - xs[lo])
        return ys[lo] * (1 - t) + ys[hi] * t


def _tail_root_index(d: Drawing) -> int:
    return 31 if d.params["tail_type"] in (0, 2) else 30


class Lift:
    def __init__(self, d: Drawing, look: Look):
        self.d, self.look = d, look
        a = d.params
        h = d.head
        k_top = 6 if a["neck_type"] == 0 else 5
        k_bot = 5 if a["neck_type"] == 0 else 6
        e = _tail_root_index(d)
        top = [p for p in h.top] + [p for p in d.curve0[k_top + 1 : e + 1]]
        bot = [p for p in h.bottom] + [p for p in d.curve1[k_bot + 1 : e + 1]]
        self.top_p, self.bot_p = _Profile(top), _Profile(bot)
        self.x_nose = h.nose[0]
        self.x_end = d.curve0[e][0]
        tail = [f for f in d.fins if f.kind == "tail"][0]
        x_tip = max(p[0] for p in tail.tip)
        self.u = look.length_m / (x_tip - self.x_nose)
        self.x_c = (self.x_nose + x_tip) / 2
        self._stations()

    def P(self, px, py, lat=0.0):
        """Drawing point (+ lateral metres) -> (x, y, z) metres. Nose is +Z, back +Y."""
        return (lat, (150.0 - py) * self.u, (self.x_c - px) * self.u)

    def _stations(self):
        n = STATIONS
        xs = [self.x_nose + (self.x_end - self.x_nose) * (k / (n - 1)) ** 1.25 for k in range(n)]
        hh = [(self.bot_p(x) - self.top_p(x)) / 2 for x in xs]
        mid = [(self.bot_p(x) + self.top_p(x)) / 2 for x in xs]
        hmin = 1.5
        hh = [max(v, hmin) for v in hh]
        for _ in range(2):  # smooth the noisy head outline
            hh = [hh[0]] + [(hh[i - 1] + 2 * hh[i] + hh[i + 1]) / 4 for i in range(1, n - 1)] + [hh[-1]]
            mid = [mid[0]] + [(mid[i - 1] + 2 * mid[i] + mid[i + 1]) / 4 for i in range(1, n - 1)] + [mid[-1]]
        hh[0] = 0.0
        self.xs, self.hh, self.mid = xs, hh, mid
        self.hh_p = _Profile(list(zip(xs, hh)))
        self.mid_p = _Profile(list(zip(xs, mid)))

    def hw(self, x):
        return self.hh_p(x) * self.look.flat

    def surface_lat(self, x, y):
        hh, mid = self.hh_p(x), self.mid_p(x)
        r = min(0.9, abs(y - mid) / max(hh, 1e-6))
        return self.hw(x) * math.sqrt(1 - r * r) * self.u

    def snap_y(self, x, y):
        """Pull a root point that sits on the outline slightly into the body."""
        hh, mid = self.hh_p(x), self.mid_p(x)
        return y + 0.12 * hh if y < mid else y - 0.12 * hh

    # ------------------------------------------------------------ body
    def body(self, mesh: Mesh):
        """One textured `flank` surface: planar side-view UVs (u nose -> tail root, v back -> belly), shared by both flanks."""
        n, s = STATIONS, SIDES
        rings = []
        for k in range(n):
            x, hh, mid = self.xs[k], self.hh[k], self.mid[k]
            hw = hh * self.look.flat
            ring = []
            for j in range(s):
                th = 2 * math.pi * j / s
                u = (x - self.x_nose) / (self.x_end - self.x_nose)
                ring.append((x, mid - hh * math.cos(th), self.u * hw * math.sin(th), (u, (1 - math.cos(th)) / 2)))
            rings.append(ring)
        centre = lambda k: self.P(self.xs[k], self.mid[k], 0.0)  # noqa: E731

        for k in range(n - 1):
            for j in range(s):
                j2 = (j + 1) % s
                a, b = rings[k][j], rings[k][j2]
                c, dd = rings[k + 1][j2], rings[k + 1][j]
                A, B, C, D = (self.P(*p[:3]) for p in (a, b, c, dd))
                ua, ub, uc, ud = a[3], b[3], c[3], dd[3]
                ctr = centre(k)
                if k == 0:
                    mesh.add("flank", A, C, D, ctr, (ua, uc, ud))
                else:
                    mesh.add("flank", A, B, C, ctr, (ua, ub, uc))
                    mesh.add("flank", A, C, D, ctr, (ua, uc, ud))
        # tail-end cap (flat, hidden by the tail fin root)
        last = [self.P(*p[:3]) for p in rings[-1]]
        cc = centre(n - 1)
        for j in range(s):
            j2 = (j + 1) % s
            mesh.add("flank", cc, last[j], last[j2], (cc[0], cc[1], cc[2] + 1.0), ((1.0, 0.5), rings[-1][j][3], rings[-1][j2][3]))
        # nose cap is the k == 0 fan (its ring has zero radius)

    # ------------------------------------------------------------ fins
    def _strip(self, mesh, fin, m, place):
        root = arc_resample(fin.root, m)
        tip = arc_resample(fin.tip, m)
        r3, t3 = [], []
        span = max(dist(r, t) for r, t in zip(root, tip)) * self.u
        for i, (r, t) in enumerate(zip(root, tip)):
            rp, tp = place(r, t, i)
            r3.append(rp)
            t3.append(tp)
        ridge = 0.05 * span
        for i in range(m - 1):
            sgn0 = ridge if i % 2 == 0 else -ridge
            sgn1 = -sgn0
            a, b = r3[i], r3[i + 1]
            c = (t3[i + 1][0] + sgn1, t3[i + 1][1], t3[i + 1][2])
            dd = (t3[i][0] + sgn0, t3[i][1], t3[i][2])
            u0, u1 = i / (m - 1), (i + 1) / (m - 1)
            mesh.add("fin", a, b, c, None, ((u0, 0.0), (u1, 0.0), (u1, 1.0)))
            mesh.add("fin", a, c, dd, None, ((u0, 0.0), (u1, 1.0), (u0, 1.0)))

    def fins(self, mesh: Mesh):
        for fin in self.d.fins:
            k = fin.kind
            m = M_FIN[k]
            if k in ("dorsal", "anal", "finlet", "tail"):

                def place(r, t, i, k=k):
                    ry = r[1] if k == "tail" else self.snap_y(r[0], r[1])
                    return self.P(r[0], ry), self.P(t[0], t[1])

                self._strip(mesh, fin, m, place)
            else:
                splay = 0.6 if k == "pectoral" else 0.75
                for side in (1, -1):

                    def place(r, t, i, side=side, k=k, splay=splay):
                        y = r[1] if k == "pectoral" else self.snap_y(r[0], r[1]) - 0.1 * self.hh_p(r[0])
                        lat0 = 0.95 * self.surface_lat(r[0], y)
                        v = (t[0] - r[0], t[1] - r[1])
                        vl = math.hypot(*v)
                        tx, ty = r[0] + v[0] * math.cos(splay), y + (t[1] - r[1]) * math.cos(splay)
                        return self.P(r[0], y, side * lat0), self.P(tx, ty, side * (lat0 + vl * self.u * math.sin(splay)))

                    self._strip(mesh, fin, m, place)
        for a, tip, b in self.d.finlets:
            top = tip[1] < self.mid_p(tip[0])
            ra = self.P(a[0], self.snap_y(a[0], a[1]))
            rb = self.P(b[0], self.snap_y(b[0], b[1]))
            mesh.add("fin", ra, rb, self.P(*tip), None, ((0.25, 0.0), (0.75, 0.0), (0.5, 1.0)))
            del top
        if self.d.adipose:
            poly = arc_resample(self.d.adipose, 8)
            ctr = self.P(
                (poly[0][0] + poly[-1][0]) / 2, self.snap_y(poly[0][0], (poly[0][1] + poly[-1][1]) / 2)
            )
            pts = [self.P(*p) for p in poly]
            for i in range(len(pts) - 1):
                mesh.add("fin", ctr, pts[i], pts[i + 1], None, ((0.5, 0.0), (i / 7, 1.0), ((i + 1) / 7, 1.0)))

    # ------------------------------------------------------------ eyes, barbel
    def eyes(self, mesh: Mesh):
        if "blind" in self.look.features:
            return
        ex, ey, er, _t = self.d.head.eye
        hh = self.hh_p(ex)
        lat = self.surface_lat(ex, ey) * 0.88
        r = min(er * self.u * 0.6, 0.4 * hh * self.u)
        y = min(max(ey, self.mid_p(ex) - 0.75 * hh), self.mid_p(ex) + 0.75 * hh)
        for side in (1, -1):
            c = self.P(ex, y, side * lat)
            self._ball(mesh, c, r, side)
        if "barbel" in self.look.features:
            hx, hy = self.d.head.jaw_hinge
            top = self.P(hx, hy, 0.0)
            bar = (top[0], top[1] - 0.12 * self.look.length_m, top[2] - 0.05 * self.look.length_m)
            w = 0.006 * self.look.length_m / 0.3
            mesh.add("fin", (top[0] - w, top[1], top[2]), (top[0] + w, top[1], top[2]), bar, None, ((0.5, 0.5),) * 3)

    def _ball(self, mesh, c, r, side):
        """6 meridians x 3 bands, pole axis on the lateral axis; the outer cap is the pupil."""
        rings = [(0.0, 0.0), (math.pi / 3, 0), (2 * math.pi / 3, 0), (math.pi, 0)]
        n = 6

        def pt(pol, j):
            az = 2 * math.pi * j / n
            return (c[0] + side * r * math.cos(pol), c[1] + r * math.sin(pol) * math.cos(az), c[2] + r * math.sin(pol) * math.sin(az))

        for j in range(n):
            j2 = (j + 1) % n
            mesh.add("pupil", pt(0, 0), pt(rings[1][0], j), pt(rings[1][0], j2), c)
            for (p0, _), (p1, _) in ((rings[1], rings[2]),):
                a, b, cc, dd = pt(p0, j), pt(p0, j2), pt(p1, j2), pt(p1, j)
                mesh.add("iris", a, b, cc, c)
                mesh.add("iris", a, cc, dd, c)
            mesh.add("iris", pt(rings[2][0], j), pt(rings[2][0], j2), pt(math.pi, 0), c)


def lift(d: Drawing, look: Look) -> Mesh:
    """Drawing -> centred Mesh (origin at the bounding-box centre)."""
    L = Lift(d, look)
    mesh = Mesh()
    L.body(mesh)
    L.fins(mesh)
    L.eyes(mesh)
    lo, hi = mesh.bounds()
    mesh.shift(tuple((lo[i] + hi[i]) / 2 for i in range(3)))
    return mesh
