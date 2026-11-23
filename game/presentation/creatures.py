"""Animated non-humanoid enemies, drawn procedurally in the same outlined pixel style as the pack art.

Every creature has: idle (breathing), move (gait cycle), windup (anticipation), strike, hit (recoil) and
death (collapse). Sprites face right; the caller mirrors them for left. Larger enemies are drawn larger
so threat is readable at a glance. Husks use the pack's skeleton animations.
"""
import math

import pygame

from . import assets

OUT = (12, 10, 14)
SKEL = "Entities/Mobs/Skeleton Crew/Skeleton - Base/"
_cache = {}


def _shade(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c)


def _outline(s):
    w, h = s.get_size()
    out = pygame.Surface((w, h), pygame.SRCALPHA)
    sil = pygame.mask.from_surface(s, 1).to_surface(setcolor=(*OUT, 255), unsetcolor=(0, 0, 0, 0))
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        out.blit(sil, (dx, dy))
    out.blit(s, (0, 0))
    return out


def frame(shape, color, anim, idx):
    """Surface for a creature pose (cached)."""
    key = (shape, tuple(color), anim, idx)
    if key not in _cache:
        fn = DRAW.get(shape, _wolf)
        _cache[key] = _outline(fn(tuple(color), anim, idx))
    return _cache[key]


FRAMES = {"idle": 4, "move": 4, "windup": 2, "strike": 2, "hit": 2, "death": 4}


def _pose(anim, idx):
    """Shared pose parameters: bob, lean (+forward), reach, legphase, open (jaw/arm), lie (0..1)."""
    t = idx / max(1, FRAMES[anim])
    p = {"bob": 0, "lean": 0, "reach": 0, "leg": 0.0, "open": 0, "lie": 0.0, "eyes": 1}
    if anim == "idle":
        p["bob"] = (0, 0, 1, 1)[idx % 4]
    elif anim == "move":
        p["leg"] = idx * math.pi / 2
        p["bob"] = (0, 1, 0, 1)[idx % 4]
    elif anim == "windup":
        p["lean"] = -2 - idx
        p["bob"] = 1
        p["open"] = 1 + idx
    elif anim == "strike":
        p["lean"] = 3 + 2 * idx
        p["reach"] = 4 + 2 * idx
        p["open"] = 3
    elif anim == "hit":
        p["lean"] = -3
        p["eyes"] = 0
    elif anim == "death":
        p["lie"] = min(1.0, (idx + 1) / 3)
        p["eyes"] = 0
    return p


# ----------------------------------------------------------------------------- wolf (and ice wolf)
def _wolf(col, anim, idx):
    p = _pose(anim, idx)
    s = pygame.Surface((34, 24), pygame.SRCALPHA)
    dark, light = _shade(col, 0.62), _shade(col, 1.25)
    ox = 3 + p["lean"]
    by = 9 + p["bob"]
    if p["lie"] >= 1:
        pygame.draw.ellipse(s, col, (ox + 2, 13, 22, 8))
        pygame.draw.ellipse(s, light, (ox + 4, 13, 16, 3))
        pygame.draw.circle(s, col, (ox + 25, 16), 4)
        for k in range(4):
            pygame.draw.line(s, dark, (ox + 6 + k * 4, 13), (ox + 4 + k * 4, 9), 2)
        pygame.draw.line(s, dark, (ox + 2, 17), (ox - 2, 20), 2)
        return s
    # legs (back pair darker, behind)
    for i, (x, ph) in enumerate(((ox + 7, 0), (ox + 19, math.pi), (ox + 9, math.pi), (ox + 21, 0))):
        sw = int(round(2.5 * math.sin(p["leg"] + ph)))
        c = dark if i < 2 else col
        reach = p["reach"] if i >= 2 else 0
        pygame.draw.line(s, c, (x, by + 5), (x + sw + reach // 2, by + 11), 3)
        pygame.draw.line(s, OUT, (x + sw + reach // 2 - 1, by + 12), (x + sw + reach // 2 + 1, by + 12))
    # tail
    tail_up = 2 if anim in ("windup", "idle") else 0
    pygame.draw.line(s, dark, (ox + 3, by + 2), (ox - 2, by - 2 - tail_up), 3)
    pygame.draw.line(s, light, (ox - 2, by - 3 - tail_up), (ox - 3, by - 4 - tail_up), 1)
    # body
    pygame.draw.ellipse(s, col, (ox + 2, by - 1, 20 + p["reach"] // 2, 10))
    pygame.draw.ellipse(s, light, (ox + 5, by - 1, 14, 3))
    pygame.draw.ellipse(s, dark, (ox + 6, by + 5, 12, 4))
    # head
    hx, hy = ox + 22 + p["reach"], by - 3 + (1 if anim == "windup" else 0)
    pygame.draw.circle(s, col, (hx, hy + 3), 5)
    pygame.draw.polygon(s, col, [(hx + 2, hy + 1), (hx + 9, hy + 3), (hx + 9, hy + 5), (hx + 2, hy + 7)])
    if p["open"]:
        pygame.draw.polygon(s, (120, 30, 30), [(hx + 3, hy + 5), (hx + 9, hy + 5 + p["open"] // 2), (hx + 3, hy + 7)])
        pygame.draw.line(s, (240, 240, 230), (hx + 5, hy + 5), (hx + 8, hy + 5))
    pygame.draw.polygon(s, dark, [(hx - 3, hy), (hx - 1, hy - 5), (hx + 1, hy)])
    pygame.draw.polygon(s, col, [(hx, hy), (hx + 2, hy - 4), (hx + 3, hy)])
    s.set_at((hx + 9, hy + 3), OUT)
    if p["eyes"]:
        s.set_at((hx + 3, hy + 2), (250, 230, 120) if anim in ("windup", "strike") else (20, 20, 20))
    return s


# ----------------------------------------------------------------------------- skitterer (cave bug)
def _bug(col, anim, idx):
    p = _pose(anim, idx)
    s = pygame.Surface((24, 18), pygame.SRCALPHA)
    dark, light = _shade(col, 0.6), _shade(col, 1.35)
    ox = 3 + p["lean"]
    by = 7 + p["bob"]
    if p["lie"] >= 1:
        pygame.draw.ellipse(s, dark, (ox + 2, 9, 14, 7))
        for k in range(3):
            pygame.draw.line(s, dark, (ox + 5 + k * 4, 9), (ox + 4 + k * 4, 4), 1)
        return s
    for k in range(3):
        sw = int(round(2 * math.sin(p["leg"] + k * 2.1)))
        x = ox + 5 + k * 4
        pygame.draw.line(s, dark, (x, by + 4), (x - 2 + sw, by + 9), 1)
        pygame.draw.line(s, dark, (x + 1, by + 4), (x + 3 - sw, by + 9), 1)
    pygame.draw.ellipse(s, col, (ox + 2, by - 1, 15, 9))
    pygame.draw.line(s, dark, (ox + 9, by - 1), (ox + 9, by + 7))
    pygame.draw.ellipse(s, light, (ox + 4, by, 4, 2))
    pygame.draw.circle(s, col, (ox + 17 + p["reach"] // 2, by + 3), 3)
    m = 1 + p["open"]
    hx = ox + 19 + p["reach"] // 2
    pygame.draw.line(s, (200, 190, 160), (hx, by + 2), (hx + 3, by + 2 - m // 2))
    pygame.draw.line(s, (200, 190, 160), (hx, by + 4), (hx + 3, by + 4 + m // 2))
    if p["eyes"]:
        s.set_at((hx - 1, by + 2), (220, 60, 60))
    return s


# ----------------------------------------------------------------------------- sand wurm
def _worm(col, anim, idx):
    p = _pose(anim, idx)
    s = pygame.Surface((36, 30), pygame.SRCALPHA)
    dark, light = _shade(col, 0.6), _shade(col, 1.25)
    rise = {"windup": 6 + idx * 2, "strike": 4, "idle": 2, "hit": 1}.get(anim, 0)
    if p["lie"] >= 1:
        for k in range(6):
            pygame.draw.circle(s, dark if k % 2 else col, (4 + k * 5, 24), 4)
        return s
    phase = idx * 0.9
    pts = []
    for k in range(7):
        x = 3 + k * 4 + (p["reach"] if k > 3 else 0)
        y = 22 - int(3 * math.sin(phase + k * 0.9)) - (rise * k // 6 if k >= 4 else 0)
        pts.append((x, y))
    for k, (x, y) in enumerate(pts[:-1]):
        r = 4 + (1 if 2 <= k <= 4 else 0)
        pygame.draw.circle(s, dark if k % 2 else col, (x, y), r)
        pygame.draw.circle(s, light, (x - 1, y - 2), 1)
    hx, hy = pts[-1]
    pygame.draw.circle(s, col, (hx, hy), 5)
    open_ = 1 + p["open"]
    pygame.draw.circle(s, (90, 30, 30), (hx + 3, hy), open_)
    for a in range(0, 360, 60):
        ex = hx + 3 + int((open_ + 1) * math.cos(math.radians(a)))
        ey = hy + int((open_ + 1) * math.sin(math.radians(a)))
        s.set_at((ex, ey), (240, 235, 215))
    return s


# ----------------------------------------------------------------------------- brutes: stone / bog / crystal
def _brute(col, anim, idx, kind="stone"):
    p = _pose(anim, idx)
    s = pygame.Surface((40, 40), pygame.SRCALPHA)
    dark, light = _shade(col, 0.6), _shade(col, 1.3)
    ox = 8 + p["lean"] // 2
    by = 12 + p["bob"]
    if p["lie"] >= 1:
        pygame.draw.ellipse(s, col, (4, 26, 30, 11))
        pygame.draw.ellipse(s, dark, (8, 30, 22, 6))
        if kind == "crystal":
            for k in range(3):
                pygame.draw.polygon(s, light, [(10 + k * 7, 28), (12 + k * 7, 22), (14 + k * 7, 28)])
        return s
    raise_ = {"windup": 8 + 2 * idx, "strike": -4, "idle": 0, "move": 0, "hit": 2}.get(anim, 0)
    # legs
    for k, ph in ((0, 0), (1, math.pi)):
        sw = int(round(2 * math.sin(p["leg"] + ph)))
        pygame.draw.rect(s, dark if k == 0 else col, (ox + 5 + k * 10 + sw, by + 17, 6, 9), border_radius=2)
    # body
    if kind == "crystal":
        body = [(ox + 2, by + 18), (ox + 4, by + 4), (ox + 12, by - 2), (ox + 22, by + 4), (ox + 24, by + 18), (ox + 13, by + 22)]
        pygame.draw.polygon(s, col, body)
        pygame.draw.polygon(s, light, [(ox + 4, by + 5), (ox + 12, by - 1), (ox + 13, by + 10)])
        pygame.draw.line(s, dark, (ox + 13, by + 10), (ox + 13, by + 21))
        glow = (255, 255, 255) if idx % 2 else (200, 250, 255)
        pygame.draw.circle(s, glow, (ox + 13, by + 11), 2)
        for sx in (ox + 1, ox + 23):
            pygame.draw.polygon(s, light, [(sx - 2, by + 6), (sx, by - 2), (sx + 2, by + 6)])
    else:
        pygame.draw.ellipse(s, col, (ox, by, 26, 22))
        pygame.draw.ellipse(s, light, (ox + 4, by + 2, 14, 6))
        pygame.draw.ellipse(s, dark, (ox + 4, by + 14, 18, 7))
        if kind == "stone":
            pygame.draw.line(s, dark, (ox + 8, by + 5), (ox + 12, by + 12))
            pygame.draw.line(s, dark, (ox + 12, by + 12), (ox + 10, by + 17))
            pygame.draw.circle(s, col, (ox + 13, by - 2), 5)
        else:  # bog lurker: moss and drips
            for mx, my in ((ox + 5, by + 3), (ox + 15, by + 1), (ox + 20, by + 8)):
                pygame.draw.circle(s, (70, 120, 60), (mx, my), 3)
            pygame.draw.line(s, (90, 140, 90), (ox + 7, by + 20), (ox + 7, by + 24))
            pygame.draw.circle(s, col, (ox + 17, by + 2), 6)
    # eyes
    eye = {"stone": (255, 160, 60), "bog": (230, 230, 80), "crystal": (255, 255, 255)}[kind]
    if p["eyes"]:
        ex, ey = (ox + 15, by - 3) if kind == "stone" else (ox + 18, by + 1) if kind == "bog" else (ox + 15, by + 4)
        s.set_at((ex, ey), eye)
        s.set_at((ex + 2, ey), eye)
    # arms / fists
    arm_y = by + 6 - raise_
    fx = ox + 24 + p["reach"]
    pygame.draw.line(s, dark, (ox + 20, by + 7), (fx, arm_y + 6), 4)
    pygame.draw.circle(s, col if kind != "crystal" else light, (fx + 1, arm_y + 7), 4 if kind != "bog" else 3)
    pygame.draw.line(s, dark, (ox + 2, by + 8), (ox - 2, by + 14 - raise_ // 2), 4)
    pygame.draw.circle(s, dark, (ox - 2, by + 15 - raise_ // 2), 3)
    return s


def _stone(c, a, i):
    return _brute(c, a, i, "stone")


def _bog(c, a, i):
    return _brute(c, a, i, "bog")


def _crystal(c, a, i):
    return _brute(c, a, i, "crystal")


def _dummy(col, anim, idx):
    s = pygame.Surface((18, 26), pygame.SRCALPHA)
    wob = (-1, 1)[idx % 2] if anim == "hit" else 0
    pygame.draw.rect(s, (100, 70, 45), (8, 12, 2, 14))
    pygame.draw.rect(s, (110, 80, 50), (2 + wob, 13, 14, 2))
    pygame.draw.ellipse(s, col, (4 + wob, 9, 10, 12))
    pygame.draw.circle(s, (205, 175, 115), (9 + wob, 6), 4)
    pygame.draw.line(s, (150, 40, 40), (6 + wob, 12), (11 + wob, 17))
    pygame.draw.line(s, (150, 40, 40), (11 + wob, 12), (6 + wob, 17))
    return s


DRAW = {"beast": _wolf, "bug": _bug, "worm": _worm, "brute": _stone, "bog": _bog, "crystal": _crystal,
        "dummy": _dummy}


def shape_for(enemy_id, enemy):
    if enemy_id in ("bog_lurker",):
        return "bog"
    if enemy_id in ("crystal_golem",):
        return "crystal"
    if enemy.get("training"):
        return "dummy"
    return enemy.get("shape", "beast")


def creature_anim(c):
    """(anim, frame index) from a combatant's state for creature rigs."""
    st = c.state
    if st == "dead":
        return "death", min(3, int(c.dead_t / 0.12))
    if st == "stagger" or (c.flash > 0 and st == "idle"):
        return "hit", int(c.state_t * 12) % 2
    if st == "windup":
        return "windup", min(1, int(2 * c.state_t / max(0.01, (c.profile or {}).get("windup", 0.3))))
    if st == "active":
        return "strike", 1
    if st == "recovery":
        return "strike", 0
    if c.moving:
        return "move", int(c.anim_t * 10) % 4
    return "idle", int((c.cid * 0.37 + c.state_t) * 4) % 4


# ----------------------------------------------------------------------------- husk = pack skeleton
def skeleton(anim, idx):
    try:
        if anim == "death":
            fr = assets.frames(SKEL + "Death/Death-Sheet.png", 64, 64)
            return fr[min(len(fr) - 1, idx * 3)], 64
        if anim == "move":
            fr = assets.frames(SKEL + "Run/Run-Sheet.png", 64, 64)
            return fr[idx % len(fr)], 64
        fr = assets.frames(SKEL + "Idle/Idle-Sheet.png", 32, 32)
        return fr[idx % len(fr)], 32
    except (FileNotFoundError, pygame.error):
        return None, 0
