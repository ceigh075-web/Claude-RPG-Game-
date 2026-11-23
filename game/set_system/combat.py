"""Authoritative combat rules: attack profiles, timing, damage, blocking, knockback, stagger, statuses.

Pure functions over plain numbers/dicts so they are deterministic and unit-testable. The real-time layer
(gameplay/combat.py) decides *when* things collide; this module decides *what happens*.
"""
import math

# share of an attack cycle spent in each phase
WINDUP, ACTIVE, RECOVERY = 0.28, 0.14, 0.40
TEMPO = 1.3                  # combat overhaul: every attack cycle runs 30% faster
RANGED_RECOVERY = 0.55       # ...and ranged weapons reload in about half the time
MIN_ENEMY_WINDUP = 0.18      # enemy wind-ups never get shorter than this, so they stay readable
CANCEL_AFTER = 0.3           # share of recovery after which a new action may cut it short
COMBO_MAX = 3
COMBO_WINDOW = 0.55          # seconds after recovery starts in which the next combo hit can be queued
COMBO_FINISHER = {"damage": 1.4, "knockback": 1.6, "stagger": 1.5}

KICK = {"damage": 3.0, "reach": 18, "arc": 70, "knockback": 170, "stagger": 0.5, "speed": 0.9, "guard_damage": 35}
DODGE_TIME, DODGE_IFRAMES, DODGE_COOLDOWN = 0.3, 0.24, 0.45
GUARD_MAX, GUARD_REGEN = 100.0, 28.0
BLOCK_ARC = 75               # degrees either side of facing that a block covers
BACKSTAB_ARC = 60
GUARD_BREAKERS = {"battleaxe", "hammer"}
BLEEDERS = {"axe": (2.0, 3.0), "battleaxe": (3.5, 4.0)}   # dps, seconds
ARMOR_PIERCE = {"mace": 0.5}

STATUS_DEFS = {
    # status: (kind, default magnitude, default duration)
    "bleed": ("dot", 3.0, 4.0), "burn": ("dot", 4.0, 3.0), "poison": ("dot", 3.0, 6.0), "scald": ("dot", 2.5, 3.0),
    "chill": ("slow", 0.5, 3.0), "entangle": ("root", 1.0, 1.6), "root": ("root", 1.0, 2.0),
    "shock": ("stagger", 0.5, 0.0), "stagger": ("stagger", 0.6, 0.0), "blind": ("blind", 0.5, 3.0),
    "pull": ("pull", 120.0, 0.0), "pierce": ("armor_break", 0.5, 4.0), "none": ("none", 0, 0),
}


def weapon_stats(data, weapon_type, item_id=None):
    """Base numbers for a weapon type, upgraded by the ore of a specific item if given."""
    w = data.weapons[weapon_type]
    out = dict(w)
    if item_id:
        it = data.item(item_id)
        out["damage"] = it["damage"]
        out["speed"] = it["speed"]
        out["ore"] = it.get("ore")
        out["mana_conduct"] = data.ores[it["ore"]]["equipment"]["mana_conduct"] if it.get("ore") else 0.0
    return out


def attack_profile(data, attrs, skills, weapon_type, item_id=None, combo_step=1):
    """Everything about one swing/shot from a character with the given attributes and skills."""
    w = weapon_stats(data, weapon_type, item_id)
    scale = sum(attrs.get(a, 10) * s for a, s in w["scaling"].items()) / 10.0
    skill = skills.get(w["skill"], 0.0)
    dmg = w["damage"] * (0.6 + 0.4 * scale) * (1 + skill / 100.0)
    speed = w["speed"] * (1 + attrs.get("dexterity", 10) / 100.0) * (1 + skill / 400.0) * TEMPO
    cycle = 1.0 / speed
    kb = w["knockback"] * (1 + attrs.get("strength", 10) / 100.0)
    stagger = w["stagger"]
    finisher = combo_step >= COMBO_MAX and w["class"] == "melee"
    if finisher:
        dmg *= COMBO_FINISHER["damage"]
        kb *= COMBO_FINISHER["knockback"]
        stagger *= COMBO_FINISHER["stagger"]
        if weapon_type == "knuckles":
            stagger = max(stagger, 0.8)
    windup = cycle * WINDUP * (0.6 if combo_step > 1 else 1.0)
    return {
        "weapon": weapon_type, "class": w["class"], "skill": w["skill"], "damage": dmg, "knockback": kb,
        "stagger": stagger, "reach": w["reach"], "arc": w["arc"], "windup": windup, "active": cycle * ACTIVE,
        "recovery": cycle * RECOVERY * (RANGED_RECOVERY if w["class"] == "ranged" else 1.0),
        "guard_break": weapon_type in GUARD_BREAKERS,
        "armor_pierce": ARMOR_PIERCE.get(weapon_type, 0.0), "bleed": BLEEDERS.get(weapon_type),
        "backstab": 3.0 if weapon_type == "dagger" else 1.0, "finisher": finisher,
        "projectile_speed": w.get("projectile_speed", 0), "ammo": w.get("ammo"), "pellets": w.get("pellets", 1),
        "pierce": 1 if weapon_type == "crossbow" else 0, "scaling": list(w["scaling"]),
        "chargeable": weapon_type == "bow",
    }


def kick_profile(attrs):
    s = attrs.get("strength", 10)
    return {"weapon": "kick", "class": "melee", "skill": "unarmed", "damage": KICK["damage"] + s * 0.15,
            "knockback": KICK["knockback"] * (1 + s / 100.0), "stagger": KICK["stagger"], "reach": KICK["reach"],
            "arc": KICK["arc"], "windup": 0.12, "active": 0.1, "recovery": 0.32, "guard_break": False,
            "guard_damage": KICK["guard_damage"], "armor_pierce": 0.0, "bleed": None, "backstab": 1.0,
            "finisher": False, "scaling": ["strength"]}


def enemy_profile(data, enemy):
    """Attack profile for an enemy archetype entry from enemies.json."""
    w = data.weapons[enemy["weapon"]]
    heavy = enemy["archetype"] == "heavy"
    speed = w["speed"] * (0.75 if heavy else 1.0) * (1.25 if enemy["archetype"] == "fast" else 1.0) * TEMPO
    cycle = 1.0 / speed
    return {"weapon": enemy["weapon"], "class": w["class"], "skill": w["skill"], "damage": float(enemy["damage"]),
            "knockback": w["knockback"] * (1.4 if heavy else 1.0), "stagger": w["stagger"] * (1.3 if heavy else 1.0),
            "reach": max(enemy["attack_range"], 14) if w["class"] == "melee" else enemy["attack_range"],
            "arc": max(w["arc"], 60), "windup": max(MIN_ENEMY_WINDUP, cycle * WINDUP * (1.6 if heavy else 1.0)),
            "active": cycle * ACTIVE,
            "recovery": cycle * RECOVERY * (RANGED_RECOVERY if w["class"] == "ranged" else 1.0), "guard_break": enemy["weapon"] in GUARD_BREAKERS or heavy,
            "armor_pierce": ARMOR_PIERCE.get(enemy["weapon"], 0.0), "bleed": BLEEDERS.get(enemy["weapon"]),
            "backstab": 1.0, "finisher": False, "projectile_speed": w.get("projectile_speed", 0),
            "ammo": None, "pellets": w.get("pellets", 1), "pierce": 0, "scaling": []}


# ------------------------------------------------------------------ geometry helpers
def angle_between(v1, v2):
    """Unsigned angle in degrees between two 2D vectors."""
    a1, a2 = math.atan2(v1[1], v1[0]), math.atan2(v2[1], v2[0])
    d = abs(math.degrees(a1 - a2)) % 360
    return 360 - d if d > 180 else d


def in_arc(origin, facing, target, reach, arc, target_radius=6.0):
    dx, dy = target[0] - origin[0], target[1] - origin[1]
    dist = math.hypot(dx, dy)
    if dist > reach + target_radius:
        return False
    if dist < 4:
        return True
    return angle_between(facing, (dx, dy)) <= arc / 2 + math.degrees(math.atan2(target_radius, max(dist, 1)))


# ------------------------------------------------------------------ hit resolution
def resolve_hit(profile, attacker_pos, defender, rng, charge_mult=1.0):
    """Compute the outcome of `profile` landing on `defender`.

    defender: dict-like with keys armor, blocking (bool), facing (vec), guard, poise, blocking_skill,
              dodging_skill, iframes (bool), blind (float miss chance of the attacker is passed via profile).
    Returns dict: damage, knockback, stagger_time, blocked, guard_broken, backstab, dodged, statuses, guard_damage.
    """
    out = {"damage": 0.0, "knockback": 0.0, "stagger_time": 0.0, "blocked": False, "guard_broken": False,
           "backstab": False, "dodged": False, "statuses": [], "guard_damage": 0.0, "missed": False}
    if defender.get("iframes"):
        out["dodged"] = True
        return out
    if profile.get("miss_chance", 0) and rng.random() < profile["miss_chance"]:
        out["missed"] = True
        return out
    to_attacker = (attacker_pos[0] - defender["x"], attacker_pos[1] - defender["y"])
    dmg = profile["damage"] * charge_mult * rng.uniform(0.9, 1.1)
    kb = profile["knockback"] * charge_mult
    stagger = profile["stagger"]
    # backstab: attacker is behind the defender
    if profile.get("backstab", 1.0) > 1.0 and angle_between(defender["facing"], to_attacker) > 180 - BACKSTAB_ARC:
        dmg *= profile["backstab"]
        out["backstab"] = True
    # blocking
    if defender.get("blocking") and angle_between(defender["facing"], to_attacker) <= BLOCK_ARC:
        guard_dmg = dmg * 1.5 + profile.get("guard_damage", 0)
        if profile.get("guard_break") or defender["guard"] - guard_dmg <= 0:
            out["guard_broken"] = True
            out["guard_damage"] = defender["guard"]
            dmg *= 0.6
            stagger = max(stagger, 0.7)
        else:
            out["blocked"] = True
            out["guard_damage"] = guard_dmg
            dmg *= max(0.08, 0.3 - defender.get("blocking_skill", 0) / 400.0)
            kb *= 0.35
            stagger = 0.0
    armor = defender.get("armor", 0.0) * (1 - profile.get("armor_pierce", 0.0))
    if defender.get("armor_break"):
        armor *= 0.5
    dmg = max(1.0 if not out["blocked"] else 0.0, dmg - armor * 0.5)
    out["damage"] = dmg
    out["knockback"] = kb / max(0.5, defender.get("mass", 1.0))
    if stagger > defender.get("poise", 0.3):
        out["stagger_time"] = 0.15 + (stagger - defender.get("poise", 0.3)) * 0.8
    if profile.get("bleed") and not out["blocked"]:
        dps, dur = profile["bleed"]
        out["statuses"].append(("bleed", dps, dur))
    if not out["blocked"]:
        for st in profile.get("statuses", []):
            out["statuses"].append(st)
    return out


def xp_for_hit(profile, result):
    """Skill/attribute training produced by landing a hit (attacker side)."""
    if result["dodged"] or result["missed"]:
        return {}
    base = 1.0 + result["damage"] / 10.0
    gains = {profile["skill"]: base}
    for a in profile.get("scaling", []):
        gains[a] = gains.get(a, 0) + base * 0.5
    return gains


def status_info(name):
    return STATUS_DEFS.get(name, STATUS_DEFS["none"])
