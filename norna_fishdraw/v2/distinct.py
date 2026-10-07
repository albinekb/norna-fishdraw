"""Species held apart: how alike two catchable species look, side and top, at their canonical seed.

    python3 norna_fishdraw/v2/distinct.py [--cap 0.88] [--top 12]

Every game slug (`game.GAME`) is baked at its `CANON` seed through the fail-closed `make`, its side and top silhouette is
rasterised in units of its own body length (`variety.silhouette`) and every pair is scored by `variety.overlap`, the mean
of the two IoUs. The guard is on wave 2 (`game2.GAME2`): no new slug may overlap ANY other slug above the cap, so a
seventy-first fish cannot be a recoloured copy of one that is there. The first thirty-eight overlap each other by more
(the frost char and the rill trout are one silhouette in two colours); they are reported, not guarded.
"""

from __future__ import annotations

import itertools
import os
import sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from norna_fishdraw.v2 import build as B  # noqa: E402
from norna_fishdraw.v2 import game as GM  # noqa: E402
from norna_fishdraw.v2 import variety as V  # noqa: E402


#: the most two species may overlap when one of them is a wave-2 slug (mean of side and top IoU)
CAP = 0.88


def pairs() -> list[tuple[float, str, str]]:
    """Every pair of game slugs with its overlap, the most alike first."""
    sils = {slug: V.silhouette(B.make(slug, GM.CANON[slug], log=lambda *a: None)) for slug in GM.SLUGS}
    return sorted(((V.overlap(sils[a], sils[b]), a, b) for a, b in itertools.combinations(sils, 2)), reverse=True)


def too_alike(cap: float = CAP) -> list[tuple[float, str, str]]:
    """The pairs over `cap` that involve a wave-2 slug."""
    from norna_fishdraw.v2.game2 import GAME2

    return [p for p in pairs() if p[0] > cap and (p[1] in GAME2 or p[2] in GAME2)]


def main(argv: list[str]) -> int:
    cap = float(argv[argv.index("--cap") + 1]) if "--cap" in argv else CAP
    top = int(argv[argv.index("--top") + 1]) if "--top" in argv else 12
    from norna_fishdraw.v2.game2 import GAME2

    ranked = pairs()
    new = [p for p in ranked if p[1] in GAME2 or p[2] in GAME2]
    print("worst %d pairs involving a wave-2 slug:" % top)
    for o, a, b in new[:top]:
        print("  %.3f  %s  %s" % (o, a, b))
    over = [p for p in new if p[0] > cap]
    print("%d wave-2 pairs over the cap %.2f; the worst of all %d pairs is %.3f (%s, %s)" % (len(over), cap, len(ranked), *ranked[0]))
    return 1 if over else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
