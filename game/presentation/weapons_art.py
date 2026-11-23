"""Equipped-weapon sprites: one per (weapon type, ore), drawn pointing *up* with the grip at the bottom.

Most silhouettes come from the Pixel Crawler wooden weapon sheet; the striking part (blade / head) is
recoloured to the ore's metal so Rustite, Greyvein, Sunsilver and Voidglass gear are told apart at a
glance. Crossbow, knuckles and firelock are drawn procedurally in the same style.
"""
import math

import pygame

from . import assets

# weapon type -> (pack sprite or None, target length in px, fraction of the sprite that is "head")
STYLE = {
    "dagger": ("w_dagger", 12, 0.6), "shortsword": ("w_sword", 17, 0.68), "longsword": ("w_sword", 22, 0.7),
    "greatsword": ("w_sword", 28, 0.72), "axe": ("w_axe", 17, 0.45), "battleaxe": ("w_axe", 24, 0.45),
    "spear": ("w_spear", 30, 0.25), "polearm": ("w_warhammer", 28, 0.35), "hammer": ("w_mallet", 22, 0.4),
    "mace": ("w_mallet", 16, 0.42), "bow": ("w_bow", 20, 1.0), "throwing": ("w_dagger", 9, 0.6),
    "knuckles": (None, 7, 1.0), "crossbow": (None, 15, 1.0), "firelock": (None, 18, 1.0),
    "pickaxe": ("w_pickaxe", 16, 0.35), "hatchet": ("w_axe", 13, 0.45), "fists": (None, 0, 0),
}
ORE_COLOR = {"rustite": (176, 98, 62), "greyvein": (168, 176, 188), "sunsilver": (236, 214, 120),
             "voidglass": (126, 80, 190), None: (180, 182, 190)}
OUT = (0, 0, 0)
_cache = {}


def _is_grip_wrap(c):
    return c[0] >= 200 and c[1] >= 200 and c[2] >= 190


def _from_pack(name, length, head_frac, metal):
    src = assets.sprite(name)
    w, h = src.get_size()
    scale = length / h
    if abs(scale - 1) > 0.08:
        src = pygame.transform.scale(src, (max(3, round(w * scale)), max(4, round(h * scale))))
        w, h = src.get_size()
    out = src.copy()
    ramp = assets.ramp(metal, 6)
    cut = h * head_frac
    for y in range(h):
        for x in range(w):
            c = out.get_at((x, y))
            if not c.a or (c.r, c.g, c.b) == OUT or c.r + c.g + c.b < 60:
                continue
            if head_frac >= 1.0 or y < cut:
                if _is_grip_wrap((c.r, c.g, c.b)) and head_frac < 1.0:
                    continue
                L = assets.luminance(c)
                i = int(max(0, min(5, (L - 50) / 170 * 6)))
                out.set_at((x, y), (*ramp[i], 255))
    # a bright edge glint makes metal read as metal
    for y in range(int(cut) if head_frac < 1 else h):
        for x in range(w):
            c = out.get_at((x, y))
            if c.a and (c.r, c.g, c.b) != OUT and x + 1 < w and out.get_at((x + 1, y)).a and \
                    (out.get_at((x + 1, y))[:3] == OUT) and y % 3 == 0:
                out.set_at((x, y), (*[min(255, v + 70) for v in metal], 255))
    return out


def _procedural(wtype, metal):
    dark = tuple(int(v * 0.6) for v in metal)
    wood = (120, 78, 44)
    if wtype == "knuckles":
        s = pygame.Surface((7, 7), pygame.SRCALPHA)
        pygame.draw.rect(s, metal, (1, 1, 5, 3))
        for x in (1, 3, 5):
            s.set_at((x, 1), tuple(min(255, v + 60) for v in metal))
        pygame.draw.rect(s, dark, (2, 4, 3, 2))
    elif wtype == "crossbow":
        s = pygame.Surface((13, 15), pygame.SRCALPHA)
        pygame.draw.line(s, wood, (6, 14), (6, 3), 3)
        pygame.draw.arc(s, metal, (0, 0, 13, 8), 0, math.pi, 2)
        pygame.draw.line(s, (220, 220, 210), (1, 4), (11, 4))
        pygame.draw.rect(s, dark, (5, 9, 3, 2))
    elif wtype == "firelock":
        s = pygame.Surface((7, 18), pygame.SRCALPHA)
        pygame.draw.rect(s, wood, (2, 10, 4, 8))
        pygame.draw.rect(s, metal, (2, 0, 3, 11))
        pygame.draw.rect(s, dark, (1, 0, 5, 2))
        s.set_at((3, 1), (30, 30, 30))
        pygame.draw.rect(s, dark, (1, 10, 2, 2))
    else:
        return None
    return _outlined(s)


def _outlined(s):
    w, h = s.get_size()
    out = pygame.Surface((w + 2, h + 2), pygame.SRCALPHA)
    m = pygame.mask.from_surface(s, 1)
    sil = m.to_surface(setcolor=(*OUT, 255), unsetcolor=(0, 0, 0, 0))
    for dx, dy in ((0, 1), (2, 1), (1, 0), (1, 2)):
        out.blit(sil, (dx, dy))
    out.blit(s, (1, 1))
    return out


def sprite(wtype, ore=None):
    """Upright weapon sprite (grip at the bottom centre) or None for fists."""
    key = (wtype, ore)
    if key not in _cache:
        name, length, frac = STYLE.get(wtype, (None, 0, 0))
        metal = ORE_COLOR.get(ore, ORE_COLOR[None])
        if name:
            try:
                _cache[key] = _from_pack(name, length, frac, metal)
            except (KeyError, FileNotFoundError, pygame.error):
                _cache[key] = None
        elif length:
            _cache[key] = _procedural(wtype, metal)
        else:
            _cache[key] = None
    return _cache[key]


def posed(wtype, ore, angle_deg, flip=False):
    """Rotated weapon (cached by 15-degree steps) and the grip's offset inside the rotated image."""
    a = int(round(angle_deg / 15.0)) * 15 % 360
    key = (wtype, ore, a, flip)
    if key not in _cache:
        base = sprite(wtype, ore)
        if base is None:
            _cache[key] = None
        else:
            if flip:
                base = pygame.transform.flip(base, True, False)
            w, h = base.get_size()
            grip = pygame.math.Vector2(0, h / 2 - 2)        # grip near the bottom, relative to centre
            rot = pygame.transform.rotate(base, a)
            g = grip.rotate(-a)
            _cache[key] = (rot, (rot.get_width() / 2 + g.x, rot.get_height() / 2 + g.y))
    return _cache[key]


def angle_for(dx, dy):
    """Rotation (degrees, pygame CCW) that turns an upright sprite to point along (dx, dy)."""
    return math.degrees(math.atan2(-dx, -dy))
