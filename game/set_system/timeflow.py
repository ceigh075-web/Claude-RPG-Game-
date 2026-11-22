"""Advancing game time and everything that depends on it (needs, healing)."""
from . import needs


def advance(state, minutes, resting=False, exertion=1.0, water_mult=1.0):
    """Advance the clock by `minutes` and tick needs for the player. Returns messages."""
    if minutes <= 0:
        return []
    day_before = state.clock.day_index
    state.clock.advance(minutes)
    msgs = needs.tick(state.player, minutes / 60.0, state.race_data, exertion=exertion,
                      resting=resting, water_mult=water_mult)
    if state.clock.day_index != day_before:
        state.stats["days"] = state.stats.get("days", 0) + (state.clock.day_index - day_before)
    return msgs


def sleep_until_morning(state, wake_hour=7):
    """Sleep until the next wake_hour. Returns (hours slept, messages)."""
    h = state.clock.hour_float
    hours = (wake_hour - h) % 24
    hours = max(hours, 1.0)
    msgs = advance(state, hours * 60, resting=True)
    return hours, msgs
