"""The body plans, one profile engine: genes shape the rings, the plan fixes its character.

Round (a spindle), flat (a disc lying on its side, both eyes on top), ribbon and eel (long, thin), hammerhead (a thin
cephalofoil plate), globe (a puffer), disc (a tall compressed sunfish), armoured (a sturgeon), ray (flat, with wings
and a whip tail), seahorse (a curled spine, standing), squid (mantle, head, arms). The `body` genes are fractions of
body length: height, width (w/h of the cross-section), taper, peak (where the body is deepest), nose_p (1 pointed, 2
round, 4 blunt), nose and tail floors, hump and sag of back and belly, section exponents `nt` and `nb` (a small `nb` is
a keel), pinch (peduncle), snout_up, bill (duckbill), brow (forehead), rostrum (a sword), curve and flick (lateral arc
and tail bend), curl (seahorse).
"""

from __future__ import annotations

import math

from .spine import UNIFORM, Ring, envelope, stations, thetas


#: per plan: ring count, station power, vertex angles, uv mode ('side' or 'top'), the jaw's home
FLAT_THETAS = thetas([0, 3, 9, 18, 45, 90, 135, 180])
DISC_THETAS = thetas([0, 30, 55, 70, 80, 90, 100, 110, 125, 150, 180])  # fine round the flanks: a tall thin body's eye socket
PLANS = {
    "round": dict(R=14, power=1.7, thetas=UNIFORM, uv="side"),
    "flat": dict(R=14, power=1.4, thetas=FLAT_THETAS, uv="top"),
    "ribbon": dict(R=20, power=2.4, thetas=UNIFORM, uv="side"),
    "eel": dict(R=20, power=2.3, thetas=UNIFORM, uv="side"),
    "hammerhead": dict(R=14, power=1.5, thetas=UNIFORM, uv="side"),
    "globe": dict(R=14, power=1.6, thetas=UNIFORM, uv="side"),
    "disc": dict(R=14, power=1.6, thetas=DISC_THETAS, uv="side"),
    "armoured": dict(R=16, power=1.5, thetas=UNIFORM, uv="side"),
    "ray": dict(R=14, power=1.4, thetas=FLAT_THETAS, uv="top"),
    "seahorse": dict(R=20, power=2.0, thetas=UNIFORM, uv="side"),
    "squid": dict(R=16, power=1.5, thetas=UNIFORM, uv="side"),
}
ORDER = tuple(PLANS)

_HEAD_W = (0.62, 1.0, 0.5)  # hammerhead cephalofoil half-span at rings 0..2, fraction of the full half-span
_HEAD_H = (0.4, 0.5, 0.75)  # and its thinness against the trunk


def _g(b, key, default):
    return b.get(key, default)


def _smooth(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def _spine_path(st, L, curl):
    """Seahorse: a head tube pointing forward (+Z), a neck bend, a body hanging down and a tail curling forward again.
    The tangent nose to tail is (0, -sin a, -cos a): a = 0 runs back along -Z, pi/2 runs down. -> [(cy, cz, a)]."""
    pts = []
    y = z = 0.0
    for k, s in enumerate(st):
        a = _smooth((s - 0.1) / 0.2) * (math.pi / 2) + curl * _smooth((s - 0.62) / 0.38) * (1.4 * math.pi)
        pts.append((y, z, a))
        if k + 1 < len(st):
            ds = st[k + 1] - s
            y += -math.sin(a) * L * ds
            z += -math.cos(a) * L * ds
    return pts


def body_rings(g):
    """-> (rings, thetas, uv mode). The one profile engine over the genome's `body` genes."""
    L, b, plan = g["len_m"], g["body"], g["plan"]
    spec = PLANS[plan]
    st = stations(spec["R"], spec["power"])
    height, width = b["height"], b["width"]
    hh = 0.5 * height * L
    peak, nose_p = _g(b, "peak", 0.36), _g(b, "nose_p", 2.0)
    nose_f, tail_f, k = _g(b, "nose", 0.14), _g(b, "tail", 0.12), b["taper"]
    rost = _g(b, "rostrum", 0.0)
    path = _spine_path(st, L, _g(b, "curl", 0.0)) if plan == "seahorse" else None
    rings = []
    for idx, s in enumerate(st):
        if rost > 0 and s < rost:
            e = 0.1 * (0.6 + 0.4 * s / rost)
        else:
            sb = (s - rost) / (1.0 - rost) if rost > 0 else s
            e = envelope(sb, peak, nose_p, nose_f, tail_f, k)
        e *= 1.0 - _g(b, "pinch", 0.0) * math.exp(-(((s - 0.88) / 0.06) ** 2))
        e = max(e, 0.05)
        h = hh * e
        ht = hb = h
        ht *= 1.0 + _g(b, "hump", 0.0) * math.exp(-(((s - _g(b, "hump_at", 0.38)) / 0.14) ** 2))
        hb *= 1.0 + _g(b, "sag", 0.0) * math.exp(-(((s - 0.5) / 0.16) ** 2))
        ht *= 1.0 + _g(b, "brow", 0.0) * math.exp(-(((s - 0.1) / 0.06) ** 2))
        w = h * width
        bill = _g(b, "bill", 0.0) * _smooth(1.0 - s / 0.14)
        w *= 1.0 + bill
        ht *= 1.0 - 0.45 * bill
        hb *= 1.0 - 0.45 * bill
        cy = _g(b, "snout_up", 0.0) * hh * max(0.0, 1.0 - s / 0.2) ** 2
        cx = _g(b, "curve", 0.0) * L * math.sin(math.pi * s) + _g(b, "flick", 0.0) * L * max(0.0, s - 0.55) ** 2
        cz = (0.5 - s) * L
        pitch = 0.0
        if path:
            cy, cz, alpha = path[idx]
            pitch = -alpha
        nt, nb = _g(b, "nt", 2.2), _g(b, "nb", 2.2)
        if plan == "hammerhead" and idx < 3:
            span = 0.5 * b["head"] * L
            ht = hb = h * _HEAD_H[idx]
            w = max(w, span * _HEAD_W[idx])
            nt = nb = 3.2
        rings.append(Ring(s, cx, cy, cz, ht, hb, w, nt, nb, pitch))
    if path:  # recentre on the middle of the spine's bounding box, nose +Z stays nose
        ys = [r.cy for r in rings]
        zs = [r.cz for r in rings]
        oy, oz = (max(ys) + min(ys)) / 2, (max(zs) + min(zs)) / 2
        rings = [Ring(r.s, r.cx, r.cy - oy, r.cz - oz, r.ht, r.hb, r.w, r.nt, r.nb, r.pitch) for r in rings]
    return rings, spec["thetas"], spec["uv"]
