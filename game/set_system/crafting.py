"""Crafting: recipes at stations, ingredient checks, skill gates, knowledge gates, time and training."""
from . import timeflow

STATIONS = {
    "furnace": "Furnace", "anvil": "Anvil", "workbench": "Workbench", "stove": "Stove",
    "alchemy": "Alchemy Table", "campfire": "Campfire",
}
# map objects that act as crafting stations
OBJECT_STATION = {"furnace": "furnace", "anvil": "anvil", "workbench": "workbench", "stove": "stove",
                  "alchemy_table": "alchemy", "campfire": "campfire"}


def recipes_for(data, station):
    out = [r for r in data.recipes.values() if r["station"] == station or r.get("alt_station") == station]
    return sorted(out, key=lambda r: (r.get("skill", 0), data.item(r["out"])["name"]))


def check(state, recipe, times=1):
    """(ok, reason) for crafting `recipe` `times` times."""
    p = state.player
    need = recipe.get("requires")
    if need and need not in state.known_recipes:
        return False, f"You don't know how to work {need.title()} yet."
    if p.skills["crafting"] < recipe.get("skill", 0):
        return False, f"Needs Crafting {recipe['skill']}."
    for item, qty in recipe["inputs"].items():
        if not p.inventory.has(item, qty * times):
            return False, f"Missing {state.data.item(item)['name']} ({p.inventory.count(item)}/{qty * times})."
    return True, ""


def craft_minutes(state, recipe):
    return max(5, int(recipe["minutes"] * (1 - state.player.skills["crafting"] / 200)))


def craft(state, recipe, times=1):
    """Craft and advance time. Returns (ok, messages)."""
    ok, why = check(state, recipe, times)
    if not ok:
        return False, [why]
    p = state.player
    for item, qty in recipe["inputs"].items():
        p.inventory.remove(item, qty * times)
    p.inventory.add(recipe["out"], recipe["qty"] * times)
    minutes = craft_minutes(state, recipe) * times
    msgs = timeflow.advance(state, minutes)
    xp = (3 + recipe.get("skill", 0) / 5) * times
    res = p.train("crafting", xp, state.race_data)
    p.train("dexterity", xp * 0.2, state.race_data)
    state.stats["crafted"] = state.stats.get("crafted", 0) + recipe["qty"] * times
    name = state.data.item(recipe["out"])["name"]
    msgs.insert(0, f"Crafted {recipe['qty'] * times}x {name} ({minutes} min).")
    if res["point_up"]:
        msgs.append(f"Crafting improved to {p.skills['crafting']:.0f}.")
    return True, msgs


def learn(state, item_id):
    """Use a recipe item (e.g. smithing notes) to learn a gated recipe family."""
    it = state.data.item(item_id)
    if it["type"] != "recipe":
        return False, "That isn't something you can study."
    if it["unlocks"] in state.known_recipes:
        return False, "You already know this."
    state.player.inventory.remove(item_id)
    state.known_recipes.append(it["unlocks"])
    state.memory.record("player", "accomplishment", f"{state.player.name} learned to work {it['unlocks'].title()}.",
                        day=state.clock.day_index, minute=state.clock.total_minutes % 1440, importance=3)
    return True, f"You study the notes. You can now craft with {it['unlocks'].title()}!"
