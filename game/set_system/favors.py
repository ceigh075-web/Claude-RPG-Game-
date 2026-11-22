"""Personal requests (favors) NPCs ask of the player. Many recruitment paths require one."""
from . import relationships as rel


def defs(data):
    if not hasattr(data, "_favors"):
        import json
        import os
        from ..core.data import DATA_DIR
        with open(os.path.join(DATA_DIR, "favors.json"), encoding="utf-8") as f:
            data._favors = json.load(f)
    return data._favors


def status(state, fid):
    return state.favors.get(fid, {}).get("status")


def favor_of(npc):
    return npc["recruit"].get("favor")


def start(state, npc):
    fid = favor_of(npc)
    if not fid:
        return False, f"{npc['name']} doesn't need anything from you."
    if status(state, fid):
        return False, "You've already agreed to this."
    state.favors[fid] = {"status": "active", "started": state.clock.total_minutes, "npc": npc["id"]}
    d = defs(state.data)[fid]
    state.memory.record(npc["id"], "promise", f"{state.player.name} promised {npc['name']}: {d['desc']}",
                        day=state.clock.day_index, minute=state.clock.total_minutes % 1440, importance=3,
                        related=["player"], location=state.location)
    return True, f"New favor: {d['title']} - {d['desc']}"


def progress(state, fid):
    """(done: bool, detail text)."""
    d = defs(state.data)[fid]
    f = state.favors.get(fid)
    if not f:
        return False, "Not started."
    t = d["type"]
    inv = state.player.inventory
    if t == "deliver":
        parts = [f"{state.data.item(i)['name']} {inv.count(i)}/{q}" for i, q in d["items"].items()]
        return all(inv.has(i, q) for i, q in d["items"].items()), ", ".join(parts)
    if t == "pay":
        return state.gold >= d["gold"], f"{state.gold}/{d['gold']} marks"
    if t == "duel":
        return bool(state.flags.get(f"duel_won:{d['npc']}")), "Win the duel."
    if t == "flag":
        return bool(state.flags.get(d["flag"])), d["desc"]
    if t == "clear":
        ls = state.location_state(d["location"])
        cleared = [g for g in ls.get("groups", {}).values() if g.get("defeated_at", -1) >= f["started"]]
        total = ls.get("group_count") or max(1, len(state.data.location(d["location"]).get("enemies", [])))
        return len(cleared) >= total, f"{len(cleared)}/{total} groups defeated in {state.data.location(d['location'])['name']}"
    return False, ""


def complete(state, npc):
    fid = favor_of(npc)
    if status(state, fid) != "active":
        return False, "No favor in progress."
    done, detail = progress(state, fid)
    if not done:
        return False, f"Not yet: {detail}"
    d = defs(state.data)[fid]
    if d["type"] == "deliver":
        for i, q in d["items"].items():
            state.player.inventory.remove(i, q)
    elif d["type"] == "pay":
        state.gold -= d["gold"]
    state.favors[fid]["status"] = "done"
    if d.get("sets_flag"):
        state.flags[d["sets_flag"]] = True
    rel.change(state, npc["id"], reason="the player kept their word", friendship=15, trust=12, respect=8)
    rel.note(state, "honesty", 2)
    state.memory.record(npc["id"], "promise_kept", f"{state.player.name} did as promised for {npc['name']}: {d['title']}.",
                        day=state.clock.day_index, minute=state.clock.total_minutes % 1440, importance=3,
                        related=["player"], location=state.location)
    return True, f"Favor complete: {d['title']}. {npc['name']} is grateful."


def active(state):
    return [(fid, f) for fid, f in state.favors.items() if f["status"] == "active"]
