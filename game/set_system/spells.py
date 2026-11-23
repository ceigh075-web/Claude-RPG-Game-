"""Spell rules. A spell is: element (+ optional sub-element) + movement class + effect + tier, tuned with a
focus (specialisation) and a size. Spells made with only an element use the element's own identity.

The Set System computes every number (mana, power, range, speed, area, duration, recast) from data
multipliers (data/magic.json), so every combination is balanced by the same formula. Only effects listed for
the element (or the chosen sub-element) are allowed.

Old saves stored spells as {sub, move, stat, tier}; `normalize` fills in element, focus and size so they keep
working unchanged.
"""
from .combat import status_info

MANA_BASE = 8.0
MAX_PERSISTENT = 3          # traps / fields / wards / barriers a caster may keep active at once

STARTER_SPELLS = [
    {"name": "Ash Dart", "element": "fire", "sub": "ash", "move": "projectile", "stat": "damage", "tier": 1,
     "focus": "balanced", "size": 1.0},
    {"name": "Mending Light", "element": "light", "sub": "light", "move": "aura", "stat": "heal", "tier": 1,
     "focus": "balanced", "size": 1.0},
]


class SpellError(Exception):
    pass


def normalize(data, spell):
    """Fill in fields missing from older spells (element from sub-element, balanced focus, size 1)."""
    out = dict(spell)
    m = data.magic
    sub = out.get("sub")
    if sub in ("", "none"):
        sub = out["sub"] = None
    if not out.get("element"):
        if sub is None or sub not in m["subelements"]:
            raise SpellError("spell has neither element nor sub-element")
        out["element"] = m["subelements"][sub]["element"]
    out.setdefault("sub", None)
    out.setdefault("focus", "balanced")
    out["size"] = float(out.get("size", 1.0))
    for k in TUNING_KEYS:
        out[k] = float(out.get(k, 1.0))
    out.setdefault("behavior", "standard")
    out["hue"] = int(out.get("hue", 0))
    out["intensity"] = float(out.get("intensity", 1.0))
    return out


TUNING_KEYS = ("duration", "potency", "velocity", "reach")


def duration_matters(sp, data=None):
    if data is not None:
        m = data.magic
        el = m["elements"][sp["element"]]
        src = m["subelements"][sp["sub"]] if sp.get("sub") else el
        if (src.get("status", "none") if src.get("status", "none") != "none" else el.get("status", "none")) != "none":
            return True             # lingering statuses (burn, chill...) last longer
    return sp["move"] in ("ground", "ward", "aura", "orbit", "trap", "barrier") or \
        sp["stat"] in ("strength", "speed", "dexterity", "health", "defense", "root", "affliction") or \
        sp.get("behavior") == "lingering"


def velocity_matters(sp):
    return sp["move"] in ("projectile", "homing", "wave")


def reach_matters(data, sp):
    return data.magic["movements"][sp["move"]]["range"] > 0


def allowed_effects(data, element, sub=None):
    m = data.magic
    if sub:
        return list(m["subelements"][sub]["stats"])
    return list(m["elements"][element]["effects"])


def validate(data, spell, level=None):
    m = data.magic
    sp = normalize(data, spell)
    if sp["element"] not in m["elements"]:
        raise SpellError(f"unknown element {sp['element']}")
    if sp["sub"] is not None:
        if sp["sub"] not in m["subelements"]:
            raise SpellError(f"unknown sub-element {sp['sub']}")
        if m["subelements"][sp["sub"]]["element"] != sp["element"]:
            raise SpellError(f"{m['subelements'][sp['sub']]['name']} is not a kind of {m['elements'][sp['element']]['name']}")
    if sp["move"] not in m["movements"]:
        raise SpellError(f"unknown movement {sp['move']}")
    if sp["stat"] not in m["stats"]:
        raise SpellError(f"unknown effect {sp['stat']}")
    if str(sp["tier"]) not in m["tiers"]:
        raise SpellError(f"unknown tier {sp['tier']}")
    if sp["focus"] not in m["focuses"]:
        raise SpellError(f"unknown focus {sp['focus']}")
    lo, hi = m["sizes"]["min"], m["sizes"]["max"]
    if not lo <= sp["size"] <= hi:
        raise SpellError(f"size must be between {lo} and {hi}")
    for k in TUNING_KEYS:
        t = m["tuning"][k]
        if not t["min"] <= sp[k] <= t["max"]:
            raise SpellError(f"{t['name']} must be between {t['min']} and {t['max']}")
    bh = m["behaviors"].get(sp["behavior"])
    if bh is None:
        raise SpellError(f"unknown behaviour {sp['behavior']}")
    if bh["moves"] and sp["move"] not in bh["moves"]:
        raise SpellError(f"{bh['name']} only works with: " + ", ".join(m["movements"][x]["name"] for x in bh["moves"]))
    if not 0 <= sp["hue"] < len(m["appearance"]["hues"]):
        raise SpellError("unknown colour variant")
    ai = m["appearance"]["intensity"]
    if not ai["min"] <= sp["intensity"] <= ai["max"]:
        raise SpellError("intensity out of range")
    if sp["stat"] not in allowed_effects(data, sp["element"], sp["sub"]):
        src = m["subelements"][sp["sub"]]["name"] if sp["sub"] else m["elements"][sp["element"]]["name"]
        raise SpellError(f"{src} cannot carry {m['stats'][sp['stat']]['name']}")
    if level is not None and level < m["tiers"][str(sp["tier"])]["level"]:
        raise SpellError(f"Tier {sp['tier']} spells need level {m['tiers'][str(sp['tier'])]['level']}")
    return True


def compute(data, spell, magic_skill=0.0, mana_conduct=0.0):
    """All gameplay numbers for a spell."""
    validate(data, spell)
    sp = normalize(data, spell)
    m = data.magic
    el = m["elements"][sp["element"]]
    src = m["subelements"][sp["sub"]] if sp["sub"] else el       # the source of power/speed/mana/status/colour
    mv = m["movements"][sp["move"]]
    sc = m["stats"][sp["stat"]]
    fc = m["focuses"][sp["focus"]]
    tier = int(sp["tier"])
    td = m["tiers"][str(tier)]
    size = sp["size"]
    aff = el["affinity"].get(sp["stat"], 1.0)
    focus_bonus = 1.1 if sp["focus"] == el["focus_affinity"] and sp["focus"] != "balanced" else 1.0
    skill_mult = 1 + magic_skill / 100.0
    elem_power = (el["power"] if sp["sub"] else 1.0)
    power = (sc["base"] * src["power"] * elem_power * mv["power"] * td["power"] * skill_mult * (1 + mana_conduct)
             * aff * fc.get("power", 1.0) * (0.7 + 0.3 * size))
    if fc.get("power", 1.0) > 1:
        power *= focus_bonus
    tune = m["tuning"]
    bh = m["behaviors"][sp["behavior"]]
    power *= sp["potency"]
    # every choice that changes what the spell does changes its price (shown to the player as a breakdown)
    base_mana = MANA_BASE * src["mana"] * mv["mana"] * sc["mana"] * td["mana"]
    factors = [("Element" + (" / sub-element" if sp["sub"] else ""), src["mana"]),
               (f"{mv['name']} movement", mv["mana"]), (f"{sc['name']} effect", sc["mana"]), (f"Tier {tier}", td["mana"]),
               (f"Size x{size:g}", size ** mv["size_cost"])]
    factors.append((f"Duration x{sp['duration']:g}" + ("" if duration_matters(sp, data) else " (no effect)"),
                    sp["duration"] ** tune["duration"]["cost"] if duration_matters(sp, data) else 1.0))
    factors.append((f"Potency x{sp['potency']:g}", sp["potency"] ** tune["potency"]["cost"]))
    factors.append((f"Speed x{sp['velocity']:g}" + ("" if velocity_matters(sp) else " (no effect)"),
                    sp["velocity"] ** tune["velocity"]["cost"] if velocity_matters(sp) else 1.0))
    factors.append((f"Range x{sp['reach']:g}" + ("" if reach_matters(data, sp) else " (no effect)"),
                    sp["reach"] ** tune["reach"]["cost"] if reach_matters(data, sp) else 1.0))
    factors.append((f"{bh['name']} behaviour", bh["mana"]))
    fmana = fc.get("mana", 1.0) / (focus_bonus if fc.get("mana", 1.0) < 1 else 1.0)
    factors.append((f"{fc['name']} focus", fmana))
    disc = 1 - min(0.3, magic_skill / 300.0)
    factors.append(("Your Magic skill", disc))
    mana = MANA_BASE
    for _, f in factors:
        mana *= f
    rng = mv["range"] * (1 + 0.2 * (tier - 1)) * fc.get("range", 1.0) * (focus_bonus if "range" in fc else 1.0) * sp["reach"]
    area = min(mv["max_area"], mv["area"] * (1 + 0.25 * (tier - 1)) * size * fc.get("area", 1.0)
               * (focus_bonus if "area" in fc else 1.0))
    speed = mv["speed"] * src["speed"] * (el["speed"] if sp["sub"] else 1.0) * fc.get("speed", 1.0) * \
        (focus_bonus if "speed" in fc else 1.0) * sp["velocity"]
    dur_mult = fc.get("duration", 1.0) * (focus_bonus if "duration" in fc else 1.0) * sp["duration"]
    control = fc.get("control", 1.0) * (focus_bonus if "control" in fc else 1.0)
    status = src["status"] if src["status"] != "none" else el["status"]
    if sp["stat"] in ("strength", "speed", "dexterity", "health", "defense"):
        duration = (8.0 + 4.0 * tier) * dur_mult
    elif sp["stat"] in ("root", "affliction"):
        kind, mag, dur = status_info(status if sp["stat"] == "affliction" else "root")
        duration = (dur or 1.5) * (1 + 0.3 * (tier - 1)) * dur_mult * control
    else:
        duration = mv["duration"]
    if sp["stat"] == "knockback":
        power *= control
    zone_duration = mv["duration"] * (1 + 0.25 * (tier - 1)) * dur_mult
    cooldown = mv["cooldown"] * (0.85 + 0.15 * tier) * (0.5 if sp["behavior"] == "rapid" else 1.0)
    if sp["stat"] == "root":
        status = "root"
    style = sp["sub"] or sp["element"]
    if sp["hue"] or sp["intensity"] != 1.0:
        style = f"{style}#{sp['hue']}#{sp['intensity']:g}"      # a colour/intensity variant of the look
    color = variant_color(tuple(src["color"]), sp["hue"])
    out = {
        "name": sp.get("name") or describe_name(data, sp), "sub": style, "sub_id": sp["sub"],
        "element": sp["element"], "move": sp["move"], "stat": sp["stat"], "tier": tier, "focus": sp["focus"],
        "size": size, "color": color, "behavior": sp["behavior"], "hue": sp["hue"], "intensity": sp["intensity"],
        "duration_mult": sp["duration"], "potency": sp["potency"],
        "power": round(power, 1), "mana": max(1, round(mana)), "range": round(rng), "area": round(area),
        "radius": round(4 * size ** 0.5, 1), "speed": round(speed), "duration": round(duration, 1),
        "zone_duration": round(zone_duration, 1), "cooldown": round(cooldown, 2), "status": status,
        "target": sc["target"], "chain_jumps": 2 + tier,
        "hp_cost": round(mana * 0.3) if sp["sub"] == "blood" else 0,
        "cost_breakdown": [(label, round(f, 2)) for label, f in factors if abs(f - 1.0) > 0.005],
    }
    out["description"] = describe(data, out)
    return out


def variant_color(col, hue):
    """The colour variants offered in the designer (0 = natural)."""
    import colorsys
    if not hue:
        return col
    r, g, b = (c / 255.0 for c in col)
    h, l, sat = colorsys.rgb_to_hls(r, g, b)
    if hue == 1:
        h, sat = (h - 0.08) % 1.0, min(1.0, sat * 1.15)       # warm
    elif hue == 2:
        h = (h + 0.1) % 1.0                                    # cool
    elif hue == 3:
        l = l * 0.55                                           # shadow
    elif hue == 4:
        l, sat = min(0.92, l * 0.5 + 0.48), sat * 0.6          # pale
    elif hue == 5:
        h = (h + 0.5) % 1.0                                    # inverted
    r, g, b = colorsys.hls_to_rgb(h, l, sat)
    return (int(r * 255), int(g * 255), int(b * 255))


def describe_name(data, spell):
    m = data.magic
    sp = normalize(data, spell)
    src = m["subelements"][sp["sub"]]["name"] if sp["sub"] else m["elements"][sp["element"]]["name"]
    big = " Great" if sp["size"] >= 2 else (" Lesser" if sp["size"] <= 0.75 else "")
    return f"{src}{big} {m['movements'][sp['move']]['name']}".replace("  ", " ")


def describe(data, p):
    m = data.magic
    stat = m["stats"][p["stat"]]["name"]
    mv = m["movements"][p["move"]]["desc"]
    kind = m["subelements"][p["sub_id"]]["name"].lower() if p["sub_id"] else m["elements"][p["element"]]["name"].lower()
    eff = {
        "damage": f"deals {p['power']:.0f} {kind} damage", "heal": f"heals {p['power']:.0f}",
        "strength": f"+{p['power']:.0f} Strength for {p['duration']:.0f}s",
        "speed": f"+{p['power']:.0f} Speed for {p['duration']:.0f}s",
        "dexterity": f"+{p['power']:.0f} Dexterity for {p['duration']:.0f}s",
        "health": f"+{p['power']:.0f} max health for {p['duration']:.0f}s",
        "defense": f"absorbs {p['power'] * 4:.0f} damage for {p['duration']:.0f}s",
        "knockback": "hurls enemies away", "root": f"roots enemies for {p['duration']:.1f}s",
        "affliction": f"inflicts {p['status']} for {p['duration']:.1f}s",
    }[p["stat"]]
    cost = f"{p['mana']} mana" + (f" + {p['hp_cost']} health" if p["hp_cost"] else "")
    return f"{mv} It {eff}. ({stat}; {cost}; size {p['size']:.2g}; area {p['area']})"


def starter_spellbook():
    return [dict(s) for s in STARTER_SPELLS]


def migrate(data, spells_list):
    """Upgrade spells saved by older versions in place (element / focus / size)."""
    out = []
    for sp in spells_list:
        try:
            out.append(normalize(data, sp))
        except SpellError:
            continue
    return out


def capacity(data, level):
    sb = data.magic["spellbook"]
    return min(sb["max_capacity"], sb["base_capacity"] + level // sb["per_levels"])


MAX_DRAFTS = 6


def revise(state, where, index, spell):
    """Edit an existing spell (book or draft) in place."""
    validate(state.data, spell, state.player.level)
    lst = state.spellbook if where == "book" else state.spell_drafts
    if not (0 <= index < len(lst)):
        return False, "No such spell."
    if any(d["name"] == spell["name"] for k, d in enumerate(state.spell_drafts + state.spellbook)
           if d is not lst[index]):
        return False, "A spell with that name already exists."
    lst[index] = dict(spell)
    return True, f"'{spell['name']}' rewritten."


def save_draft(state, spell):
    """Creating a spell is free: it goes to the drafts list (not yet usable outside practice)."""
    validate(state.data, spell, state.player.level)
    if len(state.spell_drafts) >= MAX_DRAFTS:
        return False, f"You can keep at most {MAX_DRAFTS} drafts. Discard one first."
    if any(d["name"] == spell["name"] for d in state.spell_drafts + state.spellbook):
        return False, "A spell with that name already exists."
    state.spell_drafts.append(dict(spell))
    return True, f"Draft '{spell['name']}' saved."


# ------------------------------------------------------------------ mana economy (real-time)
REGEN_CALM = 0.05          # fraction of max mana restored per second out of combat
REGEN_COMBAT = 0.025       # ...and while fighting
HIT_MANA_RATIO = 0.4       # weapon damage dealt -> mana
HIT_MANA_CAP = 12.0        # most mana one weapon hit can restore


def regen_per_second(char, in_combat):
    return char.max_mana * (REGEN_COMBAT if in_combat else REGEN_CALM)


def mana_from_hit(damage, skill):
    """Mana restored by landing a weapon hit (spells and blocked hits give none)."""
    if skill == "magic" or damage <= 0:
        return 0.0
    return min(HIT_MANA_CAP, damage * HIT_MANA_RATIO)


def inscribe(state, draft_index, replace_index=None, at_table=True):
    """Record a draft in the spell book. Free and possible anywhere (QoL rework); `at_table` is kept only
    for call compatibility. The book's size still grows with level."""
    data = state.data
    p = state.player
    if not (0 <= draft_index < len(state.spell_drafts)):
        return False, "No such draft."
    draft = state.spell_drafts[draft_index]
    validate(data, draft, p.level)
    cap = capacity(data, p.level)
    if replace_index is None and len(state.spellbook) >= cap:
        return False, f"Your spell book is full ({cap}). Choose a spell to replace."
    if replace_index is not None:
        old = state.spellbook[replace_index]["name"]
        state.spellbook[replace_index] = draft
        msg = f"'{old}' fades from the page. '{draft['name']}' is inscribed in its place."
    else:
        state.spellbook.append(draft)
        msg = f"'{draft['name']}' is inscribed in your spell book."
    del state.spell_drafts[draft_index]
    p.train("magic", 10 + draft["tier"] * 5, state.race_data)
    state.memory.record("player", "accomplishment", f"{p.name} inscribed the spell '{draft['name']}'.",
                        day=state.clock.day_index, minute=state.clock.total_minutes % 1440, importance=2)
    return True, msg
