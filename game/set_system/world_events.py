"""Deterministic world simulation: one roll per in-game day, seeded from the world seed and the date.

Events depend on time (season, festivals), location, faction relations, the player's standing and past
actions, and existing conditions (Hollow strength, wars, territory). Every outcome is applied here by the
Set System (prices, spawns, shop stock, relations, jobs, territory) and recorded in Set AI world history.
"""
from . import factions, jobs, relationships as rel

HOLLOW_START = 50.0
ELITES = {  # biome -> (base enemy, names)
    "mountain": ("stone_brute", ["the Ashmaw", "Old Cragjaw"]), "cave": ("stone_brute", ["the Deepmaw"]),
    "snow": ("ice_wolf", ["Whitefang", "the Frost Widow"]), "swamp": ("bog_lurker", ["the Mire King", "Old Gulper"]),
    "forest": ("wolf", ["Greyhide the Elder", "the Thornwolf"]), "grassland": ("wolf", ["the Meadow Terror"]),
    "desert": ("sand_wurm", ["the Salt Devourer"]), "canyon": ("sand_wurm", ["the Red Burrower"]),
    "moor": ("husk", ["the Fog Walker"]), "ruins": ("husk", ["the Bellringer"]), "volcanic": ("stone_brute", ["the Cinder Colossus"]),
    "crystal": ("crystal_golem", ["the Prism Warden"]), "coast": ("bog_lurker", ["the Wreck Crawler"]),
    "hills": ("wolf", ["the Rust Hound"]),
}
FESTIVALS = {(5, 14): ("brackenford", "Harvest Festival"), (11, 20): ("velmora", "Lastlight Festival")}  # (month, day)
HONORS = {"crown": ("Warden of the Realm", {"marks": 200}), "ironhold": ("Friend of the Forge", {"greyvein_bar": 5}),
          "caravans": ("Road Partner", {"marks": 300}), "ashen": ("Circle Associate", {"mana_crystal": 3}),
          "thornblood": ("Blood-Sworn", {"leather": 4, "thornwood": 4}), "hollow": ("Hollow Friend", {"marks": 150})}


def world(state):
    w = state.world
    w.setdefault("active_events", [])
    w.setdefault("modifiers", [])
    w.setdefault("hollow_strength", HOLLOW_START)
    w.setdefault("territory", {})
    w.setdefault("titles", [])
    w.setdefault("boards", {})
    w.setdefault("next_id", 1)
    return w


def _record(state, text, importance, related=None, location=None, etype="world_event"):
    state.memory.record("world", etype, text, day=state.clock.day_index, minute=state.clock.total_minutes % 1440,
                        importance=importance, related=related or [], location=location)


def start_event(state, etype, headline, days, location=None, data=None, importance=3):
    w = world(state)
    ev = {"id": w["next_id"], "type": etype, "headline": headline, "location": location,
          "until": state.clock.day_index + days, "data": data or {}}
    w["next_id"] += 1
    w["active_events"].append(ev)
    _record(state, headline, importance, location=location)
    return ev


def add_modifier(state, ev, **mod):
    mod.setdefault("until", ev["until"])
    mod["event"] = ev["id"]
    world(state)["modifiers"].append(mod)


def hollow_kill(state, n=1):
    w = world(state)
    w["hollow_strength"] = max(0.0, w["hollow_strength"] - 1.5 * n)


# ====================================================================== daily step
def daily(state, rng):
    w = world(state)
    msgs = []
    day = state.clock.day_index
    # expire
    for ev in [e for e in w["active_events"] if e["until"] <= day]:
        msgs += _expire(state, ev)
    w["active_events"] = [e for e in w["active_events"] if e["until"] > day]
    w["modifiers"] = [m for m in w["modifiers"] if m["until"] > day]
    msgs += jobs.daily(state, rng)
    # the Hollow grows unless broken
    if state.flags.get("hollow_broken"):
        if w["hollow_strength"] > 0:
            w["hollow_strength"] = 0.0
            _record(state, "With Black Ren beaten, the Hollow scatters. The roads grow quieter.", 5, ["black_ren", "player"],
                    etype="faction_change")
            msgs.append("News: the Hollow has broken apart.")
    else:
        w["hollow_strength"] = min(100.0, w["hollow_strength"] + 0.6)
    msgs += _territory(state)
    msgs += _honors(state)
    # festivals (fixed dates)
    key = (state.clock.month_index, state.clock.day_of_month)
    if key in FESTIVALS:
        town, name = FESTIVALS[key]
        ev = start_event(state, "festival", f"The {name} begins in {state.data.location(town)['name']}!", 3, town, importance=2)
        add_modifier(state, ev, kind="price", location=town, type="food", mult=0.7)
        add_modifier(state, ev, kind="price", location=town, type="drink", mult=0.7)
        msgs.append("News: " + ev["headline"])
    # random events
    if rng.random() < 0.45:
        etype = _choose(state, rng)
        if etype:
            ev = START[etype](state, rng)
            if ev:
                msgs.append("News: " + ev["headline"])
    return msgs


def _choose(state, rng):
    w = world(state)
    active = {e["type"] for e in w["active_events"]}
    weights = {"caravan_arrival": 3.0, "shortage": 1.5 + (1.0 if state.clock.season == "winter" else 0.0),
               "settlement_problem": 1.0, "dangerous_creature": 0.0 if "dangerous_creature" in active else 0.9}
    if not state.flags.get("hollow_broken"):
        weights["hollow_raid"] = w["hollow_strength"] / 25.0
    rel_ct = factions.relation(state, "crown", "thornblood")
    if not state.flags.get("peace_crown_thornblood"):
        if rel_ct < -20:
            weights["faction_skirmish"] = 1.0
        if rel_ct <= -60 and "war" not in active:
            weights["war"] = 0.6
    from . import companions
    if companions.squad(state) and "companion_problem" not in active:
        weights["companion_problem"] = 0.7
    total = sum(weights.values())
    roll = rng.uniform(0, total)
    for k, v in weights.items():
        roll -= v
        if roll <= 0:
            return k
    return None


# ====================================================================== event starters
def _town(state, rng, prefer=None):
    towns = list(state.data.towns)
    if prefer:
        towns = [t for t in towns if state.data.towns[t]["specialty"] in prefer] or towns
    return rng.choice(sorted(towns))


def ev_caravan(state, rng):
    town = _town(state, rng, prefer=("trading", "farming", "military", "crafting", "frontier"))
    name = state.data.location(town)["name"]
    ev = start_event(state, "caravan_arrival", f"A Free Caravan League convoy arrives in {name}: shops restocked, prices down.",
                     3, town, importance=2)
    for sid, s in state.location_state(town).get("shops", {}).items():
        sdef = state.data.shops[sid]
        for item, (base, _) in sdef["stock"].items():
            s["stock"][item] = max(s["stock"].get(item, 0), base)
        s["cash"] = max(s["cash"], sdef["cash"])
    add_modifier(state, ev, kind="price", location=town, type="*", mult=0.85)
    return ev


def ev_shortage(state, rng):
    town = _town(state, rng)
    name = state.data.location(town)["name"]
    ev = start_event(state, "shortage", f"Food is running short in {name}. Prices soar.", 6, town)
    add_modifier(state, ev, kind="price", location=town, type="food", mult=1.6)
    add_modifier(state, ev, kind="price", location=town, type="drink", mult=1.3)
    jobs.post(state, town, {"type": "delivery", "title": f"Food for {name}", "item": "ration", "qty": 6, "to": town,
                            "reward": 110, "rep": 6, "days": 6, "desc": f"Bring 6 Travel Rations to {name} before the shortage worsens.",
                            "event": ev["id"]})
    return ev


def ev_hollow_raid(state, rng):
    towns = [t for t in sorted(state.data.towns) if state.data.towns[t]["faction"] in ("crown", "caravans", None, "none")]
    town = rng.choice(towns)
    name = state.data.location(town)["name"]
    ev = start_event(state, "hollow_raid", f"Hollow outlaws raided the outskirts of {name} in the night.", 5, town)
    for s in state.location_state(town).get("shops", {}).values():
        s["cash"] = s["cash"] // 2
    w = world(state)
    w["hollow_strength"] = min(100.0, w["hollow_strength"] + 3)
    jobs.post(state, town, {"type": "bounty", "title": f"Raiders of {name}", "enemy": "bandit_cutthroat", "count": 4,
                            "reward": 140, "rep": 6, "days": 10, "desc": f"Kill 4 Hollow cutthroats anywhere. {name} wants payback.",
                            "event": ev["id"]})
    return ev


def ev_skirmish(state, rng):
    targets = [l for l in ("kingsroad_verge", "meadowrun", "greywood", "widows_crossing")]
    loc = rng.choice(targets)
    ev = start_event(state, "faction_skirmish", f"Thornblood raiders clash with Crown patrols near "
                                                f"{state.data.location(loc)['name']}.", 6, loc)
    key = "crown|thornblood"
    state.faction_relations[key] = max(-100, state.faction_relations.get(key, -40) - 5)
    add_modifier(state, ev, kind="spawn", location=loc, enemy="thornblood_raider", count=3, hostile_override=True)
    return ev


def ev_war(state, rng):
    ev = start_event(state, "war", "War! The Crown of Velmora and the Thornblood Clans take up arms.", 14, None, importance=4)
    for t, town in state.data.towns.items():
        if town["faction"] in ("crown", "thornblood"):
            add_modifier(state, ev, kind="price", location=t, type="weapon", mult=1.25)
            add_modifier(state, ev, kind="price", location=t, type="armor", mult=1.25)
            add_modifier(state, ev, kind="price", location=t, type="food", mult=1.2)
    for loc in ("thornwild", "kingsroad_verge", "widows_crossing"):
        add_modifier(state, ev, kind="spawn", location=loc, enemy="thornblood_raider", count=3, hostile_override=True)
    return ev


def ev_creature(state, rng):
    loc = rng.choice(sorted(state.data.wilderness))
    biome = state.data.location(loc)["biome"]
    base, names = ELITES.get(biome, ("wolf", ["the Beast"]))
    name = rng.choice(names)
    ev = start_event(state, "dangerous_creature", f"A monster called {name} stalks {state.data.location(loc)['name']}.",
                     12, loc, {"name": name, "enemy": base})
    add_modifier(state, ev, kind="spawn", location=loc, enemy=base, count=1, elite=name)
    jobs.post(state, rng.choice(sorted(state.data.towns)), {"type": "hunt", "title": f"Hunt {name}", "event": ev["id"],
              "location": loc, "reward": 300, "rep": 8, "days": 12,
              "desc": f"Slay {name} in {state.data.location(loc)['name']}."})
    return ev


def ev_settlement(state, rng):
    town = _town(state, rng)
    name = state.data.location(town)["name"]
    ev = start_event(state, "settlement_problem", f"A fever spreads through {name}. The healers need salves.", 8, town)
    add_modifier(state, ev, kind="price", location=town, type="medicine", mult=1.5)
    jobs.post(state, town, {"type": "delivery", "title": f"Medicine for {name}", "item": "herbal_salve", "qty": 3, "to": town,
                            "reward": 80, "rep": 10, "days": 8, "desc": f"Bring 3 Herbal Salves to {name}.", "event": ev["id"]})
    return ev


def ev_companion(state, rng):
    from . import companions
    cid = rng.choice(sorted(companions.squad(state)))
    npc = state.data.npcs[cid]
    amount = 60 + rng.randint(0, 4) * 20
    ev = start_event(state, "companion_problem", f"{npc['name']} owes {amount} marks to a creditor back home and is worried sick.",
                     7, npc["home"], {"npc": cid}, importance=2)
    jobs.post(state, npc["home"], {"type": "pay", "title": f"Help {npc['name']}", "gold": amount, "npc": cid, "reward": 0,
                                   "rep": 0, "days": 7, "desc": f"Cover {npc['name']}'s {amount}-mark debt (turn in at any board).",
                                   "event": ev["id"]}, accept=True)
    return ev


START = {"caravan_arrival": ev_caravan, "shortage": ev_shortage, "hollow_raid": ev_hollow_raid,
         "faction_skirmish": ev_skirmish, "war": ev_war, "dangerous_creature": ev_creature,
         "settlement_problem": ev_settlement, "companion_problem": ev_companion}


def _expire(state, ev):
    msgs = []
    if ev["type"] == "war":
        _record(state, "The war between the Crown and the Clans burns itself out, for now.", 4)
        msgs.append("News: the war has ended.")
    if ev["type"] == "settlement_problem" and not ev["data"].get("resolved"):
        _record(state, f"The fever in {state.data.location(ev['location'])['name']} took lives before it passed.", 3,
                location=ev["location"])
    if ev["type"] == "companion_problem" and not ev["data"].get("resolved"):
        cid = ev["data"]["npc"]
        rel.change(state, cid, reason="the player ignored their troubles", friendship=-10, trust=-8)
    return msgs


def resolve_event(state, event_id):
    for ev in world(state)["active_events"]:
        if ev["id"] == event_id:
            ev["data"]["resolved"] = True
            if ev["type"] in ("dangerous_creature",):
                ev["until"] = state.clock.day_index + 1
            return ev
    return None


def elite_slain(state, event_id):
    ev = resolve_event(state, event_id)
    if ev:
        _record(state, f"{state.player.name} slew {ev['data']['name']}.", 4, ["player"], ev["location"], "accomplishment")
        world(state)["modifiers"] = [m for m in world(state)["modifiers"] if m.get("event") != event_id]


# ====================================================================== territory & honors
def _territory(state):
    w = world(state)
    terr = w["territory"]
    msgs = []
    holder = terr.get("widows_crossing", "crown")
    if holder != "hollow" and w["hollow_strength"] >= 75 and not state.flags.get("hollow_broken"):
        terr["widows_crossing"] = "hollow"
        _record(state, "The Hollow seized Widow's Crossing and fortified the crossroads.", 4, location="widows_crossing",
                etype="settlement")
        msgs.append("News: the Hollow has taken Widow's Crossing!")
    elif holder == "hollow" and (w["hollow_strength"] < 40 or state.flags.get("hollow_broken")):
        terr["widows_crossing"] = "crown"
        _record(state, "The Hollow lost its grip on Widow's Crossing.", 4, location="widows_crossing", etype="settlement")
        msgs.append("News: Widow's Crossing is free of the Hollow.")
    return msgs


def holder(state, loc):
    return world(state)["territory"].get(loc)


def _honors(state):
    w = world(state)
    msgs = []
    for fac, (title, gifts) in HONORS.items():
        if title not in w["titles"] and state.reputation.get(fac, 0) >= 60:
            w["titles"].append(title)
            for item, n in gifts.items():
                if item == "marks":
                    state.gold += n
                else:
                    state.player.inventory.add(item, n)
            _record(state, f"The {state.data.factions[fac]['name']} named {state.player.name} '{title}'.", 4, ["player"],
                    etype="accomplishment")
            msgs.append(f"Honor: the {state.data.factions[fac]['name']} names you '{title}'! A gift awaits in your pack.")
    return msgs


def spawn_modifiers(state, loc):
    return [m for m in world(state)["modifiers"] if m["kind"] == "spawn" and m["location"] == loc]
