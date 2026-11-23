"""Environment art built from the Pixel Crawler tilesets.

Ground textures are taken from the pack and *tinted* to each biome's palette (the existing per-biome colours
in art.BIOME_GROUND stay the source of truth), so every region keeps its identity while gaining the pack's
hand-drawn texture. Transitions between ground types get organic overhanging edges, water is animated and
shorelines get foam. Everything falls back to the procedural art when the asset folder is missing.
"""
import random

import pygame

from ..world import mapgen as mg
from . import assets

FLOORS = "Environment/Tilesets/Floors_Tiles.png"
WATER = "Environment/Tilesets/Water_tiles.png"
T = 16

# texture name -> list of 16x16 source rects
TEX = {
    "grass": [(16 + 16 * (i % 3), 160 + 16 * (i // 3)) for i in range(6)],
    "cobble": [(96 + 16 * (i % 3), 160 + 16 * (i // 3)) for i in range(6)],
    "dirt": [(176 + 16 * (i % 3), 160 + 16 * (i // 3)) for i in range(6)],
    "brick": [(256 + 16 * (i % 3), 16 + 16 * (i // 3)) for i in range(9)],
    "snow": [(16 * (i % 5), 352 + 16 * (i // 5)) for i in range(10)],
    "sand": [(80 + 16 * (i % 5), 352 + 16 * (i // 5)) for i in range(10)],
}
# biome -> (ground texture, alt texture, path texture)
BIOME_TEX = {
    "grassland": ("grass", "grass", "dirt"), "forest": ("grass", "dirt", "dirt"), "hills": ("grass", "dirt", "dirt"),
    "mountain": ("cobble", "dirt", "dirt"), "snow": ("snow", "snow", "snow"), "desert": ("sand", "sand", "dirt"),
    "coast": ("sand", "grass", "dirt"), "swamp": ("grass", "dirt", "dirt"), "canyon": ("dirt", "dirt", "sand"),
    "volcanic": ("dirt", "cobble", "cobble"), "moor": ("grass", "dirt", "dirt"), "ruins": ("grass", "cobble", "cobble"),
    "cave": ("cobble", "cobble", "dirt"), "crystal": ("snow", "cobble", "cobble"), "interior": ("dirt", "dirt", "dirt"),
}
PRIORITY = {mg.GROUND: 3, mg.ALT: 2.5, mg.PATH: 2, mg.FIELD: 2, mg.PLAZA: 1, mg.WATER: 0}
_cache = {}
_ok = None


def enabled():
    global _ok
    if _ok is None:
        try:
            _ok = assets.available() and assets.image(FLOORS) is not None and assets.image(WATER) is not None
        except (FileNotFoundError, pygame.error):
            _ok = False
    return _ok


def _mean(surf):
    w, h = surf.get_size()
    tot = [0, 0, 0]
    n = 0
    for y in range(h):
        for x in range(w):
            c = surf.get_at((x, y))
            if c.a:
                tot[0] += c.r
                tot[1] += c.g
                tot[2] += c.b
                n += 1
    return [v / max(1, n) for v in tot]


def tinted(src, target, contrast=1.0):
    """Shift a texture's average colour onto `target` while keeping its detail (and optionally boosting it)."""
    m = _mean(src)
    out = src.copy()
    w, h = out.get_size()
    for y in range(h):
        for x in range(w):
            c = out.get_at((x, y))
            if not c.a:
                continue
            px = []
            for i, v in enumerate((c.r, c.g, c.b)):
                d = (v - m[i]) * contrast
                px.append(max(0, min(255, int(target[i] + d * (target[i] / max(30.0, m[i]))))))
            out.set_at((x, y), (*px, c.a))
    return out


def texture(name, variant, color, contrast=1.0):
    key = ("tex", name, variant % len(TEX[name]), tuple(color), contrast)
    s = _cache.get(key)
    if s is None:
        x, y = TEX[name][variant % len(TEX[name])]
        src = assets.image(FLOORS).subsurface((x, y, T, T)).copy()
        s = tinted(src, color, contrast)
        _cache[key] = s
    return s


def ground(tid, biome, variant, palette, base_colors, path_color):
    """Tile surface for ground-like tiles, or None to let the procedural art draw it."""
    g_tex, a_tex, p_tex = BIOME_TEX.get(biome, BIOME_TEX["grassland"])
    g, alt = base_colors
    if tid == mg.GROUND:
        return texture(g_tex, variant * 2 + 1, g)
    if tid == mg.ALT:
        return texture(a_tex, variant * 2, alt, 1.1)
    if tid == mg.PATH:
        return texture(p_tex, variant, path_color, 1.1)
    if tid == mg.PLAZA:
        col = (150, 146, 138)
        if palette and "wall" in palette:
            col = tuple(int(0.7 * a + 0.3 * b) for a, b in zip(col, palette["wall"]))
        return texture("brick", variant, col, 1.0)
    if tid == mg.FLOOR_STONE:
        return texture("cobble", variant, (124, 120, 126) if biome != "cave" else (86, 80, 90), 0.9)
    if tid == mg.FIELD:
        key = ("field", variant)
        s = _cache.get(key)
        if s is None:
            s = texture("dirt", variant, (112, 80, 50), 1.1).copy()
            for y in range(1, T, 4):
                pygame.draw.line(s, (84, 58, 38), (0, y), (T, y))
                pygame.draw.line(s, (134, 98, 64), (0, y + 1), (T, y + 1))
            _cache[key] = s
        return s
    return None


def water(biome, variant, frame):
    key = ("water", biome, variant % 3, frame % 4)
    s = _cache.get(key)
    if s is None:
        src = assets.image(WATER).subsurface((80 + 96 * (frame % 4), 16 + 16 * (variant % 3), T, T)).copy()
        if biome in ("swamp",):
            src = tinted(src, (58, 92, 76), 0.9)
        elif biome in ("cave", "volcanic"):
            src = tinted(src, (40, 70, 110), 1.0)
        elif biome in ("snow", "crystal"):
            src = tinted(src, (90, 150, 200), 1.0)
        s = src
        _cache[key] = s
    return s


def _edge_profile(seed, n=T):
    r = random.Random(seed)
    h = []
    v = r.uniform(1.5, 3.5)
    for _ in range(n):
        v = max(1.0, min(4.5, v + r.uniform(-1.2, 1.2)))
        h.append(int(round(v)))
    return h


def fringe(src_tile, side, seed, foam=False):
    """An overhang cut from `src_tile` with a ragged edge, to lay over a neighbouring lower-priority tile."""
    key = ("fringe", id(src_tile), side, seed % 4, foam)
    s = _cache.get(key)
    if s is None:
        s = pygame.Surface((T, T), pygame.SRCALPHA)
        prof = _edge_profile(seed % 4 * 31 + {"n": 0, "s": 1, "w": 2, "e": 3}[side])
        dark = (0, 0, 0, 70)
        for i in range(T):
            d = prof[i]
            for k in range(d + 1):
                # copy the neighbour pixels that would continue past the border
                if side == "n":     # neighbour is above: its bottom rows hang down into this tile
                    x, y = i, k
                    sx, sy = i, (T - 1 - d + k) % T
                elif side == "s":
                    x, y = i, T - 1 - k
                    sx, sy = i, (d - k) % T
                elif side == "w":
                    x, y = k, i
                    sx, sy = (T - 1 - d + k) % T, i
                else:
                    x, y = T - 1 - k, i
                    sx, sy = (d - k) % T, i
                if k == d:
                    s.set_at((x, y), (220, 235, 245, 130) if foam else dark)
                else:
                    s.set_at((x, y), src_tile.get_at((sx, sy)))
        _cache[key] = s
    return s


def draw_edges(canvas, m, art_tile, x0, y0, x1, y1, camx, camy):
    """Overlay ragged transitions where a higher-priority ground meets a lower one (grass over paths, shores)."""
    tiles = m.tiles
    W, H = m.w, m.h
    for ty in range(y0, y1):
        row = tiles[ty]
        for tx in range(x0, x1):
            tid = row[tx]
            p = PRIORITY.get(tid)
            if p is None or p >= 3:
                continue
            for side, nx, ny in (("n", tx, ty - 1), ("s", tx, ty + 1), ("w", tx - 1, ty), ("e", tx + 1, ty)):
                if not (0 <= nx < W and 0 <= ny < H):
                    continue
                nt = tiles[ny][nx]
                np_ = PRIORITY.get(nt)
                if np_ is None or np_ <= p:
                    continue
                src = art_tile(nt, (nx * 7 + ny * 13) % 4)
                canvas.blit(fringe(src, side, nx * 3 + ny * 5, foam=(tid == mg.WATER)),
                            (tx * T - camx, ty * T - camy))


# ============================================================================ buildings
WALLS = "Environment/Structures/Buildings/Walls.png"
WALL_STRIP = {"log": 0, "plank": 96, "vplank": 192, "plaster": 288, "plaster2": 384, "brick": 480}
# town specialty -> (wall strip, roof style)
TOWN_STYLE = {
    "farming": ("log", "thatch"), "military": ("brick", "slate"), "mining": ("vplank", "slate"),
    "crafting": ("plank", "shingle"), "trading": ("plaster", "tile"), "magic": ("plaster2", "shingle"),
    "mercenary": ("vplank", "tile"), "hunting": ("log", "thatch"), "frontier": ("plank", "plank"),
}
SPECIAL_ROOF = {"temple": "slate", "chapel": "slate", "palace": "tile", "mage_tower": "shingle", "barn": "plank"}


def _wall_strip(style, tint):
    key = ("wallstrip", style, tint)
    s = _cache.get(key)
    if s is None:
        img = assets.image(WALLS)
        x = WALL_STRIP[style]
        top = img.subsurface((x, 184, 96, 6)).copy()
        bottom = img.subsurface((x, 214, 96, 26)).copy()
        s = pygame.Surface((96, 32), pygame.SRCALPHA)
        s.blit(top, (0, 0))
        s.blit(bottom, (0, 6))
        if tint:
            s = tinted(s, tint, 1.0) if style.startswith("plaster") or style == "brick" else s
        _cache[key] = s
    return s


def _window(lit=False):
    s = pygame.Surface((10, 11), pygame.SRCALPHA)
    pygame.draw.rect(s, (40, 28, 22), (0, 0, 10, 11))
    pygame.draw.rect(s, (120, 84, 50), (1, 1, 8, 9))
    glass = (250, 214, 120) if lit else (126, 178, 214)
    pygame.draw.rect(s, glass, (2, 2, 6, 6))
    pygame.draw.line(s, (120, 84, 50), (5, 2), (5, 7))
    pygame.draw.line(s, (120, 84, 50), (2, 5), (7, 5))
    if not lit:
        s.set_at((3, 3), (220, 240, 250))
        s.set_at((6, 3), (220, 240, 250))
    pygame.draw.rect(s, (90, 62, 38), (0, 9, 10, 2))
    return s


def _roof(w, h, col, style, seed):
    """Top-down pitched roof: ridge across the middle, rows of shingles, lit/shaded halves, outlined."""
    r = random.Random(seed)
    s = pygame.Surface((w, h + 4), pygame.SRCALPHA)
    col = tuple(col)
    light = tuple(min(255, int(v * 1.18 + 8)) for v in col)
    dark = tuple(int(v * 0.72) for v in col)
    darker = tuple(int(v * 0.5) for v in col)
    ridge = h // 2
    pygame.draw.rect(s, light, (0, 0, w, ridge))
    pygame.draw.rect(s, col, (0, ridge, w, h + 4 - ridge))
    row_h = {"thatch": 3, "slate": 4, "tile": 4, "shingle": 4, "plank": 5}[style]
    for y in range(1, h + 4, row_h):
        base = light if y < ridge else col
        line = tuple(int(v * 0.8) for v in base)
        if style == "plank":
            pygame.draw.line(s, line, (0, y), (w, y))
            continue
        pygame.draw.line(s, line, (0, y + row_h - 1), (w, y + row_h - 1))
        if style == "thatch":
            for x in range(0, w, 2):
                if r.random() < 0.5:
                    s.set_at((x, y + r.randint(0, row_h - 1)), tuple(int(v * r.uniform(0.75, 1.15)) for v in base))
        else:
            step = {"slate": 5, "tile": 4, "shingle": 6}[style]
            off = (y // row_h) % 2 * (step // 2)
            for x in range(off, w, step):
                pygame.draw.line(s, line, (x, y), (x, y + row_h - 2))
                if style == "tile":
                    s.set_at((x + 1, y), tuple(min(255, v + 25) for v in base))
                elif r.random() < 0.15:
                    pygame.draw.line(s, tuple(int(v * 0.9) for v in base), (x + 1, y), (x + step - 1, y))
    if style == "plank":
        for x in range(0, w, 7):
            pygame.draw.line(s, dark, (x, 0), (x, h + 3))
    # ridge beam and eaves
    pygame.draw.line(s, darker, (0, ridge), (w, ridge))
    pygame.draw.line(s, light, (0, ridge - 1), (w, ridge - 1))
    pygame.draw.rect(s, dark, (0, h + 1, w, 3))
    pygame.draw.rect(s, (16, 12, 14), (0, 0, w, h + 4), 1)
    return s


def building(b, specialty, palette, lit=False):
    """Facade + roof image covering the building's footprint (plus a few px of eave shadow)."""
    key = ("bld", b["id"], b["x"], b["y"], specialty, lit)
    s = _cache.get(key)
    if s is not None:
        return s
    wstyle, rstyle = TOWN_STYLE.get(specialty, ("plank", "shingle"))
    rstyle = SPECIAL_ROOF.get(b["type"], rstyle)
    W, H = b["w"] * T, b["h"] * T
    roof_h = (b["h"] - 2) * T
    s = pygame.Surface((W, H + 3), pygame.SRCALPHA)
    wall_tint = None
    if palette and wstyle.startswith(("plaster", "brick")):
        wall_tint = tuple(int(0.55 * a + 0.45 * c) for a, c in zip((214, 200, 170), palette["wall"]))
    strip = _wall_strip(wstyle, wall_tint)
    for x in range(0, W, 96):
        s.blit(strip, (x, roof_h), (0, 0, min(96, W - x), 32))
    pygame.draw.rect(s, (16, 12, 14), (0, roof_h, W, 32), 1)
    # windows either side of the door (the door itself is a separate object sprite)
    dx = (b["door"][0] - b["x"]) * T
    win = _window(lit)
    r = random.Random(b["id"] + specialty)
    for wx in range(6, W - 10, 18):
        if abs(wx + 5 - (dx + 8)) < 16:
            continue
        s.blit(win, (wx, roof_h + 11))
        if specialty in ("farming", "trading", "magic") and r.random() < 0.6:
            pygame.draw.rect(s, (110, 70, 40), (wx - 1, roof_h + 22, 12, 3))
            for k in range(4):
                s.set_at((wx + 1 + k * 3, roof_h + 21), r.choice(((220, 80, 90), (240, 200, 80), (200, 120, 220))))
    roof_col = palette["roof"] if palette else (140, 70, 50)
    s.blit(_roof(W, roof_h, roof_col, rstyle, hash(b["id"]) & 0xffff), (0, 0))
    # chimney on homes and workplaces with fires
    if b["type"] in ("house", "inn", "smithy", "forge", "farmhouse", "longhouse", "tannery", "apothecary"):
        cx = W - 14 if dx < W // 2 else 6
        pygame.draw.rect(s, (90, 80, 78), (cx, 2, 8, 10))
        pygame.draw.rect(s, (16, 12, 14), (cx, 2, 8, 10), 1)
        pygame.draw.rect(s, (40, 34, 34), (cx + 2, 3, 4, 2))
    # banners mark military / mercenary / crown buildings
    if specialty in ("military", "mercenary") or b["type"] in ("barracks", "palace", "guild_hall", "arena"):
        bcol = (70, 90, 170) if specialty != "mercenary" else (170, 50, 40)
        for bx in (4, W - 10):
            pygame.draw.rect(s, bcol, (bx, roof_h + 2, 6, 12))
            pygame.draw.polygon(s, bcol, [(bx, roof_h + 14), (bx + 3, roof_h + 11), (bx + 6, roof_h + 14)])
            pygame.draw.line(s, (230, 200, 90), (bx + 1, roof_h + 5), (bx + 4, roof_h + 5))
    # soft shadow along the base
    sh = pygame.Surface((W, 3), pygame.SRCALPHA)
    sh.fill((0, 0, 0, 60))
    s.blit(sh, (0, H))
    _cache[key] = s
    return s


# ============================================================================ props / vegetation
TREES = {
    "grassland": ["tree_green", "tree_big_green", "tree_green", "tree_yellow"],
    "forest": ["tree_big_green", "pine_green", "tree_green", "tallpine_green"],
    "hills": ["tree_yellow", "tree_green", "tree_big_yellow", "tallpine_olive"],
    "coast": ["tree_green", "tree_big_green", "tree_yellow", "tree_green"],
    "ruins": ["tree_big_orange", "tree_dead", "tree_orange", "tree_green"],
    "moor": ["tree_dead", "pine_dead", "tallpine_brown", "tree_dead"],
    "swamp": ["tree_dead", "pine_dead", "tallpine_olive", "tree_dead"],
    "volcanic": ["pine_dead", "tree_dead", "pine_dead", "tallpine_red"],
    "snow": ["tree_snow", "pine_teal", "tree_big_snow", "pine_teal"],
    "mountain": ["pine_dark", "pine_teal", "tallpine_green", "pine_dark"],
}
ROCK_TONE = {"desert": "brown", "canyon": "brown", "volcanic": "dark", "cave": "dark", "moor": "grey", "coast": "grey",
             "hills": "brown", "snow": "grey", "mountain": "grey", "swamp": "dark", "ruins": "grey", "crystal": "dark"}
BUSH = {"berries": "bush_red", "herbs": "bush_green", "fiber": "shrub_yellow", "salt": "rock_small_grey",
        "meat": "shrub_green", "mushrooms": "mushroom_red"}


def _sp(name):
    try:
        return assets.sprite(name)
    except (KeyError, FileNotFoundError, pygame.error, ValueError):
        return None


def _snowcap(img):
    out = img.copy()
    w, h = out.get_size()
    for x in range(w):
        for y in range(h):
            c = out.get_at((x, y))
            if c.a and (c.r, c.g, c.b) != (0, 0, 0) and sum(c[:3]) > 40:
                for k in range(2):
                    if y + k < h and out.get_at((x, y + k)).a and sum(out.get_at((x, y + k))[:3]) > 40:
                        out.set_at((x, y + k), (236, 242, 250, 255))
                break
    return out


def prop(kind, variant, biome, extra=None):
    """Pack sprite for a map object, or None to keep the procedural one. Positions/collision are unchanged."""
    if not enabled():
        return None
    key = ("prop", kind, variant, biome, extra)
    if key in _cache:
        return _cache[key]
    img = None
    v = variant if isinstance(variant, int) else 0
    if kind in ("tree", "pine", "dead_tree"):
        if kind == "pine":
            pool = TREES["snow" if biome == "snow" else "mountain"]
        elif kind == "dead_tree":
            pool = ["tree_dead", "pine_dead", "tree_dead", "tallpine_brown"]
        else:
            pool = TREES.get(biome, TREES["grassland"])
        img = _sp(pool[v % len(pool)])
    elif kind == "rock":
        tone = ROCK_TONE.get(biome, "grey")
        size = ["rock_big_", "rock_med_", "rock_", "rock_med_"][v % 4]
        img = _sp(size + tone)
        if img is not None and biome in ("volcanic", "cave", "swamp", "crystal"):
            img = tinted(img, {"volcanic": (72, 62, 60), "cave": (88, 82, 92), "swamp": (84, 90, 76),
                               "crystal": (90, 96, 122)}[biome], 1.1)
        if img is not None and biome == "snow":
            img = _snowcap(img)
    elif kind == "ore_vein":
        tone = ROCK_TONE.get(biome, "grey")
        base = _sp(("rock_big_" if v % 2 else "rock_med_") + ("dark" if tone == "dark" else "grey"))
        if base is not None:
            img = base.copy()
            if extra != "depleted":
                col = tuple(extra) if extra else (180, 100, 60)
                hi = tuple(min(255, c + 70) for c in col)
                w, h = img.get_size()
                r = random.Random(v * 13 + w)
                for _ in range(max(4, w * h // 60)):
                    x, y = r.randrange(2, w - 2), r.randrange(2, h - 2)
                    if img.get_at((x, y)).a and img.get_at((x, y))[:3] != (0, 0, 0):
                        pygame.draw.polygon(img, col, [(x, y - 2), (x + 1, y), (x, y + 1), (x - 1, y)])
                        img.set_at((x, y - 1), hi)
            else:
                img = tinted(img, (88, 84, 82), 0.8)
    elif kind in ("mana_crystal_node", "crystal_spire"):
        name = "crystal_big" if kind == "crystal_spire" or extra != "depleted" else "crystal_small"
        img = _sp(name)
        if img is not None and extra == "depleted":
            img = tinted(img, (110, 110, 120), 0.6)
        elif img is not None and kind == "crystal_spire" and v % 2:
            img = tinted(img, (170, 140, 230), 1.0)
    elif kind == "bush":
        name = BUSH.get(variant, "bush_green") if extra != "depleted" else "bush_small"
        if biome in ("snow", "volcanic", "moor") and extra != "depleted":
            name = "deadbush" if variant not in BUSH else name
        img = _sp(name)
        if img is not None and extra == "depleted":
            img = tinted(img, (96, 104, 70), 0.9)
    elif kind == "barrel":
        img = _sp("barrel")
    elif kind == "crate":
        img = _sp("crate_stack" if v % 2 else "crate_crops")
    elif kind in ("anvil", "furnace", "workbench", "stove", "bed", "table", "shelf", "counter"):
        img = _sp(kind)
    elif kind == "alchemy_table":
        img = _sp("alchemy")
    _cache[key] = img
    return img


def campfire(frame):
    try:
        fr = assets.frames("Environment/Structures/Stations/Bonfire/Bonfire_01-Sheet.png", 32, 32)
    except (FileNotFoundError, pygame.error):
        return None
    return fr[frame % len(fr)]


DECOR = {
    "grassland": ["flower_yellow", "flower_white", "pinkflower", "pebbles", "leafplant", "flower_blue"],
    "forest": ["mushroom", "leafplant", "twigs", "mushroom_red", "stump_small", "flower_white"],
    "hills": ["pebbles", "flower_yellow", "flower_orange", "pebbles"],
    "coast": ["pebbles", "dryreeds", "flower_white"],
    "swamp": ["cattail", "reeds", "mushroom_blue", "leafplant"],
    "moor": ["dryreeds", "deadbush", "pebbles", "foxglove2"],
    "ruins": ["pebbles", "twigs", "flower_white", "mushroom"],
    "desert": ["pebbles", "deadbush", "dryreeds"],
    "canyon": ["pebbles", "deadbush"],
    "volcanic": ["pebbles", "rock_small_dark"],
    "snow": ["pebbles"],
    "mountain": ["pebbles", "rock_small_grey", "pebbles"],
    "cave": ["pebbles", "mushroom_blue", "crystal_tiny"],
    "crystal": ["crystal_tiny", "pebbles"],
}


def decor_layer(m, biome):
    """Deterministic non-colliding ground clutter (flowers, pebbles, mushrooms) on open ground tiles."""
    key = ("decor", id(m), m.w, m.h, biome)
    lst = _cache.get(key)
    if lst is None:
        lst = []
        names = DECOR.get(biome, [])
        taken = {(o["x"], o["y"]) for o in m.objects}
        r = random.Random(f"decor{m.w}x{m.h}{biome}{len(m.objects)}")
        if names and m.kind != "interior":
            dens = 0.03 if biome not in ("desert", "snow", "volcanic") else 0.015
            for y in range(m.h):
                for x in range(m.w):
                    if m.tiles[y][x] in (mg.GROUND, mg.ALT) and (x, y) not in taken and r.random() < dens:
                        img = _sp(r.choice(names))
                        if img is not None:
                            if biome == "snow":
                                img = tinted(img, (170, 176, 190), 0.8)
                            lst.append((x * T + r.randint(0, 6) + 8 - img.get_width() // 2,
                                        y * T + r.randint(4, 14) - img.get_height(), img))
        _cache[key] = lst
    return lst
