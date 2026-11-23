"""Procedural pixel art. Everything is drawn once with primitives and cached; no external image files.

Scale: 16x16 tiles, 16x24 characters, drawn on a 640x360 canvas that is scaled 2x to the window.
"""
import math

import pygame

from ..core.rng import stable_rng
from ..world import mapgen as mg

T = mg.TILE
OUTLINE = (24, 20, 28)

BIOME_GROUND = {
    "grassland": ((86, 140, 60), (110, 150, 70)), "forest": ((60, 110, 50), (84, 92, 52)),
    "hills": ((100, 140, 70), (130, 122, 82)), "mountain": ((112, 106, 100), (92, 86, 82)),
    "snow": ((226, 231, 240), (204, 212, 228)), "desert": ((222, 198, 142), (204, 174, 122)),
    "coast": ((212, 202, 152), (96, 146, 76)), "swamp": ((70, 96, 60), (84, 76, 52)),
    "canyon": ((182, 104, 72), (160, 88, 62)), "volcanic": ((64, 58, 58), (94, 54, 42)),
    "moor": ((112, 116, 82), (92, 96, 76)), "ruins": ((96, 130, 72), (142, 138, 124)),
    "cave": ((72, 66, 72), (58, 52, 58)), "crystal": ((92, 112, 142), (122, 152, 172)),
    "interior": ((120, 90, 60), (110, 82, 55)),
}
PATH_COLOR = {"snow": (190, 196, 210), "cave": (96, 90, 96), "desert": (196, 166, 116), "volcanic": (82, 76, 74),
              "canyon": (150, 110, 80), "crystal": (150, 160, 175)}


def _jitter(c, r, amt):
    return tuple(max(0, min(255, v + r.randint(-amt, amt))) for v in c)


def _shade(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c)


class Art:
    def __init__(self):
        self.cache = {}

    def _get(self, key, fn):
        s = self.cache.get(key)
        if s is None:
            s = fn()
            self.cache[key] = s
        return s

    # ================================================================== tiles
    def tile(self, tile_id, biome, variant=0, palette=None):
        pk = tuple(map(tuple, palette.values())) if palette else None
        return self._get(("tile", tile_id, biome, variant, pk), lambda: self._make_tile(tile_id, biome, variant, palette))

    def _make_tile(self, tid, biome, variant, palette):
        from . import env
        if env.enabled():
            if tid == mg.WATER:
                img = env.water(biome, variant % 4, variant // 4)
            else:
                img = env.ground(tid, biome, variant, palette, BIOME_GROUND.get(biome, BIOME_GROUND["grassland"]),
                                 PATH_COLOR.get(biome, (152, 122, 84)))
            if img is not None:
                return img.convert() if pygame.display.get_surface() else img
        s = pygame.Surface((T, T))
        r = stable_rng("tile", tid, biome, variant)
        g, alt = BIOME_GROUND.get(biome, BIOME_GROUND["grassland"])
        if tid in (mg.GROUND, mg.ALT):
            base = g if tid == mg.GROUND else alt
            s.fill(base)
            for _ in range(22):
                s.set_at((r.randrange(T), r.randrange(T)), _jitter(base, r, 14))
            if biome in ("grassland", "forest", "hills", "coast", "ruins", "moor") and tid == mg.GROUND:
                for _ in range(3):
                    x, y = r.randrange(1, T - 1), r.randrange(2, T)
                    c = _shade(base, 1.25)
                    s.set_at((x, y), c)
                    s.set_at((x, y - 1), c)
                    s.set_at((x + 1, y - 1), _shade(base, 1.15))
            if biome == "ruins" and tid == mg.ALT:
                pygame.draw.line(s, _shade(base, 0.8), (0, 7), (T, 7))
                pygame.draw.line(s, _shade(base, 0.8), (7 + variant % 2 * 4, 0), (7 + variant % 2 * 4, 7))
            if biome == "snow":
                for _ in range(4):
                    s.set_at((r.randrange(T), r.randrange(T)), (255, 255, 255))
        elif tid == mg.PATH:
            base = PATH_COLOR.get(biome, (152, 122, 84))
            s.fill(base)
            for _ in range(26):
                s.set_at((r.randrange(T), r.randrange(T)), _jitter(base, r, 18))
            for _ in range(2):
                pygame.draw.rect(s, _shade(base, 0.8), (r.randrange(T - 2), r.randrange(T - 2), 2, 1))
        elif tid == mg.PLAZA:
            s.fill((128, 124, 118))
            for y in range(0, T, 8):
                off = 4 if (y // 8) % 2 else 0
                for x in range(-off, T, 8):
                    c = _jitter((150, 146, 138), r, 10)
                    pygame.draw.rect(s, c, (x + 1, y + 1, 6, 6))
        elif tid == mg.WATER:
            base = (52, 104, 168) if biome != "swamp" else (60, 92, 80)
            s.fill(base)
            for _ in range(3):
                x, y = r.randrange(T - 4), r.randrange(T)
                pygame.draw.line(s, _shade(base, 1.35), (x, y), (x + 3, y))
        elif tid == mg.FIELD:
            s.fill((112, 80, 50))
            for y in range(1, T, 4):
                pygame.draw.line(s, (90, 62, 40), (0, y), (T, y))
        elif tid == mg.FLOOR_WOOD:
            s.fill((132, 94, 60))
            for y in range(0, T, 4):
                pygame.draw.line(s, (100, 70, 44), (0, y), (T, y))
                x = (r.randrange(T) + y * 3) % T
                pygame.draw.line(s, (100, 70, 44), (x, y), (x, y + 3))
        elif tid == mg.FLOOR_STONE:
            s.fill((120, 118, 124))
            pygame.draw.rect(s, (100, 98, 104), (0, 0, T, T), 1)
            for _ in range(8):
                s.set_at((r.randrange(T), r.randrange(T)), (136, 134, 140))
        elif tid == mg.WALL:
            wall = tuple(palette["wall"]) if palette else (150, 120, 90)
            if biome == "interior":
                wall = (96, 72, 56)
            s.fill(wall)
            for y in (5, 11):
                pygame.draw.line(s, _shade(wall, 0.82), (0, y), (T, y))
            pygame.draw.line(s, _shade(wall, 0.6), (0, T - 1), (T, T - 1))
            if variant % 3 == 1 and biome != "interior":
                pygame.draw.rect(s, (60, 50, 40), (4, 3, 7, 6))
                pygame.draw.rect(s, (240, 210, 120), (5, 4, 5, 4))
                pygame.draw.line(s, (60, 50, 40), (7, 4), (7, 7))
        elif tid == mg.ROOF:
            roof = tuple(palette["roof"]) if palette else (140, 70, 50)
            s.fill(roof)
            for y in range(0, T, 4):
                pygame.draw.line(s, _shade(roof, 0.75), (0, y + 3), (T, y + 3))
                for x in range((y // 4) % 2 * 3, T, 6):
                    s.set_at((x, y + 1), _shade(roof, 1.15))
        elif tid == mg.VOID:
            s.fill((22, 20, 26))
            if biome == "cave":
                for _ in range(10):
                    s.set_at((r.randrange(T), r.randrange(T)), (40, 36, 44))
        return s.convert() if pygame.display.get_surface() else s

    # ================================================================== objects
    def obj(self, kind, variant=0, biome="grassland", extra=None):
        key = ("obj", kind, variant, biome, extra)
        return self._get(key, lambda: self._make_obj(kind, variant, biome, extra))

    def _make_obj(self, kind, variant, biome, extra):
        from . import env
        if kind == "campfire" and env.enabled():
            img = env.campfire(variant)
            if img is not None:
                return img
        img = env.prop(kind, variant, biome, extra)
        if img is not None:
            return img
        r = stable_rng("obj", kind, variant, biome, extra)
        if kind == "tree":
            s = pygame.Surface((T + 8, 30), pygame.SRCALPHA)
            pygame.draw.rect(s, (92, 64, 40), (10, 18, 4, 11))
            base = [(56, 120, 52), (68, 132, 56), (50, 108, 60), (78, 128, 50)][variant % 4]
            if biome == "forest":
                base = _shade(base, 0.85)
            for cx, cy, rr in ((12, 11, 9), (7, 14, 6), (17, 14, 6)):
                pygame.draw.circle(s, _shade(base, 0.7), (cx, cy + 1), rr)
                pygame.draw.circle(s, base, (cx, cy), rr)
            for _ in range(10):
                s.set_at((r.randrange(4, 20), r.randrange(3, 18)), _shade(base, 1.25))
            return _outline(s)
        if kind == "pine":
            s = pygame.Surface((T + 4, 30), pygame.SRCALPHA)
            pygame.draw.rect(s, (80, 56, 36), (8, 22, 4, 7))
            col = (40, 92, 64)
            for i, (w, y) in enumerate(((7, 2), (9, 8), (10, 14))):
                pygame.draw.polygon(s, col, [(10, y), (10 - w, y + 9), (10 + w, y + 9)])
                if biome in ("snow", "mountain"):
                    pygame.draw.line(s, (240, 245, 250), (10 - w + 2, y + 8), (10 + w - 2, y + 8))
            return _outline(s)
        if kind == "dead_tree":
            s = pygame.Surface((T + 4, 28), pygame.SRCALPHA)
            c = (88, 72, 60)
            pygame.draw.line(s, c, (10, 27), (10, 6), 3)
            pygame.draw.line(s, c, (10, 14), (4, 6), 2)
            pygame.draw.line(s, c, (10, 11), (16, 3), 2)
            pygame.draw.line(s, c, (10, 19), (16, 14), 2)
            return _outline(s)
        if kind == "cactus":
            s = pygame.Surface((T, 24), pygame.SRCALPHA)
            c = (70, 140, 80)
            pygame.draw.rect(s, c, (6, 4, 4, 19), border_radius=2)
            pygame.draw.rect(s, c, (2, 9, 3, 7), border_radius=1)
            pygame.draw.rect(s, c, (11, 6, 3, 8), border_radius=1)
            return _outline(s)
        if kind == "crystal_spire":
            s = pygame.Surface((T, 28), pygame.SRCALPHA)
            for dx, h, col in ((3, 18, (120, 200, 230)), (8, 24, (160, 230, 250)), (12, 14, (100, 170, 220))):
                pygame.draw.polygon(s, col, [(dx, 27), (dx + 2, 27 - h), (dx + 4, 27)])
            return _outline(s)
        if kind == "rock":
            s = pygame.Surface((T, T), pygame.SRCALPHA)
            base = {"canyon": (150, 90, 70), "volcanic": (50, 46, 50), "snow": (150, 155, 165), "desert": (170, 140, 100)}.get(biome, (128, 124, 120))
            pygame.draw.ellipse(s, _shade(base, 0.75), (1, 5, 14, 11))
            pygame.draw.ellipse(s, base, (2, 3, 12, 10))
            pygame.draw.line(s, _shade(base, 1.25), (5, 5), (9, 4))
            return _outline(s)
        if kind == "ore_vein":
            ore_col = extra or (180, 100, 60)
            s = self._make_obj("rock", variant, "mountain", None).copy()
            depleted = ore_col == "depleted"
            if not depleted:
                for x, y in ((4, 6), (9, 5), (6, 9), (10, 10), (3, 11)):
                    x += r.randint(-1, 1)
                    pygame.draw.rect(s, _shade(ore_col, 0.7), (x, y + 1, 3, 2))
                    pygame.draw.rect(s, ore_col, (x, y, 3, 2))
                    s.set_at((x, y), _shade(ore_col, 1.5))
                s.set_at((11, 3), (255, 255, 230))  # glint
                s.set_at((12, 4), (255, 255, 230))
            else:
                s.fill((0, 0, 0, 60), special_flags=pygame.BLEND_RGBA_SUB)
            return s
        if kind == "mana_crystal_node":
            s = pygame.Surface((T, T), pygame.SRCALPHA)
            if extra != "depleted":
                for dx, h in ((3, 8), (7, 12), (11, 7)):
                    pygame.draw.polygon(s, (150, 120, 240), [(dx, 15), (dx + 2, 15 - h), (dx + 4, 15)])
                    pygame.draw.line(s, (220, 200, 255), (dx + 2, 15 - h + 2), (dx + 2, 13))
            else:
                pygame.draw.rect(s, (90, 80, 120), (4, 12, 8, 3))
            return _outline(s)
        if kind == "bush":
            s = pygame.Surface((T, T), pygame.SRCALPHA)
            base = (60, 124, 56) if biome != "swamp" else (70, 110, 70)
            pygame.draw.circle(s, _shade(base, 0.7), (8, 10), 6)
            pygame.draw.circle(s, base, (8, 9), 6)
            if extra != "depleted":
                berry = {"mirelight_herb": (140, 240, 200), "herbs": (200, 220, 120), "mushrooms": (220, 200, 170),
                         "fiber": (210, 200, 140), "salt": (240, 240, 240), "meat": (200, 60, 60)}.get(variant, (200, 40, 60))
                for _ in range(5):
                    s.set_at((r.randrange(4, 12), r.randrange(5, 13)), berry)
            return _outline(s)
        if kind == "scavenge":
            s = pygame.Surface((T, T), pygame.SRCALPHA)
            if extra == "depleted":
                pygame.draw.rect(s, (100, 90, 80), (3, 12, 9, 2))
                return s
            pygame.draw.polygon(s, (110, 90, 70), [(1, 14), (5, 8), (9, 10), (15, 14)])
            pygame.draw.line(s, (150, 130, 100), (3, 12), (13, 7), 2)
            pygame.draw.rect(s, (130, 130, 140), (6, 9, 3, 3))
            return _outline(s)
        if kind == "well":
            s = pygame.Surface((T, 22), pygame.SRCALPHA)
            pygame.draw.rect(s, (90, 70, 50), (2, 2, 2, 14))
            pygame.draw.rect(s, (90, 70, 50), (12, 2, 2, 14))
            pygame.draw.polygon(s, (140, 70, 50), [(0, 4), (8, 0), (16, 4)])
            pygame.draw.ellipse(s, (120, 120, 125), (1, 12, 14, 9))
            pygame.draw.ellipse(s, (40, 70, 120), (4, 14, 8, 4))
            return _outline(s)
        if kind == "door":
            s = pygame.Surface((T, T), pygame.SRCALPHA)
            pygame.draw.rect(s, (70, 46, 30), (3, 1, 10, 15))
            pygame.draw.rect(s, (110, 74, 44), (4, 2, 8, 14))
            pygame.draw.line(s, (80, 52, 34), (8, 2), (8, 15))
            s.set_at((10, 9), (220, 200, 120))
            return s
        if kind == "exit_door":
            s = pygame.Surface((T, T), pygame.SRCALPHA)
            pygame.draw.rect(s, (150, 60, 50), (2, 4, 12, 10))
            pygame.draw.polygon(s, (240, 220, 160), [(8, 13), (4, 8), (12, 8)])
            return s
        if kind in ("palisade", "fence"):
            s = pygame.Surface((T, 20), pygame.SRCALPHA)
            c = (120, 86, 54)
            if kind == "palisade":
                for x in range(1, T, 5):
                    pygame.draw.rect(s, c, (x, 3, 4, 17))
                    pygame.draw.polygon(s, c, [(x, 3), (x + 2, 0), (x + 4, 3)])
                pygame.draw.line(s, _shade(c, 0.7), (0, 9), (T, 9), 2)
            else:
                pygame.draw.rect(s, c, (1, 6, 3, 14))
                pygame.draw.rect(s, c, (12, 6, 3, 14))
                pygame.draw.line(s, c, (0, 9), (T, 9), 2)
                pygame.draw.line(s, c, (0, 15), (T, 15), 2)
            return _outline(s)
        if kind == "barrel":
            s = pygame.Surface((T, T), pygame.SRCALPHA)
            pygame.draw.rect(s, (130, 90, 50), (3, 2, 10, 13), border_radius=3)
            pygame.draw.line(s, (70, 60, 60), (3, 5), (12, 5))
            pygame.draw.line(s, (70, 60, 60), (3, 11), (12, 11))
            return _outline(s)
        if kind == "crate":
            s = pygame.Surface((T, T), pygame.SRCALPHA)
            pygame.draw.rect(s, (160, 120, 70), (2, 3, 12, 12))
            pygame.draw.rect(s, (110, 80, 45), (2, 3, 12, 12), 1)
            pygame.draw.line(s, (110, 80, 45), (2, 3), (13, 14))
            return _outline(s)
        if kind == "counter":
            s = pygame.Surface((T, T), pygame.SRCALPHA)
            pygame.draw.rect(s, (110, 72, 44), (0, 3, T, 13))
            pygame.draw.rect(s, (150, 104, 64), (0, 3, T, 4))
            return s
        if kind in ("shelf", "bookshelf"):
            s = pygame.Surface((T, 20), pygame.SRCALPHA)
            pygame.draw.rect(s, (100, 66, 40), (1, 0, 14, 20))
            for y in (4, 10, 16):
                pygame.draw.line(s, (70, 46, 28), (1, y), (14, y))
                for x in range(2, 14, 2):
                    col = [(170, 60, 50), (60, 90, 160), (200, 170, 80), (80, 140, 80)][(x + y + variant) % 4]
                    if kind == "shelf":
                        col = [(200, 190, 160), (140, 100, 60), (120, 120, 130)][(x + y) % 3]
                    pygame.draw.line(s, col, (x, y - 3), (x, y - 1))
            return _outline(s)
        if kind == "bed":
            s = pygame.Surface((T, 22), pygame.SRCALPHA)
            pygame.draw.rect(s, (110, 70, 44), (1, 0, 14, 22))
            pygame.draw.rect(s, (230, 230, 220), (2, 2, 12, 5))
            pygame.draw.rect(s, (150, 50, 50), (2, 7, 12, 13))
            return _outline(s)
        if kind == "table":
            s = pygame.Surface((T, T), pygame.SRCALPHA)
            pygame.draw.rect(s, (140, 96, 58), (1, 4, 14, 7))
            pygame.draw.rect(s, (100, 66, 40), (2, 11, 2, 4))
            pygame.draw.rect(s, (100, 66, 40), (12, 11, 2, 4))
            pygame.draw.circle(s, (220, 210, 190), (5, 6), 2)
            return _outline(s)
        if kind == "anvil":
            s = pygame.Surface((T, T), pygame.SRCALPHA)
            pygame.draw.polygon(s, (70, 70, 80), [(1, 5), (15, 5), (12, 9), (4, 9)])
            pygame.draw.rect(s, (60, 60, 70), (6, 9, 4, 4))
            pygame.draw.rect(s, (80, 80, 90), (3, 13, 10, 3))
            return _outline(s)
        if kind == "furnace":
            s = pygame.Surface((T, 20), pygame.SRCALPHA)
            pygame.draw.rect(s, (110, 100, 100), (1, 2, 14, 18))
            pygame.draw.rect(s, (240, 140, 40), (4, 10, 8, 6))
            pygame.draw.rect(s, (250, 220, 120), (6, 12, 4, 3))
            return _outline(s)
        if kind == "workbench":
            s = pygame.Surface((T, T), pygame.SRCALPHA)
            pygame.draw.rect(s, (150, 108, 64), (0, 4, T, 6))
            pygame.draw.rect(s, (100, 70, 40), (1, 10, 2, 6))
            pygame.draw.rect(s, (100, 70, 40), (13, 10, 2, 6))
            pygame.draw.line(s, (180, 180, 190), (3, 3), (8, 3), 2)
            pygame.draw.rect(s, (120, 80, 50), (10, 1, 4, 3))
            return _outline(s)
        if kind == "stove":
            s = pygame.Surface((T, 20), pygame.SRCALPHA)
            pygame.draw.rect(s, (70, 70, 76), (1, 4, 14, 16))
            pygame.draw.rect(s, (40, 40, 44), (3, 12, 10, 6))
            pygame.draw.rect(s, (240, 130, 40), (5, 14, 6, 3))
            pygame.draw.rect(s, (80, 80, 86), (11, 0, 3, 5))
            return _outline(s)
        if kind == "alchemy_table":
            s = pygame.Surface((T, T), pygame.SRCALPHA)
            pygame.draw.rect(s, (110, 76, 50), (0, 6, T, 5))
            pygame.draw.rect(s, (80, 56, 36), (2, 11, 2, 5))
            pygame.draw.rect(s, (80, 56, 36), (12, 11, 2, 5))
            for x, col in ((3, (120, 220, 140)), (8, (160, 120, 240)), (12, (240, 120, 120))):
                pygame.draw.rect(s, col, (x, 2, 2, 4))
                s.set_at((x, 1), (230, 230, 230))
            return _outline(s)
        if kind == "scribing_table":
            s = pygame.Surface((T, T), pygame.SRCALPHA)
            pygame.draw.polygon(s, (120, 86, 56), [(1, 6), (15, 4), (15, 10), (1, 11)])
            pygame.draw.rect(s, (90, 60, 40), (3, 11, 2, 5))
            pygame.draw.rect(s, (90, 60, 40), (11, 10, 2, 6))
            pygame.draw.rect(s, (235, 225, 200), (4, 5, 7, 4))
            pygame.draw.line(s, (150, 100, 230), (12, 2), (10, 7))
            return _outline(s)
        if kind == "training_dummy":
            s = self._make_creature("dummy", (170, 130, 80), "down", 0)
            return _outline(s)
        if kind.startswith("base_"):
            return _outline(self._make_base(kind[5:], variant, extra))
        if kind == "chest":
            s = pygame.Surface((T, T), pygame.SRCALPHA)
            pygame.draw.rect(s, (130, 86, 46), (1, 5, 14, 10))
            pygame.draw.rect(s, (160, 110, 60), (1, 3, 14, 4))
            pygame.draw.rect(s, (220, 190, 90), (7, 6, 2, 3))
            return _outline(s)
        if kind == "lantern":
            s = pygame.Surface((T, T), pygame.SRCALPHA)
            pygame.draw.line(s, (80, 60, 40), (8, 15), (8, 4), 2)
            pygame.draw.rect(s, (250, 210, 110), (5, 1, 6, 5))
            return _outline(s)
        if kind == "campfire":
            s = pygame.Surface((T, T), pygame.SRCALPHA)
            pygame.draw.line(s, (90, 60, 40), (2, 14), (14, 10), 3)
            pygame.draw.line(s, (90, 60, 40), (2, 10), (14, 14), 3)
            flick = variant % 2
            pygame.draw.polygon(s, (240, 120, 40), [(4, 12), (8, 1 + flick), (12, 12)])
            pygame.draw.polygon(s, (255, 220, 100), [(6, 12), (8, 5 + flick), (10, 12)])
            return s
        if kind == "landmark":
            s = pygame.Surface((T, 26), pygame.SRCALPHA)
            pygame.draw.rect(s, (150, 146, 136), (4, 2, 8, 23))
            pygame.draw.rect(s, (120, 116, 108), (2, 21, 12, 5))
            pygame.draw.line(s, (100, 96, 90), (6, 6), (10, 12))
            pygame.draw.circle(s, (120, 200, 220), (8, 8), 1)
            return _outline(s)
        if kind == "bounty_board":
            s = pygame.Surface((T, 22), pygame.SRCALPHA)
            pygame.draw.rect(s, (90, 64, 40), (2, 8, 2, 14))
            pygame.draw.rect(s, (90, 64, 40), (12, 8, 2, 14))
            pygame.draw.rect(s, (140, 100, 60), (0, 1, T, 11))
            for x, y in ((2, 3), (7, 4), (11, 3)):
                pygame.draw.rect(s, (235, 225, 200), (x, y, 4, 5))
            return _outline(s)
        if kind == "crop":
            s = pygame.Surface((T, T), pygame.SRCALPHA)
            col = [(200, 180, 80), (120, 170, 70), (210, 160, 60)][variant % 3]
            for x in (3, 8, 13):
                pygame.draw.line(s, (90, 130, 50), (x, 14), (x, 7))
                pygame.draw.rect(s, col, (x - 1, 5, 3, 3))
            return s
        # unknown -> magenta box so missing art is obvious during development
        s = pygame.Surface((T, T))
        s.fill((255, 0, 255))
        return s

    # ================================================================== characters
    def character(self, look, direction, frame, action=False):
        key = ("char", tuple(sorted((k, tuple(v) if isinstance(v, list) else v) for k, v in look.items())),
               direction, frame, action)
        return self._get(key, lambda: _outline(self._make_char(look, direction, frame, action)))

    def _make_char(self, look, d, frame, action):
        s = pygame.Surface((16, 24), pygame.SRCALPHA)
        skin = tuple(look["skin"])
        hair = tuple(look["hair"])
        shirt = tuple(look["shirt"])
        pants = tuple(look["pants"])
        race = look.get("race", "human")
        wide = 1 if race in ("kethari", "murrok") else 0
        # walking cycle: frames 0..3 ; frame 0 = idle
        swing = (0, 1, 0, -1)[frame % 4]
        bob = 1 if frame % 2 == 1 else 0
        y0 = bob
        # legs
        if d in ("down", "up"):
            pygame.draw.rect(s, pants, (5 - wide, 16 + y0, 2 + wide, 6 + swing - bob))
            pygame.draw.rect(s, pants, (9, 16 + y0, 2 + wide, 6 - swing - bob))
            pygame.draw.rect(s, (60, 44, 34), (5 - wide, 21 + swing, 2 + wide, 1))
            pygame.draw.rect(s, (60, 44, 34), (9, 21 - swing, 2 + wide, 1))
        else:
            pygame.draw.rect(s, pants, (6 + swing, 16 + y0, 3, 6 - bob))
            pygame.draw.rect(s, _shade(pants, 0.8), (7 - swing, 16 + y0, 3, 6 - bob))
        # torso
        pygame.draw.rect(s, shirt, (4 - wide, 9 + y0, 8 + wide * 2, 8))
        pygame.draw.line(s, _shade(shirt, 0.75), (4 - wide, 15 + y0), (11 + wide, 15 + y0))  # belt
        # arms
        arm = 4 if action else 0
        if d in ("down", "up"):
            pygame.draw.rect(s, shirt, (2 - wide, 10 + y0 - swing, 2, 5))
            pygame.draw.rect(s, shirt, (12 + wide, 10 + y0 + swing, 2, 5))
            pygame.draw.rect(s, skin, (2 - wide, 15 + y0 - swing, 2, 1))
            pygame.draw.rect(s, skin, (12 + wide, 15 + y0 + swing, 2, 1))
        elif d == "left":
            pygame.draw.rect(s, _shade(shirt, 0.85), (6 - swing - arm, 10 + y0, 3 + arm, 4 if action else 5))
            pygame.draw.rect(s, skin, (6 - swing - arm, 14 + y0 if not action else 12 + y0, 2, 1))
        else:
            pygame.draw.rect(s, _shade(shirt, 0.85), (7 + swing, 10 + y0, 3 + arm, 4 if action else 5))
            pygame.draw.rect(s, skin, (8 + swing + arm, 14 + y0 if not action else 12 + y0, 2, 1))
        # head
        hx, hy = 4, 1 + y0
        pygame.draw.rect(s, skin, (hx, hy, 8, 8))
        if race == "sylth":  # long swept ears
            pygame.draw.polygon(s, skin, [(hx, hy + 4), (hx - 3, hy + 1), (hx, hy + 6)])
            pygame.draw.polygon(s, skin, [(hx + 8, hy + 4), (hx + 11, hy + 1), (hx + 8, hy + 6)])
        if race == "murrok":  # small round ears
            pygame.draw.rect(s, _shade(skin, 0.8), (hx, hy - 1, 2, 2))
            pygame.draw.rect(s, _shade(skin, 0.8), (hx + 6, hy - 1, 2, 2))
        # hair
        style = look.get("hair_style", 0)
        if d == "up":
            pygame.draw.rect(s, hair, (hx, hy, 8, 7 if style != 2 else 5))
        else:
            pygame.draw.rect(s, hair, (hx, hy, 8, 2))
            if style == 1:  # long
                if d == "down":
                    pygame.draw.rect(s, hair, (hx, hy, 1, 8))
                    pygame.draw.rect(s, hair, (hx + 7, hy, 1, 8))
                elif d == "left":
                    pygame.draw.rect(s, hair, (hx + 5, hy, 3, 9))
                else:
                    pygame.draw.rect(s, hair, (hx, hy, 3, 9))
            elif style == 0:
                if d == "left":
                    pygame.draw.rect(s, hair, (hx + 5, hy, 3, 4))
                elif d == "right":
                    pygame.draw.rect(s, hair, (hx, hy, 3, 4))
                else:
                    pygame.draw.rect(s, hair, (hx, hy + 2, 1, 2))
                    pygame.draw.rect(s, hair, (hx + 7, hy + 2, 1, 2))
        # face
        eye = (30, 26, 40)
        if d == "down":
            s.set_at((hx + 2, hy + 4), eye)
            s.set_at((hx + 5, hy + 4), eye)
            if race == "murrok":
                s.set_at((hx + 1, hy + 7), (240, 240, 220))
                s.set_at((hx + 6, hy + 7), (240, 240, 220))
        elif d == "left":
            s.set_at((hx + 1, hy + 4), eye)
        elif d == "right":
            s.set_at((hx + 6, hy + 4), eye)
        if race == "kethari" and d != "up":
            for px, py in ((hx + 1, hy + 6), (hx + 6, hy + 5), (hx + 3, hy + 7)):
                s.set_at((px, py), _shade(skin, 0.7))
        return s

    # ================================================================== creatures / combat
    def combatant(self, look, direction, frame, action=False):
        shape = look.get("shape", "humanoid")
        if shape in ("humanoid", None):
            img = self.character({k: v for k, v in look.items() if k not in ("shape", "hood")}, direction, frame, action)
            if look.get("hood"):
                return self._get(("hooded", tuple(look["shirt"]), direction, frame, action),
                                 lambda: self._hood(img, look, direction))
            return img
        if shape == "brute":
            base = self.character({k: v for k, v in look.items() if k not in ("shape", "hood")}, direction, frame, action)
            return self._get(("brute", tuple(look["shirt"]), direction, frame, action),
                             lambda: pygame.transform.scale(base, (24, 36)))
        key = ("creature", shape, tuple(look["shirt"]), direction, frame % 4)
        return self._get(key, lambda: _outline(self._make_creature(shape, tuple(look["shirt"]), direction, frame % 4)))

    def _hood(self, img, look, d):
        s = img.copy()
        col = _shade(tuple(look["shirt"]), 0.8)
        pygame.draw.rect(s, col, (4, 1, 10, 3))
        if d == "up":
            pygame.draw.rect(s, col, (4, 1, 10, 9))
        elif d == "left":
            pygame.draw.rect(s, col, (8, 1, 6, 9))
        elif d == "right":
            pygame.draw.rect(s, col, (3, 1, 6, 9))
        else:
            pygame.draw.rect(s, col, (4, 1, 2, 8))
            pygame.draw.rect(s, col, (12, 1, 2, 8))
        return s

    def _make_creature(self, shape, col, d, frame):
        dark, light = _shade(col, 0.7), _shade(col, 1.2)
        step = (0, 1, 0, -1)[frame]
        if shape == "beast":
            s = pygame.Surface((22, 16), pygame.SRCALPHA)
            if d in ("left", "right"):
                pygame.draw.ellipse(s, col, (3, 5, 13, 7))
                pygame.draw.line(s, dark, (3, 7), (0, 4 + step), 2)          # tail
                for lx, o in ((5, step), (8, -step), (11, step), (14, -step)):
                    pygame.draw.rect(s, dark, (lx, 11, 2, 4 + o if o > 0 else 4))
                pygame.draw.circle(s, col, (17, 6), 4)
                pygame.draw.rect(s, light, (19, 6, 3, 2))                     # snout
                pygame.draw.polygon(s, dark, [(15, 3), (16, 0), (18, 3)])      # ear
                s.set_at((18, 5), (20, 20, 20))
                if d == "left":
                    s = pygame.transform.flip(s, True, False)
            else:
                pygame.draw.ellipse(s, col, (6, 2, 10, 13))
                for lx, o in ((6, step), (14, -step)):
                    pygame.draw.rect(s, dark, (lx, 4 + o, 2, 3))
                    pygame.draw.rect(s, dark, (lx, 11 - o, 2, 3))
                hy = 12 if d == "down" else 2
                pygame.draw.circle(s, col, (11, hy), 4)
                pygame.draw.polygon(s, dark, [(7, hy - 3), (8, hy - 6), (10, hy - 3)])
                pygame.draw.polygon(s, dark, [(12, hy - 3), (14, hy - 6), (15, hy - 3)])
                if d == "down":
                    s.set_at((9, hy), (20, 20, 20))
                    s.set_at((13, hy), (20, 20, 20))
            return s
        if shape == "dummy":
            s = pygame.Surface((16, 24), pygame.SRCALPHA)
            pygame.draw.rect(s, (110, 80, 50), (7, 10, 2, 14))
            pygame.draw.rect(s, (110, 80, 50), (2, 11, 12, 2))
            pygame.draw.ellipse(s, col, (4, 7, 8, 10))
            pygame.draw.circle(s, (200, 170, 110), (8, 5), 4)
            pygame.draw.line(s, (150, 40, 40), (6, 11), (10, 15))
            pygame.draw.line(s, (150, 40, 40), (10, 11), (6, 15))
            return s
        if shape == "bug":
            s = pygame.Surface((16, 14), pygame.SRCALPHA)
            for i in range(3):
                o = step if i % 2 else -step
                pygame.draw.line(s, dark, (3, 4 + i * 3), (0, 3 + i * 3 + o))
                pygame.draw.line(s, dark, (12, 4 + i * 3), (15, 3 + i * 3 - o))
            pygame.draw.ellipse(s, col, (3, 2, 10, 11))
            pygame.draw.line(s, dark, (8, 2), (8, 12))
            pygame.draw.circle(s, light, (5, 5), 1)
            return s
        if shape == "worm":
            s = pygame.Surface((24, 16), pygame.SRCALPHA)
            for i in range(5):
                x = 3 + i * 4
                y = 9 + int(2 * math.sin(i + frame))
                pygame.draw.circle(s, col if i % 2 else dark, (x, y), 4 - (1 if i == 0 else 0))
            pygame.draw.circle(s, light, (20, 7), 4)
            pygame.draw.line(s, (240, 230, 210), (22, 8), (23, 10))
            if d == "left":
                s = pygame.transform.flip(s, True, False)
            return s
        s = pygame.Surface((16, 16), pygame.SRCALPHA)
        s.fill(col)
        return s

    def _make_base(self, t, variant, extra):
        wood, dark, roof = (150, 108, 64), (96, 66, 40), (120, 60, 44)
        if t == "plot":
            s = pygame.Surface((T, T), pygame.SRCALPHA)
            for x, y in ((1, 1), (13, 1), (1, 13), (13, 13)):
                pygame.draw.rect(s, dark, (x, y, 2, 3))
            pygame.draw.rect(s, (220, 200, 140), (2, 2, 12, 12), 1)
            return s
        if t == "construction":
            s = pygame.Surface((28, 24), pygame.SRCALPHA)
            pygame.draw.line(s, wood, (2, 23), (14, 2), 2)
            pygame.draw.line(s, wood, (26, 23), (14, 2), 2)
            pygame.draw.line(s, wood, (6, 14), (22, 14), 2)
            pygame.draw.rect(s, (130, 126, 120), (4, 18, 8, 5))
            return s
        if t == "farm":
            s = pygame.Surface((28, 20), pygame.SRCALPHA)
            pygame.draw.rect(s, (112, 80, 50), (0, 4, 28, 16))
            for y in range(6, 20, 4):
                pygame.draw.line(s, (90, 62, 40), (1, y), (26, y))
            if extra:
                col = (200, 180, 80) if extra == "ripe" else (90, 150, 70)
                h = 5 if extra == "ripe" else 3
                for x in range(3, 27, 4):
                    for y in range(8, 20, 4):
                        pygame.draw.line(s, col, (x, y), (x, y - h))
            return s
        body = {"storage": ((24, 22), (140, 100, 60)), "workshop": ((30, 26), (130, 120, 110)),
                "bunkhouse": ((32, 24), (160, 130, 90)), "trading": ((30, 24), (170, 140, 90)),
                "research": ((22, 34), (120, 110, 140)), "training": ((30, 20), wood),
                "well": ((16, 22), (120, 120, 125)), "palisade": ((32, 22), wood), "watchtower": ((18, 40), wood)}
        (w, h), col = body.get(t, ((24, 24), wood))
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        if t == "palisade":
            for x in range(0, w, 4):
                pygame.draw.rect(s, wood, (x, 4, 3, h - 4))
                pygame.draw.polygon(s, wood, [(x, 4), (x + 1, 0), (x + 3, 4)])
            pygame.draw.line(s, dark, (0, 10), (w, 10), 2)
            return s
        if t == "watchtower":
            for x in (2, w - 4):
                pygame.draw.rect(s, dark, (x, 10, 2, h - 10))
            pygame.draw.line(s, dark, (2, 22), (w - 3, 34), 1)
            pygame.draw.rect(s, wood, (0, 6, w, 6))
            pygame.draw.polygon(s, roof, [(0, 6), (w // 2, 0), (w, 6)])
            return s
        if t == "training":
            pygame.draw.ellipse(s, (180, 160, 120), (0, 6, w, h - 6), 1)
            pygame.draw.rect(s, dark, (6, 4, 2, 14))
            pygame.draw.rect(s, (170, 130, 80), (3, 6, 8, 3))
            pygame.draw.rect(s, dark, (20, 4, 2, 14))
            pygame.draw.rect(s, (170, 130, 80), (17, 6, 8, 3))
            return s
        if t == "well":
            return self._make_obj("well", 0, "grassland", None)
        wall_h = h // 2
        pygame.draw.rect(s, col, (1, h - wall_h, w - 2, wall_h))
        pygame.draw.polygon(s, roof if t != "research" else (70, 60, 120), [(0, h - wall_h), (w // 2, 0 if t != "research" else 4), (w, h - wall_h)])
        pygame.draw.rect(s, dark, (w // 2 - 2, h - 7, 5, 7))
        if t == "trading":
            for x in range(0, w, 6):
                pygame.draw.rect(s, (200, 60, 60) if (x // 6) % 2 else (240, 230, 210), (x, h - wall_h - 2, 6, 3))
        if t == "workshop":
            pygame.draw.rect(s, (90, 90, 96), (w - 7, 0, 4, h - wall_h))
            pygame.draw.circle(s, (240, 140, 50), (6, h - 5), 2)
        if t == "storage":
            pygame.draw.rect(s, (160, 120, 70), (3, h - 6, 6, 5))
        if t in ("bunkhouse", "research"):
            pygame.draw.rect(s, (240, 210, 120), (4, h - wall_h + 3, 4, 3))
            pygame.draw.rect(s, (240, 210, 120), (w - 8, h - wall_h + 3, 4, 3))
        if extra == "damaged":
            pygame.draw.line(s, (30, 20, 20), (3, h - wall_h), (w - 4, h - 2), 2)
            pygame.draw.line(s, (30, 20, 20), (w - 4, h - wall_h), (5, h - 3), 2)
        return s

    def white(self, img):
        """Solid white silhouette used for hit flashes."""
        return self._get(("white", id(img)), lambda: pygame.mask.from_surface(img).to_surface(
            setcolor=(255, 255, 255, 230), unsetcolor=(0, 0, 0, 0)))

    def pickup(self, item_type):
        def make():
            s = pygame.Surface((8, 8), pygame.SRCALPHA)
            col = {"marks": (240, 200, 80), "weapon": (200, 200, 210), "ore": (180, 120, 80), "food": (200, 80, 60),
                   "valuable": (120, 220, 220), "magic": (160, 120, 240)}.get(item_type, (200, 180, 140))
            pygame.draw.circle(s, _shade(col, 0.6), (4, 5), 3)
            pygame.draw.circle(s, col, (4, 4), 3)
            s.set_at((3, 3), (255, 255, 255))
            return s
        return self._get(("pickup", item_type), make)

    # ================================================================== misc
    def light(self, radius):
        def make():
            s = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
            s.fill((255, 255, 255, 255))  # outside the circle: leave darkness untouched (MIN blend)
            for rr in range(radius, 0, -2):
                a = int(255 * (rr / radius) ** 1.5)
                pygame.draw.circle(s, (255, 255, 255, a), (radius, radius), rr)
            return s
        return self._get(("light", radius), make)

    def shadow(self, w=12):
        def make():
            s = pygame.Surface((w, 4), pygame.SRCALPHA)
            pygame.draw.ellipse(s, (0, 0, 0, 70), (0, 0, w, 4))
            return s
        return self._get(("shadow", w), make)


def _outline(surf):
    """Add a 1px dark outline around the opaque pixels of a sprite."""
    w, h = surf.get_size()
    out = pygame.Surface((w, h), pygame.SRCALPHA)
    mask = pygame.mask.from_surface(surf)
    olay = mask.to_surface(setcolor=OUTLINE + (255,), unsetcolor=(0, 0, 0, 0))
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        out.blit(olay, (dx, dy))
    out.blit(surf, (0, 0))
    return out


def random_look(race_data, rng, race_id, role="citizen"):
    """A varied look (hair, clothes, accessories) for a new character or an anonymous townsperson."""
    from .looks import build
    return build(rng, race_data, race_id, role, None, rng.randint(18, 60), "they/them")


def npc_look(data, npc):
    """Named NPCs: an identity built from occupation, faction, age, pronouns and personality (see looks.py)."""
    from .looks import npc_identity
    return npc_identity(data, npc)
