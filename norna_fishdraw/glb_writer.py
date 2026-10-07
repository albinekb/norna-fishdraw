"""Minimal glTF 2.0 binary writer for a flat-shaded, pixel-textured mesh (stdlib only).

One node, one mesh, one primitive per material (POSITION + NORMAL, no indices:
every triangle owns its three vertices so normals are the face normal, the
repo's flat-shaded pv look). NORMAL is normalised int8 and TEXCOORD_0 normalised
uint16 to keep a fish under 40 KB. `flank` (the whole body) and `fin` carry a
baseColorTexture from skin.py (nearest-filtered, clamped); their baseColorFactor
is white, so a client recolours by tinting the factor. `iris` and `pupil` stay
flat colours from the palette. Metallic 0, roughness 0.85; `fin` is double-sided.
Output is byte-stable for one Python/zlib build.
"""

from __future__ import annotations

import json
import math
import struct

from .lift3d import Mesh
from .skin import Skin, body_texture, fin_texture, png_bytes

DOUBLE_SIDED = {"fin"}
ORDER = ("flank", "fin", "iris", "pupil")
TEXTURED = {"flank": 0, "fin": 1}


def _lin(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_to_linear(h: str):
    h = h.lstrip("#")
    return [round(_lin(int(h[i : i + 2], 16) / 255), 5) for i in (0, 2, 4)] + [1.0]


def _normal(t):
    a, b, c = t
    u = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    v = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
    ln = math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2) or 1.0
    return (n[0] / ln, n[1] / ln, n[2] / ln)


def _q(x: float) -> float:
    """Quantise to 1e-5 and fold -0.0 into 0.0, so libm last digits and signed zeros never reach the file."""
    return round(x, 5) + 0.0


def _q8(n):
    return struct.pack("<4b", *(round(_q(c) * 127) + 0 for c in n), 0)


def write_glb(path: str, mesh: Mesh, palette: dict, name: str, skin: Skin | None = None) -> dict:
    """Write `mesh` to `path`; returns {tris, bytes}. Material names are the palette roles."""
    skin = skin or Skin()
    roles = [r for r in ORDER if mesh.tris.get(r)]
    blob = bytearray()
    views, accessors, prims, mats = [], [], [], []
    textures = {}

    def view(data, **kw):
        views.append({"buffer": 0, "byteOffset": len(blob), "byteLength": len(data), **kw})
        blob.extend(data)
        blob.extend(b"\0" * (-len(blob) % 4))
        return len(views) - 1

    for role, png in (("flank", png_bytes(body_texture(skin, palette))), ("fin", png_bytes(fin_texture(skin, palette)))):
        if role in roles:
            textures[role] = view(png)
    for r in roles:
        tris = mesh.tris[r]
        pos = bytearray()
        nor = bytearray()
        tex = bytearray()
        lo = [1e9] * 3
        hi = [-1e9] * 3
        uvs = mesh.uvs.get(r)
        for ti, t in enumerate(tris):
            n = _normal(t)
            for vi, p in enumerate(t):
                p = tuple(_q(c) for c in p)
                pos += struct.pack("<3f", *p)
                nor += _q8(n)
                if uvs:
                    tex += struct.pack("<2H", *(max(0, min(65535, round(_q(c) * 65535))) for c in uvs[ti][vi]))
                for i in range(3):
                    lo[i] = min(lo[i], p[i])
                    hi[i] = max(hi[i], p[i])
        acc = {}
        specs = [("POSITION", pos, {"componentType": 5126, "type": "VEC3", "min": [_q(v) for v in lo], "max": [_q(v) for v in hi]}, {}),
                 ("NORMAL", nor, {"componentType": 5120, "type": "VEC3", "normalized": True}, {"byteStride": 4})]
        if uvs:
            specs.append(("TEXCOORD_0", tex, {"componentType": 5123, "type": "VEC2", "normalized": True}, {}))
        for key, data, extra, vkw in specs:
            vi = view(data, target=34962, **vkw)
            accessors.append({"bufferView": vi, "count": len(tris) * 3, **extra})
            acc[key] = len(accessors) - 1
        pbr = {"metallicFactor": 0.0, "roughnessFactor": 0.85}
        if r in TEXTURED:
            pbr["baseColorFactor"] = [1.0, 1.0, 1.0, 1.0]
            pbr["baseColorTexture"] = {"index": TEXTURED[r]}
        else:
            pbr["baseColorFactor"] = hex_to_linear(palette[r])
        mat = {"name": r, "pbrMetallicRoughness": pbr}
        if r == "flank" and "ghost" in (skin.kind,):
            mat["emissiveFactor"] = [0.45, 0.45, 0.45]
            mat["emissiveTexture"] = {"index": 0}
        if r in DOUBLE_SIDED:
            mat["doubleSided"] = True
        mats.append(mat)
        prims.append({"attributes": acc, "material": len(mats) - 1, "mode": 4})
    gltf = {
        "asset": {"version": "2.0", "generator": "norna_fishdraw (port of LingDong-/fishdraw, MIT)"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"name": name, "mesh": 0}],
        "meshes": [{"name": name, "primitives": prims}],
        "materials": mats,
        "accessors": accessors,
        "bufferViews": views,
        "buffers": [{"byteLength": len(blob)}],
        "images": [{"bufferView": textures.get(r, 0), "mimeType": "image/png", "name": r + "-skin"} for r in ("flank", "fin") if r in textures],
        "textures": [{"source": i, "sampler": 0} for i in range(len(textures))],
        "samplers": [{"magFilter": 9728, "minFilter": 9728, "wrapS": 33071, "wrapT": 33071}],
    }
    js = json.dumps(gltf, separators=(",", ":"), sort_keys=True).encode()
    js += b" " * (-len(js) % 4)
    blob += b"\0" * (-len(blob) % 4)
    gltf_len = 12 + 8 + len(js) + 8 + len(blob)
    out = struct.pack("<III", 0x46546C67, 2, gltf_len)
    out += struct.pack("<II", len(js), 0x4E4F534A) + js
    out += struct.pack("<II", len(blob), 0x004E4942) + bytes(blob)
    import os

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "wb") as f:
        f.write(out)
    return {"tris": mesh.count(), "bytes": len(out)}
