"""Violence against non-hostile characters: who fights back, who flees, who calls for help, how companions
react, and what assaults, defeats and killings cost (relationships, reputation, world history).

Everything here is deterministic Set System logic driven by NPC personality, skills and existing
relationship numbers. The Local AI never decides any of it; it only reads the resulting Set AI records and
facts when it writes dialogue.

Persistence rules (the "death and defeat" design):
  * A character brought to 0 HP is *defeated*: knocked down, not dead. Named NPCs then stay home injured
    for INJURY_DAYS and hold a grudge for GRUDGE_DAYS.
  * Only a deliberate finishing blow on a defeated character (the player must have hostile intent on)
    kills them. Death is permanent: fact `npc:<id>:alive` = False, which every system already respects
    (schedules, shops, recruitment, dialogue context).
  * Nobody is protected by default. Explicit exceptions belong in PROTECTED (empty) or an NPC's
    `"protected": true` data flag, and only make the character impossible to *kill* - they can still be
    attacked and defeated.
"""
from . import factions
from . import relationships as rel

PROTECTED = set()          # design-time exceptions (none by default)
INJURY_DAYS = 1            # a defeated named NPC stays home this many days
GRUDGE_DAYS = 3            # ...and refuses to deal with the player for this many
HELP_RADIUS = 130          # how far a cry for help carries (pixels)


def _p(npc, key, default=5):
    return (npc or {}).get("personality", {}).get(key, default)


def _stamp(state):
    return dict(day=state.clock.day_index, minute=state.clock.total_minutes % 1440)


def fighting_skill(npc):
    sk = (npc or {}).get("skills", {})
    return max(sk.get("melee", 0), sk.get("ranged", 0), sk.get("unarmed", 0), sk.get("magic", 0) * 0.8)


def courage(npc):
    """0..~15: how willing someone is to stand and fight."""
    if npc is None:                     # anonymous townsfolk / shopkeepers
        return 4.0
    return _p(npc, "aggression") * 0.6 + _p(npc, "confidence") * 0.6 + fighting_skill(npc) / 8


def reaction(npc, hp_frac, cornered=False):
    """What an attacked character does now: 'fight' | 'flee' | 'call_help' | 'yield'."""
    c = courage(npc)
    if hp_frac < 0.25 and c < 9:
        return "yield" if cornered or _p(npc, "confidence") <= 4 else "flee"
    if c >= 6.5 or (cornered and c >= 4):
        return "fight"
    if _p(npc, "sociability") >= 5:
        return "call_help"
    return "flee"


def bystander_response(state, helper, victim):
    """A nearby character hears a cry for help: 'help' | 'flee' | 'watch'."""
    if helper is None:
        return "flee"
    ties = 0
    if victim is not None:
        if helper.get("faction") and helper.get("faction") == victim.get("faction"):
            ties += 3
        if helper.get("home") == victim.get("home"):
            ties += 2
        ties += rel.npc_compatibility(helper, victim) / 40
    r = rel.get(state, helper["id"])
    regard = (r["friendship"] + r["trust"]) / 40       # liking the player makes them hesitate
    score = courage(helper) + ties - regard
    if score >= 9:
        return "help"
    if _p(helper, "confidence") <= 4 or score < 4:
        return "flee"
    return "watch"


def companion_reaction(state, cid, victim_npc=None, victim_cid=None, killed=False):
    """A squad member watches the player attack someone who wasn't hostile.
    Returns (reaction, message): 'join' | 'stand' | 'object' | 'defend' | 'leave'."""
    npc = state.data.npcs[cid]
    name = npc["name"]
    r = rel.get(state, cid)
    loyal = _p(npc, "loyalty") + (r["friendship"] + r["trust"]) / 25
    moral = _p(npc, "friendliness") + _p(npc, "honesty") - _p(npc, "aggression")
    ties = 0.0
    if victim_cid:
        from .companions import bond
        ties = 4 + bond(state, cid, victim_cid)["value"] / 15
    elif victim_npc:
        if npc.get("faction") and npc.get("faction") == victim_npc.get("faction"):
            ties += 4
        if npc.get("home") == victim_npc.get("home"):
            ties += 3
        ties += rel.npc_compatibility(npc, victim_npc) / 30
    if killed:
        if moral + ties >= loyal + 8:
            return "leave", f"{name}: \"I won't follow a murderer.\""
        if moral >= 10:
            return "object", f"{name} stares at the body in silence."
        return "stand", None
    if moral + ties >= loyal + 6 and courage(npc) >= 6:
        return "defend", f"{name} draws on you: \"Leave them alone!\""
    if _p(npc, "aggression") >= 7 and loyal >= 8 and ties < 3:
        return "join", f"{name} has your back."
    if moral >= 9 or ties >= 3:
        return "object", f"{name}: \"What are you doing?!\""
    return "stand", None


def _victim_label(state, npc_id, fallback):
    return state.data.npcs[npc_id]["name"] if npc_id in state.data.npcs else fallback


def _crime_rep(state, npc, town_faction, base, reason, witnessed=True):
    fac = (npc or {}).get("faction")
    if fac:
        factions.change_rep(state, fac, -base, reason)
    if town_faction and town_faction not in ("none", fac) and witnessed:
        factions.change_rep(state, town_faction, -max(1, base // 2), reason)


def town_faction(state):
    t = state.data.towns.get(state.location)
    return t.get("faction") if t else None


def on_assault(state, npc_id=None, label="a stranger", is_companion=False, witnessed=True):
    """The player first strikes someone who was not hostile. Returns messages."""
    npc = state.data.npcs.get(npc_id) if npc_id else None
    name = npc["name"] if npc else label
    rel.note(state, "cruelty", 2)
    state.stats["assaults"] = state.stats.get("assaults", 0) + 1
    if npc:
        rel.change(state, npc_id, reason=f"{state.player.name} attacked them", friendship=-15, trust=-25, conflict=25)
        state.memory.set_fact(f"npc:{npc_id}:grudge_until", state.clock.day_index + GRUDGE_DAYS, state.clock.day_index)
    _crime_rep(state, npc, town_faction(state), 6 if is_companion else 5, f"attacked {name}", witnessed)
    state.memory.record(npc_id or "world", "assault", f"{state.player.name} attacked {name}"
                        + (", a companion," if is_companion else "") + f" in {state.data.location(state.location)['name']}.",
                        importance=3, related=["player"] + ([npc_id] if npc_id else []), location=state.location,
                        **_stamp(state))
    return [f"You attacked {name}!"]


def on_defeat(state, npc_id=None, label="a stranger", by_player=True):
    """Someone was knocked down (0 HP). Named NPCs recover at home."""
    npc = state.data.npcs.get(npc_id) if npc_id else None
    name = npc["name"] if npc else label
    if npc:
        state.memory.set_fact(f"npc:{npc_id}:injured_until", state.clock.day_index + INJURY_DAYS, state.clock.day_index)
        if by_player:
            rel.change(state, npc_id, reason=f"{state.player.name} beat them down", respect=5, conflict=10, trust=-5)
    state.memory.record(npc_id or "world", "defeated",
                        f"{name} was beaten down" + (f" by {state.player.name}" if by_player else "") + ".",
                        importance=3, related=(["player"] if by_player else []) + ([npc_id] if npc_id else []),
                        location=state.location, **_stamp(state))
    return [f"{name} collapses."]


def can_kill(state, npc_id):
    npc = state.data.npcs.get(npc_id) if npc_id else None
    return not (npc_id in PROTECTED or (npc and npc.get("protected")))


def on_kill(state, npc_id=None, label="a stranger", witnessed=True):
    """A deliberate killing. Permanent for named NPCs. Returns messages."""
    npc = state.data.npcs.get(npc_id) if npc_id else None
    name = npc["name"] if npc else label
    msgs = [f"{name} is dead."]
    rel.note(state, "cruelty", 6)
    state.stats["murders"] = state.stats.get("murders", 0) + 1
    _crime_rep(state, npc, town_faction(state), 15, f"killed {name}", witnessed)
    state.memory.record(npc_id or "world", "death", f"{name} was killed by {state.player.name} in "
                        f"{state.data.location(state.location)['name']}.", importance=5 if npc else 3,
                        related=["player"] + ([npc_id] if npc_id else []), location=state.location, **_stamp(state))
    if not npc:
        return msgs
    state.memory.set_fact(f"npc:{npc_id}:alive", False, state.clock.day_index)
    rel.change(state, npc_id, friendship=-100, trust=-100)
    if npc_id in state.companions:
        state.companions.pop(npc_id, None)
        state.flags[f"recruited:{npc_id}"] = False
        state.flags[f"rejoin_free:{npc_id}"] = False
    if npc.get("leader") and npc.get("faction"):
        fac = npc["faction"]
        state.flags[f"succession:{fac}"] = True
        if fac == "hollow":
            state.flags["hollow_broken"] = True
        state.memory.record("world", "political", f"{name}, leader of the {state.data.factions[fac]['name']}, is dead. "
                            "A successor must be chosen.", importance=5, related=["player", npc_id],
                            location=state.location, **_stamp(state))
        msgs.append(f"The {state.data.factions[fac]['name']} have lost their leader.")
    # people who were close to the victim learn of it
    for other in state.data.npcs.values():
        if other["id"] == npc_id or not state.memory.fact(f"npc:{other['id']}:alive", True):
            continue
        if other["home"] == npc["home"] or (npc.get("faction") and other.get("faction") == npc.get("faction")):
            rel.change(state, other["id"], friendship=-8, trust=-10, conflict=8)
    return msgs


def witness(state, npc_id, victim_name, what="an attack"):
    npc = state.data.npcs.get(npc_id)
    if not npc:
        return
    rel.change(state, npc_id, trust=-6, conflict=4)
    state.memory.record(npc_id, "witnessed", f"{npc['name']} saw {state.player.name} commit {what} on {victim_name}.",
                        importance=2, related=["player"], location=state.location, **_stamp(state))


def companion_reacts(state, cid, reaction_kind, victim_name):
    """Apply the relationship side of a companion's reaction and record it."""
    npc = state.data.npcs[cid]
    if reaction_kind == "join":
        rel.change(state, cid, respect=2)
        return
    if reaction_kind == "stand":
        return
    deltas = {"object": dict(friendship=-6, trust=-8, conflict=6), "defend": dict(friendship=-15, trust=-20, conflict=20),
              "leave": dict(friendship=-25, trust=-35, conflict=25)}[reaction_kind]
    rel.change(state, cid, **deltas)
    state.memory.record(cid, "witnessed", f"{npc['name']} saw {state.player.name} attack {victim_name} and "
                        + {"object": "objected.", "defend": "stepped in to defend them.", "leave": "left the company."}[reaction_kind],
                        importance=3, related=["player"], location=state.location, **_stamp(state))
    if reaction_kind == "leave":
        from . import companions as comp_mod
        comp_mod.dismiss(state, cid)
        state.flags[f"rejoin_free:{cid}"] = False


def after_conflict(state, cid):
    """A companion who fought the player (attacked by, or defending against, them) once things calm down:
    returns ('stay' | 'leave', message)."""
    npc = state.data.npcs[cid]
    r = rel.get(state, cid)
    if cid not in state.companions:
        return "leave", None
    if r["friendship"] + r["trust"] < -20 or r["conflict"] >= 60:
        from . import companions as comp_mod
        comp_mod.dismiss(state, cid)
        state.flags[f"rejoin_free:{cid}"] = False
        state.memory.record(cid, "dismissed", f"{npc['name']} walked away from {state.player.name} after they came to blows.",
                            importance=3, related=["player"], location=state.location, **_stamp(state))
        return "leave", f"{npc['name']} has had enough and leaves your company."
    rel.change(state, cid, conflict=-5)
    return "stay", f"{npc['name']} lowers their weapon, shaken."


def grudge_active(state, npc_id):
    return npc_id is not None and state.memory.fact(f"npc:{npc_id}:grudge_until", -1) >= state.clock.day_index


def injured(state, npc_id):
    return npc_id is not None and state.memory.fact(f"npc:{npc_id}:injured_until", -1) >= state.clock.day_index
