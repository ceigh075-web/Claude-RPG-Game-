"""Where named NPCs are right now, based on their schedule and world facts (Set System)."""


def activity(data, npc, hour):
    for start, end, act in data.schedules[npc["schedule"]]:
        if start <= hour < end:
            return act
    return "home"


def is_alive(state, npc_id):
    return state.memory.fact(f"npc:{npc_id}:alive", True)


def present_npcs(state, loc_id, lmap_kind, building=None):
    """NPCs visible in this location/sub-location now. Returns list of (npc_dict, activity)."""
    data = state.data
    hour = state.clock.hour
    town = data.towns.get(loc_id)
    out = []
    for npc in data.npcs.values():
        if npc["home"] != loc_id or not is_alive(state, npc["id"]):
            continue
        if state.flags.get(f"recruited:{npc['id']}"):
            continue
        act = activity(data, npc, hour)
        if act == "home":
            continue
        place = where(npc, act, town)
        if building is None and place == "outdoor":
            out.append((npc, act))
        elif building is not None and place == building["type"]:
            out.append((npc, act))
    return out


def where(npc, act, town):
    """'outdoor' or a building type the NPC occupies for this activity."""
    if town is None:
        return "outdoor"  # wilderness NPCs are always around their camp
    if act == "work" and npc.get("shop") and npc["shop"] in town["buildings"]:
        return npc["shop"]
    if act == "tavern":
        if "inn" in town["buildings"]:
            return "inn"
        if "longhouse" in town["buildings"]:
            return "longhouse"
    return "outdoor"


def shopkeeper(state, loc_id, shop_type):
    """The named NPC running this shop, if any, and whether they're at work now."""
    for npc in state.data.npcs.values():
        if npc["home"] == loc_id and npc.get("shop") == shop_type and is_alive(state, npc["id"]) \
                and not state.flags.get(f"recruited:{npc['id']}"):
            act = activity(state.data, npc, state.clock.hour)
            return npc, act == "work" or (shop_type == "inn" and act == "tavern")
    return None, 7 <= state.clock.hour < 20  # anonymous stallkeeper keeps regular hours
