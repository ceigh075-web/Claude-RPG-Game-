"""Spell rules: a spell is sub-element + movement class + stat class + power tier.

The Set System computes every number (mana, power, range, speed, area, duration, cooldown) from data
multipliers, so all combinations are balanced by the same formula. Only stat classes listed for a
sub-element are allowed.
"""
from .combat import status_info

MANA_BASE = 8.0

STARTER_SPELLS = [
    {"name": "Ash Dart", "sub": "ash", "move": "projectile", "stat": "damage", "tier": 1},
    {"name": "Mending Light", "sub": "light", "move": "aura", "stat": "heal", "tier": 1},
]


class SpellError(Exception):
    pass


def validate(data, spell, level=None):
    m = data.magic
    if spell["sub"] not in m["subelements"]:
        raise SpellError(f"unknown sub-element {spell['sub']}")
    if spell["move"] not in m["movements"]:
        raise SpellError(f"unknown movement {spell['move']}")
    if spell["stat"] not in m["stats"]:
        raise SpellError(f"unknown stat class {spell['stat']}")
    if str(spell["tier"]) not in m["tiers"]:
        raise SpellError(f"unknown tier {spell['tier']}")
    if spell["stat"] not in m["subelements"][spell["sub"]]["stats"]:
        raise SpellError(f"{m['subelements'][spell['sub']]['name']} cannot carry {m['stats'][spell['stat']]['name']}")
    if level is not None and level < m["tiers"][str(spell["tier"])]["level"]:
        raise SpellError(f"Tier {spell['tier']} spells need level {m['tiers'][str(spell['tier'])]['level']}")
    return True


def compute(data, spell, magic_skill=0.0, mana_conduct=0.0):
    """All gameplay numbers for a spell."""
    validate(data, spell)
    m = data.magic
    sub = m["subelements"][spell["sub"]]
    mv = m["movements"][spell["move"]]
    sc = m["stats"][spell["stat"]]
    tier = int(spell["tier"])
    td = m["tiers"][str(tier)]
    skill_mult = 1 + magic_skill / 100.0
    power = sc["base"] * sub["power"] * mv["power"] * td["power"] * skill_mult * (1 + mana_conduct)
    mana = MANA_BASE * sub["mana"] * mv["mana"] * sc["mana"] * td["mana"] * (1 - min(0.3, magic_skill / 300.0))
    rng = mv["range"] * (1 + 0.2 * (tier - 1))
    area = mv["area"] * (1 + 0.25 * (tier - 1))
    speed = mv["speed"] * sub["speed"]
    if spell["stat"] in ("strength", "speed", "dexterity", "health", "defense"):
        duration = 8.0 + 4.0 * tier
    elif spell["stat"] in ("root", "affliction"):
        kind, mag, dur = status_info(sub["status"] if spell["stat"] == "affliction" else "root")
        duration = (dur or 1.5) * (1 + 0.3 * (tier - 1))
    else:
        duration = mv["duration"]
    zone_duration = mv["duration"] * (1 + 0.25 * (tier - 1))
    cooldown = mv["cooldown"] * (1 + 0.25 * (tier - 1)) * (0.8 + 0.2 * sub["mana"])
    status = sub["status"]
    if spell["stat"] == "root":
        status = "root"
    out = {
        "name": spell.get("name") or describe_name(data, spell), "sub": spell["sub"], "move": spell["move"],
        "stat": spell["stat"], "tier": tier, "element": sub["element"], "color": tuple(sub["color"]),
        "power": round(power, 1), "mana": max(1, round(mana)), "range": round(rng), "area": round(area),
        "speed": round(speed), "duration": round(duration, 1), "zone_duration": round(zone_duration, 1),
        "cooldown": round(cooldown, 2), "status": status, "target": sc["target"],
        "hp_cost": round(mana * 0.3) if spell["sub"] == "blood" else 0,
    }
    out["description"] = describe(data, out)
    return out


def describe_name(data, spell):
    m = data.magic
    return f"{m['subelements'][spell['sub']]['name']} {m['movements'][spell['move']]['name']}"


def describe(data, p):
    m = data.magic
    stat = m["stats"][p["stat"]]["name"]
    mv = m["movements"][p["move"]]["desc"]
    eff = {
        "damage": f"deals {p['power']:.0f} {p['sub']} damage", "heal": f"heals {p['power']:.0f}",
        "strength": f"+{p['power']:.0f} Strength for {p['duration']:.0f}s",
        "speed": f"+{p['power']:.0f} Speed for {p['duration']:.0f}s",
        "dexterity": f"+{p['power']:.0f} Dexterity for {p['duration']:.0f}s",
        "health": f"+{p['power']:.0f} max health for {p['duration']:.0f}s",
        "defense": f"absorbs {p['power'] * 4:.0f} damage for {p['duration']:.0f}s",
        "knockback": "hurls enemies away", "root": f"roots enemies for {p['duration']:.1f}s",
        "affliction": f"inflicts {p['status']} for {p['duration']:.1f}s",
    }[p["stat"]]
    cost = f"{p['mana']} mana" + (f" + {p['hp_cost']} health" if p["hp_cost"] else "")
    return f"{mv} It {eff}. ({stat}; {cost}; cooldown {p['cooldown']:.1f}s)"


def starter_spellbook():
    return [dict(s) for s in STARTER_SPELLS]


def capacity(data, level):
    sb = data.magic["spellbook"]
    return min(sb["max_capacity"], sb["base_capacity"] + level // sb["per_levels"])
