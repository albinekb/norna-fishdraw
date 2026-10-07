"""Seventy more catchable species (fishdraw wave 2): the ponds' roach and tench, the shore's plaice and haddock, the warm isle's
lionfish, the deep sea's giants and four legends, each a v2 genome like `game.py`'s thirty-eight.

A slug here is an archetype's plan with every gene PINNED to one value (`pin`: the archetype's midpoint, then the
slug's own numbers), so the canonical fish is the one written down and not a draw inside a range. `BODY_LEN2` is the
body length gene that makes the baked fish, tail and jaw included, the median length `presets.py` gives the slug; it is
written by `python3 norna_fishdraw/v2/calibrate.py` and read back by `game.game`. Colours, skin and sizes come
from the v1 table like every other slug; the server's rows are `fish_loot.FISH_TABLE`.

Every pair of species is held apart by `distinct.py` (side and top silhouette overlap against all the others).
"""

from __future__ import annotations

from .game import BODY_LEN, ADIPOSE, CHIN_BARBEL, FORKED, LUNATE, QUIET_JAW, ROUNDED, SECOND_DORSAL, TRUNCATE, game
from .genome import ARMOURED, DISC, EEL, FLAT, GLOBE, HAMMER, JAW, LURE, RAY, RIBBON, ROUND, SEAHORSE, SQUID, WHISK, R



def pin(base: dict, **over) -> dict:
    """Every gene of `base` at the middle of its range (a gate stays a gate), then `over`'s own values on top."""
    out = {k: (v if k.endswith("?") else R(round((v[0] + v[1]) / 2, 5))) for k, v in base.items()}
    out.update(over)
    return out


def V(x, y=None):
    return R(x, x if y is None else y)


def body(**kw):
    """`body(h=.2, w=.5, pk=.37)`: the body genes by short name."""
    names = dict(h="height", w="width", pk="peak", np="nose_p", nose="nose", tail="tail", taper="taper", hump="hump", sag="sag", brow="brow", pinch="pinch",
                 curve="curve", flick="flick", nt="nt", nb="nb", rost="rostrum", up="snout_up", head="head", curl="curl", bill="bill")
    return {"body." + names[k]: V(v) for k, v in kw.items()}


def fin(name, s0, s1, h, m=None):
    out = {"parts.%s.s0" % name: V(s0), "parts.%s.s1" % name: V(s1), "parts.%s.h" % name: V(h)}
    if m is not None:
        out["parts.%s.membrane" % name] = V(m)
    return out


def dor(s0, s1, h, m=None):
    return fin("dorsal", s0, s1, h, m)


def ana(s0, s1, h, m=None):
    return fin("anal", s0, s1, h, m)


def dor2(s0, s1, h, m=0.5):
    return {"parts.dorsal2?": R(1.0), **fin("dorsal2", s0, s1, h, m)}


def pec(ln, s=None, filament=None):
    out = {"parts.pectoral.len": V(ln)}
    if s is not None:
        out["parts.pectoral.s"] = V(s)
    if filament is not None:
        out["parts.pectoral.filament"] = V(filament)
    return out


def pel(ln, s=None):
    out = {"parts.pelvic.len": V(ln)}
    if s is not None:
        out["parts.pelvic.s"] = V(s)
    return out


def tl(shape, ln=None, lobe=None, fork=None, streamer=None):
    out = {"parts.tail.shape": V(shape)}
    for k, v in (("len", ln), ("lobe", lobe), ("fork", fork), ("streamer", streamer)):
        if v is not None:
            out["parts.tail." + k] = V(v)
    return out


def eye(size=None, bulge=None, k=None, theta=None):
    out = {}
    for name, v in (("size", size), ("bulge", bulge), ("k", k), ("theta", theta)):
        if v is not None:
            out["parts.eye." + name] = V(v)
    return out


def jaw(proj, drop, gape, teeth=0, tooth=0.25, slope=0.0):
    return {"parts.jaw.proj": V(proj), "parts.jaw.drop": V(drop), "parts.jaw.gape": V(gape), "parts.jaw.slope": V(slope), "parts.jaw.teeth": V(teeth), "parts.jaw.tooth": V(tooth), "parts.jaw.up": V(0)}


def barbels(n, ln, tip=0.15, curl=0.3):
    return {"parts.barbels.n": V(n), "parts.barbels.len": V(ln), "parts.barbels.tip": V(tip), "parts.barbels.curl": V(curl)}


def lure(stalk, bulb=0.9, s=0.085, curl=0.8):
    return {"parts.lure.s": V(s), "parts.lure.stalk": V(stalk), "parts.lure.bulb": V(bulb), "parts.lure.curl": V(curl)}


def finlets(n, h):
    return {"parts.finlets?": R(1.0), "parts.finlets.n": V(n), "parts.finlets.h": V(h)}


def scutes(rows, h):
    return {"parts.scutes?": R(1.0), "parts.scutes.rows": V(rows), "parts.scutes.h": V(h)}


def wart(h, step=2):
    return {"parts.wart?": R(1.0), "parts.wart.h": V(h), "parts.wart.step": V(step)}


def frill(s0, s1, h, m=0.6):
    return {"parts.frill?": R(1.0), **fin("frill", s0, s1, h, m)}


def adipose(s0=0.7, s1=0.76, h=0.4):
    return {"parts.dorsal2?": R(1.0), "parts.dorsal2.s0": V(s0), "parts.dorsal2.s1": V(s1), "parts.dorsal2.h": V(h), "parts.dorsal2.membrane": V(0.85)}


#: a round-plan start: no hump, sag or brow, a modest peduncle, no streamers, no filament
RB = pin(ROUND, **{"body.hump": V(0), "body.sag": V(0), "body.brow": V(0), "body.pinch": V(0.12), "body.curve": V(0), "parts.pectoral.filament": V(0), "parts.tail.streamer": V(0)})
EB = pin(EEL)
DB = pin(DISC, **{"body.hump": V(0), "body.sag": V(0), "body.brow": V(0), "body.pinch": V(0.1), "parts.tail.fork": V(0.3)})
FB = pin(FLAT, **{"body.hump": V(0), "body.pinch": V(0), "body.curve": V(0)})
RAYB = pin(RAY)
GB = pin(GLOBE, **{"body.sag": V(0), "body.pinch": V(0.3)})
HB = pin(HAMMER)
SB = pin(SEAHORSE, **{"body.brow": V(0)})
QB = pin(SQUID, **{"parts.arms.n": V(8), "parts.club.n": V(2)})
RIB = pin(RIBBON)
AB = pin(ARMOURED)


def g2(slug, plan, base, *parts, pal=None, skins=None, finish=None):
    over: dict = {}
    for p in parts:
        over.update(p)
    return game(slug, plan, base, over, None, pal=pal, skins=skins, widen=1.0, finish=finish)


#: the body length gene per new slug (nose to tail root, metres): written by calibrate.py, never by hand
# BODY_LEN2 begin
BODY_LEN2: dict[str, float] = {
    "crucian-carp": 0.187,
    "roach": 0.186,
    "ruffe": 0.1079,
    "gudgeon": 0.1195,
    "bullhead": 0.0959,
    "stickleback": 0.0725,
    "tench": 0.3374,
    "ide": 0.2808,
    "zander": 0.438,
    "burbot": 0.4718,
    "whitefish": 0.3047,
    "sun-perch": 0.1444,
    "wels": 1.1939,
    "icicle-eel": 0.5979,
    "frostjaw": 0.4526,
    "ember-ray": 0.7842,
    "forge-bream": 0.2622,
    "sulfur-eel": 0.6448,
    "gall-lumpfish": 0.2453,
    "lantern-bleak": 0.0927,
    "wisp-fish": 0.1637,
    "cave-eel": 0.5475,
    "mimir-carp": 0.5676,
    "norn-trout": 0.3044,
    "hoard-carp": 0.4663,
    "sprat": 0.0906,
    "sandeel": 0.2175,
    "dab": 0.1965,
    "sea-scorpion": 0.1722,
    "ballan-wrasse": 0.2584,
    "grey-mullet": 0.3441,
    "whiting": 0.2427,
    "pipefish": 0.2463,
    "rockling": 0.2338,
    "flying-fish": 0.2168,
    "haddock": 0.4514,
    "sand-plaice": 0.3702,
    "turbot": 0.4481,
    "dapple-skate": 0.6842,
    "sea-bass": 0.395,
    "lumpsucker": 0.2638,
    "conger": 1.4206,
    "cuckoo-wrasse": 0.2174,
    "red-gurnard": 0.2538,
    "tide-seahorse": 0.3906,
    "pufferfish": 0.2324,
    "sun-angelfish": 0.1903,
    "cuttlefish": 0.2902,
    "ribbonfish": 0.9526,
    "triggerfish": 0.2184,
    "spurdog": 0.8177,
    "boxfish": 0.1782,
    "halibut": 1.3696,
    "monkfish": 0.7286,
    "ocean-sunfish": 1.0192,
    "swordfish": 1.7129,
    "john-dory": 0.3335,
    "thornback-ray": 0.7794,
    "sailfish": 1.7722,
    "coral-lionfish": 0.2595,
    "sunray": 1.5576,
    "sea-dragon": 0.7497,
    "draugr-eel": 1.6253,
    "greenland-shark": 1.7946,
    "opah": 0.7261,
    "grouper": 0.7338,
    "barracuda": 1.0985,
    "jormungand-thread": 1.8816,
    "kraken-whelp": 0.7818,
    "hel-halibut": 1.6186,
}
# BODY_LEN2 end
BODY_LEN.update(BODY_LEN2)

GAME2: dict[str, dict] = {

    # ================================================================ the ponds, brooks and lakes
    "crucian-carp": g2("crucian-carp", "round", RB, body(h=.4, w=.45, pk=.42, np=2.4, hump=.16, taper=1.3), dor(.28, .72, .9, .6), pec(.9), pel(.7), ana(.66, .8, .6), tl(3, .8, .7, .2), eye(.22)),
    "roach": g2("roach", "round", RB, body(h=.32, w=.42, pk=.38, np=2.0, taper=1.5), dor(.42, .6, 1.1, .5), pec(1.1), pel(.9), ana(.6, .8, .8, .6), tl(0, 1.1, .9, .5), eye(.26)),
    "ruffe": g2("ruffe", "round", RB, body(h=.3, w=.5, pk=.3, np=2.6, taper=1.5, pinch=0), dor(.22, .78, 1.3, .5), pec(1.2), pel(.8), ana(.62, .74, .7), tl(1, .7, .7, .1), eye(.32)),
    "gudgeon": g2("gudgeon", "round", RB, body(h=.17, w=.75, pk=.4, np=2.0), dor(.36, .52, .9, .5), pec(1.4), pel(.8), ana(.62, .72, .6), tl(0, 1.0, .8, .45), eye(.22), barbels(2, .6)),
    "bullhead": g2("bullhead", "round", RB, body(h=.24, w=1.1, pk=.2, np=3.2, taper=3.0, pinch=0), dor(.26, .4, .8, .5), dor2(.5, .66, .6), pec(2.0), pel(.8), ana(.62, .78, .5), tl(1, .8, .8, .1), eye(.3, 1.1, theta=80), jaw(.3, .3, 8)),
    "stickleback": g2("stickleback", "round", RB, body(h=.22, w=.4, pk=.4), dor(.3, .55, 2.0, .08), pec(.8), pel(1.8), ana(.62, .74, .6, .3), tl(0, .9, .7, .4), eye(.28), scutes(3, .12)),
    "tench": g2("tench", "round", RB, body(h=.3, w=.6, pk=.42, np=2.6, taper=1.2, pinch=.05), dor(.5, .66, .8, .85), pec(.9), pel(1.0), ana(.66, .8, .7, .85), tl(1, .8, .9, .1), eye(.14), barbels(1, .3)),
    "ide": g2("ide", "round", RB, body(h=.3, w=.5, pk=.34, np=1.4, hump=.1), dor(.38, .54, 1.0, .5), pec(1.1), pel(1.1), ana(.62, .8, .9, .5), tl(0, 1.3, 1.1, .5), eye(.24)),
    "zander": g2("zander", "round", RB, body(h=.17, w=.5, pk=.42, np=1.5, taper=2.0), dor(.3, .48, 1.3, .3), dor2(.58, .74, .8, .5), pec(1.0), pel(.8), ana(.66, .78, .7), tl(3, 1.1, .9, .15), eye(.28), jaw(1.0, .4, 8, 4, .3)),
    "burbot": g2("burbot", "round", RB, body(h=.22, w=.8, pk=.3, np=2.4, taper=1.5), dor(.26, .34, .7, .5), dor2(.42, .88, .5, .85), pec(1.2), pel(.7), ana(.5, .9, .45, .85), tl(1, .5, .6, .1), eye(.16), barbels(1, .5)),
    "whitefish": g2("whitefish", "round", RB, body(h=.29, w=.38, pk=.42, np=1.8, hump=.12), dor(.38, .5, 1.0, .5), adipose(), pec(.9), pel(.8), ana(.64, .78, .6), tl(0, 1.15, .95, .6), eye(.24)),
    "sun-perch": g2("sun-perch", "disc", DB, body(h=.62, w=.22), dor(.3, .75, .9, .6), ana(.4, .74, .8, .6), pec(.45), pel(.8), tl(1, .3, .3, .1), eye(.26)),
    "wels": g2("wels", "round", RB, body(h=.17, w=1.1, pk=.3, np=3.0, taper=1.3, pinch=0), dor(.3, .36, .3, .5), pec(1.0), pel(.7), ana(.45, .92, .6, .9), tl(1, .6, .5, .1), eye(.12), barbels(4, 1.2), jaw(.3, .3, 12)),
    "icicle-eel": g2("icicle-eel", "eel", EB, body(h=.06, w=.9, nose=.4, curve=.03), dor(.15, .94, .5, .9), ana(.4, .94, .4, .9), pec(.5), eye(.28), finish="ghost"),
    "frostjaw": g2("frostjaw", "round", RB, body(h=.22, w=.6, pk=.4, np=1.5), dor(.62, .76, 1.0, .5), ana(.64, .76, .8), pec(1.8), pel(.8), tl(3, 1.2, 1.0, .2), eye(.24), jaw(1.3, .5, 12, 8, .45), frill(.14, .7, .3)),
    "ember-ray": g2("ember-ray", "ray", RAYB, body(h=.07, w=7.0, pk=.4, np=1.6, taper=.8), fin("wing", .14, .7, .5, .8), dor(.78, .88, .8, .5), eye(.24)),
    "forge-bream": g2("forge-bream", "disc", DB, body(h=.52, w=.3, pk=.45, hump=.1), dor(.3, .7, .7), ana(.4, .7, .6), pec(.5), pel(.7), tl(3, .5, .5, .1), eye(.3)),
    "sulfur-eel": g2("sulfur-eel", "eel", EB, body(h=.18, w=1.0, nose=.3, curve=.05), dor(.12, .95, .6, .85), ana(.35, .95, .5, .85), pec(1.0), eye(.3)),
    "gall-lumpfish": g2("gall-lumpfish", "globe", GB, body(h=.5, w=.95, pk=.5, np=1.8, sag=.4, pinch=.4), dor(.6, .72, .5), ana(.62, .74, .4), pec(.5), tl(1, .7, .7, .1), {"parts.spikes.h": V(.2), "parts.spikes.step": V(2)}, eye(.26)),
    "lantern-bleak": g2("lantern-bleak", "round", RB, body(h=.25, w=.4, pk=.4, np=1.5), dor(.42, .52, .8, .5), ana(.5, .8, 1.1, .5), pec(.9), pel(.7), tl(0, 1.0, .9, .6), eye(.3), lure(.8, .8, .06)),
    "wisp-fish": g2("wisp-fish", "disc", DB, body(h=.5, w=.2), dor(.3, .6, 1.5, .5), ana(.4, .66, 1.2, .5), pec(.5), pel(1.4), tl(2, .6, .6, .5), eye(.3), finish="ghost"),
    "cave-eel": g2("cave-eel", "eel", EB, body(h=.09, w=.8, nose=.34, curve=-.03), dor(.3, .96, .35, .8), ana(.45, .96, .3, .8), pec(.7), eye(.12, .3)),
    "mimir-carp": g2("mimir-carp", "round", RB, body(h=.3, w=.46, pk=.38, np=2.8, hump=.3), dor(.28, .72, 1.0, .6), pec(1.0), pel(.8), ana(.66, .8, .6), tl(0, 1.0, .9, .5), eye(.2), barbels(4, .8)),
    "norn-trout": g2("norn-trout", "round", RB, body(h=.24, w=.38, pk=.4, np=1.5, sag=.12), dor(.36, .48, .9, .5), adipose(), pec(1.7), pel(.9), ana(.62, .76, .6), tl(2, 1.1, .9, .5, .8), eye(.22)),
    "hoard-carp": g2("hoard-carp", "round", RB, body(h=.38, w=.5, pk=.38, np=2.4, hump=.25), dor(.27, .72, 1.2, .5), pec(1.2), pel(1.0), ana(.66, .8, .7), tl(2, 1.3, 1.1, .5, .6), eye(.22), barbels(2, .5), scutes(3, .2)),
    # ================================================================ the shore, the sound, the open sea, Hlýey
    "sprat": g2("sprat", "round", RB, body(h=.2, w=.36, pk=.4, np=1.5, sag=.25, nb=1.8), dor(.45, .52, .8, .5), pec(.8), pel(.6), ana(.6, .8, .5), tl(0, .9, .8, .7), eye(.3)),
    "sandeel": g2("sandeel", "eel", EB, body(h=.045, w=1.0, nose=.3), dor(.25, .95, .4, .8), ana(.5, .95, .3, .8), eye(.3), jaw(.5, .3, 4)),
    "dab": g2("dab", "flat", FB, body(h=.075, w=8.5, pk=.56, np=2.8, taper=1.8), fin("fringe", .2, .9, .22, .7), tl(1, .3, .3, .1), eye(.25)),
    "sea-scorpion": g2("sea-scorpion", "round", RB, body(h=.24, w=.8, pk=.25, np=2.6, taper=2.6, brow=.3), dor(.2, .8, 1.5, .4), pec(1.8), pel(.8), ana(.65, .8, .5), tl(3, 1.0, .9, .1), eye(.3), jaw(.3, .3, 10), frill(.12, .5, .3)),
    "ballan-wrasse": g2("ballan-wrasse", "round", RB, body(h=.27, w=.5, pk=.4, np=2.0), dor(.22, .76, .8, .7), pec(.9), pel(.8), ana(.66, .78, .6), tl(1, .8, .9, .1), eye(.2), jaw(.5, .5, 5)),
    "grey-mullet": g2("grey-mullet", "round", RB, body(h=.2, w=.6, pk=.5, np=3.0, taper=1.1), dor(.35, .42, .8, .5), dor2(.6, .7, .7, .5), pec(1.0), pel(.8), ana(.62, .76, .6), tl(0, 1.0, .9, .5), eye(.22)),
    "whiting": g2("whiting", "round", RB, body(h=.14, w=.45, pk=.36, np=1.4, taper=2.4), dor(.26, .4, .9, .4), dor2(.46, .58, .8, .4), pec(.9), pel(.6), ana(.5, .8, .6), tl(3, 1.0, .9, .2), eye(.25), barbels(1, .3)),
    "pipefish": g2("pipefish", "round", RB, body(h=.06, w=1.0, pk=.5, np=1.4, rost=.18, taper=1.0), dor(.6, .8, 1.0, .6), tl(1, .5, .4, .1), eye(.14)),
    "rockling": g2("rockling", "round", RB, body(h=.12, w=.8, pk=.15, np=3.0, taper=2.4), dor(.2, .28, .6, .5), dor2(.34, .88, .6, .9), pec(1.0), ana(.5, .88, .5, .9), tl(1, .4, .4, .1), eye(.26), barbels(3, .5)),
    "flying-fish": g2("flying-fish", "round", RB, body(h=.16, w=.6, pk=.4, np=1.8), dor(.65, .75, .7, .5), pec(3.4), pel(2.0), ana(.7, .8, .5), tl(0, 1.3, 1.0, .7), eye(.26)),
    "haddock": g2("haddock", "round", RB, body(h=.21, w=.5, pk=.36), dor(.26, .38, 1.8, .4), dor2(.46, .64, .8, .5), pec(1.1), pel(.7), ana(.54, .8, .6), tl(3, 1.0, .9, .2), eye(.24), barbels(1, .3)),
    "sand-plaice": g2("sand-plaice", "flat", FB, body(h=.08, w=5.4, pk=.46, np=1.8, taper=1.4), fin("fringe", .2, .88, .26, .7), tl(1, .3, .3, .1), eye(.25)),
    "turbot": g2("turbot", "flat", FB, body(h=.08, w=9.0, pk=.5, np=1.6, taper=1.0), fin("fringe", .22, .84, .2, .7), tl(1, .25, .3, .1), eye(.26)),
    "dapple-skate": g2("dapple-skate", "ray", RAYB, body(h=.07, w=8.0, pk=.5, np=1.4, taper=.9), fin("wing", .14, .66, .4, .8), dor(.78, .88, .6, .5), eye(.22)),
    "sea-bass": g2("sea-bass", "round", RB, body(h=.21, w=.45, pk=.38, np=1.4), dor(.32, .46, 1.3, .2), dor2(.52, .66, .7, .5), pec(1.0), pel(.8), ana(.62, .76, .7), tl(0, 1.1, .9, .45), eye(.22), QUIET_JAW),
    "lumpsucker": g2("lumpsucker", "globe", GB, body(h=.48, w=.9, pk=.45, np=2.0, pinch=.2), dor(.35, .65, 1.2, .5), ana(.62, .74, .4), pec(.5), tl(1, .5, .5, .1), {"parts.spikes.h": V(.14), "parts.spikes.step": V(2)}, eye(.22)),
    "conger": g2("conger", "eel", EB, body(h=.14, w=1.0, nose=.4), dor(.1, .96, .6, .85), ana(.3, .96, .5, .85), pec(.9), eye(.2), jaw(.8, .4, 9, 5, .3)),
    "cuckoo-wrasse": g2("cuckoo-wrasse", "round", RB, body(h=.17, w=.45, pk=.4, np=1.6), dor(.2, .8, 1.0, .7), pec(.9), pel(.7), ana(.62, .78, .5), tl(1, 1.0, .9, .1), eye(.22), jaw(.3, .3, 4)),
    "red-gurnard": g2("red-gurnard", "round", RB, body(h=.26, w=.6, pk=.2, np=2.6, taper=2.0, brow=.15), dor(.22, .36, 1.4, .4), dor2(.44, .7, .7, .5), pec(2.4, filament=1.0), pel(.8), ana(.6, .74, .5), tl(3, 1.0, .9, .1), eye(.26), QUIET_JAW),
    "tide-seahorse": g2("tide-seahorse", "seahorse", SB, body(h=.14, w=.9, curl=.8), dor(.42, .54, 1.0, .6), pec(.6), eye(.25)),
    "pufferfish": g2("pufferfish", "globe", GB, body(h=.5, w=1.0, pk=.5, np=2.2, pinch=.25), dor(.66, .76, .4), ana(.66, .76, .4), pec(.3), tl(1, .4, .4, .1), {"parts.spikes.h": V(.1), "parts.spikes.step": V(2)}, eye(.28)),
    "sun-angelfish": g2("sun-angelfish", "disc", DB, body(h=.8, w=.2), dor(.28, .74, 1.4, .6), ana(.38, .72, 1.3, .6), pec(.5), pel(1.2), tl(3, .35, .35, .1), eye(.26)),
    "cuttlefish": g2("cuttlefish", "squid", QB, body(h=.25, w=.95), {"parts.arms.len": V(1.4), "parts.club.len": V(3.0)}, eye(.28)),
    "ribbonfish": g2("ribbonfish", "ribbon", RIB, body(h=.06, taper=1.0), {"parts.crest.h": V(.8)}, jaw(.5, .3, 6)),
    "triggerfish": g2("triggerfish", "round", RB, body(h=.46, w=.35, pk=.42, np=1.8), dor(.28, .34, 2.0, .2), dor2(.44, .72, .9, .6), ana(.46, .74, .8, .6), pec(.6), pel(.8), tl(3, .8, .8, .2), eye(.2)),
    "spurdog": g2("spurdog", "hammerhead", HB, body(h=.15, w=.6, head=.12), dor(.34, .42, 1.6, .3), pec(1.5), tl(0, 1.2, 1.0, .5), eye(.2)),
    "boxfish": g2("boxfish", "round", RB, body(h=.38, w=1.0, pk=.45, np=3.5, nt=3.2, nb=3.2, taper=1.0), dor(.62, .7, .8, .6), ana(.62, .7, .8, .6), pec(.4), tl(1, .6, .6, .1), eye(.24), scutes(3, .1)),
    "halibut": g2("halibut", "flat", FB, body(h=.075, w=3.6, pk=.42, np=1.3, taper=1.5), fin("fringe", .18, .94, .2, .7), tl(2, .45, .4, .1), eye(.24)),
    "monkfish": g2("monkfish", "round", RB, body(h=.2, w=1.6, pk=.2, np=3.5, taper=2.4, pinch=0), dor(.4, .48, .9, .5), pec(1.8), ana(.6, .7, .5), tl(1, .8, .8, .1), eye(.2), jaw(.4, .6, 16, 6, .3), lure(1.2, .9)),
    "ocean-sunfish": g2("ocean-sunfish", "disc", DB, body(h=.9, w=.22), dor(.5, .58, 2.4, .6), ana(.5, .58, 2.0, .6), pec(.4), pel(.2), tl(3, .2, .2, .1), eye(.2)),
    "swordfish": g2("swordfish", "round", RB, body(h=.16, w=.55, pk=.42, np=1.3, rost=.22), dor(.36, .46, 1.1, .6), pec(1.0), pel(.5), ana(.66, .74, .6), tl(2, 1.5, 1.2, .55), eye(.2), finlets(4, .2)),
    "john-dory": g2("john-dory", "disc", DB, body(h=.7, w=.22, brow=.1), dor(.3, .5, 3.0, .1), ana(.5, .74, .8, .5), pec(.5), pel(.8), tl(1, .35, .35, .1), eye(.34), jaw(1.0, .6, 12)),
    "thornback-ray": g2("thornback-ray", "ray", RAYB, body(h=.08, w=8.0, pk=.5, np=2.2, taper=1.0), fin("wing", .14, .7, .5, .8), dor(.76, .88, .8, .5), eye(.22)),
    "sailfish": g2("sailfish", "round", RB, body(h=.13, w=.55, pk=.42, np=1.3, rost=.2), dor(.2, .75, 3.2, .85), pec(1.0), pel(1.4), ana(.66, .74, .6), tl(2, 1.4, 1.1, .55), eye(.2)),
    "coral-lionfish": g2("coral-lionfish", "round", RB, body(h=.3, w=.6, pk=.38, np=2.0), dor(.28, .66, 2.2, .1), pec(2.6, .26, 1.0), pel(1.0), ana(.62, .76, 1.2, .2), tl(1, 1.0, 1.0, .1), eye(.26)),
    "sunray": g2("sunray", "ray", RAYB, body(h=.06, w=11.0, pk=.5, np=2.6, taper=.7), fin("wing", .14, .66, .55, .9), dor(.8, .9, .4, .5), eye(.2)),
    "sea-dragon": g2("sea-dragon", "seahorse", SB, body(h=.1, w=.8, curl=.3, nose=.4), dor(.4, .6, 1.2, .8), pec(.8), eye(.25)),
    "draugr-eel": g2("draugr-eel", "eel", EB, body(h=.12, w=.9, nose=.36, curve=-.04, flick=.04), dor(.12, .96, .5, .5), ana(.4, .96, .4, .5), pec(.6), eye(.24), jaw(.8, .4, 10, 6, .3), finish="ghost"),
    "greenland-shark": g2("greenland-shark", "hammerhead", HB, body(h=.17, w=.75, head=.14), dor(.4, .46, .6, .3), pec(1.2), tl(0, 1.2, 1.0, .3), eye(.14)),
    "opah": g2("opah", "disc", DB, body(h=.85, w=.22), dor(.3, .5, 1.6, .5), ana(.42, .6, 1.2, .5), pec(1.0), pel(.7), tl(2, .6, .6, .5), eye(.26)),
    "grouper": g2("grouper", "round", RB, body(h=.3, w=.7, pk=.4, np=2.4, taper=1.1, pinch=0), dor(.26, .72, .7, .85), pec(1.0), pel(.8), ana(.64, .76, .6), tl(1, 1.1, 1.1, .1), eye(.18), jaw(.5, .5, 8)),
    "barracuda": g2("barracuda", "round", RB, body(h=.1, w=.7, pk=.4, np=1.2), dor(.5, .56, 1.0, .5), dor2(.72, .78, .6, .5), pec(.8), pel(.5), ana(.72, .78, .5), tl(0, 1.2, 1.0, .5), eye(.2), jaw(1.4, .4, 6, 6, .3)),
    "jormungand-thread": g2("jormungand-thread", "ribbon", RIB, body(h=.07, curve=.05, taper=1.0), {"parts.crest.h": V(.6)}, jaw(.8, .4, 14, 7, .3)),
    "kraken-whelp": g2("kraken-whelp", "squid", QB, body(h=.3, w=1.0), {"parts.arms.len": V(3.2), "parts.club.len": V(6.0)}, eye(.3)),
    "hel-halibut": g2("hel-halibut", "flat", FB, body(h=.075, w=5.2, pk=.62, np=2.0, taper=2.4), fin("fringe", .14, .96, .34, .85), tl(1, .5, .5, .1), eye(.26)),
}
