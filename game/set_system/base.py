"""Property and base building: a town house (early game) and an outpost at Widow's Crossing (mid game).

Construction, farming, production, worker upkeep, defense, raids and research all run here as plain
deterministic rules. Daily steps are driven from set_system/daily.py.
"""
from . import companions, factions, relationships as rel, timeflow
from .inventory import Inventory

MIN_PER_HOUR = 60


# ====================================================================== shared helpers
def _pay(state, marks, items, src=None):
    """Check and pay marks + items (from the player's pack, then base storage). Returns (ok, reason)."""
    if state.gold < marks:
        return False, f"Needs {marks} marks (you have {state.gold})."
    stores = [state.player.inventory] + ([src] if src is not None else [])
    for item, qty in items.items():
        have = sum(s.count(item) for s in stores)
        if have < qty:
            return False, f"Needs {qty}x {state.data.item(item)['name']} (you have {have})."
    state.gold -= marks
    for item, qty in items.items():
        for s in stores:
            take = min(qty, s.count(item))
            if take:
                s.remove(item, take)
                qty -= take
    return True, ""


def storage(state, holder):
    inv = Inventory.from_dict(holder.setdefault("storage", {}), state.data)
    return inv


def save_storage(holder, inv):
    holder["storage"] = inv.to_dict()


def hist(state, text, importance=3, location=None, etype="settlement"):
    state.memory.record("player", etype, text, day=state.clock.day_index, minute=state.clock.total_minutes % 1440,
                        importance=importance, location=location or state.location)


# ====================================================================== town houses
def house_price(state, town):
    return state.data.base["houses"].get(town)


def buy_house(state, town, building_id):
    price = house_price(state, town)
    if price is None:
        return False, "This house isn't for sale."
    if town in state.property:
        return False, "You already own a house here."
    if state.gold < price:
        return False, f"The house costs {price} marks."
    state.gold -= price
    state.property[town] = {"building": building_id, "bought": state.clock.day_index, "storage": {}}
    state.player.inventory.add("house_deed")
    hist(state, f"{state.player.name} bought a house in {state.data.location(town)['name']}.", 3, town)
    return True, "The house is yours! Bed, storage chest, workbench, scribing table and training dummy inside."


def owns_house(state, town, building_id=None):
    p = state.property.get(town)
    return bool(p) and (building_id is None or p["building"] == building_id)


# ====================================================================== outpost
def outpost_cost(state):
    o = state.data.base["outpost"]
    marks = o["charter_marks_with_crown"] if state.reputation.get("crown", 0) >= 20 else o["charter_marks"]
    return marks, o["charter_items"]


def found_outpost(state, plots):
    from .world_events import holder
    if state.base.get("founded") is not None:
        return False, "You already have an outpost."
    if holder(state, state.data.base["outpost"]["location"]) == "hollow":
        return False, "The Hollow holds Widow's Crossing. Drive them out first."
    marks, items = outpost_cost(state)
    ok, why = _pay(state, marks, items)
    if not ok:
        return False, why
    state.base.update({"founded": state.clock.day_index, "location": state.data.base["outpost"]["location"],
                       "plots": [list(p) for p in plots], "buildings": {}, "storage": {}, "research": {},
                       "raid": None, "log": []})
    state.flags["outpost_founded"] = True
    factions.change_rep(state, "crown", 3, "settled Widow's Crossing")
    hist(state, f"{state.player.name} founded an outpost at Widow's Crossing.", 5, state.base["location"])
    return True, "Your outpost is founded! Build on the marked plots."


def founded(state):
    return state.base.get("founded") is not None


def building_at(state, plot):
    return state.base.get("buildings", {}).get(str(plot))


def buildings_of(state, btype, complete=True):
    return [(k, b) for k, b in state.base.get("buildings", {}).items()
            if b["type"] == btype and (not complete or (b["done"] and not b.get("damaged")))]


def build(state, plot, btype):
    if not founded(state):
        return False, "Found an outpost first."
    if building_at(state, plot):
        return False, "That plot is taken."
    d = state.data.base["buildings"][btype]
    store = storage(state, state.base)
    ok, why = _pay(state, d["marks"], d["items"], store)
    if not ok:
        return False, why
    save_storage(state.base, store)
    hours = d["hours"] / (1 + 0.5 * len(workers(state)))
    state.base["buildings"][str(plot)] = {"type": btype, "done": False,
                                          "ready_at": state.clock.total_minutes + int(hours * MIN_PER_HOUR),
                                          "damaged": False, "crop": None}
    return True, f"Construction of the {d['name']} has begun ({hours:.0f} h)."


def demolish(state, plot):
    b = building_at(state, plot)
    if not b:
        return False, "Nothing there."
    del state.base["buildings"][str(plot)]
    return True, f"The {state.data.base['buildings'][b['type']]['name']} was torn down."


def repair(state, plot):
    b = building_at(state, plot)
    if not b or not b.get("damaged"):
        return False, "Nothing to repair."
    d = state.data.base["buildings"][b["type"]]
    half = {k: max(1, v // 2) for k, v in d["items"].items()}
    store = storage(state, state.base)
    ok, why = _pay(state, d["marks"] // 2, half, store)
    if not ok:
        return False, why
    save_storage(state.base, store)
    b["damaged"] = False
    return True, f"The {d['name']} is repaired."


def update_construction(state):
    msgs = []
    for k, b in state.base.get("buildings", {}).items():
        if not b["done"] and state.clock.total_minutes >= b["ready_at"]:
            b["done"] = True
            name = state.data.base["buildings"][b["type"]]["name"]
            hist(state, f"The outpost's {name} was completed.", 2, state.base["location"])
            msgs.append(f"Outpost: the {name} is finished.")
            if b["type"] == "research":
                state.flags["research_hall"] = True
    return msgs


# ====================================================================== people
def capacity(state):
    return 4 * len(buildings_of(state, "bunkhouse"))


def workers(state):
    return [cid for cid, c in state.companions.items() if c["task"] in ("work", "guard")]


def assign(state, cid, plot=None, guard=False):
    if not founded(state):
        return False, "You have no outpost."
    if cid not in state.companions:
        return False, "Not in your company."
    current = [w for w in workers(state) if w != cid]
    if len(current) >= capacity(state):
        return False, f"Build more bunkhouses (room for {capacity(state)})."
    comp = state.companions[cid]
    comp["task"] = "guard" if guard else "work"
    comp["active"] = False
    comp["post"] = None if guard else (str(plot) if plot is not None else None)
    comp["wait_at"] = None
    return True, f"{state.data.npcs[cid]['name']} will {'guard the outpost' if guard else 'work at the outpost'}."


def worker_at(state, plot):
    return [cid for cid, c in state.companions.items() if c["task"] == "work" and c.get("post") == str(plot)]


def defense(state):
    mult = 1.5 if "fortification" in state.base.get("research", {}) and state.base["research"]["fortification"].get("done") else 1.0
    d = sum(state.data.base["defense"].get(b["type"], 0) for _, b in state.base.get("buildings", {}).items()
            if b["done"] and not b.get("damaged")) * mult
    for cid, c in state.companions.items():
        if c["task"] == "guard":
            ch = c["char"]
            d += (ch.attributes["strength"] + ch.attributes["dexterity"] + ch.attributes["health"]) / 3 + ch.skills["melee"] / 2
    return round(d, 1)


# ====================================================================== farming
def plant(state, plot, seed):
    b = building_at(state, plot)
    if not b or b["type"] != "farm" or not b["done"]:
        return False, "Not a finished farm plot."
    if b.get("crop"):
        return False, "Something is already growing."
    crop = state.data.base["crops"].get(seed)
    if not crop:
        return False, "That isn't a seed."
    if state.player.inventory.has(seed, 2):
        state.player.inventory.remove(seed, 2)
    else:
        inv = storage(state, state.base)
        if not inv.has(seed, 2):
            return False, "You need 2 seeds."
        inv.remove(seed, 2)
        save_storage(state.base, inv)
    b["crop"] = {"seed": seed, "ready_day": state.clock.day_index + crop["days"]}
    state.player.train("gathering", 2, state.race_data)
    return True, f"Planted {state.data.item(seed)['name']}. Ready in {crop['days']} days."


def harvest(state, plot, into_storage=False):
    b = building_at(state, plot)
    if not b or not b.get("crop"):
        return False, "Nothing planted."
    if state.clock.day_index < b["crop"]["ready_day"]:
        return False, f"Not ripe yet (day {b['crop']['ready_day'] + 1})."
    crop = state.data.base["crops"][b["crop"]["seed"]]
    qty = crop["qty"]
    if state.base.get("research", {}).get("agriculture", {}).get("done"):
        qty = int(qty * 1.5)
    if into_storage:
        inv = storage(state, state.base)
        inv.add(crop["yields"], qty)
        save_storage(state.base, inv)
    else:
        state.player.inventory.add(crop["yields"], qty)
        state.player.train("gathering", 4, state.race_data)
    b["crop"] = None
    return True, f"Harvested {qty}x {state.data.item(crop['yields'])['name']}."


# ====================================================================== research
def start_research(state, project):
    if not buildings_of(state, "research") and not state.property:
        return False, "You need a Research Hall (or a house with a scribing desk)."
    d = state.data.base["research"][project]
    res = state.base.setdefault("research", {})
    if project in res:
        return False, "Already researched or underway."
    if d["unlocks"] == "voidglass" and "voidglass" in state.known_recipes:
        return False, "You already know this."
    store = storage(state, state.base) if founded(state) else None
    ok, why = _pay(state, 0, d["items"], store)
    if not ok:
        return False, why
    if store is not None:
        save_storage(state.base, store)
    res[project] = {"done": False, "ready_at": state.clock.total_minutes + d["hours"] * MIN_PER_HOUR}
    return True, f"Research started: {d['name']} ({d['hours']} h)."


def update_research(state):
    msgs = []
    for pid, r in state.base.get("research", {}).items():
        if not r["done"] and state.clock.total_minutes >= r["ready_at"]:
            r["done"] = True
            d = state.data.base["research"][pid]
            if d["unlocks"] == "voidglass" and "voidglass" not in state.known_recipes:
                state.known_recipes.append("voidglass")
            hist(state, f"Research complete: {d['name']}.", 3)
            msgs.append(f"Research complete: {d['name']}!")
    return msgs


# ====================================================================== daily production, upkeep, raids
def daily(state, rng):
    msgs = []
    if state.property:
        msgs += _home_rest(state)
    if not founded(state):
        return msgs + update_research(state)
    msgs += update_construction(state)
    msgs += update_research(state)
    inv = storage(state, state.base)
    log = []
    # upkeep: each worker/guard eats and drinks from base storage (a well covers water)
    has_well = bool(buildings_of(state, "well"))
    for cid in workers(state):
        ch = state.companions[cid]["char"]
        food = next((i for i in companions.FOOD_PREF if inv.has(i)), None)
        if food:
            inv.remove(food)
            ch.food = 100.0
        else:
            rel.change(state, cid, friendship=-3, conflict=2)
            log.append(f"{ch.name} went hungry.")
        if has_well:
            ch.water = 100.0
        elif inv.has("water"):
            inv.remove("water")
            ch.water = 100.0
        if buildings_of(state, "bunkhouse"):
            ch.hp = ch.max_hp
    # production by assigned workers
    for plot, b in list(state.base["buildings"].items()):
        if not b["done"] or b.get("damaged"):
            continue
        ws = worker_at(state, plot)
        if not ws:
            continue
        ch = state.companions[ws[0]]["char"]
        t = b["type"]
        if t == "farm":
            if b.get("crop") and state.clock.day_index >= b["crop"]["ready_day"]:
                save_storage(state.base, inv)
                harvest(state, plot, into_storage=True)
                inv = storage(state, state.base)
                log.append(f"{ch.name} brought in the harvest.")
            if not b.get("crop"):
                seed = next((s for s in state.data.base["crops"] if inv.has(s, 2)), None)
                if seed:
                    inv.remove(seed, 2)
                    b["crop"] = {"seed": seed, "ready_day": state.clock.day_index + state.data.base["crops"][seed]["days"]}
            ch.train("gathering", 3, state.data.races[ch.race])
        elif t == "workshop":
            made = 0
            for ore in ("voidglass", "sunsilver", "greyvein", "rustite"):
                while made < 4 and inv.has(f"{ore}_ore", 2) and ch.skills["crafting"] + 10 >= state.data.recipes[f"smelt_{ore}"]["skill"]:
                    inv.remove(f"{ore}_ore", 2)
                    inv.add(f"{ore}_bar")
                    made += 1
            if made:
                log.append(f"{ch.name} smelted {made} bars.")
            ch.train("crafting", 3, state.data.races[ch.race])
        elif t == "trading":
            earn = 10 + ch.skills["trading"] * 0.6 + max(0, state.reputation.get("caravans", 0)) * 0.3
            if state.base.get("research", {}).get("logistics", {}).get("done"):
                earn *= 1.5
            earn = int(earn)
            state.gold += earn
            log.append(f"{ch.name} earned {earn} marks at the trading post.")
            ch.train("trading", 3, state.data.races[ch.race])
        elif t == "training":
            for skill in ("melee", "blocking", "dodging"):
                ch.train(skill, 4, state.data.races[ch.race])
            ch.train("strength", 2, state.data.races[ch.race])
    save_storage(state.base, inv)
    # raids
    msgs += _maybe_raid(state, rng)
    if log:
        state.base.setdefault("log", []).extend(f"Day {state.clock.day_index + 1}: {l}" for l in log)
        state.base["log"] = state.base["log"][-40:]
    return msgs


def _home_rest(state):
    for cid, c in state.companions.items():
        if c["task"] == "home":
            ch = c["char"]
            ch.hp, ch.food, ch.water, ch.mana = ch.max_hp, 90.0, 90.0, ch.max_mana
    return []


def raid_strength(state, rng):
    from .world_events import world
    return round(20 + world(state)["hollow_strength"] * 0.6 + rng.uniform(0, 20), 1)


def _maybe_raid(state, rng):
    from .world_events import world
    if state.flags.get("hollow_broken") or state.base.get("raid"):
        return []
    if state.clock.day_index - state.base["founded"] < 3:
        return []
    chance = 0.04 + world(state)["hollow_strength"] / 1000
    if rng.random() >= chance:
        return []
    strength = raid_strength(state, rng)
    if state.location == state.base["location"] and state.mode == "local":
        state.base["raid"] = {"strength": strength, "day": state.clock.day_index}
        return ["Alarm! Hollow raiders are attacking the outpost!"]
    return [resolve_raid(state, strength, rng)]


def resolve_raid(state, strength, rng, fought=None):
    """Settle a raid. fought=True/False when the player defended in real time."""
    d = defense(state)
    won = fought if fought is not None else (d + rng.uniform(-10, 10) >= strength)
    loc = state.base["location"]
    if won:
        for cid, c in state.companions.items():
            if c["task"] == "guard":
                c["char"].train("melee", 6, state.data.races[c["char"].race])
                rel.change(state, cid, respect=2)
        factions.change_rep(state, "crown", 2, "held the crossing against the Hollow")
        from .world_events import hollow_kill
        hollow_kill(state, 3)
        hist(state, f"The outpost at Widow's Crossing beat back a Hollow raid (defense {d:.0f} vs {strength:.0f}).", 3, loc,
             "battle")
        msg = "Outpost: a Hollow raid was beaten back!"
    else:
        inv = storage(state, state.base)
        stolen = []
        for item, qty in list(inv.items.items()):
            take = qty * 3 // 10
            if take:
                inv.remove(item, take)
                stolen.append(f"{take} {state.data.item(item)['name']}")
        save_storage(state.base, inv)
        done = [k for k, b in state.base["buildings"].items() if b["done"] and not b.get("damaged")]
        damaged = None
        if done:
            damaged = rng.choice(sorted(done))
            state.base["buildings"][damaged]["damaged"] = True
        hist(state, "Hollow raiders plundered the outpost at Widow's Crossing"
             + (f" and wrecked the {state.data.base['buildings'][state.base['buildings'][damaged]['type']]['name']}" if damaged else "")
             + ".", 3, loc, "battle")
        msg = "Outpost: raiders plundered your outpost! " + (", ".join(stolen[:4]) + " stolen." if stolen else "")
    state.base["raid"] = None
    state.base.setdefault("log", []).append(f"Day {state.clock.day_index + 1}: {msg}")
    return msg


def sleep_free(state, hours):
    return timeflow.advance(state, hours * 60, resting=True)
