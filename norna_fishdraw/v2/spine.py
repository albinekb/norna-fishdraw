"""The spine and its cross-section rings.

The spine is a path through 3-space (straight along +Z for most plans: nose +Z, back +Y, metres, centred on the middle
of the body; curled for a seahorse). Each `Ring` is a cross-section frame on it: a centre, a pitch and yaw, and a
superellipse with its own upper half (`ht`, exponent `nt`) and lower half (`hb`, `nb`) and half-width `w`: a humped back
is `ht > hb`, a sagging belly `hb > ht`, a triangular keel a small `nb`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass



def thetas(half) -> list[float]:
    """Ring vertex angles in radians from a half list in degrees over [0, 180] (both ends included), mirrored round."""
    deg = list(half) + [360.0 - a for a in reversed(half[1:-1])]
    return [math.radians(a) for a in deg]


UNIFORM = thetas([0, 30, 60, 90, 120, 150, 180])  # a vertex every 30 degrees: back, belly and both flanks always there


@dataclass(frozen=True)
class Ring:
    s: float
    cx: float
    cy: float
    cz: float
    ht: float
    hb: float
    w: float
    nt: float = 2.2
    nb: float = 2.2
    pitch: float = 0.0  # tilt of the cross-section plane about X (a curled spine)
    yaw: float = 0.0  # and about Y

    @property
    def centre(self):
        return (self.cx, self.cy, self.cz)

    @property
    def r(self) -> float:
        """The local body radius: what every part size is a fraction of."""
        return max(0.5 * (self.ht + self.hb), self.w)

    def point(self, theta: float):
        c, s = math.cos(theta), math.sin(theta)
        h, n = (self.ht, self.nt) if c >= 0 else (self.hb, self.nb)
        e = 2.0 / n
        y = h * math.copysign(abs(c) ** e, c) if abs(c) > 1e-12 else 0.0
        x = self.w * math.copysign(abs(s) ** e, s) if abs(s) > 1e-12 else 0.0
        cp, sp, cy, sy = math.cos(self.pitch), math.sin(self.pitch), math.cos(self.yaw), math.sin(self.yaw)
        y1, z1 = y * cp, y * sp
        x2, z2 = x * cy + z1 * sy, -x * sy + z1 * cy
        return (self.cx + x2, self.cy + y1, self.cz + z2)


def envelope(s: float, peak: float, nose_p: float, nose: float, tail: float, k: float) -> float:
    """0..1 body bulk along the spine: a superellipse quarter up to `peak` (nose_p 1 pointed, 2 round, 4 blunt), then a
    power-law taper, each floored so no ring collapses."""
    if s < peak:
        u = 1.0 - s / peak
        return max((1.0 - u**nose_p) ** (1.0 / nose_p), nose)
    u = (s - peak) / (1.0 - peak)
    return max(1.0 - u**k, tail)


def stations(count: int, power: float = 1.7) -> list[float]:
    """Ring stations nose 0 -> tail 1, denser toward the head so the head's cells are about square (room for sockets)."""
    return [(k / (count - 1)) ** power for k in range(count)]
