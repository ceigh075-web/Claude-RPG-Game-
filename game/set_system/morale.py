"""Morale, surrender, prisoners and retainers (deterministic Set System rules).

Combat side: human enemies carry morale (data: enemies.json "morale"). It drops when they're badly hurt, when
allies fall or their leader goes down, and rises when they outnumber their foes. When it breaks they flee, or
- if their kind ever yields ("surrenders": true) and they're cornered or hurt - they surrender.

After a surrender the player decides: take them prisoner (needs a house or an outpost to hold them), recruit
them if they're willing, demand their purse, or let them go. Prisoners have loyalty and resentment that change
daily with how they're treated; they remember it, may come to serve you, or may escape. Retainers (recruited
prisoners) work for your settlement. Nothing here is graphic: it's about choices and their consequences.

The Local AI never decides any of this; it may only read the resulting memories.
"""
from . import factions
from . import relationships as rel

BREAK_POINT = 25          # morale at or below this breaks the will to fight
RECRUIT_LOYALTY = 60      # a prisoner this loyal agrees to serve
ESCAPE_RESENTMENT = 75


def _stamp(state):
    return dict(day=state.clock.day_index, minute=state.clock.total_minutes % 1440)


# ------------------------------------------------------------------ combat morale
def initial(enemy):
    """Starting morale; 0 means mindless (beasts, the dead): never breaks."""
    return float(enemy.get("morale", 0))


def update(morale, hp_frac, allies_down=0, leader_down=False, outnumber=0.0):
    """New morale value after this moment's events (outnumber: our numbers / theirs)."""
    if morale <= 0:
        return 0.0
    m = morale
    if hp_frac < 0.4:
        m -= (0.4 - hp_frac) * 60
    m -= 15 * allies_down
    if leader_down:
        m -= 25
    if outnumber >= 2:
        m += 5
    elif outnumber < 0.6:
        m -= 5
    return max(1.0, min(100.0, m))


def decide(enemy, morale, hp_frac, cornered=False):
    """'fight' | 'flee' | 'surrender'."""
    if morale <= 0 or morale > BREAK_POINT:
        return "fight"
    if enemy.get("surrenders") and (cornered or hp_frac < 0.35):
        return "surrender"
    return "flee"


# ------------------------------------------------------------------ after a surrender
def can_hold_prisoners(state):
    from . import base
    return base.founded(state) or bool(getattr(state, "property", {}))


def willingness(state, enemy_id):
    """How willing a surrendered foe is to join you outright (0-100)."""
    e = state.data.enemies[enemy_id]
    w = 30 + 100 - e.get("morale", 50)
    fac = e.get("faction")
    if fac:
        w -= 20 if factions.rep(state, fac) < -20 else 0
        w += 10 if state.flags.get("hollow_broken") and fac == "hollow" else 0
    w += rel.profile(state).get("kindness", 0) * 2 - rel.profile(state).get("cruelty", 0)
    return max(0, min(100, int(w)))


def options(state, enemy_id):
    """[(label, key, enabled, why)] for the choice shown when you approach someone who surrendered."""
    hold = can_hold_prisoners(state)
    will = willingness(state, enemy_id)
    return [
        ("Take them prisoner", "prisoner", hold, "" if hold else "needs a house or an outpost to hold them"),
        ("Ask them to join your outpost" if will >= 70 else "Ask them to join you", "recruit", will >= 70 and hold,
         "" if will >= 70 and hold else ("not willing yet" if will < 70 else "needs a house or outpost")),
        ("Demand their purse", "rob", True, ""),
        ("Let them go", "release", True, ""),
    ]


def resolve(state, enemy_id, choice, purse=0):
    """Apply the player's choice. Returns a message."""
    data = state.data
    e = data.enemies[enemy_id]
    name = e["name"]
    fac = e.get("faction")
    if choice == "release":
        rel.note(state, "kindness", 2)
        if fac:
            factions.change_rep(state, fac, 2, f"spared a {name}")
        state.memory.record("player", "kindness", f"{state.player.name} let a defeated {name} go free.", importance=2,
                            location=state.location, **_stamp(state))
        return f"The {name} backs away, then runs. Word of your mercy will spread."
    if choice == "rob":
        state.gold += purse
        rel.note(state, "greed", 1)
        if fac:
            factions.change_rep(state, fac, -1, f"robbed a {name}")
        return f"The {name} hands over {purse} marks and flees." if purse else f"The {name} has nothing. They flee."
    if choice == "prisoner":
        if not can_hold_prisoners(state):
            return "You have nowhere to hold a prisoner (buy a house or found an outpost)."
        p = {"id": f"pr{state.stats.get('prisoners_taken', 0) + 1}", "enemy": enemy_id, "name": name,
             "loyalty": 10.0, "resentment": 20.0, "kind": True, "since": state.clock.day_index, "talked": -1}
        state.stats["prisoners_taken"] = state.stats.get("prisoners_taken", 0) + 1
        prisoners(state).append(p)
        state.memory.record("player", "significant", f"{state.player.name} took a {name} prisoner.", importance=2,
                            location=state.location, **_stamp(state))
        return f"The {name} is taken to your holdings as a prisoner."
    if choice == "recruit":
        if willingness(state, enemy_id) < 70 or not can_hold_prisoners(state):
            return f"The {name} refuses."
        retainers(state).append({"name": name, "enemy": enemy_id, "since": state.clock.day_index, "loyalty": 55.0})
        state.memory.record("player", "recruited", f"A former {name} swore to serve {state.player.name}.",
                            importance=2, location=state.location, **_stamp(state))
        return f"The {name} lays down their weapon and swears to serve your outpost."
    return "Nothing happens."


# ------------------------------------------------------------------ prisoners and retainers
def prisoners(state):
    return state.stats.setdefault("prisoners", [])


def retainers(state):
    return state.stats.setdefault("retainers", [])


def set_treatment(state, pid, kind):
    for p in prisoners(state):
        if p["id"] == pid:
            p["kind"] = bool(kind)
            return f"{p['name']} will be treated {'kindly (costs a ration a day)' if kind else 'plainly'}."
    return "No such prisoner."


def talk(state, pid):
    for p in prisoners(state):
        if p["id"] == pid:
            if p["talked"] == state.clock.day_index:
                return f"You've already spoken with the {p['name']} today."
            p["talked"] = state.clock.day_index
            p["loyalty"] = min(100.0, p["loyalty"] + 6)
            p["resentment"] = max(0.0, p["resentment"] - 4)
            return f"You talk with the {p['name']} for a while. They seem a little less hostile."
    return "No such prisoner."


def release_prisoner(state, pid):
    for p in list(prisoners(state)):
        if p["id"] == pid:
            prisoners(state).remove(p)
            fac = state.data.enemies[p["enemy"]].get("faction")
            if fac:
                factions.change_rep(state, fac, 3, f"released a captive {p['name']}")
            rel.note(state, "kindness", 2)
            state.memory.record("player", "kindness", f"{state.player.name} released a captive {p['name']}.",
                                importance=2, **_stamp(state))
            return f"You release the {p['name']}."
    return "No such prisoner."


def recruit_prisoner(state, pid):
    for p in list(prisoners(state)):
        if p["id"] == pid:
            if p["loyalty"] < RECRUIT_LOYALTY:
                return f"The {p['name']} isn't ready to serve you (loyalty {p['loyalty']:.0f}/{RECRUIT_LOYALTY})."
            prisoners(state).remove(p)
            retainers(state).append({"name": p["name"], "enemy": p["enemy"], "since": state.clock.day_index,
                                     "loyalty": p["loyalty"]})
            state.memory.record("player", "recruited", f"A captive {p['name']} chose to serve {state.player.name}.",
                                importance=2, **_stamp(state))
            return f"The {p['name']} joins your outpost as a retainer."
    return "No such prisoner."


def daily(state):
    """Once a day: prisoners' feelings change with their treatment; some escape; retainers earn their keep."""
    msgs = []
    inv = state.player.inventory
    for p in list(prisoners(state)):
        fed = False
        if p["kind"] and inv.has("ration"):
            inv.remove("ration")
            fed = True
        if fed:
            p["loyalty"] = min(100.0, p["loyalty"] + 5)
            p["resentment"] = max(0.0, p["resentment"] - 5)
        else:
            p["loyalty"] = min(100.0, p["loyalty"] + 1)
            p["resentment"] = min(100.0, p["resentment"] + (2 if p["kind"] else 6))
        if p["resentment"] >= ESCAPE_RESENTMENT:
            prisoners(state).remove(p)
            msgs.append(f"A captive {p['name']} escaped in the night.")
            state.memory.record("player", "significant", f"A captive {p['name']} escaped from {state.player.name}.",
                                importance=2, **_stamp(state))
    for r in retainers(state):
        r["loyalty"] = min(100.0, r["loyalty"] + 1)
    pay = 3 * len(retainers(state))
    if pay:
        state.gold += pay
        msgs.append(f"Your retainers brought in {pay} marks.")
    return msgs
