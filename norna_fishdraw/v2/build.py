"""seed -> genome -> mesh, fail closed: `make` retries a failed catch at weaker gene strength, down to the plain species.

The build is welded from the start: the genes decide which lattice vertices and cells the parts will root on, the loft
leaves exactly those open (sockets, tentacle roots, bump cells), and each part is then built from the body's own
vertices around them.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field

from ..lift3d import Mesh
from . import genome as G
from . import parts as P
from .loft import loft, surviving_edges
from .plans import PLANS as PLAN_SPECS
from .plans import body_rings
from .surface import add, mul, norm
from .validate import Report, validate


LADDER = (1.0, 0.7, 0.4, 0.0)  # gift expression: full, then weaker, then the plain species mesh
LOG = logging.getLogger("norna_fishdraw.v2")
FAILURES: list[dict] = []  # every rejected attempt of this process: {species, seed, strength, failed, notes}


@dataclass
class Fish:
    genome: dict  # as drawn (the row payload)
    eff: dict  # as built: gifts applied at `strength`
    strength: float
    grid: object
    skin: Mesh
    parts: list
    layout: dict = field(default_factory=dict)
    attempts: list = field(default_factory=list)  # [(strength, Report)] rejected before this one

    def mesh(self) -> Mesh:
        m = Mesh()
        for src in [self.skin, *[p.mesh for p in self.parts]]:
            for role, tris in src.tris.items():
                m.tris.setdefault(role, []).extend(tris)
            for role, uvs in src.uvs.items():
                m.uvs.setdefault(role, []).extend(uvs)
        return m


# ----------------------------------------------------------------------------------------------------- layout
def _near(seq, target):
    return min(range(len(seq)), key=lambda k: abs(seq[k] - target))


def _jdeg(thetas, deg):
    t = math.radians(deg % 360.0)
    return min(range(len(thetas)), key=lambda k: min(abs(thetas[k] - t), 2 * math.pi - abs(thetas[k] - t)))


def _rimset(ij, K):
    i, j = ij
    return {(i, (j + 1) % K), (i + 1, (j + 1) % K), (i + 1, j % K), (i, (j - 1) % K), (i - 1, (j - 1) % K), (i - 1, j % K)}


def _free(ij, holes, K):
    """No two holes may be adjacent or share a rim EDGE (two rim vertices): the shared edge would lose both its faces."""
    a = _rimset(ij, K)
    for h in holes:
        if h == ij or (h[0], h[1] % K) in a or ij in _rimset(h, K) or len(a & _rimset(h, K)) >= 2:
            return False
    return True


def _run(chain, holes, edges):
    """The longest stretch of `chain` whose vertices are all alive and whose consecutive edges all still have a face."""
    best, cur = [], []
    for ij in chain:
        if ij in holes:
            cur = []
            continue
        if cur and frozenset((cur[-1], ij)) not in edges:
            cur = []
        cur = cur + [ij]
        if len(cur) > len(best):
            best = cur
    return best


def _hump(u):
    return 0.35 + 0.65 * math.sin(math.pi * min(1.0, 0.05 + 0.9 * u))


def _span(grid_S, s0, s1, j, n_min, R):
    i0, i1 = _near(grid_S, s0), _near(grid_S, s1)
    i1 = min(max(i1, i0 + n_min - 1), R - 2)
    i0 = max(1, min(i0, i1 - n_min + 1))
    return [(i, j) for i in range(i0, i1 + 1)]


def layout(g, rings, thetas):
    """Decide, before the loft, which lattice vertices become sockets and tentacle roots, which cells become bumps, and
    which chains the fins and jaw root on. Eyes cut first; every later cut keeps clear of the chains. -> dict."""
    R, K = len(rings), len(thetas)
    S = [r.s for r in rings]
    pr, plan = g["parts"], g["plan"]
    holes: dict = {}
    recess: dict = {}
    jb = K // 2
    lay = {"eyes": [], "lure": None, "tents": [], "cells": {}, "K": K, "R": R, "chains": {}, "jaw": None}

    def hole(ij, depth=0.0):
        holes[ij] = depth
        if depth:
            recess[ij] = depth

    e = pr["eye"]
    body = g["body"]
    rost = body.get("rostrum", 0.0)
    s_eye = rost + (1.0 - rost) * e["k"] * body.get("peak", 0.36)
    ie = 1 if plan == "hammerhead" else min(max(_near(S, s_eye), 1), R - 2)
    if e.get("cyclops"):
        lay["eyes"] = [(ie, 0)]
    else:
        je = _jdeg(thetas, e["theta"])
        lay["eyes"] = [(ie, je), (ie, (K - je) % K)] if je not in (0, jb) else [(ie, je)]
    for ij in lay["eyes"]:
        hole(ij, 0.1 * rings[ij[0]].r)
    edges = surviving_edges(R, K, holes)
    reserved: set = set()
    chains = lay["chains"]

    def chain(name, ch, need):
        run = _run(ch, holes, edges)
        if len(run) >= need:
            chains[name] = run
            reserved.update(run)
        else:
            chains[name] = None

    flank = _jdeg(thetas, 115)
    if "dorsal" in pr:
        d = pr["dorsal"]
        chain("dorsal", _span(S, d["s0"], d["s1"], 0, 3, R), 3)
    if "anal" in pr:
        d = pr["anal"]
        chain("anal", _span(S, d["s0"], d["s1"], jb, 3, R), 3)
    if "pectoral" in pr:
        i0 = _near(S, pr["pectoral"]["s"])
        for tag, j in (("l", flank), ("r", (K - flank) % K)):
            chain("pectoral." + tag, [(i0 + k, j) for k in range(3) if i0 + k < R - 1], 2)
    if "pelvic" in pr:
        ribbon = plan == "ribbon"
        i0 = _near(S, pr["pelvic"]["s"])
        jp = _jdeg(thetas, 160 if ribbon else 145)
        for tag, j in (("l", jp), ("r", (K - jp) % K)):
            chain("pelvic." + tag, [(i0, j), (i0 + 1, j)], 2)
    if "dorsal2" in pr:
        d = pr["dorsal2"]
        chain("dorsal2", _span(S, d["s0"], d["s1"], 0, 3, R), 3)
    if "frill" in pr:
        d = pr["frill"]
        jf = _jdeg(thetas, 60)
        for tag, j in (("l", jf), ("r", (K - jf) % K)):
            chain("frill." + tag, _span(S, d["s0"], d["s1"], j, 4, R), 4)
    if "crest" in pr:
        d = pr["crest"]
        chain("crest", _span(S, d["s0"], d["s1"], 0, 6, R), 6)
    for key in ("fringe", "wing"):
        if key in pr:
            d = pr[key]
            je_ = _jdeg(thetas, 90)
            for tag, j in (("l", je_), ("r", (K - je_) % K)):
                chain("%s.%s" % (key, tag), _span(S, d["s0"], d["s1"], j, 4, R), 4)
    if "finlets" in pr:
        n = pr["finlets"]["n"]
        rr = list(range(R - 2 - n, R - 1))
        chain("finlets.top", [(i, 0) for i in rr], 2)
        chain("finlets.bottom", [(i, jb) for i in rr], 2)
    if "jaw" in pr and plan in ("round", "ribbon", "eel", "armoured"):
        s_b = {"round": 0.11, "ribbon": 0.1, "eel": 0.11, "armoured": 0.1}[plan]
        ib = min(max(_near(S, s_b), 3), R - 3)
        degs = (300, 330, 0, 30, 60) if pr["jaw"].get("up") else (120, 150, 180, 210, 240)
        js = [_jdeg(thetas, d_) for d_ in degs]
        run = _run([(ib, j) for j in js], holes, edges)
        if len(run) == 5:
            lay["jaw"] = (ib, js)
            reserved.update(run)
    if "tail" in pr:  # the last ring's two roots stay clear too
        reserved.update((R - 1, j) for j in range(K))

    def clear(ij):
        return _rimset(ij, K) | {ij}

    def free(ij):
        return _free(ij, holes, K) and not (clear(ij) & reserved)

    if "lure" in pr:
        il = min(max(_near(S, pr["lure"]["s"]), 1), R - 2)
        while not free((il, 0)) and il < R - 3:
            il += 1
        if free((il, 0)):
            lay["lure"] = (il, 0)
            hole((il, 0))
    want = []
    if "tent" in pr:
        t = pr["tent"]
        band = t.get("band", 1)
        if band == 1:  # a ring of them round the mouth
            slots = [(1, j) for j in (jb, jb - 2, jb + 2, jb - 4, jb + 4, 0)]
        elif band == 0:  # on the chin
            slots = [(2, jb - 1), (2, jb + 1), (3, jb), (3, jb - 2), (3, jb + 2)]
        else:  # along the belly
            slots = [(i, jb) for i in range(4, R - 3, 2)]
        want += [("tent", t, ij) for ij in slots[: t["n"]]]
    if "barbels" in pr:
        b = pr["barbels"]
        slots = [(2, jb - 1), (2, jb + 1), (3, jb - 3), (3, jb + 3), (3, jb), (2, jb - 3), (2, jb + 3), (4, jb)]
        want += [("barbel", b, ij) for ij in slots[: b["n"]]]
    if plan == "squid":
        a, c = pr["arms"], pr["club"]
        arm_slots = [(1, j) for j in range(0, K, 2)] + [(3, 0), (3, K - 2)]
        club_slots = [(3, jb - 2), (3, jb)]
        want += [("arm", a, ij) for ij in arm_slots[: a["n"]]]
        want += [("club", c, ij) for ij in club_slots[: c["n"]]]
    for kind, spec, ij in want:
        ij = (min(max(ij[0], 1), R - 2), ij[1] % K)
        if free(ij):
            hole(ij)
            lay["tents"].append((kind, spec, ij))
    taken = set(reserved)
    for (i, j) in holes:
        taken |= _rimset((i, j), K) | {(i, j)}

    def ok_cell(i, j):
        vs = {(i, j % K), (i, (j + 1) % K), (i + 1, (j + 1) % K), (i + 1, j % K)}
        return not (vs & taken)

    cells = lay["cells"]
    used_edges: set = set()

    def pick(cands):
        """Greedy, never edge-adjacent: two bumps sharing a body edge would leave that edge with no face at all."""
        out = []
        for (i, j) in cands:
            q = [(i, j % K), (i, (j + 1) % K), (i + 1, (j + 1) % K), (i + 1, j % K)]
            es = [frozenset((q[k], q[(k + 1) % 4])) for k in range(4)]
            if ok_cell(i, j) and not any(e in used_edges for e in es):
                out.append((i, j))
                used_edges.update(es)
        return out

    if "scutes" in pr:
        rows = [0, 2, K - 2, 4, K - 4][: pr["scutes"]["rows"]]
        cells["scute"] = pick([(i, j) for i in range(4, R - 3, 2) for j in rows])
    if "spikes" in pr:
        st = max(1, pr["spikes"]["step"])
        cells["spike"] = pick([(i, j) for i in range(3, R - 4, st) for j in range(0, K, st)])
    if "wart" in pr:
        st = max(1, pr["wart"]["step"])
        cells["wart"] = pick([(i, j) for i in range(3, R - 3, st) for j in range(1, K, st + 1)])
    lay["holes"], lay["recess"] = holes, recess
    return lay


# ----------------------------------------------------------------------------------------------------- assemble
def assemble(grid, g, lay) -> list:
    L, plan, pr = g["len_m"], g["plan"], g["parts"]
    K, R = grid.K, grid.R
    th = grid.thetas
    jb = K // 2
    Rm = max(r.r for r in grid.rings)
    ch = lay["chains"]
    out: list = []
    for n, ij in enumerate(lay["eyes"]):
        tag = "eye" if len(lay["eyes"]) == 1 else ("eye.r" if n else "eye.l")
        out.append(P.eye(grid, tag, ij, pr["eye"]["size"], pr["eye"]["bulge"]))
    if lay["jaw"]:
        j = pr["jaw"]
        ib, js = lay["jaw"]
        out.extend(P.jaw(grid, "jaw", ib, js, j["proj"], j["drop"], j["gape"], j.get("slope", 0.0), j["teeth"], j["tooth"]))
    for kind, spec, ij in lay["tents"]:
        nm = "%s%d" % (kind, sum(1 for p in out if p.kind in ("tentacle", "barbel", "arm")))
        seed_plane = G.unit(g["seed"], "plane." + nm) * 2 * math.pi
        if kind == "barbel":
            out.extend(P.tube(grid, nm, "barbel", ij, spec["len"], spec["tip"], curl=spec["curl"], plane=seed_plane, lean=0.15, lean_dir=(0, 0, 1), bend_to=(0.0, 0.0, 1.0), segs=3, role="barbel", unit=Rm, collar=0.45))
        elif kind == "tent":
            ln = spec["len"]
            out.extend(P.tube(grid, nm, "tentacle", ij, ln, spec["tip"], curl=spec["curl"], plane=seed_plane, lean=1.0, lean_dir=(0, 0, 1), bend_to=(0.0, 0.0, 1.0), segs=4 if ln < 1.4 else 5, club=spec.get("club", 0.0), suckers=spec.get("suck", 0.0), role="arm", unit=Rm, collar=0.55))
        elif kind == "arm":
            out.extend(P.tube(grid, nm, "arm", ij, spec["len"], 0.12, curl=spec["curl"], plane=seed_plane, lean=1.4, lean_dir=(0, 0, 1), bend_to=grid.radial(*ij), segs=4, suckers=spec["suck"], role="arm", unit=Rm))
        else:
            out.extend(P.tube(grid, nm, "arm", ij, spec["len"], 0.2, curl=spec["curl"], plane=seed_plane, lean=1.6, lean_dir=norm(add((0.0, 0.0, 1.0), mul(grid.radial(*ij), 0.4))), bend_to=grid.radial(*ij), segs=5, club=spec["size"], suckers=0.6, role="arm", unit=Rm, bulb_role="arm"))
    if lay["lure"]:
        u = pr["lure"]
        out.extend(P.tube(grid, "lure", "stalk", lay["lure"], u["stalk"], 0.09, curl=u["curl"], bend_to=(0.0, 0.0, 1.0), lean=0.0, segs=3, club=u["bulb"], role="stalk", unit=Rm, collar=0.42))
    if ch.get("dorsal"):
        d = pr["dorsal"]
        out.append(P.fin(grid, "dorsal", "dorsal", ch["dorsal"], d["h"], (1.0, 0.45, 0.0), profile=_hump, membrane=d.get("membrane", 0.55)))
    if ch.get("dorsal2"):
        d = pr["dorsal2"]
        out.append(P.fin(grid, "dorsal2", "dorsal", ch["dorsal2"], d["h"], (1.0, 0.45, 0.0), profile=_hump, membrane=d.get("membrane", 0.55)))
    for tag in ("l", "r"):
        if ch.get("frill." + tag):
            d = pr["frill"]
            out.append(P.fin(grid, "frill." + tag, "frill", ch["frill." + tag], d["h"], (1.0, 0.2, 0.1), profile=lambda u: 0.5 + 0.5 * math.sin(math.pi * u), membrane=d.get("membrane", 0.7), ripple=0.25, wave=(4.0, 0.2)))
    if ch.get("anal"):
        out.append(P.fin(grid, "anal", "anal", ch["anal"], pr["anal"]["h"], (1.0, 0.4, 0.0), profile=_hump, membrane=0.55))
    for tag in ("l", "r"):
        if ch.get("pectoral." + tag):
            out.append(P.fin(grid, "pectoral." + tag, "pectoral", ch["pectoral." + tag], pr["pectoral"]["len"], (0.8, 0.9, -0.2), profile=lambda u: 1.0 - 0.5 * u, membrane=0.5, ext={0: 1.0 + pr["pectoral"].get("filament", 0.0)}))
        if ch.get("pelvic." + tag):
            ribbon = plan == "ribbon"
            out.append(P.fin(grid, "pelvic." + tag, "pelvic", ch["pelvic." + tag], pr["pelvic"]["len"], (0.6, 1.2, -0.1) if ribbon else (0.8, pr["pelvic"].get("back", 0.7), 0.0), membrane=1.0))
    if ch.get("crest"):
        d = pr["crest"]
        out.append(P.fin(grid, "crest", "crest", ch["crest"], d["h"], (1.0, 0.12, 0.0), profile=lambda u: (1.0 - 0.45 * u) * (1.0 + 0.9 * max(0.0, 1 - u / 0.1)), membrane=d.get("membrane", 0.5), wave=(d.get("waves", 2.0), 0.14)))
    for key in ("fringe", "wing"):
        for tag in ("l", "r"):
            c = ch.get("%s.%s" % (key, tag))
            if c:
                d = pr[key]
                out.append(P.fin(grid, "%s.%s" % (key, tag), key, c, d["h"], (1.0, 0.1, 0.0), profile=lambda u: 0.3 + 0.7 * math.sin(math.pi * min(1.0, u * 0.95 + 0.02)), membrane=d.get("membrane", 0.7), ripple=0.04))
    for tag, nm in (("top", "finlets.top"), ("bottom", "finlets.bottom")):
        c = ch.get(nm)
        if c:
            out.append(P.finlets(grid, nm, [ij[0] for ij in c], c[0][1], pr["finlets"]["h"]))
    if "tail" in pr:
        t = pr["tail"]
        if plan in ("flat", "ray", "squid"):
            ja, jbb = _jdeg(th, 90), _jdeg(th, 270)
        else:
            ja, jbb = 0, jb
        out.append(P.tail(grid, "tail", ja, jbb, t["len"], t["lobe"], t["fork"], G.TAIL_SHAPES[t.get("shape", 0)], t.get("streamer", 0.0)))
    for kind, cells in lay["cells"].items():
        if not cells:
            continue
        spec = pr[{"spike": "spikes", "scute": "scutes", "wart": "wart"}[kind]]
        out.append(P.bumps(grid, kind + "s", kind, cells, spec["h"], {"spike": "spike", "scute": "plate", "wart": "plate"}[kind]))
    return out


def _uvfn(rings, thetas, mode):
    if mode == "top":
        return lambda i, j: (rings[i].s, 0.5 + 0.5 * math.sin(thetas[j]))
    return lambda i, j: (rings[i].s, (1.0 - math.cos(thetas[j])) / 2.0)


def build(genome: dict, strength: float = 1.0) -> Fish:
    eff = G.effective(genome, strength)
    rings, thetas, uv = body_rings(eff)
    lay = layout(eff, rings, thetas)
    cells = frozenset(c for cs in lay["cells"].values() for c in cs)
    grid, skin = loft(rings, thetas, _uvfn(rings, thetas, uv), lay["holes"], cells, lay["recess"], uv_under=(uv != "top"))
    return Fish(genome, eff, strength, grid, skin, assemble(grid, eff, lay), lay)


def _log(fish: Fish, report: Report):
    g = fish.genome
    rec = {"species": g["species"], "seed": g["seed"], "strength": fish.strength, "failed": report.failed(), "notes": list(report.notes)}
    FAILURES.append(rec)
    LOG.warning("fishdraw v2 rejected %s seed=%d strength=%.2f: %s", rec["species"], rec["seed"], rec["strength"], "; ".join(rec["notes"]))


def make_from(genome: dict, ladder=LADDER, log=_log) -> Fish:
    """The fail-closed pipeline: validate each rung of the ladder, return the first that passes."""
    attempts = []
    for strength in ladder:
        fish = build(genome, strength)
        report = validate(fish)
        if report.ok:
            fish.attempts = attempts
            return fish
        attempts.append((strength, report))
        log(fish, report)
    raise AssertionError("plain species mesh failed for %s seed %s: a species bug, never shipped" % (genome["species"], genome["seed"]))


def make(species: str, seed: int, gifts=None, log=_log) -> Fish:
    return make_from(G.draw(species, seed, gifts), log=log)
