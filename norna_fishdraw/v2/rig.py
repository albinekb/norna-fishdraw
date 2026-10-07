"""The skeleton for free: spine bones along the rings, a jaw bone on its hinge, a bone chain down every tentacle.

Each body vertex is weighted to its two nearest spine bones by ring index; because every part is welded to the body, a
root vertex carries exactly the body's weights and the part cannot tear off. Fins, eyes, spikes take the weights of the
nearest root vertex; the jaw's free vertices and its teeth follow the jaw bone; tube ring m follows bone m of its chain.
Weights are keyed by vertex tuple, so a shared vertex has one weight set wherever it is read.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .surface import add, cross, dot, mul, norm, sub



TUBE_LIMIT = {"barbel": 0.15, "stalk": 0.45, "tentacle": 0.12, "arm": 0.15}  # max bend per joint toward the tube's bend direction
TUBE_LIMIT_NEG = {"barbel": 0.08, "stalk": 0.45, "tentacle": 0.05, "arm": 0.05}  # and the other way: tentacles may not fold through each other


@dataclass
class Bone:
    name: str
    parent: int
    pos: tuple  # rest position, world
    kind: str  # spine | jaw | tube
    axis: tuple = (0.0, 1.0, 0.0)  # the axis it bends about
    group: str = ""  # the part it belongs to
    limit: float = 0.0  # how far a joint may bend toward its bend direction, radians (tubes)
    limit_neg: float = 0.0  # and the other way


@dataclass
class Rig:
    bones: list = field(default_factory=list)
    weights: dict = field(default_factory=dict)  # vertex tuple -> [(bone, weight)]
    spine: list = field(default_factory=list)  # bone indices of the spine, head first


def _nearest(v, roots, table):
    best = min(roots, key=lambda r: (r[0] - v[0]) ** 2 + (r[1] - v[1]) ** 2 + (r[2] - v[2]) ** 2)
    return table[best]


def build_rig(fish) -> Rig:
    grid = fish.grid
    R = grid.R
    rig = Rig()
    wave_axis = (1.0, 0.0, 0.0) if fish.genome["plan"] in ("flat", "ray", "seahorse") else (0.0, 1.0, 0.0)  # up-and-down ripple for discs, side to side for the rest
    nb = 9 if R >= 18 else 7
    idxs = []
    for k in range(nb):
        i = min(range(R), key=lambda r: abs(grid.rings[r].s - k / (nb - 1)))  # evenly along the spine, not along the rings
        if not idxs or i > idxs[-1]:
            idxs.append(i)
    if idxs[-1] != R - 1:
        idxs.append(R - 1)
    for k, i in enumerate(idxs):
        rig.spine.append(len(rig.bones))
        rig.bones.append(Bone("spine%d" % k, rig.spine[k - 1] if k else -1, grid.rings[i].centre, "spine", wave_axis, "spine"))
    w: dict = {}

    def ring_weights(i):
        for k in range(len(idxs) - 1):
            if idxs[k] <= i <= idxs[k + 1]:
                t = (i - idxs[k]) / (idxs[k + 1] - idxs[k])  # ring index blend: rings are denser at the head, so bones are chosen by s
                return [(rig.spine[k], 1 - t), (rig.spine[k + 1], t)] if 0 < t < 1 else [(rig.spine[k] if t == 0 else rig.spine[k + 1], 1.0)]
        return [(rig.spine[-1], 1.0)]

    def spine_near(i):
        return max(k for k in range(len(idxs)) if idxs[k] <= i)

    for i in range(R):
        rw = ring_weights(i)
        for j in range(grid.K):
            w[grid.V[i][j]] = rw
    w[grid.nose] = [(rig.spine[0], 1.0)]
    w[grid.tail] = [(rig.spine[-1], 1.0)]
    for pt in fish.parts:
        if pt.meta.get("hinge") is not None:  # the jaw: a bone on the hinge, child of the spine bone at its ring
            b = len(rig.bones)
            f_ = cross(pt.meta["dir"], pt.meta["axis"])  # forward along the jaw
            sign = 1.0 if dot(cross(pt.meta["axis"], f_), pt.meta["dir"]) > 0 else -1.0  # so a positive angle opens it
            rig.bones.append(Bone("jaw", rig.spine[0], pt.meta["hinge"], "jaw", mul(pt.meta["axis"], sign), pt.id))
            pt.meta["bone"] = b
            for v in pt.verts():
                if v not in w:
                    w[v] = [(b, 1.0)]
        elif "rings" in pt.meta:  # a tube: bone m at ring m's centre, chained to the spine bone at its root ring
            rings, centres = pt.meta["rings"], pt.meta["centres"]
            parent = rig.spine[spine_near(pt.meta["root"][0])]
            ids = []
            for m in range(1, len(rings)):
                b = len(rig.bones)
                rig.bones.append(Bone("%s.%d" % (pt.id, m), parent, centres[m], "tube", pt.meta["axis"], pt.id, TUBE_LIMIT.get(pt.kind, 0.3), TUBE_LIMIT_NEG.get(pt.kind, 0.1)))
                ids.append(b)
                parent = b
                for v in rings[m]:
                    w.setdefault(v, [(b, 1.0)])
            pt.meta["bones"] = ids
            for v in pt.verts():
                if v not in w:
                    w[v] = [(ids[-1], 1.0)]
    for pt in fish.parts:
        if pt.meta.get("of"):  # a bulb follows the last bone of its stalk
            last = next(q for q in fish.parts if q.id == pt.meta["of"]).meta["bones"][-1]
            for v in pt.verts():
                w.setdefault(v, [(last, 1.0)])
    # everything else (fins, eyes, bumps, tail) takes the weights of its nearest root
    for pt in fish.parts:
        free = [v for v in pt.verts() if v not in w]
        if not free:
            continue
        roots = [r for r in pt.roots if r in w]
        if not roots:
            roots = list(w)
        for v in free:
            w[v] = _nearest(v, roots, w)
    rig.weights = w
    return rig


# ----------------------------------------------------------------------------------------------------- posing
def _rot(axis, ang):
    a = norm(axis)
    c, s = math.cos(ang), math.sin(ang)
    x, y, z = a
    return ((c + x * x * (1 - c), x * y * (1 - c) - z * s, x * z * (1 - c) + y * s),
            (y * x * (1 - c) + z * s, c + y * y * (1 - c), y * z * (1 - c) - x * s),
            (z * x * (1 - c) - y * s, z * y * (1 - c) + x * s, c + z * z * (1 - c)))


def _mm(a, b):
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)) for i in range(3))


def _mv(m, v):
    return (m[0][0] * v[0] + m[0][1] * v[1] + m[0][2] * v[2], m[1][0] * v[0] + m[1][1] * v[1] + m[1][2] * v[2], m[2][0] * v[0] + m[2][1] * v[1] + m[2][2] * v[2])


def skin_matrices(rig: Rig, angles: dict):
    """Per bone: (R, t) with posed = R (v - rest) + t_world; `angles` maps bone index -> radians about that bone's axis."""
    world = []
    for b, bone in enumerate(rig.bones):
        rl = _rot(bone.axis, angles.get(b, 0.0))
        if bone.parent < 0:
            world.append((rl, bone.pos))
        else:
            rp, tp = world[bone.parent]
            pp = rig.bones[bone.parent].pos
            # the bone's joint sits at its rest offset from the parent's joint, carried by the parent's pose
            t = add(tp, _mv(rp, sub(bone.pos, pp)))
            world.append((_mm(rp, rl), t))
    return world


def posed(rig: Rig, angles: dict):
    """-> function mapping a rest vertex tuple to its posed position (linear blend skinning), cached."""
    world = skin_matrices(rig, angles)
    cache: dict = {}

    def f(v):
        if v not in cache:
            out = (0.0, 0.0, 0.0)
            for b, wt in rig.weights.get(v, ()):
                r, t = world[b]
                out = add(out, mul(add(_mv(r, sub(v, rig.bones[b].pos)), t), wt))
            cache[v] = out
        return cache[v]

    return f
