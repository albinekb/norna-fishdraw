"""Variety, measured: how alike two catches of one species look at a glance.

A catch's silhouette is its side and top projection rasterised on a fixed grid in units of its own body length (nose
aligned, centred on the body's axis), so two seeds compare by SHAPE, not by size. The overlap of two catches is the mean
of their side and top IoU. `species_variety` reports the mean and worst pairwise overlap over a set of seeds: the guard
that keeps the gene space from silently collapsing into six recoloured copies of one fish.
"""

from __future__ import annotations

import itertools


COLS, ROWS = 90, 48
SPAN_Z, SPAN_Y = 0.8, 0.6  # the grid covers +-SPAN of a body length either side of the centre


def mask(fish, axis: int):
    """The set of cells covered when looking along the axis that is neither z nor `axis` (1 = side view, 0 = top)."""
    tris = [t for ts in fish.mesh().tris.values() for t in ts]
    pts = [p for t in tris for p in t]
    skin = [p for ts in fish.skin.tris.values() for t in ts for p in t]
    zc = (max(p[2] for p in skin) + min(p[2] for p in skin)) / 2
    L = max(p[2] for p in skin) - min(p[2] for p in skin)
    ac = (max(p[axis] for p in skin) + min(p[axis] for p in skin)) / 2
    cell = []
    for t in tris:
        P = [((p[2] - zc) / L, (p[axis] - ac) / L) for p in t]
        us = [(u + SPAN_Z) / (2 * SPAN_Z) * COLS for u, _ in P]
        vs = [(v + SPAN_Y) / (2 * SPAN_Y) * ROWS for _, v in P]
        i0, i1 = max(0, int(min(us))), min(COLS - 1, int(max(us)))
        j0, j1 = max(0, int(min(vs))), min(ROWS - 1, int(max(vs)))
        (ax, ay), (bx, by), (cx, cy) = zip(us, vs)
        den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(den) < 1e-12:
            continue
        for i in range(i0, i1 + 1):
            for j in range(j0, j1 + 1):
                x, y = i + 0.5, j + 0.5
                w1 = ((by - cy) * (x - cx) + (cx - bx) * (y - cy)) / den
                w2 = ((cy - ay) * (x - cx) + (ax - cx) * (y - cy)) / den
                if w1 >= -0.02 and w2 >= -0.02 and w1 + w2 <= 1.02:
                    cell.append((i, j))
    return frozenset(cell)


def silhouette(fish):
    return mask(fish, 1), mask(fish, 0)


def iou(a, b) -> float:
    return len(a & b) / max(1, len(a | b))


def overlap(sa, sb) -> float:
    return 0.5 * (iou(sa[0], sb[0]) + iou(sa[1], sb[1]))


def species_variety(species: str, seeds, make) -> dict:
    """-> {mean, worst, pair}: overlap statistics over every pair of catches of `species` for `seeds`."""
    sils = [silhouette(make(species, s)) for s in seeds]
    vals = [(overlap(sils[i], sils[j]), (seeds[i], seeds[j])) for i, j in itertools.combinations(range(len(seeds)), 2)]
    worst = max(vals)
    return {"mean": sum(v for v, _ in vals) / len(vals), "worst": worst[0], "pair": worst[1]}
