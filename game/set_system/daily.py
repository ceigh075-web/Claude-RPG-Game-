"""Things that happen once per in-game day. Called by timeflow whenever the date changes.
Each system registers its own daily step here so the order is explicit and deterministic."""
from . import companions, relationships as rel


def new_day(state):
    msgs = []
    rng = state.rng.derive("day", state.clock.day_index)
    msgs += companions.daily(state, rng)
    rel.neglect(state)
    from . import base, world_events
    msgs += world_events.daily(state, rng)
    msgs += base.daily(state, rng)
    from . import crime, morale
    msgs += morale.daily(state)
    msgs += crime.daily(state, rng)
    for hook in EXTRA_HOOKS:
        msgs += hook(state, rng) or []
    return msgs


EXTRA_HOOKS = []  # world events (Phase 7) and base production (Phase 8) append their daily steps
