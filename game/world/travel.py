"""Oregon-Trail-style text travel between adjacent locations, simulated in one-hour steps."""
from . import effects, weather
from .worldmap import TERRAIN_SPEED
from ..set_system import items as items_mod
from ..set_system import skirmish, timeflow

BASE_KMH = 4.5
PACES = {
    # name: (speed mult, needs exertion mult, hp loss per hour, description)
    "steady":    (1.0, 1.0, 0.0, "A sustainable walk. No extra strain."),
    "strenuous": (1.3, 1.35, 0.0, "Faster, but you eat and drink more."),
    "grueling":  (1.6, 1.8, 1.5, "Very fast. Hurts you every hour and burns supplies."),
}
RATIONS = {
    # eat/drink when the need drops below this level
    "meager":   15,
    "normal":   40,
    "generous": 65,
}
FOOD_PREF = ["ration", "cooked_meat", "bread", "fish", "meat", "mushrooms", "berries", "kelp"]
DRINK_PREF = ["water", "ale"]


def start(state, world, dest):
    route = world.route(state.location, dest)
    if route is None:
        return False, "There is no direct route there."
    state.travel = {
        "from": state.location, "to": dest, "km": route["km"], "done": 0.0, "terrain": route["terrain"],
        "hours": 0.0, "pending_event": None, "pending_combat": None, "log": [], "arrived": False,
        "danger": world.route_danger(state.location, dest),
    }
    state.mode = "travel"
    state.sub_location = None
    dest_name = state.data.location(dest)["name"]
    log(state, f"You set out from {state.data.location(state.location)['name']} toward {dest_name} ({route['km']:.0f} km of {route['terrain']}).")
    return True, f"Travelling to {dest_name}."


def log(state, text):
    state.travel["log"].append(f"[{state.clock.time_str()}] {text}")
    if len(state.travel["log"]) > 200:
        del state.travel["log"][:50]


def current_biome(state):
    t = state.travel
    return t["terrain"]


def speed_kmh(state):
    """Current travel speed and a breakdown of factors."""
    t = state.travel
    p = state.player
    factors = []
    pace = PACES[state.settings["pace"]][0]
    terr = TERRAIN_SPEED.get(t["terrain"], 1.0)
    w = weather.info(weather.weather_for(state, current_biome(state)))
    spd = BASE_KMH * pace * terr * w["speed"]
    factors += [("pace", pace), ("terrain", terr), ("weather", w["speed"])]
    attr = 1.0 + (p.attr("speed") - 10) / 100 + p.skills["athletics"] / 200
    spd *= attr
    factors.append(("fitness", round(attr, 2)))
    if state.clock.is_night:
        spd *= 0.75
        factors.append(("night", 0.75))
    if p.hp < p.max_hp * 0.3:
        spd *= 0.7
        factors.append(("wounded", 0.7))
    enc = p.encumbrance()
    if enc > 1.0:
        spd *= 0.6
        factors.append(("overloaded", 0.6))
    return spd, factors


def auto_consume(state):
    """Eat and drink from supplies according to the ration setting. Returns messages."""
    p = state.player
    threshold = RATIONS[state.settings["rations"]]
    msgs = []
    for need, prefs, key in (("food", FOOD_PREF, "food"), ("water", DRINK_PREF, "water")):
        guard = 0
        while getattr(p, need) < threshold and guard < 5:
            guard += 1
            item = next((i for i in prefs if p.inventory.has(i)), None)
            if item is None:
                break
            items_mod.use_item(state, p, item)
            msgs.append(f"Consumed {state.data.item(item)['name']}.")
    return msgs


def step(state, rng_events=True):
    """Advance one hour of travel. Returns a list of messages. May set travel['pending_event']."""
    t = state.travel
    if t is None or t["arrived"] or t["pending_event"] or t.get("pending_combat"):
        return []
    msgs = []
    pace_mult, exertion, hp_loss, _ = PACES[state.settings["pace"]]
    wid = weather.weather_for(state, current_biome(state))
    winfo = weather.info(wid)
    spd, _ = speed_kmh(state)
    step_km = min(spd, t["km"] - t["done"])
    hours = step_km / spd if spd > 0 else 1.0
    hours = max(hours, 0.25)
    msgs += timeflow.advance(state, hours * 60, exertion=exertion, water_mult=winfo["water"])
    t["done"] += step_km
    t["hours"] += hours
    state.stats["km_travelled"] = state.stats.get("km_travelled", 0.0) + step_km
    p = state.player
    race = state.race_data
    p.train("athletics", 1.2 * hours * pace_mult, race)
    p.train("speed", 0.6 * hours * pace_mult, race)
    if hp_loss:
        p.damage(hp_loss * hours)
        p.hp = max(p.hp, 1)
        p.alive = True
    msgs += auto_consume(state)
    if t["done"] >= t["km"] - 1e-6:
        t["arrived"] = True
        msgs.append(f"You arrive at {state.data.location(t['to'])['name']}.")
    elif rng_events:
        ev = roll_event(state, wid)
        if ev:
            t["pending_event"] = ev["id"]
    for m in msgs:
        log(state, m)
    return msgs


def eligible_events(state, wid):
    t = state.travel
    out = []
    for ev in state.data.travel_events:
        if "terrain" in ev and t["terrain"] not in ev["terrain"]:
            continue
        if t["danger"] < ev.get("min_danger", 0) or t["danger"] > ev.get("max_danger", 99):
            continue
        if "weather" in ev and wid not in ev["weather"]:
            continue
        if ev.get("time") == "night" and not state.clock.is_night:
            continue
        out.append(ev)
    return out


def roll_event(state, wid):
    t = state.travel
    chance = 0.07 + 0.025 * t["danger"] + weather.info(wid)["event_bonus"] + (0.03 if state.clock.is_night else 0)
    if state.rng.random() >= chance:
        return None
    pool = eligible_events(state, wid)
    if not pool:
        return None
    weights = [e["weight"] * event_weight_mult(state, e) for e in pool]
    total = sum(weights)
    roll = state.rng.uniform(0, total)
    for e, wgt in zip(pool, weights):
        roll -= wgt
        if roll <= 0:
            return e
    return pool[-1]


def event_by_id(state, eid):
    return next(e for e in state.data.travel_events if e["id"] == eid)


def event_weight_mult(state, ev):
    """World conditions shape road encounters: Hollow strength drives outlaw ambushes; escorts draw attacks;
    wars bring patrols."""
    from ..set_system.world_events import world
    w = world(state)
    m = 1.0
    if ev["id"] in ("hostile_travelers", "hollow_ambush"):
        m *= 0.15 if state.flags.get("hollow_broken") else max(0.3, w["hollow_strength"] / 50.0)
        from ..set_system import jobs
        if jobs.escort_active(state):
            m *= 1.8
    if ev["id"] == "toll_patrol" and any(e["type"] == "war" for e in w["active_events"]):
        m *= 2.0
    if ev["id"] == "merchant_caravan" and any(e["type"] == "caravan_arrival" for e in w["active_events"]):
        m *= 2.0
    return m


def choose(state, choice_index):
    """Resolve the pending event with the given choice. Returns messages."""
    t = state.travel
    ev = event_by_id(state, t["pending_event"])
    choice = ev["choices"][choice_index]
    if not effects.requirement_met(state, choice.get("requires")):
        return ["You can't do that."]
    log(state, f"> {choice['label']}")
    ctx = {"location": t["to"], "reason": ev["id"], "defer_combat": True}
    msgs = effects.apply(state, choice["effects"], ctx)
    t["pending_event"] = None
    if ctx.get("pending_combat"):
        t["pending_combat"] = ctx["pending_combat"]
    if t["done"] >= t["km"] - 1e-6:
        t["arrived"] = True
    for m in msgs:
        log(state, m)
    return msgs


def auto_resolve_combat(state):
    """Resolve a pending travel fight abstractly (the player chose not to fight in real time)."""
    t = state.travel
    pc = t["pending_combat"]
    t["pending_combat"] = None
    res = skirmish.resolve(state, pc["enemy"], pc["count"])
    for m in res["messages"]:
        log(state, m)
    return res


def finish_combat(state, outcome, enemy_id, count, killed):
    """Record the result of a real-time travel fight."""
    t = state.travel
    t["pending_combat"] = None
    name = state.data.enemies[enemy_id]["name"]
    if outcome == "victory":
        log(state, f"You win the fight against {count} {name}(s).")
    elif outcome == "fled":
        log(state, f"You break away from the {name}s and escape down the road.")
        state.memory.record(enemy_id, "escaped", f"{state.player.name} escaped a fight with {name}s on the road.",
                            day=state.clock.day_index, minute=state.clock.total_minutes % 1440, importance=2,
                            related=["player"], location=t["to"])
    else:
        log(state, f"The {name}s beat you ({killed} of them fell first).")


def rest(state, hours):
    msgs = timeflow.advance(state, hours * 60, resting=True)
    msgs += auto_consume(state)
    state.travel["hours"] += hours
    msgs.insert(0, f"You rest for {hours} hours.")
    for m in msgs:
        log(state, m)
    return msgs


def turn_back(state):
    t = state.travel
    t["from"], t["to"] = t["to"], t["from"]
    t["done"] = t["km"] - t["done"]
    msg = f"You turn back toward {state.data.location(t['to'])['name']}."
    log(state, msg)
    return [msg]


def arrive(state):
    """Finish travel and enter the destination location."""
    t = state.travel
    origin = t["from"]
    state.location = t["to"]
    state.mode = "local"
    state.local_pos = None
    state.flags["arrived_from"] = origin
    state.travel = None
    first = state.discover(state.location)
    from ..set_system import jobs
    for m in jobs.on_arrival(state, state.location):
        state.add_log(m)
    from ..set_system import companions as comp_mod
    comp_mod.shared_travel(state, state.location)
    name = state.data.location(state.location)["name"]
    state.add_log(f"Arrived at {name}." + (" (New location discovered!)" if first else ""))
    return first
