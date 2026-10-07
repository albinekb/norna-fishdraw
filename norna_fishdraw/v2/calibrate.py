"""Set each wave-2 slug's body length gene so the baked fish is v1's median length.

    python3 norna_fishdraw/v2/calibrate.py            # rewrite BODY_LEN2 in game2.py
    python3 norna_fishdraw/v2/calibrate.py --check    # exit 1 when any slug's baked length is off by more than 0.5%

A fish scales whole with its body length gene (every part is a fraction of the local radius), so the measured nose-to-tail
length over the gene is a constant per slug: one measurement and one division give the gene, a second confirms it.
"""

from __future__ import annotations

import os
import re
import sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from norna_fishdraw.presets import SPECIES as V1  # noqa: E402
from norna_fishdraw.v2 import build as B  # noqa: E402
from norna_fishdraw.v2 import game as GM  # noqa: E402
from norna_fishdraw.v2.genome import R  # noqa: E402


GAME2_PY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "game2.py")


def measured(slug: str, length_gene: float) -> float:
    """The baked fish's nose-to-tail length (m) with the body length gene set to `length_gene`."""
    genes = GM.GAME[slug]["genes"]
    old = genes["len_m"]
    genes["len_m"] = R(length_gene)
    try:
        lo, hi = B.make(slug, GM.CANON[slug], log=lambda *a: None).mesh().bounds()
    finally:
        genes["len_m"] = old
    return hi[2] - lo[2]


def solve(slug: str) -> float:
    target = V1[slug].length_m
    x = GM.GAME[slug]["genes"]["len_m"][0]
    for _ in range(3):
        x = round(target * x / measured(slug, x), 4)
    return x


def write(values: dict[str, float]) -> None:
    text = open(GAME2_PY).read()
    block = "BODY_LEN2: dict[str, float] = {\n" + "".join('    "%s": %g,\n' % (k, v) for k, v in values.items()) + "}\n"
    text = re.sub(r"(# BODY_LEN2 begin\n).*?(# BODY_LEN2 end)", lambda m: m.group(1) + block + m.group(2), text, flags=re.S)
    with open(GAME2_PY, "w") as f:
        f.write(text)


def main(argv: list[str]) -> int:
    from norna_fishdraw.v2.game2 import BODY_LEN2

    if argv[:1] == ["--check"]:
        off = []
        for slug in BODY_LEN2:
            got, want = measured(slug, BODY_LEN2[slug]), V1[slug].length_m
            if abs(got - want) > 0.005 * want:
                off.append("%s: baked %.4f m, v1 says %.4f m" % (slug, got, want))
        print("\n".join(off) or "all %d wave-2 slugs are at their median length" % len(BODY_LEN2))
        return 1 if off else 0
    only = argv[0].split(",") if argv else list(BODY_LEN2)
    values = dict(BODY_LEN2)
    for slug in only:
        values[slug] = solve(slug)
    write(values)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
