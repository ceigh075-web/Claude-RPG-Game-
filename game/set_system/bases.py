"""Bases of operations (Set System): every house you own and your outpost.

A base is somewhere to sleep, store goods, hold prisoners, craft and plan from. One of them is your home base.
From any base you can hire a carter to ride to another of your bases: the journey takes the road time, is
safe, and costs a few marks per 10 km. Everything here is deterministic game state; no AI is involved.
"""
from . import base as base_mod
from . import morale, timeflow

CARTER_KMH = 6.0
CARTER_MARKS_PER_10KM = 3


def starter_house(state, world):
    """Give a new character the small house in their starting town (deed included). Returns a message or None."""
    from ..world import mapgen
    town = state.location
    if town in state.property or town not in state.data.towns:
        return None
    m = mapgen.generate(state.data, world, town)
    house = next((b for b in getattr(m, "buildings", {}).values() if b["type"] == "property_for_sale"), None)
    if house is None:
        return None
    state.property[town] = {"building": house["id"], "bought": state.clock.day_index, "storage": {}, "starter": True}
    state.player.inventory.add("house_deed")
    inv = base_mod.storage(state, state.property[town])
    for item, n in (("ration", 2), ("bandage", 1), ("wood", 4)):
        inv.add(item, n)
    base_mod.save_storage(state.property[town], inv)
    state.settings["home_base"] = f"house:{town}"
    return (f"You have a small house in {state.data.location(town)['name']}: a bed, a storage chest, a workbench and "
            "a scribing table. It's your first base of operations.")


def list_bases(state):
    """[{id, kind, name, location, beds, cells, storage, stations, home}] for every base you hold."""
    data = state.data
    home = state.settings.get("home_base")
    out = []
    for town, prop in sorted(getattr(state, "property", {}).items()):
        inv = base_mod.storage(state, prop)
        out.append({"id": f"house:{town}", "kind": "house", "location": town,
                    "name": f"House in {data.location(town)['name']}" + (" (your first home)" if prop.get("starter") else ""),
                    "beds": 1 + morale.HOUSE_BEDS, "cells": morale.HOUSE_CELLS,
                    "storage": sum(inv.items.values()),
                    "stations": ["bed", "storage chest", "workbench", "stove", "scribing table", "training dummy"]})
    if base_mod.founded(state):
        loc = state.base.get("location")
        inv = base_mod.storage(state, state.base)
        built = [state.data.base["buildings"][b["type"]]["name"] for b in state.base.get("buildings", {}).values()
                 if b.get("done")]
        out.append({"id": "outpost", "kind": "outpost", "location": loc,
                    "name": f"Outpost at {data.location(loc)['name']}" if loc in data.locations else "Your outpost",
                    "beds": morale.OUTPOST_BEDS + morale.BUNK_BEDS * len(base_mod.buildings_of(state, "bunkhouse")),
                    "cells": morale.STOCKADE_CELLS * len(base_mod.buildings_of(state, "stockade")),
                    "storage": sum(inv.items.values()), "stations": built or ["no buildings yet"]})
    for b in out:
        b["home"] = b["id"] == home
    if out and not any(b["home"] for b in out):
        out[0]["home"] = True
    return out


def set_home(state, base_id):
    if not any(b["id"] == base_id for b in list_bases(state)):
        return False, "That isn't one of your bases."
    state.settings["home_base"] = base_id
    name = next(b["name"] for b in list_bases(state) if b["id"] == base_id)
    return True, f"{name} is now your home base."


def home_location(state):
    for b in list_bases(state):
        if b["home"]:
            return b["location"]
    return None


def at_base(state):
    """The base you're standing in (by location), or None."""
    return next((b for b in list_bases(state) if b["location"] == state.location), None)


def carter_quote(state, world, base_id):
    """(ok, km, hours, marks, reason) for riding from the base you're at to another of your bases."""
    here = at_base(state)
    target = next((b for b in list_bases(state) if b["id"] == base_id), None)
    if here is None:
        return False, 0, 0, 0, "Carters only run between your own bases: go to one first."
    if target is None:
        return False, 0, 0, 0, "No such base."
    if target["location"] == state.location:
        return False, 0, 0, 0, "You're already there."
    path, km = world.shortest_path(state.location, target["location"])
    if not path:
        return False, 0, 0, 0, "No road leads there."
    hours = km / CARTER_KMH
    marks = max(2, int(round(km / 10 * CARTER_MARKS_PER_10KM)))
    return True, km, hours, marks, ""


def ride_carter(state, world, base_id):
    ok, km, hours, marks, why = carter_quote(state, world, base_id)
    if not ok:
        return False, why
    if state.gold < marks:
        return False, f"The carter wants {marks} marks."
    target = next(b for b in list_bases(state) if b["id"] == base_id)
    state.gold -= marks
    timeflow.advance(state, int(hours * 60), resting=True)
    state.location = target["location"]
    state.local_pos = None
    state.sub_location = None
    state.mode = "local"
    state.discovered.add(target["location"])
    base_mod.hist(state, f"{state.player.name} rode a carter's wagon to their {target['name'].lower()}.", 1,
                  target["location"], "travel")
    return True, f"You ride the carter's wagon {km:.0f} km ({hours:.0f} h, {marks} marks) to your {target['name'].lower()}."
