"""Procedural motion from body plan and genes, and the validator's check at the extremes of it.

`bone_pose(rig, plan, t, ...)` is the pure runtime table (S3 ports it to TypeScript as `bonePose`): a body wave whose
amplitude ramps head to tail by plan (an eel's full-body undulation, a tuna's tail-only stroke, a flatfish's edge
ripple), tentacle chains that follow it as a spring chain with lag, jaw gape. `validate_motion` poses the fish at the
MAXIMUM of every channel (a wave at four phases, every tentacle at full curl each way, the jaw open) and re-runs the
checks that a bend can break: no NaN or flipped face, still one welded piece, nothing detached, nothing pierced into
the body, no tentacle through another.
"""

from __future__ import annotations

import copy
import math

from ..lift3d import Mesh
from . import rig as RG
from .surface import dot, sub
from .validate import validate


#: max yaw (radians) of the last spine bone, by plan; earlier bones ramp up to it
SPINE_AMP = {"round": 0.5, "flat": 0.3, "ribbon": 0.9, "eel": 1.0, "hammerhead": 0.5, "globe": 0.15, "disc": 0.25, "armoured": 0.3, "ray": 0.35, "seahorse": 0.1, "squid": 0.25}
RAMP = {"round": 1.8, "flat": 1.0, "ribbon": 1.3, "eel": 1.4, "hammerhead": 1.8, "globe": 1.5, "disc": 1.5, "armoured": 1.4, "ray": 1.0, "seahorse": 1.0, "squid": 1.0}
GAPE_MAX = 0.4  # radians the jaw opens beyond its rest
LAG = 0.35  # a tentacle joint follows its parent a third of a cycle late


def spine_angles(rig, plan, phase):
    n = len(rig.spine)
    out = {}
    for k, b in enumerate(rig.spine):
        u = k / max(1, n - 1)
        out[b] = SPINE_AMP[plan] * (0.04 + 0.96 * u ** RAMP[plan]) * math.sin(phase - 1.4 * u * math.pi)
    return out


def bone_pose(rig, plan, t, hz=1.0, gape=0.0):
    """Angles per bone at clock `t`: the spine wave, tentacle chains lagging it, the jaw."""
    phase = 2 * math.pi * hz * t
    out = spine_angles(rig, plan, phase)
    for b, bone in enumerate(rig.bones):
        if bone.kind == "tube":
            m = int(bone.name.rsplit(".", 1)[1])
            out[b] = bone.limit * 0.6 * math.sin(phase - LAG * 2 * math.pi * m) * (0.4 + 0.15 * m)
        elif bone.kind == "jaw":
            out[b] = gape
    return out


def rig_doc(rig, plan) -> dict:
    """The rig as the client reads it (`fish.json` `models[slug].rig`, the client's `rigOf`): per bone
    `[name, kind, ax, ay, az, limit]`: its glTF joint name, kind, the axis it bends about (rest frame, which is the
    joint's local frame: joints carry no rest rotation) and its joint limit; and the spine bones head first. `bone_pose`
    reads nothing else."""
    r4 = lambda x: round(x, 4) + 0.0  # noqa: E731  (4 places: platforms agree, as the manifest's dims do)
    return {
        "plan": plan,
        "spine": list(rig.spine),
        "bones": [[b.name, b.kind, *(r4(c) for c in b.axis), r4(b.limit)] for b in rig.bones],
    }


def pose_sets(rig, plan):
    """Every extreme worth checking: (name, angles)."""
    poses = [("rest", {})] + [("wave%d" % k, spine_angles(rig, plan, k * math.pi / 2)) for k in range(4)]
    tubes = {b: (bone.limit, bone.limit_neg) for b, bone in enumerate(rig.bones) if bone.kind == "tube"}
    jaws = [b for b, bone in enumerate(rig.bones) if bone.kind == "jaw"]
    for sign in (1, -1):
        a = spine_angles(rig, plan, math.pi / 2)
        a.update({b: (lim[0] if sign > 0 else -lim[1]) for b, lim in tubes.items()})
        poses.append(("curl%+d" % sign, a))
    if jaws:
        a = spine_angles(rig, plan, math.pi / 2)
        a.update({b: GAPE_MAX for b in jaws})
        a.update({b: lim[0] for b, lim in tubes.items()})
        poses.append(("gape", a))
    return poses


def posed_fish(fish, rig, angles):
    """A copy of the fish with every vertex (and every shared root) carried to its posed position."""
    f = RG.posed(rig, angles)
    out = copy.copy(fish)

    def move(m):
        n = Mesh()
        n.tris = {r: [tuple(f(p) for p in t) for t in ts] for r, ts in m.tris.items()}
        n.uvs = m.uvs
        return n

    out.skin = move(fish.skin)
    parts = []
    for pt in fish.parts:
        q = copy.copy(pt)
        q.mesh = move(pt.mesh)
        q.roots = [f(r) for r in pt.roots]
        q.edges = [(f(a), f(b)) for a, b in pt.edges]
        parts.append(q)
    out.parts = parts
    out._map = f
    return out


def _ring_r(ring, c):
    return sum(math.dist(v, c) for v in ring) / len(ring)


def validate_motion(fish, rig, rate=None) -> list:
    """-> notes (empty = the fish holds together at every extreme)."""
    plan = fish.genome["plan"]
    notes = []
    skip = frozenset({"silhouette", "proportions", "envelope", "complete"})
    for name, angles in pose_sets(rig, plan):
        pf = posed_fish(fish, rig, angles)
        rep = validate(pf, skip=skip)
        for n in rep.notes:
            notes.append("%s: %s" % (name, n))
        tubes = [p for p in pf.parts if "rings" in p.meta]
        f = pf._map
        for a in range(len(tubes)):
            for b in range(a + 1, len(tubes)):
                ra, rb = tubes[a].meta["rings"], tubes[b].meta["rings"]
                for i in range(1, len(ra)):
                    for j in range(1, len(rb)):
                        ca = tuple(sum(f(v)[k] for v in ra[i]) / 6 for k in range(3))
                        cb = tuple(sum(f(v)[k] for v in rb[j]) / 6 for k in range(3))
                        pa = [f(v) for v in ra[i]]
                        pb = [f(v) for v in rb[j]]
                        if math.dist(ca, cb) < 0.3 * (_ring_r(pa, ca) + _ring_r(pb, cb)):
                            notes.append("%s: %s and %s pass through each other" % (name, tubes[a].id, tubes[b].id))
                            break
                    else:
                        continue
                    break
    return notes
