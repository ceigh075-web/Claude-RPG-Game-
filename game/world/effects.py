"""Executes data-driven effect lists (travel events, interactions) through the Set System.

This is the only path by which event *data* changes game state, so every outcome is validated here.
"""
from ..set_system import factions, skirmish, timeflow

WATER_CARRY_LIMIT = 8


def roll_loot(state, table_id, mult=1.0):
    msgs = []
    for item, lo, hi, chance in state.data.loot_tables[table_id]:
        if state.rng.random() < min(1.0, chance * mult):
            n = state.rng.randint(lo, hi)
            if item == "marks":
                state.gold += n
                msgs.append(f"Found {n} marks.")
            else:
                state.player.inventory.add(item, n)
                msgs.append(f"Found {n}x {state.data.item(item)['name']}.")
    if not msgs:
        msgs.append("You find nothing of use.")
    return msgs


def refill_water(state):
    inv = state.player.inventory
    have = inv.count("water")
    add = max(0, WATER_CARRY_LIMIT - have)
    if add:
        inv.add("water", add)
    return add


def requirement_met(state, req):
    if not req:
        return True
    if "gold" in req and state.gold < req["gold"]:
        return False
    if "item" in req:
        item, qty = req["item"]
        if not state.player.inventory.has(item, qty):
            return False
    return True


def apply(state, effects, ctx=None):
    """Apply a list of effect dicts. Returns a list of message strings. ctx may carry travel info."""
    ctx = ctx if ctx is not None else {}
    msgs = []
    p = state.player
    for eff in effects:
        op = eff["op"]
        if op == "text":
            msgs.append(eff["text"])
        elif op == "item":
            q = eff["qty"]
            if q > 0:
                p.inventory.add(eff["id"], q)
                msgs.append(f"+{q} {state.data.item(eff['id'])['name']}")
            else:
                q = min(-q, p.inventory.count(eff["id"]))
                if q:
                    p.inventory.remove(eff["id"], q)
                    msgs.append(f"-{q} {state.data.item(eff['id'])['name']}")
        elif op == "gold":
            amt = max(eff["amount"], -state.gold)
            state.gold += amt
            msgs.append(f"{amt:+d} marks")
        elif op == "hp":
            if eff["amount"] < 0:
                p.damage(-eff["amount"])
                p.hp = max(p.hp, 1)  # events wound, combat kills
                p.alive = True
            else:
                p.heal(eff["amount"])
            msgs.append(f"{eff['amount']:+d} health")
        elif op == "food":
            p.food = max(0.0, min(100.0, p.food + eff["amount"]))
        elif op == "water":
            p.water = max(0.0, min(100.0, p.water + eff["amount"]))
        elif op == "refill_water":
            n = refill_water(state)
            msgs.append(f"Filled {n} water flask{'s' if n != 1 else ''}." if n else "Your flasks are already full.")
        elif op == "time":
            msgs += timeflow.advance(state, eff["hours"] * 60)
            if state.travel is not None:
                state.travel["hours"] += eff["hours"]
        elif op == "rep":
            factions.change_rep(state, eff["faction"], eff["amount"], ctx.get("reason"))
            msgs.append(f"{state.data.factions[eff['faction']]['name']} reputation {eff['amount']:+d}")
        elif op == "memory":
            state.memory.record("player", eff["type"], eff["text"], day=state.clock.day_index,
                                minute=state.clock.total_minutes % 1440, importance=eff.get("importance", 1),
                                location=ctx.get("location", state.location))
        elif op == "xp":
            p.train(eff["skill"], eff["amount"], state.race_data)
        elif op == "loot":
            mult = 1.0 + p.skills["gathering"] / 200
            msgs += roll_loot(state, eff["table"], mult)
        elif op == "progress":
            if state.travel is not None:
                t = state.travel
                t["done"] = max(0.0, min(t["km"], t["done"] + eff["km"]))
                msgs.append(("Gained" if eff["km"] > 0 else "Lost") + f" {abs(eff['km'])} km.")
        elif op == "rumor":
            msgs.append('"' + state.rng.choice(state.data.rumors) + '"')
        elif op == "check":
            skill = eff["skill"]
            val = p.skills.get(skill, p.attributes.get(skill, 0))
            chance = min(0.95, eff["base"] + val * eff["per_point"])
            branch = "success" if state.rng.random() < chance else "fail"
            msgs += apply(state, eff[branch], ctx)
        elif op == "combat":
            lo, hi = eff["count"]
            res = skirmish.resolve(state, eff["enemy"], state.rng.randint(lo, hi))
            msgs += res["messages"]
            ctx["combat"] = res
        else:
            raise ValueError(f"unknown effect op '{op}'")
    return msgs
