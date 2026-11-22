"""Food, water, mana and natural healing over game time."""

FOOD_PER_HOUR = 3.0
WATER_PER_HOUR = 4.5
LOW = 25.0


def status(char):
    """List of current need conditions."""
    out = []
    if char.food <= 0:
        out.append("starving")
    elif char.food < LOW:
        out.append("hungry")
    if char.water <= 0:
        out.append("dehydrated")
    elif char.water < LOW:
        out.append("thirsty")
    return out


def apply_modifiers(char):
    """Recompute temporary attribute penalties from needs."""
    mods = {}
    st = status(char)
    if "hungry" in st:
        for a in ("strength", "speed"):
            mods[a] = mods.get(a, 0) - char.attributes[a] * 0.15
    if "starving" in st:
        for a in ("strength", "speed", "dexterity"):
            mods[a] = mods.get(a, 0) - char.attributes[a] * 0.3
    if "thirsty" in st:
        for a in ("speed", "dexterity"):
            mods[a] = mods.get(a, 0) - char.attributes[a] * 0.15
    if "dehydrated" in st:
        for a in ("strength", "speed", "dexterity"):
            mods[a] = mods.get(a, 0) - char.attributes[a] * 0.3
    char.modifiers = mods
    return st


def tick(char, hours, race_data=None, exertion=1.0, resting=False, water_mult=1.0):
    """Advance needs by `hours` of game time. Returns a list of messages for notable changes."""
    msgs = []
    if hours <= 0 or not char.alive:
        return msgs
    nm = (race_data or {}).get("needs_mult", {})
    before = set(status(char))
    rest_mult = 0.6 if resting else 1.0
    char.food = max(0.0, char.food - FOOD_PER_HOUR * hours * nm.get("food", 1.0) * exertion * rest_mult)
    char.water = max(0.0, char.water - WATER_PER_HOUR * hours * nm.get("water", 1.0) * exertion * rest_mult * water_mult)
    # mana regeneration
    regen = char.max_mana * (0.18 if resting else 0.06) * hours
    char.mana = min(char.max_mana, char.mana + regen)
    st = status(char)
    # starvation / dehydration damage, otherwise slow natural healing
    harm = 0.0
    if "starving" in st:
        harm += 2.0 * hours
    if "dehydrated" in st:
        harm += 3.0 * hours
    if harm:
        char.damage(harm)
    elif "hungry" not in st and "thirsty" not in st:
        char.heal(char.max_hp * (0.08 if resting else 0.02) * hours)
    apply_modifiers(char)
    after = set(st)
    for s in sorted(after - before):
        msgs.append({"hungry": "You are getting hungry.", "starving": "You are starving! You are losing health.",
                     "thirsty": "You are thirsty.", "dehydrated": "You are dehydrated! You are losing health."}[s])
    return msgs
