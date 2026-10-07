"""norna_fishdraw tests (pure Python, no Blender): python3 norna_fishdraw/test_fishdraw.py"""

import json
import os
import re
import shutil
import struct
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from norna_fishdraw import build as fbuild  # noqa: E402
from norna_fishdraw.fishdraw_port import Rng, fish_drawing, generate_params, str_to_seed  # noqa: E402
from norna_fishdraw.glb_writer import write_glb  # noqa: E402
from norna_fishdraw.skin import png_decode  # noqa: E402
from norna_fishdraw.presets import SLUGS, SPECIES, fish_for, fish_from_seed  # noqa: E402

_BAKE = None
MODELS = None  # the v2 game bake, written once per test run by setUpModule


def setUpModule():
    global _BAKE, MODELS
    from norna_fishdraw.v2 import bake

    _BAKE = tempfile.TemporaryDirectory()
    MODELS = _BAKE.name
    bake.bake_game(MODELS, log=lambda *a: None)


def tearDownModule():
    _BAKE.cleanup()


def glb_tris(path):
    with open(path, "rb") as f:
        data = f.read()
    jl = struct.unpack_from("<I", data, 12)[0]
    g = json.loads(data[20 : 20 + jl])
    return sum(g["accessors"][p["attributes"]["POSITION"]]["count"] // 3 for p in g["meshes"][0]["primitives"]), g


def write_skin_bytes(slug, seed):
    from norna_fishdraw.skin import body_texture

    f = fish_for(slug, seed)
    return repr(body_texture(f.look.skin, f.look.palette))


class Parity(unittest.TestCase):
    def test_matches_fishdraw_js(self):
        # goldens captured from `node fishdraw.js` internals (generate_params, str_to_seed, body curves)
        self.assertEqual(str_to_seed("trout"), 3000520182)
        d = fish_drawing("trout")
        self.assertAlmostEqual(d.params["body_length"], 256.0958554666421, places=9)
        self.assertEqual((d.params["tail_type"], d.params["pattern_type"]), (2, 1))
        self.assertAlmostEqual(d.curve0[1][0], 105.21322889463514, places=9)
        self.assertAlmostEqual(d.curve0[1][1], 114.995551241412, places=9)
        self.assertAlmostEqual(d.curve1[2][1], 191.02634198913813, places=9)

    def test_rng_in_unit_range_and_seeded(self):
        a, b = Rng(str_to_seed("x")), Rng(str_to_seed("x"))
        xs = [a.rand() for _ in range(50)]
        self.assertEqual(xs, [b.rand() for _ in range(50)])
        self.assertTrue(all(0 <= v <= 1 for v in xs))
        self.assertNotEqual(generate_params(Rng(1)), generate_params(Rng(2)))


class Fishes(unittest.TestCase):
    def test_deterministic_bytes(self):
        with tempfile.TemporaryDirectory() as t:
            for n in (1, 2):
                f = fish_for("tusk-pike", "abc")
                write_glb(os.path.join(t, "%d.glb" % n), f.mesh(), f.look.palette, "x")
            self.assertEqual(open(os.path.join(t, "1.glb"), "rb").read(), open(os.path.join(t, "2.glb"), "rb").read())

    def test_skin_is_textured_pixel_art_with_uvs(self):
        with tempfile.TemporaryDirectory() as t:
            f = fish_for("reed-perch", "a")
            p = os.path.join(t, "a.glb")
            write_glb(p, f.mesh(), f.look.palette, "x", f.look.skin)
            _, g = glb_tris(p)
            self.assertEqual([m["name"] for m in g["materials"]][:2], ["flank", "fin"])
            self.assertEqual(g["samplers"][0]["magFilter"], 9728)  # nearest
            prim = {g["materials"][pr["material"]]["name"]: pr for pr in g["meshes"][0]["primitives"]}
            self.assertIn("TEXCOORD_0", prim["flank"]["attributes"])
            self.assertNotIn("TEXCOORD_0", prim["iris"]["attributes"])
            data = open(p, "rb").read()
            jl = struct.unpack_from("<I", data, 12)[0]
            bin0 = 20 + jl + 8
            shapes = []
            for im in g["images"]:
                bv = g["bufferViews"][im["bufferView"]]
                im_ = png_decode(data[bin0 + bv["byteOffset"] : bin0 + bv["byteOffset"] + bv["byteLength"]])
                shapes.append((len(im_), len(im_[0]), len(im_[0][0])))
            self.assertEqual(shapes, [(32, 64, 4), (16, 32, 4)])
            tex = png_decode(data[bin0 + g["bufferViews"][g["images"][0]["bufferView"]]["byteOffset"] :][: g["bufferViews"][g["images"][0]["bufferView"]]["byteLength"]])
            self.assertGreater(len({tuple(px) for row in tex for px in row}), 12)  # gradient + bars + scales, not flat
            self.assertLess(os.path.getsize(p), 40 * 1024)
            # the catch seed varies the texture; same seed does not
            a = write_skin_bytes("reed-perch", "a")
            self.assertEqual(a, write_skin_bytes("reed-perch", "a"))
            self.assertNotEqual(a, write_skin_bytes("reed-perch", "b"))

    def test_no_negative_zero_in_buffers(self):
        for slug in SLUGS:
            for seed in (None, "n1"):
                f = fish_for(slug, seed)
                with tempfile.TemporaryDirectory() as t:
                    p = os.path.join(t, "a.glb")
                    write_glb(p, f.mesh(), f.look.palette, "x", f.look.skin)
                    data = open(p, "rb").read()
                jl = struct.unpack_from("<I", data, 12)[0]
                g = json.loads(data[20 : 20 + jl])
                blob = data[20 + jl + 8 :]
                for ac in g["accessors"]:
                    bv = g["bufferViews"][ac["bufferView"]]
                    if ac["componentType"] == 5126:
                        raw = blob[bv["byteOffset"] : bv["byteOffset"] + bv["byteLength"]]
                        for (w,) in struct.iter_unpack("<I", raw):
                            self.assertNotEqual(w, 0x80000000, (slug, seed))
                self.assertIsNone(re.search(rb"-0\.0[,\]]", data[20 : 20 + jl]), slug)

    def test_output_is_identical_across_20_processes_and_hash_seeds(self):
        import hashlib
        import subprocess

        code = (
            "import sys,hashlib,tempfile,os;sys.path.insert(0,%r)\n"
            "from norna_fishdraw.presets import fish_for\n"
            "from norna_fishdraw.glb_writer import write_glb\n"
            "h=hashlib.sha256()\n"
            "d=tempfile.mkdtemp()\n"
            "for sp,sd in (('shardfin',None),('loki-salmon',None),('shardfin','s1'),('loki-salmon','s2'),('mottled-eel','s3')):\n"
            "    f=fish_for(sp,sd);p=os.path.join(d,'a.glb');write_glb(p,f.mesh(),f.look.palette,'x',f.look.skin);h.update(open(p,'rb').read())\n"
            "print(h.hexdigest())\n" % os.path.dirname(HERE)
        )
        digests = set()
        for i in range(20):
            r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env={**os.environ, "PYTHONHASHSEED": str(i * 7919)}, timeout=60)
            self.assertEqual(r.returncode, 0, r.stderr)
            digests.add(r.stdout.strip())
        self.assertEqual(len(digests), 1, digests)
        del hashlib

    def test_winding_is_stable_under_1ulp_noise(self):
        # a face edge-on to the reference point (the nose fan) must not flip winding on a 1-ulp sign change
        from norna_fishdraw.lift3d import Mesh

        a, b, c = (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)
        for eps in (-1e-17, 0.0, 1e-17):
            m = Mesh()
            m.add("flank", a, b, c, (0.3, 0.3, eps))
            self.assertEqual(m.tris["flank"][0], (a, b, c))

    def test_seed_varies_the_catch(self):
        a, b = fish_for("reed-perch", "a"), fish_for("reed-perch", "b")
        self.assertNotEqual(a.kg, b.kg)
        self.assertNotEqual(a.mesh().bounds(), b.mesh().bounds())

    def test_budget_bounds_orientation(self):
        for slug in SLUGS:
            for seed in (None, "s1", "s2", 7):
                f = fish_for(slug, seed)
                m = f.mesh()
                self.assertLess(m.count(), 600, (slug, seed))
                (x0, y0, z0), (x1, y1, z1) = m.bounds()
                lat, up, long = x1 - x0, y1 - y0, z1 - z0
                self.assertAlmostEqual(long, f.length_m, delta=f.length_m * 0.2, msg=(slug, seed))
                self.assertGreater(long, lat)  # nose axis is the longest
                self.assertLess(abs(x0 + x1), 1e-6)  # symmetric
                lo, hi = SPECIES[slug].kg[0], SPECIES[slug].kg[1]
                if seed is not None:
                    self.assertTrue(lo <= f.kg <= hi)
                # nose +Z: the heavier (head) half is in +Z, the tail fin tip is in -Z
                tail = min(p[2] for t in m.tris["fin"] for p in t)
                self.assertAlmostEqual(tail, z0, places=6)

    def test_random_seed_fish_budget(self):
        for i in range(24):
            self.assertLess(fish_from_seed("seed-%02d" % i).mesh().count(), 600)


def _glb_parts(data):
    """(json without offsets/extents, per-accessor value lists, decoded textures): what a platform may not change."""
    jl = struct.unpack_from("<I", data, 12)[0]
    g = json.loads(data[20 : 20 + jl])
    blob = data[20 + jl + 8 :]
    pix = [png_decode(blob[g["bufferViews"][im["bufferView"]]["byteOffset"] :][: g["bufferViews"][im["bufferView"]]["byteLength"]]) for im in g["images"]]
    fmt = {5126: ("f", 4), 5120: ("b", 1), 5121: ("B", 1), 5123: ("H", 2)}
    arrs = []
    for ac in g["accessors"]:
        bv = g["bufferViews"][ac["bufferView"]]
        n = {"VEC3": 3, "VEC2": 2, "VEC4": 4, "MAT4": 16}[ac["type"]]  # a skinned v2 fish: joints, weights, bind matrices
        code, size = fmt[ac["componentType"]]
        stride = bv.get("byteStride") or size * n
        vals = []
        for i in range(ac["count"]):
            vals += struct.unpack_from("<%d%s" % (n, code), blob, bv["byteOffset"] + i * stride)
        arrs.append((vals, ac["componentType"]))
        ac.pop("min", None), ac.pop("max", None)
    for bv in g["bufferViews"]:
        bv.pop("byteOffset"), bv.pop("byteLength")
    g["buffers"] = []
    return json.dumps(g, sort_keys=True), arrs, pix


def _assert_same_glb(tc, a, b, name):
    ja, aa, pa = _glb_parts(a)
    jb, ab, pb = _glb_parts(b)
    tc.assertEqual(ja, jb, name)
    for (x, ct), (y, _) in zip(aa, ab):
        tc.assertEqual(len(x), len(y), name)
        # positions to 3e-5 m; normalised int8 normals / uint16 UVs to a couple of steps
        tc.assertLessEqual(max(abs(p - q) for p, q in zip(x, y)), 3e-5 if ct == 5126 else 2, name)
    for x, y in zip(pa, pb):
        px = [(p, q) for rx, ry in zip(x, y) for p, q in zip(rx, ry)]
        bad = sum(1 for p, q in px if max(abs(p[i] - q[i]) for i in range(3)) > 12)
        tc.assertLess(bad / len(px), 0.02, name)  # a threshold flip may move a few texels


class Exported(unittest.TestCase):
    def test_every_species_has_glb_calibrate_and_index(self):
        from norna_fishdraw.v2 import validate as v2validate

        idx = json.load(open(os.path.join(MODELS, "fish.json")))
        self.assertEqual(idx["species"], list(SLUGS))
        for slug in SLUGS:
            p = os.path.join(MODELS, slug + ".glb")
            self.assertTrue(os.path.exists(p), slug)
            self.assertTrue(os.path.exists(os.path.join(MODELS, slug + ".calibrate.json")), slug)
            tris, g = glb_tris(p)
            # fishdraw v2's budget (welded jaws, round eyes, ray fins): 900 a fish, its own plan's where `validate.TRI_BUDGET` gives one (the squid's 1500)
            plan = idx["models"][slug]["plan"]
            self.assertLess(tris, v2validate.TRI_BUDGET.get(slug, v2validate.TRI_BUDGET.get(plan, v2validate.DEFAULT_BUDGET)), slug)
            self.assertEqual(tris, idx["models"][slug]["tris"])
            self.assertIn(slug, json.dumps(idx))  # an asset checker can read the stem from a non-calibrate file

    def test_v1_builds_apart_from_the_v2_bake(self):
        # Norna ships fishdraw v2 (`v2/bake.py --game`, pinned in v2/test_v2.py); v1 still builds, into its own directory.
        self.assertNotEqual(os.path.realpath(fbuild.DEFAULT_OUT), os.path.realpath(MODELS))
        with tempfile.TemporaryDirectory() as t:
            fbuild.build(t)
            self.assertEqual(sorted(json.load(open(os.path.join(t, "fish.json")))["species"]), sorted(SLUGS))
            shipped = json.load(open(os.path.join(MODELS, "fish.json")))
            self.assertNotEqual(shipped["generator"], json.load(open(os.path.join(t, "fish.json")))["generator"])
            self.assertNotEqual(open(os.path.join(t, "grey-cod.glb"), "rb").read(), open(os.path.join(MODELS, "grey-cod.glb"), "rb").read())


class Icons(unittest.TestCase):
    def test_icons_render_and_a_changed_glb_reads_stale(self):
        from norna_fishdraw import icons
        from pathlib import Path

        slugs = ["grey-cod", "tusk-pike"]
        with tempfile.TemporaryDirectory() as t:
            # a two-species model directory: fish.json names the species, each with its GLB
            models, out = Path(t, "fish"), Path(t, "icons")
            models.mkdir()
            idx = json.load(open(os.path.join(MODELS, "fish.json")))
            idx["species"] = slugs
            idx["models"] = {s: idx["models"][s] for s in slugs}
            (models / "fish.json").write_text(json.dumps(idx))
            for s in slugs:
                shutil.copy(os.path.join(MODELS, s + ".glb"), models / (s + ".glb"))
            self.assertEqual(icons.main(["--models", str(models), "--out", str(out)]), 0)
            for s in slugs:
                self.assertTrue((out / (s + ".webp")).exists(), s)
            self.assertEqual(icons.main(["--models", str(models), "--out", str(out), "--check"]), 0)
            # a GLB that changed since its icon was rendered must read stale
            with open(models / "grey-cod.glb", "ab") as f:
                f.write(b"\0\0\0\0")
            stale = icons.check()
        self.assertEqual(len(stale), 1, stale)
        self.assertIn("grey-cod", stale[0])

    def test_icon_render_is_deterministic_and_fills_the_tile(self):
        from norna_fishdraw import icons
        from pathlib import Path

        icons.MODELS = Path(MODELS)
        a = icons.downsample(icons.render("tusk-pike"))
        self.assertEqual(a, icons.downsample(icons.render("tusk-pike")))
        n = icons.ICON
        alpha = [a[(y * n + x) * 4 + 3] for y in range(n) for x in range(n)]
        self.assertGreater(sum(1 for v in alpha if v > 128), 400)
        xs = [x for y in range(n) for x in range(n) if alpha[y * n + x] > 0]
        ys = [y for y in range(n) for x in range(n) if alpha[y * n + x] > 0]
        self.assertGreater(max(max(xs) - min(xs), max(ys) - min(ys)), n * 0.8)
        self.assertEqual(alpha[0], 0)
        self.assertEqual(alpha[n * n - 1], 0)
        self.assertEqual(alpha[n - 1], 0)
        self.assertEqual(alpha[n * (n - 1)], 0)


if __name__ == "__main__":
    unittest.main()
