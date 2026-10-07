"""The gate seed sweep: every species x plain / one mutation / a stacked pair, through the fail-closed `make`.

    python3 norna_fishdraw/v2/sweep.py [N]          # default 500; prints the stats as JSON
    python3 norna_fishdraw/v2/sweep.py --game [N]   # the same over the game's slugs

Zero tolerated failures: `make` raises if even the plain species mesh fails, so a sweep that returns is a sweep of fish
that all validate. What it measures beyond that: how often a gifted catch had to retry, which checks tripped, and that
plain species draws never need a retry.
"""

from __future__ import annotations

import collections
import json
import os
import sys
import time

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from norna_fishdraw.v2 import genome as G  # noqa: E402
from norna_fishdraw.v2.build import make_from  # noqa: E402


KINDS = ("plain", "one", "pair")  # no gift, one mutation (a mutant), two stacked (a legend)


def cases(n: int):
    names = sorted(G.SPECIES)
    for i in range(n):
        sp = names[i % len(names)]
        kind = KINDS[(i // len(names)) % 3]
        seed = 10_000 + i
        yield sp, seed, kind, G.roll_gifts(seed, {"plain": 0, "one": 1, "pair": 2}[kind])


def game_cases(n: int):
    """The game's slugs (`game.GAME`) in turn, plain / one mutation / a stacked pair, as `cases` does the archetypes."""
    from norna_fishdraw.v2 import game

    names = list(game.SLUGS)
    for i in range(n):
        sp = names[i % len(names)]
        kind = KINDS[(i // len(names)) % 3]
        seed = 20_000 + i
        yield sp, seed, kind, G.roll_gifts(seed, {"plain": 0, "one": 1, "pair": 2}[kind])


def sweep(n: int = 500, source=cases) -> dict:
    stats = {"runs": 0, "tris_max": 0, "rejected_attempts": 0}
    final = collections.Counter()
    tripped = collections.Counter()
    by_kind = collections.Counter()
    retried_by_kind = collections.Counter()
    plan_runs = collections.Counter()
    t0 = time.time()
    for sp, seed, kind, gifts in source(n):
        g = G.draw(sp, seed, gifts)
        fish = make_from(g, log=lambda *a: None)  # raises if the plain mesh fails: that is the gate going red
        stats["runs"] += 1
        by_kind[kind] += 1
        plan_runs[g["plan"]] += 1
        final[fish.strength] += 1
        stats["tris_max"] = max(stats["tris_max"], sum(len(t) for t in fish.mesh().tris.values()))
        if fish.attempts:
            retried_by_kind[kind] += 1
        for _, rep in fish.attempts:
            stats["rejected_attempts"] += 1
            tripped.update(rep.failed())
    stats["seconds"] = round(time.time() - t0, 2)
    stats["final_strength"] = {str(k): v for k, v in sorted(final.items())}
    stats["tripped_checks"] = dict(tripped)
    stats["by_kind"] = dict(by_kind)
    stats["retried_by_kind"] = dict(retried_by_kind)
    stats["by_plan"] = dict(plan_runs)
    return stats


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--game"]
    print(json.dumps(sweep(int(args[0]) if args else 500, game_cases if "--game" in sys.argv else cases), indent=1))
