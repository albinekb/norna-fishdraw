"""norna_fishdraw v2 tests (pure Python): python3 norna_fishdraw/v2/test_v2.py"""

import copy
import json
import math
import os
import random
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))

from norna_fishdraw.v2 import build as B  # noqa: E402
from norna_fishdraw.v2 import fixtures as F  # noqa: E402
from norna_fishdraw.v2 import genome as G  # noqa: E402
from norna_fishdraw.v2 import bake, compare, finish, game, glb, motion, rig as RG, skin2, surface, sweep, validate as V, variety, vectors  # noqa: E402
from norna_fishdraw.skin import body_texture  # noqa: E402
import struct
import tempfile

QUIET = lambda *a: None  # noqa: E731

_BAKE = None
BAKED = None  # the game bake (`bake.bake_game`), written once per test run by setUpModule


def setUpModule():
    global _BAKE, BAKED
    _BAKE = tempfile.TemporaryDirectory()
    BAKED = _BAKE.name
    bake.bake_game(BAKED, log=QUIET)


def tearDownModule():
    _BAKE.cleanup()


def n_tris(mesh):
    return sum(len(t) for t in mesh.tris.values())


def skin_tris(fish):
    return [t for ts in fish.skin.tris.values() for t in ts]


class Drawn(unittest.TestCase):
    def test_every_plan_builds_a_clean_fish(self):
        seen = set()
        for sp in sorted(G.SPECIES):
            for seed in range(1, 7):
                g = G.draw(sp, seed)
                fish = B.build(g, 1.0)
                rep = V.validate(fish)
                self.assertTrue(rep.ok, "%s %d: %s" % (sp, seed, rep.notes))
                seen.add(g["plan"])
        self.assertEqual(seen, set(G.PLANS))
        self.assertGreaterEqual(len(G.PLANS), 11)
        # the plan's own character, read off the mesh
        flat = B.build(G.draw("plaice", 1))
        lo, hi = flat.skin.bounds()
        self.assertGreater(hi[0] - lo[0], 4 * (hi[1] - lo[1]))  # a disc lying on its side
        eyes = [p for p in flat.parts if p.kind == "eye"]
        self.assertEqual(len(eyes), 2)
        self.assertTrue(all(sum(v[1] for v in p.roots) / 6 > 0 for p in eyes))  # both on the upper face
        hh = B.build(G.draw("hammerhead", 1))
        tips = sorted(sum(v[0] for v in p.roots) / 6 for p in hh.parts if p.kind == "eye")
        self.assertLess(tips[0], -0.05 * hh.eff["len_m"])  # an eye at each tip of the cephalofoil
        self.assertGreater(tips[1], 0.05 * hh.eff["len_m"])
        sq = B.build(G.draw("squid", 1))
        self.assertEqual(sum(1 for p in sq.parts if p.kind == "arm"), 10)  # eight arms and two clubs
        self.assertTrue(any(p.kind == "bulb" for p in sq.parts))

    def test_same_seed_same_fish_and_a_new_gene_shifts_nothing(self):
        self.assertEqual(G.draw("perch", 5), G.draw("perch", 5))
        self.assertNotEqual(G.draw("perch", 5), G.draw("perch", 6))
        self.assertEqual(json.loads(json.dumps(G.draw("angler", 9, ["fanged"]))), G.draw("angler", 9, ["fanged"]))
        base = G.draw("perch", 5)
        G.SPECIES["perch-x"] = copy.deepcopy(G.SPECIES["perch"])
        G.SPECIES["perch-x"]["genes"]["parts.barbels.n"] = (3, 3)
        G.SPECIES["perch-x"]["genes"]["parts.barbels.len"] = (0.5, 0.9)
        G.SPECIES["perch-x"]["genes"]["parts.barbels.tip"] = (0.1, 0.2)
        G.SPECIES["perch-x"]["genes"]["parts.barbels.curl"] = (0.2, 0.9)
        try:
            wider = G.draw("perch-x", 5)
        finally:
            del G.SPECIES["perch-x"]
        for k in ("body", "palette", "len_m"):
            self.assertEqual(base[k], wider[k], k)
        self.assertEqual(base["parts"]["eye"], wider["parts"]["eye"])
        self.assertIn("barbels", wider["parts"])

    def test_a_part_lands_on_the_skin_it_was_placed_on(self):
        fish = B.build(G.draw("catfish", 3))
        ix = V.TriIndex(skin_tris(fish))
        rng = random.Random(4)
        for _ in range(200):
            pos, nrm, tan = fish.grid.at(surface.SurfacePoint(rng.random(), rng.random() * 6.2831853))
            cut = list(fish.layout["holes"]) + [c for cs in fish.layout["cells"].values() for c in cs]
            if any(math.dist(pos, fish.grid.V[i][j]) < 0.12 * fish.eff["len_m"] for (i, j) in cut):
                continue  # where a socket or a bump cell was cut the body is deliberately open: the part's own faces are there
            self.assertLess(abs(ix.dist(pos, k=len(ix.items))), 1e-9)  # brute force: the closest of every face
            self.assertAlmostEqual(surface.dot(nrm, nrm), 1.0, places=9)
            self.assertAlmostEqual(surface.dot(tan, tan), 1.0, places=9)

    def test_body_and_parts_are_one_welded_piece_with_no_t_junction(self):
        for sp in sorted(G.SPECIES):
            for seed in (1, 2, 3):
                fish = B.build(G.draw(sp, seed))
                notes, comps = V._welded(skin_tris(fish), fish.parts, 1.0)
                self.assertEqual((notes, comps), ([], 1), "%s %d" % (sp, seed))
                skin_v = {p for t in skin_tris(fish) for p in t}
                skin_e = {frozenset(e) for a, b, c in skin_tris(fish) for e in ((a, b), (b, c), (c, a))}
                self.assertTrue(fish.parts)
                for pt in fish.parts:
                    if pt.parent == "skin":
                        self.assertTrue(set(pt.roots) <= skin_v, pt.id)  # the roots ARE body vertices, shared tuples
                        self.assertTrue(all(frozenset(e) in skin_e for e in pt.edges), pt.id)  # every root edge is a body edge
                # a T-junction: a part vertex sitting inside a body edge it does not share an endpoint with
                part_v = [p for pt in fish.parts for p in pt.verts() if p not in skin_v]
                for a, b in [tuple(e) for e in skin_e][::7]:
                    ab = surface.sub(b, a)
                    ln2 = surface.dot(ab, ab)
                    for p in part_v[::3]:
                        t = surface.dot(surface.sub(p, a), ab) / ln2
                        if 0.02 < t < 0.98:
                            q = surface.add(a, surface.mul(ab, t))
                            self.assertGreater(math.dist(p, q), 1e-6, "%s %d: a part vertex sits in a body edge" % (sp, seed))


class Validator(unittest.TestCase):
    def test_rejects_each_known_break_and_passes_its_unbroken_twin(self):
        caught = 0
        for name, fn in F.FIXTURES.items():
            fish, expected = fn()
            twin = B.build(fish.genome, fish.strength)  # the same fish, unbroken
            self.assertTrue(V.validate(twin).ok, "%s: the unbroken twin must pass" % name)
            rep = V.validate(fish)
            self.assertFalse(rep.ok, name)
            for check in expected:
                self.assertFalse(rep.checks[check], "%s should trip %s: %s" % (name, check, rep.notes))
            caught += 1
        self.assertEqual(caught, len(F.FIXTURES))
        self.assertGreaterEqual(caught, 13)
        for name in ("floating-crest", "loose-pelvics", "floating-teeth", "cube-eye", "eye-block-above-head", "stalk-without-bulb", "near-miss-weld"):
            self.assertIn(name, F.FIXTURES)

    def test_every_check_is_the_one_catching_its_break(self):
        # relax one check and its break walks through: the sabotage of the sabotage
        def passes(fixture, check, **patch):
            fish, _ = F.FIXTURES[fixture]()
            old = {k: getattr(V, k) for k in patch}
            try:
                for k, v in patch.items():
                    setattr(V, k, v)
                return V.validate(fish).checks[check]
            finally:
                for k, v in old.items():
                    setattr(V, k, v)

        self.assertFalse(passes("floating-crest", "connected"))
        self.assertTrue(passes("floating-crest", "connected", TOUCH=5.0))
        self.assertTrue(passes("floating-crest", "rooted", TOUCH=5.0))
        self.assertTrue(passes("loose-pelvics", "rooted", TOUCH=5.0))
        self.assertTrue(passes("floating-teeth", "connected", TOUCH=5.0))
        self.assertFalse(passes("eye-through-skull", "pierce"))
        self.assertTrue(passes("eye-through-skull", "pierce", PIERCE=5.0))
        self.assertFalse(passes("inward-face", "mesh"))
        self.assertTrue(passes("giant-tail", "silhouette", SILHOUETTE={p: (0.0, 0.0) for p in G.PLANS}))
        self.assertTrue(passes("giant-tail", "proportions", EXTENT={**V.EXTENT, "tail": (0.0, 99.0)}))
        self.assertTrue(passes("eye-block-above-head", "envelope", EYES_ON_TOP=frozenset(G.PLANS)))
        self.assertTrue(passes("stalk-without-bulb", "complete", KIND_NEEDS={}))
        # the weld check itself: with it blinded, the near-miss and the cube eye walk through it
        real = V._welded
        V._welded = lambda skin, parts, L: ([], 1)
        try:
            self.assertTrue(V.validate(F.near_miss_weld()[0]).checks["welded"])
            self.assertTrue(V.validate(F.cube_eye()[0]).checks["welded"])
        finally:
            V._welded = real
        self.assertFalse(V.validate(F.near_miss_weld()[0]).checks["welded"])

    def test_albins_flags_are_red_and_green(self):
        # the two retried angler cells he asked about: both now build, whole, and stay inside the head
        for seed, gifts in ((10070, [{"gene": "bigeye", "x": 0.632}]), (10077, [{"gene": "fanged", "x": 0.687}, {"gene": "gigantism", "x": 0.928}])):
            fish = B.make("angler", seed, gifts=gifts, log=QUIET)
            self.assertTrue(V.validate(fish).ok)
            self.assertLessEqual(fish.attempts and len(fish.attempts) or 0, 3)
            kinds = {p.kind for p in fish.parts}
            self.assertTrue({"stalk", "bulb", "jaw", "tooth"} <= kinds, "no fragments: the lure and the jaw come whole")
            eyes = [p for p in fish.parts if p.kind == "eye"]
            self.assertEqual(len(eyes), 2)
            rep = V.validate(fish)
            self.assertLess(rep.worst["eye_above_back"], 0.005)
            self.assertLessEqual(rep.worst["eye_to_head"], V.EYE_TO_HEAD["round"])
            for e in eyes:  # neither eye crosses the midplane to the far flank
                side = 1 if sum(v[0] for v in e.roots) > 0 else -1
                self.assertGreaterEqual(min(v[0] * side for v in e.verts()), -1e-6)
        # and the break itself, built on purpose from the same seed, is red
        fish, expected = F.eye_block_above_head(10070)
        rep = V.validate(fish)
        self.assertFalse(rep.checks["envelope"])

    def test_a_part_and_its_children_go_together_at_every_strength(self):
        for sp, gifts in (("angler", ["lure", "fanged"]), ("perch", ["lure", "bearded"]), ("catfish", ["fanged"]), ("pike", ["bearded"])):
            g = G.draw(sp, 77, gifts)
            for strength in B.LADDER:
                kinds = [p.kind for p in B.build(g, strength).parts]
                self.assertEqual("stalk" in kinds, "bulb" in kinds, "%s at %.1f: a stalk and its bulb are one part" % (sp, strength))
                self.assertTrue("tooth" not in kinds or "jaw" in kinds)
        self.assertFalse(V.validate(F.stalk_without_bulb()[0]).checks["complete"])

    def test_a_fish_with_no_skin_is_not_ok(self):
        fish = B.build(G.draw("perch", 1))
        fish.skin.tris.clear()
        self.assertFalse(V.validate(fish).ok)


class FailClosed(unittest.TestCase):
    def test_a_failing_gene_retries_weaker_and_logs_its_seed(self):
        G.GIFTS["_big_dorsal"] = lambda g, x: g["parts"]["dorsal"].update(h=40.0 * x * x)
        try:
            logged = []
            gifts = [{"gene": "_big_dorsal", "x": 1.0}]
            fish = B.make("perch", 10301, gifts=gifts, log=lambda f, r: logged.append((f.genome["seed"], f.strength, r.failed())))
            self.assertEqual([s for _, s, _ in logged], [1.0, 0.7])
            self.assertEqual({s for s, _, _ in logged}, {10301})
            self.assertEqual(fish.strength, 0.4)
            self.assertEqual(len(fish.attempts), len(logged))
            self.assertTrue(V.validate(fish).ok)
            before = len(B.FAILURES)
            B.make("perch", 10301, gifts=gifts)
            self.assertGreater(len(B.FAILURES), before)
            self.assertEqual(B.FAILURES[-1]["seed"], 10301)
        finally:
            del G.GIFTS["_big_dorsal"]

    def test_down_to_the_plain_species_mesh(self):
        def monster(g, x):
            g["parts"]["dorsal"]["h"] = 60.0

        G.GIFTS["_monster"] = monster
        try:
            logged = []
            g = G.draw("perch", 3, ["_monster"])
            fish = B.make_from(g, log=lambda f, r: logged.append(f.strength))
        finally:
            del G.GIFTS["_monster"]
        self.assertEqual(logged, [1.0, 0.7, 0.4])
        self.assertEqual(fish.strength, 0.0)
        self.assertEqual(fish.mesh().tris, B.build(G.draw("perch", 3), 1.0).mesh().tris)  # exactly the plain species

    def test_a_plain_species_that_fails_is_a_gate_failure_not_a_fallback(self):
        g = G.draw("perch", 3)
        g["parts"]["dorsal"]["h"] = 60.0  # in the plain genome itself: nothing weaker to fall back to
        with self.assertRaises(AssertionError):
            B.make_from(g, log=QUIET)


def read_glb(path):
    with open(path, "rb") as f:
        data = f.read()
    jl = struct.unpack_from("<I", data, 12)[0]
    return json.loads(data[20 : 20 + jl]), data


class Skins(unittest.TestCase):
    def test_v1_skins_carry_over_and_new_families_paint(self):
        g = G.draw("perch", 3)
        for kind in ("plain", "bars", "blotch", "spots", "stars"):
            self.assertEqual(skin2.body_pixels(g, g["palette"], kind), body_texture(skin2.skin_of(g, kind), g["palette"]), kind)  # v1's own pixels
        for kind in skin2.NEW_KINDS:
            rows = skin2.body_pixels(g, g["palette"], kind)
            self.assertEqual((len(rows), len(rows[0])), (32, 64))
            self.assertNotEqual(rows, skin2.body_pixels(g, g["palette"], "plain"), kind)
        self.assertNotEqual(skin2.body_pixels(G.draw("perch", 3), g["palette"]), skin2.body_pixels(G.draw("perch", 4), g["palette"]))  # per-catch variation
        # the body UV: u along the spine station, v back to belly, shared by both flanks
        fish = B.build(g)
        uv = fish.skin.uvs["flank"]
        self.assertTrue(all(0 <= c <= 1 for t in uv for p in t for c in p))
        self.assertEqual(len(uv), len(fish.skin.tris["flank"]))

    def test_every_species_has_a_v1_analogue_in_the_game_set(self):
        shipped = set(game.SLUGS)
        self.assertEqual(set(compare.ANALOG), set(G.SPECIES))
        self.assertTrue(set(compare.ANALOG.values()) <= shipped)


class Glb(unittest.TestCase):
    def test_every_species_bakes_a_skinned_glb(self):
        with tempfile.TemporaryDirectory() as t:
            for sp in sorted(G.SPECIES):
                fish = B.make(sp, 2, log=QUIET)
                rig = RG.build_rig(fish)
                p = os.path.join(t, sp + ".glb")
                info = glb.write_glb(p, fish, rig, sp)
                g, data = read_glb(p)
                self.assertLess(info["bytes"], 160_000, sp)
                self.assertTrue(set(info["roles"]) <= set(finish.ORDER))
                self.assertEqual({m["name"] for m in g["materials"]}, set(info["roles"]))
                counts = {a["count"] for pr in g["meshes"][0]["primitives"] for a in [g["accessors"][pr["attributes"]["POSITION"]]]}
                for pr in g["meshes"][0]["primitives"]:
                    n = g["accessors"][pr["attributes"]["POSITION"]]["count"]
                    self.assertEqual(n % 3, 0)
                    for key in ("NORMAL", "JOINTS_0", "WEIGHTS_0"):
                        self.assertEqual(g["accessors"][pr["attributes"][key]]["count"], n, "%s %s" % (sp, key))
                    mat = g["materials"][pr["material"]]
                    self.assertEqual("TEXCOORD_0" in pr["attributes"], "baseColorTexture" in mat["pbrMetallicRoughness"], "%s %s" % (sp, mat["name"]))
                    self.assertEqual(mat.get("doubleSided", False), mat["name"] in finish.DOUBLE_SIDED)
                sk = g["skins"][0]
                self.assertEqual(len(sk["joints"]), len(rig.bones))
                self.assertEqual(g["accessors"][sk["inverseBindMatrices"]]["count"], len(rig.bones))
                self.assertLessEqual(len(rig.bones), 255)
                joint_nodes = [g["nodes"][j] for j in sk["joints"]]
                self.assertEqual(sum(len(n.get("children", [])) for n in joint_nodes), len(rig.bones) - 1)  # one tree
                # every vertex's four weights add to 255 and name real joints
                blob = data[20 + struct.unpack_from("<I", data, 12)[0] + 8 :]
                pr = g["meshes"][0]["primitives"][0]
                wv = g["bufferViews"][g["accessors"][pr["attributes"]["WEIGHTS_0"]]["bufferView"]]
                jv = g["bufferViews"][g["accessors"][pr["attributes"]["JOINTS_0"]]["bufferView"]]
                for k in range(0, min(60, g["accessors"][pr["attributes"]["WEIGHTS_0"]]["count"])):
                    w4 = struct.unpack_from("<4B", blob, wv["byteOffset"] + 4 * k)
                    j4 = struct.unpack_from("<4B", blob, jv["byteOffset"] + 4 * k)
                    self.assertEqual(sum(w4), 255)
                    self.assertTrue(all(j < len(rig.bones) for j, w in zip(j4, w4) if w))
            # byte-stable
            fish = B.make("angler", 3, log=QUIET)
            a, b = os.path.join(t, "a.glb"), os.path.join(t, "b.glb")
            glb.write_glb(a, fish, RG.build_rig(fish), "x")
            glb.write_glb(b, fish, RG.build_rig(fish), "x")
            self.assertEqual(open(a, "rb").read(), open(b, "rb").read())
            # a pose rides on the node; the catalogue roll for a lying plan exists, none for a standing one
            glb.write_glb(a, fish, None, "x", pose=(0.0, 0.0, 0.5, 0.8660254))
            self.assertEqual(read_glb(a)[0]["nodes"][0]["rotation"][2], 0.5)
            self.assertIsNotNone(glb.display_pose("flat"))
            self.assertIsNone(glb.display_pose("round"))

    def test_finishes_and_glow_ride_standard_extensions(self):
        with tempfile.TemporaryDirectory() as t:
            def bake(sp, gifts, seed=6):
                fish = B.make(sp, seed, gifts, log=QUIET)
                p = os.path.join(t, "f.glb")
                glb.write_glb(p, fish, RG.build_rig(fish), sp)
                return read_glb(p)[0], fish

            g, fish = bake("angler", ["bioluminescent"])
            flank = next(m for m in g["materials"] if m["name"] == "flank")
            self.assertIn("emissiveTexture", flank)
            self.assertIn("KHR_materials_emissive_strength", flank["extensions"])
            self.assertGreater(flank["extensions"]["KHR_materials_emissive_strength"]["emissiveStrength"], 2.0)
            self.assertTrue(any(i["name"] == "glow" for i in g["images"]))
            self.assertEqual(fish.eff["skin"]["kind"], "stars")
            self.assertGreater(sum(1 for r in skin2.glow_mask(fish.eff, fish.eff["palette"]) for p in r if p[0] > 0), 10)  # lit photophores
            bulb = next(m for m in g["materials"] if m["name"] == "bulb")
            self.assertIn("emissiveFactor", bulb)
            plain, _ = bake("angler", [])
            self.assertNotIn("emissiveTexture", next(m for m in plain["materials"] if m["name"] == "flank"))
            g, _ = bake("perch", ["shiny"])
            flank = next(m for m in g["materials"] if m["name"] == "flank")
            self.assertGreaterEqual(flank["pbrMetallicRoughness"]["metallicFactor"], 0.8)
            g, _ = bake("perch", ["shimmer"])
            self.assertIn("KHR_materials_iridescence", next(m for m in g["materials"] if m["name"] == "flank")["extensions"])
            g, _ = bake("perch", ["pearl"])
            ext = next(m for m in g["materials"] if m["name"] == "flank")["extensions"]
            self.assertIn("KHR_materials_sheen", ext)
            self.assertIn("KHR_materials_iridescence", ext)
            g, _ = bake("perch", ["holographic"])
            ir = next(m for m in g["materials"] if m["name"] == "flank")["extensions"]["KHR_materials_iridescence"]
            self.assertIn("iridescenceThicknessTexture", ir)
            self.assertIn("KHR_materials_clearcoat", next(m for m in g["materials"] if m["name"] == "iris")["extensions"])  # a wet eye
            self.assertTrue({"KHR_materials_iridescence", "KHR_materials_sheen", "KHR_materials_clearcoat"} >= set(g["extensionsUsed"]) - {"KHR_materials_emissive_strength"})


class Rigged(unittest.TestCase):
    def test_a_rest_pose_moves_nothing_and_a_wave_keeps_it_welded(self):
        fish = B.make("tuna", 3, log=QUIET)
        rig = RG.build_rig(fish)
        rest = RG.posed(rig, {})
        every = [v for t in skin_tris(fish) for v in t] + [v for p in fish.parts for v in p.verts()]
        for v in every[::7]:
            self.assertLess(math.dist(rest(v), v), 1e-9)
        for v, ws in rig.weights.items():
            self.assertAlmostEqual(sum(w for _, w in ws), 1.0, places=9)
        wave = RG.posed(rig, motion.spine_angles(rig, "round", math.pi / 2))
        self.assertGreater(max(math.dist(wave(v), v) for v in every), 0.01)  # it really moves
        for pt in fish.parts:  # a root is a body vertex: same tuple, same weights, so it posed to the same point
            if pt.parent == "skin":
                for r in pt.roots:
                    self.assertEqual(rig.weights[r], rig.weights[r])
                    self.assertEqual(wave(r), wave(r))
        pf = motion.posed_fish(fish, rig, motion.spine_angles(rig, "round", math.pi / 2))
        notes, comps = V._welded(skin_tris(pf), pf.parts, 1.0)
        self.assertEqual((notes, comps), ([], 1))

    def test_every_extreme_of_motion_holds_together(self):
        for sp in sorted(G.SPECIES):
            for seed in (1, 2):
                fish = B.make(sp, seed, log=QUIET)
                rig = RG.build_rig(fish)
                self.assertEqual(motion.validate_motion(fish, rig), [], "%s %d" % (sp, seed))
        # and the check is live: an exaggerated pose (every tentacle bent far past its limit) is caught
        fish = B.make("squid", 2, log=QUIET)
        rig = RG.build_rig(fish)
        crazy = {b: 1.4 for b, bone in enumerate(rig.bones) if bone.kind == "tube"}
        pf = motion.posed_fish(fish, rig, crazy)
        self.assertFalse(V.validate(pf, skip=frozenset({"silhouette", "proportions", "envelope", "complete"})).ok)
        self.assertEqual(sum(1 for b in rig.bones if b.kind == "jaw"), 0)
        # tentacle chains lag the body: a later joint of one chain peaks after an earlier one
        cat = B.make("mawfish", 2, log=QUIET)
        crig = RG.build_rig(cat)
        tube = [b for b, bone in enumerate(crig.bones) if bone.kind == "tube" and bone.group == "tent0"]
        self.assertGreaterEqual(len(tube), 3)
        peaks = [max(range(64), key=lambda k: motion.bone_pose(crig, "round", k / 64)[b]) for b in tube]
        self.assertNotEqual(peaks[0], peaks[-1])


class Variety(unittest.TestCase):
    def test_seeds_of_one_species_stay_unlike(self):
        mk = lambda sp, s: B.make(sp, s, log=QUIET)  # noqa: E731
        means = {}
        for sp in ("perch", "plaice", "catfish", "oarfish", "puffer", "skate"):
            r = variety.species_variety(sp, list(range(100, 110)), mk)
            means[sp] = r["mean"]
            self.assertLess(r["mean"], 0.78, "%s: seeds look alike (mean overlap %.2f)" % (sp, r["mean"]))
            self.assertLess(r["worst"], 0.95, "%s: two seeds are the same fish (%s)" % (sp, r["pair"]))
        # the instrument is live: ten copies of one seed overlap completely
        r = variety.species_variety("perch", [100] * 4, mk)
        self.assertAlmostEqual(r["mean"], 1.0)
        # different plans are far apart
        a, b = variety.silhouette(mk("squid", 1)), variety.silhouette(mk("sunfish", 1))
        self.assertLess(variety.overlap(a, b), 0.5)


class Sweep(unittest.TestCase):
    def test_seed_sweep_has_no_failure(self):
        stats = sweep.sweep(500)
        self.assertGreaterEqual(stats["runs"], 500)  # an empty sweep must not pass
        self.assertEqual(set(stats["by_plan"]), set(G.PLANS))
        self.assertGreaterEqual(len(stats["by_plan"]), 11)
        self.assertEqual(set(stats["by_kind"]), {"plain", "one", "pair"})
        self.assertNotIn("plain", stats["retried_by_kind"])  # a plain species draw never needs a retry
        mutated = stats["by_kind"]["one"] + stats["by_kind"]["pair"]
        self.assertLess(sum(stats["retried_by_kind"].values()), 0.25 * mutated)  # the genes are sane, not always broken
        self.assertGreater(sum(stats["retried_by_kind"].values()), 0)  # and the ladder is exercised
        self.assertEqual(sum(stats["final_strength"].values()), stats["runs"])
        self.assertLessEqual(stats["tris_max"], 1500)
        self.assertLess(stats["seconds"], 60)


class Pinned(unittest.TestCase):
    def test_vectors_hold(self):
        with open(vectors.PATH) as f:
            pinned = json.load(f)
        self.assertEqual(len(pinned), len(vectors.CASES))
        for want, case in zip(pinned, vectors.CASES):
            self.assertEqual(vectors.vector(*case), want, "%s %d" % case[:2])


    def test_motion_vectors_hold(self):
        with open(vectors.MOTION_PATH) as f:
            pinned = json.load(f)
        self.assertEqual([v["slug"] for v in pinned], list(vectors.MOTION_SLUGS))
        fresh = vectors.compute_motion()
        # The rigs exactly; the angles to 1e-12 (libm's sin differs in the last digit across platforms: d2070 vs a Mac)
        self.assertEqual([v["rig"] for v in fresh], [v["rig"] for v in pinned])
        for f, p in zip(fresh, pinned):
            self.assertEqual(len(f["poses"]), len(p["poses"]), f["slug"])
            for fp, pp in zip(f["poses"], p["poses"]):
                self.assertEqual((fp["t"], fp["hz"], fp["gape"], len(fp["angles"])), (pp["t"], pp["hz"], pp["gape"], len(pp["angles"])), f["slug"])
                self.assertLess(max(abs(x - y) for x, y in zip(fp["angles"], pp["angles"])), 1e-12, f["slug"])
        # every motion shape is in it: a jaw, a tube chain, the flatfish's up-and-down wave, the hammerhead
        kinds = {b[1] for v in pinned for b in v["rig"]["bones"]}
        self.assertEqual(kinds, {"spine", "jaw", "tube"})
        self.assertIn("flat", {v["rig"]["plan"] for v in pinned})
        self.assertTrue(any(abs(a) > 0.05 for v in pinned for p in v["poses"] for a in p["angles"]))  # it swims


class Stdlib(unittest.TestCase):
    def test_v2_imports_without_pillow(self):
        mods = [m[:-3] for m in os.listdir(HERE) if m.endswith(".py") and not m.startswith("test_") and m != "sheet.py"]
        code = "import sys; sys.modules['PIL'] = None; sys.path.insert(0, %r)\n" % os.path.dirname(os.path.dirname(HERE)) + "".join("import norna_fishdraw.v2.%s\n" % m for m in sorted(mods) if m != "__init__")
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        self.assertEqual(r.returncode, 0, r.stderr)


class InGame(unittest.TestCase):
    def test_the_bake_manifest_names_every_game_species(self):
        man = json.load(open(os.path.join(BAKED, "fish.json")))
        self.assertEqual(man["generator"], "fishdraw v2 bake --game")
        self.assertEqual(man["species"], list(game.SLUGS))

    def test_every_catchable_slug_is_a_v2_species(self):
        slugs = list(game.SLUGS)
        self.assertEqual(len(slugs), 110)  # 13 originals, 13 water-tier, 6 rod-locked, flatfish, hammerhead, big-eye, the lagoon's three, wave 2's seventy, brook minnow, lake crayfish
        self.assertEqual(set(slugs), set(game.GAME))
        self.assertTrue({"ribbon", "eel", "disc", "armoured", "flat", "hammerhead"} <= {game.GAME[s]["plan"] for s in slugs})
        self.assertIn("lure", G.draw("fathom-cod", game.CANON["fathom-cod"])["parts"])  # the deep's angler
        self.assertEqual(G.draw("soulfish", 1)["finish"]["kind"], "ghost")

    def test_the_game_bake_is_stable(self):
        # the same bake twice: identical sizes and manifest, GLBs equal up to platform rounding
        from norna_fishdraw.test_fishdraw import _assert_same_glb

        models = BAKED
        with tempfile.TemporaryDirectory() as t:
            doc = bake.bake_game(t, log=QUIET)
            self.assertEqual(len(doc["models"]), 110)
            for name in sorted(os.listdir(t)):
                a, b = open(os.path.join(t, name), "rb").read(), open(os.path.join(models, name), "rb").read()
                if name.endswith(".glb"):  # libm / zlib builds differ in the last digit: compare quantised content
                    _assert_same_glb(self, a, b, name)
                else:
                    self.assertEqual(a, b, name)
        for slug, m in doc["models"].items():  # whole fish, tail and jaw included, at v1's median length
            self.assertAlmostEqual(m["dims"][2], m["lengthM"], delta=0.02 * m["lengthM"], msg=slug)
            self.assertLessEqual(m["tris"], V.TRI_BUDGET.get(slug, V.TRI_BUDGET.get(m["plan"], V.DEFAULT_BUDGET)), slug)

    def test_game_glbs_are_skinned_and_the_manifest_carries_their_rig(self):
        models = BAKED
        man = json.load(open(os.path.join(models, "fish.json")))
        for slug in game.SLUGS:
            g, _ = read_glb(os.path.join(models, slug + ".glb"))
            joints = [g["nodes"][j]["name"] for j in g["skins"][0]["joints"]]
            rig = man["models"][slug]["rig"]
            self.assertEqual([b[0] for b in rig["bones"]], joints, slug)
            self.assertEqual(rig["plan"], man["models"][slug]["plan"], slug)
            self.assertTrue(all(rig["bones"][i][1] == "spine" for i in rig["spine"]), slug)
            self.assertGreaterEqual(len(rig["spine"]), 6, slug)
            # a lying plan's pose rides a root above mesh and skeleton (a skinned node's own transform is ignored)
            root = g["nodes"][g["scenes"][0]["nodes"][0]]
            if man["models"][slug]["plan"] == "flat":
                self.assertEqual(root["children"], [0, 1], slug)
                self.assertIn("rotation", root, slug)
            self.assertNotIn("rotation", g["nodes"][0], slug)

    def test_game_seed_sweep_has_no_failure(self):
        stats = sweep.sweep(330, sweep.game_cases)
        self.assertEqual(stats["runs"], 330)
        self.assertEqual(stats["by_kind"], {"plain": 110, "one": 110, "pair": 110})  # every slug, once per kind
        self.assertEqual(set(stats["by_plan"]), {"round", "disc", "eel", "ribbon", "armoured", "flat", "hammerhead", "ray", "globe", "seahorse", "squid"})
        self.assertNotIn("plain", stats["retried_by_kind"])  # every slug's own fish builds whole at full strength
        self.assertEqual(sum(stats["final_strength"].values()), 330)


class WaveTwo(unittest.TestCase):
    def test_wave_two_species_are_calibrated_and_held_apart(self):
        from norna_fishdraw.v2 import calibrate, distinct
        from norna_fishdraw.v2.game2 import GAME2

        self.assertEqual(len(GAME2), 70)
        self.assertEqual(calibrate.main(["--check"]), 0)
        self.assertEqual(distinct.too_alike(), [])
        a, b = (variety.silhouette(B.make(s, game.CANON[s], log=QUIET)) for s in ("frost-char", "rill-trout"))
        self.assertGreater(variety.overlap(a, b), distinct.CAP)  # the instrument is live: the old pair it does not guard overlaps whole


if __name__ == "__main__":
    unittest.main()
