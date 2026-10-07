"""v1 against v2, species by species, in one light: `python3 norna_fishdraw/v2/compare.py [OUT.png]`.

Each cell renders the v1 GLB (`out/fish/<slug>.glb`) and a freshly baked, skinned v2 GLB of the
nearest v2 species through the SAME software rasteriser the bag icons use (`icons.render_path`): the same view, the
same key and rim light, the same textures sampled the same way. A human reads it: v2 must win or tie on every species.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from norna_fishdraw import icons  # noqa: E402
from norna_fishdraw.v2 import build as B  # noqa: E402
from norna_fishdraw.v2 import genome as G  # noqa: E402
from norna_fishdraw.v2 import glb as GLB  # noqa: E402
from norna_fishdraw.v2 import rig as RG  # noqa: E402


#: the nearest v1 species of each v2 species (v1 has no flatfish, ray, seahorse or squid: nearest silhouette)
ANALOG = {
    "perch": "reed-perch", "pike": "tusk-pike", "catfish": "gloam-barbel", "angler": "deep-wolffish", "tuna": "storm-tuna", "carp": "moss-carp",
    "billfish": "ash-gar", "lionfish": "jewel-bleak", "plaice": "silver-bream", "oarfish": "mottled-eel", "eel": "mire-loach", "moray": "mottled-eel",
    "hammerhead": "storm-tuna", "puffer": "moonscale", "sunfish": "silver-bream", "angelfish": "glass-shiner", "sturgeon": "ember-sturgeon",
    "skate": "sea-ling", "seahorse": "star-fin", "squid": "cinder-wyrm", "mawfish": "fathom-cod",
}
PX = 256


def _font(n):
    from PIL import ImageFont

    try:
        return ImageFont.load_default(size=n)
    except TypeError:
        return ImageFont.load_default()


def _rolled(fish, q):
    import copy

    from norna_fishdraw.v2.surface import add, cross, mul

    x, y, z, w = q

    def rot(p):
        t = mul(cross((x, y, z), p), 2.0)
        return add(add(p, mul(t, w)), cross((x, y, z), t))

    out = copy.deepcopy(fish)
    for m in [out.skin, *[p.mesh for p in out.parts]]:
        m.tris = {r: [tuple(rot(p) for p in t) for t in ts] for r, ts in m.tris.items()}
    return out


def tile(path: Path):
    from PIL import Image

    old = (icons.ICON, icons.W)
    icons.ICON, icons.W = PX, PX * icons.SS
    try:
        return Image.frombytes("RGBA", (PX, PX), icons.downsample(icons.render_path(path)))
    finally:
        icons.ICON, icons.W = old


def main(argv):
    from PIL import Image, ImageDraw  # Pillow only draws the sheet: the module imports without it

    out = argv[0] if argv else os.path.expanduser("out/sheets/s2-v1-vs-v2.png")
    names = [n for n in G.SPECIES]
    cols = 3
    rows = (len(names) + cols - 1) // cols
    cw = 2 * PX + 20
    sheet = Image.new("RGB", (cols * cw, rows * (PX + 34)), (34, 28, 24))
    d = ImageDraw.Draw(sheet)
    tmp = tempfile.mkdtemp(prefix="fishdraw-v2-compare-")
    for k, sp in enumerate(names):
        f = B.make(sp, 1, log=lambda *a: None)
        p2 = os.path.join(tmp, sp + ".glb")
        pose = GLB.display_pose(f.genome["plan"])
        rig = RG.build_rig(f)
        if pose:  # the icon rasteriser ignores node rotations: roll the geometry itself, as a bag icon or a hand would show it
            f = _rolled(f, pose)
            rig = None
        GLB.write_glb(p2, f, rig, sp)
        v1 = tile(icons.MODELS / (ANALOG[sp] + ".glb"))
        v2 = tile(Path(p2))
        x, y = (k % cols) * cw, (k // cols) * (PX + 34)
        for im, dx in ((v1, 0), (v2, PX + 10)):
            bg = Image.new("RGBA", im.size, (52, 44, 38, 255))
            bg.alpha_composite(im)
            sheet.paste(bg.convert("RGB"), (x + dx, y + 30))
        d.text((x + 6, y + 6), "%s   v1: %s  |  v2" % (sp, ANALOG[sp]), font=_font(14), fill=(240, 230, 210))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    sheet.save(out)
    print(out, sheet.size)


if __name__ == "__main__":
    main(sys.argv[1:])
