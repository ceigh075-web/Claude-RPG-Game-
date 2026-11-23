"""Relationships between the player and NPCs (and between NPCs): friendship, trust, affection, respect,
conflict, compatibility and romance. Only Set System code changes these numbers; the Local AI can at most
report the *tone* of a conversation, which is turned into small bounded deltas here."""

STATS = ("friendship", "trust", "affection", "respect", "conflict")
ROMANCE_STAGES = ("none", "interested", "dating", "partners", "broken")
LIMIT = 100


def get(state, npc_id):
    r = state.relationships.get(npc_id)
    if r is None:
        r = {"friendship": 0, "trust": 0, "affection": 0, "respect": 0, "conflict": 0, "romance": "none",
             "last_talk": -1, "last_gift": -1, "last_tone": -1, "dating_since": None, "met": None}
        state.relationships[npc_id] = r
    return r


def change(state, npc_id, reason=None, **deltas):
    r = get(state, npc_id)
    for k, v in deltas.items():
        r[k] = max(-LIMIT, min(LIMIT, r[k] + v))
    update_romance(state, npc_id)
    big = {k: v for k, v in deltas.items() if abs(v) >= 10}
    if big and reason:
        npc = state.data.npcs.get(npc_id)
        name = npc["name"] if npc else npc_id
        state.memory.record(npc_id, "relationship", f"{name}: {reason}", day=state.clock.day_index,
                            minute=state.clock.total_minutes % 1440, importance=2, related=["player"])
    return r


def bond_label(r):
    """Plain-language standing from friendship and trust (used for notifications and the UI)."""
    v = r["friendship"] + r["trust"]
    for limit, name in ((-80, "Enemy"), (-30, "Hostile"), (-8, "Wary"), (12, "Acquaintance"), (45, "Friendly"),
                        (90, "Friend"), (150, "Close friend")):
        if v < limit:
            return name
    return "Devoted"


# ------------------------------------------------------------------ player profile & compatibility
def profile(state):
    return state.stats.setdefault("profile", {"kindness": 0, "cruelty": 0, "bravery": 0, "greed": 0, "honesty": 0})


def note(state, trait, amount=1):
    p = profile(state)
    p[trait] = p.get(trait, 0) + amount


def compatibility(state, npc):
    """0..100: how well this NPC's values fit the way the player has behaved."""
    t = npc["personality"]
    p = profile(state)

    def n(x):
        return max(-1.0, min(1.0, x / 10.0))
    score = 50.0
    score += (t["friendliness"] + t["loyalty"] - 10) * 2.0 * n(p["kindness"] - p["cruelty"])
    score += (t["aggression"] + t["confidence"] - 10) * 2.0 * n(p["bravery"])
    score += (t["greed"] - 5) * 3.0 * n(p["greed"])
    score += (t["honesty"] - 5) * 3.0 * n(p["honesty"])
    score += (t["friendliness"] - 5) * 2.0
    return max(0.0, min(100.0, score))


def npc_compatibility(a, b):
    """Personality similarity between two NPCs, 0..100."""
    pa, pb = a["personality"], b["personality"]
    diff = sum(abs(pa[k] - pb[k]) for k in pa) / len(pa)
    return max(0.0, min(100.0, 100 - diff * 14))


# ------------------------------------------------------------------ everyday interactions
def talk(state, npc):
    """A conversation: once per day it builds friendship (more with sociable NPCs)."""
    r = get(state, npc["id"])
    if r["met"] is None:
        r["met"] = state.clock.day_index
    if r["last_talk"] == state.clock.day_index:
        return 0
    r["last_talk"] = state.clock.day_index
    gain = 2 + (1 if npc["personality"]["sociability"] >= 7 else 0)
    change(state, npc["id"], friendship=gain)
    return gain


def apply_tone(state, npc, tone):
    """Bounded effect of the conversation's tone (reported by the dialogue layer), once per day."""
    r = get(state, npc["id"])
    if r["last_tone"] == state.clock.day_index or tone not in ("kind", "rude", "flirty", "neutral"):
        return {}
    r["last_tone"] = state.clock.day_index
    compat = compatibility(state, npc)
    if tone == "kind":
        d = {"friendship": 2, "trust": 1}
        note(state, "kindness")
    elif tone == "rude":
        d = {"friendship": -4, "conflict": 5}
        if npc["personality"]["aggression"] >= 7:
            d["respect"] = 2
    elif tone == "flirty":
        d = {"affection": 3} if npc.get("romanceable") and compat >= 45 else {"respect": -2, "conflict": 2}
    else:
        d = {}
    if d:
        change(state, npc["id"], **d)
    return d


def gift(state, npc, item_id):
    """Give an item. Liked tags please, disliked tags offend, once per day. Returns (ok, message, deltas)."""
    r = get(state, npc["id"])
    if not state.player.inventory.has(item_id):
        return False, "You don't have that.", {}
    if r["last_gift"] == state.clock.day_index:
        return False, f"{npc['name']} has already accepted a gift today.", {}
    tags = state.data.item_tags(item_id)
    value = state.data.item(item_id)["value"]
    state.player.inventory.remove(item_id)
    r["last_gift"] = state.clock.day_index
    bonus = min(6, value // 15)
    if tags & set(npc["likes"]):
        d = {"friendship": 8 + bonus, "affection": 4 + bonus // 2, "trust": 2}
        msg = f"{npc['name']} loves it!"
    elif tags & set(npc["dislikes"]):
        d = {"friendship": -6, "conflict": 4}
        msg = f"{npc['name']} takes it with a frown."
    else:
        d = {"friendship": 2 + bonus // 2}
        msg = f"{npc['name']} thanks you."
    if npc["personality"]["greed"] >= 7:
        d["friendship"] = d.get("friendship", 0) + bonus
    change(state, npc["id"], **d)
    note(state, "kindness")
    state.memory.record(npc["id"], "gift", f"{state.player.name} gave {npc['name']} {state.data.item(item_id)['name']}.",
                        day=state.clock.day_index, minute=state.clock.total_minutes % 1440,
                        importance=2 if d.get("friendship", 0) >= 8 or d.get("friendship", 0) < 0 else 1,
                        related=["player"], location=state.location)
    return True, msg, d


# ------------------------------------------------------------------ romance
def update_romance(state, npc_id):
    npc = state.data.npcs.get(npc_id)
    if not npc:
        return
    r = get(state, npc_id)
    stage = r["romance"]
    if stage == "none" and npc.get("romanceable") and r["affection"] >= 30 and compatibility(state, npc) >= 50:
        r["romance"] = "interested"
    elif stage in ("dating", "partners") and (r["affection"] < 15 or r["conflict"] > 60):
        breakup(state, npc_id, initiated_by="npc")


def can_ask_out(state, npc):
    r = get(state, npc["id"])
    return npc.get("romanceable") and r["romance"] == "interested"


def ask_out(state, npc):
    r = get(state, npc["id"])
    if not can_ask_out(state, npc):
        return False, f"{npc['name']} doesn't see you that way."
    if r["affection"] < 50:
        change(state, npc["id"], affection=-5)
        return False, f"{npc['name']} smiles but says they're not ready."
    _jealousy(state, npc["id"])
    r["romance"] = "dating"
    r["dating_since"] = state.clock.day_index
    state.memory.record(npc["id"], "relationship", f"{npc['name']} and {state.player.name} started courting.",
                        day=state.clock.day_index, minute=state.clock.total_minutes % 1440, importance=3,
                        related=["player"])
    return True, f"{npc['name']} says yes!"


def can_commit(state, npc):
    r = get(state, npc["id"])
    return (r["romance"] == "dating" and r["affection"] >= 80 and r["trust"] >= 50
            and state.clock.day_index - (r["dating_since"] or 0) >= 7)


def commit(state, npc):
    if not can_commit(state, npc):
        return False, "It's too soon for that."
    r = get(state, npc["id"])
    r["romance"] = "partners"
    state.memory.record(npc["id"], "relationship", f"{npc['name']} and {state.player.name} became partners.",
                        day=state.clock.day_index, minute=state.clock.total_minutes % 1440, importance=4,
                        related=["player"])
    return True, f"You and {npc['name']} are now partners."


def breakup(state, npc_id, initiated_by="player"):
    r = get(state, npc_id)
    if r["romance"] not in ("dating", "partners"):
        return False, "There's nothing to end."
    r["romance"] = "broken"
    r["affection"] = min(r["affection"], 10)
    r["conflict"] = min(LIMIT, r["conflict"] + 20)
    npc = state.data.npcs[npc_id]
    who = state.player.name if initiated_by == "player" else npc["name"]
    state.memory.record(npc_id, "relationship", f"{who} ended the romance between {npc['name']} and {state.player.name}.",
                        day=state.clock.day_index, minute=state.clock.total_minutes % 1440, importance=3,
                        related=["player"])
    return True, f"You and {npc['name']} are no longer together."


def _jealousy(state, new_id):
    for other, r in state.relationships.items():
        if other != new_id and r["romance"] in ("dating", "partners"):
            change(state, other, affection=-20, conflict=20, trust=-15)
            state.memory.record(other, "relationship", f"{state.data.npcs[other]['name']} learned {state.player.name} "
                                f"is courting someone else.", day=state.clock.day_index, importance=3, related=["player", new_id])


def neglect(state):
    """Daily: partners and close friends you ignore for a week drift away."""
    for npc_id, r in state.relationships.items():
        if r["last_talk"] >= 0 and state.clock.day_index - r["last_talk"] > 7 and r["romance"] in ("dating", "partners"):
            change(state, npc_id, affection=-2)
