"""Loads and validates all JSON content, and derives generated items (ore, bars, weapons)."""
import json
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")

# Gift / preference tags derived from item ids & types.
TYPE_TAGS = {
    "food": "food", "drink": "drink", "medicine": "herbs", "ore": "ore", "bar": "ore",
    "weapon": "weapons", "tool": "tools", "magic": "magic", "valuable": "jewelry",
    "book": "books", "ammo": "weapons",
}
ID_TAGS = {
    "herbs": "herbs", "mirelight_herb": "herbs", "relic_shard": "relic", "hide": "hide",
    "leather": "hide", "trinket": "jewelry", "old_book": "books", "ale": "drink",
}


class DataError(Exception):
    pass


def _load(name):
    with open(os.path.join(DATA_DIR, name), encoding="utf-8") as f:
        return json.load(f)


class GameData:
    """Read-only content database. One instance shared by the whole game."""

    def __init__(self):
        self.races = _load("races.json")
        self.factions = _load("factions.json")
        self.faction_relations = self.factions.pop("relations")
        loc = _load("locations.json")
        self.towns = {t["id"]: dict(t, kind="town") for t in loc["towns"]}
        self.wilderness = {w["id"]: dict(w, kind="wild") for w in loc["wilderness"]}
        self.locations = {**self.towns, **self.wilderness}
        self.routes = loc["routes"]
        self.ores = _load("ores.json")
        self.weapons = {k: v for k, v in _load("weapons.json").items() if not k.startswith("_")}
        self.magic = _load("magic.json")
        self.items = {k: v for k, v in _load("items.json").items() if not k.startswith("_")}
        self.enemies = _load("enemies.json")
        self.npcs = {n["id"]: n for n in _load("npcs.json")}
        self.schedules = {k: v for k, v in _load("schedules.json").items() if not k.startswith("_")}
        self.shops = {k: v for k, v in _load("shops.json").items() if not k.startswith("_")}
        self.recipe_list = _load("recipes.json")["recipes"]
        self.economy = {k: v for k, v in _load("economy.json").items() if not k.startswith("_")}
        te = _load("travel_events.json")
        self.travel_events = te["events"]
        self.loot_tables = te["loot_tables"]
        self.rumors = te["rumors"]
        self._generate_items()
        self.validate()

    # ------------------------------------------------------------------ generation
    def _generate_items(self):
        for oid, ore in self.ores.items():
            self.items[f"{oid}_ore"] = {
                "name": f"{ore['name']} Ore" if "Iron" not in ore["name"] else f"{ore['name'].split()[0]} Ore",
                "type": "ore", "value": ore["value"], "weight": 1.5, "ore": oid,
                "desc": f"Raw {ore['name']}. {ore['uses']}",
            }
            self.items[f"{oid}_bar"] = {
                "name": f"{ore['name']} Bar", "type": "bar", "value": ore["bar_value"], "weight": 1.0, "ore": oid,
                "desc": f"A smelted bar of {ore['name']}.",
            }
        for wid, w in self.weapons.items():
            if w.get("bars", 0) <= 0:
                continue
            for oid, ore in self.ores.items():
                eq = ore["equipment"]
                extra_value = sum(self.items.get(m, {"value": 2})["value"] * q for m, q in w["extra"].items())
                self.items[f"{wid}_{oid}"] = {
                    "name": f"{ore['name'].split()[0]} {w['name'] if wid != 'throwing' else 'Throwing Knives'}",
                    "type": "weapon", "weapon": wid, "ore": oid,
                    "value": int(w["bars"] * ore["bar_value"] * 1.3 + extra_value + 5),
                    "weight": round(w["weight"] * eq["weight_mult"], 2),
                    "damage": round(w["damage"] * eq["damage_mult"], 1),
                    "speed": round(w["speed"] * eq["speed_mult"], 2),
                    "desc": f"{w['special']} ({ore['name']}: tier {ore['tier']}.)",
                }
        # metal armor: a helm and a mail coat per ore
        for oid, ore in self.ores.items():
            eq = ore["equipment"]
            short = ore["name"].split()[0]
            for slot, (key, label, base, bars, extra) in {"head": ("helm", "Helm", 2.0, 2, {}),
                                                            "body": ("mail", "Mail", 5.0, 4, {"leather": 2})}.items():
                self.items[f"{key}_{oid}"] = {
                    "name": f"{short} {label}", "type": "armor", "slot": slot, "ore": oid,
                    "armor": round(base * eq["armor_mult"], 1),
                    "value": int(bars * ore["bar_value"] * 1.3 + 12 * sum(extra.values()) + 5),
                    "weight": round((3.0 if slot == "head" else 8.0) * eq["weight_mult"], 1), "bars": bars, "extra": extra,
                    "desc": f"{ore['name']} {label.lower()}. Armor {round(base * eq['armor_mult'], 1)}.",
                }
        self._generate_recipes()
        self.items.setdefault("old_book", {"name": "Weathered Book", "type": "book", "value": 10, "weight": 0.5,
                                            "desc": "A water-stained book. Scholars love these."})

    def _generate_recipes(self):
        tier_skill = {1: 0, 2: 10, 3: 25, 4: 45}
        self.recipes = {}
        for oid, ore in self.ores.items():
            t = ore["tier"]
            self.recipes[f"smelt_{oid}"] = {"id": f"smelt_{oid}", "out": f"{oid}_bar", "qty": 1, "station": "furnace",
                                            "inputs": {f"{oid}_ore": 2}, "minutes": 20 + 10 * t, "skill": tier_skill[t]}
            need = "voidglass" if oid == "voidglass" else None
            for wid, w in self.weapons.items():
                if w.get("bars", 0) <= 0:
                    continue
                station = "workbench" if wid in ("bow", "crossbow", "throwing") else "anvil"
                inputs = {f"{oid}_bar": w["bars"]}
                inputs.update(w["extra"])
                self.recipes[f"{wid}_{oid}"] = {"id": f"{wid}_{oid}", "out": f"{wid}_{oid}", "qty": 3 if wid == "throwing" else 1,
                                                "station": station, "inputs": inputs, "minutes": 40 + 20 * w["bars"],
                                                "skill": tier_skill[t], "requires": need}
            for key in ("helm", "mail"):
                it = self.items[f"{key}_{oid}"]
                inputs = {f"{oid}_bar": it["bars"]}
                inputs.update(it["extra"])
                self.recipes[f"{key}_{oid}"] = {"id": f"{key}_{oid}", "out": f"{key}_{oid}", "qty": 1, "station": "anvil",
                                                "inputs": inputs, "minutes": 50 + 25 * it["bars"], "skill": tier_skill[t] + 5,
                                                "requires": need}
        for r in self.recipe_list:
            self.recipes[r["id"]] = r

    # ------------------------------------------------------------------ helpers
    def item(self, item_id):
        try:
            return self.items[item_id]
        except KeyError:
            raise DataError(f"Unknown item '{item_id}'") from None

    def item_tags(self, item_id):
        it = self.item(item_id)
        tags = set()
        if item_id in ID_TAGS:
            tags.add(ID_TAGS[item_id])
        if it["type"] in TYPE_TAGS:
            tags.add(TYPE_TAGS[it["type"]])
        return tags

    def location(self, loc_id):
        return self.locations[loc_id]

    # ------------------------------------------------------------------ validation
    def validate(self):
        errs = []

        def need(cond, msg):
            if not cond:
                errs.append(msg)

        need(len(self.towns) == 9, f"expected 9 towns, got {len(self.towns)}")
        need(len(self.wilderness) == 20, f"expected 20 wilderness areas, got {len(self.wilderness)}")
        need(len(self.ores) == 4, "expected 4 ores")
        melee = [w for w in self.weapons.values() if w["class"] == "melee"]
        ranged = [w for w in self.weapons.values() if w["class"] == "ranged"]
        need(len(melee) == 12 and len(ranged) == 4, "expected 12 melee + 4 ranged weapon types")
        need(len(self.magic["elements"]) == 4, "expected 4 elements")
        need(len(self.magic["subelements"]) == 16, "expected 16 sub-elements")
        for eid, el in self.magic["elements"].items():
            need(len(el["subs"]) == 4, f"element {eid} needs 4 subs")
            for s in el["subs"]:
                need(self.magic["subelements"].get(s, {}).get("element") == eid, f"sub {s} not linked to {eid}")
        need(40 <= len(self.npcs) <= 50, f"NPC count {len(self.npcs)} outside 40-50")
        ids = set(self.locations)
        for a, b, terrain in self.routes:
            need(a in ids and b in ids, f"route {a}-{b} references unknown location")
        for n in self.npcs.values():
            need(n["home"] in ids, f"npc {n['id']} home {n['home']} unknown")
            need(n["race"] in self.races, f"npc {n['id']} race unknown")
            need(n["faction"] is None or n["faction"] in self.factions, f"npc {n['id']} faction unknown")
            need(n["schedule"] in self.schedules, f"npc {n['id']} schedule unknown")
            need(bool(n.get("recruit")), f"npc {n['id']} has no recruitment path")
            for e in n["equipment"]:
                need(e in self.items, f"npc {n['id']} equipment {e} unknown")
            if "shop" in n:
                need(n["shop"] in self.shops, f"npc {n['id']} shop unknown")
        for sid, shop in self.shops.items():
            for it in shop["stock"]:
                need(it in self.items, f"shop {sid} stocks unknown item {it}")
        for rid, r in self.recipes.items():
            need(r["out"] in self.items, f"recipe {rid} makes unknown item {r['out']}")
            for it in r["inputs"]:
                need(it in self.items, f"recipe {rid} needs unknown item {it}")
        for tname, table in self.loot_tables.items():
            for row in table:
                need(row[0] == "marks" or row[0] in self.items, f"loot {tname} unknown item {row[0]}")
        for e in self.enemies.values():
            for it in e["loot"]:
                need(it == "marks" or it in self.items, f"enemy loot unknown {it}")
        # graph connectivity
        adj = {i: set() for i in ids}
        for a, b, _ in self.routes:
            adj[a].add(b)
            adj[b].add(a)
        seen, stack = set(), ["brackenford"]
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            stack.extend(adj[cur] - seen)
        need(seen == ids, f"unreachable locations: {sorted(ids - seen)}")
        if errs:
            raise DataError("Data validation failed:\n  " + "\n  ".join(errs))
