"""The v2 contact sheet: every body plan x 6 seeds, the validator's retried cells, and the known-break fixtures.

    python3 norna_fishdraw/v2/sheet.py [OUT_DIR]     # default out/sheets/s2-*.png
    python3 norna_fishdraw/v2/sheet.py --game [OUT.png [MODELS_DIR]] [--only a,b]   # the shipped game fish

A painter's-algorithm flat-shaded view (Pillow only draws polygons; no numpy, no GPU). Not a gate: a human (or a vision
judge) reads it. Cell frames: green = built clean, orange = the validator retried it at weaker gene strength (the
rejected attempt is the red-framed inset), red = rejected outright (the fixtures).
"""

from __future__ import annotations

import math
import os
import sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from norna_fishdraw.v2 import genome as G  # noqa: E402
from norna_fishdraw.v2.build import build, make, make_from  # noqa: E402
from norna_fishdraw.v2.fixtures import FIXTURES  # noqa: E402
from norna_fishdraw.v2.surface import add, cross, dot, mul, norm, sub  # noqa: E402
from norna_fishdraw.v2.sweep import cases  # noqa: E402
from norna_fishdraw.v2.validate import validate  # noqa: E402


CELL_W, CELL_H, CAP_H = 320, 210, 62
BG, CAP_BG = (22, 30, 42), (14, 18, 26)
ROW_SPECIES = {
    "round": ("perch", "pike", "catfish", "angler", "angler", "pike"),
    "flat": ("plaice",) * 6,
    "ribbon": ("oarfish",) * 6,
    "hammerhead": ("hammerhead",) * 6,
}
ROW_GIFTS = (0, 1, 1, 2, 2, 1)  # mutations per cell: plain, mutant, mutant, legend, legend, mutant
ELEVATION = {"flat": 52.0, "hammerhead": 42.0}


def _font(size):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _hex(c):
    return tuple(int(c[i : i + 2], 16) for i in (1, 3, 5))


def render(mesh, palette, plan="round", w=CELL_W, h=CELL_H - 0, az=32.0, el=None):
    el = math.radians(el if el is not None else ELEVATION.get(plan, 20.0))
    a = math.radians(az)
    d = (-math.cos(el) * math.cos(a), math.sin(el), math.cos(el) * math.sin(a))  # toward the camera, off the -X flank
    f = mul(d, -1.0)
    right = norm(cross(f, (0.0, 1.0, 0.0)))
    up = cross(right, f)
    light = norm(add(add(mul(up, 0.8), mul(right, -0.4)), mul(d, 0.5)))
    tris = []
    for role, ts in mesh.tris.items():
        col = _hex(palette.get(role, "#cccccc"))
        for t in ts:
            if all(c == c for p in t for c in p):  # a NaN face (a fixture) is not drawn
                tris.append((role, col, t))
    pts = [p for _, _, t in tris for p in t]
    sx = [dot(p, right) for p in pts]
    sy = [dot(p, up) for p in pts]
    S = 3
    scale = min((w * S * 0.9) / (max(sx) - min(sx)), (h * S * 0.9) / (max(sy) - min(sy)))
    cx, cy = (max(sx) + min(sx)) / 2, (max(sy) + min(sy)) / 2
    img = Image.new("RGB", (w * S, h * S), BG)
    dr = ImageDraw.Draw(img)
    order = sorted(tris, key=lambda rt: sum(dot(p, d) for p in rt[2]))
    for role, col, t in order:
        n = norm(cross(sub(t[1], t[0]), sub(t[2], t[0])))
        if dot(n, d) < 0:
            n = mul(n, -1.0)
        k = 1.0 if role == "bulb" else 0.35 + 0.65 * max(0.0, dot(n, light))
        shade = tuple(min(255, int(c * k)) for c in col)
        poly = [(w * S / 2 + (dot(p, right) - cx) * scale, h * S / 2 - (dot(p, up) - cy) * scale) for p in t]
        dr.polygon(poly, fill=shade)
    return img.resize((w, h), Image.LANCZOS)


def _cell(img, title, sub_line, status, color, inset=None):
    out = Image.new("RGB", (CELL_W, CELL_H + CAP_H), CAP_BG)
    out.paste(img.resize((CELL_W, CELL_H), Image.LANCZOS) if img.size != (CELL_W, CELL_H) else img, (0, 0))
    dr = ImageDraw.Draw(out)
    dr.rectangle([0, 0, CELL_W - 1, CELL_H + CAP_H - 1], outline=color, width=3)
    dr.text((8, CELL_H + 4), title, font=_font(14), fill=(235, 235, 240))
    dr.text((8, CELL_H + 22), sub_line, font=_font(12), fill=(170, 180, 195))
    dr.text((8, CELL_H + 40), status, font=_font(12), fill=color)
    return out


def _gifts(g):
    return ", ".join("%s %.1f" % (x["gene"], x["x"]) for x in g["gift"]) or "plain"


def fish_cell(g, fish=None, az=32.0, el=None):
    fish = fish or make_from(g, log=lambda *a: None)
    img = render(fish.mesh(), g["palette"], g["plan"], w=CELL_W, h=CELL_H, az=az, el=el)
    title = "%s #%d  %.2f m" % (g["species"], g["seed"], g["len_m"])
    if fish.attempts:
        return _cell(img, title, _gifts(g), "RETRIED 1.0 -> %.1f" % fish.strength, (240, 160, 40))
    return _cell(img, title, _gifts(g), "ok, built at full strength", (70, 190, 110))


def retried_pair(g, fish):
    """Two cells side by side: the rejected full-strength attempt (red) and what shipped (orange), so nothing is hidden."""
    s0, rep0 = fish.attempts[0]
    bad = build(g, s0)
    a = _cell(render(bad.mesh(), g["palette"], g["plan"], w=CELL_W, h=CELL_H), "%s #%d rejected" % (g["species"], g["seed"]), _gifts(g), "REJECTED at 1.0: " + ", ".join(rep0.failed()), (220, 60, 60))
    return [a, fish_cell(g, fish)]


def fixture_cell(name, fn):
    fish, expected = fn()
    rep = validate(fish)
    g = fish.genome
    img = render(fish.mesh(), g["palette"], g["plan"], w=CELL_W, h=CELL_H)
    return _cell(img, name, "%s #%d, known break" % (g["species"], g["seed"]), "REJECTED: " + ", ".join(rep.failed()), (220, 60, 60))


def retried_cases(n=3):
    out = []
    for sp, seed, kind, gifts in cases(500):
        g = G.draw(sp, seed, gifts)
        if not gifts:
            continue
        fish = make_from(g, log=lambda *a: None)
        if fish.attempts and all(o[0]["species"] != sp for o in out):
            out.append((g, fish))
        if len(out) >= n:
            break
    return out


def blank():
    return Image.new("RGB", (CELL_W, CELL_H + CAP_H), BG)


def _row_of(cells, per=6):
    cells = list(cells)
    while len(cells) % per:
        cells.append(blank())
    return [cells[i : i + per] for i in range(0, len(cells), per)]


def paste_rows(rows, labels, title, per=6):
    head = 34
    sheet = Image.new("RGB", (CELL_W * per, 40 + sum(head + CELL_H + CAP_H for _ in rows)), (10, 12, 18))
    dr = ImageDraw.Draw(sheet)
    dr.text((10, 8), title, font=_font(18), fill=(235, 235, 240))
    y = 40
    for label, cells in zip(labels, rows):
        dr.text((10, y + 8), label, font=_font(16), fill=(120, 190, 230))
        y += head
        for i, c in enumerate(cells):
            sheet.paste(c, (i * CELL_W, y))
        y += CELL_H + CAP_H
    return sheet


def flags_row(out_dir):
    """The S1 review flags: the two retried angler cells, S1 above / now below, 3/4 and head-on."""
    cells = []
    before = os.path.join(out_dir, "before")
    for seed, gifts in ((10070, [{"gene": "bigeye", "x": 0.632}]), (10077, [{"gene": "fanged", "x": 0.687}, {"gene": "gigantism", "x": 0.928}])):
        g = G.draw("angler", seed, gifts)
        for view, az in (("3q", 32.0), ("front", 88.0)):
            p = os.path.join(before, "s1-%d-%s.png" % (seed, view))
            if os.path.exists(p):
                cells.append(_cell(Image.open(p).convert("RGB"), "angler #%d  S1" % seed, _gifts(g), "BEFORE: block above the eye, plank jaw, hex eye", (220, 60, 60)))
        for view, az in (("3q", 32.0), ("front", 88.0)):
            fish = make_from(g, log=lambda *a: None)
            cells.append(_cell(render(fish.mesh(), g["palette"], "round", w=CELL_W, h=CELL_H, az=az), "angler #%d  now" % seed, _gifts(g), "AFTER: sockets, jaw with lip and gape, retried whole" if fish.attempts else "AFTER: sockets, lip and gape, built whole", (70, 190, 110)))
    return cells


def tentacle_cells():
    out = []
    for sp, seed in (("catfish", 4), ("mawfish", 3), ("squid", 2), ("squid", 7), ("angler", 5), ("sturgeon", 3)):
        g = G.draw(sp, seed)
        fish = make_from(g, log=lambda *a: None)
        n = sum(1 for p in fish.parts if p.kind in ("tentacle", "arm", "barbel", "stalk"))
        out.append(fish_cell(g, fish, az=20.0))
        out[-1] = _cell(render(fish.mesh(), g["palette"], g["plan"], w=CELL_W, h=CELL_H, az=20.0), "%s #%d  %d sub-spines" % (sp, seed, n), "whiskers, mouth ring, arms and clubs, lure", "welded rings of six, tapering, with suckers or a club" if sp in ("squid", "mawfish") else "welded rings of six", (70, 190, 110))
    return out


def variety_sheet(species, n=24, base=200, per=6):
    cells = []
    for k in range(n):
        g = G.draw(species, base + k)
        fish = make_from(g, log=lambda *a: None)
        cells.append(_cell(render(fish.mesh(), g["palette"], g["plan"], w=CELL_W, h=CELL_H), "%s #%d" % (species, base + k), "skin: %s" % g["skin"]["kind"], "%.2f m" % g["len_m"], (70, 190, 110)))
    return paste_rows(_row_of(cells, per), ["%s: %d seeds of one species" % (species, n)] + [""] * (len(cells) // per - 1), "norna-fishdraw v2: variety of ONE species", per)


def zoo_sheet(n=48, per=8):
    names = sorted(G.SPECIES, key=lambda s: (G.PLANS.index(G.SPECIES[s]["plan"]), s))
    cells = []
    for k in range(n):
        sp = names[k % len(names)]
        seed = 500 + k
        g = G.draw(sp, seed)
        fish = make_from(g, log=lambda *a: None)
        cells.append(_cell(render(fish.mesh(), g["palette"], g["plan"], w=CELL_W, h=CELL_H), "%s #%d" % (sp, seed), g["plan"], "%.2f m" % g["len_m"], (70, 190, 110)))
    return paste_rows(_row_of(cells, per), [""] * (len(cells) // per), "norna-fishdraw v2: zoo, %d seeds across every plan" % n, per)


def game_sheet(out_path, models_dir=None, only=None):
    """The game fish as shipped (`only`: those slugs alone): per slug the baked GLB through the bag icon's rasteriser (textures, its light), then
    the same fish flat-shaded at 3/4 and head-on, so a broken, floating or inside-out part shows from three sides."""
    from pathlib import Path

    from norna_fishdraw.v2 import compare
    from norna_fishdraw.v2 import game as GM

    models = Path(models_dir) if models_dir else Path(compare.icons.MODELS)
    tw, per = 230, 2
    block = tw + 2 * CELL_W
    cells = []
    for slug in only or GM.SLUGS:
        g = G.draw(slug, GM.CANON[slug])
        fish = make_from(g, log=lambda *a: None)
        im = Image.new("RGB", (block, CELL_H + CAP_H), CAP_BG)
        t = compare.tile(models / (slug + ".glb")).resize((tw, tw), Image.LANCZOS)
        bg = Image.new("RGBA", t.size, (52, 44, 38, 255))
        bg.alpha_composite(t)
        im.paste(bg.convert("RGB"), (0, 0))
        im.paste(render(fish.mesh(), g["palette"], g["plan"], az=32.0), (tw, 0))
        im.paste(render(fish.mesh(), g["palette"], g["plan"], az=82.0, el=12.0), (tw + CELL_W, 0))
        dr = ImageDraw.Draw(im)
        dr.rectangle([0, 0, block - 1, CELL_H + CAP_H - 1], outline=(70, 190, 110), width=2)
        dims = [round(max(p[i] for ts in fish.mesh().tris.values() for t in ts for p in t) - min(p[i] for ts in fish.mesh().tris.values() for t in ts for p in t), 3) for i in range(3)]
        dr.text((8, CELL_H + 6), "%s  (%s plan, skin %s%s)" % (slug, g["plan"], g["skin"]["kind"], ", " + g["finish"]["kind"] if g["finish"]["kind"] != "none" else ""), font=_font(15), fill=(235, 235, 240))
        dr.text((8, CELL_H + 28), "%.2f m long, %d tris, parts: %s" % (dims[2], fish.mesh().count(), ", ".join(sorted({pt.kind for pt in fish.parts}))), font=_font(12), fill=(170, 180, 195))
        cells.append(im)
    rows = [cells[i : i + per] for i in range(0, len(cells), per)]
    sheet = Image.new("RGB", (block * per, 40 + len(rows) * (CELL_H + CAP_H)), (10, 12, 18))
    ImageDraw.Draw(sheet).text((10, 10), "norna-fishdraw v2 in game: the %d catchable fish as shipped (bag icon | 3/4 | head-on)" % len(cells), font=_font(18), fill=(235, 235, 240))
    for r, row in enumerate(rows):
        for c, im in enumerate(row):
            sheet.paste(im, (c * block, 40 + r * (CELL_H + CAP_H)))
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    sheet.save(out_path)
    return out_path


def main(argv):
    if argv[:1] == ["--game"]:
        only = None
        if "--only" in argv:
            k = argv.index("--only")
            only, argv = argv[k + 1].split(","), argv[:k] + argv[k + 2 :]
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        print(game_sheet(argv[1] if len(argv) > 1 else os.path.join(root, "out", "sheets", "game-sheet.png"), argv[2] if len(argv) > 2 else None, only))
        return
    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "out", "sheets")
    if argv:
        out_dir = argv[0]
    rows, labels = [], []
    seed_species = {"round": ("perch", "pike", "catfish", "angler", "tuna", "carp"), "flat": ("plaice",) * 6, "ribbon": ("oarfish",) * 6, "eel": ("eel", "moray") * 3,
                    "hammerhead": ("hammerhead",) * 6, "globe": ("puffer",) * 6, "disc": ("sunfish", "angelfish") * 3, "armoured": ("sturgeon",) * 6, "ray": ("skate",) * 6, "seahorse": ("seahorse",) * 6, "squid": ("squid",) * 6}
    for pi, plan in enumerate(G.PLANS):
        cells = []
        for i in range(6):
            seed = 1000 * (pi + 1) + i
            g = G.draw(seed_species[plan][i], seed, G.roll_gifts(seed, (0, 1, 1, 2, 2, 1)[i]))
            cells.append(fish_cell(g, el=45.0 if plan in ("flat", "ray") else None))
        rows.append(cells)
        labels.append(plan)
    retried = []
    for g, f in retried_cases(3):
        retried += retried_pair(g, f)
    rows += _row_of(retried)
    labels += ["retried by the validator: rejected | shipped"] + [""] * (len(_row_of(retried)) - 1)
    rows += _row_of(tentacle_cells())
    labels += ["sub-spine parts: whiskers, mouth ring, arms and clubs, lure"]
    rows += _row_of(flags_row(out_dir))
    labels += ["Review flags (S1 above, S2 below): two seeds, 3/4 and head-on"] + [""] * (len(_row_of(flags_row(out_dir))) - 1)
    fx = [fixture_cell(k, fn) for k, fn in FIXTURES.items()]
    rows += _row_of(fx)
    labels += ["known breaks (must be rejected)"] + [""] * (len(_row_of(fx)) - 1)
    paste_rows(rows, labels, "norna-fishdraw v2, slice S2: plans x 6 seeds, retries, sub-spines, review flags, known breaks").save(os.path.join(out_dir, "s2-sheet.png"))
    variety_sheet("perch").save(os.path.join(out_dir, "s2-variety-perch.png"))
    variety_sheet("plaice").save(os.path.join(out_dir, "s2-variety-plaice.png"))
    zoo_sheet().save(os.path.join(out_dir, "s2-zoo.png"))
    print("sheets in", out_dir)


if __name__ == "__main__":
    main(sys.argv[1:])
