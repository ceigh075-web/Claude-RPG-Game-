"""Glue between gameplay objects and the animated sprite pipeline.

Everything here only *reads* gameplay state (equipment, enemy definitions, combat state) to decide what a
character looks like and which weapon it visibly holds. No gameplay values are changed.
"""
import pygame

from . import animator, assets, charsprites, creatures
from . import weapons_art as wa

ORE_ARMOR = {"rustite": (150, 92, 64), "greyvein": (150, 158, 172), "sunsilver": (214, 190, 104),
             "voidglass": (106, 70, 160)}
LEATHER = (122, 86, 54)

# humanoid enemy outfits: readable silhouettes per role
ENEMY_OUTFIT = {
    "bandit_cutthroat": {"hood": (78, 58, 46), "shirt": (96, 74, 58), "pants": (60, 50, 44), "ore": "rustite"},
    "bandit_archer": {"hood": (64, 90, 56), "shirt": (78, 96, 62), "pants": (66, 58, 46), "ore": "rustite"},
    "hollow_shieldbearer": {"armor": (118, 122, 134), "helm": (104, 108, 120), "shirt": (70, 70, 84),
                            "pants": (52, 52, 62), "ore": "greyvein"},
    "hollow_captain": {"armor": (52, 50, 62), "helm": (40, 38, 48), "shirt": (120, 30, 34), "pants": (40, 40, 50),
                       "ore": "greyvein", "smear": (255, 150, 150)},
    "thornblood_raider": {"race": "murrok", "shirt": (110, 80, 50), "pants": (80, 58, 40),
                          "warpaint": (170, 40, 40), "ore": "rustite", "hair_style": 2},
}
_enabled = None


def enabled():
    """Animated pack sprites are used when the asset folder is present; otherwise the old procedural art."""
    global _enabled
    if _enabled is None:
        try:
            _enabled = assets.available() and charsprites.base("idle", "down") is not None
        except (FileNotFoundError, pygame.error, KeyError, IndexError):
            _enabled = False
    return _enabled


def dress(look, char, data):
    """Look dict extended with worn armour/helmet colours (keyed on the equipped items' ore)."""
    if not char:
        return look
    eq = getattr(char, "equipment", {}) or {}
    body, head = eq.get("body"), eq.get("head")
    if not body and not head:
        return look
    out = dict(look)
    if body:
        ore = data.items.get(body, {}).get("ore")
        out["armor"] = ORE_ARMOR.get(ore, LEATHER)
    if head:
        ore = data.items.get(head, {}).get("ore")
        out["helm"] = ORE_ARMOR.get(ore, LEATHER)
    return out


def _item_weapon(data, item):
    it = data.items.get(item) if item else None
    if it and it.get("type") == "weapon":
        return it["weapon"], it.get("ore")
    return None


def weapon_for(c, data, state=None):
    """(weapon type, ore) visibly held by a combatant, or None for bare hands."""
    if c.enemy:
        e = c.enemy
        if e.get("shape") != "humanoid" or e.get("weapon") == "fists":
            return None
        ore = ENEMY_OUTFIT.get(getattr(c, "enemy_id", ""), {}).get("ore", "rustite")
        return e["weapon"], ore
    char = c.char
    if not char:
        return None
    eq = char.equipment
    melee = _item_weapon(data, eq.get("weapon"))
    ranged = _item_weapon(data, eq.get("ranged"))
    prof = c.profile
    if prof and c.state in ("windup", "active", "recovery", "draw"):
        wt = prof.get("weapon")
        for w in (melee, ranged):
            if w and w[0] == wt:
                return w
        return None if wt in ("fists", "kick") else (wt, None)
    if state is not None and c.char is state.player and state.settings.get("weapon_mode") == "ranged" and ranged:
        return ranged
    return melee or ranged


def enemy_look(c):
    """Pack-compositor look for a humanoid enemy."""
    eid = getattr(c, "enemy_id", "")
    base = dict(c.look)
    o = ENEMY_OUTFIT.get(eid, {})
    look = {"race": o.get("race", "human"), "skin": base.get("skin", (190, 170, 150)),
            "hair": base.get("hair", (50, 40, 30)), "shirt": o.get("shirt", base.get("shirt")),
            "pants": o.get("pants", base.get("pants")), "hair_style": o.get("hair_style", 2)}
    for k in ("hood", "armor", "helm", "warpaint", "smear"):
        if k in o:
            look[k] = o[k]
    if look["race"] == "murrok":
        look["skin"] = (150, 160, 120)
    return look


def combatant_entries(world, art, camx, camy, t, state=None):
    """Sprite entries for every combatant using the animated pipeline (None if unavailable)."""
    if not enabled():
        return None
    data = world.data
    out = []
    for c in world.combatants:
        e = c.enemy
        shape = e.get("shape", "humanoid") if e else "humanoid"
        eid = getattr(c, "enemy_id", "")
        shadow_w = 12
        if e and eid == "husk":
            out += _husk(c, art, camx, camy, t)
            shadow_w = 12
        elif shape == "humanoid":
            look = enemy_look(c) if e else dress(c.look, c.char, data)
            out += animator.humanoid_entries(c, look, weapon_for(c, data, state), t, camx, camy, art, art.white)
        else:
            cshape = creatures.shape_for(eid, e)
            anim, idx = creatures.creature_anim(c)
            img = creatures.frame(cshape, e["color"], anim, idx)
            if c.facing == "left" or (c.facing in ("up", "down") and c.aim[0] < 0):
                img = pygame.transform.flip(img, True, False)
            w, h = img.get_size()
            x, y = c.x - w / 2 - camx, c.y - h + 3 - camy
            if c.state == "stagger":
                x += (t * 60 % 2 > 1) * 2 - 1
            if c.state == "dead":
                img = img.copy()
                img.set_alpha(max(0, int(255 * (1 - max(0.0, c.dead_t - 0.6) / 1.0))))
            out.append((c.y, img, int(x), int(y)))
            if c.flash > 0 and c.state != "dead":
                out.append((c.y + 0.01, art.white(img), int(x), int(y)))
            shadow_w = max(12, min(30, int(w * 0.7)))
        sh = art.shadow(shadow_w)
        out.append((c.y - 0.5, sh, int(c.x - sh.get_width() / 2 - camx), int(c.y - 3 - camy)))
    return out


def _husk(c, art, camx, camy, t):
    st = c.state
    if st == "dead":
        anim, idx = "death", min(7, int(c.dead_t / 0.1))
    elif c.moving or st in ("windup", "active", "recovery"):
        anim, idx = "move", int((c.anim_t if c.moving else c.state_t) * 10) % 6
    else:
        anim, idx = "idle", int(t * 6 + c.cid) % 4
    img, size = creatures.skeleton(anim, idx)
    if img is None:
        return []
    left = c.facing == "left" or (c.facing in ("up", "down") and c.aim[0] < 0)
    if left:
        img = pygame.transform.flip(img, True, False)
    foot = 47 if size == 64 else 31
    x, y = c.x - size / 2 - camx, c.y - foot - camy
    if st == "active":  # lunge toward the target
        x += c.aim[0] * 4
        y += c.aim[1] * 2
    elif st == "windup":
        x -= c.aim[0] * 2
    if st == "dead":
        img = img.copy()
        img.set_alpha(max(0, int(255 * (1 - max(0.0, c.dead_t - 0.9) / 0.8))))
    out = [(c.y, img, int(x), int(y))]
    if c.flash > 0 and st != "dead":
        out.append((c.y + 0.01, art.white(img), int(x), int(y)))
    return out


def npc_entries(a, art, camx, camy, t, data=None):
    """Entries for a non-combat wanderer/shopkeeper; named NPCs carry their listed weapon."""
    if not enabled():
        return None
    weapon = None
    npc = getattr(a, "npc", None)
    if npc and data is not None:
        for item in npc.get("equipment", []):
            weapon = _item_weapon(data, item)
            if weapon:
                break
    out = animator.humanoid_entries(a, a.look, weapon, t, camx, camy, art, art.white)
    sh = art.shadow(12)
    out.append((a.y - 0.5, sh, int(a.x - 6 - camx), int(a.y - 3 - camy)))
    return out


def portrait(art, look, direction="down", frame=0, walking=False):
    """Character preview for menus (22x32, feet at the bottom); falls back to the procedural sprite."""
    if not enabled():
        return art.character(look, direction, frame)
    anim = "walk" if walking else "idle"
    surf, _, _ = charsprites.compose(look, anim, direction, frame % (6 if walking else 4))
    return surf.subsurface((21, 16, 22, 32))
