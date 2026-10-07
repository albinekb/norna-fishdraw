"""Finishes and per-role materials: the PBR set a v2 GLB carries (numbers are Gate 3).

A finish is one gene family on any species: glossy wet to matte on every catch, and the rare shiny metallic, shimmer
(thin-film iridescence), pearlescent (sheen plus a low iridescence) and holographic (iridescence with a baked fleck of
thickness). They ride the standard glTF extensions the engine's GLB parser already reads (`KHR_materials_clearcoat`,
`_sheen`, `_iridescence`, `_emissive_strength`), applied per role, so only the roles that need them compile them.
"""

from __future__ import annotations


#: role -> palette key for flat-coloured roles
FLAT = {"iris": "iris", "pupil": "pupil", "sclera": "sclera", "glint": "glint", "lid": "lid", "tooth": "tooth", "mouth": "mouth", "jaw": "jaw", "arm": "arm", "sucker": "sucker", "stalk": "stalk", "bulb": "bulb", "barbel": "barbel", "spike": "spike", "plate": "plate"}
ORDER = ("flank", "under", "fin", "lid", "sclera", "iris", "pupil", "glint", "tooth", "mouth", "jaw", "arm", "sucker", "stalk", "bulb", "barbel", "spike", "plate")
DOUBLE_SIDED = {"fin", "barbel"}  # thin roles: both faces draw (frill, sail and wing join them when a plan makes them)
BODY_ROLES = {"flank", "under", "lid", "jaw", "arm"}
METAL = {"gold": (1.0, 0.82, 0.32), "silver": (0.9, 0.92, 0.96), "copper": (0.93, 0.55, 0.38)}


def _lerp(a, b, t):
    return a + (b - a) * t


def material(role: str, g: dict, textured: bool, glow_tex: bool) -> dict:
    """-> {base: [r,g,b,a] factor (linear), metallic, roughness, emissive: (rgb, strength)|None, blend, double, ext: {...}}"""
    fin = g.get("finish", {"kind": "none", "gloss": 0.5})
    kind, gloss = fin["kind"], fin.get("gloss", 0.5)
    x = fin.get("x", 1.0)
    m = {"base": [1.0, 1.0, 1.0, 1.0], "metallic": 0.0, "roughness": 0.85, "emissive": None, "blend": False, "double": role in DOUBLE_SIDED, "ext": {}}
    if role in BODY_ROLES or role == "fin":
        m["roughness"] = round(_lerp(0.9, 0.3, gloss), 3)
        if gloss > 0.65 and role != "fin":
            m["ext"]["KHR_materials_clearcoat"] = {"clearcoatFactor": round(0.35 + 0.4 * gloss, 3), "clearcoatRoughnessFactor": 0.2}
        if kind == "shiny":
            c = METAL[fin.get("metal", "gold")]
            m.update(metallic=round(0.8 + 0.2 * x, 3), roughness=0.3)
            m["base"] = [*c, 1.0]
        elif kind == "shimmer":
            m.update(metallic=0.2, roughness=0.35)
            m["ext"]["KHR_materials_iridescence"] = {"iridescenceFactor": round(0.6 + 0.4 * x, 3), "iridescenceIor": 1.3, "iridescenceThicknessMinimum": 250.0, "iridescenceThicknessMaximum": 650.0}
        elif kind == "pearl":
            m.update(metallic=0.0, roughness=0.4)
            m["ext"]["KHR_materials_iridescence"] = {"iridescenceFactor": 0.35, "iridescenceIor": 1.3, "iridescenceThicknessMinimum": 150.0, "iridescenceThicknessMaximum": 450.0}
            m["ext"]["KHR_materials_sheen"] = {"sheenColorFactor": [1.0, 1.0, 1.0], "sheenRoughnessFactor": 0.4}
        elif kind == "holo":
            m.update(metallic=0.3, roughness=0.3)
            m["ext"]["KHR_materials_iridescence"] = {"iridescenceFactor": 1.0, "iridescenceIor": 1.3, "iridescenceThicknessMinimum": 100.0, "iridescenceThicknessMaximum": 800.0, "holoFleck": True}
        elif kind == "ghost":
            m["blend"] = True
            m["base"][3] = 0.55
    elif role in ("iris", "sclera", "glint"):
        m["roughness"] = 0.25
        m["ext"]["KHR_materials_clearcoat"] = {"clearcoatFactor": 0.6, "clearcoatRoughnessFactor": 0.1}
    if role == "glint":
        m["emissive"] = ([1.0, 1.0, 1.0], 1.0)
    if role == "bulb" and g.get("lure_glow", True):
        m["emissive"] = ([0.4, 1.0, 0.9], 2.0 + 3.0 * g.get("glow", 0.5))
        m["roughness"] = 0.3
    if glow_tex and role in ("flank", "under"):
        m["emissive"] = ([1.0, 1.0, 1.0], 2.0 + 3.0 * g.get("glow", 0.5))
    return m
