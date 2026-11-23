"""Encounter composition (deterministic, data-driven: data/encounters.json).

A wild area's spawn point names an anchor enemy; the templates that share that anchor describe the mixed groups
that can appear there (raiders with archers and a hexer, a frost witch with her wolves...). Danger raises the
upper counts. Falls back to the old single-type pack when no template applies.
"""
MAX_GROUP = 9           # hard cap per group, for performance


def templates_for(data, anchor):
    return [t for t in data.encounters if t["anchor"] == anchor]


def compose(data, anchor, danger, rng, biome=None):
    """List of enemy ids for one group."""
    opts = [t for t in templates_for(data, anchor) if danger >= t.get("min_danger", 0)
            and (biome is None or not t.get("biomes") or biome in t["biomes"])]
    if not opts:
        lo, hi = data.enemies[anchor]["pack"]
        return [anchor] * rng.randint(lo, hi)
    total = sum(t["weight"] for t in opts)
    roll = rng.uniform(0, total)
    pick = opts[-1]
    for t in opts:
        roll -= t["weight"]
        if roll <= 0:
            pick = t
            break
    bonus = max(0, (danger - 1) // 2)
    out = []
    for eid, lo, hi in pick["members"]:
        n = rng.randint(lo, hi + (bonus if hi > 0 else 0))
        out += [eid] * n
    if not out:
        out = [anchor]
    return out[:MAX_GROUP]


def extra_groups(danger):
    """Extra groups roaming an area beyond its fixed spawn points (more on dangerous ground)."""
    return max(0, danger - 2)
