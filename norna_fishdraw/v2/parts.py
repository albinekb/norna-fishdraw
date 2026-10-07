"""The kit: fins with rays, sockets with eyeballs, a lower jaw with teeth on its rim, tubes (tentacles, whiskers, a lure
stalk and bulb), bumps (spikes, scutes, warts). Every part is built FROM the body's own vertices.

Welded by construction: a part's root is a chain of the body lattice's exact vertex tuples (`Grid.v(i, j)`), its first
faces use those same tuples, and every root edge is an edge of the body mesh. Nothing is placed beside the skin and
stitched afterwards. `Part.roots` / `Part.edges` record what was shared so the validator can check the claim.

Sizes are fractions of the local body radius at the root (`Ring.r`), never world lengths, so gigantism scales the
body and the parts follow.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..lift3d import Mesh
from .surface import Grid, add, cross, dot, lerp, mean, mid, mul, norm, sub


UP = (0.0, 1.0, 0.0)


@dataclass
class Part:
    id: str
    kind: str
    mesh: Mesh
    roots: list  # vertex tuples shared with the parent (the body, or another part)
    edges: list  # (a, b) pairs of those: each must be an edge of the parent's mesh
    parent: str = "skin"
    group: bool = False  # many bumps in one part: measured by reach, not by bounding box
    meta: dict = field(default_factory=dict)  # builder notes for the rig (hinge, tube rings), never trusted by the validator

    def verts(self):
        seen: dict = {}
        for tris in self.mesh.tris.values():
            for t in tris:
                for p in t:
                    seen[p] = None
        return list(seen)


def _edges(chain, closed=False):
    e = [(chain[k], chain[k + 1]) for k in range(len(chain) - 1)]
    if closed:
        e.append((chain[-1], chain[0]))
    return e


def rot(v, axis, ang):
    """Rodrigues rotation of v about unit `axis` by `ang`."""
    c, s = math.cos(ang), math.sin(ang)
    return add(add(mul(v, c), mul(cross(axis, v), s)), mul(axis, dot(axis, v) * (1 - c)))


def _basis(n):
    n = norm(n)
    e1 = norm(cross(n, UP if abs(n[1]) < 0.9 else (1.0, 0.0, 0.0)))
    return e1, cross(n, e1)


# ----------------------------------------------------------------------------------------------------- eyes
def eye(grid: Grid, ident: str, ij, size: float, bulge: float) -> Part:
    """An eyeball seated in the socket the loft left: a dome whose base ring IS the socket's rim of body vertices.

    The visible eye has radius `size` x the local body radius (clamped to the socket). The rim up to it is eyelid skin on
    a low shelf; the eyeball above is rings of twelve on a circle (so it reads round, not hexagonal) in sclera, iris with
    one face lit as the highlight, and pupil. `bulge` flattens or raises the eyeball over the shelf.
    """
    i, j = ij
    rim = grid.rim(i, j)
    c = mean(rim)
    a = grid.n(i, j)
    rho = sum(math.dist(p, c) for p in rim) / 6
    e_r = size * grid.rings[i].r
    f1 = min(0.92, max(0.2, e_r / rho))
    lid_h = 0.12 * rho + 0.35 * bulge * f1 * rho  # a low shelf, so the circle never dips under a curving body
    eb = bulge * f1 * rho
    e1, e2 = _basis(a)
    out = sub(c, mul(a, 0.8 * rho))
    # the rim's angular position round the axis, so ring points line up with the body vertices they sit above
    ang = [math.atan2(dot(sub(p, c), e2), dot(sub(p, c), e1)) for p in rim]
    base = ang[0]

    def ring(f, h):
        return [add(add(c, mul(add(mul(e1, math.cos(base + k * math.pi / 6)), mul(e2, math.sin(base + k * math.pi / 6))), f * rho)), mul(a, h)) for k in range(12)]

    r1 = ring(f1, lid_h)
    r2 = ring(0.87 * f1, lid_h + 0.49 * eb)
    r3 = ring(0.6 * f1, lid_h + 0.8 * eb)
    apex = add(c, mul(a, lid_h + eb))
    m = Mesh()
    # lid: three faces per rim edge, from the hexagon of body vertices up to the circle
    for k in range(6):
        k1 = (k + 1) % 6
        p, mi, q = r1[2 * k], r1[2 * k + 1], r1[(2 * k + 2) % 12]
        m.add("lid", rim[k], rim[k1], mi, out)
        m.add("lid", rim[k], mi, p, out)
        m.add("lid", rim[k1], q, mi, out)
    for k in range(12):
        k1 = (k + 1) % 12
        for (lo, hi, role) in ((r1, r2, "sclera"), (r2, r3, "glint" if k == 2 else "iris")):
            m.add(role, lo[k], lo[k1], hi[k1], out)
            m.add(role if role != "glint" else "iris", lo[k], hi[k1], hi[k], out)
        m.add("pupil", r3[k], r3[k1], apex, out)
    return Part(ident, "eye", m, list(rim), _edges(rim, True))


# ----------------------------------------------------------------------------------------------------- fins
def fin(grid: Grid, ident: str, kind: str, chain, height: float, dirw, *, profile=None, membrane=0.55, ripple=0.06, wave=None, ext=None, unit=None) -> Part:
    """A fin on a chain of body vertices: rays (tips) with scalloped membrane between, rippled so the rays read as ridges.

    `height` is a fraction of each root's local body radius (or of `unit` metres). `dirw` = (kn, kb, ky) mixes the root's
    normal, the way back along the body and world up. `wave` = (waves, amplitude) ripples the whole fin along its length;
    `ext` lengthens named rays (filament streamers); `membrane` is the notch height between rays (1 = flat edge).
    """
    kn, kb, ky = dirw
    n = len(chain)
    body_len = abs(grid.rings[0].cz - grid.rings[-1].cz) or 1.0
    P = [grid.v(*ij) for ij in chain]
    D, S, H = [], [], []
    for k, (i, j) in enumerate(chain):
        nrm = grid.n(i, j)
        tan = norm(sub(grid.v(min(i + 1, grid.R - 1), j), grid.v(max(i - 1, 0), j)))
        d = norm(add(add(mul(nrm, kn), mul(tan, kb)), mul(UP, ky)))
        D.append(d)
        S.append(norm(cross(d, tan)))
        u = k / max(1, n - 1)
        base = unit if unit is not None else grid.rings[i].r
        h = max(height * base * (profile(u) if profile else 1.0) * ((ext or {}).get(k, 1.0)), 0.006 * body_len)
        H.append(h)
    rip = [(ripple * H[k] * (1 if k % 2 == 0 else -1)) for k in range(n)]
    if wave:
        for k in range(n):
            rip[k] += wave[1] * H[k] * math.sin(2 * math.pi * wave[0] * k / max(1, n - 1))
    Q = [add(add(P[k], mul(D[k], H[k])), mul(S[k], rip[k])) for k in range(n)]
    m = Mesh()
    uv = lambda k, v: (k / max(1, n - 1), v)  # noqa: E731
    for k in range(n - 1):
        if membrane >= 0.999:
            m.add("fin", P[k], P[k + 1], Q[k + 1], uv=(uv(k, 0.0), uv(k + 1, 0.0), uv(k + 1, 1.0)))
            m.add("fin", P[k], Q[k + 1], Q[k], uv=(uv(k, 0.0), uv(k + 1, 1.0), uv(k, 1.0)))
            continue
        hm = 0.5 * (H[k] + H[k + 1]) * membrane
        N = add(add(mid(P[k], P[k + 1]), mul(norm(add(D[k], D[k + 1])), hm)), mul(S[k], -0.5 * (rip[k] + rip[k + 1])))
        um = (k + 0.5) / max(1, n - 1)
        m.add("fin", P[k], P[k + 1], N, uv=(uv(k, 0.0), uv(k + 1, 0.0), (um, membrane)))
        m.add("fin", P[k], N, Q[k], uv=(uv(k, 0.0), (um, membrane), uv(k, 1.0)))
        m.add("fin", P[k + 1], Q[k + 1], N, uv=(uv(k + 1, 0.0), uv(k + 1, 1.0), (um, membrane)))
    return Part(ident, kind, m, list(P), _edges(P))


def tail(grid: Grid, ident: str, ja: int, jb: int, length: float, lobe: float, fork: float, shape: str = "forked", streamer: float = 0.0) -> Part:
    """A caudal fan on the last ring: roots are two opposite ring vertices and the cap centre, five rays between.

    `length` and `lobe` are fractions of the body's deepest radius. Shapes: forked, rounded, lunate (swept lobes),
    truncate. `streamer` stretches the outer rays into filaments.
    """
    last = grid.R - 1
    A, B, C = grid.v(last, ja), grid.v(last, jb), grid.tail
    Rm = max(r.r for r in grid.rings)
    back = norm(sub(grid.rings[last].centre, grid.rings[last - 1].centre))
    axis = norm(sub(A, B))
    ln, lb = length * Rm, lobe * Rm
    # five rays across the span: outer lobes, shoulders, centre
    fr = (1.0, 0.5, 0.0, -0.5, -1.0)
    lens = {"forked": (1.0, 0.82, 1.0 - fork, 0.82, 1.0), "rounded": (0.78, 0.96, 1.0, 0.96, 0.78), "lunate": (1.05, 0.7, 0.55, 0.7, 1.05), "truncate": (0.92, 0.96, 0.98, 0.96, 0.92)}[shape]
    sweep = {"lunate": 0.35}.get(shape, 0.0)
    tips = []
    for k in range(5):
        ext = 1.0 + (streamer if k in (0, 4) else 0.0)
        base = [A, C, B][k // 2] if k % 2 == 0 else mid([A, C, B][k // 2], [A, C, B][k // 2 + 1])
        spread = mul(axis, fr[k] * lb * (1 + 0.15 * abs(fr[k])))
        tips.append(add(add(base, mul(back, ln * lens[k] * ext)), add(spread, mul(back, sweep * abs(fr[k]) * ln))))
    m = Mesh()
    # fan: upper half from A and C, lower from B and C
    m.add("fin", A, tips[0], tips[1], uv=((0.0, 0.0), (0.0, 1.0), (0.25, 1.0)))
    m.add("fin", A, tips[1], C, uv=((0.0, 0.0), (0.25, 1.0), (0.5, 0.0)))
    m.add("fin", C, tips[1], tips[2], uv=((0.5, 0.0), (0.25, 1.0), (0.5, 1.0)))
    m.add("fin", C, tips[2], tips[3], uv=((0.5, 0.0), (0.5, 1.0), (0.75, 1.0)))
    m.add("fin", C, tips[3], B, uv=((0.5, 0.0), (0.75, 1.0), (1.0, 0.0)))
    m.add("fin", B, tips[3], tips[4], uv=((1.0, 0.0), (0.75, 1.0), (1.0, 1.0)))
    return Part(ident, "tail", m, [A, C, B], [(A, C), (C, B)])


def finlets(grid: Grid, ident: str, ring_range, j: int, height: float) -> Part:
    """A row of small single-ray finlets along a chain: one welded triangle per body edge."""
    P = [grid.v(i, j) for i in ring_range]
    m = Mesh()
    for k in range(len(P) - 1):
        i = ring_range[k]
        nrm = norm(add(grid.n(i, j), grid.n(i + 1, j)))
        tan = norm(sub(P[k + 1], P[k]))
        tip = add(add(mid(P[k], P[k + 1]), mul(nrm, height * grid.rings[i].r)), mul(tan, 0.5 * height * grid.rings[i].r))
        m.add("fin", P[k], P[k + 1], tip, uv=((0.0, 0.0), (1.0, 0.0), (0.5, 1.0)))
    return Part(ident, "finlet", m, list(P), _edges(P), group=True)


# ----------------------------------------------------------------------------------------------------- jaw
def _clear_of_body(grid: Grid, p, away, i_b: int):
    """Nudge a free vertex off any body vertex it nearly lands on (a coincidence reads as a botched weld): the check
    for a near miss cannot tell a hair's gap from a bad join, so the builder never leaves one."""
    h = 0.0006 * abs(grid.rings[0].cz - grid.rings[-1].cz)
    for i in range(max(0, i_b - 4), min(grid.R, i_b + 2)):
        for q in grid.V[i]:
            if math.dist(p, q) < h:
                return add(p, mul(away, 2 * h))
    return p


def jaw(grid: Grid, ident: str, i_b: int, js, proj: float, drop: float, gape: float, slope: float, teeth: int, tooth: float):
    """A lower (or, with `js` over the back, an upturned) jaw lofted forward from a chain of five body vertices.

    Station 0 IS the body chain; the trough floor and inner lip collapse onto it there, so the jaw grows out of the
    skin. Out front it tapers, hangs `drop` x local radius, and opens `gape` degrees about the hinge. Each side's lip is
    a rim: teeth are pyramids whose bases are lip faces, so they share the jaw's own vertices. -> [jaw part, teeth parts].
    """
    B = [grid.v(i_b, j) for j in js]
    ring = grid.rings[i_b]
    H = B[2]
    r_b = ring.r
    rad = grid.radial(i_b, js[2])  # out of the body at the keel: down for an underslung jaw
    f = norm(sub(grid.rings[max(i_b - 1, 0)].centre, ring.centre))
    ex = norm(cross(f, rad))
    Lj = dot(sub(grid.nose, ring.centre), f) + proj * r_b
    D = drop * r_b
    M = 5
    g = math.radians(gape)

    def local(p):
        d = sub(p, H)
        return dot(d, ex), dot(d, rad)

    cs = [local(p) for p in B]
    stations = [B]
    inner0 = [B[3], B[2], B[1]]
    loops = [[B[0], B[1], B[2], B[3], B[4], inner0[0], inner0[1], inner0[2]]]
    for k in range(1, M + 1):
        t = k / M
        wt = 1.0 - 0.72 * t**1.8
        dt = 1.0 - 0.55 * t**1.5
        pts = []
        for lat, rd in cs:
            a = Lj * t - slope * Lj * t * 0.0
            b = rd * dt + D * t - slope * Lj * t
            # rotate the (forward a, outward b) pair about the hinge by the gape: the front swings outward
            a2, b2 = a * math.cos(g) - b * math.sin(g), a * math.sin(g) + b * math.cos(g)
            pts.append(add(add(add(H, mul(f, a2)), mul(ex, lat * wt)), mul(rad, b2)))
        lip_m = mid(pts[0], pts[4])
        inr = add(add(pts[4], mul(sub(lip_m, pts[4]), 0.42)), mul(rad, 0.08 * D))
        inl = add(add(pts[0], mul(sub(lip_m, pts[0]), 0.42)), mul(rad, 0.08 * D))
        floor = add(lip_m, mul(sub(pts[2], lip_m), 0.5))
        loops.append([_clear_of_body(grid, p, rad, i_b) for p in (pts[0], pts[1], pts[2], pts[3], pts[4], inr, floor, inl)])
    m = Mesh()
    inside = lambda k: add(mid(loops[k][0], loops[k][4]), mul(rad, 0.15 * D))  # noqa: E731
    shell_role = {0: "jaw", 1: "jaw", 2: "jaw", 3: "jaw", 4: "jaw", 7: "jaw", 5: "mouth", 6: "mouth"}
    up = mul(rad, -1.0)

    def face(role, a, b, c, c_idx, k):
        if c_idx <= 3:
            m.add(role, a, b, c, out=inside(k))
        else:  # lip tops and the trough face the body side
            n = cross(sub(b, a), sub(c, a))
            if dot(n, up) < 0:
                b, c = c, b
            m.add(role, a, b, c)

    lip_faces: dict = {}
    for k in range(M):
        for ci in range(8):
            c1 = (ci + 1) % 8
            a, b, c, d = loops[k][ci], loops[k][c1], loops[k + 1][c1], loops[k + 1][ci]
            role = shell_role[ci]
            face(role, a, b, c, ci, k)
            face(role, a, c, d, ci, k)
            if ci in (4, 7):
                lip_faces[(ci, k)] = (a, b, c, d)
    # front cap
    fc = mean(loops[M])
    for ci in range(8):
        a, b = loops[M][ci], loops[M][(ci + 1) % 8]
        m.add("jaw", fc, a, b, out=mid(inside(M), inside(M - 1)))
    jp = Part(ident, "jaw", m, list(B), _edges(B), meta={"hinge": H, "axis": ex, "dir": rad, "ring": i_b})
    out = [jp]
    # teeth: lip faces from the front, alternating sides, never the hinge segment
    slots = [(c, k) for k in range(M - 1, 0, -1) for c in (7, 4)]
    for n_t, (ci, k) in enumerate(slots[: max(0, min(teeth, len(slots)))]):
        a, b, c, d = lip_faces[(ci, k)]
        base = (a, b, c) if ci == 7 else (a, d, c)
        cen = mean(base)
        n = norm(cross(sub(base[1], base[0]), sub(base[2], base[0])))
        if dot(n, up) < 0:
            n = mul(n, -1.0)
        apex = add(add(cen, mul(n, tooth * r_b)), mul(f, 0.35 * tooth * r_b))
        tm = Mesh()
        ref = add(cen, mul(n, -0.5 * tooth * r_b))
        for p, q in ((base[0], base[1]), (base[1], base[2]), (base[2], base[0])):
            tm.add("tooth", p, q, apex, out=ref)
        out.append(Part("%s.tooth%d" % (ident, n_t), "tooth", tm, list(base), _edges(list(base), True), parent=ident))
    return out


# ----------------------------------------------------------------------------------------------------- tubes
def tube(grid: Grid, ident: str, kind: str, ij, length: float, tip: float, *, curl=0.0, plane=0.0, lean=0.0, lean_dir=(0.0, 0.0, 1.0), bend_to=None, segs=4, club=0.0, suckers=0.0, sucker_h=0.18, role="arm", collar=0.65, unit=None, bulb_role="bulb"):
    """A sub-spine rooted on a socket: rings of six, the first IS the hexagon of body vertices around a removed vertex.

    `length` is a fraction of the body's local radius at the root (or of `unit`); the radius tapers from the rim to `tip`
    x the rim; `curl` radians bend the path over its length in a plane turned `plane` radians about the root normal; a
    `club` fraction of the rim radius ends it in a bulb (returned as its own welded part); suckers are small cones on one
    side. -> [tube part] or [tube part, bulb part].
    """
    i, j = ij
    rim = grid.rim(i, j)
    c0 = mean(rim)
    a0 = grid.n(i, j)
    rho = sum(math.dist(p, c0) for p in rim) / 6
    Lm = length * (unit if unit is not None else grid.rings[i].r)
    d0 = norm(add(a0, mul(lean_dir, lean)))
    # curl plane: a fixed axis perpendicular to the first direction
    ref = norm(cross(d0, UP if abs(d0[1]) < 0.9 else (1.0, 0.0, 0.0)))
    axis = norm(cross(d0, bend_to)) if bend_to is not None else rot(ref, d0, plane)
    offs = [sub(p, c0) for p in rim]
    seg = Lm / segs
    rings = [list(rim)]
    centres = [c0]
    dirs = [d0]
    c, d = c0, d0
    for m_ in range(1, segs + 1):
        step = seg * (0.6 if m_ == 1 else 1.0)
        c = add(c, mul(d, step))
        d = norm(rot(d, axis, curl / segs))
        scale = collar if m_ == 1 else collar * (tip / collar) ** ((m_ - 1) / max(1, segs - 1))
        # carry the rim's offsets along: rotate the base frame a0 -> d about their common perpendicular
        ax = cross(a0, d)
        ang = math.atan2(math.sqrt(dot(ax, ax)), dot(a0, d))
        carried = [mul(rot(o, norm(ax), ang), scale) if dot(ax, ax) > 1e-12 else mul(o, scale) for o in offs]
        rings.append([add(c, o) for o in carried])
        centres.append(c)
        dirs.append(d)
    m = Mesh()
    inward = norm(sub(c0, grid.rings[i].centre))
    inward = mul(inward, -1.0)  # toward the body axis: the side suckers face
    sucker_cells = set()
    if suckers > 0:
        for m_ in range(1, segs):
            if math.floor((m_ + 1) * suckers) > math.floor(m_ * suckers):
                ku = max(range(6), key=lambda k: dot(sub(rings[m_][k], centres[m_]), inward))
                sucker_cells.add((m_, ku))
    for m_ in range(segs):
        out_ref = mid(centres[m_], centres[m_ + 1])
        for k in range(6):
            k1 = (k + 1) % 6
            a, b, c2, d2 = rings[m_][k], rings[m_][k1], rings[m_ + 1][k1], rings[m_ + 1][k]
            if (m_, k) in sucker_cells:
                ctr = mean([a, b, c2, d2])
                nrm = norm(sub(ctr, out_ref))
                apex = add(ctr, mul(nrm, sucker_h * rho * (tip + (1 - tip) * (1 - m_ / segs))))
                for p, q in ((a, b), (b, c2), (c2, d2), (d2, a)):
                    m.add("sucker", p, q, apex, out=out_ref)
                continue
            m.add(role, a, b, c2, out=out_ref)
            m.add(role, a, c2, d2, out=out_ref)
    tip_ring = rings[segs]
    parts = []
    if club >= 0.15:  # smaller is no club at all, never a sliver of one
        bm = Mesh()
        rb = club * rho
        d = dirs[segs]
        ax = cross(a0, d)
        ang = math.atan2(math.sqrt(dot(ax, ax)), dot(a0, d))
        offd = [rot(o, norm(ax), ang) if dot(ax, ax) > 1e-12 else o for o in offs]
        # a ball in three rings (bulging out, widest, closing in) between the stalk's last ring and an apex
        stages = ((0.5, 0.8), (1.1, 1.0), (1.8, 0.75))
        prev = list(tip_ring)
        ce = centres[segs]
        for dist, rad in stages:
            ce = add(centres[segs], mul(d, dist * rb))
            cur = [add(ce, mul(o, rad * rb / rho)) for o in offd]
            for k in range(6):
                k1 = (k + 1) % 6
                bm.add(bulb_role, prev[k], prev[k1], cur[k1], out=ce)
                bm.add(bulb_role, prev[k], cur[k1], cur[k], out=ce)
            prev = cur
        apex = add(centres[segs], mul(d, 2.2 * rb))
        for k in range(6):
            bm.add(bulb_role, prev[k], prev[(k + 1) % 6], apex, out=ce)
        tp = Part(ident, kind, m, list(rim), _edges(rim, True), meta={"rings": rings, "centres": centres, "axis": axis, "root": (i, j)})
        bp = Part(ident + ".bulb", "bulb", bm, list(tip_ring), _edges(tip_ring, True), parent=ident, meta={"of": ident})
        return [tp, bp]
    apex = add(centres[segs], mul(dirs[segs], 0.7 * seg))
    for k in range(6):
        m.add(role, tip_ring[k], tip_ring[(k + 1) % 6], apex, out=centres[segs])
    return [Part(ident, kind, m, list(rim), _edges(rim, True), meta={"rings": rings, "centres": centres, "axis": axis, "root": (i, j)})]


# ----------------------------------------------------------------------------------------------------- bumps
def bumps(grid: Grid, ident: str, kind: str, cells, height: float, role: str) -> Part:
    """Spikes, scutes or warts: each replaces one body cell by a pyramid on that cell's own four vertices."""
    m = Mesh()
    roots, edges = [], []
    for (i, j) in cells:
        j1 = (j + 1) % grid.K
        q = [grid.v(i, j), grid.v(i, j1), grid.v(i + 1, j1), grid.v(i + 1, j)]
        ctr = mean(q)
        nrm = norm(add(add(grid.n(i, j), grid.n(i, j1)), add(grid.n(i + 1, j1), grid.n(i + 1, j))))
        apex = add(ctr, mul(nrm, height * grid.rings[i].r))
        perim = q[::-1] if getattr(grid, "flip", False) else q  # the lattice's own winding: each root edge is the neighbour's, reversed
        for k in range(4):
            m.add(role, perim[k], perim[(k + 1) % 4], apex)
        roots.extend(q)
        edges.extend(_edges(q, True))
    return Part(ident, kind, m, roots, edges, group=True)
