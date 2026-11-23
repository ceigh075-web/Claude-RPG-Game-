"""Player-facing knowledge derived from the game data: where things come from, what they're for, how to earn
money and what to do next. Read-only; nothing here changes game state.

Places the player hasn't been to yet are marked "(unexplored)" so they know where to head next.
"""
from ..gameplay import interactions

TOOLS = {"pickaxe": "mining ore (needed for ore veins)", "hatchet": "chopping wood", "bedroll": "camping on the road"}


def _place(state, lid):
    loc = state.data.location(lid)
    return loc["name"] if lid in state.discovered else loc["name"] + " (unexplored)"


def _places(state, ids, limit=4):
    names = []
    for lid in sorted(ids, key=lambda i: (i not in state.discovered, state.data.location(i)["name"])):
        n = _place(state, lid)
        if n not in names:
            names.append(n)
    out = names[:limit]
    if len(names) > limit:
        out.append(f"{len(names) - limit} more")
    return ", ".join(out)


STATION = {"alchemy": "an alchemy table", "alchemy_table": "an alchemy table", "anvil": "an anvil",
           "furnace": "a furnace", "workbench": "a workbench", "stove": "a stove", "campfire": "a campfire",
           "loom": "a loom", "tannery": "a tanning rack"}
SHOP_ORDER = ["market", "general_store", "provisioner", "assayer", "smithy", "armorer", "apothecary", "enchanter"]


def station_name(st):
    return STATION.get(st, ("an " if st[:1] in "aeiou" else "a ") + st.replace("_", " "))


def enemy_homes(data, enemy_id):
    return [w["id"] for w in data.wilderness.values() if enemy_id in w.get("enemies", [])]


def shop_towns(data, shop_type):
    return [t["id"] for t in data.towns.values() if shop_type in t.get("shops", [])]


def sources(state, item_id):
    """Ways to obtain an item, most useful first."""
    data = state.data
    out = []
    wild = list(data.wilderness.values())
    forage = [w["id"] for w in wild if item_id in w["resources"].get("forage", [])]
    if forage:
        out.append("Forage bushes in " + _places(state, forage))
    if item_id.endswith("_ore"):
        ore = item_id[:-4]
        veins = [w["id"] for w in wild if ore in w["resources"].get("ores", [])]
        if veins:
            need = data.ores[ore]["mining_skill"]
            out.append(f"Mine {data.ores[ore]['name']} veins (pickaxe{f', Mining {need}+' if need else ''}) in "
                       + _places(state, veins))
    if item_id == "wood":
        out.append("Chop trees with a hatchet or axe in almost any wild area")
    if item_id == "stone":
        out.append("Break rocks in the wilds")
    if item_id == "mana_crystal":
        cr = [w["id"] for w in wild if w["resources"].get("crystals")]
        if cr:
            out.append("Mine glowing crystal nodes in " + _places(state, cr))
    scav = [entry for entry in data.loot_tables.get("scavenge", []) if entry[0] == item_id]
    if scav:
        piles = [w["id"] for w in wild if w["resources"].get("scavenge")]
        out.append("Search debris piles in " + _places(state, piles, 3))
    drops = [e for eid, e in data.enemies.items() if item_id in e.get("loot", {}) and not e.get("training")]
    for e in drops[:3]:
        eid = next(k for k, v in data.enemies.items() if v is e)
        homes = enemy_homes(data, eid)
        out.append(f"Dropped by {e['name']}" + (f" ({_places(state, homes, 2)})" if homes else ""))
    for r in data.recipes.values():
        if r["out"] == item_id:
            ins = ", ".join(f"{n}x {data.item(i)['name']}" for i, n in r["inputs"].items())
            out.append(f"Craft at {station_name(r['station'])} from {ins}")
            break
    sellers = [st for st, sh in data.shops.items() if item_id in sh.get("stock", {})]
    if sellers:
        towns = [t for st in sellers for t in shop_towns(data, st)]
        names = sorted({data.shops[st]["name"] for st in sellers})
        out.append(f"Buy from {', '.join(names[:3])}" + (f" in {_places(state, towns, 3)}" if towns else ""))
    towns = [t["id"] for t in data.towns.values() if item_id in t.get("resources", [])]
    if towns:
        out.append("Local produce of " + _places(state, towns))
    for feat, loot in interactions.TREASURES.items():
        if item_id in loot:
            out.append("Hidden treasure at a landmark deep in the wilds")
            break
    return out or ["Rare: found on adventures, through jobs or as rewards"]


def uses(state, item_id):
    """What an item is good for."""
    data = state.data
    it = data.item(item_id)
    out = []
    t = it["type"]
    if it.get("food"):
        out.append(f"Eat: +{it['food']} food")
    if it.get("water"):
        out.append(f"Drink: +{it['water']} water")
    if it.get("heal"):
        out.append(f"Heals {it['heal']} health")
    if it.get("mana"):
        out.append(f"Restores {it['mana']} mana")
    if t == "weapon":
        w = data.weapons[it["weapon"]]
        out.append(f"Equip as a {w['class']} weapon ({it['weapon']}, {w['skill']} skill)")
    elif t == "armor":
        out.append(f"Wear on your {it.get('slot', 'body')}: +{it.get('armor', 0)} armour")
    elif t == "tool":
        out.append("Tool for " + TOOLS.get(item_id, "gathering"))
    elif t == "ore" and item_id.endswith("_ore"):
        out.append(data.ores[item_id[:-4]]["uses"])
    made = []
    for r in data.recipes.values():
        if item_id in r["inputs"]:
            name = data.item(r["out"])["name"]
            if name not in made:
                made.append(name)
    if made:
        out.append("Crafting: " + ", ".join(made[:5]) + (f" and {len(made) - 5} more" if len(made) > 5 else ""))
    order = {k: i for i, k in enumerate(SHOP_ORDER)}
    buyers = [data.shops[k]["name"] for k in sorted(data.shops, key=lambda k: order.get(k, 99))
              if t in data.shops[k].get("buys", [])]
    if buyers:
        out.append(f"Sell to {', '.join(buyers[:3])} (about {max(1, int(it['value'] * 0.5))}+ marks each)")
    return out


def money_methods(state):
    """How to earn marks, from the systems that exist."""
    data = state.data
    out = [
        ("Sell what you gather", "Forage herbs and berries, mine ore, chop wood and search debris, then sell at shops. "
                                 "Each shop only buys certain kinds of goods (shown when you sell). Merchants have "
                                 "limited cash that refills weekly."),
        ("Craft, then sell", "Smelt ore into bars and forge tools or weapons: finished goods sell for far more than "
                             "raw materials. Recipes show what they need and where to find it."),
        ("Job boards", "Every town square has a job board: bounties, deliveries, escorts and monster hunts pay well. "
                       "Check progress in the Journal (J), Jobs tab."),
        ("Trade between towns", "Prices differ by region and with world events (shortages, caravans). Buy where "
                                "goods are cheap and sell where they're scarce."),
        ("Loot", "Enemies drop hides, meat, coins and gear. Bandits and Hollow soldiers carry marks."),
        ("Favors", "Named NPCs ask for favors; finishing them earns gifts, trust and sometimes marks."),
        ("Your outpost", "Later, an outpost's farms and workshops produce goods every day."),
    ]
    work = [(t["name"], a) for t in data.towns.values() for a in t.get("activities", []) if "pay" in a.lower()
            or "work" in a.lower() or "bount" in a.lower()]
    if work:
        out.insert(2, ("Town work", "; ".join(f"{a} ({n})" for n, a in work[:5])))
    return out


def job_next_step(state, job):
    """A plain-language 'what to do next' for an active job."""
    data = state.data
    t = job["type"]
    town = data.location(job["town"])["name"]
    if t == "bounty":
        homes = enemy_homes(data, job["enemy"])
        where = _places(state, homes, 3) if homes else "on the roads (ambushes)"
        return f"Hunt {data.enemies[job['enemy']]['name']}s in {where}, then report to the board in {town}."
    if t == "delivery":
        item = data.item(job["item"])["name"]
        src = sources(state, job["item"])[0]
        return f"Get {job['qty']}x {item} ({src.lower()}) and bring it to {data.location(job['to'])['name']}."
    if t == "escort":
        return f"Travel to {data.location(job['to'])['name']} with your charge."
    if t == "hunt":
        return f"Find and slay the named beast near {_place(state, job.get('where', job['town']))}, then return to {town}."
    if t == "pay":
        return f"Gather {job['gold']} marks and pay at the board in {town}."
    return "Check the job board."


def place_summary(state, lid):
    """One-line 'what's here' for the guide's places chapter."""
    data = state.data
    loc = data.location(lid)
    if loc["kind"] == "town":
        shops = ", ".join(sorted({data.shops[s]["name"] for s in loc.get("shops", []) if s in data.shops})) or "no shops"
        acts = "; ".join(loc.get("activities", [])[:3])
        return f"Town ({loc['specialty']}). Shops: {shops}. {acts}"
    res = loc["resources"]
    bits = []
    if res.get("forage"):
        bits.append("forage " + ", ".join(data.item(i)["name"].lower() for i in res["forage"]))
    if res.get("ores"):
        bits.append("ore: " + ", ".join(data.ores[o]["name"] for o in res["ores"]))
    if res.get("crystals"):
        bits.append("mana crystals")
    if res.get("wood"):
        bits.append("wood")
    if res.get("water"):
        bits.append("fresh water")
    foes = ", ".join(data.enemies[e]["name"] for e in loc.get("enemies", []) if e in data.enemies)
    return f"Wilds, danger {loc['danger']}/5. " + ("; ".join(bits) or "little to gather") + (f". Beware: {foes}" if foes else "")


def station_places(state, station):
    """Towns where a crafting station can be found (from the buildings each town has)."""
    from ..world import mapgen
    obj = {"alchemy": "alchemy_table"}.get(station, station)
    btypes = {b for b, objs in mapgen.STATIONS_BY_BUILDING.items() if obj in objs}
    if station in ("anvil", "furnace"):
        btypes |= {"smithy", "forge"}
    towns = [t["id"] for t in state.data.towns.values() if btypes & set(t.get("buildings", []))]
    if station == "campfire":
        return "campsites in the wilds, or rest anywhere on the road"
    return _places(state, towns, 5) if towns else "nowhere you know of yet"
