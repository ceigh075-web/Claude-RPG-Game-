"""Chooses animations from actors' existing (gameplay) state and produces depth-sorted sprite entries.

Read-only with respect to gameplay: it only inspects Actor / Combatant fields (state, state_t, profile,
moving, anim_t, facing, aim, flash, dead_t, blocking, charge, action) and never changes them.
"""
import math

import pygame

from . import charsprites as cs
from . import weapons_art as wa

SLICE = {"shortsword", "longsword", "greatsword", "axe", "battleaxe", "polearm"}
CRUSH = {"hammer", "mace"}
RANGED = {"bow", "crossbow", "throwing", "firelock"}
SMEAR_SCALE = {"dagger": 0.8, "shortsword": 0.95, "longsword": 1.1, "greatsword": 1.35, "axe": 1.0,
               "battleaxe": 1.3, "polearm": 1.3, "hammer": 1.2, "mace": 1.0, "fists": 0.7, "knuckles": 0.75, "kick": 0.8}
_scaled = {}


def attack_kind(weapon):
    if weapon in SLICE:
        return "slice"
    if weapon in CRUSH:
        return "crush"
    return "pierce"


def _phase_frame(c):
    """Map attack phases onto the 8-frame attack sheets: anticipation 0-2, strike 3-4, follow-through 5-7."""
    p = c.profile
    st, t = c.state, c.state_t
    if st == "windup":
        return min(2, int(3 * t / max(0.01, p.get("windup", 0.2))))
    if st == "active":
        return 3 + min(1, int(2 * t / max(0.01, p.get("active", 0.1))))
    return 5 + min(2, int(3 * t / max(0.01, p.get("recovery", 0.2))))


def choose(a, t):
    """(anim, frame) for an actor at time t."""
    st = getattr(a, "state", None)
    if st == "dead":
        return "death", min(7, int(getattr(a, "dead_t", 0) / 0.09))
    if st == "stagger":
        return "hit", min(3, int(a.state_t / 0.08))
    if getattr(a, "flash", 0) > 0 and st in (None, "idle"):
        return "hit", 1
    prof = getattr(a, "profile", None)
    if st in ("windup", "active", "recovery") and prof:
        return attack_kind(prof.get("weapon", "fists")), _phase_frame(a)
    if st == "draw":
        return "pierce", 1 + int(t * 6) % 2
    if st == "cast":
        return "crush", min(3, int(a.state_t / 0.07))
    if getattr(a, "blocking", False):
        return "pierce", 0
    if st == "dodge":
        return "run", int(a.state_t * 24) % 6
    act = getattr(a, "action_kind", None)
    if getattr(a, "action", False) and act:
        return {"mine": "crush", "chop": "slice", "gather": "collect"}.get(act, "collect"), int(t * 10) % 8
    if getattr(a, "moving", False):
        fast = getattr(a, "speed", 60) > 105
        return ("run" if fast else "walk"), int(getattr(a, "anim_t", 0) * (11 if fast else 9)) % 6
    return "idle", int(t * 5 + (id(a) % 7)) % 4


def _smear(smear, scale, tint):
    key = (id(smear), round(scale, 2), tint)
    if key not in _scaled:
        s = smear
        if abs(scale - 1) > 0.03:
            s = pygame.transform.scale(smear, (int(64 * scale), int(64 * scale)))
        if tint:
            s = s.copy()
            s.fill((*tint, 255), special_flags=pygame.BLEND_RGBA_MULT)
        _scaled[key] = s
    return _scaled[key]


def humanoid_entries(a, look, weapon, t, camx, camy, art, white_fn):
    """Sprite entries (sort_y, surface, x, y) for a humanoid. weapon = (type, ore) or None."""
    anim, frame = choose(a, t)
    d = a.facing
    surf, smear, info = cs.compose(look, anim, d, frame)
    fx = a.x - 32 - camx
    fy = a.y - cs.FOOT_Y - camy
    if getattr(a, "state", None) == "stagger":
        fx += math.sin(t * 70) * 1.2
    entries = []
    dead = getattr(a, "state", None) == "dead"
    alpha = 255
    if dead:
        alpha = max(0, int(255 * (1 - max(0.0, a.dead_t - 0.8) / 0.8)))
    # weapon
    wtype, ore = weapon if weapon else (None, None)
    if anim in ("slice", "pierce", "crush", "collect") and getattr(a, "state", None) == "cast":
        wtype = None  # hands free while casting
    wsurf = None
    if wtype and wtype not in ("fists",) and not dead:
        if info.grip and anim in ("slice", "pierce", "crush"):
            gx, gy = info.grip
            tx, ty = info.tip
            if d == "left":
                gx, tx = 63 - gx, 63 - tx
            ang = wa.angle_for(tx - gx, ty - gy)
            if wtype == "bow":
                ang += 90 if d != "left" else -90
            p = wa.posed(wtype, ore, ang)
            if p:
                wsurf, (ox, oy) = p
                wx, wy = fx + gx - ox, fy + gy - oy
                order = -0.2 if d == "up" else 0.05
                entries.append((a.y + order, wsurf, int(wx), int(wy)))
        elif anim in ("idle", "walk", "run", "hit"):
            # carried on the back: diagonal, visible behind the shoulders
            torso = info.regions["torso"]
            if torso:
                cx = sum(p[0] for p in torso) / len(torso)
                cy = min(p[1] for p in torso) + 2
                if d == "left":
                    cx = 63 - cx
                lean = {"down": 35, "up": -35, "right": 30, "left": -30}[d]
                if wtype == "bow":
                    lean = {"down": -20, "up": 20, "right": -15, "left": 15}[d]
                p = wa.posed(wtype, ore, lean)
                if p:
                    wsurf, (ox, oy) = p
                    order = 0.05 if d == "up" else -0.2
                    entries.append((a.y + order, wsurf, int(fx + cx - ox + 1), int(fy + cy + 6 - oy)))
    body = surf
    if alpha < 255:
        body = surf.copy()
        body.set_alpha(alpha)
    entries.append((a.y, body, int(fx), int(fy)))
    if getattr(a, "flash", 0) > 0 and not dead:
        entries.append((a.y + 0.01, white_fn(surf), int(fx), int(fy)))
    if smear is not None and getattr(a, "state", None) in ("active", "recovery"):
        prof = a.profile or {}
        sc = SMEAR_SCALE.get(prof.get("weapon"), 1.0)
        tint = look.get("smear")
        s = _smear(smear, sc, tuple(tint) if tint else None)
        s = s.copy()
        if getattr(a, "state", None) == "recovery":
            s.set_alpha(max(0, 150 - int(a.state_t * 700)))
        else:
            s.set_alpha(185)   # bright but see-through, so the target stays readable
        off = (64 * sc - 64) / 2
        entries.append((a.y + 0.02, s, int(fx - off), int(fy - off + (64 * sc - 64) / 2 * 0.3)))
    # dodge afterimages
    if getattr(a, "state", None) == "dodge":
        for k in (1, 2):
            g = surf.copy()
            g.set_alpha(110 // k)
            dv = getattr(a, "dodge_vec", (0, 0))
            entries.append((a.y - 0.05 * k, g, int(fx - dv[0] * 7 * k), int(fy - dv[1] * 7 * k)))
    return entries
