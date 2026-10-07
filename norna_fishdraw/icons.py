#!/usr/bin/env python3
"""Bag icons for the norna-fishdraw species, rendered from their own GLBs.

    python3 norna_fishdraw/icons.py            # render all
    python3 norna_fishdraw/icons.py grey-cod   # render some
    python3 norna_fishdraw/icons.py --check    # committed icons fresh against the GLBs?
    python3 norna_fishdraw/icons.py --sheet P  # also a contact sheet PNG at P

A software rasteriser over the GLB: the geometry, normals, UVs and PNG skins
are read straight out of `out/fish/<slug>.glb` (stdlib only, no
numpy, no GPU), so the same bytes give the same pixels on every box. Fixed
view like the painted set (`tools/paint_fish_icons.py`): flank to the eye,
turned a little toward the camera and tipped to show the back, nose up-right on
the tile's diagonal, warm key from the upper left and a cool rim from below,
drawn at 4x and box-filtered to 128 px, transparent background. Pillow only
encodes the webp (same quality settings as the painted icons).

The icons land in `out/icons/<slug>.webp` (override the directories with
`--models DIR` and `--out DIR`), and `out/icons/fishdraw-icons.json` records
the sha256 of each GLB an icon was rendered from plus RENDER_VERSION; `--check`
needs neither Pillow nor a GPU, it fails for a missing icon, a GLB that changed
since, or a render-version bump.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from norna_fishdraw.skin import png_decode  # noqa: E402

MODELS = ROOT / "out" / "fish"
OUT_DIR = ROOT / "out" / "icons"
MANIFEST = OUT_DIR / "fishdraw-icons.json"

#: Bump when any constant below (or the shading) changes: `--check` then asks for a re-render.
RENDER_VERSION = 1

ICON = 128
SS = 4
W = ICON * SS
BORDER = 0.04
LEAN = 36.0
YAW = -14.0
PITCH = 10.0
WEBP_QUALITY = 80
ALPHA_QUALITY = 60

KEY = (-0.45, 0.7, 0.55)
RIM = (0.35, -0.8, 0.3)
AMBIENT = 0.5
KEY_GAIN = 0.62
KEY_TINT = (1.0, 0.94, 0.84)
RIM_GAIN = 0.2
RIM_TINT = (0.55, 0.72, 1.0)


def _unit(v):
    n = math.sqrt(sum(c * c for c in v)) or 1.0
    return tuple(c / n for c in v)


KEY = _unit(KEY)
RIM = _unit(RIM)


def species() -> list[str]:
    return list(json.loads((MODELS / "fish.json").read_text())["species"])


def glb_sha(slug: str) -> str:
    return hashlib.sha256((MODELS / f"{slug}.glb").read_bytes()).hexdigest()


# ------------------------------------------------------------------ GLB read


def _s2l(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _qrot(q, v):
    """`v` turned by the unit quaternion `q` = (x, y, z, w)."""
    x, y, z, w = q
    vx, vy, vz = v
    tx, ty, tz = 2 * (y * vz - z * vy), 2 * (z * vx - x * vz), 2 * (x * vy - y * vx)
    return (vx + w * tx + y * tz - z * ty, vy + w * ty + z * tx - x * tz, vz + w * tz + x * ty - y * tx)


def _node_turn(gltf):
    """The rotation the mesh's node and its ancestors carry (a flatfish's catalogue pose), as a function of a vector.
    Identity for a node with none, so every fish baked without a pose renders exactly as before."""
    nodes = gltf.get("nodes") or []
    parent = {c: i for i, n in enumerate(nodes) for c in n.get("children", ())}
    chain = []
    i = next((k for k, n in enumerate(nodes) if n.get("mesh") == 0), None)
    while i is not None:
        if nodes[i].get("rotation"):
            chain.append(tuple(nodes[i]["rotation"]))
        i = parent.get(i)
    if not chain:
        return lambda v: tuple(v)

    def turn(v):
        for q in chain:  # the node's own rotation first, then each ancestor's
            v = _qrot(q, v)
        return v

    return turn


def read_glb(path: Path):
    """Triangles per primitive: (positions, normals, uvs|None, material dict, texture rows|None)."""
    data = path.read_bytes()
    jlen = struct.unpack("<I", data[12:16])[0]
    gltf = json.loads(data[20 : 20 + jlen])
    bin0 = 20 + jlen + 8
    blob = data[bin0:]

    def view_bytes(i):
        v = gltf["bufferViews"][i]
        return blob[v["byteOffset"] : v["byteOffset"] + v["byteLength"]]

    def accessor(i, fmt, n):
        a = gltf["accessors"][i]
        raw = view_bytes(a["bufferView"])
        stride = gltf["bufferViews"][a["bufferView"]].get("byteStride") or struct.calcsize(fmt) * n
        return [struct.unpack_from(fmt * n, raw, k * stride)[:n] for k in range(a["count"])]

    images = {}
    prims = []
    turn = _node_turn(gltf)
    for p in gltf["meshes"][0]["primitives"]:
        mat = gltf["materials"][p["material"]]
        pbr = mat["pbrMetallicRoughness"]
        at = p["attributes"]
        pos = [turn(v) for v in accessor(at["POSITION"], "f", 3)]
        nor = [turn(tuple(c / 127.0 for c in v)) for v in accessor(at["NORMAL"], "b", 3)]
        # NORMAL is VEC3 int8 with a 4-byte stride: read 3 and ignore the pad.
        uv = None
        tex = None
        if "TEXCOORD_0" in at:
            uv = [(u / 65535.0, v / 65535.0) for u, v in accessor(at["TEXCOORD_0"], "H", 2)]
            ti = pbr["baseColorTexture"]["index"]
            if ti not in images:
                img = gltf["images"][gltf["textures"][ti]["source"]]
                images[ti] = png_decode(view_bytes(img["bufferView"]))
            tex = images[ti]
        prims.append((pos, nor, uv, mat, tex))
    return prims


# ------------------------------------------------------------------ view


def _rot(deg):
    r = math.radians(deg)
    return math.cos(r), math.sin(r)


def make_view():
    cy, sy_ = _rot(YAW)
    cp, sp = _rot(PITCH)
    cl, sl = _rot(LEAN)

    def v(p):
        x, y, z = p
        x1 = x * cy + z * sy_
        z1 = -x * sy_ + z * cy
        sx, sy, d = z1, y, -x1
        sy2 = sy * cp + d * sp
        d2 = d * cp - sy * sp
        return (sx * cl - sy2 * sl, sx * sl + sy2 * cl, d2)

    return v


# ------------------------------------------------------------------ raster


def render(slug: str):
    """Return the supersampled premultiplied RGBA as four flat lists (r, g, b, a), W*W each."""
    return render_path(MODELS / f"{slug}.glb")


def render_path(path: Path):
    """The same render for any GLB path (the v2 side-by-side sheets use it, so v1 and v2 share one light and view)."""
    prims = read_glb(path)
    view = make_view()
    tris = []
    lo = [1e9, 1e9]
    hi = [-1e9, -1e9]
    for pos, nor, uv, mat, tex in prims:
        for t in range(0, len(pos), 3):
            vs = [view(pos[t + k]) for k in range(3)]
            ns = [view(nor[t + k]) for k in range(3)]
            for a in vs:
                lo[0] = min(lo[0], a[0])
                hi[0] = max(hi[0], a[0])
                lo[1] = min(lo[1], a[1])
                hi[1] = max(hi[1], a[1])
            n = _unit(tuple(sum(c[i] for c in ns) / 3 for i in range(3)))
            tris.append((vs, n, uv[t : t + 3] if uv else None, mat, tex))
    span = max(hi[0] - lo[0], hi[1] - lo[1])
    scale = W * (1 - 2 * BORDER) / span
    cx = (lo[0] + hi[0]) / 2
    cy = (lo[1] + hi[1]) / 2
    zbuf = [-1e9] * (W * W)
    R = [0.0] * (W * W)
    G = [0.0] * (W * W)
    B = [0.0] * (W * W)
    A = [0.0] * (W * W)
    for vs, n, uv, mat, tex in tris:
        pts = [((a[0] - cx) * scale + W / 2, W / 2 - (a[1] - cy) * scale, a[2] * scale) for a in vs]
        (x0, y0, z0), (x1, y1, z1), (x2, y2, z2) = pts
        den = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(den) < 1e-9:
            continue
        pbr = mat["pbrMetallicRoughness"]
        fac = pbr.get("baseColorFactor", [1, 1, 1, 1])
        emis = mat.get("emissiveFactor")
        two = mat.get("doubleSided", False)
        nx, ny, nz = n
        if two and nz < 0:
            nx, ny, nz = -nx, -ny, -nz
        key = max(0.0, nx * KEY[0] + ny * KEY[1] + nz * KEY[2])
        rim = max(0.0, nx * RIM[0] + ny * RIM[1] + nz * RIM[2])
        light = [AMBIENT + KEY_GAIN * key * KEY_TINT[i] for i in range(3)]
        cool = [RIM_GAIN * rim * RIM_TINT[i] for i in range(3)]
        flat = None if tex else tuple(min(1.0, _lin_to_s(fac[i])) for i in range(3))
        minx = max(0, int(math.floor(min(x0, x1, x2))))
        maxx = min(W - 1, int(math.ceil(max(x0, x1, x2))))
        miny = max(0, int(math.floor(min(y0, y1, y2))))
        maxy = min(W - 1, int(math.ceil(max(y0, y1, y2))))
        for py in range(miny, maxy + 1):
            fy = py + 0.5
            for px in range(minx, maxx + 1):
                fx = px + 0.5
                l0 = ((y1 - y2) * (fx - x2) + (x2 - x1) * (fy - y2)) / den
                l1 = ((y2 - y0) * (fx - x2) + (x0 - x2) * (fy - y2)) / den
                l2 = 1 - l0 - l1
                if l0 < -1e-9 or l1 < -1e-9 or l2 < -1e-9:
                    continue
                z = l0 * z0 + l1 * z1 + l2 * z2
                i = py * W + px
                if z <= zbuf[i]:
                    continue
                if tex:
                    u = l0 * uv[0][0] + l1 * uv[1][0] + l2 * uv[2][0]
                    v = l0 * uv[0][1] + l1 * uv[1][1] + l2 * uv[2][1]
                    th, tw = len(tex), len(tex[0])
                    tx = tex[min(th - 1, max(0, int(v * th)))][min(tw - 1, max(0, int(u * tw)))]
                    if tx[3] < 128:
                        continue
                    base = (tx[0] / 255.0 * fac[0], tx[1] / 255.0 * fac[1], tx[2] / 255.0 * fac[2])
                else:
                    base = flat
                zbuf[i] = z
                e = [0.0, 0.0, 0.0]
                if emis:
                    e = [base[k] * emis[k] * 0.45 for k in range(3)]
                R[i] = min(1.0, base[0] * light[0] + cool[0] + e[0])
                G[i] = min(1.0, base[1] * light[1] + cool[1] + e[1])
                B[i] = min(1.0, base[2] * light[2] + cool[2] + e[2])
                A[i] = 1.0
    return R, G, B, A


def _lin_to_s(c: float) -> float:
    return 12.92 * c if c <= 0.0031308 else 1.055 * (c ** (1 / 2.4)) - 0.055


def downsample(planes):
    """Box-filter SS x SS blocks to ICON x ICON, colour weighted by coverage; returns RGBA bytes."""
    R, G, B, A = planes
    out = bytearray()
    for y in range(ICON):
        for x in range(ICON):
            sa = sr = sg = sb = 0.0
            for dy in range(SS):
                base = (y * SS + dy) * W + x * SS
                for dx in range(SS):
                    a = A[base + dx]
                    if a:
                        sa += a
                        sr += R[base + dx]
                        sg += G[base + dx]
                        sb += B[base + dx]
            if sa == 0:
                out += b"\0\0\0\0"
            else:
                out += bytes(
                    (round(sr / sa * 255), round(sg / sa * 255), round(sb / sa * 255), round(sa / (SS * SS) * 255))
                )
    return bytes(out)


def icon_image(slug: str):
    from PIL import Image

    return Image.frombytes("RGBA", (ICON, ICON), downsample(render(slug)))


# ------------------------------------------------------------------ manifest / check


def manifest_now(slugs) -> dict:
    return {
        "generator": "norna_fishdraw/icons.py",
        "renderVersion": RENDER_VERSION,
        "icons": {s: {"glb": f"{MODELS.name}/{s}.glb", "glbSha256": glb_sha(s)} for s in slugs},
    }


def check() -> list[str]:
    """Reasons the committed icons are stale (empty when fresh). Stdlib only."""
    problems = []
    slugs = species()
    try:
        have = json.loads(MANIFEST.read_text())
    except (OSError, ValueError):
        return [f"{MANIFEST} missing or unreadable; run icons.py"]
    if have.get("renderVersion") != RENDER_VERSION:
        problems.append(f"renderVersion {have.get('renderVersion')} != {RENDER_VERSION}")
    for s in slugs:
        f = OUT_DIR / f"{s}.webp"
        if not f.exists():
            problems.append(f"{s}: no icon at {f}")
            continue
        raw = f.read_bytes()[:30]
        if raw[:4] != b"RIFF" or raw[8:12] != b"WEBP":
            problems.append(f"{s}: not a webp")
        row = have.get("icons", {}).get(s)
        if not row or row.get("glbSha256") != glb_sha(s):
            problems.append(f"{s}: rendered from an older glb; run icons.py {s}")
    for s in have.get("icons", {}):
        if s not in slugs:
            problems.append(f"{s}: manifest row for a species that is gone")
    return problems


def main(argv: list[str]) -> int:
    global MODELS, OUT_DIR, MANIFEST
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("species", nargs="*")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--sheet", type=Path)
    ap.add_argument("--models", type=Path, help=f"directory of <slug>.glb + fish.json (default {MODELS})")
    ap.add_argument("--out", type=Path, help=f"icon directory (default {OUT_DIR})")
    args = ap.parse_args(argv)
    if args.models:
        MODELS = args.models
    if args.out:
        OUT_DIR = args.out
        MANIFEST = OUT_DIR / "fishdraw-icons.json"
    if args.check:
        problems = check()
        for p in problems:
            print("stale:", p)
        print("fishdraw icons fresh" if not problems else f"{len(problems)} stale")
        return 1 if problems else 0
    all_slugs = species()
    unknown = [s for s in args.species if s not in all_slugs]
    if unknown:
        print("unknown species:", ", ".join(unknown))
        return 2
    slugs = args.species or all_slugs
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        have = json.loads(MANIFEST.read_text())
    except (OSError, ValueError):
        have = {}
    man = manifest_now(slugs)
    if have.get("renderVersion") == RENDER_VERSION:
        for s in all_slugs:
            if s not in slugs and s in have.get("icons", {}):
                man["icons"][s] = have["icons"][s]
    images = []
    for s in slugs:
        img = icon_image(s)
        img.save(OUT_DIR / f"{s}.webp", "WEBP", quality=WEBP_QUALITY, alpha_quality=ALPHA_QUALITY, method=6)
        images.append(img)
        print(f"{s}: {(OUT_DIR / f'{s}.webp').stat().st_size} bytes")
    MANIFEST.write_text(json.dumps(man, indent=4) + "\n")
    if args.sheet:
        from PIL import Image

        cols = 5
        rows = (len(images) + cols - 1) // cols
        sheet = Image.new("RGBA", (cols * 140, rows * 140), (34, 28, 24, 255))
        for i, im in enumerate(images):
            sheet.alpha_composite(im, ((i % cols) * 140 + 6, (i // cols) * 140 + 6))
        sheet.save(args.sheet)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
