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


TOP = 26        # building images reserve this many px above the footprint for towers, spires and flags
SIGN_ITEM = {"provisioner": "bread", "inn": "ale", "outfitter": "shortsword_rustite", "armorer": "helm_rustite",
             "forge": "hammer_rustite", "smithy": "hammer_rustite", "assayer": "greyvein_ore", "market": "marks",
             "general_store": "ration", "warehouse": "plank", "enchanter": "mana_crystal", "apothecary": "herbal_salve",
             "scavenger_shop": "scrap", "tannery": "leather", "guild_hall": "longsword_rustite",
             "mage_tower": "arcane_dust", "workshop": "nails", "docks": "fish", "shaman_hut": "mirelight_herb",
             "arena": "spear_rustite"}
AWNING = {"market", "general_store", "provisioner", "outfitter", "apothecary", "scavenger_shop", "assayer"}
RICH_TOWNS = {"velmora", "saltmarket", "glimmerfen"}
POOR_TOWNS = {"duskreach", "thornhollow"}


def _outline_rect(s, rect, col=(16, 12, 14)):
    pygame.draw.rect(s, col, rect, 1)


def _sign(item, data):
    """A hanging shop sign: wooden board on a bracket with the trade's pictogram."""
    from . import icons
    s = pygame.Surface((20, 22), pygame.SRCALPHA)
    pygame.draw.line(s, (40, 30, 24), (0, 1), (16, 1), 2)            # iron bracket
    pygame.draw.line(s, (40, 30, 24), (2, 3), (6, 1))
    for x in (4, 14):
        pygame.draw.line(s, (60, 50, 44), (x, 2), (x, 5))            # chains
    pygame.draw.rect(s, (150, 106, 62), (1, 6, 18, 15))
    pygame.draw.rect(s, (110, 76, 44), (1, 18, 18, 3))
    pygame.draw.line(s, (186, 140, 90), (2, 7), (17, 7))
    _outline_rect(s, (1, 6, 18, 15))
    if data is not None and item:
        try:
            ic = icons.icon(data, item)
            s.blit(ic, (10 - ic.get_width() // 2, 14 - ic.get_height() // 2))
        except Exception:
            pass
    return s


def _awning(w, col):
    s = pygame.Surface((w, 8), pygame.SRCALPHA)
    alt = (236, 228, 210)
    for x in range(0, w, 6):
        c = col if (x // 6) % 2 == 0 else alt
        pygame.draw.rect(s, c, (x, 0, 6, 5))
        pygame.draw.polygon(s, c, [(x, 5), (x + 3, 7), (x + 6, 5)])
    pygame.draw.line(s, tuple(int(v * 0.6) for v in col), (0, 0), (w, 0))
    pygame.draw.line(s, (0, 0, 0, 60), (0, 5), (w, 5))
    return s


def _lantern(lit):
    s = pygame.Surface((7, 10), pygame.SRCALPHA)
    pygame.draw.line(s, (40, 30, 24), (3, 0), (3, 2))
    pygame.draw.rect(s, (40, 30, 24), (1, 2, 5, 7))
    pygame.draw.rect(s, (255, 214, 120) if lit else (150, 130, 90), (2, 3, 3, 5))
    return s


def _steeple(roof_col, stone, emblem, h=46):
    s = pygame.Surface((18, h), pygame.SRCALPHA)
    pygame.draw.rect(s, stone, (3, 18, 12, h - 18))
    pygame.draw.rect(s, tuple(int(v * 0.78) for v in stone), (11, 18, 4, h - 18))
    pygame.draw.rect(s, (30, 24, 26), (6, 24, 6, 8))                   # belfry opening
    pygame.draw.circle(s, (200, 170, 70), (9, 29), 2)                  # bell
    pygame.draw.polygon(s, roof_col, [(1, 19), (9, 2), (17, 19)])
    pygame.draw.polygon(s, tuple(int(v * 0.7) for v in roof_col), [(9, 2), (17, 19), (9, 19)])
    pygame.draw.polygon(s, (16, 12, 14), [(1, 19), (9, 2), (17, 19)], 1)
    pygame.draw.line(s, emblem, (9, 0), (9, 4))
    pygame.draw.line(s, emblem, (7, 1), (11, 1))
    _outline_rect(s, (3, 18, 12, h - 18))
    return s


def _spire(roof_col, wall, glow, h=50):
    s = pygame.Surface((20, h), pygame.SRCALPHA)
    pygame.draw.rect(s, wall, (4, 20, 12, h - 20))
    pygame.draw.rect(s, tuple(int(v * 0.75) for v in wall), (12, 20, 4, h - 20))
    for y in range(30, h - 4, 12):
        pygame.draw.rect(s, glow, (8, y, 4, 5))
    pygame.draw.rect(s, glow, (8, 27, 4, 6))
    pygame.draw.polygon(s, roof_col, [(1, 21), (10, 0), (19, 21)])
    pygame.draw.polygon(s, tuple(int(v * 0.7) for v in roof_col), [(10, 0), (19, 21), (10, 21)])
    pygame.draw.polygon(s, (16, 12, 14), [(1, 21), (10, 0), (19, 21)], 1)
    _outline_rect(s, (4, 20, 12, h - 20))
    s.set_at((10, 0), (255, 240, 170))
    return s


def _battlements(w, stone):
    s = pygame.Surface((w, 7), pygame.SRCALPHA)
    pygame.draw.rect(s, stone, (0, 3, w, 4))
    for x in range(0, w, 6):
        pygame.draw.rect(s, stone, (x, 0, 4, 4))
        pygame.draw.rect(s, (16, 12, 14), (x, 0, 4, 4), 1)
    pygame.draw.rect(s, (16, 12, 14), (0, 3, w, 4), 1)
    return s


def _flag(col):
    s = pygame.Surface((12, 20), pygame.SRCALPHA)
    pygame.draw.line(s, (60, 50, 44), (1, 0), (1, 19))
    pygame.draw.polygon(s, col, [(2, 1), (11, 3), (2, 7)])
    pygame.draw.polygon(s, (16, 12, 14), [(2, 1), (11, 3), (2, 7)], 1)
    return s


def building(b, specialty, palette, lit=False, data=None, town=None):
    """Facade + roof image covering the building's footprint (plus TOP px above it for towers and flags).
    Every type gets its own architecture: signs with the trade's pictogram, awnings, steeples, spires,
    battlements, lanterns, forge glow, barn doors; richer towns get gilded trim, poorer ones patched roofs."""
    key = ("bld2", b["id"], b["x"], b["y"], specialty, lit, town)
    s = _cache.get(key)
    if s is None:
        base = _building_base(b, specialty, palette, lit)
        s = pygame.Surface((base.get_width(), base.get_height() + TOP), pygame.SRCALPHA)
        s.blit(base, (0, TOP))
        _decorate(s, b, specialty, palette, lit, data, town)
        _cache[key] = s
    return s


def _decorate(s, b, specialty, palette, lit, data, town):
    t = b["type"]
    W, H = b["w"] * T, b["h"] * T
    roof_h = (b["h"] - 2) * T
    wall_y = TOP + roof_h                      # top of the facade
    dx = (b["door"][0] - b["x"]) * T
    roof_col = tuple(palette["roof"]) if palette else (140, 70, 50)
    accent = tuple(palette.get("accent", (170, 50, 40))) if palette else (170, 50, 40)
    stone = (150, 146, 140)
    r = random.Random(b["id"])
    # hipped roof ends on grander buildings: a different roof silhouette from the plain gable
    if t in ("inn", "temple", "chapel", "palace", "guild_hall", "barracks", "mage_tower", "market") and roof_h > 16:
        hw = min(W // 4, roof_h // 2 + 4)
        ridge = TOP + roof_h // 2
        shade = tuple(int(v * 0.62) for v in roof_col)
        lightc = tuple(min(255, int(v * 1.1)) for v in roof_col)
        pygame.draw.polygon(s, shade, [(0, TOP), (hw, ridge), (0, TOP + roof_h + 3)])
        pygame.draw.polygon(s, lightc, [(W - 1, TOP), (W - 1 - hw, ridge), (W - 1, TOP + roof_h + 3)])
        for pts in ([(0, TOP), (hw, ridge), (0, TOP + roof_h + 3)], [(W - 1, TOP), (W - 1 - hw, ridge), (W - 1, TOP + roof_h + 3)]):
            pygame.draw.lines(s, (16, 12, 14), False, pts, 1)
    # wealth
    if town in RICH_TOWNS:
        pygame.draw.line(s, (214, 178, 80), (1, wall_y - 3), (W - 2, wall_y - 3))
        pygame.draw.line(s, (214, 178, 80), (1, wall_y + 1), (W - 2, wall_y + 1))
    elif town in POOR_TOWNS:
        for _ in range(max(1, W // 40)):
            px, py = r.randint(4, max(5, W - 14)), TOP + r.randint(2, max(3, roof_h - 8))
            pygame.draw.rect(s, (120, 100, 70), (px, py, 8, 5))
            _outline_rect(s, (px, py, 8, 5), (70, 56, 40))
    # awnings over shop fronts
    if t in AWNING:
        aw = _awning(W - 4, accent if t != "market" else (170, 50, 50))
        s.blit(aw, (2, wall_y + 2))
    # hanging sign beside the door
    item = SIGN_ITEM.get(t) or (SIGN_ITEM.get(b.get("shop")) if b.get("shop") else None)
    if item:
        sx = dx + 18 if dx + 40 < W else max(2, dx - 20)
        s.blit(_sign(item, data), (sx, wall_y + 3))
    # lanterns by inn and tavern doors (glowing at night)
    if t in ("inn", "guild_hall", "palace", "temple", "chapel"):
        for lx in (dx - 9, dx + 18):
            if 0 <= lx < W - 7:
                s.blit(_lantern(lit), (lx, wall_y + 6))
    # towers and roofs with a skyline
    if t in ("temple", "chapel"):
        st = _steeple(roof_col, (200, 196, 186), (230, 200, 90), wall_y + 6)
        s.blit(st, (W // 2 - 9, 0))
    elif t == "mage_tower":
        sp = _spire((90, 70, 150), (170, 160, 190), (150, 220, 255) if lit else (110, 160, 210), wall_y + 4)
        s.blit(sp, (W // 2 - 10, 0))
    elif t in ("barracks", "palace", "watchtower", "arena"):
        s.blit(_battlements(W, stone), (0, TOP - 4))
        if t == "palace":
            for fx in (2, W // 2 - 1, W - 12):
                s.blit(_flag(accent), (fx, TOP - 22))
            tw = _spire(roof_col, (200, 194, 180), (240, 210, 120), wall_y - 2)
            s.blit(tw, (2, 4))
            s.blit(tw, (W - 22, 4))
        elif t != "arena":
            s.blit(_flag(accent), (W // 2 - 1, TOP - 20))
    elif t in ("guild_hall", "longhouse"):
        s.blit(_flag(accent), (W - 14, TOP - 18))
    elif t == "shaman_hut":
        for k in range(3):
            pygame.draw.line(s, (150, 110, 70), (W // 2 - 4 + k * 4, TOP - 6), (W // 2 - 2 + k, TOP + 6), 2)
        pygame.draw.circle(s, (230, 220, 200), (W // 2, TOP - 6), 3)
        pygame.draw.circle(s, (16, 12, 14), (W // 2, TOP - 6), 3, 1)
    # trade details on the facade
    if t in ("forge", "smithy"):
        gx = 6 if dx > W // 2 else W - 22
        pygame.draw.rect(s, (40, 26, 20), (gx, wall_y + 10, 16, 12))
        pygame.draw.rect(s, (255, 140, 50), (gx + 2, wall_y + 14, 12, 7))
        pygame.draw.rect(s, (255, 210, 110), (gx + 4, wall_y + 16, 8, 4))
        _outline_rect(s, (gx, wall_y + 10, 16, 12))
        cx = W - 16 if dx < W // 2 else 8
        pygame.draw.rect(s, (90, 80, 78), (cx, TOP - 6, 9, 16))
        _outline_rect(s, (cx, TOP - 6, 9, 16))
        for k in range(3):                                      # smoke
            pygame.draw.circle(s, (180, 180, 186, 140 - k * 40), (cx + 4 + k, TOP - 9 - k * 5), 3 + k)
    elif t in ("barn", "farmhouse", "warehouse") and b["w"] >= 4:
        bx = 6 if dx > W // 2 else W - 26
        pygame.draw.rect(s, (130, 60, 44), (bx, wall_y + 8, 20, 24))
        pygame.draw.line(s, (230, 220, 200), (bx, wall_y + 8), (bx + 19, wall_y + 31))
        pygame.draw.line(s, (230, 220, 200), (bx + 19, wall_y + 8), (bx, wall_y + 31))
        _outline_rect(s, (bx, wall_y + 8, 20, 24), (230, 220, 200))
    elif t == "tannery":
        hx = 6 if dx > W // 2 else W - 22
        pygame.draw.line(s, (90, 62, 40), (hx, wall_y + 6), (hx + 16, wall_y + 6))
        for k in range(2):
            pygame.draw.rect(s, (170, 130, 90), (hx + 1 + k * 8, wall_y + 7, 6, 10))
            _outline_rect(s, (hx + 1 + k * 8, wall_y + 7, 6, 10), (100, 70, 50))
    elif t == "docks":
        for k in range(0, W, 10):
            pygame.draw.rect(s, (120, 86, 54), (k + 2, wall_y + 26, 3, 8))
    elif t in ("house", "property_for_sale") and r.random() < 0.6:
        # flower boxes or laundry lines on homes
        pygame.draw.line(s, (200, 190, 170), (4, wall_y + 4), (W - 5, wall_y + 4))
        for k in range(r.randint(1, 3)):
            lx = r.randint(8, max(9, W - 16))
            pygame.draw.rect(s, r.choice([(200, 80, 80), (80, 120, 200), (230, 220, 200), (110, 170, 90)]),
                             (lx, wall_y + 5, 6, 6))
    if t == "property_for_sale":
        sx = dx + 18 if dx + 30 < W else max(2, dx - 16)
        pygame.draw.rect(s, (220, 210, 180), (sx, wall_y + 10, 12, 8))
        _outline_rect(s, (sx, wall_y + 10, 12, 8))
        pygame.draw.line(s, (180, 40, 40), (sx + 2, wall_y + 13), (sx + 9, wall_y + 13))
        pygame.draw.line(s, (180, 40, 40), (sx + 2, wall_y + 15), (sx + 7, wall_y + 15))


def _building_base(b, specialty, palette, lit=False):
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
