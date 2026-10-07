"""The never-broken validator: geometry only, read off the triangles, never off what the builder says it did.

Checks, each a named key of the Report: `connected` (every part touches the skin, directly or through its parent),
`rooted` (every claimed root point lies on its parent's surface), `pierce` (no part vertex deeper inside the body than
its allowance), `proportions` (per-kind size limits; eyes and bulbs must be balls), `mesh` (no NaN, no degenerate or
inward-facing face, under the tri budget), `silhouette` (the skin fills a floor share of the fish's side and top view).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..lift3d import Mesh
from .surface import add, cross, dot, mean, mul, norm, sub


TOUCH = 0.01  # a root or contact counts within this fraction of body length of the surface
PIERCE = 0.04  # tolerated embedding, fraction of body length
TRI_BUDGET = {"squid": 1500, "sturgeon": 1100, "mawfish": 1300}  # per plan; the rest share DEFAULT_BUDGET
DEFAULT_BUDGET = 900
DEGENERATE = 1e-9  # min triangle area, fraction of body length squared
BAND = 0.04  # a section is read from skin vertices within this fraction of length of a part

#: extent (largest bounding-box side) of one part, fraction of body length: (min, max)
EXTENT = {
    "eye": (0.004, 0.4),
    "tooth": (0.003, 0.12),
    "jaw": (0.01, 0.5),
    "barbel": (0.01, 0.35),
    "tentacle": (0.04, 0.9),
    "arm": (0.04, 1.2),
    "stalk": (0.03, 0.5),
    "bulb": (0.004, 0.35),
    "dorsal": (0.01, 1.3),
    "anal": (0.01, 1.3),
    "pectoral": (0.01, 1.2),
    "pelvic": (0.005, 0.9),
    "frill": (0.01, 0.9),
    "tail": (0.01, 0.85),
    "fringe": (0.01, 0.9),
    "wing": (0.01, 1.0),
    "finlet": (0.003, 0.2),
    "crest": (0.1, 1.0),
}
REACH = {"finlet": (0.002, 0.08), "spike": (0.002, 0.14), "scute": (0.0003, 0.08), "wart": (0.00005, 0.05)}  # group parts: how far a bump stands off
CREST_HEIGHT = 0.26  # a crest rises at most this far above the body, fraction of length
EYE_TO_HEAD = {"round": 1.25, "flat": 0.9, "ribbon": 0.7, "eel": 0.7, "hammerhead": 1.8, "globe": 0.62, "disc": 0.62, "armoured": 0.7, "ray": 0.9, "seahorse": 0.7, "squid": 0.8}
EYES_ON_TOP = frozenset({"flat", "ray"})  # both eyes sit on the upper face: they may stand above it
EYE_STANDS = {"round": 0.8, "hammerhead": 1.3, "flat": 0.9, "ray": 0.9}  # default 0.5: how far the eyeball may stand off the skull, as a fraction of the head's depth
BUMPS = frozenset({"spike", "scute", "wart"})
KIND_NEEDS = {"stalk": "bulb", "tooth": "jaw"}  # a part and its children go together
#: skin coverage floor of the whole fish's side and top bounding box
SILHOUETTE = {"round": (0.1, 0.01), "flat": (0.2, 0.2), "ribbon": (0.1, 0.04), "eel": (0.1, 0.04), "hammerhead": (0.06, 0.06), "globe": (0.2, 0.15), "disc": (0.12, 0.04), "armoured": (0.15, 0.05), "ray": (0.15, 0.2), "seahorse": (0.05, 0.05), "squid": (0.05, 0.03)}


@dataclass
class Report:
    ok: bool
    checks: dict = field(default_factory=dict)
    worst: dict = field(default_factory=dict)
    notes: list = field(default_factory=list)

    def failed(self):
        return [k for k, v in self.checks.items() if not v]


def _closest(p, a, b, c):
    """Closest point to p on triangle abc (Ericson, Real-Time Collision Detection 5.1.5)."""
    ab, ac, ap = sub(b, a), sub(c, a), sub(p, a)
    d1, d2 = dot(ab, ap), dot(ac, ap)
    if d1 <= 0 and d2 <= 0:
        return a
    bp = sub(p, b)
    d3, d4 = dot(ab, bp), dot(ac, bp)
    if d3 >= 0 and d4 <= d3:
        return b
    vc = d1 * d4 - d3 * d2
    if vc <= 0 and d1 >= 0 and d3 <= 0:
        return add(a, mul(ab, d1 / (d1 - d3)))
    cp = sub(p, c)
    d5, d6 = dot(ab, cp), dot(ac, cp)
    if d6 >= 0 and d5 <= d6:
        return c
    vb = d5 * d2 - d1 * d6
    if vb <= 0 and d2 >= 0 and d6 <= 0:
        return add(a, mul(ac, d2 / (d2 - d6)))
    va = d3 * d6 - d5 * d4
    if va <= 0 and (d4 - d3) >= 0 and (d5 - d6) >= 0:
        return add(b, mul(sub(c, b), (d4 - d3) / ((d4 - d3) + (d5 - d6))))
    den = 1.0 / (va + vb + vc)
    return add(a, add(mul(ab, vb * den), mul(ac, vc * den)))


class TriIndex:
    """Triangles bucketed by centroid z: nearest-by-centroid candidates, then exact distance on a few."""

    def __init__(self, tris, bins=16):
        self.items = []
        for a, b, c in tris:
            n = cross(sub(b, a), sub(c, a))
            ln = math.sqrt(dot(n, n))
            if ln < 1e-18 or ln != ln:
                continue
            cen = ((a[0] + b[0] + c[0]) / 3, (a[1] + b[1] + c[1]) / 3, (a[2] + b[2] + c[2]) / 3)
            self.items.append((cen, mul(n, 1 / ln), a, b, c))
        zs = [it[0][2] for it in self.items] or [0.0]
        self.z0, self.z1 = min(zs), max(zs)
        self.bins = max(1, min(bins, len(self.items) // 4 or 1))
        self.dz = (self.z1 - self.z0) / self.bins or 1.0
        self.buckets = [[] for _ in range(self.bins)]
        for i, it in enumerate(self.items):
            self.buckets[self._bin(it[0][2])].append(i)

    def _bin(self, z):
        return min(self.bins - 1, max(0, int((z - self.z0) / self.dz)))

    def _near(self, p, k):
        b = self._bin(p[2])
        idx = [i for q in (b - 1, b, b + 1) if 0 <= q < self.bins for i in self.buckets[q]]
        if len(idx) < k:
            idx = range(len(self.items))
        it = self.items
        scored = sorted(idx, key=lambda i: (it[i][0][0] - p[0]) ** 2 + (it[i][0][1] - p[1]) ** 2 + (it[i][0][2] - p[2]) ** 2)
        return scored[:k]

    def sd(self, p):
        """Cheap signed distance off the nearest-centroid triangle's plane (negative = inside)."""
        i = self._near(p, 1)[0]
        cen, n = self.items[i][0], self.items[i][1]
        return dot(sub(p, cen), n)

    def _pseudo(self):
        """Angle-weighted vertex normals and edge normal sums: the sign of a distance to an edge or a corner of a thin
        body must come from the faces that meet there, not from one face's plane."""
        if hasattr(self, "_vn"):
            return
        self._vn: dict = {}
        self._en: dict = {}
        for _, n, a, b, c in self.items:
            for p0, p1, p2 in ((a, b, c), (b, c, a), (c, a, b)):
                u, w = norm(sub(p1, p0)), norm(sub(p2, p0))
                ang = math.acos(max(-1.0, min(1.0, dot(u, w))))
                self._vn[p0] = add(self._vn.get(p0, (0.0, 0.0, 0.0)), mul(n, ang))
            for e in (frozenset((a, b)), frozenset((b, c)), frozenset((c, a))):
                self._en[e] = add(self._en.get(e, (0.0, 0.0, 0.0)), n)

    def dist(self, p, k=8):
        """Signed distance to the surface via the exact closest point on the `k` nearest-centroid triangles; the sign
        from the pseudonormal at that closest point (face, edge or vertex)."""
        self._pseudo()
        best, bi, bq = 1e30, None, None
        for i in self._near(p, k):
            _, n, a, b, c = self.items[i]
            q = _closest(p, a, b, c)
            d = sub(p, q)
            dd = math.sqrt(dot(d, d))
            if dd < best:
                best, bi, bq = dd, i, q
        _, n, a, b, c = self.items[bi]
        tol = 1e-9 + 1e-7 * best
        nrm = n
        for v in (a, b, c):
            if math.dist(bq, v) <= tol:
                nrm = self._vn[v]
                break
        else:
            for e0, e1 in ((a, b), (b, c), (c, a)):
                ab = sub(e1, e0)
                t = dot(sub(bq, e0), ab) / max(dot(ab, ab), 1e-30)
                if 0.0 < t < 1.0 and math.dist(bq, add(e0, mul(ab, t))) <= tol:
                    nrm = self._en[frozenset((e0, e1))]
                    break
        d = sub(p, bq)
        return best if dot(d, nrm) >= -1e-12 else -best


def _tris(mesh: Mesh):
    return [t for tris in mesh.tris.values() for t in tris]


def _bbox(pts):
    return tuple(min(p[i] for p in pts) for i in range(3)), tuple(max(p[i] for p in pts) for i in range(3))


def _max_dihedral(tris):
    """Largest angle (degrees) between the normals of two faces sharing an edge: a ball is gentle, a cube is 90."""
    edge: dict = {}
    for t in tris:
        n = norm(cross(sub(t[1], t[0]), sub(t[2], t[0])))
        for i in range(3):
            a, b = t[i], t[(i + 1) % 3]
            edge.setdefault((a, b) if a < b else (b, a), []).append(n)
    worst = 0.0
    for ns in edge.values():
        if len(ns) == 2:
            worst = max(worst, math.degrees(math.acos(max(-1.0, min(1.0, dot(ns[0], ns[1]))))))
    return worst


def _coverage(tris, bounds, axes, cols=40, rows=16):
    """Fraction of the bounding box's cells whose centre lies under some triangle, seen along the third axis."""
    (lo, hi) = bounds
    u0, u1, v0, v1 = lo[axes[0]], hi[axes[0]], lo[axes[1]], hi[axes[1]]
    du, dv = (u1 - u0) / cols or 1.0, (v1 - v0) / rows or 1.0
    hit = set()
    for t in tris:
        P = [(p[axes[0]], p[axes[1]]) for p in t]
        i0 = max(0, int((min(p[0] for p in P) - u0) / du))
        i1 = min(cols - 1, int((max(p[0] for p in P) - u0) / du))
        j0 = max(0, int((min(p[1] for p in P) - v0) / dv))
        j1 = min(rows - 1, int((max(p[1] for p in P) - v0) / dv))
        (ax, ay), (bx, by), (cx, cy) = P
        den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(den) < 1e-18:
            continue
        for i in range(i0, i1 + 1):
            x = u0 + (i + 0.5) * du
            for j in range(j0, j1 + 1):
                y = v0 + (j + 0.5) * dv
                w1 = ((by - cy) * (x - cx) + (cx - bx) * (y - cy)) / den
                w2 = ((cy - ay) * (x - cx) + (ax - cx) * (y - cy)) / den
                if w1 >= 0 and w2 >= 0 and w1 + w2 <= 1:
                    hit.add((i, j))
    return len(hit) / (cols * rows)


def _welded(skin_tris, parts, L):
    """The by-construction claim, read back off the triangles: every part's roots are its parent's own vertices, every
    root edge is a parent edge (no T-junction), and the whole fish is one vertex-connected component."""
    def edge_set(tris):
        out = set()
        for a, b, c in tris:
            out.update((frozenset((a, b)), frozenset((b, c)), frozenset((c, a))))
        return out

    verts = {"skin": {p for t in skin_tris for p in t}}
    edges = {"skin": edge_set(skin_tris)}
    notes = []
    for pt in parts:
        tris = _tris(pt.mesh)
        verts[pt.id] = {p for t in tris for p in t}
        edges[pt.id] = edge_set(tris)
    parent_of = {pt.id: pt.parent for pt in parts}
    for pt in parts:
        par = pt.parent
        if par not in verts:
            notes.append("%s has parent %r, which is not on the fish" % (pt.id, par))
            continue
        loose = [r for r in pt.roots if r not in verts[par]]
        if loose or not pt.roots:
            notes.append("%s has %d root vertices that are not %s's own" % (pt.id, len(loose) or 1, par))
            continue
        bad = [e for e in pt.edges if frozenset(e) not in edges[par]]
        if bad:
            notes.append("%s has %d root edges that are not %s edges (a T-junction)" % (pt.id, len(bad), par))
    # a part vertex that is not a parent vertex but sits within a hair of one is a near miss: touching, not welded
    h = 0.0002 * L
    cell = lambda p: (int(p[0] // h), int(p[1] // h), int(p[2] // h))  # noqa: E731
    grids: dict = {}
    for pid in verts:
        g_ = grids[pid] = {}
        for p in verts[pid]:
            g_.setdefault(cell(p), []).append(p)
    for pt in parts:
        par = pt.parent
        if par not in grids:
            continue
        own = verts[par]
        miss = 0
        for p in verts[pt.id]:
            if p in own:
                continue
            c0 = cell(p)
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for dz in (-1, 0, 1):
                        for q in grids[par].get((c0[0] + dx, c0[1] + dy, c0[2] + dz), ()):
                            if math.dist(p, q) < h:
                                miss += 1
        if miss:
            notes.append("%s has %d vertices within a hair of %s's own but not shared (a near-miss weld)" % (pt.id, miss, par))
    # one vertex-connected component over every triangle
    parent: dict = {}

    def find(x):
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for t in skin_tris + [t for pt in parts for t in _tris(pt.mesh)]:
        for p in t[1:]:
            parent[find(p)] = find(t[0])
    comps = len({find(p) for p in parent})
    if comps != 1:
        notes.append("%d vertex-connected pieces, expected 1" % comps)
    return notes, comps


def _band_extent(skin_pts, z, band):
    ys = [p[1] for p in skin_pts if abs(p[2] - z) <= band]
    xs = [abs(p[0]) for p in skin_pts if abs(p[2] - z) <= band]
    return (min(ys), max(ys), max(xs)) if ys else (0.0, 0.0, 0.0)


def validate(fish, skip=frozenset()) -> Report:
    """Run every check on a built `Fish` (skin mesh + parts). Reads triangles only. `skip` names checks a posed fish
    does not owe (silhouette, proportions, envelope, complete): the pose check keeps mesh, welded, connected and pierce."""
    skin_tris = _tris(fish.skin)
    rep = Report(True)
    rep.checks = {k: True for k in ("mesh", "welded", "connected", "rooted", "pierce", "envelope", "complete", "proportions", "silhouette")}

    def fail(key, note, **worst):
        rep.checks[key] = False
        rep.notes.append("%s: %s" % (key, note))
        for k, v in worst.items():
            rep.worst[k] = max(rep.worst.get(k, 0.0), v)

    allv = [p for t in skin_tris for p in t] + [p for pt in fish.parts for tris in pt.mesh.tris.values() for t in tris for p in t]
    if not skin_tris or any(c != c or abs(c) == math.inf for p in allv for c in p):
        fail("mesh", "no skin" if not skin_tris else "NaN or infinite vertex")
        rep.ok = False
        return rep
    skin_pts = [p for t in skin_tris for p in t]
    lo, hi = _bbox(skin_pts)
    L = max(hi[i] - lo[i] for i in range(3))
    if L <= 0:
        fail("mesh", "no skin length")
        rep.ok = False
        return rep
    eps, tol = TOUCH * L, PIERCE * L
    plan = fish.genome["plan"]

    # --- mesh
    n_tris = len(skin_tris) + sum(len(_tris(pt.mesh)) for pt in fish.parts)
    budget = TRI_BUDGET.get(fish.genome["species"], TRI_BUDGET.get(plan, DEFAULT_BUDGET))
    rep.worst["tris"] = float(n_tris)
    if n_tris > budget:
        fail("mesh", "%d tris over the budget %d" % (n_tris, budget))
    skin = TriIndex(skin_tris)
    for t in skin_tris + [t for pt in fish.parts for t in _tris(pt.mesh)]:
        cr = cross(sub(t[1], t[0]), sub(t[2], t[0]))
        if 0.5 * math.sqrt(dot(cr, cr)) < DEGENERATE * L * L:
            fail("mesh", "degenerate triangle")
            break
    # faces wind consistently (no directed edge used twice) and, on the whole, look away from the body's middle
    directed: dict = {}
    bump_tris = [t for pt in fish.parts if pt.kind in BUMPS for t in _tris(pt.mesh)]
    for a_, b_, c_ in skin_tris + bump_tris:  # a bump stands in for the cell it replaced: its faces wind like the skin's
        for e in ((a_, b_), (b_, c_), (c_, a_)):
            directed[e] = directed.get(e, 0) + 1
    flipped = sum(1 for n in directed.values() if n > 1)
    mid_pt = tuple(sum(p[k] for p in skin_pts) / len(skin_pts) for k in range(3))
    outward = sum(dot(cross(sub(b_, a_), sub(c_, a_)), sub(mean([a_, b_, c_]), mid_pt)) for a_, b_, c_ in skin_tris)
    if flipped:
        fail("mesh", "%d skin edges are wound twice the same way (a flipped face)" % flipped)
    if outward <= 0:
        fail("mesh", "the skin as a whole faces inward")

    # --- welded: by construction, so this is an assertion that should never fire
    notes, comps = _welded(skin_tris, fish.parts, L)
    rep.worst["pieces"] = float(comps)
    for n in notes:
        fail("welded", n)

    by_id = {pt.id: pt for pt in fish.parts}
    idx = {"skin": skin}
    verts = {pt.id: pt.verts() for pt in fish.parts}

    def index(pid):
        if pid not in idx:
            idx[pid] = TriIndex(_tris(by_id[pid].mesh), bins=1)
        return idx[pid]

    # --- connected (geometric tripwire): union-find over contact; a part must reach the skin
    comp = {pid: pid for pid in ["skin", *by_id]}

    def root_of(x):
        while comp[x] != x:
            comp[x] = comp[comp[x]]
            x = comp[x]
        return x

    def touches(pid, target):
        ix = index(target)
        pos = neg = False
        for v in verts[pid]:
            d = ix.dist(v)
            if abs(d) <= eps:
                return True
            pos, neg = pos or d > 0, neg or d < 0
            if target == "skin" and pos and neg:
                return True
        return False

    for pt in fish.parts:
        if (pt.parent in idx or pt.parent in by_id) and touches(pt.id, pt.parent):
            comp[root_of(pt.id)] = root_of(pt.parent)
    for pt in fish.parts:
        if root_of(pt.id) != root_of("skin"):
            for other in ["skin", *[q for q in by_id if q != pt.id]]:
                if root_of(other) != root_of(pt.id) and touches(pt.id, other):
                    comp[root_of(pt.id)] = root_of(other)
                    break
    for pt in fish.parts:
        if root_of(pt.id) != root_of("skin"):
            fail("connected", "%s floats free of the fish" % pt.id)

    # --- rooted (tripwire): every claimed root point is on its parent's surface
    for pt in fish.parts:
        if pt.parent != "skin" and pt.parent not in by_id:
            fail("rooted", "%s has parent %r, which is not on the fish" % (pt.id, pt.parent))
            continue
        ix = index(pt.parent)
        if not pt.roots:
            fail("rooted", "%s claims no root" % pt.id)
        for r in pt.roots[:8]:
            d = abs(ix.dist(r, k=24))
            rep.worst["root_gap"] = max(rep.worst.get("root_gap", 0.0), d / L)
            if d > eps:
                fail("rooted", "%s root is %.3f L off its %s" % (pt.id, d / L, pt.parent))
                break

    # --- pierce: no vertex deeper inside the body than the tolerance (parts only ever grow outward)
    for pt in fish.parts:
        if pt.kind in BUMPS:  # a bump stands where the skin was cut away: there is no skin there to be inside of
            continue
        for v in verts[pt.id]:
            if skin.sd(v) < -tol:
                depth = -skin.dist(v)
                rep.worst["pierce"] = max(rep.worst.get("pierce", 0.0), depth / L)
                if depth > tol:
                    fail("pierce", "%s sits %.3f L inside the body (allows %.3f L)" % (pt.id, depth / L, tol / L))
                    break

    # --- envelope: an eye stays inside the head's silhouette: not above the back, not through the far flank
    for pt in fish.parts:
        if pt.kind != "eye" or "envelope" in skip:
            continue
        vs = verts[pt.id]
        cz = sum(v[2] for v in vs) / len(vs)
        ymin, ymax, xmax = _band_extent(skin_pts, cz, BAND * L)
        top = max(v[1] for v in vs)
        rep.worst["eye_above_back"] = max(rep.worst.get("eye_above_back", 0.0), (top - ymax) / L)
        mid_eye = abs(sum(v[0] for v in pt.roots) / len(pt.roots)) < 0.2 * xmax  # a cyclops stands on the midline
        if plan not in EYES_ON_TOP and not mid_eye and top > ymax + tol:
            fail("envelope", "%s rises %.3f L above the back" % (pt.id, (top - ymax) / L))
        cx = sum(v[0] for v in pt.roots) / len(pt.roots)
        if abs(cx) > 0.2 * xmax:
            far = min(v[0] * (1 if cx > 0 else -1) for v in vs)
            if far < -tol:
                fail("envelope", "%s reaches through to the far flank" % pt.id)
        vis = [p for role in ("sclera", "iris", "pupil") for t in pt.mesh.tris.get(role, []) for p in t]  # the eye you can see
        ext = max(max(v[i] for v in vis) - min(v[i] for v in vis) for i in range(3)) if vis else 0.0
        depth = max(ymax - ymin, 1e-9)
        if plan in EYES_ON_TOP:
            depth = max(2 * xmax * 0.5, 1e-9)  # the head's width: both eyes sit on the upper face
        ratio = ext / depth
        rep.worst["eye_to_head"] = max(rep.worst.get("eye_to_head", 0.0), ratio)
        if ratio > EYE_TO_HEAD[plan]:
            fail("proportions", "%s is %.2f of the head's depth, allowed %.2f" % (pt.id, ratio, EYE_TO_HEAD[plan]))
        roots = pt.roots
        stand = max(min(math.dist(v, r) for r in roots) for v in vs) / depth
        rep.worst["eye_stands"] = max(rep.worst.get("eye_stands", 0.0), stand)
        if stand > EYE_STANDS.get(plan, 0.5):
            fail("proportions", "%s stands %.2f of the head's depth off the skull, allowed %.2f" % (pt.id, stand, EYE_STANDS.get(plan, 0.5)))

    # --- complete: a part and its children go together
    kinds = {}
    for pt in fish.parts:
        kinds.setdefault(pt.kind, []).append(pt)
    for kind, need in ({} if "complete" in skip else KIND_NEEDS).items():
        if kind in kinds and need not in kinds:
            fail("complete", "%s without its %s" % (kind, need))

    # --- proportions
    for pt in [] if "proportions" in skip else fish.parts:
        vs = verts[pt.id]
        if pt.group:
            lim = REACH.get(pt.kind)
            rset = set(pt.roots)
            feet: dict = {}  # each free vertex (an apex) -> the roots of the faces it stands on
            for t in _tris(pt.mesh):
                for v in t:
                    if v not in rset:
                        feet.setdefault(v, set()).update(r for r in t if r in rset)
            reach = max((math.dist(v, mean(list(rs))) / L for v, rs in feet.items() if rs), default=0.0)
            rep.worst["reach_" + pt.kind] = max(rep.worst.get("reach_" + pt.kind, 0.0), reach)
            if lim is None or not lim[0] <= reach <= lim[1]:
                fail("proportions", "%s stands off %.3f L, allowed %s" % (pt.id, reach, lim))
            continue
        lo_p, hi_p = _bbox(vs)
        ext = max(hi_p[i] - lo_p[i] for i in range(3)) / L
        lim = EXTENT.get(pt.kind)
        if lim is None:
            fail("proportions", "unknown part kind %r" % pt.kind)
            continue
        rep.worst["ext_" + pt.kind] = max(rep.worst.get("ext_" + pt.kind, 0.0), ext)
        if not lim[0] <= ext <= lim[1]:
            fail("proportions", "%s is %.3f L long, allowed %.3f..%.3f" % (pt.id, ext, *lim))
        if pt.kind == "crest" and (hi_p[1] - hi[1]) / L > CREST_HEIGHT:
            fail("proportions", "%s rises %.3f L above the body" % (pt.id, (hi_p[1] - hi[1]) / L))
    if "proportions" not in skip and not 0.05 <= fish.genome["len_m"] <= 6.0:
        fail("proportions", "body length out of range")

    # --- silhouette
    if "silhouette" in skip:
        rep.ok = all(rep.checks.values())
        return rep
    everything = _bbox(allv)
    side_floor, top_floor = SILHOUETTE[plan]
    side = _coverage(skin_tris, everything, (2, 1))
    top_v = _coverage(skin_tris, everything, (2, 0))
    rep.worst["side_fill"], rep.worst["top_fill"] = side, top_v
    if side < side_floor or top_v < top_floor:
        fail("silhouette", "skin fills %.2f side / %.2f top of the fish, floors %.2f / %.2f" % (side, top_v, side_floor, top_floor))

    rep.ok = all(rep.checks.values())
    return rep
