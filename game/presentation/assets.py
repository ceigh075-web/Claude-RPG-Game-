"""External pixel-art assets (Pixel Crawler free pack by Anokolisa, see ASSETS.md).

Sprites are named in MANIFEST and cut from atlases either by connected-component index or by an
approximate rectangle that is then trimmed to the largest sprite inside it (so neighbours never leak in).
Everything is loaded lazily and cached. If an asset is missing the caller falls back to procedural art.
"""
import os

import pygame

from ..core.paths import BUNDLE_ROOT

ROOT = os.path.join(BUNDLE_ROOT, "assets", "pixel_crawler")
_cache = {}
_comp_cache = {}

TREES = "Environment/Props/Static/Trees/"
VEG = "Environment/Props/Static/Vegetation.png"
ROCKS = "Environment/Props/Static/Rocks.png"
IPROPS = "Environment/Structures/Buildings/Interior/Interior_Props_01.png"
FURN = "Environment/Props/Static/Furniture.png"
BPROPS = "Environment/Structures/Buildings/Props.png"
FARM = "Environment/Props/Static/Farm.png"
WOOD = "Weapons/Wood/Wood.png"

# name -> ("idx", atlas, gap, index) | ("rect", atlas, (x, y, w, h)) | ("raw", atlas, (x, y, w, h))
MANIFEST = {
    # trees (deciduous, seasonal) - Model_01 Size_02 cells
    "tree_green": ("idx", TREES + "Model_01/Size_02.png", 2, 0),
    "tree_yellow": ("idx", TREES + "Model_01/Size_02.png", 2, 1),
    "tree_dead": ("idx", TREES + "Model_01/Size_02.png", 2, 2),
    "tree_snow": ("idx", TREES + "Model_01/Size_02.png", 2, 3),
    "tree_orange": ("idx", TREES + "Model_01/Size_02.png", 2, 10),
    "tree_gold": ("idx", TREES + "Model_01/Size_02.png", 2, 11),
    "tree_big_green": ("rect", TREES + "Model_01/Size_03.png", (0, 0, 52, 96)),
    "tree_big_yellow": ("rect", TREES + "Model_01/Size_03.png", (52, 0, 46, 96)),
    "tree_big_orange": ("rect", TREES + "Model_01/Size_03.png", (0, 96, 52, 96)),
    "tree_big_snow": ("rect", TREES + "Model_01/Size_03.png", (140, 96, 52, 96)),
    # conifers and pines
    "pine_teal": ("idx", TREES + "Model_02/Size_03.png", 2, 0),
    "pine_green": ("idx", TREES + "Model_02/Size_03.png", 2, 4),
    "pine_dark": ("idx", TREES + "Model_02/Size_03.png", 2, 3),
    "pine_dead": ("idx", TREES + "Model_02/Size_03.png", 2, 2),
    "tallpine_green": ("idx", TREES + "Model_03/Size_02.png", 2, 0),
    "tallpine_olive": ("idx", TREES + "Model_03/Size_02.png", 2, 1),
    "tallpine_brown": ("idx", TREES + "Model_03/Size_02.png", 2, 8),
    "tallpine_red": ("idx", TREES + "Model_03/Size_02.png", 2, 9),
    "sapling_green": ("idx", TREES + "Model_03/Size_02.png", 2, 2),
    "sapling_brown": ("idx", TREES + "Model_03/Size_02.png", 2, 10),
    "stump": ("rect", TREES + "Model_01/Size_03.png", (192, 0, 16, 30)),
    # bushes and plants
    "bush_green": ("idx", VEG, 1, 4), "bush_yellow": ("idx", VEG, 1, 5), "bush_orange": ("idx", VEG, 1, 6),
    "bush_red": ("idx", VEG, 1, 7), "bush_small": ("idx", VEG, 1, 8),
    "shrub_green": ("idx", VEG, 1, 9), "shrub_yellow": ("idx", VEG, 1, 10), "shrub_orange": ("idx", VEG, 1, 11),
    "shrub_red": ("idx", VEG, 1, 12),
    "deadbush_big": ("idx", VEG, 1, 79), "deadbush": ("idx", VEG, 1, 80), "cattail": ("idx", VEG, 1, 27),
    "foxglove": ("idx", VEG, 1, 28), "foxglove2": ("idx", VEG, 1, 29), "pinkflower": ("idx", VEG, 1, 36),
"leafplant": ("rect", VEG, (64, 145, 46, 26)),
    "reeds": ("idx", VEG, 1, 26), "dryreeds": ("idx", VEG, 1, 63), "mushroom": ("idx", VEG, 1, 96),
    "mushroom_red": ("idx", VEG, 1, 102), "mushroom_blue": ("idx", VEG, 1, 103), "twigs": ("idx", VEG, 1, 104),
    "pebbles": ("idx", VEG, 1, 135), "stump_small": ("idx", VEG, 1, 93),
    "flower_orange": ("raw", VEG, (100, 368, 12, 12)), "flower_white": ("raw", VEG, (100, 384, 12, 12)),
    "flower_blue": ("raw", VEG, (100, 400, 12, 12)), "flower_yellow": ("raw", VEG, (100, 416, 12, 12)),
    # rocks, ore, crystals
    "rock_big_brown": ("idx", ROCKS, 1, 4), "rock_brown": ("idx", ROCKS, 1, 5), "rock_small_brown": ("idx", ROCKS, 1, 6),
    "rock_med_brown": ("idx", ROCKS, 1, 7), "rock_big_grey": ("idx", ROCKS, 1, 8), "rock_grey": ("idx", ROCKS, 1, 9),
    "rock_small_grey": ("idx", ROCKS, 1, 10), "rock_med_grey": ("idx", ROCKS, 1, 11),
    "rock_big_dark": ("idx", ROCKS, 1, 56), "rock_dark": ("idx", ROCKS, 1, 57), "rock_small_dark": ("idx", ROCKS, 1, 58),
    "rock_med_dark": ("idx", ROCKS, 1, 59),
    "crystal_big": ("idx", ROCKS, 1, 106), "crystal_small": ("idx", ROCKS, 1, 110), "crystal_tiny": ("idx", ROCKS, 1, 111),
    # crafting stations and fire
    "anvil": ("rect", "Environment/Structures/Stations/Anvil/Anvil.png", (0, 26, 62, 46)),
    "furnace": ("rect", "Environment/Structures/Stations/Furnace/Furnace.png", (46, 64, 46, 64)),
    "furnace_small": ("rect", "Environment/Structures/Stations/Furnace/Furnace.png", (0, 80, 34, 48)),
    "workbench": ("rect", "Environment/Structures/Stations/Workbench/Workbench.png", (0, 76, 34, 38)),
    "spit": ("rect", "Environment/Structures/Stations/Cooking Station/Cooker/Cooker_01.png", (0, 0, 64, 64)),
    "stove": ("rect", IPROPS, (114, 0, 32, 48)),
    "alchemy": ("rect", "Environment/Structures/Stations/Alchemy/Alchemy_Table_01-Sheet.png", (0, 30, 32, 34)),
    # furniture / interior props
    "bed": ("rect", IPROPS, (0, 292, 32, 56)), "bed_double": ("rect", IPROPS, (32, 292, 48, 56)),
    "table_long": ("rect", IPROPS, (0, 0, 64, 28)), "table_round": ("rect", IPROPS, (78, 4, 40, 40)),
    "table": ("rect", IPROPS, (110, 64, 38, 30)), "desk": ("rect", IPROPS, (146, 74, 30, 24)),
    "chair": ("rect", IPROPS, (64, 4, 14, 22)), "bench": ("rect", IPROPS, (128, 293, 48, 22)),
    "bathtub": ("rect", IPROPS, (128, 144, 48, 30)), "sink_counter": ("rect", IPROPS, (112, 224, 98, 34)),
    "oven_brick": ("rect", IPROPS, (382, 44, 50, 100)), "plant_pot": ("rect", IPROPS, (16, 350, 16, 34)),
    "plants_pots": ("rect", IPROPS, (32, 352, 48, 32)), "rug_green": ("rect", IPROPS, (336, 336, 48, 48)),
    "rug_dark": ("rect", IPROPS, (384, 336, 48, 48)), "window": ("rect", IPROPS, (66, 174, 28, 34)),
    "trophy_wolf": ("idx", IPROPS, 1, 3), "trophy_bear": ("idx", IPROPS, 1, 2), "broom": ("idx", IPROPS, 1, 62),
    "barrel": ("idx", FURN, 0, 16), "pot": ("idx", FURN, 0, 15), "jar": ("idx", FURN, 0, 18),
    "bucket_water": ("idx", FURN, 0, 5), "crate_stack": ("idx", FURN, 0, 14),
    "shelf": ("rect", FURN, (0, 96, 32, 48)), "wardrobe": ("rect", FURN, (0, 46, 30, 50)),
    "counter": ("rect", FURN, (32, 120, 48, 24)), "dresser": ("rect", FURN, (48, 22, 32, 26)),
    "door_wood": ("rect", BPROPS, (100, 24, 24, 42)), "door_iron": ("rect", BPROPS, (132, 24, 26, 42)),
    "door_arch": ("rect", BPROPS, (164, 22, 22, 44)), "window_arch": ("rect", BPROPS, (100, 62, 24, 34)),
    "window_square": ("rect", BPROPS, (132, 98, 24, 26)), "window_shutter": ("rect", BPROPS, (36, 96, 24, 30)),
    "chimney": ("rect", BPROPS, (2, 70, 28, 56)), "flowerbox": ("rect", BPROPS, (50, 154, 30, 18)),
    "bench_out": ("rect", BPROPS, (82, 160, 60, 32)), "fence": ("rect", BPROPS, (22, 174, 36, 20)),
    "banner_red": ("idx", "Environment/Props/Static/Dungeon_Props.png", 1, 14),
    "banner_blue": ("idx", "Environment/Props/Static/Dungeon_Props.png", 1, 15),
    "banner_green": ("idx", "Environment/Props/Static/Dungeon_Props.png", 1, 16),
    "scarecrow": ("rect", FARM, (240, 32, 32, 50)), "crate_crops": ("rect", FARM, (160, 0, 18, 30)),
    # weapon silhouettes (wood; recoloured per ore at runtime)
    "w_sword": ("idx", WOOD, 0, 0), "w_warhammer": ("idx", WOOD, 0, 1), "w_arrow": ("idx", WOOD, 0, 2),
    "w_spear": ("idx", WOOD, 0, 4), "w_wand": ("idx", WOOD, 0, 5), "w_shield": ("idx", WOOD, 0, 7),
    "w_dagger": ("idx", WOOD, 0, 8), "w_axe": ("idx", WOOD, 0, 9), "w_staff": ("idx", WOOD, 0, 11),
    "w_pickaxe": ("idx", WOOD, 0, 13), "w_mallet": ("idx", WOOD, 0, 14), "w_sickle": ("idx", WOOD, 0, 15),
    "w_bow": ("idx", WOOD, 0, 16),
}


def available():
    return os.path.isdir(ROOT)


def image(rel):
    key = ("img", rel)
    if key not in _cache:
        path = os.path.join(ROOT, rel)
        img = pygame.image.load(path)
        if pygame.display.get_surface():
            img = img.convert_alpha()
        _cache[key] = img
    return _cache[key]


def components(rel, gap=1):
    key = (rel, gap)
    if key not in _comp_cache:
        img = image(rel)
        mask = pygame.mask.from_surface(img, 1)
        boxes = [pygame.Rect(r) for r in mask.get_bounding_rects() if r[2] * r[3] >= 6]
        merged = True
        while merged:
            merged = False
            out = []
            while boxes:
                b = boxes.pop()
                for i, o in enumerate(out):
                    if b.inflate(gap * 2, gap * 2).colliderect(o):
                        out[i] = o.union(b)
                        merged = True
                        break
                else:
                    out.append(b)
            boxes = out
        boxes.sort(key=lambda r: (r.y // 8, r.x))
        _comp_cache[key] = boxes
    return _comp_cache[key]


def _trim_largest(surf):
    """Keep only the largest connected opaque blob (plus anything touching its bbox tightly)."""
    mask = pygame.mask.from_surface(surf, 1)
    comps = mask.connected_components(6)
    if not comps:
        return surf
    big = max(comps, key=lambda m: m.count())
    rect = pygame.Rect(big.get_bounding_rects()[0])
    for r in big.get_bounding_rects()[1:]:
        rect.union_ip(r)
    # include small pieces fully inside the main bbox (details separated by transparent gaps)
    keep = pygame.mask.Mask(surf.get_size())
    for m in comps:
        rs = m.get_bounding_rects()
        if m is big or (rs and rect.contains(rs[0])):
            keep.draw(m, (0, 0))
    out = pygame.Surface(rect.size, pygame.SRCALPHA)
    src = surf.subsurface(rect)
    kmask = keep.overlap_mask(keep, (0, 0))
    for y in range(rect.h):
        for x in range(rect.w):
            if kmask.get_at((rect.x + x, rect.y + y)):
                out.set_at((x, y), src.get_at((x, y)))
    return out


def sprite(name):
    """A named sprite from the manifest (cached). Raises KeyError for unknown names."""
    key = ("spr", name)
    if key in _cache:
        return _cache[key]
    spec = MANIFEST[name]
    kind, rel = spec[0], spec[1]
    img = image(rel)
    if kind == "idx":
        rect = components(rel, spec[2])[spec[3]]
        out = img.subsurface(rect).copy()
    elif kind == "raw":
        out = img.subsurface(pygame.Rect(spec[2]).clip(img.get_rect())).copy()
    else:
        sub = img.subsurface(pygame.Rect(spec[2]).clip(img.get_rect())).copy()
        out = _trim_largest(sub)
    _cache[key] = out
    return out


def frames(rel, fw, fh=None):
    """Split a horizontal animation sheet into frames."""
    key = ("frames", rel, fw, fh)
    if key not in _cache:
        img = image(rel)
        fh = fh or img.get_height()
        _cache[key] = [img.subsurface((i * fw, 0, fw, fh)).copy() for i in range(img.get_width() // fw)]
    return _cache[key]


def patch(rel, rect):
    """A raw rectangular patch (textures)."""
    key = ("patch", rel, tuple(rect))
    if key not in _cache:
        _cache[key] = image(rel).subsurface(rect).copy()
    return _cache[key]


# ---------------------------------------------------------------------- colour utilities
def luminance(c):
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


def ramp(base, n=5):
    """A dark-to-light colour ramp around `base` (shading for recolours)."""
    out = []
    for i in range(n):
        f = 0.45 + 0.9 * i / (n - 1)
        out.append(tuple(max(0, min(255, int(v * f + (30 * (i - n // 2) if f > 1 else 0)))) for v in base))
    return out


def recolor_lum(surf, base, keep=lambda c: False, lo=40, hi=230):
    """Map every pixel's luminance onto a ramp built from `base`, except pixels where keep(rgb) is True."""
    r = ramp(base, 6)
    out = surf.copy()
    w, h = out.get_size()
    for y in range(h):
        for x in range(w):
            c = out.get_at((x, y))
            if c.a == 0 or keep((c.r, c.g, c.b)):
                continue
            L = luminance(c)
            i = int(max(0, min(5, (L - lo) / max(1, hi - lo) * 6)))
            out.set_at((x, y), (*r[i], c.a))
    return out


def tint(surf, color, amount=0.5):
    out = surf.copy()
    ov = pygame.Surface(out.get_size(), pygame.SRCALPHA)
    ov.fill((*color, int(255 * amount)))
    out.blit(ov, (0, 0), special_flags=pygame.BLEND_RGBA_MULT if amount >= 1 else 0)
    if amount < 1:
        base = surf.copy()
        mask = pygame.mask.from_surface(surf, 1).to_surface(setcolor=(*color, int(255 * amount)), unsetcolor=(0, 0, 0, 0))
        base.blit(mask, (0, 0))
        return base
    return out
