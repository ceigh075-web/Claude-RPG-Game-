"""Crime, bounties, town guards and seizing settlements (deterministic Set System rules).

* Theft from barrels, crates and other people's chests, robbing the fallen, assault and murder in a town
  are crimes when someone sees them: the town's faction thinks less of you, witnesses remember, and the
  town puts a bounty on you. Guards attack wanted criminals on sight; paying the fine at a job board (or to
  a guard) clears it.
* A town whose guards have all been beaten can be seized at its job board. The town then pays you a daily
  tax and its shops give you a discount, but its former faction turns on you and may take it back unless your
  retainers hold it.
"""
from . import factions
from . import relationships as rel

FINES = {"theft": 2.0, "assault": 40, "murder": 150, "robbery": 3.0}
RETAKE_CHANCE = 0.08          # per day, for each seized town not held by enough retainers
HOLD_RETAINERS = 3
OWNER_DISCOUNT = 0.85


def _stamp(state):
    return dict(day=state.clock.day_index, minute=state.clock.total_minutes % 1440)


def town_of(state):
    loc = state.location
    return loc if loc in state.data.towns else None


def bounty(state, town):
    return int(state.flags.get(f"bounty:{town}", 0)) if town else 0


def add_bounty(state, town, amount, what):
    if not town or owner(state, town) == "player":
        return []
    state.flags[f"bounty:{town}"] = bounty(state, town) + int(amount)
    name = state.data.location(town)["name"]
    state.memory.record(town, "significant", f"{name} put a {bounty(state, town)}-mark bounty on {state.player.name} for "
                        f"{what}.", importance=3, related=["player"], location=town, **_stamp(state))
    return [f"Wanted in {name}: {bounty(state, town)} marks. Guards will try to arrest you."]


def pay_fine(state, town):
    owed = bounty(state, town)
    if owed <= 0:
        return False, "You're not wanted here."
    if state.gold < owed:
        return False, f"The fine is {owed} marks; you have {state.gold}."
    state.gold -= owed
    state.flags[f"bounty:{town}"] = 0
    fac = state.data.towns[town].get("faction")
    if fac and fac != "none":
        factions.change_rep(state, fac, 2, "paid a fine")
    return True, f"You pay {owed} marks. Your name is cleared in {state.data.location(town)['name']}."


def crime(state, kind, value=0, witnesses=(), label="someone"):
    """Record a witnessed crime. witnesses = list of named-NPC ids who saw it (anonymous people count too)."""
    msgs = []
    town = town_of(state)
    fac = state.data.towns[town].get("faction") if town else None
    if fac and fac != "none":
        factions.change_rep(state, fac, -3 if kind in ("theft", "robbery") else -5, f"{kind} in town")
    for nid in witnesses:
        if nid in state.data.npcs:
            rel.change(state, nid, trust=-6, conflict=4)
            state.memory.record(nid, "witnessed", f"{state.data.npcs[nid]['name']} saw {state.player.name} commit "
                                f"{kind} against {label}.", importance=2, related=["player"], location=state.location,
                                **_stamp(state))
    rel.note(state, "greed" if kind in ("theft", "robbery") else "cruelty", 1)
    fine = FINES[kind]
    amount = fine * max(5, value) + 10 if isinstance(fine, float) else fine
    msgs += add_bounty(state, town, amount, kind)
    return msgs


def loot_container(state, loc_key, obj_key, chest=False):
    """Search a barrel / crate / chest (once a day each). Returns (messages, value taken)."""
    from ..world import effects
    ls = state.location_state(loc_key).setdefault("searched", {})
    if ls.get(obj_key) == state.clock.day_index:
        return ["You've already gone through this today."], 0
    ls[obj_key] = state.clock.day_index
    gold0 = state.gold
    inv0 = dict(state.player.inventory.items)
    msgs = effects.roll_loot(state, "container", 2.0 if chest else 1.0)
    value = state.gold - gold0
    for item, n in state.player.inventory.items.items():
        value += max(0, n - inv0.get(item, 0)) * state.data.item(item)["value"]
    return msgs, value


# ------------------------------------------------------------------ seizing settlements
def owner(state, town):
    from . import world_events
    return world_events.holder(state, town)


def can_seize(state, town, guards_standing, guards_seen):
    if not town or owner(state, town) == "player":
        return False, "You already hold this town." if town else "Not a town."
    if guards_seen == 0:
        return False, "Its guards must be dealt with first."
    if guards_standing > 0:
        return False, f"{guards_standing} guard{'s' if guards_standing > 1 else ''} still stand against you."
    return True, ""


def seize(state, town):
    from . import world_events
    data = state.data
    t = data.towns[town]
    fac = t.get("faction")
    world_events.world(state)["territory"][town] = "player"
    state.flags[f"bounty:{town}"] = 0
    if fac and fac != "none":
        factions.change_rep(state, fac, -40, f"seized {t['name']}")
    for npc in data.npcs.values():
        if npc["home"] == town:
            rel.change(state, npc["id"], trust=-10, respect=8)
    state.memory.record("world", "political", f"{state.player.name} seized control of {t['name']}"
                        + (f" from the {data.factions[fac]['name']}" if fac in data.factions else "") + ".",
                        importance=5, related=["player"], location=town, **_stamp(state))
    return [f"{t['name']} is yours. Its people pay you taxes and its merchants give you better prices.",
            "Its former masters will want it back: keep retainers to hold it."]


def owned_towns(state):
    from . import world_events
    return [t for t, h in world_events.world(state)["territory"].items() if h == "player" and t in state.data.towns]


def price_factor(state, town):
    return OWNER_DISCOUNT if town and owner(state, town) == "player" else 1.0


def daily(state, rng):
    """Taxes from held towns; former owners may take them back."""
    from . import morale, world_events
    msgs = []
    for town in owned_towns(state):
        t = state.data.towns[town]
        tax = max(5, t.get("population", 100) // 25)
        state.gold += tax
        msgs.append(f"{t['name']} pays you {tax} marks in taxes.")
        if len(morale.retainers(state)) < HOLD_RETAINERS and rng.random() < RETAKE_CHANCE:
            fac = t.get("faction") if t.get("faction") not in (None, "none") else None
            world_events.world(state)["territory"][town] = fac or "free"
            msgs.append(f"{t['name']} has been retaken" + (f" by the {state.data.factions[fac]['name']}" if fac else "") + "!")
            state.memory.record("world", "political", f"{t['name']} threw off {state.player.name}'s rule.", importance=4,
                                related=["player"], location=town, **_stamp(state))
    return msgs
