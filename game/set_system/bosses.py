"""Boss rules (Set System): who guards which lair, their numbers, whether they've fallen, and the rewards.
The fight itself runs in gameplay/boss.py; nothing here depends on presentation or the Local AI."""
from ..core.rng import stable_rng
from . import factions


def defeated(state, boss_id):
    return f"boss_dead:{boss_id}" in state.flags          # value: the day it fell (day 0 counts)


def at(state, loc_id):
    """The undefeated boss guarding a location, or None."""
    for bid, b in state.data.bosses.items():
        if b["location"] == loc_id and not defeated(state, bid):
            return bid
    return None


def enemy_def(data, boss_id):
    """A full enemy definition for the boss, built from its base enemy."""
    b = data.bosses[boss_id]
    base = data.enemies[b["base"]]
    return dict(base, name=b["name"], hp=b["hp"], damage=b["damage"], armor=b["armor"], speed=b["speed"],
                flee_below=0, morale=999, surrenders=False, xp=b["reward"]["xp"], boss=boss_id,
                loot={"marks": list(b["reward"]["marks"])}, aggro=400, pack=[1, 1], boss_color=b.get("color"))


def on_defeat(state, boss_id):
    """Mark the boss as fallen, apply reputation, record it. Returns (messages, reward items for the body)."""
    b = state.data.bosses[boss_id]
    state.flags[f"boss_dead:{boss_id}"] = state.clock.day_index
    msgs = [f"{b['name']} is defeated!"]
    for fac, delta in b.get("reputation", {}).items():
        factions.change_rep(state, fac, delta, f"defeated {b['name']}")
    state.stats["bosses"] = state.stats.get("bosses", 0) + 1
    state.memory.record("player", "significant", f"{state.player.name} defeated {b['name']}.", importance=5,
                        day=state.clock.day_index, minute=state.clock.total_minutes % 1440, location=state.location)
    items = [{"item": it, "qty": n} for it, n in b["reward"]["items"]]
    return msgs, items


def lairs(state):
    """[(location, boss id, defeated)] for the world map."""
    return [(b["location"], bid, defeated(state, bid)) for bid, b in state.data.bosses.items()]


def spawn_point(data, boss_id, m):
    """Where the boss waits: a fixed, deterministic spot away from the map's entrance."""
    rng = stable_rng("boss", boss_id)
    ex, ey = m.entry
    best, bd = None, -1
    for _ in range(40):
        x, y = rng.randint(8, m.w - 9), rng.randint(6, m.h - 7)
        if m.solid(x, y):
            continue
        d = (x - ex) ** 2 + (y - ey) ** 2
        if d > bd:
            best, bd = (x, y), d
    return best or (m.w // 2, m.h // 2)
