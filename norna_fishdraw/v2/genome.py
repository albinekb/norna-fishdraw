"""Genes, species ranges, the seed -> genome draw, and the mutation catalogue.

A species is a range per gene; a catch is one draw from its seed; a mutation (a `gift`) moves genes outside the range.
Each gene reads its own named sub-stream `unit(seed, "body.height")`, so adding a gene never shifts the others.

Units: `body.*` genes are fractions of body length; every `parts.*` size is a fraction of the LOCAL body radius at the
part's root (`Ring.r`) or, for tails, tubes and lures, of the body's deepest radius: gigantism scales the body and the
parts follow. A species lists a gene to have it; a path ending in `?` is a gate: `("parts.finlets?", (p, p))` makes
the whole `parts.finlets` group exist for a fraction p of seeds.
"""

from __future__ import annotations

import copy
import hashlib


VERSION = 2
INT_GENES = frozenset({"parts.jaw.teeth", "parts.jaw.up", "parts.tent.n", "parts.tent.band", "parts.barbels.n", "parts.arms.n", "parts.club.n", "parts.tail.shape", "parts.finlets.n", "parts.spikes.step", "parts.wart.step", "parts.scutes.rows", "parts.eye.cyclops"})
TAIL_SHAPES = ("forked", "rounded", "lunate", "truncate")


def unit(seed: int, name: str) -> float:
    """A stable float in [0, 1) for (seed, stream name): order-free, so a port in another language can match it."""
    h = hashlib.sha256(("%d:%s" % (seed, name)).encode()).digest()
    return int.from_bytes(h[:8], "big") / 2.0**64


def R(lo, hi=None):
    return (lo, lo if hi is None else hi)


# ----------------------------------------------------------------------------- plan templates (gene ranges)
def _fins_round():
    return {
        "parts.dorsal.s0": R(0.30, 0.36), "parts.dorsal.s1": R(0.54, 0.62), "parts.dorsal.h": R(0.8, 1.3), "parts.dorsal.membrane": R(0.35, 0.65),
        "parts.pectoral.len": R(0.8, 1.3), "parts.pectoral.s": R(0.26, 0.32), "parts.pectoral.filament": R(0.0, 1.6),
        "parts.pelvic.len": R(0.6, 1.0), "parts.pelvic.s": R(0.40, 0.46),
        "parts.anal.s0": R(0.62, 0.66), "parts.anal.s1": R(0.76, 0.84), "parts.anal.h": R(0.5, 0.85),
        "parts.tail.len": R(0.9, 1.4), "parts.tail.lobe": R(0.7, 1.05), "parts.tail.fork": R(0.25, 0.6), "parts.tail.shape": R(0, 3), "parts.tail.streamer": R(0.0, 0.9),
    }


ROUND = {
    "len_m": R(0.28, 0.45), "body.height": R(0.19, 0.27), "body.width": R(0.45, 0.65), "body.taper": R(1.4, 2.2),
    "body.peak": R(0.32, 0.42), "body.nose_p": R(1.6, 2.6), "body.nose": R(0.12, 0.18), "body.tail": R(0.1, 0.16),
    "body.pinch": R(0.0, 0.35), "body.hump": R(0.0, 0.3), "body.sag": R(0.0, 0.18), "body.brow": R(0.0, 0.18),
    "body.nt": R(1.9, 2.6), "body.nb": R(1.9, 2.6), "body.curve": R(-0.01, 0.01),
    "parts.eye.size": R(0.2, 0.3), "parts.eye.bulge": R(0.6, 1.0), "parts.eye.k": R(0.2, 0.26), "parts.eye.theta": R(86.0, 94.0),
    **_fins_round(),
}
FLAT = {
    "len_m": R(0.30, 0.55), "body.height": R(0.06, 0.085), "body.width": R(5.5, 8.0), "body.taper": R(1.2, 2.0),
    "body.peak": R(0.40, 0.52), "body.nose_p": R(1.8, 2.6), "body.nose": R(0.2, 0.3), "body.tail": R(0.2, 0.34),
    "body.pinch": R(0.0, 0.25), "body.hump": R(0.0, 0.2), "body.nt": R(2.4, 3.2), "body.nb": R(2.2, 3.0), "body.curve": R(-0.012, 0.012),
    "parts.eye.size": R(0.2, 0.3), "parts.eye.bulge": R(0.3, 0.6), "parts.eye.k": R(0.2, 0.3), "parts.eye.theta": R(15.0, 20.0),
    "parts.fringe.s0": R(0.18, 0.26), "parts.fringe.s1": R(0.84, 0.92), "parts.fringe.h": R(0.18, 0.3), "parts.fringe.membrane": R(0.6, 0.9),
    "parts.tail.len": R(0.25, 0.4), "parts.tail.lobe": R(0.22, 0.4), "parts.tail.fork": R(0.0, 0.2), "parts.tail.shape": R(1, 3),
}
RIBBON = {
    "len_m": R(1.4, 3.2), "body.height": R(0.08, 0.11), "body.width": R(0.32, 0.5), "body.taper": R(0.7, 1.1),
    "body.peak": R(0.1, 0.2), "body.nose_p": R(1.5, 2.2), "body.nose": R(0.28, 0.4), "body.tail": R(0.07, 0.12), "body.hump": R(0.0, 0.15),
    "body.curve": R(-0.02, 0.02), "body.nt": R(2.0, 2.6), "body.nb": R(2.0, 2.6),
    "parts.eye.size": R(0.25, 0.35), "parts.eye.bulge": R(0.6, 1.0), "parts.eye.k": R(0.3, 0.5), "parts.eye.theta": R(86.0, 94.0),
    "parts.crest.s0": R(0.07, 0.11), "parts.crest.s1": R(0.88, 0.95), "parts.crest.h": R(1.2, 1.9), "parts.crest.waves": R(1.0, 3.0), "parts.crest.membrane": R(0.7, 0.9),
    "parts.pelvic.len": R(2.5, 4.0), "parts.pelvic.s": R(0.14, 0.18),
    "parts.tail.len": R(0.9, 1.4), "parts.tail.lobe": R(0.3, 0.6), "parts.tail.fork": R(0.1, 0.3), "parts.tail.shape": R(0, 2),
}
EEL = {
    "len_m": R(0.8, 1.8), "body.height": R(0.11, 0.15), "body.width": R(0.85, 1.1), "body.taper": R(0.6, 1.0),
    "body.peak": R(0.15, 0.3), "body.nose_p": R(1.8, 2.6), "body.nose": R(0.3, 0.45), "body.tail": R(0.08, 0.14),
    "body.curve": R(-0.04, 0.04), "body.flick": R(-0.05, 0.05), "body.nt": R(2.0, 2.2), "body.nb": R(2.0, 2.2),
    "parts.eye.size": R(0.25, 0.35), "parts.eye.bulge": R(0.6, 1.0), "parts.eye.k": R(0.3, 0.5), "parts.eye.theta": R(86.0, 94.0),
    "parts.dorsal.s0": R(0.14, 0.3), "parts.dorsal.s1": R(0.9, 0.96), "parts.dorsal.h": R(0.45, 0.8), "parts.dorsal.membrane": R(0.7, 0.95),
    "parts.anal.s0": R(0.35, 0.5), "parts.anal.s1": R(0.9, 0.96), "parts.anal.h": R(0.4, 0.7),
    "parts.pectoral.len": R(0.6, 1.0), "parts.pectoral.s": R(0.12, 0.16),
}
HAMMER = {
    "len_m": R(0.9, 2.2), "body.height": R(0.12, 0.15), "body.width": R(0.55, 0.75), "body.taper": R(1.4, 2.1),
    "body.peak": R(0.3, 0.4), "body.nose": R(0.14, 0.2), "body.tail": R(0.08, 0.12), "body.head": R(0.2, 0.3), "body.pinch": R(0.0, 0.3),
    "body.curve": R(-0.012, 0.012), "body.nt": R(2.0, 2.4), "body.nb": R(1.9, 2.3),
    "parts.eye.size": R(0.2, 0.3), "parts.eye.bulge": R(0.6, 1.0), "parts.eye.k": R(0.3, 0.3), "parts.eye.theta": R(88.0, 92.0),
    "parts.dorsal.s0": R(0.3, 0.36), "parts.dorsal.s1": R(0.44, 0.52), "parts.dorsal.h": R(1.6, 2.4), "parts.dorsal.membrane": R(0.2, 0.4),
    "parts.pectoral.len": R(1.4, 2.2), "parts.pectoral.s": R(0.28, 0.34),
    "parts.pelvic.len": R(0.7, 1.1), "parts.pelvic.s": R(0.56, 0.62),
    "parts.anal.s0": R(0.7, 0.74), "parts.anal.s1": R(0.78, 0.82), "parts.anal.h": R(0.5, 0.8),
    "parts.tail.len": R(1.1, 1.6), "parts.tail.lobe": R(0.9, 1.4), "parts.tail.fork": R(0.3, 0.55), "parts.tail.shape": R(2, 2),
}
GLOBE = {
    "len_m": R(0.2, 0.4), "body.height": R(0.42, 0.55), "body.width": R(0.85, 1.05), "body.taper": R(1.0, 1.5),
    "body.peak": R(0.45, 0.55), "body.nose_p": R(1.8, 2.4), "body.nose": R(0.2, 0.3), "body.tail": R(0.14, 0.2), "body.pinch": R(0.2, 0.5),
    "body.sag": R(0.0, 0.2), "body.nt": R(2.0, 2.2), "body.nb": R(2.0, 2.2),
    "parts.eye.size": R(0.22, 0.32), "parts.eye.bulge": R(0.7, 1.1), "parts.eye.k": R(0.25, 0.32), "parts.eye.theta": R(86.0, 94.0),
    "parts.pectoral.len": R(0.35, 0.55), "parts.pectoral.s": R(0.34, 0.4),
    "parts.dorsal.s0": R(0.6, 0.66), "parts.dorsal.s1": R(0.74, 0.8), "parts.dorsal.h": R(0.5, 0.8), "parts.dorsal.membrane": R(0.4, 0.7),
    "parts.anal.s0": R(0.62, 0.66), "parts.anal.s1": R(0.74, 0.8), "parts.anal.h": R(0.4, 0.7),
    "parts.tail.len": R(0.5, 0.8), "parts.tail.lobe": R(0.5, 0.8), "parts.tail.fork": R(0.0, 0.2), "parts.tail.shape": R(1, 3),
    "parts.spikes.h": R(0.1, 0.22), "parts.spikes.step": R(2, 2),
}
DISC = {
    "len_m": R(0.2, 0.5), "body.height": R(0.55, 0.85), "body.width": R(0.14, 0.24), "body.taper": R(1.0, 1.6),
    "body.peak": R(0.4, 0.55), "body.nose_p": R(1.6, 2.4), "body.nose": R(0.12, 0.2), "body.tail": R(0.1, 0.2), "body.pinch": R(0.0, 0.3),
    "body.hump": R(0.0, 0.25), "body.sag": R(0.0, 0.2), "body.brow": R(0.0, 0.2), "body.nt": R(2.2, 3.0), "body.nb": R(1.6, 2.4),
    "parts.eye.size": R(0.2, 0.3), "parts.eye.bulge": R(0.6, 1.0), "parts.eye.k": R(0.2, 0.28), "parts.eye.theta": R(86.0, 94.0),
    "parts.dorsal.s0": R(0.28, 0.36), "parts.dorsal.s1": R(0.7, 0.8), "parts.dorsal.h": R(0.7, 1.5), "parts.dorsal.membrane": R(0.5, 0.9),
    "parts.anal.s0": R(0.3, 0.38), "parts.anal.s1": R(0.68, 0.78), "parts.anal.h": R(0.6, 1.3),
    "parts.pectoral.len": R(0.35, 0.6), "parts.pectoral.s": R(0.3, 0.36),
    "parts.pelvic.len": R(0.5, 1.4), "parts.pelvic.s": R(0.34, 0.4), "parts.pelvic.back": R(0.1, 0.3),
    "parts.tail.len": R(0.25, 0.45), "parts.tail.lobe": R(0.2, 0.4), "parts.tail.fork": R(0.0, 0.3), "parts.tail.shape": R(1, 3),
}
ARMOURED = {
    "len_m": R(0.8, 2.0), "body.height": R(0.14, 0.19), "body.width": R(0.7, 0.95), "body.taper": R(1.1, 1.7),
    "body.peak": R(0.3, 0.42), "body.nose_p": R(1.2, 2.0), "body.nose": R(0.1, 0.16), "body.tail": R(0.07, 0.12), "body.rostrum": R(0.06, 0.12),
    "body.snout_up": R(0.0, 0.4), "body.pinch": R(0.0, 0.3), "body.nt": R(1.8, 2.4), "body.nb": R(2.2, 3.0), "body.curve": R(-0.01, 0.01),
    "parts.eye.size": R(0.2, 0.28), "parts.eye.bulge": R(0.6, 1.0), "parts.eye.k": R(0.3, 0.4), "parts.eye.theta": R(86.0, 94.0),
    "parts.dorsal.s0": R(0.66, 0.7), "parts.dorsal.s1": R(0.8, 0.86), "parts.dorsal.h": R(0.8, 1.2), "parts.dorsal.membrane": R(0.35, 0.6),
    "parts.anal.s0": R(0.7, 0.74), "parts.anal.s1": R(0.8, 0.86), "parts.anal.h": R(0.6, 0.9),
    "parts.pectoral.len": R(0.9, 1.4), "parts.pectoral.s": R(0.2, 0.26),
    "parts.pelvic.len": R(0.6, 0.9), "parts.pelvic.s": R(0.5, 0.56),
    "parts.tail.len": R(1.0, 1.5), "parts.tail.lobe": R(0.9, 1.3), "parts.tail.fork": R(0.3, 0.5), "parts.tail.shape": R(0, 0),
    "parts.scutes.h": R(0.22, 0.4), "parts.scutes.rows": R(3, 4),
}
RAY = {
    "len_m": R(0.5, 1.4), "body.height": R(0.05, 0.075), "body.width": R(6.0, 9.0), "body.taper": R(0.5, 0.9),
    "body.peak": R(0.38, 0.5), "body.nose_p": R(1.2, 2.0), "body.nose": R(0.2, 0.35), "body.tail": R(0.05, 0.09), "body.nt": R(2.4, 3.2), "body.nb": R(2.2, 3.0),
    "parts.eye.size": R(0.2, 0.3), "parts.eye.bulge": R(0.3, 0.6), "parts.eye.k": R(0.2, 0.3), "parts.eye.theta": R(15.0, 20.0),
    "parts.wing.s0": R(0.14, 0.2), "parts.wing.s1": R(0.62, 0.7), "parts.wing.h": R(0.35, 0.55), "parts.wing.membrane": R(0.7, 0.95),
    "parts.dorsal.s0": R(0.74, 0.8), "parts.dorsal.s1": R(0.84, 0.9), "parts.dorsal.h": R(0.6, 1.0), "parts.dorsal.membrane": R(0.4, 0.6),
}
SEAHORSE = {
    "len_m": R(0.12, 0.3), "body.height": R(0.1, 0.14), "body.width": R(0.7, 0.95), "body.taper": R(0.8, 1.2),
    "body.peak": R(0.3, 0.4), "body.nose_p": R(1.5, 2.2), "body.nose": R(0.2, 0.3), "body.tail": R(0.08, 0.12), "body.curl": R(0.5, 1.0),
    "body.brow": R(0.0, 0.2), "body.nt": R(2.0, 2.6), "body.nb": R(2.0, 2.6),
    "parts.eye.size": R(0.2, 0.3), "parts.eye.bulge": R(0.6, 1.0), "parts.eye.k": R(0.2, 0.3), "parts.eye.theta": R(86.0, 94.0),
    "parts.dorsal.s0": R(0.4, 0.46), "parts.dorsal.s1": R(0.52, 0.58), "parts.dorsal.h": R(0.8, 1.2), "parts.dorsal.membrane": R(0.5, 0.8),
    "parts.pectoral.len": R(0.5, 0.8), "parts.pectoral.s": R(0.2, 0.24),
}
SQUID = {
    "len_m": R(0.3, 0.9), "body.height": R(0.2, 0.28), "body.width": R(0.9, 1.05), "body.taper": R(0.9, 1.4),
    "body.peak": R(0.5, 0.6), "body.nose_p": R(1.6, 2.4), "body.nose": R(0.34, 0.44), "body.tail": R(0.05, 0.1), "body.nt": R(2.0, 2.2), "body.nb": R(2.0, 2.2),
    "parts.eye.size": R(0.22, 0.3), "parts.eye.bulge": R(0.7, 1.1), "parts.eye.k": R(0.3, 0.34), "parts.eye.theta": R(86.0, 94.0),
    "parts.fringe.s0": R(0.6, 0.66), "parts.fringe.s1": R(0.92, 0.97), "parts.fringe.h": R(0.5, 0.8), "parts.fringe.membrane": R(0.8, 1.0),
    "parts.arms.n": R(8, 8), "parts.arms.len": R(2.0, 3.2), "parts.arms.curl": R(0.0, 1.2), "parts.arms.suck": R(0.5, 0.9),
    "parts.club.n": R(2, 2), "parts.club.len": R(4.0, 6.0), "parts.club.curl": R(0.0, 0.8), "parts.club.size": R(0.9, 1.4),
}
JAW = {"parts.jaw.proj": R(0.7, 1.1), "parts.jaw.drop": R(0.35, 0.5), "parts.jaw.gape": R(6.0, 14.0), "parts.jaw.slope": R(0.0, 0.1), "parts.jaw.teeth": R(0, 0), "parts.jaw.tooth": R(0.2, 0.32), "parts.jaw.up": R(0, 0)}
WHISK = {"parts.barbels.n": R(4, 4), "parts.barbels.len": R(0.5, 0.9), "parts.barbels.tip": R(0.1, 0.2), "parts.barbels.curl": R(0.2, 1.0)}
LURE = {"parts.lure.s": R(0.07, 0.1), "parts.lure.stalk": R(1.4, 2.2), "parts.lure.bulb": R(0.8, 1.1), "parts.lure.curl": R(0.5, 1.2)}


def _pal(body, fin, accent, iris="#ffcc59"):
    def h(c):
        return "#%02x%02x%02x" % tuple(max(0, min(255, round(v * 255))) for v in c)

    def hx(s):
        return [int(s[i : i + 2], 16) / 255 for i in (1, 3, 5)]

    def mix(a, b, t):
        return [a[i] * (1 - t) + b[i] * t for i in range(3)]

    b = hx(body)
    return {
        "back": h(mix(b, (0.08, 0.1, 0.16), 0.5)), "flank": body, "belly": h(mix(b, (1, 1, 0.94), 0.55)), "fin": fin, "accent": accent, "iris": iris, "pupil": "#1a1a2e",
        "sclera": "#e6e1d2", "lid": body, "glint": "#ffffff", "tooth": "#ece6d2", "mouth": "#7a2f36", "jaw": h(mix(b, (1, 1, 0.94), 0.35)), "arm": h(mix(b, (0.05, 0.05, 0.08), 0.2)),
        "sucker": "#efe3d0", "stalk": "#3a3a46", "bulb": "#88ffee", "barbel": h(mix(b, (1, 1, 0.9), 0.2)), "spike": "#d8d0b4", "plate": h(mix(b, (0.1, 0.08, 0.06), 0.35)),
    }


#: the genes whose ranges are widened per species: the shape and size genes that make two seeds look unlike
_WIDEN = ("body.height", "body.width", "body.taper", "body.peak", "body.nose_p", "body.nose", "body.tail", "body.pinch", "body.hump", "body.sag", "body.brow", "body.nt", "body.nb", "body.curve", "body.flick", "body.snout_up",
          ".h", ".len", ".lobe", ".fork", ".s0", ".s1", ".membrane", ".stalk", "len_m")
_CLAMP = {"body.peak": (0.2, 0.62), "body.nose_p": (1.0, 3.4), "body.nt": (1.5, 3.2), "body.nb": (1.4, 3.2), "body.taper": (0.5, 3.0), "body.nose": (0.06, 0.4), "body.tail": (0.05, 0.4), "body.pinch": (0.0, 0.7),
          "body.hump": (0.0, 0.5), "body.sag": (0.0, 0.35), "body.brow": (0.0, 0.35), "body.width": (0.25, 12.0), "body.height": (0.02, 1.0), "len_m": (0.1, 5.5), ".s0": (0.05, 0.9), ".s1": (0.12, 0.98), ".membrane": (0.05, 1.0), ".fork": (0.0, 0.8)}


def _widen(genes: dict, k: float) -> dict:
    out = {}
    for path, (lo, hi) in genes.items():
        if path.endswith("?") or path in INT_GENES or path.endswith(".theta") or path.endswith(".k") or path.endswith(".size") or path.endswith(".bulge") or ".tail.shape" in path:
            out[path] = (lo, hi)
            continue
        if any(path.endswith(w) or path == w for w in _WIDEN):
            c, half = (lo + hi) / 2, (hi - lo) / 2
            half = max(half * k, 0.02 * abs(c) * (k - 1))
            lo, hi = c - half, c + half
            for key, (a, b) in _CLAMP.items():
                if path.endswith(key) or path == key:
                    lo, hi = max(lo, a), min(hi, b)
        out[path] = (round(lo, 4), round(hi, 4))
    return out


EXTRAS = {
    "parts.dorsal2?": R(0.5), "parts.dorsal2.s0": R(0.6, 0.66), "parts.dorsal2.s1": R(0.7, 0.82), "parts.dorsal2.h": R(0.4, 1.0), "parts.dorsal2.membrane": R(0.3, 0.8),
    "parts.frill?": R(0.3), "parts.frill.s0": R(0.12, 0.2), "parts.frill.s1": R(0.6, 0.8), "parts.frill.h": R(0.18, 0.4), "parts.frill.membrane": R(0.5, 0.9),
    "parts.wart?": R(0.25), "parts.wart.h": R(0.03, 0.07), "parts.wart.step": R(2, 2),
    "parts.scutes?": R(0.2), "parts.scutes.h": R(0.15, 0.3), "parts.scutes.rows": R(3, 3),
    "body.bill?": R(0.2), "body.bill": R(0.4, 1.2),
    "body.rostrum?": R(0.12), "body.rostrum": R(0.07, 0.16),
    "body.snout_up?": R(0.3), "body.snout_up": R(0.2, 0.8),
}


def S(plan, base, over=None, extra=None, pal=None, skins=("plain",), skin=None, widen=2.0, extras=True):
    genes = dict(base)
    genes.update(over or {})
    genes = _widen(genes, widen)
    genes.update(extra or {})
    if extras and plan in ("round", "armoured"):
        for k, v in EXTRAS.items():
            if k.rstrip("?") in genes or (k.endswith("?") and k[:-1] in genes):
                continue  # the species already decides this gene
            genes.setdefault(k, v)
    return {"plan": plan, "genes": genes, "palette": pal, "skins": skins, "skin": skin or {}}


SPECIES: dict[str, dict] = {
    "perch": S("round", ROUND, pal=_pal("#a8b257", "#c75c33", "#38421f"), skins=("bars", "stripes", "plain"), skin=dict(bars=6, lateral=False, scales=1.0)),
    "pike": S("round", ROUND, {"body.height": R(0.14, 0.19), "body.peak": R(0.5, 0.6), "body.nose_p": R(1.2, 1.8), "len_m": R(0.5, 0.9), "body.hump": R(0, 0.05), "parts.dorsal.s0": R(0.66, 0.7), "parts.dorsal.s1": R(0.8, 0.86), "parts.anal.s0": R(0.66, 0.7), "parts.anal.s1": R(0.8, 0.86), "parts.tail.shape": R(0, 0)},
              {**JAW, "parts.jaw.teeth": R(5, 7), "parts.jaw.tooth": R(0.22, 0.34), "parts.jaw.proj": R(1.0, 1.5)}, _pal("#75854c", "#575c33", "#ebe0b2"), ("spots", "stripes", "mottle")),
    "catfish": S("round", ROUND, {"body.height": R(0.16, 0.22), "body.width": R(0.8, 1.1), "body.peak": R(0.3, 0.38), "body.hump": R(0, 0.1), "parts.dorsal.h": R(0.3, 0.5), "parts.tail.shape": R(1, 1)}, {**WHISK, "parts.barbels.n": R(4, 6)}, _pal("#bda89e", "#99807a", "#ebd6cc"), ("mottle", "plain", "spots")),
    "angler": S("round", ROUND, {"body.height": R(0.28, 0.35), "body.width": R(0.8, 1.0), "body.peak": R(0.42, 0.5), "body.hump": R(0, 0.1), "parts.eye.size": R(0.3, 0.4), "len_m": R(0.35, 0.6), "parts.tail.shape": R(1, 1), "parts.pectoral.len": R(0.6, 0.9), "parts.dorsal.h": R(0.5, 0.9)},
                {**JAW, "parts.jaw.teeth": R(6, 9), "parts.jaw.tooth": R(0.28, 0.42), "parts.jaw.proj": R(1.0, 1.5), "parts.jaw.gape": R(10.0, 20.0), **LURE}, _pal("#2a2a38", "#38404c", "#b2b8c7"), ("plain", "mottle")),
    "tuna": S("round", ROUND, {"body.height": R(0.2, 0.26), "len_m": R(0.8, 1.6), "body.peak": R(0.38, 0.46), "body.nose_p": R(1.2, 1.7), "body.pinch": R(0.4, 0.6), "body.nose": R(0.1, 0.14), "parts.tail.shape": R(2, 2), "parts.tail.len": R(1.3, 1.8), "parts.tail.lobe": R(1.0, 1.4), "parts.dorsal.s1": R(0.5, 0.56), "parts.dorsal.h": R(0.7, 1.0), "parts.pectoral.len": R(1.0, 1.5)},
              {"parts.finlets?": R(0.7, 0.7), "parts.finlets.n": R(4, 5), "parts.finlets.h": R(0.18, 0.3), **JAW, "parts.jaw.proj": R(0.2, 0.5), "parts.jaw.drop": R(0.25, 0.35), "parts.jaw.gape": R(2.0, 6.0)}, _pal("#2e4770", "#e6cc4c", "#ccd9e6"), ("plain", "stripes")),
    "carp": S("round", ROUND, {"body.height": R(0.24, 0.3), "body.hump": R(0.18, 0.36), "body.peak": R(0.4, 0.5), "body.nose_p": R(2.0, 3.0), "parts.dorsal.s0": R(0.28, 0.32), "parts.dorsal.s1": R(0.6, 0.7), "parts.dorsal.h": R(0.5, 0.8), "parts.tail.shape": R(0, 0)}, {**WHISK, "parts.barbels.n": R(2, 2), "parts.barbels.len": R(0.4, 0.6)}, _pal("#6b8038", "#80662e", "#dbc266"), ("blotch", "mottle", "spots")),
    "billfish": S("round", ROUND, {"body.height": R(0.17, 0.22), "len_m": R(1.2, 2.6), "body.rostrum": R(0.18, 0.28), "body.peak": R(0.42, 0.5), "body.pinch": R(0.4, 0.6), "parts.tail.shape": R(2, 2), "parts.tail.len": R(1.3, 1.8), "parts.tail.lobe": R(1.1, 1.5), "parts.dorsal.s0": R(0.4, 0.46), "parts.dorsal.s1": R(0.7, 0.8), "parts.dorsal.h": R(1.4, 2.4), "parts.dorsal.membrane": R(0.7, 0.95), "parts.pectoral.s": R(0.4, 0.46), "parts.anal.s0": R(0.7, 0.74), "parts.anal.s1": R(0.8, 0.84), "parts.eye.k": R(0.4, 0.55)}, {"parts.finlets?": R(0.5, 0.5), "parts.finlets.n": R(4, 5), "parts.finlets.h": R(0.18, 0.28)}, _pal("#2f5880", "#3a5070", "#cfd8e4"), ("stripes", "plain")),
    "lionfish": S("round", ROUND, {"body.height": R(0.22, 0.3), "len_m": R(0.2, 0.35), "parts.dorsal.s0": R(0.26, 0.3), "parts.dorsal.s1": R(0.62, 0.7), "parts.dorsal.h": R(1.6, 2.6), "parts.dorsal.membrane": R(0.08, 0.2), "parts.pectoral.len": R(1.8, 2.8), "parts.pectoral.s": R(0.26, 0.3), "parts.tail.shape": R(1, 3), "parts.pelvic.len": R(1.0, 1.6), "body.brow": R(0.08, 0.25)}, {**WHISK, "parts.barbels.n": R(2, 2), "parts.barbels.len": R(0.3, 0.5)}, _pal("#b8463a", "#c9a56a", "#f0e4d0"), ("bars", "stripes")),
    "plaice": S("flat", FLAT, pal=_pal("#a89868", "#b8a070", "#6a5a3a"), skins=("mottle", "spots", "blotch")),
    "oarfish": S("ribbon", RIBBON, extra={**JAW, "parts.jaw.teeth": R(0, 0), "parts.jaw.proj": R(0.5, 0.8), "parts.jaw.drop": R(0.3, 0.4), "parts.jaw.gape": R(4.0, 10.0)}, pal=_pal("#c8ccd4", "#e04058", "#6a707c"), skins=("plain", "mottle", "stripes")),
    "eel": S("eel", EEL, pal=_pal("#706b4c", "#4c4733", "#9e945c"), skins=("mottle", "blotch", "stripes")),
    "moray": S("eel", EEL, {"body.height": R(0.12, 0.16), "len_m": R(0.8, 1.6), "parts.dorsal.s0": R(0.08, 0.14), "parts.dorsal.h": R(0.5, 0.9)}, {**JAW, "parts.jaw.teeth": R(6, 8), "parts.jaw.tooth": R(0.25, 0.4), "parts.jaw.proj": R(0.6, 1.0), "parts.jaw.gape": R(10.0, 20.0)}, _pal("#6a7a3a", "#4a5a2a", "#e0c040"), ("mottle", "spots", "blotch")),
    "hammerhead": S("hammerhead", HAMMER, pal=_pal("#6a7a88", "#6a7a88", "#c0c8d0"), skins=("plain", "gradient")),
    "puffer": S("globe", GLOBE, pal=_pal("#c8b070", "#a09050", "#503820"), skins=("spots", "mottle", "stripes")),
    "sunfish": S("disc", DISC, {"len_m": R(0.5, 1.2), "parts.tail.len": R(0.2, 0.35), "parts.tail.shape": R(3, 3), "parts.dorsal.s0": R(0.5, 0.58), "parts.dorsal.s1": R(0.72, 0.8), "parts.dorsal.h": R(1.4, 2.4), "parts.anal.s0": R(0.5, 0.58), "parts.anal.s1": R(0.7, 0.78), "parts.anal.h": R(1.2, 2.0)}, pal=_pal("#9aa4ae", "#8a949e", "#c8ced4"), skins=("mottle", "plain")),
    "angelfish": S("disc", DISC, {"body.height": R(0.6, 0.8), "parts.pelvic.len": R(0.8, 1.4), "parts.dorsal.h": R(1.0, 1.8)}, pal=_pal("#e0c860", "#e8d890", "#202028"), skins=("bars", "stripes")),
    "sturgeon": S("armoured", ARMOURED, extra={**WHISK, "parts.barbels.n": R(4, 4), "parts.barbels.len": R(0.3, 0.5), **JAW, "parts.jaw.teeth": R(0, 0), "parts.jaw.proj": R(0.0, 0.2), "parts.jaw.drop": R(0.3, 0.4), "parts.jaw.gape": R(4.0, 8.0)}, pal=_pal("#6a6a58", "#585848", "#a0a088"), skins=("plain", "mottle", "gradient")),
    "skate": S("ray", RAY, pal=_pal("#8a7a5a", "#7a6a4a", "#d0c090"), skins=("mottle", "spots", "eyespot")),
    "seahorse": S("seahorse", SEAHORSE, pal=_pal("#d8a040", "#e0b860", "#704010"), skins=("stripes", "spots", "mottle")),
    "squid": S("squid", SQUID, pal=_pal("#c07080", "#a05868", "#f0c0c8"), skins=("spots", "mottle", "gradient")),
    "mawfish": S("round", ROUND, {"body.height": R(0.2, 0.26), "len_m": R(0.4, 0.8), "body.peak": R(0.3, 0.38), "body.nose_p": R(1.4, 2.0), "parts.eye.size": R(0.32, 0.42), "parts.dorsal.h": R(0.5, 0.9), "parts.tail.shape": R(0, 1)},
                 {**JAW, "parts.jaw.teeth": R(6, 8), "parts.jaw.tooth": R(0.3, 0.45), "parts.jaw.proj": R(0.8, 1.2), "parts.jaw.gape": R(14.0, 24.0), "parts.tent.n": R(4, 6), "parts.tent.band": R(1, 1), "parts.tent.len": R(1.4, 2.4), "parts.tent.tip": R(0.1, 0.2), "parts.tent.curl": R(0.3, 1.2), "parts.tent.club": R(0.0, 0.5), "parts.tent.suck": R(0.0, 0.0)}, _pal("#242c3a", "#303848", "#7ab8d0"), ("plain", "mottle")),
}
PLANS = tuple(sorted({sp["plan"] for sp in SPECIES.values()}, key=lambda p: ["round", "flat", "ribbon", "eel", "hammerhead", "globe", "disc", "armoured", "ray", "seahorse", "squid"].index(p)))


def _set(d: dict, path: str, val):
    *head, last = path.split(".")
    for k in head:
        d = d.setdefault(k, {})
    d[last] = val


def _jitter(hexc: str, k: float, hue: float = 0.0, sat: float = 0.0) -> str:
    """Lightness `k`, a hue turn of `hue` (0..1 of the wheel) and a saturation change, so seeds differ in colour too."""
    import colorsys

    r, g_, b = (int(hexc[i : i + 2], 16) / 255 for i in (1, 3, 5))
    h, s_, v = colorsys.rgb_to_hsv(r, g_, b)
    r, g_, b = colorsys.hsv_to_rgb((h + hue) % 1.0, max(0.0, min(1.0, s_ * (1 + sat))), max(0.0, min(1.0, v * (1 + k))))
    return "#%02x%02x%02x" % (round(r * 255), round(g_ * 255), round(b * 255))


def draw(species: str, seed: int, gifts=None) -> dict:
    """One catch: every gene is `lo + (hi - lo) * unit(seed, path)`. `gifts` is a list of kind names or {gene, x} dicts."""
    sp = SPECIES[species] if species in SPECIES else game_species(species)
    g = {"v": VERSION, "species": species, "seed": seed, "plan": sp["plan"], "body": {}, "parts": {}}
    gates = {p[:-1]: lo for p, (lo, hi) in sp["genes"].items() if p.endswith("?")}
    for path, (lo, hi) in sp["genes"].items():
        if path.endswith("?"):
            continue
        group = ".".join(path.split(".")[:2])
        if group in gates and unit(seed, group + "?") >= gates[group]:
            continue
        val = lo + (hi - lo) * unit(seed, path)
        val = int(round(val)) if path in INT_GENES else round(val, 6)
        _set(g, path, val)
    jit = sp.get("jitter", 1.0)  # a game species keeps its named colour: its catches vary on the client (`catchShade`)
    k = (unit(seed, "palette") - 0.5) * 0.3 * jit
    hue, sat = (unit(seed, "palette.hue") - 0.5) * 0.14 * jit, (unit(seed, "palette.sat") - 0.5) * 0.5 * jit
    tinted = ("flank", "back", "belly", "fin", "accent", "jaw", "arm", "lid", "barbel", "plate", "spike")
    g["palette"] = {role: (_jitter(c, k, hue, sat) if role in tinted else c) for role, c in sp["palette"].items()}
    kinds = sp["skins"]
    sk = dict(sp["skin"])
    sk["kind"] = kinds[int(unit(seed, "skin.kind") * len(kinds)) % len(kinds)]
    sk["seed"] = int(unit(seed, "skin.seed") * 2**31) or 1
    sk["density"] = round(0.7 + 0.6 * unit(seed, "skin.density"), 4)
    sk["tint"] = [round((unit(seed, "skin.tint.%d" % i) - 0.5) * 0.12, 4) for i in range(3)]
    sk.setdefault("bars", 4 + int(unit(seed, "skin.bars") * 4))
    sk.setdefault("lateral", unit(seed, "skin.lateral") < 0.5)
    sk.setdefault("scales", round(0.4 + 1.0 * unit(seed, "skin.scales"), 3))
    g["skin"] = sk
    g["finish"] = {"kind": sp.get("finish", "none"), "gloss": round(unit(seed, "finish.gloss"), 3)}
    g["gift"] = [x if isinstance(x, dict) else {"gene": x, "x": 1.0} for x in (gifts or [])]
    g["behave"] = {}
    return g


def game_species(slug: str) -> dict:
    """A catchable game species (`game.GAME`, one per `fish_loot.FISH_TABLE` slug), drawn by the same `draw`."""
    from .game import GAME

    return GAME[slug]


def roll_gifts(seed: int, n: int) -> list[dict]:
    """`n` distinct mutations for a seed (n = 1 a mutant, 2 a legend): kind and expression x in [0.5, 1)."""
    kinds = sorted(GIFTS)
    out: list[dict] = []
    i = 0
    while len(out) < n:
        kind = kinds[int(unit(seed, "gift.kind.%d" % i) * len(kinds))]
        i += 1
        if all(o["gene"] != kind for o in out):
            out.append({"gene": kind, "x": round(0.5 + 0.5 * unit(seed, "gift.x.%d" % len(out)), 3)})
    return out


# ----------------------------------------------------------------------------- mutations
def _mul(g, path, k, default=None):
    node = g
    *head, last = path.split(".")
    for key in head:
        node = node.get(key)
        if node is None:
            return False
    if last not in node:
        if default is None:
            return False
        node[last] = default
    node[last] = round(node[last] * k, 6)
    return True


def _fanged(g, x):
    if g["plan"] not in ("round", "ribbon", "eel"):
        return
    jaw = g["parts"].setdefault("jaw", {"proj": 0.9, "drop": 0.4, "gape": 10.0, "slope": 0.0, "teeth": 0, "tooth": 0.25, "up": 0})
    jaw["teeth"] = max(jaw.get("teeth", 0), 4) + int(round(4 * x))
    jaw["tooth"] = round(jaw.get("tooth", 0.25) * (1 + 1.6 * x), 6)


def _bearded(g, x):
    if g["plan"] not in ("round", "ribbon", "hammerhead", "armoured"):
        return
    b = g["parts"].setdefault("barbels", {"n": 0, "len": 0.5, "tip": 0.15, "curl": 0.5})
    b["n"] = min(8, max(b["n"], 2) + int(round(4 * x)))
    b["len"] = round(b["len"] * (1 + 1.0 * x), 6)


def _lure(g, x):
    if g["plan"] == "round" and "lure" not in g["parts"]:
        g["parts"]["lure"] = {"s": 0.085, "stalk": round(0.9 + 0.9 * x, 6), "bulb": round(0.3 + 0.2 * x, 6), "curl": 0.9}


def _cyclops(g, x):
    g["parts"]["eye"]["cyclops"] = 1
    _mul(g, "parts.eye.size", 1 + 0.3 * x)


def _glow(g, x):
    g["glow"] = round(x, 4)
    g["skin"]["kind"] = "stars"
    g["palette"]["glow"] = "#66ffe0"
    g["palette"]["accent"] = "#66ffe0"  # the photophores are the star pattern, lit


def _finish(kind):
    def f(g, x):
        g["finish"] = {**g["finish"], "kind": kind, "x": round(x, 4), "metal": ("gold", "silver", "copper")[int(unit(g["seed"], "finish.metal") * 3) % 3]}

    return f


GIFTS = {
    "gigantism": lambda g, x: g.update(len_m=round(g["len_m"] * (1 + 1.5 * x), 6)),
    "dwarf": lambda g, x: g.update(len_m=round(g["len_m"] * (1 - 0.5 * x), 6)),
    "fanged": _fanged,
    "bearded": _bearded,
    "cyclops": _cyclops,
    "bigeye": lambda g, x: _mul(g, "parts.eye.size", 1 + 2.0 * x),
    "winged": lambda g, x: _mul(g, "parts.pectoral.len", 1 + 1.6 * x),
    "spined": lambda g, x: _mul(g, "parts.dorsal.h", 1 + 1.2 * x) or _mul(g, "parts.crest.h", 1 + 1.2 * x),
    "lure": _lure,
    "bioluminescent": _glow,
    "shiny": _finish("shiny"),
    "shimmer": _finish("shimmer"),
    "pearl": _finish("pearl"),
    "holographic": _finish("holo"),
}


def effective(g: dict, strength: float) -> dict:
    """The genome the builder reads: gifts applied at `strength` x their expression. Strength 0 is the plain species.

    A gift acts on whole parts: it scales or adds a part with all its children, never strips one to a fragment."""
    e = copy.deepcopy(g)
    for gift in g["gift"]:
        x = gift["x"] * strength
        if x > 1e-9:
            GIFTS[gift["gene"]](e, x)
    return e
