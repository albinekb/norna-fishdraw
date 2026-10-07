"""Rings to a watertight body: a quad per lattice cell split into two triangles, a fan cap at each end.

Parts that are welded to the body ask for it here: a `hole` removes a vertex and its six faces (an eye socket, a
tentacle root) leaving a hexagon of the body's own vertices to build from; a `cell_hole` removes one cell (a scute, a
spike). `recess` pulls a hole's rim inward, the socket. Everything else stays one smooth lofted surface.
"""

from __future__ import annotations

from ..lift3d import Mesh
from .spine import Ring
from .surface import Grid, add, cross, dot, mean, mul, norm, sub



def loft(rings: list[Ring], thetas: list[float], uvfn, holes=None, cell_holes=frozenset(), recess=None, uv_under=True):
    """-> (Grid, Mesh). `holes`: {(i, j)} vertices to leave open; `recess`: {(i, j): depth} rim pull-ins (metres)."""
    holes = holes or {}
    R, K = len(rings), len(thetas)
    V = [[r.point(t) for t in thetas] for r in rings]
    # sockets: pull each hole's rim inward along its own radial, once per vertex (deepest wins)
    pull: dict = {}
    for (i, j), depth in (recess or {}).items():
        for (ri, rj) in ((i, j + 1), (i + 1, j + 1), (i + 1, j), (i, j - 1), (i - 1, j - 1), (i - 1, j)):
            k = (ri, rj % K)
            pull[k] = max(pull.get(k, 0.0), depth)
    for (ri, rj), depth in pull.items():
        c = rings[ri].centre
        V[ri][rj] = sub(V[ri][rj], mul(norm(sub(V[ri][rj], c)), depth))

    def cell_tris(i, j):
        j1 = (j + 1) % K
        return [((i, j), (i, j1), (i + 1, j1)), ((i, j), (i + 1, j1), (i + 1, j))]

    # one winding for the whole lattice, chosen by the fattest ring's flank facing away from its own centre
    fat = max(range(1, R - 1), key=lambda i: rings[i].r)
    t0 = [V[a][b] for a, b in cell_tris(fat, 0)[0]]
    flip = dot(cross(sub(t0[1], t0[0]), sub(t0[2], t0[0])), sub(mean(t0), rings[fat].centre)) < 0
    if flip:
        def cell_tris(i, j, _ct=cell_tris):  # noqa: F811
            return [(t[0], t[2], t[1]) for t in _ct(i, j)]

    acc = [[(0.0, 0.0, 0.0)] * K for _ in range(R)]
    faces = []
    for i in range(R - 1):
        out = mean([rings[i].centre, rings[i + 1].centre])
        for j in range(K):
            for tri in cell_tris(i, j):
                p = [V[a][b] for a, b in tri]
                n = cross(sub(p[1], p[0]), sub(p[2], p[0]))
                for a, b in tri:
                    acc[a][b] = add(acc[a][b], n)
                faces.append((tri, out, (i, j)))
    N = [[norm(v) for v in row] for row in acc]

    r0, rl = rings[0], rings[-1]
    nose = add(r0.centre, mul(norm(sub(r0.centre, rings[1].centre)), 0.3 * r0.r))
    tail = add(rl.centre, mul(norm(sub(rl.centre, rings[-2].centre)), 0.0))
    mesh = Mesh()
    for tri, out, cell in faces:
        if cell in cell_holes or any(v in holes for v in tri):
            continue
        p = [V[a][b] for a, b in tri]
        nrm = norm(cross(sub(p[1], p[0]), sub(p[2], p[0])))
        role = "under" if nrm[1] < -0.3 else "flank"
        mesh.add(role, *p, uv=tuple(uvfn(a, b) for a, b in tri) if (uv_under or role != "under") else None)
    # caps: a fan whose winding continues the lattice's: it must use each ring edge opposite to the cell beside it
    for j in range(K):
        j1 = (j + 1) % K
        p, q = ((0, j1), (0, j)) if not flip else ((0, j), (0, j1))  # the nose ring edge, against the lattice's direction
        mesh.add("flank", nose, V[p[0]][p[1]], V[q[0]][q[1]], uv=((0.0, 0.5), uvfn(*p), uvfn(*q)))
        p, q = ((R - 1, j), (R - 1, j1)) if not flip else ((R - 1, j1), (R - 1, j))
        mesh.add("flank", tail, V[p[0]][p[1]], V[q[0]][q[1]], uv=((1.0, 0.5), uvfn(*p), uvfn(*q)))
    grid = Grid(rings, thetas, V, N, nose, tail)
    grid.flip = flip
    return grid, mesh


def surviving_edges(R: int, K: int, holes, cell_holes=frozenset()) -> set:
    """The lattice edges that still have a face after the holes are cut: a part's root chain may only use these."""
    out = set()
    for i in range(R - 1):
        for j in range(K):
            if (i, j) in cell_holes:
                continue
            j1 = (j + 1) % K
            for tri in (((i, j), (i, j1), (i + 1, j1)), ((i, j), (i + 1, j1), (i + 1, j))):
                if any(v in holes for v in tri):
                    continue
                out.update((frozenset((tri[0], tri[1])), frozenset((tri[1], tri[2])), frozenset((tri[2], tri[0]))))
    return out
