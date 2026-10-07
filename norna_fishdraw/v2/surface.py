"""The lattice every part is welded to: ring i x vertex j, with exact vertex tuples shared by body and parts.

`Grid.V[i][j]` are the body's own vertices; a part's root is a chain of these same tuples (never a point computed
beside them), so body and part share vertices and every root edge is a body edge. `at(SurfacePoint)` lands exactly on
the body's triangles for anything that needs a point between vertices (tests, the validator's probes).
"""

from __future__ import annotations

import bisect
import math
from dataclasses import dataclass



def add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def mul(a, k):
    return (a[0] * k, a[1] * k, a[2] * k)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def norm(a):
    n = math.sqrt(dot(a, a))
    return (a[0] / n, a[1] / n, a[2] / n) if n > 1e-12 else (0.0, 1.0, 0.0)


def lerp(a, b, t):
    return a + (b - a) * t


def mid(a, b):
    return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2)


def mean(pts):
    n = len(pts)
    return (sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n, sum(p[2] for p in pts) / n)


@dataclass(frozen=True)
class SurfacePoint:
    s: float
    theta: float


class Grid:
    """Ring vertices `V[i][j]` (ring i nose to tail, vertex j round the ring) with smooth outward normals `N[i][j]`."""

    def __init__(self, rings, thetas, verts, normals, nose, tail):
        self.rings, self.thetas, self.V, self.N = rings, thetas, verts, normals
        self.nose, self.tail = nose, tail  # the cap-fan centre vertices
        self.R, self.K = len(verts), len(verts[0])
        self.S = [r.s for r in rings]

    def j(self, j):
        return j % self.K

    def v(self, i, j):
        return self.V[i][j % self.K]

    def n(self, i, j):
        return self.N[i][j % self.K]

    def radial(self, i, j):
        """Unit vector from ring i's centre out to vertex j: the 'out' of a socket or a root."""
        c = self.rings[i].centre
        return norm(sub(self.v(i, j), c))

    def snap(self, s: float, theta: float):
        """The lattice vertex (i, j) nearest the surface coordinate (s, theta)."""
        i = min(range(self.R), key=lambda k: abs(self.S[k] - s))
        t = theta % (2 * math.pi)
        j = min(range(self.K), key=lambda k: min(abs(self.thetas[k] - t), 2 * math.pi - abs(self.thetas[k] - t)))
        return i, j

    def rim(self, i, j):
        """The six body vertices around (i, j), cyclic: the hexagon left when the vertex and its six faces are removed."""
        v = self.v
        return [v(i, j + 1), v(i + 1, j + 1), v(i + 1, j), v(i, j - 1), v(i - 1, j - 1), v(i - 1, j)]

    def at(self, p: SurfacePoint):
        """-> (position on the skin, outward normal, unit tangent nose to tail), exactly on the body's triangles."""
        s = min(max(p.s, 0.0), 1.0)
        i = min(max(bisect.bisect_right(self.S, s) - 1, 0), self.R - 2)
        v = (s - self.S[i]) / (self.S[i + 1] - self.S[i])
        t = p.theta % (2 * math.pi)
        th = self.thetas
        j = min(max(bisect.bisect_right(th, t) - 1, 0), self.K - 1)
        j1 = (j + 1) % self.K
        t1 = th[j1] if j1 else 2 * math.pi
        u = (t - th[j]) / (t1 - th[j])
        ia = (i, j), (i, j1), (i + 1, j1), (i + 1, j)
        w = (1 - u, u - v, v, 0.0) if u >= v else (1 - v, 0.0, u, v - u)
        pos = nrm = (0.0, 0.0, 0.0)
        for (ri, ci), wk in zip(ia, w):
            if wk:
                pos = add(pos, mul(self.V[ri][ci], wk))
                nrm = add(nrm, mul(self.N[ri][ci], wk))
        a, b, c, d = (self.V[r][q] for r, q in ia)
        tan = norm(add(mul(sub(d, a), 1 - u), mul(sub(c, b), u)))
        return pos, norm(nrm), tan
