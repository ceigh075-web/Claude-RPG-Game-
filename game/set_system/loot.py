"""Looting rules (Set System): what the fallen carry, what's in containers, and moving it into your pack.

Contents are plain lists of {"item", "qty"} entries ("marks" is money). Rolls use stable seeds, so the same
body or barrel on the same day always holds the same things, and taking an entry removes it from the list:
nothing can be collected twice. Container contents live in the location's saved state and refill slowly.
"""
from ..core.rng import stable_rng

CATEGORIES = ("money", "equipment", "consumable", "material", "valuable", "misc")
CATEGORY_NAME = {"money": "Money", "equipment": "Equipment", "consumable": "Food & medicine", "material": "Materials",
                 "valuable": "Valuables", "misc": "Other"}
CATEGORY_COLOR = {"money": (240, 205, 90), "equipment": (150, 200, 255), "consumable": (130, 220, 130),
                  "material": (215, 180, 130), "valuable": (200, 150, 255), "misc": (200, 200, 200)}
CONTAINER_REFILL_DAYS = 3
GEAR_CHANCE = 0.35          # a humanoid foe's weapon survives the fight
ARMOR_CHANCE = 0.2          # ...and a leader's armour

CITIZEN_TABLE = [("bread", 1, 2, 0.35), ("ale", 1, 1, 0.2), ("cloth", 1, 2, 0.2), ("trinket", 1, 1, 0.12),
                 ("bandage", 1, 1, 0.15), ("herbs", 1, 3, 0.15), ("nails", 2, 4, 0.1)]
GUARD_TABLE = [("ration", 1, 2, 0.4), ("bandage", 1, 2, 0.3), ("longsword_rustite", 1, 1, 0.3),
               ("helm_rustite", 1, 1, 0.15)]


def category(data, item):
    if item == "marks":
        return "money"
    t = data.item(item)["type"]
    if t in ("weapon", "armor", "ammo", "tool"):
        return "equipment"
    if t in ("food", "drink", "medicine"):
        return "consumable"
    if t in ("material", "ore", "bar", "magic"):
        return "material"
    if t in ("valuable",):
        return "valuable"
    return "misc"


def value(data, entry):
    return entry["qty"] if entry["item"] == "marks" else data.item(entry["item"])["value"] * entry["qty"]


def label(data, entry):
    if entry["item"] == "marks":
        return f"{entry['qty']} marks"
    name = data.item(entry["item"])["name"]
    return f"{name} x{entry['qty']}" if entry["qty"] > 1 else name


def stack(entries):
    """Merge duplicate items and sort money first, then by category."""
    out = {}
    for e in entries:
        if e["qty"] > 0:
            out[e["item"]] = out.get(e["item"], 0) + e["qty"]
    return [{"item": k, "qty": v} for k, v in out.items()]


def sort(data, entries):
    order = {c: i for i, c in enumerate(CATEGORIES)}
    return sorted(entries, key=lambda e: (order[category(data, e["item"])], -value(data, e)))


def _roll(rng, table, mult=1.0):
    out = []
    for item, lo, hi, chance in table:
        if rng.random() < min(1.0, chance * mult):
            out.append({"item": item, "qty": rng.randint(lo, hi)})
    return out


def weapon_item(data, weapon, danger=1):
    """The plain item for an enemy's weapon class (better metal in dangerous places)."""
    tier = "greyvein" if danger >= 4 else "rustite"
    for cand in (f"{weapon}_{tier}", f"{weapon}_rustite"):
        if cand in data.items:
            return cand
    return None


def enemy_gear(data, enemy, rng, danger=1):
    """Gear left on a fallen humanoid foe's body (materials and coin scatter on the ground instead)."""
    out = []
    if enemy.get("shape", "humanoid") != "humanoid" or enemy.get("training"):
        return out
    w = weapon_item(data, enemy.get("weapon", "fists"), danger)
    if w and rng.random() < GEAR_CHANCE:
        out.append({"item": w, "qty": 1})
    leader = enemy.get("elite_event") or "captain" in enemy.get("name", "").lower() or enemy.get("hp", 0) >= 120
    if leader and rng.random() < ARMOR_CHANCE * 2:
        out.append({"item": "mail_rustite" if danger < 4 else "mail_greyvein", "qty": 1})
    elif enemy.get("armor", 0) >= 3 and rng.random() < ARMOR_CHANCE:
        out.append({"item": "helm_rustite", "qty": 1})
    if enemy.get("weapon") == "bow" and rng.random() < 0.6:
        out.append({"item": "arrow", "qty": rng.randint(3, 8)})
    return out


def citizen_loot(state, key, greedy=False, guard=False):
    """What a beaten townsperson (or guard) carries: a purse and a few belongings."""
    rng = stable_rng("body", key, state.clock.day_index)
    marks = rng.randint(2, 10) + (10 if greedy else 0) + (rng.randint(4, 12) if guard else 0)
    out = [{"item": "marks", "qty": marks}] + _roll(rng, GUARD_TABLE if guard else CITIZEN_TABLE)
    return sort(state.data, stack(out))


def container(state, loc_key, obj_key, chest=False):
    """The live contents list of a barrel / crate / chest (saved with the location; refills every few days)."""
    cs = state.location_state(loc_key).setdefault("containers", {})
    entry = cs.get(obj_key)
    day = state.clock.day_index
    if entry is None or (not entry["items"] and day >= entry["refill"]):
        rng = stable_rng("container", loc_key, obj_key, day)
        items = _roll(rng, state.data.loot_tables["container"], 2.0 if chest else 1.0)
        entry = cs[obj_key] = {"items": sort(state.data, stack(items)), "refill": day + CONTAINER_REFILL_DAYS}
    return entry["items"]


def take(state, entries, index, qty=None):
    """Move one entry (or part of it) into the player's pack. Returns (message, value taken)."""
    if not 0 <= index < len(entries):
        return None, 0
    e = entries[index]
    n = e["qty"] if qty is None else max(1, min(qty, e["qty"]))
    got = {"item": e["item"], "qty": n}
    if e["item"] == "marks":
        state.gold += n
    else:
        state.player.inventory.add(e["item"], n)
    e["qty"] -= n
    if e["qty"] <= 0:
        entries.pop(index)
    return f"+ {label(state.data, got)}", value(state.data, got)


def take_all(state, entries, only=None):
    """Take everything (or one category). Returns (messages, value taken)."""
    msgs, total = [], 0
    i = 0
    while i < len(entries):
        if only and category(state.data, entries[i]["item"]) != only:
            i += 1
            continue
        m, v = take(state, entries, i)
        msgs.append(m)
        total += v
    return msgs, total


def deposit_materials(state, storage_inv):
    """Quick-deposit: move every raw material from the pack into storage. Returns how many items moved."""
    inv = state.player.inventory
    moved = 0
    for item, n in list(inv.items.items()):
        if item in state.player.equipment.values():
            continue
        if category(state.data, item) == "material":
            inv.remove(item, n)
            storage_inv.add(item, n)
            moved += n
    return moved
