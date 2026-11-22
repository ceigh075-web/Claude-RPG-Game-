"""Companions: recruiting, the squad, tasks, shared supplies, buddy bonds between companions, and reactions."""
from . import items as items_mod
from . import needs, recruitment, relationships as rel
from .stats import Character

MAX_SQUAD = 4
TASKS = {"follow": "Follow you and fight", "wait": "Wait at the current location", "gather": "Gather while you explore",
         "guard": "Guard your outpost", "work": "Work at your outpost", "home": "Rest at your house"}
FOOD_PREF = ["ration", "cooked_meat", "bread", "fish", "meat", "mushrooms", "berries", "kelp"]
DRINK_PREF = ["water", "ale"]


def build_character(data, npc):
    c = Character(npc["id"], npc["name"], npc["race"], npc["attributes"], npc["skills"], npc["pronouns"])
    c.inventory.bind(data)
    for item in npc["equipment"]:
        c.inventory.add(item)
        slot = items_mod.weapon_slot(data, item)
        if slot and not c.equipment.get(slot):
            c.equipment[slot] = item
    c.inventory.add("ration", 2)
    c.inventory.add("water", 2)
    c.hp = c.max_hp
    c.mana = c.max_mana
    c.food = c.water = 80.0
    return c


def squad(state):
    return [cid for cid, c in state.companions.items() if c["active"]]


def char(state, cid):
    return state.companions[cid]["char"]


def recruit(state, npc):
    ok, path = recruitment.can_recruit(state, npc)
    if not ok:
        return False, f"{npc['name']} won't join you yet."
    req = {"main": npc["recruit"], "alt": npc["recruit"].get("alt", {}), "rejoin": {}}[path]
    cost = req.get("gold", 0)
    if cost:
        state.gold -= cost
    state.flags[f"recruited:{npc['id']}"] = True
    active = len(squad(state)) < MAX_SQUAD
    state.companions[npc["id"]] = {"char": build_character(state.data, npc), "task": "follow" if active else "wait",
                                   "active": active, "joined": state.clock.day_index, "wait_at": None if active else state.location,
                                   "downed": False}
    rel.change(state, npc["id"], trust=10, friendship=5)
    state.memory.record(npc["id"], "recruited", f"{npc['name']} joined {state.player.name}'s company"
                        + (f" for {cost} marks." if cost else "."), day=state.clock.day_index,
                        minute=state.clock.total_minutes % 1440, importance=3, related=["player"], location=state.location)
    msg = f"{npc['name']} joins you!" + ("" if active else f" (Your squad is full: they'll wait here in "
                                                         f"{state.data.location(state.location)['name']}.)")
    if npc.get("leader"):
        succession(state, npc)
    return True, msg


def succession(state, npc):
    """A faction leader leaving to follow the player: their faction appoints a successor (world history)."""
    fac = npc["faction"]
    name = state.data.factions[fac]["name"]
    state.flags[f"succession:{fac}"] = True
    state.memory.record("world", "political", f"{npc['name']} stepped down to travel with {state.player.name}. "
                        f"A successor now leads the {name}.", day=state.clock.day_index,
                        minute=state.clock.total_minutes % 1440, importance=5, related=["player", npc["id"]],
                        location=state.location)


def dismiss(state, cid):
    comp = state.companions.pop(cid, None)
    if comp is None:
        return False, "Not in your company."
    npc = state.data.npcs[cid]
    c = comp["char"]
    returned = []
    for item, qty in list(c.inventory.items.items()):
        if item not in c.equipment.values() and item not in npc["equipment"] and item not in ("ration", "water"):
            state.player.inventory.add(item, qty)
            returned.append(item)
    state.flags[f"recruited:{cid}"] = False
    # they remember being let go; it was not a betrayal, but it stings a little
    rel.change(state, cid, friendship=-3)
    state.memory.record(cid, "dismissed", f"{state.player.name} parted ways with {npc['name']}, who went home.",
                        day=state.clock.day_index, minute=state.clock.total_minutes % 1440, importance=2, related=["player"])
    state.flags[f"rejoin_free:{cid}"] = True
    return True, f"{npc['name']} heads home." + (" They hand back the shared supplies they carried." if returned else "")


def set_task(state, cid, task):
    comp = state.companions[cid]
    if task not in TASKS:
        return False, "Unknown task."
    if task in ("guard", "work"):
        from . import base
        return base.assign(state, cid, guard=(task == "guard"))
    if task == "home" and not state.property:
        return False, "You don't own a house yet."
    if task in ("follow", "gather") and not comp["active"]:
        if len(squad(state)) >= MAX_SQUAD:
            return False, f"Your squad is full ({MAX_SQUAD})."
        comp["active"] = True
    if task in ("wait", "home"):
        comp["active"] = False
        comp["wait_at"] = state.location if task == "wait" else next(iter(state.property))
    comp["task"] = task
    return True, f"{state.data.npcs[cid]['name']}: {TASKS[task].lower()}."


def give(state, cid, item, qty=1):
    c = char(state, cid)
    if not state.player.inventory.has(item, qty):
        return False, "You don't have that many."
    state.player.inventory.remove(item, qty)
    c.inventory.add(item, qty)
    return True, f"Gave {qty}x {state.data.item(item)['name']}."


def take(state, cid, item, qty=1):
    c = char(state, cid)
    if not c.inventory.has(item, qty):
        return False, "They don't have that many."
    c.inventory.remove(item, qty)
    for slot, eq in c.equipment.items():
        if eq == item and not c.inventory.has(item):
            c.equipment[slot] = None
    state.player.inventory.add(item, qty)
    return True, f"Took {qty}x {state.data.item(item)['name']}."


# ------------------------------------------------------------------ needs
def eat_from_packs(state, c, threshold=40):
    """Companions eat and drink from their own pack first, then from the player's."""
    msgs = []
    for need, prefs in (("food", FOOD_PREF), ("water", DRINK_PREF)):
        for _ in range(4):
            if getattr(c, need) >= threshold:
                break
            src = next((inv for inv in (c.inventory, state.player.inventory) for i in prefs if inv.has(i)), None)
            if src is None:
                break
            item = next(i for i in prefs if src.has(i))
            it = state.data.item(item)
            src.remove(item)
            c.food = min(100.0, c.food + it.get("food", 0))
            c.water = min(100.0, c.water + it.get("water", 0))
    return msgs


def tick_needs(state, hours, exertion=1.0, resting=False, water_mult=1.0):
    for cid in squad(state):
        c = char(state, cid)
        needs.tick(c, hours, state.data.races[c.race], exertion=exertion, resting=resting, water_mult=water_mult)
        if c.hp <= 0:
            c.hp = 1.0
            c.alive = True
        eat_from_packs(state, c)


# ------------------------------------------------------------------ bonds between companions (buddy system)
def bond_key(a, b):
    return "|".join(sorted((a, b)))


def bond(state, a, b):
    return state.bonds.setdefault(bond_key(a, b), {"value": 0, "status": "strangers"})


def daily(state, rng):
    """Once per in-game day: companions in the squad grow closer or clash; couples may form."""
    msgs = []
    ids = squad(state)
    data = state.data
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            na, nb = data.npcs[a], data.npcs[b]
            comp = rel.npc_compatibility(na, nb)
            bd = bond(state, a, b)
            roll = rng.random()
            if roll < comp / 130:
                bd["value"] = min(100, bd["value"] + 6)
                event = "companion_bond"
                text = f"{na['name']} and {nb['name']} share stories by the fire."
            elif roll > 0.75 + comp / 400:
                bd["value"] = max(-100, bd["value"] - 8)
                event = "companion_conflict"
                text = f"{na['name']} and {nb['name']} argue over {'money' if na['personality']['greed'] > 6 else 'how to do things'}."
            else:
                continue
            old = bd["status"]
            if bd["value"] >= 70 and na.get("romanceable") and nb.get("romanceable") and comp >= 60 \
                    and state.relationships.get(a, {}).get("romance") not in ("dating", "partners") \
                    and state.relationships.get(b, {}).get("romance") not in ("dating", "partners"):
                bd["status"] = "couple"
            elif bd["value"] >= 40:
                bd["status"] = "friends" if old != "couple" else old
            elif bd["value"] <= -40:
                bd["status"] = "rivals"
            elif old not in ("couple",):
                bd["status"] = "acquainted"
            if bd["status"] != old and bd["status"] in ("friends", "rivals", "couple"):
                text = {"friends": f"{na['name']} and {nb['name']} have become friends.",
                        "rivals": f"{na['name']} and {nb['name']} can't stand each other anymore.",
                        "couple": f"{na['name']} and {nb['name']} are now a couple!"}[bd["status"]]
                state.memory.record(a, event, text, day=state.clock.day_index, importance=3, related=[b, "player"])
                msgs.append(text)
            elif rng.random() < 0.35:
                msgs.append(text)
                state.memory.add_chatter(a, text, state.clock.day_index)
    return msgs


# ------------------------------------------------------------------ shared experiences & reactions
def shared_victory(state, enemies_killed):
    names = []
    for cid in squad(state):
        rel.change(state, cid, friendship=2, trust=2, respect=1)
        names.append(state.data.npcs[cid]["name"])
        if enemies_killed >= 3:
            state.memory.record(cid, "battle", f"{state.data.npcs[cid]['name']} fought beside {state.player.name} "
                                f"and won ({enemies_killed} foes).", day=state.clock.day_index,
                                minute=state.clock.total_minutes % 1440, importance=2, related=["player"],
                                location=state.location)
    return names


def shared_travel(state, location):
    for cid in squad(state):
        rel.change(state, cid, friendship=1)
        state.memory.add_chatter(cid, f"Travelled with {state.player.name} to {state.data.location(location)['name']}.",
                                 state.clock.day_index)


def react_to_kill(state, faction):
    """Companions from a faction disapprove when the player kills its members."""
    msgs = []
    for cid in squad(state):
        npc = state.data.npcs[cid]
        if npc.get("faction") == faction:
            rel.change(state, cid, friendship=-6, trust=-4, conflict=6)
            msgs.append(f"{npc['name']} glares at you: those were their people.")
            state.memory.record(cid, "witnessed", f"{npc['name']} saw {state.player.name} kill members of their own faction.",
                                day=state.clock.day_index, importance=3, related=["player"], location=state.location)
    return msgs


def react_to_kindness(state):
    for cid in squad(state):
        if state.data.npcs[cid]["personality"]["friendliness"] >= 7:
            rel.change(state, cid, friendship=1)


def gather(state, hours, rng):
    """Companions told to gather bring in forage from the current wilderness area each hour."""
    loc = state.data.location(state.location)
    forage = loc.get("resources", {}).get("forage", [])
    msgs = []
    if not forage:
        return msgs
    for cid in squad(state):
        if state.companions[cid]["task"] != "gather":
            continue
        c = char(state, cid)
        for _ in range(int(hours)):
            if rng.random() < 0.5 + c.skills["gathering"] / 200:
                item = rng.choice(forage)
                state.player.inventory.add(item)
                c.train("gathering", 2, state.data.races[c.race])
                msgs.append(f"{state.data.npcs[cid]['name']} gathered {state.data.item(item)['name']}.")
    return msgs
