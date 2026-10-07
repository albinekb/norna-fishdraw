"""A binary glTF 2.0 writer for a v2 fish: one skinned mesh, one primitive per role, the finishes' materials.

Extends the v1 writer's conventions (unindexed flat-shaded triangles, quantised to 1e-5 with -0.0 folded, int8 normals,
uint16 UVs, nearest-filtered pixel-art textures, byte-stable) with: an open role set (`under`, `lid`, `sclera`, `glint`,
`tooth`, `mouth`, `jaw`, `arm`, `sucker`, `stalk`, `bulb`, ...), per-material PBR from `finish.py` (metallic, roughness,
emissive with `KHR_materials_emissive_strength`, `BLEND` alpha, clearcoat, sheen, iridescence), two-sided thin roles,
a node pose quaternion, and one skin: spine, jaw and tentacle joints with `JOINTS_0` / `WEIGHTS_0` per vertex.
"""

from __future__ import annotations

import json
import math
import os
import struct

from . import finish as FIN
from . import skin2
from ..skin import png_bytes


TEXTURED = {"flank": 0, "under": 0, "fin": 1}


def _lin(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_to_linear(h: str):
    h = h.lstrip("#")
    return [round(_lin(int(h[i : i + 2], 16) / 255), 5) for i in (0, 2, 4)]


def _q(x: float) -> float:
    return round(x, 5) + 0.0


def _normal(t):
    a, b, c = t
    u = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    v = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
    ln = math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2) or 1.0
    return (n[0] / ln, n[1] / ln, n[2] / ln)


def _q8(n):
    return struct.pack("<4b", *(round(_q(c) * 127) + 0 for c in n), 0)


def _fleck_png(seed: int) -> bytes:
    """A 32x16 greyscale-ish fleck map: per-texel thickness the holographic finish varies its iridescence by."""
    from ..fishdraw_port import Rng

    r = Rng(seed or 1)
    rows = []
    for y in range(16):
        row = []
        for x in range(32):
            v = int(255 * (0.25 + 0.75 * r.rand() ** 2))
            row.append([v, v, v, 255])
        rows.append(row)
    return png_bytes(rows)


def _weights4(ws):
    ws = sorted(ws, key=lambda bw: -bw[1])[:4]
    tot = sum(w for _, w in ws) or 1.0
    q = [round(255 * w / tot) for _, w in ws]
    q[0] += 255 - sum(q)
    ids = [b for b, _ in ws] + [0] * (4 - len(ws))
    q += [0] * (4 - len(q))
    return struct.pack("<4B", *ids), struct.pack("<4B", *q)


def write_glb(path: str, fish, rig=None, name: str = "fish", pose=None) -> dict:
    """Write `fish` to `path`; returns {tris, bytes, roles, joints}. `rig` skins it; `pose` is a node quaternion."""
    g = fish.eff
    pal = g["palette"]
    mesh = fish.mesh()
    roles = [r for r in FIN_ORDER if mesh.tris.get(r)]
    glow = bool(g.get("glow"))
    holo = g.get("finish", {}).get("kind") == "holo"
    blob = bytearray()
    views, accessors, prims, mats, images = [], [], [], [], []
    used = set()

    def view(data, **kw):
        views.append({"buffer": 0, "byteOffset": len(blob), "byteLength": len(data), **kw})
        blob.extend(data)
        blob.extend(b"\0" * (-len(blob) % 4))
        return len(views) - 1

    def add_image(label, png):
        images.append({"bufferView": view(png), "mimeType": "image/png", "name": label})
        return len(images) - 1

    img_body = add_image("flank-skin", png_bytes(skin2.body_pixels(g, pal)))
    img_fin = add_image("fin-skin", png_bytes(skin2.fin_pixels(g, pal)))
    img_glow = add_image("glow", png_bytes(skin2.glow_mask(g, pal))) if glow else None
    img_holo = add_image("fleck", _fleck_png(g["skin"]["seed"])) if holo else None
    tex_of = {"body": img_body, "fin": img_fin, "glow": img_glow, "holo": img_holo}
    textures = [{"source": i, "sampler": 0} for i in range(len(images))]

    for r in roles:
        tris = mesh.tris[r]
        uvs = mesh.uvs.get(r)
        textured = r in TEXTURED and bool(uvs) and len(uvs) == len(tris)
        pos, nor, tex, jnt, wgt = bytearray(), bytearray(), bytearray(), bytearray(), bytearray()
        lo, hi = [1e9] * 3, [-1e9] * 3
        for ti, t in enumerate(tris):
            n = _normal(t)
            for vi, p in enumerate(t):
                pq = tuple(_q(c) for c in p)
                pos += struct.pack("<3f", *pq)
                nor += _q8(n)
                if textured:
                    tex += struct.pack("<2H", *(max(0, min(65535, round(_q(c) * 65535))) for c in uvs[ti][vi]))
                if rig is not None:
                    j4, w4 = _weights4(rig.weights[p])
                    jnt += j4
                    wgt += w4
                for i in range(3):
                    lo[i], hi[i] = min(lo[i], pq[i]), max(hi[i], pq[i])
        acc = {}
        specs = [("POSITION", pos, {"componentType": 5126, "type": "VEC3", "min": [_q(v) for v in lo], "max": [_q(v) for v in hi]}, {}),
                 ("NORMAL", nor, {"componentType": 5120, "type": "VEC3", "normalized": True}, {"byteStride": 4})]
        if textured:
            specs.append(("TEXCOORD_0", tex, {"componentType": 5123, "type": "VEC2", "normalized": True}, {}))
        if rig is not None:
            specs.append(("JOINTS_0", jnt, {"componentType": 5121, "type": "VEC4"}, {"byteStride": 4}))
            specs.append(("WEIGHTS_0", wgt, {"componentType": 5121, "type": "VEC4", "normalized": True}, {"byteStride": 4}))
        for key, data, extra, vkw in specs:
            vi = view(data, target=34962, **vkw)
            accessors.append({"bufferView": vi, "count": len(tris) * 3, **extra})
            acc[key] = len(accessors) - 1
        m = FIN.material(r, g, textured, glow and r in ("flank", "under"))
        pbr = {"metallicFactor": m["metallic"], "roughnessFactor": m["roughness"]}
        mat = {"name": r, "pbrMetallicRoughness": pbr}
        if textured:
            pbr["baseColorFactor"] = m["base"]
            pbr["baseColorTexture"] = {"index": tex_of["fin"] if r == "fin" else tex_of["body"]}
        else:
            key = FIN.FLAT.get(r, r)
            pbr["baseColorFactor"] = hex_to_linear(pal.get(key, "#cccccc")) + [m["base"][3]]
        if m["blend"]:
            mat["alphaMode"] = "BLEND"
        if m["double"]:
            mat["doubleSided"] = True
        ext = dict(m["ext"])
        if m["emissive"]:
            rgb, strength = m["emissive"]
            mat["emissiveFactor"] = rgb
            if glow and r in ("flank", "under"):
                mat["emissiveTexture"] = {"index": tex_of["glow"]}
                mat["emissiveFactor"] = [1.0, 1.0, 1.0]
            ext["KHR_materials_emissive_strength"] = {"emissiveStrength": strength}
        if "KHR_materials_iridescence" in ext and ext["KHR_materials_iridescence"].pop("holoFleck", False) and tex_of["holo"] is not None:
            ext["KHR_materials_iridescence"]["iridescenceThicknessTexture"] = {"index": tex_of["holo"]}
        if ext:
            mat["extensions"] = ext
            used.update(ext)
        mats.append(mat)
        prims.append({"attributes": acc, "material": len(mats) - 1, "mode": 4})

    nodes = [{"name": name, "mesh": 0}]
    gltf = {
        "asset": {"version": "2.0", "generator": "norna_fishdraw v2"},
        "scene": 0,
        "meshes": [{"name": name, "primitives": prims}],
        "materials": mats,
        "accessors": accessors,
        "bufferViews": views,
        "images": images,
        "textures": textures,
        "samplers": [{"magFilter": 9728, "minFilter": 9728, "wrapS": 33071, "wrapT": 33071}],
    }
    if pose:
        nodes[0]["rotation"] = [round(c, 6) for c in pose]
    n_joints = 0
    if rig is not None:
        n_joints = len(rig.bones)
        ibm = bytearray()
        for b in rig.bones:
            ibm += struct.pack("<16f", 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, *(_q(-c) for c in b.pos), 1)
        accessors.append({"bufferView": view(bytes(ibm)), "count": n_joints, "componentType": 5126, "type": "MAT4"})
        children: dict = {}
        for k, b in enumerate(rig.bones):
            if b.parent >= 0:
                children.setdefault(b.parent, []).append(1 + k)
        for k, b in enumerate(rig.bones):
            par = rig.bones[b.parent].pos if b.parent >= 0 else (0.0, 0.0, 0.0)
            node = {"name": b.name, "translation": [_q(b.pos[i] - par[i]) for i in range(3)]}
            if k in children:
                node["children"] = children[k]
            nodes.append(node)
        nodes[0]["skin"] = 0
        gltf["skins"] = [{"joints": list(range(1, 1 + n_joints)), "inverseBindMatrices": len(accessors) - 1, "skeleton": 1}]
        gltf["scenes"] = [{"nodes": [0, 1]}]
        if pose:
            # A skinned mesh's own node transform is ignored (glTF 2.0 skins): the pose rides a root above the mesh
            # node and the skeleton, so the joints, and with them every vertex, are turned by it.
            rot = nodes[0].pop("rotation")
            nodes.append({"name": name + ".pose", "rotation": rot, "children": [0, 1]})
            gltf["scenes"] = [{"nodes": [len(nodes) - 1]}]
    else:
        gltf["scenes"] = [{"nodes": [0]}]
    gltf["nodes"] = nodes
    gltf["buffers"] = [{"byteLength": len(blob)}]
    if used:
        gltf["extensionsUsed"] = sorted(used)
    js = json.dumps(gltf, separators=(",", ":"), sort_keys=True).encode()
    js += b" " * (-len(js) % 4)
    blob += b"\0" * (-len(blob) % 4)
    total = 12 + 8 + len(js) + 8 + len(blob)
    out = struct.pack("<III", 0x46546C67, 2, total) + struct.pack("<II", len(js), 0x4E4F534A) + js + struct.pack("<II", len(blob), 0x004E4942) + bytes(blob)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "wb") as f:
        f.write(out)
    return {"tris": mesh.count(), "bytes": len(out), "roles": roles, "joints": n_joints}


FIN_ORDER = FIN.ORDER


def display_pose(plan: str):
    """The catalogue pose of a plan that lies down: a flatfish or ray rolled 70 degrees about its nose axis so a bag icon
    or a hand shows its upper face, not its edge. None for every plan that already stands as it swims."""
    if plan in ("flat", "ray"):
        a = math.radians(70.0) / 2
        return (0.0, 0.0, math.sin(a), math.cos(a))
    return None
