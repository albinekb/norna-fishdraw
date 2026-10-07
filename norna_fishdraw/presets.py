"""Per-species presets over the fishdraw generator, and `fish_for(species, seed)`.

Species, kilograms and lengths mirror the game's own tables:
  * slugs and `kg=(min, max, median)`: Norna's server-side fish table
  * `length_m` (at the median kg), `depth`, `width`, colours: Norna's client look table
    FISH_LOOKS (test_fishdraw.py reads both files and fails when these drift).

A preset is a dict of fishdraw parameter overrides applied AFTER generate_params
(so the stream is still the JS one) plus a `Look` (real length, flatness,
palette). Colours are the looks.ts body / fin / accent; back and belly are
derived from the body colour (darker, lighter), so a species reads the same on
the reveal card and in the hand. Not snapped to LOOM32: its 32 entries have no
violet, and the pale species would collapse onto one entry.

Variation per catch (`fish_for(species, seed)`): weight drawn triangularly in
the species' kg range, length scales with the cube root of weight, the
silhouette noise of fishdraw differs per seed, and body / fin lengths jitter by
a few percent. Nothing is random but the seed: stream = xorshift via
`str_to_seed("<species>:<seed>")`, jitter stream = `str_to_seed("jitter:<species>:<seed>")`.
"""

from __future__ import annotations

from dataclasses import dataclass

from .fishdraw_port import Drawing, Rng, draw, generate_params, str_to_seed
from .lift3d import Look, Mesh, lift
from .skin import Skin

#: drawing-space body length (head to tail root) the depth ratios are measured against
_BODY_L = 380.0


def _bh(depth: float) -> float:
    """body_height (the half height param) for a depth fraction of body length."""
    return depth * _BODY_L / 1.6


def _hex(rgb) -> str:
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(c * 255))) for c in rgb)


def _mix(a, b, t):
    return tuple(a[i] * (1 - t) + b[i] * t for i in range(3))


def _palette(body, fin, accent, iris=(1.0, 0.8, 0.35)):
    return {
        "back": _hex(_mix(body, (0.08, 0.1, 0.16), 0.5)),
        "flank": _hex(body),
        "belly": _hex(_mix(body, (1, 1, 0.94), 0.55)),
        "fin": _hex(fin),
        "accent": _hex(accent),
        "iris": _hex(iris),
        "pupil": "#1a1a2e",
    }


@dataclass(frozen=True)
class Species:
    slug: str
    kg: tuple  # (min, max, median)
    length_m: float
    depth: float
    width: float
    body: tuple
    fin: tuple
    accent: tuple
    features: tuple
    params: dict
    iris: tuple = (1.0, 0.8, 0.35)

    @property
    def look(self) -> Look:
        skin = Skin(aspect=self.depth, seed=str_to_seed(self.slug + ":skin"), **SKINS[self.slug])
        return Look(self.length_m, self.width / self.depth, _palette(self.body, self.fin, self.accent, self.iris), self.features, skin)


def _p(depth, **kw):
    kw["body_height"] = _bh(depth)
    return kw


SPECIES: dict[str, Species] = {
    s.slug: s
    for s in (
        Species("pale-fish", (0.2, 0.9, 0.4), 0.24, 0.27, 0.12, (0.86, 0.85, 0.8), (0.64, 0.64, 0.6), (0.95, 0.95, 0.9), (),
                _p(0.27, body_curve_type=1, body_curve_amount=0.9, body_length=330, dorsal_type=0, dorsal_texture_type=1, dorsal_length=70,
                   dorsal_start=12, dorsal_end=20, wing_length=80, wing_type=0, wing_texture_type=0, pelvic_length=55, pelvic_type=0, pelvic_texture_type=0,
                   anal_start=20, anal_end=28, anal_length=40, anal_type=0, anal_texture_type=0, tail_type=2, tail_length=85, pattern_type=0, finlet_type=0, eye_size=12)),
        Species("reed-perch", (0.15, 0.7, 0.4), 0.22, 0.36, 0.14, (0.66, 0.7, 0.34), (0.78, 0.36, 0.2), (0.22, 0.26, 0.12), ("stripes",),
                _p(0.36, body_curve_type=1, body_curve_amount=0.9, body_length=330, dorsal_type=1, dorsal_texture_type=1, dorsal_length=85,
                   dorsal_start=11, dorsal_end=24, wing_length=70, wing_type=0, wing_texture_type=0, pelvic_type=1, pelvic_texture_type=0, pelvic_length=60,
                   anal_start=21, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_type=3, tail_length=70, pattern_type=3, pattern_scale=0.55, finlet_type=0, eye_size=13)),
        Species("blind-cavefish", (0.1, 0.5, 0.3), 0.16, 0.25, 0.11, (0.93, 0.8, 0.78), (0.86, 0.7, 0.7), (0.98, 0.88, 0.86), ("blind",),
                _p(0.25, body_curve_type=0, body_curve_amount=0.9, body_length=330, dorsal_type=0, dorsal_texture_type=0, dorsal_length=45,
                   dorsal_start=14, dorsal_end=21, wing_length=60, wing_type=0, wing_texture_type=0, pelvic_length=40, pelvic_type=0, pelvic_texture_type=0,
                   anal_start=20, anal_end=27, anal_length=35, anal_type=0, anal_texture_type=0, tail_type=1, tail_length=60, pattern_type=0, finlet_type=0)),
        Species("skerry-herring", (0.15, 0.4, 0.25), 0.20, 0.21, 0.09, (0.72, 0.78, 0.86), (0.38, 0.48, 0.6), (0.92, 0.95, 1.0), (),
                _p(0.21, body_curve_type=0, body_curve_amount=0.92, body_length=340, head_length=32, dorsal_type=0, dorsal_texture_type=1, dorsal_length=45,
                   dorsal_start=13, dorsal_end=19, wing_length=60, wing_type=0, wing_texture_type=0, pelvic_length=35, pelvic_type=0, pelvic_texture_type=0,
                   anal_start=21, anal_end=29, anal_length=35, anal_type=0, anal_texture_type=0, tail_type=5, tail_length=95, pattern_type=0, finlet_type=0, eye_size=12)),
        Species("silver-bream", (0.5, 2.5, 1.1), 0.30, 0.46, 0.10, (0.85, 0.87, 0.9), (0.52, 0.54, 0.6), (1.0, 1.0, 1.0), (),
                _p(0.46, body_curve_type=0, body_curve_amount=0.97, body_length=300, dorsal_type=0, dorsal_texture_type=1, dorsal_length=70,
                   dorsal_start=13, dorsal_end=22, wing_length=80, wing_type=0, wing_texture_type=0, pelvic_length=60, pelvic_type=0, pelvic_texture_type=0,
                   anal_start=18, anal_end=29, anal_length=60, anal_type=0, anal_texture_type=1, tail_type=2, tail_length=80, pattern_type=0, finlet_type=0, eye_size=12)),
        Species("mottled-eel", (0.6, 3.2, 1.8), 0.62, 0.07, 0.06, (0.44, 0.42, 0.3), (0.3, 0.28, 0.2), (0.62, 0.58, 0.36), ("mottle",),
                _p(0.07, body_curve_type=0, body_curve_amount=0.97, body_length=420, head_length=22, dorsal_type=0, dorsal_texture_type=0, dorsal_length=18,
                   dorsal_start=7, dorsal_end=28, wing_length=25, wing_type=0, wing_texture_type=0, pelvic_length=8, pelvic_type=0, pelvic_texture_type=0,
                   anal_start=14, anal_end=30, anal_length=16, anal_type=0, anal_texture_type=0, tail_type=1, tail_length=22, pattern_type=1, pattern_scale=0.6, finlet_type=0, eye_size=8, nose_height=0)),
        Species("grey-cod", (1.5, 8.0, 3.5), 0.48, 0.26, 0.14, (0.56, 0.56, 0.5), (0.4, 0.4, 0.36), (0.78, 0.76, 0.68), ("barbel", "mottle"),
                _p(0.26, body_curve_type=1, body_curve_amount=0.9, body_length=340, head_length=35, mouth_size=11, jaw_size=1.25, dorsal_type=0, dorsal_texture_type=1, dorsal_length=55,
                   dorsal_start=9, dorsal_end=26, wing_length=75, wing_type=0, wing_texture_type=0, pelvic_length=55, pelvic_type=0, pelvic_texture_type=0,
                   anal_start=17, anal_end=29, anal_length=50, anal_type=0, anal_texture_type=1, tail_type=3, tail_length=75, pattern_type=1, pattern_scale=0.8, finlet_type=0, eye_size=13)),
        Species("frost-char", (0.3, 1.6, 0.9), 0.30, 0.24, 0.11, (0.62, 0.74, 0.86), (0.86, 0.5, 0.42), (0.95, 0.98, 1.0), ("mottle",),
                _p(0.24, body_curve_type=0, body_curve_amount=0.93, body_length=340, dorsal_type=0, dorsal_texture_type=1, dorsal_length=55,
                   dorsal_start=12, dorsal_end=19, wing_length=70, wing_type=0, wing_texture_type=0, pelvic_length=55, pelvic_type=0, pelvic_texture_type=0,
                   anal_start=21, anal_end=28, anal_length=50, anal_type=0, anal_texture_type=0, tail_type=2, tail_length=80, pattern_type=1, pattern_scale=0.6, finlet_type=2, eye_size=12)),
        Species("star-fin", (0.1, 0.4, 0.25), 0.15, 0.30, 0.10, (0.2, 0.22, 0.36), (0.27, 0.29, 0.44), (0.86, 0.8, 0.62), ("stars",),
                _p(0.30, body_curve_type=1, body_curve_amount=0.9, body_length=320, dorsal_type=1, dorsal_texture_type=0, dorsal_length=80,
                   dorsal_start=12, dorsal_end=22, wing_length=80, wing_type=1, wing_texture_type=0, pelvic_length=55, pelvic_type=1, pelvic_texture_type=0,
                   anal_start=21, anal_end=28, anal_length=50, anal_type=1, anal_texture_type=0, tail_type=2, tail_length=95, pattern_type=4, pattern_scale=1, finlet_type=0, eye_size=14),
                (0.95, 0.9, 0.7)),
        Species("shardfin", (0.3, 1.4, 0.7), 0.30, 0.30, 0.10, (0.42, 0.34, 0.66), (0.56, 0.5, 0.84), (0.86, 0.8, 1.0), ("stars",),
                _p(0.30, body_curve_type=0, body_curve_amount=0.92, body_length=330, dorsal_type=1, dorsal_texture_type=1, dorsal_length=100,
                   dorsal_start=11, dorsal_end=21, wing_length=75, wing_type=0, wing_texture_type=0, pelvic_length=60, pelvic_type=1, pelvic_texture_type=1,
                   anal_start=20, anal_end=28, anal_length=55, anal_type=0, anal_texture_type=1, tail_type=5, tail_length=85, pattern_type=4, pattern_scale=1, finlet_type=0, eye_size=12),
                (0.9, 0.85, 1.0)),
        Species("tusk-pike", (1.5, 9.0, 4.0), 0.62, 0.15, 0.09, (0.46, 0.52, 0.3), (0.34, 0.36, 0.2), (0.92, 0.88, 0.7), ("tusks", "mottle"),
                _p(0.15, body_curve_type=0, body_curve_amount=0.92, body_length=430, head_length=35, mouth_size=11, jaw_size=1.2, has_teeth=1, neck_type=1,
                   dorsal_type=0, dorsal_texture_type=0, dorsal_length=45, dorsal_start=21, dorsal_end=28, wing_length=45, wing_type=0, wing_texture_type=0,
                   pelvic_length=35, pelvic_type=0, pelvic_texture_type=0, pelvic_start=15, pelvic_end=19, anal_start=22, anal_end=29, anal_length=45, anal_type=0, anal_texture_type=0,
                   tail_type=2, tail_length=70, pattern_type=1, pattern_scale=0.8, finlet_type=0, eye_size=11)),
        Species("loki-salmon", (3.0, 11.0, 5.0), 0.64, 0.24, 0.12, (0.8, 0.76, 0.74), (0.46, 0.17, 0.12), (0.86, 0.32, 0.22), ("kype", "mottle"),
                _p(0.24, body_curve_type=0, body_curve_amount=0.92, body_length=380, head_length=33, dorsal_type=0, dorsal_texture_type=1, dorsal_length=55,
                   dorsal_start=12, dorsal_end=18, wing_length=70, wing_type=0, wing_texture_type=0, pelvic_length=50, pelvic_type=0, pelvic_texture_type=0,
                   anal_start=21, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_type=2, tail_length=80, pattern_type=1, pattern_scale=0.7, finlet_type=2, eye_size=12)),
        Species("soulfish", (2.0, 6.0, 3.5), 0.46, 0.26, 0.11, (0.66, 0.88, 1.0), (0.5, 0.74, 0.92), (0.8, 0.96, 1.0), ("ghost",),
                _p(0.26, body_curve_type=1, body_curve_amount=0.9, body_length=340, dorsal_type=1, dorsal_texture_type=0, dorsal_length=90,
                   dorsal_start=11, dorsal_end=24, wing_length=150, wing_type=1, wing_texture_type=0, pelvic_length=80, pelvic_type=1, pelvic_texture_type=0,
                   anal_start=19, anal_end=29, anal_length=70, anal_type=1, anal_texture_type=0, tail_type=1, tail_length=100, pattern_type=0, finlet_type=0, eye_size=13),
                (0.9, 1.0, 1.0)),
        # ---- water-tier species (fish_loot.py WATER_BODIES), shallow and common to remote and rare
        Species("mire-loach", (0.05, 0.3, 0.15), 0.14, 0.17, 0.09, (0.5, 0.42, 0.28), (0.4, 0.34, 0.22), (0.72, 0.62, 0.4), ("barbel", "mottle"),
                _p(0.17, body_curve_type=0, body_curve_amount=0.95, body_length=390, head_length=26, dorsal_type=0, dorsal_texture_type=0, dorsal_length=35,
                   dorsal_start=12, dorsal_end=22, wing_length=40, wing_type=0, wing_texture_type=0, pelvic_length=25, pelvic_type=0, pelvic_texture_type=0,
                   anal_start=22, anal_end=28, anal_length=25, anal_type=0, anal_texture_type=0, tail_type=3, tail_length=55, pattern_type=1, pattern_scale=0.6, finlet_type=0, eye_size=9)),
        Species("rill-trout", (0.2, 1.2, 0.5), 0.28, 0.24, 0.10, (0.58, 0.52, 0.3), (0.72, 0.46, 0.26), (0.82, 0.2, 0.18), ("mottle",),
                _p(0.24, body_curve_type=0, body_curve_amount=0.93, body_length=345, dorsal_type=0, dorsal_texture_type=1, dorsal_length=55,
                   dorsal_start=12, dorsal_end=19, wing_length=65, wing_type=0, wing_texture_type=0, pelvic_length=50, pelvic_type=0, pelvic_texture_type=0,
                   anal_start=21, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_type=2, tail_length=78, pattern_type=2, pattern_scale=0.6, finlet_type=2, eye_size=12)),
        Species("moss-carp", (2.0, 12.0, 5.0), 0.55, 0.42, 0.17, (0.42, 0.5, 0.22), (0.5, 0.4, 0.18), (0.86, 0.76, 0.4), ("barbel",),
                _p(0.42, body_curve_type=1, body_curve_amount=0.92, body_length=330, head_length=30, mouth_size=8, dorsal_type=0, dorsal_texture_type=1, dorsal_length=95,
                   dorsal_start=9, dorsal_end=24, wing_length=75, wing_type=0, wing_texture_type=0, pelvic_length=60, pelvic_type=0, pelvic_texture_type=0,
                   anal_start=19, anal_end=28, anal_length=50, anal_type=0, anal_texture_type=1, tail_type=2, tail_length=85, pattern_type=0, finlet_type=0, eye_size=11, has_moustache=1)),
        Species("rime-grayling", (0.3, 1.8, 0.8), 0.32, 0.26, 0.09, (0.62, 0.68, 0.78), (0.5, 0.36, 0.62), (0.9, 0.95, 1.0), ("mottle",),
                _p(0.26, body_curve_type=0, body_curve_amount=0.93, body_length=340, dorsal_type=1, dorsal_texture_type=1, dorsal_length=150,
                   dorsal_start=10, dorsal_end=20, wing_length=70, wing_type=0, wing_texture_type=0, pelvic_length=60, pelvic_type=1, pelvic_texture_type=0,
                   anal_start=21, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_type=2, tail_length=80, pattern_type=2, pattern_scale=0.55, finlet_type=0, eye_size=12)),
        Species("rime-smelt", (0.03, 0.2, 0.08), 0.12, 0.16, 0.07, (0.8, 0.9, 0.92), (0.7, 0.82, 0.86), (0.97, 1.0, 1.0), (),
                _p(0.16, body_curve_type=0, body_curve_amount=0.95, body_length=350, dorsal_type=0, dorsal_texture_type=0, dorsal_length=30,
                   dorsal_start=14, dorsal_end=20, wing_length=45, wing_type=0, wing_texture_type=0, pelvic_length=30, pelvic_type=0, pelvic_texture_type=0,
                   anal_start=21, anal_end=28, anal_length=30, anal_type=0, anal_texture_type=0, tail_type=2, tail_length=70, pattern_type=0, finlet_type=0, eye_size=14)),
        Species("gloam-barbel", (0.3, 2.0, 0.9), 0.30, 0.22, 0.11, (0.74, 0.66, 0.62), (0.6, 0.5, 0.48), (0.92, 0.84, 0.8), ("barbel",),
                _p(0.22, body_curve_type=1, body_curve_amount=0.92, body_length=350, head_length=34, mouth_size=9, dorsal_type=0, dorsal_texture_type=0, dorsal_length=45,
                   dorsal_start=11, dorsal_end=22, wing_length=60, wing_type=0, wing_texture_type=0, pelvic_length=45, pelvic_type=0, pelvic_texture_type=0,
                   anal_start=20, anal_end=28, anal_length=40, anal_type=0, anal_texture_type=0, tail_type=3, tail_length=65, pattern_type=0, finlet_type=0, eye_size=7,
                   has_moustache=1, moustache_length=45)),
        Species("root-lamprey", (0.4, 3.0, 1.2), 0.55, 0.06, 0.06, (0.28, 0.3, 0.34), (0.2, 0.22, 0.26), (0.62, 0.66, 0.52), ("tusks",),
                _p(0.06, body_curve_type=0, body_curve_amount=0.97, body_length=430, head_length=20, mouth_size=11, jaw_size=1.1, has_teeth=1, dorsal_type=0, dorsal_texture_type=0,
                   dorsal_length=20, dorsal_start=10, dorsal_end=28, wing_length=14, wing_type=0, wing_texture_type=0, pelvic_length=6, pelvic_type=0, pelvic_texture_type=0,
                   anal_start=16, anal_end=30, anal_length=16, anal_type=0, anal_texture_type=0, tail_type=1, tail_length=20, pattern_type=0, finlet_type=0, eye_size=6, nose_height=0)),
        Species("kelp-pollock", (0.5, 4.0, 1.6), 0.40, 0.24, 0.12, (0.42, 0.5, 0.34), (0.3, 0.36, 0.26), (0.85, 0.88, 0.7), (),
                _p(0.24, body_curve_type=0, body_curve_amount=0.93, body_length=360, head_length=33, jaw_size=1.15, dorsal_type=0, dorsal_texture_type=1, dorsal_length=55,
                   dorsal_start=9, dorsal_end=26, wing_length=65, wing_type=0, wing_texture_type=0, pelvic_length=45, pelvic_type=0, pelvic_texture_type=0,
                   anal_start=18, anal_end=29, anal_length=55, anal_type=0, anal_texture_type=1, tail_type=2, tail_length=70, pattern_type=0, finlet_type=0, eye_size=13)),
        Species("wave-mackerel", (0.3, 1.6, 0.7), 0.34, 0.20, 0.10, (0.22, 0.46, 0.58), (0.18, 0.3, 0.4), (0.08, 0.12, 0.2), ("stripes",),
                _p(0.20, body_curve_type=0, body_curve_amount=0.95, body_length=370, head_length=32, dorsal_type=0, dorsal_texture_type=0, dorsal_length=45,
                   dorsal_start=11, dorsal_end=16, wing_length=55, wing_type=0, wing_texture_type=0, pelvic_length=35, pelvic_type=0, pelvic_texture_type=0,
                   anal_start=21, anal_end=26, anal_length=40, anal_type=0, anal_texture_type=0, tail_type=5, tail_length=105, pattern_type=3, pattern_scale=0.5, finlet_type=2, eye_size=12)),
        Species("sea-ling", (3.0, 18.0, 8.0), 0.95, 0.13, 0.10, (0.5, 0.45, 0.32), (0.35, 0.3, 0.2), (0.8, 0.76, 0.58), ("barbel", "mottle"),
                _p(0.13, body_curve_type=0, body_curve_amount=0.95, body_length=440, head_length=34, mouth_size=10, jaw_size=1.2, dorsal_type=0, dorsal_texture_type=0, dorsal_length=40,
                   dorsal_start=8, dorsal_end=27, wing_length=55, wing_type=0, wing_texture_type=0, pelvic_length=35, pelvic_type=0, pelvic_texture_type=0,
                   anal_start=15, anal_end=29, anal_length=40, anal_type=0, anal_texture_type=0, tail_type=3, tail_length=60, pattern_type=1, pattern_scale=0.8, finlet_type=0, eye_size=11,
                   has_moustache=1, moustache_length=14)),
        Species("storm-tuna", (8.0, 40.0, 18.0), 1.0, 0.30, 0.20, (0.18, 0.28, 0.44), (0.9, 0.8, 0.3), (0.8, 0.85, 0.9), (),
                _p(0.30, body_curve_type=0, body_curve_amount=0.96, body_length=380, head_length=34, dorsal_type=1, dorsal_texture_type=0, dorsal_length=70,
                   dorsal_start=12, dorsal_end=17, wing_length=85, wing_type=0, wing_texture_type=0, pelvic_length=40, pelvic_type=0, pelvic_texture_type=0,
                   anal_start=22, anal_end=27, anal_length=50, anal_type=1, anal_texture_type=0, tail_type=5, tail_length=120, pattern_type=0, finlet_type=2, eye_size=13)),
        Species("ash-gar", (1.5, 9.0, 3.5), 0.75, 0.08, 0.07, (0.34, 0.34, 0.36), (0.22, 0.22, 0.24), (0.88, 0.55, 0.25), ("tusks",),
                _p(0.08, body_curve_type=0, body_curve_amount=0.96, body_length=440, head_length=60, mouth_size=14, jaw_size=1.5, has_teeth=1, teeth_length=12, neck_type=1,
                   dorsal_type=0, dorsal_texture_type=0, dorsal_length=40, dorsal_start=22, dorsal_end=28, wing_length=40, wing_type=0, wing_texture_type=0,
                   pelvic_length=30, pelvic_type=0, pelvic_texture_type=0, pelvic_start=14, pelvic_end=18, anal_start=22, anal_end=29, anal_length=40, anal_type=0, anal_texture_type=0,
                   tail_type=3, tail_length=60, pattern_type=2, pattern_scale=0.5, finlet_type=0, eye_size=9)),
        Species("moonscale", (0.5, 3.0, 1.2), 0.34, 0.34, 0.11, (0.78, 0.8, 0.92), (0.6, 0.55, 0.85), (0.95, 0.95, 1.0), ("stars",),
                _p(0.34, body_curve_type=1, body_curve_amount=0.92, body_length=320, dorsal_type=0, dorsal_texture_type=1, dorsal_length=70,
                   dorsal_start=11, dorsal_end=22, wing_length=80, wing_type=1, wing_texture_type=0, pelvic_length=60, pelvic_type=1, pelvic_texture_type=1,
                   anal_start=20, anal_end=28, anal_length=55, anal_type=0, anal_texture_type=1, tail_type=2, tail_length=95, pattern_type=4, pattern_scale=0.8, finlet_type=0, eye_size=14),
                (0.95, 0.95, 1.0)),
        # ---- rod-locked species: dragon rod (fiery, armoured), glass rod (jewel, delicate), long rod (big, deep)
        Species("ember-sturgeon", (6.0, 30.0, 14.0), 0.9, 0.17, 0.15, (0.34, 0.17, 0.12), (0.7, 0.24, 0.1), (0.98, 0.55, 0.15), ("barbel", "mottle"),
                _p(0.17, body_curve_type=0, body_curve_amount=0.94, body_length=440, head_length=48, mouth_size=7, jaw_size=0.9, nose_height=18, dorsal_type=1, dorsal_texture_type=1,
                   dorsal_length=70, dorsal_start=21, dorsal_end=28, wing_length=75, wing_type=0, wing_texture_type=1, pelvic_length=50, pelvic_type=0, pelvic_texture_type=0,
                   anal_start=22, anal_end=29, anal_length=55, anal_type=0, anal_texture_type=1, tail_type=2, tail_length=95, pattern_type=2, pattern_scale=1.1, finlet_type=0, eye_size=9,
                   has_moustache=1, moustache_length=26)),
        Species("cinder-wyrm", (3.0, 16.0, 7.0), 1.1, 0.09, 0.09, (0.36, 0.1, 0.07), (0.9, 0.3, 0.08), (1.0, 0.7, 0.2), ("mottle", "tusks"),
                _p(0.09, body_curve_type=1, body_curve_amount=0.9, body_length=450, head_length=40, mouth_size=11, jaw_size=1.3, has_teeth=1, teeth_length=12, dorsal_type=1, dorsal_texture_type=1,
                   dorsal_length=70, dorsal_start=8, dorsal_end=28, wing_length=110, wing_type=1, wing_texture_type=1, pelvic_length=20, pelvic_type=0, pelvic_texture_type=0,
                   anal_start=15, anal_end=30, anal_length=50, anal_type=1, anal_texture_type=1, tail_type=1, tail_length=40, pattern_type=4, pattern_scale=0.8, finlet_type=0, eye_size=11,
                   has_beard=1, beard_length=30),
                (1.0, 0.45, 0.1)),
        Species("glass-shiner", (0.02, 0.12, 0.05), 0.10, 0.20, 0.06, (0.7, 0.92, 0.95), (0.6, 0.88, 0.92), (1.0, 1.0, 1.0), ("stars",),
                _p(0.20, body_curve_type=0, body_curve_amount=0.95, body_length=330, dorsal_type=0, dorsal_texture_type=1, dorsal_length=40,
                   dorsal_start=13, dorsal_end=20, wing_length=60, wing_type=0, wing_texture_type=1, pelvic_length=40, pelvic_type=0, pelvic_texture_type=1,
                   anal_start=20, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=1, tail_type=2, tail_length=90, pattern_type=4, pattern_scale=0.6, finlet_type=0, eye_size=15),
                (0.8, 1.0, 1.0)),
        Species("jewel-bleak", (0.05, 0.4, 0.15), 0.18, 0.18, 0.06, (0.78, 0.3, 0.5), (0.9, 0.55, 0.7), (1.0, 0.85, 0.9), ("stars",),
                _p(0.18, body_curve_type=0, body_curve_amount=0.95, body_length=345, dorsal_type=1, dorsal_texture_type=1, dorsal_length=70,
                   dorsal_start=12, dorsal_end=19, wing_length=80, wing_type=1, wing_texture_type=1, pelvic_length=55, pelvic_type=1, pelvic_texture_type=1,
                   anal_start=20, anal_end=28, anal_length=60, anal_type=1, anal_texture_type=1, tail_type=5, tail_length=95, pattern_type=4, pattern_scale=0.5, finlet_type=0, eye_size=14),
                (1.0, 0.9, 0.8)),
        Species("deep-wolffish", (4.0, 22.0, 10.0), 0.85, 0.20, 0.16, (0.3, 0.34, 0.4), (0.22, 0.25, 0.3), (0.7, 0.72, 0.78), ("tusks", "mottle"),
                _p(0.20, body_curve_type=0, body_curve_amount=0.94, body_length=420, head_length=42, mouth_size=11, jaw_size=1.35, has_teeth=1, teeth_length=11, neck_type=1,
                   dorsal_type=0, dorsal_texture_type=0, dorsal_length=40, dorsal_start=8, dorsal_end=28, wing_length=70, wing_type=0, wing_texture_type=0,
                   pelvic_length=18, pelvic_type=0, pelvic_texture_type=0, anal_start=16, anal_end=29, anal_length=38, anal_type=0, anal_texture_type=0,
                   tail_type=3, tail_length=60, pattern_type=3, pattern_scale=0.9, finlet_type=0, eye_size=12)),
        Species("fathom-cod", (8.0, 45.0, 20.0), 1.1, 0.28, 0.20, (0.28, 0.3, 0.26), (0.2, 0.22, 0.2), (0.78, 0.74, 0.58), ("barbel", "mottle"),
                _p(0.28, body_curve_type=1, body_curve_amount=0.9, body_length=350, head_length=38, mouth_size=12, jaw_size=1.35, dorsal_type=0, dorsal_texture_type=1, dorsal_length=60,
                   dorsal_start=9, dorsal_end=26, wing_length=85, wing_type=0, wing_texture_type=0, pelvic_length=60, pelvic_type=0, pelvic_texture_type=0,
                   anal_start=17, anal_end=29, anal_length=55, anal_type=0, anal_texture_type=1, tail_type=3, tail_length=80, pattern_type=1, pattern_scale=1.0, finlet_type=0, eye_size=14,
                   has_moustache=1, moustache_length=28)),
        # ---- the plans no slug had: a flatfish of the shore's sand, the long rod's hammerhead, the deep's big-eye
        Species("silt-flounder", (0.3, 2.4, 0.9), 0.34, 0.42, 0.05, (0.6, 0.52, 0.38), (0.52, 0.44, 0.32), (0.88, 0.46, 0.2), ("mottle",),
                _p(0.42, body_curve_type=0, body_curve_amount=0.96, body_length=300, dorsal_type=0, dorsal_texture_type=1, dorsal_length=40,
                   dorsal_start=4, dorsal_end=28, wing_length=50, wing_type=0, wing_texture_type=0, pelvic_length=30, pelvic_type=0, pelvic_texture_type=0,
                   anal_start=12, anal_end=29, anal_length=35, anal_type=0, anal_texture_type=1, tail_type=1, tail_length=55, pattern_type=1, pattern_scale=0.7, finlet_type=0, eye_size=10)),
        Species("hammer-shark", (6.0, 35.0, 15.0), 1.2, 0.16, 0.12, (0.42, 0.48, 0.54), (0.36, 0.42, 0.48), (0.86, 0.88, 0.9), (),
                _p(0.16, body_curve_type=0, body_curve_amount=0.95, body_length=430, head_length=40, dorsal_type=0, dorsal_texture_type=0, dorsal_length=95,
                   dorsal_start=11, dorsal_end=15, wing_length=110, wing_type=0, wing_texture_type=0, pelvic_length=40, pelvic_type=0, pelvic_texture_type=0,
                   anal_start=23, anal_end=26, anal_length=40, anal_type=0, anal_texture_type=0, tail_type=5, tail_length=120, pattern_type=0, finlet_type=0, eye_size=9),
                (0.95, 0.85, 0.4)),
        Species("gloom-eye", (1.0, 6.0, 2.5), 0.5, 0.3, 0.18, (0.16, 0.14, 0.22), (0.22, 0.2, 0.3), (0.55, 0.85, 1.0), ("stars",),
                _p(0.30, body_curve_type=1, body_curve_amount=0.9, body_length=330, head_length=40, mouth_size=12, jaw_size=1.3, dorsal_type=0, dorsal_texture_type=1, dorsal_length=50,
                   dorsal_start=12, dorsal_end=22, wing_length=70, wing_type=0, wing_texture_type=0, pelvic_length=45, pelvic_type=0, pelvic_texture_type=0,
                   anal_start=20, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=1, tail_type=2, tail_length=75, pattern_type=4, pattern_scale=0.6, finlet_type=0, eye_size=22),
                (0.85, 0.95, 1.0)),
        # ---- Hlýey's lagoon (round 2): a snapper, a parrotfish, an eel that lights the night shallows
        Species("lagoon-snapper", (0.3, 2.0, 0.8), 0.30, 0.29, 0.12, (0.9, 0.36, 0.3), (0.95, 0.55, 0.45), (1.0, 0.88, 0.4), (),
                _p(0.29, body_curve_type=0, body_curve_amount=0.94, body_length=330, head_length=34, dorsal_type=1, dorsal_texture_type=1, dorsal_length=75,
                   dorsal_start=10, dorsal_end=24, wing_length=60, wing_type=0, wing_texture_type=0, pelvic_length=45, pelvic_type=0, pelvic_texture_type=0,
                   anal_start=20, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_type=2, tail_length=80, pattern_type=0, finlet_type=0, eye_size=12)),
        Species("reef-parrotfish", (0.5, 4.0, 1.5), 0.38, 0.40, 0.16, (0.2, 0.68, 0.6), (0.92, 0.42, 0.62), (1.0, 0.85, 0.25), ("mottle",),
                _p(0.40, body_curve_type=1, body_curve_amount=0.9, body_length=310, head_length=36, mouth_size=8, dorsal_type=0, dorsal_texture_type=1, dorsal_length=65,
                   dorsal_start=6, dorsal_end=27, wing_length=70, wing_type=0, wing_texture_type=1, pelvic_length=45, pelvic_type=0, pelvic_texture_type=0,
                   anal_start=15, anal_end=27, anal_length=50, anal_type=0, anal_texture_type=1, tail_type=1, tail_length=70, pattern_type=1, pattern_scale=0.6, finlet_type=0, eye_size=11)),
        Species("glimmer-eel", (0.4, 3.0, 1.2), 0.55, 0.08, 0.06, (0.12, 0.2, 0.26), (0.2, 0.36, 0.44), (0.5, 0.95, 0.9), ("stars",),
                _p(0.08, body_curve_type=0, body_curve_amount=0.97, body_length=420, head_length=22, dorsal_type=0, dorsal_texture_type=0, dorsal_length=18,
                   dorsal_start=7, dorsal_end=28, wing_length=25, wing_type=0, wing_texture_type=0, pelvic_length=8, pelvic_type=0, pelvic_texture_type=0,
                   anal_start=14, anal_end=30, anal_length=16, anal_type=0, anal_texture_type=0, tail_type=1, tail_length=22, pattern_type=4, pattern_scale=0.5, finlet_type=0, eye_size=9, nose_height=0),
                (0.6, 1.0, 0.95)),
        # ---- wave 2 species (fish_loot.py WATER_BODIES), begin
        Species("crucian-carp", (0.1, 1.2, 0.4), 0.22, 0.36, 0.16, (0.72, 0.6, 0.29), (0.6, 0.42, 0.19), (0.88, 0.75, 0.44), (),
                _p(0.36, body_curve_type=0, body_curve_amount=0.94, body_length=330, head_length=34, dorsal_type=0, dorsal_texture_type=1, dorsal_length=33, wing_length=65, wing_type=0, wing_texture_type=0, pelvic_length=50, pelvic_type=0, pelvic_texture_type=0, anal_start=21, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_length=80, pattern_type=0, finlet_type=0, eye_size=12, tail_type=2, dorsal_start=10, dorsal_end=24)),
        Species("roach", (0.1, 1, 0.35), 0.22, 0.28, 0.13, (0.67, 0.72, 0.77), (0.78, 0.31, 0.24), (0.91, 0.88, 0.82), (),
                _p(0.28, body_curve_type=0, body_curve_amount=0.94, body_length=330, head_length=34, dorsal_type=0, dorsal_texture_type=1, dorsal_length=20, wing_length=65, wing_type=0, wing_texture_type=0, pelvic_length=50, pelvic_type=0, pelvic_texture_type=0, anal_start=21, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_length=80, pattern_type=0, finlet_type=0, eye_size=12, tail_type=2, dorsal_start=13, dorsal_end=20),
                (0.9, 0.2, 0.15)),
        Species("ruffe", (0.03, 0.2, 0.08), 0.12, 0.3, 0.14, (0.54, 0.48, 0.26), (0.42, 0.35, 0.19), (0.85, 0.75, 0.44), (),
                _p(0.3, body_curve_type=0, body_curve_amount=0.94, body_length=330, head_length=34, dorsal_type=0, dorsal_texture_type=1, dorsal_length=26, wing_length=65, wing_type=0, wing_texture_type=0, pelvic_length=50, pelvic_type=0, pelvic_texture_type=0, anal_start=21, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_length=80, pattern_type=0, finlet_type=0, eye_size=12, tail_type=3, dorsal_start=7, dorsal_end=25)),
        Species("gudgeon", (0.03, 0.2, 0.09), 0.13, 0.17, 0.08, (0.6, 0.6, 0.42), (0.69, 0.66, 0.53), (0.31, 0.31, 0.23), ("barbel",),
                _p(0.17, body_curve_type=0, body_curve_amount=0.94, body_length=330, head_length=34, dorsal_type=0, dorsal_texture_type=1, dorsal_length=20, wing_length=65, wing_type=0, wing_texture_type=0, pelvic_length=50, pelvic_type=0, pelvic_texture_type=0, anal_start=21, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_length=80, pattern_type=0, finlet_type=0, eye_size=12, tail_type=2, dorsal_start=12, dorsal_end=17, has_moustache=1)),
        Species("bullhead", (0.02, 0.15, 0.06), 0.11, 0.2, 0.09, (0.48, 0.39, 0.27), (0.54, 0.45, 0.32), (0.78, 0.69, 0.5), ("mottle",),
                _p(0.2, body_curve_type=0, body_curve_amount=0.94, body_length=330, head_length=34, dorsal_type=0, dorsal_texture_type=1, dorsal_length=20, wing_length=65, wing_type=0, wing_texture_type=0, pelvic_length=50, pelvic_type=0, pelvic_texture_type=0, anal_start=21, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_length=80, pattern_type=0, finlet_type=0, eye_size=12, tail_type=3, dorsal_start=11, dorsal_end=23)),
        Species("stickleback", (0.01, 0.08, 0.03), 0.08, 0.22, 0.1, (0.48, 0.54, 0.35), (0.42, 0.48, 0.31), (0.85, 0.29, 0.23), ("stripes",),
                _p(0.22, body_curve_type=0, body_curve_amount=0.94, body_length=330, head_length=34, dorsal_type=0, dorsal_texture_type=1, dorsal_length=30, wing_length=65, wing_type=0, wing_texture_type=0, pelvic_length=50, pelvic_type=0, pelvic_texture_type=0, anal_start=21, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_length=80, pattern_type=0, finlet_type=0, eye_size=12, tail_type=2, dorsal_start=10, dorsal_end=19)),
        Species("tench", (0.4, 3.5, 1.5), 0.38, 0.33, 0.15, (0.29, 0.42, 0.23), (0.23, 0.32, 0.19), (0.75, 0.63, 0.25), (),
                _p(0.33, body_curve_type=0, body_curve_amount=0.94, body_length=330, head_length=34, dorsal_type=0, dorsal_texture_type=1, dorsal_length=20, wing_length=65, wing_type=0, wing_texture_type=0, pelvic_length=50, pelvic_type=0, pelvic_texture_type=0, anal_start=21, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_length=80, pattern_type=0, finlet_type=0, eye_size=12, tail_type=3, dorsal_start=16, dorsal_end=21)),
        Species("ide", (0.3, 3, 1.1), 0.34, 0.27, 0.12, (0.72, 0.66, 0.44), (0.88, 0.54, 0.22), (0.94, 0.88, 0.69), (),
                _p(0.27, body_curve_type=0, body_curve_amount=0.94, body_length=330, head_length=34, dorsal_type=0, dorsal_texture_type=1, dorsal_length=23, wing_length=65, wing_type=0, wing_texture_type=0, pelvic_length=50, pelvic_type=0, pelvic_texture_type=0, anal_start=21, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_length=80, pattern_type=0, finlet_type=0, eye_size=12, tail_type=2, dorsal_start=12, dorsal_end=19)),
        Species("zander", (0.8, 6, 2.5), 0.5, 0.18, 0.08, (0.49, 0.54, 0.38), (0.35, 0.42, 0.29), (0.18, 0.23, 0.14), ("stripes",),
                _p(0.18, body_curve_type=0, body_curve_amount=0.94, body_length=330, head_length=34, dorsal_type=0, dorsal_texture_type=1, dorsal_length=30, wing_length=65, wing_type=0, wing_texture_type=0, pelvic_length=50, pelvic_type=0, pelvic_texture_type=0, anal_start=21, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_length=80, pattern_type=0, finlet_type=0, eye_size=12, tail_type=2, dorsal_start=10, dorsal_end=16),
                (0.9, 0.95, 0.8)),
        Species("burbot", (0.5, 4, 1.6), 0.5, 0.15, 0.07, (0.42, 0.35, 0.23), (0.29, 0.24, 0.16), (0.72, 0.63, 0.38), ("barbel", "mottle",),
                _p(0.15, body_curve_type=0, body_curve_amount=0.94, body_length=330, head_length=34, dorsal_type=0, dorsal_texture_type=1, dorsal_length=20, wing_length=65, wing_type=0, wing_texture_type=0, pelvic_length=50, pelvic_type=0, pelvic_texture_type=0, anal_start=21, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_length=80, pattern_type=0, finlet_type=0, eye_size=12, tail_type=3, dorsal_start=16, dorsal_end=24, has_moustache=1)),
        Species("whitefish", (0.3, 2.5, 1), 0.36, 0.24, 0.11, (0.82, 0.85, 0.86), (0.6, 0.64, 0.67), (0.96, 0.96, 0.93), (),
                _p(0.24, body_curve_type=0, body_curve_amount=0.94, body_length=330, head_length=34, dorsal_type=0, dorsal_texture_type=1, dorsal_length=20, wing_length=65, wing_type=0, wing_texture_type=0, pelvic_length=50, pelvic_type=0, pelvic_texture_type=0, anal_start=21, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_length=80, pattern_type=0, finlet_type=0, eye_size=12, tail_type=2, dorsal_start=13, dorsal_end=19)),
        Species("sun-perch", (0.1, 0.8, 0.3), 0.16, 0.55, 0.25, (0.88, 0.63, 0.19), (0.85, 0.44, 0.16), (0.23, 0.54, 0.78), ("stripes",),
                _p(0.55, body_curve_type=0, body_curve_amount=0.94, body_length=330, head_length=34, dorsal_type=0, dorsal_texture_type=1, dorsal_length=33, wing_length=65, wing_type=0, wing_texture_type=0, pelvic_length=50, pelvic_type=0, pelvic_texture_type=0, anal_start=21, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_length=80, pattern_type=0, finlet_type=0, eye_size=12, tail_type=3, dorsal_start=10, dorsal_end=22)),
        Species("wels", (8, 60, 22), 1.3, 0.17, 0.08, (0.23, 0.24, 0.23), (0.16, 0.17, 0.16), (0.69, 0.66, 0.53), ("barbel", "mottle",),
                _p(0.17, body_curve_type=0, body_curve_amount=0.94, body_length=330, head_length=34, dorsal_type=0, dorsal_texture_type=1, dorsal_length=20, wing_length=65, wing_type=0, wing_texture_type=0, pelvic_length=50, pelvic_type=0, pelvic_texture_type=0, anal_start=21, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_length=80, pattern_type=0, finlet_type=0, eye_size=12, tail_type=3, dorsal_start=10, dorsal_end=22, has_moustache=1)),
        Species("icicle-eel", (0.3, 2.2, 0.9), 0.6, 0.065, 0.04, (0.74, 0.85, 0.91), (0.56, 0.72, 0.82), (0.94, 0.99, 1), ("stars",),
                _p(0.065, body_curve_type=0, body_curve_amount=0.97, body_length=420, head_length=22, dorsal_type=0, dorsal_texture_type=0, dorsal_length=18, dorsal_start=7, dorsal_end=28, wing_length=25, wing_type=0, wing_texture_type=0, pelvic_length=8, pelvic_type=0, pelvic_texture_type=0, anal_start=14, anal_end=30, anal_length=16, anal_type=0, anal_texture_type=0, tail_type=1, tail_length=22, pattern_type=0, finlet_type=0, eye_size=8, nose_height=0),
                (0.7, 0.95, 1)),
        Species("frostjaw", (0.8, 6, 2.4), 0.55, 0.22, 0.1, (0.53, 0.66, 0.75), (0.42, 0.54, 0.64), (0.91, 0.96, 0.99), ("tusks",),
                _p(0.22, body_curve_type=0, body_curve_amount=0.94, body_length=330, head_length=34, dorsal_type=0, dorsal_texture_type=1, dorsal_length=23, wing_length=65, wing_type=0, wing_texture_type=0, pelvic_length=50, pelvic_type=0, pelvic_texture_type=0, anal_start=21, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_length=80, pattern_type=0, finlet_type=0, eye_size=12, tail_type=2, dorsal_start=10, dorsal_end=19, has_teeth=1, mouth_size=11)),
        Species("ember-ray", (2, 14, 6), 0.8, 0.4, 0.05, (0.78, 0.35, 0.16), (0.63, 0.23, 0.1), (1, 0.75, 0.38), ("stars",),
                _p(0.4, body_curve_type=0, body_curve_amount=0.96, body_length=300, dorsal_type=0, dorsal_texture_type=1, dorsal_length=40, dorsal_start=4, dorsal_end=28, wing_length=50, wing_type=0, wing_texture_type=0, pelvic_length=30, pelvic_type=0, pelvic_texture_type=0, anal_start=12, anal_end=29, anal_length=35, anal_type=0, anal_texture_type=1, tail_type=1, tail_length=55, pattern_type=1, pattern_scale=0.7, finlet_type=0, eye_size=10)),
        Species("forge-bream", (0.5, 3, 1.2), 0.3, 0.5, 0.23, (0.72, 0.29, 0.16), (0.48, 0.16, 0.1), (0.94, 0.63, 0.25), (),
                _p(0.5, body_curve_type=0, body_curve_amount=0.94, body_length=330, head_length=34, dorsal_type=0, dorsal_texture_type=1, dorsal_length=26, wing_length=65, wing_type=0, wing_texture_type=0, pelvic_length=50, pelvic_type=0, pelvic_texture_type=0, anal_start=21, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_length=80, pattern_type=0, finlet_type=0, eye_size=12, tail_type=3, dorsal_start=11, dorsal_end=23)),
        Species("sulfur-eel", (0.5, 3, 1.4), 0.65, 0.075, 0.04, (0.78, 0.69, 0.19), (0.54, 0.48, 0.13), (0.25, 0.23, 0.06), ("mottle",),
                _p(0.075, body_curve_type=0, body_curve_amount=0.97, body_length=420, head_length=22, dorsal_type=0, dorsal_texture_type=0, dorsal_length=18, dorsal_start=7, dorsal_end=28, wing_length=25, wing_type=0, wing_texture_type=0, pelvic_length=8, pelvic_type=0, pelvic_texture_type=0, anal_start=14, anal_end=30, anal_length=16, anal_type=0, anal_texture_type=0, tail_type=1, tail_length=22, pattern_type=0, finlet_type=0, eye_size=8, nose_height=0)),
        Species("gall-lumpfish", (0.8, 5, 2.2), 0.3, 0.5, 0.23, (0.42, 0.48, 0.16), (0.54, 0.6, 0.23), (0.82, 0.85, 0.44), ("mottle",),
                _p(0.5, body_curve_type=0, body_curve_amount=0.94, body_length=330, head_length=34, dorsal_type=0, dorsal_texture_type=1, dorsal_length=20, wing_length=65, wing_type=0, wing_texture_type=0, pelvic_length=50, pelvic_type=0, pelvic_texture_type=0, anal_start=21, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_length=80, pattern_type=0, finlet_type=0, eye_size=12, tail_type=3, dorsal_start=18, dorsal_end=22)),
        Species("lantern-bleak", (0.02, 0.15, 0.06), 0.11, 0.2, 0.09, (0.6, 0.85, 0.82), (0.47, 0.75, 0.72), (0.91, 1, 0.97), ("stars",),
                _p(0.2, body_curve_type=0, body_curve_amount=0.94, body_length=330, head_length=34, dorsal_type=0, dorsal_texture_type=1, dorsal_length=20, wing_length=65, wing_type=0, wing_texture_type=0, pelvic_length=50, pelvic_type=0, pelvic_texture_type=0, anal_start=21, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_length=80, pattern_type=0, finlet_type=0, eye_size=12, tail_type=2, dorsal_start=12, dorsal_end=19),
                (0.9, 1, 0.9)),
        Species("wisp-fish", (0.05, 0.5, 0.2), 0.2, 0.46, 0.21, (0.78, 0.72, 0.91), (0.66, 0.6, 0.82), (0.94, 0.94, 1), ("ghost",),
                _p(0.46, body_curve_type=0, body_curve_amount=0.94, body_length=330, head_length=34, dorsal_type=0, dorsal_texture_type=1, dorsal_length=33, wing_length=65, wing_type=0, wing_texture_type=0, pelvic_length=50, pelvic_type=0, pelvic_texture_type=0, anal_start=21, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_length=80, pattern_type=0, finlet_type=0, eye_size=12, tail_type=2, dorsal_start=10, dorsal_end=22),
                (0.95, 0.95, 1)),
        Species("cave-eel", (0.3, 2.2, 0.9), 0.55, 0.07, 0.04, (0.88, 0.78, 0.75), (0.78, 0.66, 0.63), (0.94, 0.87, 0.85), ("blind",),
                _p(0.07, body_curve_type=0, body_curve_amount=0.97, body_length=420, head_length=22, dorsal_type=0, dorsal_texture_type=0, dorsal_length=18, dorsal_start=7, dorsal_end=28, wing_length=25, wing_type=0, wing_texture_type=0, pelvic_length=8, pelvic_type=0, pelvic_texture_type=0, anal_start=14, anal_end=30, anal_length=16, anal_type=0, anal_texture_type=0, tail_type=1, tail_length=22, pattern_type=0, finlet_type=0, eye_size=8, nose_height=0)),
        Species("mimir-carp", (3, 18, 8), 0.7, 0.36, 0.16, (0.23, 0.48, 0.48), (0.16, 0.35, 0.38), (0.85, 0.75, 0.44), (),
                _p(0.36, body_curve_type=0, body_curve_amount=0.94, body_length=330, head_length=34, dorsal_type=0, dorsal_texture_type=1, dorsal_length=23, wing_length=65, wing_type=0, wing_texture_type=0, pelvic_length=50, pelvic_type=0, pelvic_texture_type=0, anal_start=21, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_length=80, pattern_type=0, finlet_type=0, eye_size=12, tail_type=3, dorsal_start=10, dorsal_end=22)),
        Species("norn-trout", (0.4, 3, 1.2), 0.4, 0.25, 0.11, (0.42, 0.54, 0.35), (0.78, 0.63, 0.31), (0.63, 0.35, 0.54), ("mottle",),
                _p(0.25, body_curve_type=0, body_curve_amount=0.94, body_length=330, head_length=34, dorsal_type=0, dorsal_texture_type=1, dorsal_length=20, wing_length=65, wing_type=0, wing_texture_type=0, pelvic_length=50, pelvic_type=0, pelvic_texture_type=0, anal_start=21, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_length=80, pattern_type=0, finlet_type=0, eye_size=12, tail_type=2, dorsal_start=12, dorsal_end=18)),
        Species("hoard-carp", (5, 20, 10), 0.75, 0.37, 0.17, (0.88, 0.69, 0.19), (0.78, 0.56, 0.13), (1, 0.94, 0.63), (),
                _p(0.37, body_curve_type=0, body_curve_amount=0.94, body_length=330, head_length=34, dorsal_type=0, dorsal_texture_type=1, dorsal_length=23, wing_length=65, wing_type=0, wing_texture_type=0, pelvic_length=50, pelvic_type=0, pelvic_texture_type=0, anal_start=21, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_length=80, pattern_type=0, finlet_type=0, eye_size=12, tail_type=3, dorsal_start=10, dorsal_end=22),
                (1, 0.95, 0.5)),
        Species("sprat", (0.01, 0.06, 0.03), 0.1, 0.2, 0.09, (0.66, 0.75, 0.72), (0.48, 0.6, 0.56), (0.91, 0.96, 0.94), (),
                _p(0.2, body_curve_type=0, body_curve_amount=0.94, body_length=330, head_length=34, dorsal_type=0, dorsal_texture_type=1, dorsal_length=20, wing_length=65, wing_type=0, wing_texture_type=0, pelvic_length=50, pelvic_type=0, pelvic_texture_type=0, anal_start=21, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_length=80, pattern_type=0, finlet_type=0, eye_size=12, tail_type=2, dorsal_start=13, dorsal_end=18)),
        Species("sandeel", (0.01, 0.08, 0.03), 0.22, 0.05, 0.04, (0.66, 0.72, 0.78), (0.5, 0.6, 0.66), (0.88, 0.93, 0.96), (),
                _p(0.05, body_curve_type=0, body_curve_amount=0.97, body_length=420, head_length=22, dorsal_type=0, dorsal_texture_type=0, dorsal_length=18, dorsal_start=7, dorsal_end=28, wing_length=25, wing_type=0, wing_texture_type=0, pelvic_length=8, pelvic_type=0, pelvic_texture_type=0, anal_start=14, anal_end=30, anal_length=16, anal_type=0, anal_texture_type=0, tail_type=1, tail_length=22, pattern_type=0, finlet_type=0, eye_size=8, nose_height=0)),
        Species("dab", (0.05, 0.4, 0.18), 0.22, 0.44, 0.05, (0.69, 0.6, 0.44), (0.63, 0.54, 0.38), (0.85, 0.75, 0.56), ("mottle",),
                _p(0.44, body_curve_type=0, body_curve_amount=0.96, body_length=300, dorsal_type=0, dorsal_texture_type=1, dorsal_length=40, dorsal_start=4, dorsal_end=28, wing_length=50, wing_type=0, wing_texture_type=0, pelvic_length=30, pelvic_type=0, pelvic_texture_type=0, anal_start=12, anal_end=29, anal_length=35, anal_type=0, anal_texture_type=1, tail_type=1, tail_length=55, pattern_type=1, pattern_scale=0.7, finlet_type=0, eye_size=10)),
        Species("sea-scorpion", (0.05, 0.5, 0.2), 0.2, 0.24, 0.11, (0.54, 0.29, 0.2), (0.42, 0.23, 0.16), (0.88, 0.63, 0.44), ("mottle",),
                _p(0.24, body_curve_type=0, body_curve_amount=0.94, body_length=330, head_length=34, dorsal_type=0, dorsal_texture_type=1, dorsal_length=26, wing_length=65, wing_type=0, wing_texture_type=0, pelvic_length=50, pelvic_type=0, pelvic_texture_type=0, anal_start=21, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_length=80, pattern_type=0, finlet_type=0, eye_size=12, tail_type=3, dorsal_start=10, dorsal_end=22)),
        Species("ballan-wrasse", (0.2, 2, 0.8), 0.3, 0.27, 0.12, (0.35, 0.48, 0.29), (0.54, 0.35, 0.23), (0.82, 0.63, 0.25), ("mottle",),
                _p(0.27, body_curve_type=0, body_curve_amount=0.94, body_length=330, head_length=34, dorsal_type=0, dorsal_texture_type=1, dorsal_length=23, wing_length=65, wing_type=0, wing_texture_type=0, pelvic_length=50, pelvic_type=0, pelvic_texture_type=0, anal_start=21, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_length=80, pattern_type=0, finlet_type=0, eye_size=12, tail_type=3, dorsal_start=10, dorsal_end=23)),
        Species("grey-mullet", (0.3, 3, 1.2), 0.38, 0.2, 0.09, (0.6, 0.64, 0.66), (0.42, 0.45, 0.47), (0.91, 0.93, 0.91), ("stripes",),
                _p(0.2, body_curve_type=0, body_curve_amount=0.94, body_length=330, head_length=34, dorsal_type=0, dorsal_texture_type=1, dorsal_length=23, wing_length=65, wing_type=0, wing_texture_type=0, pelvic_length=50, pelvic_type=0, pelvic_texture_type=0, anal_start=21, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_length=80, pattern_type=0, finlet_type=0, eye_size=12, tail_type=2, dorsal_start=10, dorsal_end=14)),
        Species("whiting", (0.1, 1, 0.4), 0.26, 0.16, 0.07, (0.75, 0.72, 0.6), (0.54, 0.52, 0.41), (0.94, 0.93, 0.85), ("barbel",),
                _p(0.16, body_curve_type=0, body_curve_amount=0.94, body_length=330, head_length=34, dorsal_type=0, dorsal_texture_type=1, dorsal_length=20, wing_length=65, wing_type=0, wing_texture_type=0, pelvic_length=50, pelvic_type=0, pelvic_texture_type=0, anal_start=21, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_length=80, pattern_type=0, finlet_type=0, eye_size=12, tail_type=2, dorsal_start=10, dorsal_end=17, has_moustache=1)),
        Species("pipefish", (0.01, 0.08, 0.03), 0.25, 0.04, 0.04, (0.48, 0.54, 0.31), (0.54, 0.6, 0.38), (0.82, 0.85, 0.63), ("stripes",),
                _p(0.04, body_curve_type=0, body_curve_amount=0.94, body_length=330, head_length=34, dorsal_type=0, dorsal_texture_type=1, dorsal_length=20, wing_length=65, wing_type=0, wing_texture_type=0, pelvic_length=50, pelvic_type=0, pelvic_texture_type=0, anal_start=21, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_length=80, pattern_type=0, finlet_type=0, eye_size=12, tail_type=3, dorsal_start=19, dorsal_end=26)),
        Species("rockling", (0.05, 0.5, 0.2), 0.24, 0.14, 0.06, (0.54, 0.35, 0.27), (0.42, 0.28, 0.21), (0.85, 0.72, 0.56), ("barbel", "mottle",),
                _p(0.14, body_curve_type=0, body_curve_amount=0.94, body_length=330, head_length=34, dorsal_type=0, dorsal_texture_type=1, dorsal_length=20, wing_length=65, wing_type=0, wing_texture_type=0, pelvic_length=50, pelvic_type=0, pelvic_texture_type=0, anal_start=21, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_length=80, pattern_type=0, finlet_type=0, eye_size=12, tail_type=3, dorsal_start=4, dorsal_end=26, has_moustache=1)),
        Species("flying-fish", (0.1, 0.7, 0.3), 0.24, 0.16, 0.07, (0.29, 0.47, 0.66), (0.66, 0.78, 0.88), (0.91, 0.96, 0.99), (),
                _p(0.16, body_curve_type=0, body_curve_amount=0.94, body_length=330, head_length=34, dorsal_type=0, dorsal_texture_type=1, dorsal_length=20, wing_length=65, wing_type=0, wing_texture_type=0, pelvic_length=50, pelvic_type=0, pelvic_texture_type=0, anal_start=21, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_length=80, pattern_type=0, finlet_type=0, eye_size=12, tail_type=2, dorsal_start=18, dorsal_end=23)),
        Species("haddock", (0.6, 5, 2), 0.5, 0.21, 0.09, (0.48, 0.45, 0.53), (0.35, 0.34, 0.42), (0.1, 0.1, 0.13), ("barbel",),
                _p(0.21, body_curve_type=0, body_curve_amount=0.94, body_length=330, head_length=34, dorsal_type=0, dorsal_texture_type=1, dorsal_length=26, wing_length=65, wing_type=0, wing_texture_type=0, pelvic_length=50, pelvic_type=0, pelvic_texture_type=0, anal_start=21, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_length=80, pattern_type=0, finlet_type=0, eye_size=12, tail_type=2, dorsal_start=8, dorsal_end=15, has_moustache=1)),
        Species("sand-plaice", (0.4, 3, 1.2), 0.4, 0.5, 0.05, (0.63, 0.48, 0.31), (0.54, 0.42, 0.27), (0.91, 0.42, 0.19), ("mottle",),
                _p(0.5, body_curve_type=0, body_curve_amount=0.94, body_length=330, head_length=34, dorsal_type=0, dorsal_texture_type=1, dorsal_length=20, wing_length=65, wing_type=0, wing_texture_type=0, pelvic_length=50, pelvic_type=0, pelvic_texture_type=0, anal_start=21, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_length=80, pattern_type=0, finlet_type=0, eye_size=12, tail_type=3, dorsal_start=4, dorsal_end=29)),
        Species("turbot", (1.5, 10, 4), 0.5, 0.6, 0.05, (0.54, 0.48, 0.35), (0.42, 0.37, 0.27), (0.78, 0.72, 0.54), ("mottle",),
                _p(0.6, body_curve_type=0, body_curve_amount=0.96, body_length=300, dorsal_type=0, dorsal_texture_type=1, dorsal_length=40, dorsal_start=4, dorsal_end=28, wing_length=50, wing_type=0, wing_texture_type=0, pelvic_length=30, pelvic_type=0, pelvic_texture_type=0, anal_start=12, anal_end=29, anal_length=35, anal_type=0, anal_texture_type=1, tail_type=1, tail_length=55, pattern_type=1, pattern_scale=0.7, finlet_type=0, eye_size=10)),
        Species("dapple-skate", (2, 20, 7), 0.7, 0.08, 0.5, (0.48, 0.44, 0.39), (0.38, 0.35, 0.31), (0.78, 0.74, 0.66), (),
                _p(0.08, body_curve_type=0, body_curve_amount=0.97, body_length=420, head_length=22, dorsal_type=0, dorsal_texture_type=0, dorsal_length=18, dorsal_start=7, dorsal_end=28, wing_length=25, wing_type=0, wing_texture_type=0, pelvic_length=8, pelvic_type=0, pelvic_texture_type=0, anal_start=14, anal_end=30, anal_length=16, anal_type=0, anal_texture_type=0, tail_type=1, tail_length=22, pattern_type=0, finlet_type=0, eye_size=8, nose_height=0)),
        Species("sea-bass", (0.5, 5, 2), 0.45, 0.22, 0.1, (0.68, 0.72, 0.74), (0.35, 0.42, 0.44), (0.93, 0.95, 0.95), (),
                _p(0.22, body_curve_type=0, body_curve_amount=0.94, body_length=330, head_length=34, dorsal_type=0, dorsal_texture_type=1, dorsal_length=30, wing_length=65, wing_type=0, wing_texture_type=0, pelvic_length=50, pelvic_type=0, pelvic_texture_type=0, anal_start=21, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_length=80, pattern_type=0, finlet_type=0, eye_size=12, tail_type=2, dorsal_start=9, dorsal_end=16)),
        Species("lumpsucker", (0.4, 4, 1.5), 0.3, 0.48, 0.22, (0.35, 0.42, 0.5), (0.27, 0.33, 0.42), (0.78, 0.66, 0.44), ("mottle",),
                _p(0.48, body_curve_type=0, body_curve_amount=0.94, body_length=330, head_length=34, dorsal_type=0, dorsal_texture_type=1, dorsal_length=20, wing_length=65, wing_type=0, wing_texture_type=0, pelvic_length=50, pelvic_type=0, pelvic_texture_type=0, anal_start=21, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_length=80, pattern_type=0, finlet_type=0, eye_size=12, tail_type=3, dorsal_start=13, dorsal_end=22)),
        Species("conger", (3, 30, 12), 1.5, 0.1, 0.05, (0.42, 0.42, 0.38), (0.29, 0.29, 0.27), (0.75, 0.74, 0.66), (),
                _p(0.1, body_curve_type=0, body_curve_amount=0.97, body_length=420, head_length=22, dorsal_type=0, dorsal_texture_type=0, dorsal_length=18, dorsal_start=7, dorsal_end=28, wing_length=25, wing_type=0, wing_texture_type=0, pelvic_length=8, pelvic_type=0, pelvic_texture_type=0, anal_start=14, anal_end=30, anal_length=16, anal_type=0, anal_texture_type=0, tail_type=1, tail_length=22, pattern_type=0, finlet_type=0, eye_size=8, nose_height=0)),
        Species("cuckoo-wrasse", (0.1, 0.8, 0.3), 0.24, 0.25, 0.11, (0.88, 0.48, 0.16), (0.23, 0.54, 0.82), (0.16, 0.31, 0.63), (),
                _p(0.25, body_curve_type=0, body_curve_amount=0.94, body_length=330, head_length=34, dorsal_type=0, dorsal_texture_type=1, dorsal_length=23, wing_length=65, wing_type=0, wing_texture_type=0, pelvic_length=50, pelvic_type=0, pelvic_texture_type=0, anal_start=21, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_length=80, pattern_type=0, finlet_type=0, eye_size=12, tail_type=3, dorsal_start=10, dorsal_end=22)),
        Species("red-gurnard", (0.3, 2, 0.9), 0.3, 0.22, 0.1, (0.85, 0.35, 0.26), (0.75, 0.28, 0.19), (0.96, 0.78, 0.69), (),
                _p(0.22, body_curve_type=0, body_curve_amount=0.94, body_length=330, head_length=34, dorsal_type=0, dorsal_texture_type=1, dorsal_length=30, wing_length=65, wing_type=0, wing_texture_type=0, pelvic_length=50, pelvic_type=0, pelvic_texture_type=0, anal_start=21, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_length=80, pattern_type=0, finlet_type=0, eye_size=12, tail_type=2, dorsal_start=8, dorsal_end=19)),
        Species("tide-seahorse", (0.01, 0.1, 0.04), 0.14, 0.14, 0.06, (0.85, 0.6, 0.22), (0.88, 0.72, 0.38), (0.44, 0.25, 0.06), (),
                _p(0.14, body_curve_type=0, body_curve_amount=0.94, body_length=330, head_length=34, dorsal_type=0, dorsal_texture_type=1, dorsal_length=20, wing_length=65, wing_type=0, wing_texture_type=0, pelvic_length=50, pelvic_type=0, pelvic_texture_type=0, anal_start=21, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_length=80, pattern_type=0, finlet_type=0, eye_size=12, tail_type=3, dorsal_start=13, dorsal_end=18)),
        Species("pufferfish", (0.3, 2.5, 1), 0.26, 0.5, 0.23, (0.85, 0.78, 0.56), (0.66, 0.6, 0.41), (0.31, 0.22, 0.13), ("mottle",),
                _p(0.5, body_curve_type=0, body_curve_amount=0.94, body_length=330, head_length=34, dorsal_type=0, dorsal_texture_type=1, dorsal_length=20, wing_length=65, wing_type=0, wing_texture_type=0, pelvic_length=50, pelvic_type=0, pelvic_texture_type=0, anal_start=21, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_length=80, pattern_type=0, finlet_type=0, eye_size=12, tail_type=3, dorsal_start=21, dorsal_end=25)),
        Species("sun-angelfish", (0.1, 1, 0.4), 0.22, 0.75, 0.34, (0.91, 0.82, 0.38), (0.91, 0.88, 0.6), (0.16, 0.23, 0.41), ("stripes",),
                _p(0.75, body_curve_type=0, body_curve_amount=0.94, body_length=330, head_length=34, dorsal_type=0, dorsal_texture_type=1, dorsal_length=50, wing_length=65, wing_type=0, wing_texture_type=0, pelvic_length=50, pelvic_type=0, pelvic_texture_type=0, anal_start=21, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_length=80, pattern_type=0, finlet_type=0, eye_size=12, tail_type=3, dorsal_start=10, dorsal_end=22)),
        Species("cuttlefish", (0.3, 3, 1.2), 0.35, 0.25, 0.11, (0.6, 0.48, 0.54), (0.48, 0.35, 0.42), (0.91, 0.82, 0.85), ("mottle",),
                _p(0.25, body_curve_type=0, body_curve_amount=0.94, body_length=330, head_length=34, dorsal_type=0, dorsal_texture_type=1, dorsal_length=20, wing_length=65, wing_type=0, wing_texture_type=0, pelvic_length=50, pelvic_type=0, pelvic_texture_type=0, anal_start=21, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_length=80, pattern_type=0, finlet_type=0, eye_size=12, tail_type=3, dorsal_start=16, dorsal_end=29)),
        Species("ribbonfish", (0.5, 4, 1.5), 1, 0.1, 0.05, (0.78, 0.82, 0.85), (0.91, 0.63, 0.66), (0.94, 0.96, 0.97), (),
                _p(0.1, body_curve_type=0, body_curve_amount=0.97, body_length=420, head_length=22, dorsal_type=0, dorsal_texture_type=0, dorsal_length=18, dorsal_start=7, dorsal_end=28, wing_length=25, wing_type=0, wing_texture_type=0, pelvic_length=8, pelvic_type=0, pelvic_texture_type=0, anal_start=14, anal_end=30, anal_length=16, anal_type=0, anal_texture_type=0, tail_type=1, tail_length=22, pattern_type=0, finlet_type=0, eye_size=8, nose_height=0)),
        Species("triggerfish", (0.3, 2, 0.9), 0.26, 0.46, 0.21, (0.23, 0.48, 0.54), (0.88, 0.56, 0.23), (0.94, 0.88, 0.56), ("mottle",),
                _p(0.46, body_curve_type=0, body_curve_amount=0.94, body_length=330, head_length=34, dorsal_type=0, dorsal_texture_type=1, dorsal_length=30, wing_length=65, wing_type=0, wing_texture_type=0, pelvic_length=50, pelvic_type=0, pelvic_texture_type=0, anal_start=21, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_length=80, pattern_type=0, finlet_type=0, eye_size=12, tail_type=3, dorsal_start=10, dorsal_end=22)),
        Species("spurdog", (1, 8, 3), 0.9, 0.12, 0.05, (0.48, 0.5, 0.53), (0.35, 0.38, 0.41), (0.91, 0.92, 0.93), (),
                _p(0.12, body_curve_type=0, body_curve_amount=0.94, body_length=330, head_length=34, dorsal_type=0, dorsal_texture_type=1, dorsal_length=26, wing_length=65, wing_type=0, wing_texture_type=0, pelvic_length=50, pelvic_type=0, pelvic_texture_type=0, anal_start=21, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_length=80, pattern_type=0, finlet_type=0, eye_size=12, tail_type=2, dorsal_start=10, dorsal_end=13)),
        Species("boxfish", (0.1, 0.8, 0.3), 0.2, 0.4, 0.18, (0.91, 0.82, 0.31), (0.85, 0.75, 0.25), (0.16, 0.16, 0.19), (),
                _p(0.4, body_curve_type=0, body_curve_amount=0.94, body_length=330, head_length=34, dorsal_type=0, dorsal_texture_type=1, dorsal_length=20, wing_length=65, wing_type=0, wing_texture_type=0, pelvic_length=50, pelvic_type=0, pelvic_texture_type=0, anal_start=21, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_length=80, pattern_type=0, finlet_type=0, eye_size=12, tail_type=3, dorsal_start=19, dorsal_end=25)),
        Species("halibut", (10, 120, 40), 1.5, 0.45, 0.05, (0.29, 0.34, 0.28), (0.23, 0.27, 0.22), (0.66, 0.69, 0.6), ("mottle",),
                _p(0.45, body_curve_type=0, body_curve_amount=0.96, body_length=300, dorsal_type=0, dorsal_texture_type=1, dorsal_length=40, dorsal_start=4, dorsal_end=28, wing_length=50, wing_type=0, wing_texture_type=0, pelvic_length=30, pelvic_type=0, pelvic_texture_type=0, anal_start=12, anal_end=29, anal_length=35, anal_type=0, anal_texture_type=1, tail_type=1, tail_length=55, pattern_type=1, pattern_scale=0.7, finlet_type=0, eye_size=10)),
        Species("monkfish", (5, 35, 14), 0.9, 0.34, 0.15, (0.42, 0.35, 0.27), (0.29, 0.24, 0.19), (0.78, 0.72, 0.56), ("mottle",),
                _p(0.34, body_curve_type=0, body_curve_amount=0.94, body_length=330, head_length=34, dorsal_type=0, dorsal_texture_type=1, dorsal_length=20, wing_length=65, wing_type=0, wing_texture_type=0, pelvic_length=50, pelvic_type=0, pelvic_texture_type=0, anal_start=21, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_length=80, pattern_type=0, finlet_type=0, eye_size=12, tail_type=3, dorsal_start=16, dorsal_end=26)),
        Species("ocean-sunfish", (20, 160, 60), 1.4, 0.75, 0.34, (0.54, 0.58, 0.61), (0.42, 0.45, 0.49), (0.85, 0.86, 0.88), (),
                _p(0.75, body_curve_type=0, body_curve_amount=0.94, body_length=330, head_length=34, dorsal_type=0, dorsal_texture_type=1, dorsal_length=82, wing_length=65, wing_type=0, wing_texture_type=0, pelvic_length=50, pelvic_type=0, pelvic_texture_type=0, anal_start=21, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_length=80, pattern_type=0, finlet_type=0, eye_size=12, tail_type=3, dorsal_start=16, dorsal_end=26)),
        Species("swordfish", (15, 90, 35), 2, 0.17, 0.08, (0.23, 0.35, 0.54), (0.29, 0.42, 0.6), (0.78, 0.85, 0.91), (),
                _p(0.17, body_curve_type=0, body_curve_amount=0.94, body_length=330, head_length=34, dorsal_type=0, dorsal_texture_type=1, dorsal_length=33, wing_length=65, wing_type=0, wing_texture_type=0, pelvic_length=50, pelvic_type=0, pelvic_texture_type=0, anal_start=21, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_length=80, pattern_type=0, finlet_type=0, eye_size=12, tail_type=2, dorsal_start=12, dorsal_end=16)),
        Species("john-dory", (0.5, 4, 1.5), 0.38, 0.7, 0.32, (0.66, 0.63, 0.38), (0.54, 0.51, 0.28), (0.16, 0.16, 0.13), ("mottle",),
                _p(0.7, body_curve_type=0, body_curve_amount=0.94, body_length=330, head_length=34, dorsal_type=0, dorsal_texture_type=1, dorsal_length=50, wing_length=65, wing_type=0, wing_texture_type=0, pelvic_length=50, pelvic_type=0, pelvic_texture_type=0, anal_start=21, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_length=80, pattern_type=0, finlet_type=0, eye_size=12, tail_type=3, dorsal_start=5, dorsal_end=24)),
        Species("thornback-ray", (3, 20, 8), 0.8, 0.4, 0.05, (0.54, 0.48, 0.35), (0.42, 0.37, 0.27), (0.85, 0.78, 0.63), (),
                _p(0.4, body_curve_type=0, body_curve_amount=0.96, body_length=300, dorsal_type=0, dorsal_texture_type=1, dorsal_length=40, dorsal_start=4, dorsal_end=28, wing_length=50, wing_type=0, wing_texture_type=0, pelvic_length=30, pelvic_type=0, pelvic_texture_type=0, anal_start=12, anal_end=29, anal_length=35, anal_type=0, anal_texture_type=1, tail_type=1, tail_length=55, pattern_type=1, pattern_scale=0.7, finlet_type=0, eye_size=10)),
        Species("sailfish", (15, 80, 35), 2, 0.17, 0.08, (0.23, 0.42, 0.6), (0.16, 0.29, 0.54), (0.66, 0.78, 0.91), (),
                _p(0.17, body_curve_type=0, body_curve_amount=0.94, body_length=330, head_length=34, dorsal_type=0, dorsal_texture_type=1, dorsal_length=132, wing_length=65, wing_type=0, wing_texture_type=0, pelvic_length=50, pelvic_type=0, pelvic_texture_type=0, anal_start=21, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_length=80, pattern_type=0, finlet_type=0, eye_size=12, tail_type=2, dorsal_start=6, dorsal_end=22)),
        Species("coral-lionfish", (0.3, 1.5, 0.7), 0.3, 0.3, 0.14, (0.72, 0.27, 0.18), (0.91, 0.85, 0.78), (0.94, 0.89, 0.83), ("stripes",),
                _p(0.3, body_curve_type=0, body_curve_amount=0.94, body_length=330, head_length=34, dorsal_type=0, dorsal_texture_type=1, dorsal_length=165, wing_length=65, wing_type=0, wing_texture_type=0, pelvic_length=50, pelvic_type=0, pelvic_texture_type=0, anal_start=21, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_length=80, pattern_type=0, finlet_type=0, eye_size=12, tail_type=3, dorsal_start=7, dorsal_end=22)),
        Species("sunray", (8, 60, 22), 1.6, 0.4, 0.05, (0.16, 0.23, 0.29), (0.85, 0.86, 0.88), (0.91, 0.93, 0.96), (),
                _p(0.4, body_curve_type=0, body_curve_amount=0.96, body_length=300, dorsal_type=0, dorsal_texture_type=1, dorsal_length=40, dorsal_start=4, dorsal_end=28, wing_length=50, wing_type=0, wing_texture_type=0, pelvic_length=30, pelvic_type=0, pelvic_texture_type=0, anal_start=12, anal_end=29, anal_length=35, anal_type=0, anal_texture_type=1, tail_type=1, tail_length=55, pattern_type=1, pattern_scale=0.7, finlet_type=0, eye_size=10)),
        Species("sea-dragon", (0.05, 0.4, 0.15), 0.25, 0.1, 0.05, (0.78, 0.72, 0.22), (0.66, 0.6, 0.16), (0.91, 0.88, 0.6), (),
                _p(0.1, body_curve_type=0, body_curve_amount=0.94, body_length=330, head_length=34, dorsal_type=0, dorsal_texture_type=1, dorsal_length=20, wing_length=65, wing_type=0, wing_texture_type=0, pelvic_length=50, pelvic_type=0, pelvic_texture_type=0, anal_start=21, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_length=80, pattern_type=0, finlet_type=0, eye_size=12, tail_type=3, dorsal_start=16, dorsal_end=26)),
        Species("draugr-eel", (4, 25, 10), 1.7, 0.09, 0.04, (0.54, 0.6, 0.56), (0.42, 0.48, 0.45), (0.82, 0.88, 0.83), ("ghost",),
                _p(0.09, body_curve_type=0, body_curve_amount=0.97, body_length=420, head_length=22, dorsal_type=0, dorsal_texture_type=0, dorsal_length=18, dorsal_start=7, dorsal_end=28, wing_length=25, wing_type=0, wing_texture_type=0, pelvic_length=8, pelvic_type=0, pelvic_texture_type=0, anal_start=14, anal_end=30, anal_length=16, anal_type=0, anal_texture_type=0, tail_type=1, tail_length=22, pattern_type=0, finlet_type=0, eye_size=8, nose_height=0),
                (0.8, 1, 0.9)),
        Species("greenland-shark", (30, 200, 80), 2, 0.17, 0.08, (0.35, 0.38, 0.42), (0.29, 0.32, 0.35), (0.66, 0.69, 0.72), (),
                _p(0.17, body_curve_type=0, body_curve_amount=0.94, body_length=330, head_length=34, dorsal_type=0, dorsal_texture_type=1, dorsal_length=26, wing_length=65, wing_type=0, wing_texture_type=0, pelvic_length=50, pelvic_type=0, pelvic_texture_type=0, anal_start=21, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_length=80, pattern_type=0, finlet_type=0, eye_size=12, tail_type=3, dorsal_start=11, dorsal_end=15)),
        Species("opah", (8, 70, 25), 1, 0.75, 0.34, (0.29, 0.42, 0.6), (0.85, 0.29, 0.23), (0.91, 0.93, 0.96), (),
                _p(0.75, body_curve_type=0, body_curve_amount=0.94, body_length=330, head_length=34, dorsal_type=0, dorsal_texture_type=1, dorsal_length=50, wing_length=65, wing_type=0, wing_texture_type=0, pelvic_length=50, pelvic_type=0, pelvic_texture_type=0, anal_start=21, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_length=80, pattern_type=0, finlet_type=0, eye_size=12, tail_type=2, dorsal_start=10, dorsal_end=19)),
        Species("grouper", (5, 40, 15), 0.9, 0.34, 0.15, (0.48, 0.42, 0.32), (0.35, 0.31, 0.23), (0.85, 0.78, 0.63), (),
                _p(0.34, body_curve_type=0, body_curve_amount=0.94, body_length=330, head_length=34, dorsal_type=0, dorsal_texture_type=1, dorsal_length=23, wing_length=65, wing_type=0, wing_texture_type=0, pelvic_length=50, pelvic_type=0, pelvic_texture_type=0, anal_start=21, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_length=80, pattern_type=0, finlet_type=0, eye_size=12, tail_type=3, dorsal_start=10, dorsal_end=24)),
        Species("barracuda", (3, 25, 9), 1.2, 0.12, 0.05, (0.54, 0.59, 0.63), (0.42, 0.46, 0.5), (0.88, 0.9, 0.92), ("tusks",),
                _p(0.12, body_curve_type=0, body_curve_amount=0.94, body_length=330, head_length=34, dorsal_type=0, dorsal_texture_type=1, dorsal_length=20, wing_length=65, wing_type=0, wing_texture_type=0, pelvic_length=50, pelvic_type=0, pelvic_texture_type=0, anal_start=21, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_length=80, pattern_type=0, finlet_type=0, eye_size=12, tail_type=2, dorsal_start=18, dorsal_end=22, has_teeth=1, mouth_size=11)),
        Species("jormungand-thread", (8, 40, 20), 2, 0.1, 0.05, (0.16, 0.35, 0.29), (0.78, 0.66, 0.22), (0.47, 0.88, 0.69), ("stripes",),
                _p(0.1, body_curve_type=0, body_curve_amount=0.97, body_length=420, head_length=22, dorsal_type=0, dorsal_texture_type=0, dorsal_length=18, dorsal_start=7, dorsal_end=28, wing_length=25, wing_type=0, wing_texture_type=0, pelvic_length=8, pelvic_type=0, pelvic_texture_type=0, anal_start=14, anal_end=30, anal_length=16, anal_type=0, anal_texture_type=0, tail_type=1, tail_length=22, pattern_type=0, finlet_type=0, eye_size=8, nose_height=0),
                (0.9, 0.8, 0.3)),
        Species("kraken-whelp", (10, 60, 25), 1.2, 0.3, 0.14, (0.48, 0.23, 0.35), (0.35, 0.16, 0.27), (0.91, 0.66, 0.75), ("mottle",),
                _p(0.3, body_curve_type=0, body_curve_amount=0.94, body_length=330, head_length=34, dorsal_type=0, dorsal_texture_type=1, dorsal_length=20, wing_length=65, wing_type=0, wing_texture_type=0, pelvic_length=50, pelvic_type=0, pelvic_texture_type=0, anal_start=21, anal_end=28, anal_length=45, anal_type=0, anal_texture_type=0, tail_length=80, pattern_type=0, finlet_type=0, eye_size=12, tail_type=3, dorsal_start=16, dorsal_end=29)),
        Species("hel-halibut", (40, 200, 90), 1.8, 0.5, 0.05, (0.91, 0.89, 0.85), (0.82, 0.8, 0.75), (0.16, 0.16, 0.19), ("ghost",),
                _p(0.5, body_curve_type=0, body_curve_amount=0.96, body_length=300, dorsal_type=0, dorsal_texture_type=1, dorsal_length=40, dorsal_start=4, dorsal_end=28, wing_length=50, wing_type=0, wing_texture_type=0, pelvic_length=30, pelvic_type=0, pelvic_texture_type=0, anal_start=12, anal_end=29, anal_length=35, anal_type=0, anal_texture_type=1, tail_type=1, tail_length=55, pattern_type=1, pattern_scale=0.7, finlet_type=0, eye_size=10)),
        # ---- wave 2 species, end
        Species("brook-minnow", (0.01, 0.06, 0.03), 0.09, 0.17, 0.06, (0.62, 0.66, 0.5), (0.7, 0.62, 0.4), (0.92, 0.5, 0.25), (),
                _p(0.17, body_curve_type=0, body_curve_amount=0.95, body_length=340, dorsal_type=0, dorsal_texture_type=0, dorsal_length=30,
                   dorsal_start=14, dorsal_end=20, wing_length=45, wing_type=0, wing_texture_type=0, pelvic_length=30, pelvic_type=0, pelvic_texture_type=0,
                   anal_start=21, anal_end=28, anal_length=30, anal_type=0, anal_texture_type=0, tail_type=2, tail_length=70, pattern_type=0, finlet_type=0, eye_size=14)),
        Species("lake-crayfish", (0.03, 0.18, 0.08), 0.12, 0.2, 0.12, (0.5, 0.26, 0.18), (0.4, 0.2, 0.14), (0.85, 0.4, 0.22), ("barbel",),
                _p(0.2, body_curve_type=0, body_curve_amount=0.94, body_length=330, head_length=40, mouth_size=7, jaw_size=0.9, nose_height=10, dorsal_type=1, dorsal_texture_type=1,
                   dorsal_length=40, dorsal_start=21, dorsal_end=28, wing_length=60, wing_type=0, wing_texture_type=1, pelvic_length=40, pelvic_type=0, pelvic_texture_type=0,
                   anal_start=22, anal_end=29, anal_length=40, anal_type=0, anal_texture_type=1, tail_type=2, tail_length=70, pattern_type=2, pattern_scale=1.1, finlet_type=0, eye_size=9)),
    )
}

SLUGS = tuple(SPECIES)

#: texture layout per species (skin.Skin fields); `fish_for` varies bars / density / tint per catch
SKINS = {
    "pale-fish": dict(kind="plain", scales=1.0),
    "reed-perch": dict(kind="bars", bars=6, lateral=False, scales=1.0),
    "blind-cavefish": dict(kind="plain", scales=0.3, lateral=False),
    "skerry-herring": dict(kind="plain", scales=1.1),
    "silver-bream": dict(kind="plain", scales=1.0),
    "mottled-eel": dict(kind="blotch", density=1.3, lateral=False, scales=0.0),
    "grey-cod": dict(kind="blotch", density=1.0, scales=0.6),
    "frost-char": dict(kind="spots", density=1.0, scales=0.7),
    "star-fin": dict(kind="stars", density=1.0, lateral=False, scales=0.5),
    "shardfin": dict(kind="stars", density=0.9, lateral=False, scales=0.8),
    "tusk-pike": dict(kind="spots", density=1.3, scales=0.5),
    "loki-salmon": dict(kind="blotch", density=0.7, scales=0.9),
    "soulfish": dict(kind="ghost", lateral=False, scales=0.4),
    "mire-loach": dict(kind="blotch", density=1.2, lateral=False, scales=0.0),
    "rill-trout": dict(kind="spots", density=1.4, scales=0.6),
    "moss-carp": dict(kind="blotch", density=0.5, scales=1.6),
    "rime-grayling": dict(kind="spots", density=0.9, scales=0.7),
    "rime-smelt": dict(kind="plain", scales=0.5),
    "gloam-barbel": dict(kind="plain", scales=0.5, lateral=False),
    "root-lamprey": dict(kind="blotch", density=0.6, lateral=False, scales=0.0),
    "kelp-pollock": dict(kind="plain", scales=0.8),
    "wave-mackerel": dict(kind="bars", bars=10, lateral=False, scales=0.6),
    "sea-ling": dict(kind="blotch", density=0.9, scales=0.4),
    "storm-tuna": dict(kind="plain", scales=0.7),
    "ash-gar": dict(kind="spots", density=1.6, scales=0.9),
    "moonscale": dict(kind="stars", density=0.6, lateral=False, scales=1.3),
    "ember-sturgeon": dict(kind="spots", density=1.7, scales=0.2),
    "cinder-wyrm": dict(kind="stars", density=0.9, lateral=False, scales=0.3),
    "glass-shiner": dict(kind="stars", density=0.7, lateral=False, scales=0.4),
    "jewel-bleak": dict(kind="stars", density=1.0, lateral=False, scales=0.9),
    "deep-wolffish": dict(kind="bars", bars=7, lateral=False, scales=0.4),
    "fathom-cod": dict(kind="blotch", density=1.0, scales=0.6),
    "silt-flounder": dict(kind="spots", density=1.1, lateral=False, scales=0.4),
    "hammer-shark": dict(kind="plain", lateral=False, scales=0.0),
    "gloom-eye": dict(kind="stars", density=0.8, lateral=False, scales=0.3),
    "lagoon-snapper": dict(kind="plain", lateral=False, scales=0.7),
    "reef-parrotfish": dict(kind="spots", density=0.9, lateral=False, scales=0.8),
    "glimmer-eel": dict(kind="stars", density=1.1, lateral=False, scales=0.0),
    # ---- wave 2 skins, begin
    "crucian-carp": dict(kind="plain", scales=1.5),
    "roach": dict(kind="plain", scales=1.3),
    "ruffe": dict(kind="spots", density=1.5, scales=0.6),
    "gudgeon": dict(kind="spots", density=1.3, scales=0.5),
    "bullhead": dict(kind="blotch", density=1.2, lateral=False, scales=0.0),
    "stickleback": dict(kind="bars", bars=5, lateral=False, scales=0.7),
    "tench": dict(kind="plain", scales=1.0),
    "ide": dict(kind="plain", scales=1.2),
    "zander": dict(kind="bars", bars=7, lateral=False, scales=0.8),
    "burbot": dict(kind="blotch", density=1.0, scales=0.3),
    "whitefish": dict(kind="plain", scales=1.1),
    "sun-perch": dict(kind="spots", density=1.1, lateral=False, scales=1.0),
    "wels": dict(kind="blotch", density=0.8, scales=0.0),
    "icicle-eel": dict(kind="stars", density=0.7, lateral=False, scales=0.0),
    "frostjaw": dict(kind="spots", density=0.9, scales=0.6),
    "ember-ray": dict(kind="stars", density=0.8, lateral=False, scales=0.0),
    "forge-bream": dict(kind="plain", scales=1.6),
    "sulfur-eel": dict(kind="blotch", density=1.0, lateral=False, scales=0.0),
    "gall-lumpfish": dict(kind="blotch", density=1.6, lateral=False, scales=0.0),
    "lantern-bleak": dict(kind="stars", density=1.3, lateral=False, scales=0.6),
    "wisp-fish": dict(kind="ghost", lateral=False, scales=0.3),
    "cave-eel": dict(kind="plain", scales=0.0, lateral=False),
    "mimir-carp": dict(kind="blotch", density=0.5, scales=1.6),
    "norn-trout": dict(kind="bars", bars=3, lateral=True, scales=0.8),
    "hoard-carp": dict(kind="plain", scales=1.9),
    "sprat": dict(kind="plain", scales=0.8),
    "sandeel": dict(kind="plain", scales=0.0, lateral=False),
    "dab": dict(kind="spots", density=1.0, lateral=False, scales=0.4),
    "sea-scorpion": dict(kind="blotch", density=1.4, lateral=False, scales=0.0),
    "ballan-wrasse": dict(kind="spots", density=1.0, scales=1.1),
    "grey-mullet": dict(kind="bars", bars=9, lateral=True, scales=1.2),
    "whiting": dict(kind="plain", scales=0.7),
    "pipefish": dict(kind="bars", bars=12, lateral=False, scales=0.0),
    "rockling": dict(kind="blotch", density=1.1, lateral=False, scales=0.0),
    "flying-fish": dict(kind="plain", scales=0.9),
    "haddock": dict(kind="plain", scales=0.8),
    "sand-plaice": dict(kind="spots", density=0.7, lateral=False, scales=0.0),
    "turbot": dict(kind="spots", density=1.4, lateral=False, scales=0.0),
    "dapple-skate": dict(kind="spots", density=0.6, lateral=False, scales=0.0),
    "sea-bass": dict(kind="plain", scales=1.4),
    "lumpsucker": dict(kind="spots", density=1.5, lateral=False, scales=0.0),
    "conger": dict(kind="blotch", density=0.5, lateral=False, scales=0.0),
    "cuckoo-wrasse": dict(kind="spots", density=0.8, lateral=False, scales=1.0),
    "red-gurnard": dict(kind="spots", density=0.8, lateral=False, scales=0.8),
    "tide-seahorse": dict(kind="bars", bars=8, lateral=False, scales=0.0),
    "pufferfish": dict(kind="spots", density=1.3, lateral=False, scales=0.0),
    "sun-angelfish": dict(kind="bars", bars=5, lateral=False, scales=0.9),
    "cuttlefish": dict(kind="blotch", density=1.0, lateral=False, scales=0.0),
    "ribbonfish": dict(kind="plain", scales=0.0, lateral=False),
    "triggerfish": dict(kind="spots", density=1.0, lateral=False, scales=1.0),
    "spurdog": dict(kind="spots", density=0.5, lateral=False, scales=0.0),
    "boxfish": dict(kind="spots", density=1.2, lateral=False, scales=0.0),
    "halibut": dict(kind="blotch", density=0.6, lateral=False, scales=0.0),
    "monkfish": dict(kind="blotch", density=1.2, lateral=False, scales=0.0),
    "ocean-sunfish": dict(kind="spots", density=0.4, lateral=False, scales=0.0),
    "swordfish": dict(kind="plain", scales=0.6),
    "john-dory": dict(kind="plain", scales=0.9),
    "thornback-ray": dict(kind="spots", density=1.2, lateral=False, scales=0.0),
    "sailfish": dict(kind="bars", bars=8, lateral=False, scales=0.6),
    "coral-lionfish": dict(kind="bars", bars=9, lateral=False, scales=0.0),
    "sunray": dict(kind="spots", density=0.5, lateral=False, scales=0.0),
    "sea-dragon": dict(kind="spots", density=1.1, lateral=False, scales=0.0),
    "draugr-eel": dict(kind="ghost", lateral=False, scales=0.0),
    "greenland-shark": dict(kind="spots", density=0.3, lateral=False, scales=0.0),
    "opah": dict(kind="spots", density=1.4, lateral=False, scales=0.0),
    "grouper": dict(kind="blotch", density=0.9, lateral=False, scales=0.5),
    "barracuda": dict(kind="spots", density=0.7, lateral=False, scales=0.6),
    "jormungand-thread": dict(kind="bars", bars=14, lateral=False, scales=0.4),
    "kraken-whelp": dict(kind="blotch", density=1.0, lateral=False, scales=0.0),
    "hel-halibut": dict(kind="plain", scales=0.6),
    # ---- wave 2 skins, end
    "brook-minnow": dict(kind="plain", scales=0.5),
    "lake-crayfish": dict(kind="spots", density=1.4, scales=0.2),
}

_JITTER_KEYS = ("body_length", "body_height", "dorsal_length", "wing_length", "pelvic_length", "anal_length", "tail_length")


@dataclass
class Fish:
    seed: str
    species: str | None
    kg: float | None
    length_m: float
    drawing: Drawing
    look: Look

    def mesh(self) -> Mesh:
        return lift(self.drawing, self.look)


def fish_for(species: str, seed) -> Fish:
    """A catch of `species` for `seed` (str or int): same inputs, same fish. `seed=None` is the canonical one at the median kg."""
    sp = SPECIES[species]
    if seed is None:
        rng = Rng(str_to_seed(f"{species}:canon"))
        a = generate_params(rng)
        a.update(sp.params)
        kg = sp.kg[2]
        look = sp.look
    else:
        rng = Rng(str_to_seed(f"{species}:{seed}"))
        a = generate_params(rng)
        a.update(sp.params)
        jr = Rng(str_to_seed(f"jitter:{species}:{seed}"))
        kg = jr.rndtri(*sp.kg)
        for k in _JITTER_KEYS:
            a[k] = a[k] * (1 + jr.deviate(0.07))
        a["nose_height"] = a.get("nose_height", 0) + jr.deviate(3)
        skin = sp.look.skin.varied(str_to_seed(f"skin:{species}:{seed}"), jr.rand)
        look = Look(sp.length_m * (kg / sp.kg[2]) ** (1 / 3), sp.look.flat * (1 + jr.deviate(0.08)), sp.look.palette, sp.look.features, skin)
    d = draw(a, rng)
    return Fish(str(seed), species, round(kg, 3), look.length_m, d, look)


_RANDOM_PALETTES = (
    ("#3a4a6b", "#8aa0b8", "#e6e2d0", "#c0553a", "#1a1a2e"),
    ("#2d5a2d", "#6b9b6b", "#e8d8a0", "#d4a040", "#1a3a1a"),
    ("#5c3a1e", "#b8845a", "#f0dcb0", "#7a4e2d", "#3d2817"),
    ("#0f3460", "#2e7d9b", "#c0e8f0", "#ff9a3c", "#16213e"),
    ("#4a2d6a", "#8a6ac0", "#e0d0f0", "#ffc857", "#2d1b3d"),
    ("#555555", "#9a9a8a", "#e8e8dc", "#c0553a", "#3a3a3a"),
)


def fish_from_seed(seed: str, length_m: float = 0.3) -> Fish:
    """An unconstrained fishdraw fish from the raw generator (no species): what the JS makes for the same seed string."""
    rng = Rng(str_to_seed(seed))
    a = generate_params(rng)
    pr = Rng(str_to_seed("look:" + seed))
    back, flank, belly, fin, accent = _RANDOM_PALETTES[int(pr.rand() * len(_RANDOM_PALETTES)) % len(_RANDOM_PALETTES)]
    pal = {"back": back, "flank": flank, "belly": belly, "fin": fin, "accent": accent, "iris": "#ffc857", "pupil": "#1a1a2e"}
    d = draw(a, rng)
    kind = {1: "blotch", 2: "spots", 3: "bars", 4: "stars"}.get(a["pattern_type"], "plain")
    skin = Skin(kind=kind, seed=str_to_seed("skin:" + seed), bars=4 + int(pr.rand() * 4), aspect=0.3).varied(str_to_seed("skin:" + seed), pr.rand)
    return Fish(seed, None, None, length_m, d, Look(length_m, pr.rndtri(0.3, 0.45, 0.7), pal, (), skin))
