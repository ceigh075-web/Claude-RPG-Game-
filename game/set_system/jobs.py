"""Job boards: bounties, deliveries, supply runs, caravan escorts, monster hunts, and companion troubles.
Boards refresh weekly per town; accepted jobs have deadlines; failing one costs standing (a broken promise)."""
from . import factions, relationships as rel

MAX_ACTIVE = 5
SUPPLY_ITEMS = {"food": "ration", "ore": "rustite_ore", "bar": "rustite_bar", "medicine": "bandage",
                "material": "leather", "drink": "water", "valuable": "trinket", "magic": "mana_crystal", "ammo": "arrow",
                "weapon": "dagger_rustite", "armor": "leather_cap", "tool": "pickaxe"}


def kills(state, enemy):
    return state.stats.get("kills_by", {}).get(enemy, 0)


def note_kill(state, enemy):
    kb = state.stats.setdefault("kills_by", {})
    kb[enemy] = kb.get(enemy, 0) + 1


def board(state, town):
    from .world_events import world
    w = world(state)
    b = w["boards"].get(town)
    week = state.clock.week_index
    if b is None or b["week"] != week:
        keep = [j for j in (b or {}).get("jobs", []) if j.get("event") and j["status"] == "open"]
        b = {"week": week, "jobs": keep + generate(state, town, state.rng.derive("jobs", town, week))}
        w["boards"][town] = b
    return b


def _new_id(state):
    from .world_events import world
    w = world(state)
    w["next_id"] += 1
    return w["next_id"]


def post(state, town, spec, accept=False):
    """Add a job to a town's board (used by world events)."""
    job = dict(spec, id=_new_id(state), town=town, status="open")
    job["deadline"] = state.clock.day_index + spec.get("days", 7)
    board(state, town)["jobs"].append(job)
    if accept:
        job["status"] = "active"
        state.jobs.append(job)
    return job


def generate(state, town, rng):
    data = state.data
    from ..world.worldmap import WorldMap
    wm = WorldMap(data)
    out = []
    fac = data.towns[town]["faction"]
    near_wild = [n for n in wm.neighbors(town) if n in data.wilderness]
    # bounty on something dangerous nearby
    if near_wild:
        loc = rng.choice(near_wild)
        enemy = rng.choice(data.location(loc)["enemies"])
        e = data.enemies[enemy]
        n = rng.randint(3, 6)
        out.append({"type": "bounty", "title": f"Bounty: {e['name']}s", "enemy": enemy, "count": n,
                    "start": kills(state, enemy), "reward": int(e["xp"] * n * 1.6 + 20), "rep": 4, "days": 10,
                    "desc": f"Kill {n} {e['name']}s (seen around {data.location(loc)['name']})."})
    # supply run for whatever this town lacks
    demand = sorted(data.economy.get(town, {}).items(), key=lambda kv: -kv[1])
    for t, mult in demand:
        if mult > 1.1 and t in SUPPLY_ITEMS:
            item = SUPPLY_ITEMS[t]
            qty = max(1, int(60 / max(1, data.item(item)["value"])))
            qty = min(qty, 10)
            out.append({"type": "delivery", "title": f"Supply run: {data.item(item)['name']}", "item": item, "qty": qty,
                        "to": town, "reward": int(data.item(item)["value"] * qty * mult * 1.5 + 10), "rep": 3, "days": 9,
                        "desc": f"Bring {qty}x {data.item(item)['name']} to {data.location(town)['name']}."})
            break
    # delivery or escort to another town
    others = [t for t in sorted(data.towns) if t != town]
    dest = rng.choice(others)
    path, km = wm.shortest_path(town, dest)
    if data.towns[town]["specialty"] in ("mercenary", "trading") or rng.random() < 0.4:
        out.append({"type": "escort", "title": f"Escort to {data.location(dest)['name']}", "to": dest,
                    "reward": int(40 + km * 2.2), "rep": 5, "days": int(km / 30) + 4,
                    "desc": f"Guard a caravan from {data.location(town)['name']} to {data.location(dest)['name']}. "
                            "Expect trouble on the road."})
    else:
        item = rng.choice(["salt", "grain", "leather", "fish", "hide"])
        out.append({"type": "delivery", "title": f"Deliver {data.item(item)['name']}", "item": item, "qty": 4, "to": dest,
                    "reward": int(30 + km * 1.2), "rep": 3, "days": int(km / 25) + 5,
                    "desc": f"Take 4x {data.item(item)['name']} to {data.location(dest)['name']}."})
    jobs = []
    for spec in out:
        j = dict(spec, id=_new_id(state), town=town, status="open", faction=fac if fac in data.factions else None)
        j["deadline_days"] = spec["days"]
        jobs.append(j)
    return jobs


def accept(state, town, job_id):
    b = board(state, town)
    job = next((j for j in b["jobs"] if j["id"] == job_id), None)
    if not job or job["status"] != "open":
        return False, "That job is gone."
    if len([j for j in state.jobs if j["status"] == "active"]) >= MAX_ACTIVE:
        return False, f"You can hold at most {MAX_ACTIVE} jobs."
    job["status"] = "active"
    job["deadline"] = state.clock.day_index + job.get("deadline_days", job.get("days", 7))
    if job["type"] == "bounty":
        job["start"] = kills(state, job["enemy"])
    if job["type"] == "escort":
        job["origin"] = town
    state.jobs.append(job)
    return True, f"Accepted: {job['title']}. Due by day {job['deadline'] + 1}."


def progress(state, job):
    t = job["type"]
    if t == "bounty":
        n = kills(state, job["enemy"]) - job.get("start", 0)
        return n >= job["count"], f"{min(n, job['count'])}/{job['count']} killed"
    if t == "delivery":
        have = state.player.inventory.count(job["item"])
        return have >= job["qty"] and state.location == job["to"], \
            f"{have}/{job['qty']} carried, deliver to {state.data.location(job['to'])['name']}"
    if t == "escort":
        return job.get("arrived", False), f"reach {state.data.location(job['to'])['name']}"
    if t == "hunt":
        return job.get("slain", False), "slay the beast"
    if t == "pay":
        return state.gold >= job["gold"], f"{state.gold}/{job['gold']} marks"
    return False, ""


def turn_in(state, job_id):
    job = next((j for j in state.jobs if j["id"] == job_id and j["status"] == "active"), None)
    if not job:
        return False, "No such job."
    done, detail = progress(state, job)
    if not done:
        return False, f"Not done: {detail}"
    if job["type"] == "delivery" and state.location != job["to"]:
        return False, "Deliver it at the destination's board."
    if job["type"] == "delivery":
        state.player.inventory.remove(job["item"], job["qty"])
    if job["type"] == "pay":
        state.gold -= job["gold"]
        rel.change(state, job["npc"], reason="the player paid off their debt", friendship=15, trust=10)
    job["status"] = "done"
    state.gold += job["reward"]
    if job.get("faction"):
        factions.change_rep(state, job["faction"], job["rep"], f"completed '{job['title']}'")
    elif job["rep"] and state.data.towns.get(job["town"], {}).get("faction") in state.data.factions:
        factions.change_rep(state, state.data.towns[job["town"]]["faction"], job["rep"], f"completed '{job['title']}'")
    if job["type"] in ("bounty", "hunt", "escort"):
        rel.note(state, "bravery")
        state.player.train("trading", 2, state.race_data)
    rel.note(state, "honesty")
    if job.get("event"):
        from . import world_events
        world_events.resolve_event(state, job["event"])
    state.stats["jobs_done"] = state.stats.get("jobs_done", 0) + 1
    state.memory.record("player", "accomplishment", f"{state.player.name} completed the job '{job['title']}'.",
                        day=state.clock.day_index, minute=state.clock.total_minutes % 1440,
                        importance=2 if job["reward"] < 200 else 3, location=state.location)
    return True, f"Job done: {job['title']} (+{job['reward']} marks)."


def on_arrival(state, location):
    msgs = []
    for j in state.jobs:
        if j["status"] == "active" and j["type"] == "escort" and j["to"] == location:
            j["arrived"] = True
            ok, msg = turn_in(state, j["id"])
            msgs.append(msg)
    return msgs


def on_elite_killed(state, event_id):
    for j in state.jobs:
        if j["status"] == "active" and j["type"] == "hunt" and j.get("event") == event_id:
            j["slain"] = True


def escort_active(state):
    return any(j["status"] == "active" and j["type"] == "escort" for j in state.jobs)


def daily(state, rng):
    msgs = []
    for j in state.jobs:
        if j["status"] == "active" and state.clock.day_index > j["deadline"]:
            j["status"] = "failed"
            fac = j.get("faction") or state.data.towns.get(j["town"], {}).get("faction")
            if fac in state.data.factions:
                factions.change_rep(state, fac, -3, f"failed '{j['title']}'")
            rel.note(state, "honesty", -1)
            state.memory.record("player", "promise_broken", f"{state.player.name} failed the job '{j['title']}'.",
                                day=state.clock.day_index, importance=2, location=j["town"])
            msgs.append(f"Job failed: {j['title']}.")
    state.jobs = [j for j in state.jobs if j["status"] == "active" or state.clock.day_index - j.get("deadline", 0) < 7]
    return msgs
