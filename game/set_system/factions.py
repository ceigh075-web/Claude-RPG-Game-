"""Faction reputation (player standing) and inter-faction relations."""

REP_MIN, REP_MAX = -100, 100


def init_reputation(data):
    return {fid: f.get("start_rep", 0) for fid, f in data.factions.items()}


def init_relations(data):
    return dict(data.faction_relations)


def rep(state, faction):
    return state.reputation.get(faction, 0)


def change_rep(state, faction, amount, reason=None):
    if faction not in state.reputation:
        return None
    old = state.reputation[faction]
    new = max(REP_MIN, min(REP_MAX, old + amount))
    state.reputation[faction] = new
    name = state.data.factions[faction]["name"]
    if abs(amount) >= 5 and state.memory is not None:
        state.memory.record(subject=faction, event_type="reputation",
                            description=f"Player's standing with {name} changed by {amount:+d}" + (f": {reason}" if reason else "."),
                            day=state.clock.day_index, minute=state.clock.total_minutes % 1440,
                            importance=2, location=state.location)
    return new


def standing_label(value):
    if value >= 60:
        return "Revered"
    if value >= 30:
        return "Trusted"
    if value >= 10:
        return "Friendly"
    if value > -10:
        return "Neutral"
    if value > -40:
        return "Disliked"
    return "Hostile"


def relation(state, a, b):
    if a == b:
        return 100
    return state.faction_relations.get(f"{a}|{b}", state.faction_relations.get(f"{b}|{a}", 0))


def is_hostile(state, faction):
    if not faction:
        return False
    return rep(state, faction) < state.data.factions[faction].get("hostile_below", -40)


def price_factor(state, faction):
    """Merchants of a faction give better prices to friends (up to -15%) and worse to the disliked (+25%)."""
    if not faction:
        return 1.0
    r = rep(state, faction)
    return 1.0 - 0.0015 * r if r >= 0 else 1.0 - 0.0025 * r
