"""The catchable species as v2 genomes: one per catchable slug in Norna's fish table, baked into `out/fish/`.

Each slug takes a body plan and a v2 archetype's gene ranges (`genome.py`), then its own: length, depth and cross
section from v1's size table (`presets.py`, which the game's client look table and the server's kg pin), colours
and pattern from v1's look, and the parts its name asks for (the pike's tusks, the barbel's whiskers, the grayling's
sail). The deep waters' rod-locked giants wear the deep-sea look: the fathom cod is an angler with a lit lure, the
deep wolffish a fanged, big-eyed mawfish, the soulfish a ghost oarfish. The silt flounder is the flat plan (both eyes up,
baked lying on its side by `glb.display_pose`), the hammer-shark the hammerhead plan, the gloom-eye a big-eyed deep fish.

A game species keeps its colour (`jitter` 0): per-catch variety is the client's (`catchShade`) and the rolled genes'.
`CANON` is the seed each slug is baked from. Random extras (`genome.EXTRAS`: a duckbill, a frill) stay off: a slug
lists the parts it has.
"""

from __future__ import annotations

from ..presets import SKINS as V1_SKINS
from ..presets import SPECIES as V1
from .genome import ARMOURED, DISC, EEL, EXTRAS, FLAT, HAMMER, JAW, LURE, RIBBON, ROUND, SPECIES, WHISK, R, S, _pal



def _hex(rgb) -> str:
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(c * 255))) for c in rgb)


def _without(base: dict, *prefixes: str) -> dict:
    return {k: v for k, v in base.items() if not any(k.startswith(p) for p in prefixes)}


def _genes_of(archetype: str) -> dict:
    """An archetype's gene ranges to start a slug from, without the random extras its plan rolls (`genome.EXTRAS`)."""
    extras = tuple(k.rstrip("?") for k in EXTRAS)
    return {k: v for k, v in SPECIES[archetype]["genes"].items() if not k.rstrip("?").startswith(extras)}


#: The BODY's length gene per slug (nose to tail root, metres), set so the whole baked fish, tail fin and jaw included,
#: is v1's length at the median catch (`presets.length_m`, `looks.ts` `lengthM`): the size the hand, the line and the
#: server's kg were tuned at. Parts are fractions of the body radius, so the fish scales whole.
BODY_LEN: dict[str, float] = {
    "pale-fish": 0.1962,
    "reed-perch": 0.176,
    "blind-cavefish": 0.1374,
    "skerry-herring": 0.1704,
    "silver-bream": 0.2552,
    "mottled-eel": 0.6039,
    "grey-cod": 0.395,
    "frost-char": 0.2516,
    "star-fin": 0.1174,
    "shardfin": 0.2397,
    "tusk-pike": 0.5335,
    "loki-salmon": 0.5115,
    "soulfish": 0.4172,
    "mire-loach": 0.1249,
    "rill-trout": 0.2348,
    "moss-carp": 0.4322,
    "rime-grayling": 0.2629,
    "rime-smelt": 0.1053,
    "gloam-barbel": 0.2447,
    "root-lamprey": 0.5469,
    "kelp-pollock": 0.321,
    "wave-mackerel": 0.2704,
    "sea-ling": 0.8904,
    "storm-tuna": 0.7214,
    "ash-gar": 0.6791,
    "moonscale": 0.2675,
    "ember-sturgeon": 0.8243,
    "cinder-wyrm": 1.0544,
    "glass-shiner": 0.0851,
    "jewel-bleak": 0.1557,
    "deep-wolffish": 0.7078,
    "fathom-cod": 0.817,
    "silt-flounder": 0.3127,
    "hammer-shark": 0.9183,
    "gloom-eye": 0.3699,
    "lagoon-snapper": 0.2447,
    "reef-parrotfish": 0.3078,
    "glimmer-eel": 0.5381,
    "brook-minnow": 0.0795,
    "lake-crayfish": 0.1055,
}


def game(slug: str, plan: str, base: dict, over=None, extra=None, pal=None, skins=None, widen=1.2, finish=None) -> dict:
    v = V1[slug]
    over = {k: v for k, v in (over or {}).items() if k != "len_m"}
    extra = {**(extra or {}), "len_m": R(BODY_LEN[slug])}  # exact, never widened or clamped: the size is the slug's
    p = _pal(_hex(v.body), _hex(v.fin), _hex(v.accent), _hex(v.iris))
    p.update(pal or {})
    sk = dict(V1_SKINS[slug])
    kind = sk.pop("kind")
    sp = S(plan, base, over, extra, p, skins or (kind,), sk, widen=widen, extras=False)
    sp["jitter"] = 0.0
    if finish:
        sp["finish"] = finish
    return sp


FORKED, ROUNDED, LUNATE, TRUNCATE = R(0), R(1), R(2), R(3)
ADIPOSE = {"parts.dorsal2?": R(1.0), "parts.dorsal2.s0": R(0.7, 0.74), "parts.dorsal2.s1": R(0.76, 0.8), "parts.dorsal2.h": R(0.35, 0.5), "parts.dorsal2.membrane": R(0.8, 0.9)}
SECOND_DORSAL = {"parts.dorsal2?": R(1.0), "parts.dorsal2.s0": R(0.6, 0.64), "parts.dorsal2.s1": R(0.74, 0.8), "parts.dorsal2.h": R(0.6, 0.9), "parts.dorsal2.membrane": R(0.4, 0.6)}
CHIN_BARBEL = {"parts.barbels.n": R(1, 1), "parts.barbels.len": R(0.4, 0.6), "parts.barbels.tip": R(0.15, 0.2), "parts.barbels.curl": R(0.2, 0.4)}
QUIET_JAW = {**JAW, "parts.jaw.proj": R(0.3, 0.4), "parts.jaw.drop": R(0.3, 0.34), "parts.jaw.gape": R(3.0, 4.0)}

GAME: dict[str, dict] = {
    # ---- the commons
    "pale-fish": game("pale-fish", "round", ROUND, {"body.height": R(0.24, 0.27), "body.width": R(0.44, 0.5), "parts.tail.shape": FORKED, "parts.eye.size": R(0.24, 0.27)}),
    "reed-perch": game("reed-perch", "round", ROUND, {"body.height": R(0.29, 0.32), "body.width": R(0.42, 0.48), "body.hump": R(0.12, 0.2), "parts.dorsal.s0": R(0.26, 0.3), "parts.dorsal.s1": R(0.56, 0.62), "parts.dorsal.h": R(1.1, 1.4),
                                                       "parts.dorsal.membrane": R(0.3, 0.4), "parts.tail.shape": TRUNCATE}, SECOND_DORSAL),
    "blind-cavefish": game("blind-cavefish", "round", ROUND, {"body.height": R(0.23, 0.25), "body.width": R(0.46, 0.52), "parts.eye.size": R(0.1, 0.12), "parts.eye.bulge": R(0.3, 0.4), "parts.tail.shape": ROUNDED},
                           pal={"iris": "#e8c8c4", "pupil": "#c9a6a6", "sclera": "#f2dcd8"}),
    "skerry-herring": game("skerry-herring", "round", ROUND, {"body.height": R(0.19, 0.21), "body.width": R(0.4, 0.46), "body.nose_p": R(1.5, 1.8), "parts.tail.shape": FORKED, "parts.tail.fork": R(0.55, 0.7),
                                                               "parts.dorsal.s0": R(0.4, 0.44), "parts.dorsal.s1": R(0.52, 0.56)}),
    "mire-loach": game("mire-loach", "round", ROUND, {"body.height": R(0.15, 0.17), "body.width": R(0.8, 0.9), "body.peak": R(0.3, 0.34), "parts.eye.size": R(0.16, 0.2), "parts.tail.shape": ROUNDED,
                                                       "parts.dorsal.s0": R(0.44, 0.48), "parts.dorsal.s1": R(0.56, 0.6), "parts.dorsal.h": R(0.6, 0.8)}, {**WHISK, "parts.barbels.n": R(6, 6), "parts.barbels.len": R(0.8, 1.0)}),
    "rime-smelt": game("rime-smelt", "round", ROUND, {"body.height": R(0.15, 0.17), "body.width": R(0.42, 0.46), "body.nose_p": R(1.5, 1.8), "parts.eye.size": R(0.28, 0.3), "parts.tail.shape": FORKED}, ADIPOSE),
    "gloam-barbel": game("gloam-barbel", "round", ROUND, {"body.height": R(0.21, 0.23), "body.width": R(0.62, 0.72), "parts.eye.size": R(0.15, 0.18), "body.nose_p": R(1.6, 2.0), "parts.tail.shape": FORKED},
                         {**WHISK, "parts.barbels.n": R(4, 4), "parts.barbels.len": R(0.7, 1.0)}),
    "kelp-pollock": game("kelp-pollock", "round", ROUND, {"body.height": R(0.23, 0.25), "body.width": R(0.5, 0.56), "parts.dorsal.s0": R(0.28, 0.32), "parts.dorsal.s1": R(0.42, 0.46), "parts.tail.shape": TRUNCATE},
                         {**SECOND_DORSAL, **QUIET_JAW, "parts.jaw.proj": R(0.5, 0.6)}),
    # ---- the uncommons
    "silver-bream": game("silver-bream", "disc", DISC, {"body.height": R(0.44, 0.48), "body.width": R(0.22, 0.26), "parts.tail.len": R(0.6, 0.8), "parts.tail.lobe": R(0.55, 0.75), "parts.tail.fork": R(0.4, 0.55), "parts.tail.shape": FORKED,
                                                         "parts.dorsal.h": R(0.7, 0.9), "parts.anal.s0": R(0.5, 0.54), "parts.anal.s1": R(0.78, 0.84), "parts.anal.h": R(0.5, 0.7), "parts.pelvic.len": R(0.5, 0.7)}),
    "shardfin": game("shardfin", "round", ROUND, {"body.height": R(0.28, 0.3), "body.width": R(0.36, 0.42), "parts.dorsal.s0": R(0.26, 0.3), "parts.dorsal.s1": R(0.6, 0.66), "parts.dorsal.h": R(1.8, 2.2), "parts.dorsal.membrane": R(0.12, 0.2),
                                                   "parts.anal.h": R(0.9, 1.2), "parts.anal.membrane": R(0.15, 0.2), "parts.pectoral.len": R(1.4, 1.7), "parts.tail.shape": FORKED, "parts.tail.fork": R(0.5, 0.6)}),
    "mottled-eel": game("mottled-eel", "eel", EEL, {"body.height": R(0.12, 0.125), "body.width": R(0.9, 1.0), "body.peak": R(0.2, 0.22), "body.nose": R(0.34, 0.38), "parts.eye.size": R(0.24, 0.28), "body.curve": R(0.025, 0.03), "body.flick": R(0.03, 0.04),
                                                     "parts.dorsal.s0": R(0.3, 0.34), "parts.dorsal.h": R(1.1, 1.2), "parts.anal.s0": R(0.42, 0.46), "parts.anal.h": R(0.95, 1.05), "parts.pectoral.len": R(0.9, 1.0)}, QUIET_JAW, skins=("mottle",)),
    "grey-cod": game("grey-cod", "round", ROUND, {"body.height": R(0.25, 0.27), "body.width": R(0.54, 0.6), "body.sag": R(0.08, 0.12), "parts.dorsal.s0": R(0.26, 0.3), "parts.dorsal.s1": R(0.42, 0.46), "parts.tail.shape": TRUNCATE},
                     {**SECOND_DORSAL, **CHIN_BARBEL}),
    "rill-trout": game("rill-trout", "round", ROUND, {"body.height": R(0.23, 0.25), "body.width": R(0.44, 0.5), "parts.tail.shape": TRUNCATE, "parts.dorsal.s0": R(0.36, 0.4), "parts.dorsal.s1": R(0.5, 0.54)}, ADIPOSE),
    "rime-grayling": game("rime-grayling", "round", ROUND, {"body.height": R(0.24, 0.26), "body.width": R(0.36, 0.4), "parts.dorsal.s0": R(0.26, 0.28), "parts.dorsal.s1": R(0.56, 0.6), "parts.dorsal.h": R(1.9, 2.3),
                                                             "parts.dorsal.membrane": R(0.75, 0.85), "parts.tail.shape": FORKED}, ADIPOSE),
    "wave-mackerel": game("wave-mackerel", "round", ROUND, {**{k: v for k, v in _genes_of("tuna").items() if k.startswith(("parts.tail", "parts.dorsal", "body.pinch", "parts.pectoral"))},
                                                             "body.height": R(0.18, 0.2), "body.width": R(0.5, 0.56), "body.nose_p": R(1.3, 1.6), "parts.dorsal.h": R(0.6, 0.8)},
                          {**SECOND_DORSAL, "parts.finlets?": R(1.0), "parts.finlets.n": R(4, 4), "parts.finlets.h": R(0.2, 0.26)}, skins=("bars",)),
    "ash-gar": game("ash-gar", "round", ROUND, {"body.height": R(0.1, 0.11), "body.width": R(0.85, 0.95), "body.peak": R(0.5, 0.56), "body.nose_p": R(1.1, 1.3), "body.nose": R(0.08, 0.1), "parts.eye.size": R(0.22, 0.26),
                                                 "parts.dorsal.s0": R(0.78, 0.8), "parts.dorsal.s1": R(0.86, 0.88), "parts.anal.s0": R(0.76, 0.78), "parts.anal.s1": R(0.86, 0.88), "parts.tail.shape": ROUNDED},
                    {**JAW, "parts.jaw.teeth": R(8, 8), "parts.jaw.tooth": R(0.3, 0.36), "parts.jaw.proj": R(1.6, 1.8), "parts.jaw.gape": R(4.0, 6.0)}),
    # ---- the rares
    "frost-char": game("frost-char", "round", ROUND, {"body.height": R(0.23, 0.25), "body.width": R(0.44, 0.5), "parts.tail.shape": TRUNCATE, "parts.dorsal.s0": R(0.36, 0.4), "parts.dorsal.s1": R(0.5, 0.54)}, ADIPOSE,
                       pal={"belly": "#f2b0a0"}),
    "star-fin": game("star-fin", "round", ROUND, {"body.height": R(0.28, 0.3), "body.width": R(0.4, 0.44), "parts.eye.size": R(0.28, 0.3), "parts.dorsal.h": R(1.4, 1.7), "parts.pectoral.len": R(1.6, 1.9), "parts.pectoral.filament": R(0.8, 1.0),
                                                   "parts.tail.shape": FORKED, "parts.tail.streamer": R(0.6, 0.8), "parts.pelvic.len": R(1.0, 1.2)}),
    "tusk-pike": game("tusk-pike", "round", ROUND, {**_genes_of("pike"), "body.height": R(0.14, 0.15), "body.width": R(0.6, 0.66)},
                      {**JAW, "parts.jaw.teeth": R(7, 7), "parts.jaw.tooth": R(0.4, 0.46), "parts.jaw.proj": R(1.3, 1.4)}),
    "moss-carp": game("moss-carp", "round", ROUND, {**_genes_of("carp"), "body.height": R(0.3, 0.32), "body.width": R(0.42, 0.46)},
                      {**WHISK, "parts.barbels.n": R(2, 2), "parts.barbels.len": R(0.4, 0.6)}),
    "root-lamprey": game("root-lamprey", "eel", _without(EEL, "parts.pectoral"), {"body.height": R(0.09, 0.095), "body.width": R(1.0, 1.05), "body.nose": R(0.36, 0.4), "body.nose_p": R(2.6, 3.0), "parts.eye.size": R(0.18, 0.2),
                                                                                  "body.curve": R(-0.03, -0.025), "parts.dorsal.s0": R(0.5, 0.54), "parts.dorsal.h": R(0.45, 0.55)},
                         skins=("mottle",)),
    "moonscale": game("moonscale", "disc", DISC, {"body.height": R(0.5, 0.54), "body.width": R(0.24, 0.28), "parts.dorsal.s0": R(0.3, 0.34), "parts.dorsal.s1": R(0.62, 0.66), "parts.dorsal.h": R(1.2, 1.5), "parts.pectoral.len": R(0.8, 1.0),
                                                   "parts.tail.len": R(0.6, 0.8), "parts.tail.lobe": R(0.6, 0.8), "parts.tail.fork": R(0.4, 0.5), "parts.tail.shape": LUNATE}),
    "sea-ling": game("sea-ling", "round", ROUND, {"body.height": R(0.13, 0.14), "body.width": R(0.8, 0.9), "body.peak": R(0.3, 0.34), "parts.dorsal.s0": R(0.3, 0.32), "parts.dorsal.s1": R(0.88, 0.9), "parts.dorsal.h": R(0.5, 0.6),
                                                   "parts.dorsal.membrane": R(0.8, 0.9), "parts.anal.s0": R(0.5, 0.52), "parts.anal.s1": R(0.88, 0.9), "parts.anal.h": R(0.45, 0.55), "parts.tail.shape": ROUNDED, "parts.tail.len": R(0.7, 0.8)},
                     CHIN_BARBEL),
    "storm-tuna": game("storm-tuna", "round", ROUND, {**_genes_of("tuna"), "body.height": R(0.24, 0.26), "body.width": R(0.62, 0.68)},
                       {"parts.finlets?": R(1.0), "parts.finlets.n": R(5, 5), "parts.finlets.h": R(0.22, 0.28), **JAW, "parts.jaw.proj": R(0.3, 0.4), "parts.jaw.drop": R(0.28, 0.32), "parts.jaw.gape": R(3.0, 4.0)}),
    # ---- the legends
    "loki-salmon": game("loki-salmon", "round", ROUND, {"body.height": R(0.23, 0.25), "body.width": R(0.46, 0.5), "body.hump": R(0.12, 0.18), "parts.tail.shape": TRUNCATE, "parts.dorsal.s0": R(0.36, 0.4), "parts.dorsal.s1": R(0.5, 0.54)},
                        {**ADIPOSE, **JAW, "parts.jaw.proj": R(0.55, 0.6), "parts.jaw.drop": R(0.4, 0.44), "parts.jaw.teeth": R(4, 4), "parts.jaw.tooth": R(0.22, 0.26), "parts.jaw.gape": R(4.0, 5.0)},
                        pal={"accent": "#d84a30", "fin": "#7a3020"}),
    "soulfish": game("soulfish", "ribbon", RIBBON, {"body.height": R(0.1, 0.11), "parts.crest.h": R(1.4, 1.6), "body.curve": R(0.015, 0.02)},
                     {**JAW, "parts.jaw.teeth": R(0, 0), "parts.jaw.proj": R(0.5, 0.6), "parts.jaw.drop": R(0.3, 0.34), "parts.jaw.gape": R(5.0, 6.0)}, finish="ghost"),
    # ---- rod-locked: the dragon rod's ember fish, the glass rod's jewels, the long rod's deep-sea giants
    "ember-sturgeon": game("ember-sturgeon", "armoured", ARMOURED, {"body.height": R(0.16, 0.17), "body.width": R(0.8, 0.86), "body.snout_up": R(0.2, 0.25), "body.rostrum": R(0.08, 0.09), "parts.scutes.rows": R(3, 3), "parts.scutes.h": R(0.3, 0.34)},
                           {**WHISK, "parts.barbels.n": R(4, 4), "parts.barbels.len": R(0.6, 0.7), "parts.barbels.curl": R(0.2, 0.3)},  # no jaw: its rim takes the whiskers' cells, and a sturgeon reads by its barbels
                           pal={"plate": "#f08c26", "spike": "#f08c26"}),
    "cinder-wyrm": game("cinder-wyrm", "eel", EEL, {**_genes_of("moray"), "body.height": R(0.1, 0.11), "parts.dorsal.h": R(0.9, 1.1), "body.curve": R(0.03, 0.035)},
                        {**JAW, "parts.jaw.teeth": R(7, 7), "parts.jaw.tooth": R(0.32, 0.38), "parts.jaw.proj": R(0.8, 0.9), "parts.jaw.gape": R(14.0, 16.0)}),
    "glass-shiner": game("glass-shiner", "round", ROUND, {"body.height": R(0.19, 0.21), "body.width": R(0.36, 0.4), "parts.eye.size": R(0.3, 0.32), "parts.tail.shape": FORKED, "parts.tail.fork": R(0.5, 0.6)}, finish="ghost"),
    "jewel-bleak": game("jewel-bleak", "round", ROUND, {"body.height": R(0.18, 0.2), "body.width": R(0.36, 0.4), "parts.eye.size": R(0.27, 0.3), "parts.dorsal.h": R(1.3, 1.6), "parts.anal.h": R(1.0, 1.3), "parts.pectoral.len": R(1.3, 1.6),
                                                         "parts.tail.shape": FORKED, "parts.tail.streamer": R(0.4, 0.5)}),
    "deep-wolffish": game("deep-wolffish", "round", ROUND, {**_without(_genes_of("mawfish"), "parts.tent"), "body.height": R(0.19, 0.21), "body.width": R(0.75, 0.8), "parts.dorsal.s0": R(0.24, 0.26), "parts.dorsal.s1": R(0.88, 0.9),
                                                            "parts.dorsal.h": R(0.5, 0.6), "parts.dorsal.membrane": R(0.8, 0.9)},
                          {**JAW, "parts.jaw.teeth": R(7, 7), "parts.jaw.tooth": R(0.4, 0.45), "parts.jaw.proj": R(1.0, 1.1), "parts.jaw.gape": R(16.0, 18.0)}, skins=("bars",)),
    "fathom-cod": game("fathom-cod", "round", ROUND, {**_genes_of("angler"), "body.height": R(0.29, 0.31), "body.width": R(0.85, 0.9)},
                       {**JAW, "parts.jaw.teeth": R(7, 7), "parts.jaw.tooth": R(0.3, 0.36), "parts.jaw.proj": R(1.2, 1.3), "parts.jaw.gape": R(14.0, 16.0), **LURE, "parts.lure.stalk": R(1.6, 1.8)}),
    # ---- the plans no slug had: the shore's flatfish (both eyes on its upper side, baked lying down by the plan's pose),
    # the long rod's hammerhead, the deep's big-eye
    "silt-flounder": game("silt-flounder", "flat", FLAT, {"body.height": R(0.07, 0.075), "body.width": R(6.2, 6.6), "body.peak": R(0.44, 0.48), "parts.eye.size": R(0.24, 0.26),
                                                          "parts.fringe.h": R(0.22, 0.26), "parts.tail.shape": ROUNDED}),
    "hammer-shark": game("hammer-shark", "hammerhead", HAMMER, {"body.height": R(0.18, 0.19), "body.width": R(0.72, 0.78), "body.head": R(0.32, 0.34), "parts.dorsal.h": R(1.6, 1.8)}),
    "gloom-eye": game("gloom-eye", "round", ROUND, {"body.height": R(0.27, 0.29), "body.width": R(0.6, 0.66), "body.nose_p": R(2.4, 2.8), "body.peak": R(0.34, 0.38), "parts.eye.size": R(0.44, 0.48),
                                                     "parts.eye.bulge": R(1.0, 1.1), "parts.dorsal.h": R(0.6, 0.8), "parts.tail.shape": FORKED},
                      {**QUIET_JAW, "parts.jaw.teeth": R(5, 5), "parts.jaw.tooth": R(0.24, 0.28), "parts.jaw.proj": R(0.8, 0.9), "parts.jaw.gape": R(8.0, 10.0)}),
    # ---- Hlýey's lagoon (round 2): a snapper with a long dorsal, a blunt reef grazer, and an eel that lights the night shallows
    "lagoon-snapper": game("lagoon-snapper", "round", ROUND, {"body.height": R(0.25, 0.27), "body.width": R(0.46, 0.5), "parts.dorsal.s0": R(0.3, 0.34), "parts.dorsal.s1": R(0.62, 0.66), "parts.dorsal.h": R(1.0, 1.2),
                                                                "parts.tail.shape": FORKED, "parts.tail.fork": R(0.35, 0.45)}),
    "reef-parrotfish": game("reef-parrotfish", "round", ROUND, {"body.height": R(0.34, 0.36), "body.width": R(0.54, 0.6), "body.nose_p": R(0.9, 1.1), "parts.eye.size": R(0.2, 0.22), "parts.dorsal.s0": R(0.2, 0.24), "parts.dorsal.s1": R(0.74, 0.8),
                                                                  "parts.dorsal.h": R(0.8, 1.0), "parts.dorsal.membrane": R(0.5, 0.6), "parts.tail.shape": ROUNDED}),
    "glimmer-eel": game("glimmer-eel", "eel", EEL, {"body.height": R(0.1, 0.105), "body.width": R(0.9, 1.0), "body.peak": R(0.2, 0.22), "body.nose": R(0.32, 0.36), "parts.eye.size": R(0.26, 0.3), "body.curve": R(0.025, 0.03), "body.flick": R(0.03, 0.04),
                                                      "parts.dorsal.s0": R(0.3, 0.34), "parts.dorsal.h": R(0.9, 1.0), "parts.anal.s0": R(0.42, 0.46), "parts.anal.h": R(0.8, 0.9), "parts.pectoral.len": R(0.9, 1.0)}, QUIET_JAW, skins=("stars",)),
    "brook-minnow": game("brook-minnow", "round", ROUND, {"body.height": R(0.16, 0.18), "body.width": R(0.4, 0.46), "parts.eye.size": R(0.28, 0.3), "parts.tail.shape": FORKED}),
    # A crayfish is no fish: the armoured plan's plates and barbels stand in for its shell and feelers.
    "lake-crayfish": game("lake-crayfish", "armoured", ARMOURED, {"body.height": R(0.2, 0.22), "body.width": R(0.9, 1.0), "body.snout_up": R(0.1, 0.15), "body.rostrum": R(0.05, 0.06), "parts.scutes.rows": R(3, 3), "parts.scutes.h": R(0.3, 0.34)},
                          {**WHISK, "parts.barbels.n": R(4, 4), "parts.barbels.len": R(0.9, 1.1), "parts.barbels.curl": R(0.3, 0.4)}),
}

from .game2 import GAME2  # noqa: E402  (wave 2: seventy more slugs, built from `game` above)

GAME.update(GAME2)

#: the seed each slug's shipped GLB is baked from
CANON: dict[str, int] = {slug: 1 for slug in GAME}
SLUGS = tuple(V1)  # the server's order (`presets.SLUGS` mirrors `FISH_TABLE`)
assert set(GAME) == set(SLUGS), sorted(set(SLUGS) ^ set(GAME))
