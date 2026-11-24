"""Glue between gameplay objects and the animated sprite pipeline.

Everything here only *reads* gameplay state (equipment, enemy definitions, combat state) to decide what a
character looks like and which weapon it visibly holds. No gameplay values are changed.
"""
import math

import pygame

from . import animator, assets, charsprites, creatures, looks
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
    if getattr(c, "npc", None) and c.team == "npc":
        for item in c.npc.get("equipment", []):
            w = _item_weapon(data, item)
            if w:
                return w
        return None
    if c.enemy and (c.team == "enemy" or getattr(c, "surrendered", False)):
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


_enemy_looks = {}


def enemy_look(c, data=None):
    """Varied look for a humanoid enemy (stable for each spawned combatant)."""
    e = c.enemy or {}
    if e.get("npc"):                      # duels and named foes keep their own identity
        return c.look
    eid = getattr(c, "enemy_id", "")
    if data is not None and eid in looks.ENEMY_ROLE:
        key = (eid, c.cid)
        if key not in _enemy_looks:
            if len(_enemy_looks) > 400:
                _enemy_looks.clear()
            lk = looks.enemy_variant(data, eid, c.cid)
            if e.get("elite_event") or e.get("boss"):
                lk["cape"] = [120, 20, 30]
                lk["hat"] = "horns" if eid == "thornblood_raider" else lk.get("hat", "crown")
                lk["height"] = "tall"
                lk["acc"] = sorted(set(lk.get("acc", [])) | {"pauldrons"})
            _enemy_looks[key] = lk
        return _enemy_looks[key]
    return _old_enemy_look(c)


def _old_enemy_look(c):
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
        if e and eid in ("husk", "husk_mage"):
            out += _husk(c, art, camx, camy, t)
            shadow_w = 12
        elif shape == "humanoid":
            look = enemy_look(c, data) if e and (c.team == "enemy" or getattr(c, "surrendered", False)) \
                else dress(c.look, c.char, data)
            ents = animator.humanoid_entries(c, look, weapon_for(c, data, state), t, camx, camy, art, art.white)
            if e and e.get("boss"):
                ents = _scale_entries(ents, data.bosses[e["boss"]].get("scale", 1.4), c.x - camx, c.y - camy)
                shadow_w = 26
            out += ents
        else:
            cshape = creatures.shape_for(eid, e)
            anim, idx = creatures.creature_anim(c)
            col = creature_color(cshape, eid, e, c.cid, getattr(world.map, "biome", None))
            img = creatures.frame(cshape, col, anim, idx, c.cid)
            if e.get("boss"):
                img = _boss_scale(img, data.bosses[e["boss"]].get("scale", 1.8))
            elif e.get("elite_event"):
                img = _elite(img)
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
        if getattr(c, "killed", False):
            out.append((c.y - 0.6, _blood_pool(min(1.0, c.dead_t / 2.0)), int(c.x - 11 - camx), int(c.y - 5 - camy)))
        elif getattr(c, "downed", False) and c.state == "dead":
            for k in range(3):   # dazed stars over someone knocked down (they'll get up)
                a_ = t * 3 + k * 2.1
                star = _star()
                out.append((c.y + 0.03, star, int(c.x - 2 + math.cos(a_) * 7 - camx), int(c.y - 14 + math.sin(a_) * 2 - camy)))
    return out


_boss_cache = {}


def _boss_scale(img, k):
    key = (id(img), k)
    hit = _boss_cache.get(key)
    if hit is None or hit[0] is not img:
        if len(_boss_cache) > 400:
            _boss_cache.clear()
        w, h = img.get_size()
        hit = _boss_cache[key] = (img, pygame.transform.scale(img, (int(w * k), int(h * k))))
    return hit[1]


def _scale_entries(entries, k, fx, fy):
    """Scale a humanoid's sprite entries about its feet (bosses tower over everyone)."""
    out = []
    for sort_y, surf, x, y in entries:
        s = _boss_scale(surf, k)
        out.append((sort_y, s, int(fx + (x - fx) * k), int(fy + (y - fy) * k)))
    return out


_pool_cache = {}


def _blood_pool(f):
    k = int(f * 4)
    if k not in _pool_cache:
        s = pygame.Surface((22, 9), pygame.SRCALPHA)
        w = 10 + k * 3
        pygame.draw.ellipse(s, (110, 14, 20, 200), ((22 - w) // 2, 1, w, 4 + k))
        pygame.draw.ellipse(s, (150, 30, 34, 200), ((22 - w) // 2 + 2, 2, max(2, w - 6), 2 + k // 2))
        _pool_cache[k] = s
    return _pool_cache[k]


def _star():
    if "star" not in _pool_cache:
        s = pygame.Surface((3, 3), pygame.SRCALPHA)
        s.fill((255, 235, 140), (1, 0, 1, 3))
        s.fill((255, 235, 140), (0, 1, 3, 1))
        _pool_cache["star"] = s
    return _pool_cache["star"]


BIOME_TINT = {"forest": (104, 84, 62), "desert": (200, 170, 112), "snow": (220, 226, 236), "swamp": (70, 92, 62),
              "volcanic": (74, 54, 48), "cave": (84, 74, 96), "mountain": (122, 116, 110), "crystal": (130, 150, 200),
              "moor": (100, 100, 82), "canyon": (172, 104, 72), "hills": (132, 110, 80), "coast": (150, 140, 120),
              "ruins": (110, 110, 100)}
GOLEM_HUES = [(150, 220, 230), (190, 150, 240), (150, 230, 170)]


def creature_color(shape, eid, e, cid, biome):
    """Natural creatures take on a little of their surroundings; golems come in several mineral hues."""
    col = tuple(e["color"])
    if e.get("boss_color"):
        return tuple(e["boss_color"])
    if shape == "crystal":
        return GOLEM_HUES[cid % len(GOLEM_HUES)]
    tint = BIOME_TINT.get(biome)
    if tint and shape in ("beast", "bug", "worm") and eid != "ice_wolf":
        col = tuple(int(a * 0.72 + b * 0.28) for a, b in zip(col, tint))
    return col


_elite_cache = {}


def _elite(img):
    """Named / elite monsters are drawn half again as large."""
    key = id(img)
    if key not in _elite_cache:
        if len(_elite_cache) > 300:
            _elite_cache.clear()
        w, h = img.get_size()
        _elite_cache[key] = (img, pygame.transform.scale(img, (w * 3 // 2, h * 3 // 2)))
    return _elite_cache[key][1]


def _husk(c, art, camx, camy, t):
    """Husks are pack skeletons (base / rogue / warrior / mage, fixed per spawn). The sheets only have idle,
    run and death, so attacks are a wind-up lean and a lunge, hits a recoil, using the same timing as everyone."""
    st = c.state
    variant = 4 if getattr(c, "enemy_id", "") == "husk_mage" else c.cid % 4
    if st == "dead":
        anim, idx = "death", min(7, int(c.dead_t / 0.1))
    elif c.moving or st in ("windup", "active", "recovery"):
        anim, idx = "move", int((c.anim_t if c.moving else c.state_t) * 10) % 6
    else:
        anim, idx = "idle", int(t * 6 + c.cid) % 4
    img, size, foot = creatures.skeleton(anim, idx, variant)
    if img is None:
        return []
    left = c.facing == "left" or (c.facing in ("up", "down") and c.aim[0] < 0)
    if left:
        img = pygame.transform.flip(img, True, False)
    x, y = c.x - size / 2 - camx, c.y - foot - camy
    if st == "active":  # lunge toward the target
        x += c.aim[0] * 5
        y += c.aim[1] * 2
    elif st == "windup":
        x -= c.aim[0] * 2
        y += 1
    elif st == "stagger" or c.flash > 0:
        x -= c.aim[0] * 2
    if st == "dead":
        img = img.copy()
        img.set_alpha(max(0, int(255 * (1 - max(0.0, c.dead_t - 0.9) / 0.8))))
    out = [(c.y, img, int(x), int(y))]
    if st == "windup" and creatures.SKELETONS[variant] == "Skeleton - Mage":
        orb = _orb()
        out.append((c.y + 0.02, orb, int(c.x + c.aim[0] * 8 - 3 - camx), int(c.y - 16 - camy)))
    if c.flash > 0 and st != "dead":
        out.append((c.y + 0.01, art.white(img), int(x), int(y)))
    return out


def _orb():
    if "orb" not in _pool_cache:
        s = pygame.Surface((7, 7), pygame.SRCALPHA)
        pygame.draw.circle(s, (150, 60, 200), (3, 3), 3)
        pygame.draw.circle(s, (230, 180, 255), (3, 3), 1)
        _pool_cache["orb"] = s
    return _pool_cache["orb"]


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
    """Character preview for menus (36x54, feet near the bottom, room for chibi heads and hats)."""
    if not enabled():
        return art.character(look, direction, frame)
    anim = "walk" if walking else "idle"
    surf, _, _ = charsprites.compose(look, anim, direction, frame % (6 if walking else 4))
    return surf.subsurface((14, 4, 36, 54))
