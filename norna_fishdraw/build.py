"""Write every species' canonical v1 fish: <slug>.glb + .calibrate.json + fish.json.

    python3 norna_fishdraw/build.py [--out DIR]     # default out/v1

Pure Python (no Blender), byte-stable: running it twice changes nothing.
`fish.json` is the generated index; it spells every stem as plain text so an
asset checker can grep for used models. v1 is the first lift of the fishdraw
port; the v2 bake (`v2/bake.py --game`) is what Norna ships.
"""

from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from norna_fishdraw.glb_writer import write_glb  # noqa: E402
from norna_fishdraw.presets import SLUGS, SPECIES, fish_for  # noqa: E402

ROOT = os.path.dirname(HERE)
DEFAULT_OUT = os.path.join(ROOT, "out", "v1")


def dumps(v, ind=0, width=100) -> str:
    """json.dumps, 4-space indent, scalar lists on one line while they fit in 100 columns."""
    pad = " " * ind
    if isinstance(v, dict):
        rows = ["%s    %s: %s" % (pad, json.dumps(k), dumps(x, ind + 4)) for k, x in v.items()]
        return "{\n" + ",\n".join(rows) + "\n" + pad + "}"
    if isinstance(v, list):
        one = "[" + ", ".join(json.dumps(x) for x in v) + "]"
        if all(not isinstance(x, (dict, list)) for x in v) and len(pad) + len(one) + 20 <= width:
            return one
        return "[\n" + ",\n".join(pad + "    " + dumps(x, ind + 4) for x in v) + "\n" + pad + "]"
    return json.dumps(v)


def calibrate_json(mesh, species) -> str:
    lo, hi = mesh.bounds()
    dims = [round(hi[i] - lo[i], 4) for i in range(3)]
    cal = {
        "model": {
            "boundsSource": "vertices",
            "boundsPose": "bind",
            "aabb": {"min": [round(v, 4) for v in lo], "max": [round(v, 4) for v in hi]},
            "dims": dims,
            "center": [round((lo[i] + hi[i]) / 2, 4) for i in range(3)],
            "groundOffset": 0,
            "intended": {"dimension": "length", "size": species.length_m},
            "scale": 1,
            "y": 0,
            "yaw": 0,
        },
        "notes": "%s, drawn by norna_fishdraw (a 3D port of LingDong-/fishdraw, MIT) at the median catch (%.2f kg, %.2f m). Origin at the centre, nose +Z, back +Y, 1 unit = 1 m."
        % (species.slug, species.kg[2], species.length_m),
    }
    return dumps(cal) + "\n"


def build(out_dir: str = DEFAULT_OUT) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    index = {}
    for slug in SLUGS:
        sp = SPECIES[slug]
        fish = fish_for(slug, None)
        mesh = fish.mesh()
        stats = write_glb(os.path.join(out_dir, slug + ".glb"), mesh, sp.look.palette, slug, fish.look.skin)
        with open(os.path.join(out_dir, slug + ".calibrate.json"), "w") as f:
            f.write(calibrate_json(mesh, sp))
        lo, hi = mesh.bounds()
        index[slug] = {
            "glb": slug + ".glb",
            "tris": stats["tris"],
            "lengthM": sp.length_m,
            "kg": list(sp.kg),
            "dims": [round(hi[i] - lo[i], 4) for i in range(3)],
        }
    doc = {
        "generator": "norna_fishdraw/build.py",
        "note": "Generated. One canonical fish per species (median kg); fish_for(species, seed) in norna_fishdraw/presets.py makes the per-catch variants. Origin at centre, nose +Z, back +Y, 1 unit = 1 m.",
        "species": list(SLUGS),
        "models": index,
    }
    with open(os.path.join(out_dir, "fish.json"), "w") as f:
        f.write(dumps(doc) + "\n")
    return doc


if __name__ == "__main__":
    out = DEFAULT_OUT
    if "--out" in sys.argv:
        out = os.path.abspath(sys.argv[sys.argv.index("--out") + 1])
    d = build(out)
    for s, m in d["models"].items():
        print("%-16s %4d tris  %s m" % (s, m["tris"], m["dims"]))
