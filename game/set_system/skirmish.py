"""Abstract (auto-resolved) fights used for travel encounters and off-screen battles.

Deterministic given the GameRNG state. Real-time combat (Phase 3) is used when fighting in local maps;
this resolver remains for events where the player chooses not to fight in real time and for simulated
off-screen fights.
"""
from . import items as items_mod

KO_HP = 5


def player_profile(state, p=None):
    p = p or state.player
    data = state.data
    wtype, item_id = items_mod.equipped_weapon(data, p)
    w = data.weapons[wtype]
    base = data.item(item_id)["damage"] if item_id else w["damage"]
    scale = sum(p.attr(a) * s for a, s in w["scaling"].items()) / 10.0
    skill = p.skills[w["skill"]]
    dmg = base * (0.6 + 0.4 * scale) * (1 + skill / 100)
    speed = (data.item(item_id)["speed"] if item_id else w["speed"]) * (1 + p.attr("dexterity") / 100)
    hit = min(0.95, 0.65 + p.attr("dexterity") / 200 + skill / 300)
    defend = min(0.6, p.skills["blocking"] / 250 + p.skills["dodging"] / 250 + p.attr("speed") / 400)
    return {"damage": dmg, "speed": speed, "hit": hit, "defend": defend, "weapon": wtype}


def resolve(state, enemy_id, count):
    """Fight `count` enemies of a type. Mutates state. Returns dict with outcome and messages."""
    data, rng, p = state.data, state.rng, state.player
    e = data.enemies[enemy_id]
    prof = player_profile(state)
    from . import companions as comp_mod
    allies = [comp_mod.char(state, cid) for cid in comp_mod.squad(state)]
    ally_profs = [player_profile(state, a) for a in allies]
    foes = [{"hp": float(e["hp"])} for _ in range(count)]
    msgs = [f"You fight {count} {e['name']}{'s' if count > 1 else ''}!"]
    t = 0.0
    dt = 0.5
    killed, fled = 0, 0
    hp_start = p.hp
    while foes and p.hp > KO_HP and t < 120:
        t += dt
        # player attacks
        if rng.random() < prof["speed"] * dt:
            if rng.random() < prof["hit"]:
                dmg = max(1.0, prof["damage"] - e["armor"] * 0.5) * rng.uniform(0.8, 1.2)
                foes[0]["hp"] -= dmg
                if foes[0]["hp"] <= 0:
                    foes.pop(0)
                    killed += 1
                elif e.get("flee_below", 0) and foes[0]["hp"] < e["hp"] * e["flee_below"] and rng.random() < 0.3:
                    foes.pop(0)
                    fled += 1
        for a, ap in zip(allies, ally_profs):
            if foes and a.hp > KO_HP and rng.random() < ap["speed"] * dt and rng.random() < ap["hit"]:
                foes[0]["hp"] -= max(1.0, ap["damage"] - e["armor"] * 0.5) * rng.uniform(0.8, 1.2)
                if foes[0]["hp"] <= 0:
                    foes.pop(0)
                    killed += 1
        # enemies attack (at most 3 can reach the party at once); blows spread over the party
        party = [(p, prof)] + [(a, ap) for a, ap in zip(allies, ally_profs) if a.hp > KO_HP]
        for f in foes[:3]:
            if rng.random() < 0.8 * dt:
                who, wp = party[rng.randrange(len(party))]
                if rng.random() < wp["defend"]:
                    continue
                who.damage(e["damage"] * rng.uniform(0.7, 1.1))
                if who is not p:
                    who.hp = max(who.hp, 1.0)
                    who.alive = True
    lost_hp = hp_start - p.hp
    race = state.race_data
    w = data.weapons[prof["weapon"]]
    p.train(w["skill"], 3 + killed * 3, race)
    for a in w["scaling"]:
        p.train(a, 2 + killed * 2, race)
    p.train("health", lost_hp / 5, race)
    p.train("blocking", 1 + killed, race)
    p.train("dodging", 1 + killed, race)
    loot_msgs = []
    if not foes and allies:
        comp_mod.shared_victory(state, killed)
    if not foes:
        msgs.append(f"Victory! You defeated {killed}" + (f" and {fled} fled" if fled else "") + f". (-{lost_hp:.0f} HP)")
        for _ in range(killed):
            loot_msgs += roll_enemy_loot(state, enemy_id)
        outcome = "victory"
    else:
        msgs.append(apply_defeat(state, enemy_id))
        outcome = "defeat"
    if fled:
        state.memory.record(enemy_id, "escaped", f"{fled} {e['name']}(s) fled a fight with {p.name}.",
                            day=state.clock.day_index, minute=state.clock.total_minutes % 1440, importance=1,
                            related=["player"], location=state.location)
    if e.get("faction") and killed:
        from . import factions
        factions.change_rep(state, e["faction"], -2 * killed, "killed members in a fight")
        if e["faction"] == "hollow":
            factions.change_rep(state, "crown", killed, "killed Hollow outlaws")
            factions.change_rep(state, "caravans", killed, "killed Hollow outlaws")
    state.stats["kills"] = state.stats.get("kills", 0) + killed
    from . import jobs, world_events
    for _ in range(killed):
        jobs.note_kill(state, enemy_id)
    if e.get("faction") == "hollow":
        world_events.hollow_kill(state, killed)
    return {"outcome": outcome, "messages": msgs + loot_msgs, "killed": killed, "fled": fled}


def roll_enemy_loot(state, enemy_id):
    msgs = []
    for item, (lo, hi) in state.data.enemies[enemy_id]["loot"].items():
        n = state.rng.randint(lo, hi)
        if n <= 0:
            continue
        if item == "marks":
            state.gold += n
            msgs.append(f"Looted {n} marks.")
        else:
            state.player.inventory.add(item, n)
            msgs.append(f"Looted {n}x {state.data.item(item)['name']}.")
    return msgs


def apply_defeat(state, enemy_id):
    """The player is beaten (never killed outright by a fight): robbed, left weak. Returns a message."""
    p = state.player
    e = state.data.enemies[enemy_id]
    p.hp = max(p.hp, KO_HP)
    p.alive = True
    takes_loot = e.get("faction") is not None
    stolen = int(state.gold * 0.4) if takes_loot else 0
    state.gold -= stolen
    food_taken = min(p.inventory.count("ration"), 2)
    if food_taken:
        p.inventory.remove("ration", food_taken)
    state.memory.record(enemy_id, "encounter", f"{e['name']}s beat {p.name}" + (" and robbed them." if stolen else "."),
                        day=state.clock.day_index, minute=state.clock.total_minutes % 1440, importance=2,
                        related=["player"], location=state.location)
    if takes_loot:
        return (f"You are beaten down and left in the dirt. They take {stolen} marks"
                + (f" and {food_taken} rations." if food_taken else "."))
    return "You collapse, mauled. When you come to, the beasts have torn into your food" + \
        (f" ({food_taken} rations lost)." if food_taken else ".")
