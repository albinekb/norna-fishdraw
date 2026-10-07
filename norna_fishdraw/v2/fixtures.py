"""The known breaks, built on purpose: each takes a good fish and reproduces one failure the validator must reject.

The 2026-10-04 review list from the mockup sheets: the oarfish crest floating above the body,
the pelvics hanging loose, the angler's teeth floating in front of its head, its eye a cube punching through the skull;
and from the S1 sheet: a gold block poking out above an eye, a lure stalk without its bulb. Plus one per remaining
check, so no check is vacuous. Every fixture returns `(fish, checks that must fail)`.
"""

from __future__ import annotations

import copy
import math

from ..lift3d import Mesh
from .build import make
from .surface import add, mean, mul, sub



def _clone(fish):
    return copy.deepcopy(fish)


def _part(fish, ident):
    return next(p for p in fish.parts if p.id == ident)


def _good(species, seed):
    return _clone(make(species, seed, log=lambda *a: None))


def _moved(part, d):
    """Slide the whole part (roots included): it no longer shares its vertices with anything."""
    m = Mesh()
    for role, tris in part.mesh.tris.items():
        m.tris[role] = [tuple(add(p, d) for p in t) for t in tris]
    m.uvs = part.mesh.uvs
    part.mesh = m
    part.roots = [add(r, d) for r in part.roots]
    part.edges = [(add(a, d), add(b, d)) for a, b in part.edges]


def _moved_free(part, d):
    """Slide only the vertices the part does not share with its parent (a bad build: the roots stay welded)."""
    roots = set(part.roots)
    f = lambda p: p if p in roots else add(p, d)  # noqa: E731
    m = Mesh()
    for role, tris in part.mesh.tris.items():
        m.tris[role] = [tuple(f(p) for p in t) for t in tris]
    m.uvs = part.mesh.uvs
    part.mesh = m


def cube(c, half, role="iris") -> Mesh:
    """An axis-aligned box: the mockup's block eye."""
    m = Mesh()
    s = [(sx, sy, sz) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
    v = {k: add(c, mul(k, half)) for k in s}

    def quad(a, b, cc, d):
        m.add(role, v[a], v[b], v[cc], c)
        m.add(role, v[a], v[cc], v[d], c)

    quad((1, 1, 1), (1, -1, 1), (-1, -1, 1), (-1, 1, 1))
    quad((1, 1, -1), (-1, 1, -1), (-1, -1, -1), (1, -1, -1))
    quad((1, 1, 1), (1, 1, -1), (1, -1, -1), (1, -1, 1))
    quad((-1, 1, 1), (-1, -1, 1), (-1, -1, -1), (-1, 1, -1))
    quad((1, 1, 1), (-1, 1, 1), (-1, 1, -1), (1, 1, -1))
    quad((1, -1, 1), (1, -1, -1), (-1, -1, -1), (-1, -1, 1))
    return m


def floating_crest(seed=7):
    f = _good("oarfish", seed)
    _moved(_part(f, "crest"), (0.0, 0.12 * f.eff["len_m"], 0.0))  # the mockup's crest, lifted clear of the back
    return f, ("welded", "connected", "rooted")


def loose_pelvics(seed=3):
    f = _good("perch", seed)
    for t in ("l", "r"):
        _moved(_part(f, "pelvic." + t), (0.0, -0.1 * f.eff["len_m"], 0.0))  # hung below the belly on nothing
    return f, ("welded", "connected", "rooted")


def floating_teeth(seed=5):
    f = _good("angler", seed)
    for p in f.parts:
        if p.kind == "tooth":
            _moved(p, (0.0, 0.0, 0.08 * f.eff["len_m"]))  # the fence of teeth in front of the head, off its jaw
    return f, ("welded", "connected", "rooted")


def teeth_without_jaw(seed=5):
    f = _good("angler", seed)
    f.parts = [p for p in f.parts if p.kind != "jaw"]
    for p in f.parts:
        if p.kind == "tooth":
            p.parent = "skin"
            _moved(p, (0.0, 0.0, 0.05 * f.eff["len_m"]))
    return f, ("welded", "connected", "rooted")


def cube_eye(seed=5):
    f = _good("angler", seed)
    old = _part(f, "eye.l")
    c = mean(old.roots)
    r = 0.9 * math.dist(old.roots[0], c)
    old.mesh = cube(c, r, "iris")  # a block centred on the socket, sharing nothing with the skin
    return f, ("welded",)


def eye_through_skull(seed=5):
    f = _good("angler", seed)
    old = _part(f, "eye.l")
    c = mean(old.roots)
    inward = sub((0.0, c[1], c[2]), c)
    _moved_free(old, mul(inward, 1.6))  # the eyeball driven into the head: its free vertices go through to the far side
    return f, ("pierce", "envelope")


def eye_block_above_head(seed=10070):
    """S1's gold block: an eye whose free vertices stand clear above the head's own dorsal line."""
    f = _good("angler", seed)
    for tag in ("l", "r"):
        _moved_free(_part(f, "eye." + tag), (0.0, 0.14 * f.eff["len_m"], 0.0))
    return f, ("envelope", "proportions")


def stalk_without_bulb(seed=10070):
    f = _good("angler", seed)
    f.parts = [p for p in f.parts if p.kind != "bulb"]
    return f, ("complete",)


def near_miss_weld(seed=3):
    """A fin whose root vertex sits 5e-5 m beside the body vertex instead of on it: touching, but not welded."""
    f = _good("perch", seed)
    d = _part(f, "dorsal")
    a = d.roots[1]
    b = add(a, (5e-5, 0.0, 0.0))
    m = Mesh()
    m.tris = {role: [tuple(b if p == a else p for p in t) for t in tris] for role, tris in d.mesh.tris.items()}
    m.uvs = d.mesh.uvs
    d.mesh = m
    return f, ("welded",)


def nan_vertex(seed=3):
    f = _good("perch", seed)
    role = next(iter(f.skin.tris))
    a, b, c = f.skin.tris[role][0]
    f.skin.tris[role][0] = ((math.nan, a[1], a[2]), b, c)
    return f, ("mesh",)


def inward_face(seed=3):
    f = _good("perch", seed)
    a, b, c = f.skin.tris["flank"][40]
    f.skin.tris["flank"][40] = (a, c, b)  # one face wound the wrong way
    return f, ("mesh",)


def degenerate_face(seed=3):
    f = _good("perch", seed)
    a, b, c = f.skin.tris["flank"][40]
    f.skin.tris["flank"][40] = (a, b, b)
    return f, ("mesh",)


def giant_fin(seed=3):
    f = _good("perch", seed)
    d = _part(f, "tail")
    roots = set(d.roots)

    def grow(v):  # free vertices move six times as far from their nearest root
        if v in roots:
            return v
        r = min(d.roots, key=lambda q: (q[2] - v[2]) ** 2)
        return add(r, mul(tuple(v[i] - r[i] for i in range(3)), 6.0))

    m = Mesh()
    m.tris = {role: [tuple(grow(p) for p in t) for t in tris] for role, tris in d.mesh.tris.items()}
    m.uvs = d.mesh.uvs
    d.mesh = m  # the roots stay on the skin and the tail dwarfs the fish
    return f, ("proportions",)


FIXTURES = {
    "floating-crest": floating_crest,
    "loose-pelvics": loose_pelvics,
    "floating-teeth": floating_teeth,
    "teeth-without-jaw": teeth_without_jaw,
    "cube-eye": cube_eye,
    "eye-through-skull": eye_through_skull,
    "eye-block-above-head": eye_block_above_head,
    "stalk-without-bulb": stalk_without_bulb,
    "near-miss-weld": near_miss_weld,
    "nan-vertex": nan_vertex,
    "inward-face": inward_face,
    "degenerate-face": degenerate_face,
    "giant-tail": giant_fin,
}
