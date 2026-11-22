"""Recruitment requirements and recruiting. Every named NPC has a path (main requirements, or an `alt` set)."""
from . import favors, relationships as rel


def _check(state, npc, req):
    out = []
    r = rel.get(state, npc["id"])
    if "gold" in req:
        out.append((f"{req['gold']} marks", state.gold >= req["gold"]))
    for k in ("friendship", "trust", "respect"):
        if k in req:
            out.append((f"{k.title()} {req[k]} (now {r[k]})", r[k] >= req[k]))
    for fac, v in req.get("rep", {}).items():
        cur = state.reputation.get(fac, 0)
        out.append((f"{state.data.factions[fac]['name']} standing {v} (now {cur})", cur >= v))
    for sk, v in req.get("skill", {}).items():
        cur = state.player.skills.get(sk, 0)
        out.append((f"{sk.title()} skill {v} (now {cur:.0f})", cur >= v))
    if "favor" in req:
        st = favors.status(state, req["favor"])
        title = favors.defs(state.data)[req["favor"]]["title"]
        out.append((f"Favor: {title}" + ("" if st else " (ask about it)"), st == "done"))
    return out


def requirements(state, npc):
    """List of (label, met) for the main path, and the alt path if any."""
    main = _check(state, npc, npc["recruit"])
    alt = _check(state, npc, npc["recruit"]["alt"]) if "alt" in npc["recruit"] else None
    return main, alt


def can_recruit(state, npc):
    if state.flags.get(f"recruited:{npc['id']}"):
        return False, "already"
    if not state.memory.fact(f"npc:{npc['id']}:alive", True):
        return False, "dead"
    if state.flags.get(f"rejoin_free:{npc['id']}"):
        return True, "rejoin"
    main, alt = requirements(state, npc)
    if all(m for _, m in main):
        return True, "main"
    if alt and all(m for _, m in alt):
        return True, "alt"
    return False, "unmet"
