"""Interactions with map objects. Each returns an Interaction describing what happens.

All state changes are performed by Set System code here (not by the scene), after any timed action.
"""
from ..set_system import timeflow
from ..world import effects, mapgen

RESPAWN_DAYS = {"bush": 3, "ore_vein": 7, "scavenge": 6, "tree": 5, "mana_crystal_node": 14, "rock": 4}
MIN_PER_DAY = 1440
LABELS = {
    "bush": "Forage", "ore_vein": "Mine", "scavenge": "Search", "tree": "Chop", "pine": "Chop",
    "dead_tree": "Chop", "mana_crystal_node": "Mine crystal", "well": "Drink & refill", "door": "Enter",
    "exit_door": "Leave", "bed": "Sleep", "counter": "Trade", "landmark": "Examine", "campfire": "Rest",
    "bounty_board": "Read", "water": "Drink & refill", "rock": "Break rock",
}
CHOP_KINDS = ("tree", "pine", "dead_tree")


class Interaction:
    def __init__(self, label, minutes=0, run=None, message=None, kind="instant"):
        self.label = label
        self.minutes = minutes
        self.run = run          # callable(state) -> list[str]; executed when the action completes
        self.message = message  # immediate message (for refusals)
        self.kind = kind        # instant | timed | refuse | scene


def obj_state(state, loc_key, obj):
    """Per-object persistent state: remaining charges and respawn time."""
    ls = state.location_state(loc_key).setdefault("objects", {})
    st = ls.get(obj["key"])
    now = state.clock.total_minutes
    if st and st.get("respawn") is not None and now >= st["respawn"]:
        st = None
        del ls[obj["key"]]
    if st is None:
        return {"charges": obj.get("charges", 1), "respawn": None}
    return st


def available(state, loc_key, obj):
    return obj_state(state, loc_key, obj)["charges"] > 0


def consume(state, loc_key, obj, kind):
    ls = state.location_state(loc_key).setdefault("objects", {})
    st = obj_state(state, loc_key, obj)
    st["charges"] -= 1
    if st["charges"] <= 0:
        st["respawn"] = state.clock.total_minutes + RESPAWN_DAYS.get(kind, 5) * MIN_PER_DAY
    ls[obj["key"]] = st


def depleted_keys(state, loc_key, objects):
    return {o["key"] for o in objects if o.get("harvest") and not available(state, loc_key, o)}


def has_tool(state, tool):
    inv = state.player.inventory
    if tool == "mining":
        if inv.has("pickaxe"):
            return True
        eq = state.player.equipment.get("weapon")
        return bool(eq and inv.has(eq) and state.data.item(eq)["weapon"] == "hammer")
    if tool == "woodcutting":
        if inv.has("hatchet"):
            return True
        eq = state.player.equipment.get("weapon")
        return bool(eq and inv.has(eq) and state.data.item(eq)["weapon"] in ("axe", "battleaxe"))
    return False


def for_object(state, loc_key, obj, lmap=None):
    """Return the Interaction for an object, or None if it isn't interactive."""
    data = state.data
    p = state.player
    race = state.race_data
    k = obj["kind"]

    if k == "bush":
        if not available(state, loc_key, obj):
            return Interaction("Forage", kind="refuse", message="Picked clean. It will regrow in a few days.")

        def run(s):
            n = 1 + s.rng.randint(0, 1 + int(p.skills["gathering"] // 25))
            p.inventory.add(obj["yields"], n)
            p.train("gathering", 4, race)
            consume(s, loc_key, obj, "bush")
            return [f"Foraged {n}x {data.item(obj['yields'])['name']}."]
        return Interaction("Forage", minutes=15, run=run, kind="timed")

    if k == "ore_vein":
        ore = data.ores[obj["ore"]]
        if not available(state, loc_key, obj):
            return Interaction("Mine", kind="refuse", message="This vein is exhausted for now.")
        if not has_tool(state, "mining"):
            return Interaction("Mine", kind="refuse", message=f"A vein of {ore['name']}. You need a pickaxe to mine it.")
        if p.skills["mining"] < ore["mining_skill"]:
            return Interaction("Mine", kind="refuse",
                               message=f"{ore['name']} is too hard for you to work (needs Mining {ore['mining_skill']}).")
        minutes = max(8, int(ore["mine_time"] * (1 - p.skills["mining"] / 150) * (1 - (p.attr('strength') - 10) / 150)))

        def run(s):
            n = 1 + (1 if s.rng.random() < p.skills["mining"] / 100 else 0)
            p.inventory.add(f"{obj['ore']}_ore", n)
            p.train("mining", 6 + ore["tier"] * 2, race)
            p.train("strength", 3, race)
            consume(s, loc_key, obj, "ore_vein")
            return [f"Mined {n}x {data.item(obj['ore'] + '_ore')['name']}."]
        return Interaction(f"Mine {ore['name']}", minutes=minutes, run=run, kind="timed")

    if k == "mana_crystal_node":
        if not available(state, loc_key, obj):
            return Interaction("Mine crystal", kind="refuse", message="Only dull stumps of crystal remain.")
        if not has_tool(state, "mining"):
            return Interaction("Mine crystal", kind="refuse", message="Glowing mana crystal. You need a pickaxe.")

        def run(s):
            p.inventory.add("mana_crystal", 1)
            p.train("mining", 8, race)
            p.train("magic", 2, race)
            consume(s, loc_key, obj, "mana_crystal_node")
            return ["Chipped free a Mana Crystal."]
        return Interaction("Mine crystal", minutes=40, run=run, kind="timed")

    if k in CHOP_KINDS and obj.get("choppable"):
        if not available(state, loc_key, obj):
            return Interaction("Chop", kind="refuse", message="You've taken all the good wood from this one for now.")
        if not has_tool(state, "woodcutting"):
            return Interaction("Chop", kind="refuse", message="You need a hatchet or an axe to cut wood.")

        def run(s):
            n = 1 + s.rng.randint(0, 1)
            p.inventory.add("wood", n)
            p.train("strength", 3, race)
            p.train("gathering", 2, race)
            consume(s, loc_key, obj, "tree")
            return [f"Cut {n}x Wood."]
        return Interaction("Chop wood", minutes=30, run=run, kind="timed")

    if k == "rock" and lmap is not None and lmap.kind == "wild":
        if not available(state, loc_key, obj) or not has_tool(state, "mining"):
            return None

        def run(s):
            p.inventory.add("stone", 1)
            p.train("strength", 2, race)
            consume(s, loc_key, obj, "rock")
            return ["Broke off a chunk of Stone."]
        return Interaction("Break rock", minutes=15, run=run, kind="timed")

    if k == "scavenge":
        if not available(state, loc_key, obj):
            return Interaction("Search", kind="refuse", message="Already picked over.")

        def run(s):
            msgs = effects.roll_loot(s, "scavenge", 1 + p.skills["gathering"] / 150)
            p.train("gathering", 3, race)
            p.train("dexterity", 1, race)
            consume(s, loc_key, obj, "scavenge")
            return msgs
        return Interaction("Search the debris", minutes=20, run=run, kind="timed")

    if k in ("well", "water"):
        def run(s):
            p.water = 100.0
            n = effects.refill_water(s)
            return ["You drink your fill." + (f" Filled {n} flask{'s' if n != 1 else ''}." if n else "")]
        return Interaction("Drink & refill flasks", minutes=5, run=run, kind="timed")

    if k == "campfire":
        def run(s):
            return ["You rest by the fire for an hour."] + timeflow.advance(s, 60, resting=True)
        return Interaction("Rest by the fire (1 h)", minutes=0, run=run, kind="instant")

    if k == "landmark":
        loc = data.location(loc_key) if loc_key in data.locations else {}
        return Interaction("Examine", kind="refuse",
                           message=f"{obj['label']}. {loc.get('reason', '')}")

    if k == "bounty_board":
        return Interaction("Read the board", kind="scene")

    if k in ("door", "exit_door", "counter", "bed"):
        return Interaction(LABELS[k], kind="scene")
    return None


def water_adjacent(lmap, tx, ty):
    for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
        if lmap.get(tx + dx, ty + dy) == mapgen.WATER:
            return True
    return False
