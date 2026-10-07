"""The vector files: (species, seed, gifts) -> genome, final strength and a hash of the mesh; and the motion pin.

    python3 norna_fishdraw/v2/vectors.py --write          # regenerate vectors.json (a deliberate act: it is the pin)
    python3 norna_fishdraw/v2/vectors.py --write-motion   # regenerate motion-vectors.json (the same, for bonePose)

Python and the later TypeScript port both read `vectors.json`, so the two implementations cannot drift apart unseen.
Coordinates are rounded to 1e-4 m with -0.0 folded to 0.0 before hashing, as `glb_writer` does for its freshness test.

`motion-vectors.json` pins the swim: per game slug its rig as the client reads it (`motion.rig_doc`, what `fish.json`
carries) and `motion.bone_pose` at a few clocks, rates and gapes. The game client's TypeScript port (`motion.ts`
`bonePose`, its test `motion.test.ts`) reads the same file.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from norna_fishdraw.v2 import genome as G  # noqa: E402
from norna_fishdraw.v2 import motion as MO  # noqa: E402
from norna_fishdraw.v2 import rig as RG  # noqa: E402
from norna_fishdraw.v2.build import make, make_from  # noqa: E402


HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(HERE, "vectors.json")
MOTION_PATH = os.path.join(HERE, "motion-vectors.json")

CASES = [(sp, seed, []) for sp in sorted(G.SPECIES) for seed in (1, 2)] + [
    ("angler", 77, ["fanged", "lure"]),
    ("oarfish", 78, ["spined"]),
    ("hammerhead", 79, ["bigeye", "winged"]),
    ("plaice", 80, ["cyclops"]),
]


def mesh_hash(mesh) -> str:
    h = hashlib.sha256()
    for role in sorted(mesh.tris):
        h.update(role.encode())
        for t in mesh.tris[role]:
            for p in t:
                h.update(",".join("%.4f" % (round(c, 4) + 0.0) for c in p).encode() + b";")
    return h.hexdigest()


def vector(species: str, seed: int, gifts) -> dict:
    g = G.draw(species, seed, gifts)
    fish = make_from(g, log=lambda *a: None)
    return {"species": species, "seed": seed, "gifts": list(gifts), "genome": g, "strength": fish.strength, "tris": sum(len(t) for t in fish.mesh().tris.values()), "hash": mesh_hash(fish.mesh())}


def compute() -> list:
    return [vector(*c) for c in CASES]


#: a slug per motion shape: a round fish with a jaw and a chin barbel, an eel, the angler's lure stalk, the flatfish's
#: up-and-down ripple, the hammerhead, the ribbon
MOTION_SLUGS = ("grey-cod", "mottled-eel", "fathom-cod", "silt-flounder", "hammer-shark", "soulfish")
#: (t seconds, hz, gape radians)
MOTION_SAMPLES = ((0.0, 1.0, 0.0), (0.13, 1.0, 0.0), (0.37, 2.5, 0.2), (0.71, 0.6, 0.0), (1.9, 3.2, 0.4))


def motion_vector(slug: str) -> dict:
    from norna_fishdraw.v2 import game

    fish = make(slug, game.CANON[slug], log=lambda *a: None)
    rig = RG.build_rig(fish)
    plan = fish.genome["plan"]
    poses = []
    for t, hz, gape in MOTION_SAMPLES:
        a = MO.bone_pose(rig, plan, t, hz, gape)
        poses.append({"t": t, "hz": hz, "gape": gape, "angles": [a.get(b, 0.0) for b in range(len(rig.bones))]})
    return {"slug": slug, "rig": MO.rig_doc(rig, plan), "poses": poses}


def compute_motion() -> list:
    return [motion_vector(s) for s in MOTION_SLUGS]


if __name__ == "__main__":
    if "--write-motion" in sys.argv:
        from norna_fishdraw.build import dumps

        with open(MOTION_PATH, "w") as f:
            f.write(dumps(compute_motion()) + "\n")
        print("wrote", MOTION_PATH)
    elif "--write" in sys.argv:
        with open(PATH, "w") as f:
            json.dump(compute(), f, indent=1, sort_keys=True)
            f.write("\n")
        print("wrote", PATH)
    else:
        print(json.dumps(compute()[0], indent=1))
