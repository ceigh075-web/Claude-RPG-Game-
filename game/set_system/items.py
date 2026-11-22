"""Using, equipping and dropping items. All functions return (ok: bool, message: str)."""
from . import needs

CONSUMABLE_TYPES = ("food", "drink", "medicine", "magic")


def can_use(data, item_id):
    return data.item(item_id)["type"] in CONSUMABLE_TYPES


def use_item(state, char, item_id):
    data = state.data
    if not char.inventory.has(item_id):
        return False, "You don't have that."
    it = data.item(item_id)
    if it["type"] not in CONSUMABLE_TYPES:
        return False, f"You can't use {it['name']} directly."
    parts = []
    if it.get("food"):
        if char.food >= 99 and not it.get("water"):
            return False, "You're not hungry."
        char.food = min(100.0, char.food + it["food"])
        parts.append(f"+{it['food']} food")
    if it.get("water"):
        char.water = min(100.0, char.water + it["water"])
        parts.append(f"+{it['water']} water")
    if it.get("heal"):
        if char.hp >= char.max_hp:
            return False, "You're not hurt."
        char.heal(it["heal"])
        parts.append(f"+{it['heal']} health")
    if it.get("mana"):
        char.mana = min(char.max_mana, char.mana + it["mana"])
        parts.append(f"+{it['mana']} mana")
    char.inventory.remove(item_id)
    needs.apply_modifiers(char)
    return True, f"Used {it['name']} ({', '.join(parts)})."


def weapon_slot(data, item_id):
    it = data.item(item_id)
    if it["type"] == "armor":
        return it["slot"]
    if it["type"] != "weapon":
        return None
    return "ranged" if data.weapons[it["weapon"]]["class"] == "ranged" else "weapon"


def equip(state, char, item_id):
    data = state.data
    slot = weapon_slot(data, item_id)
    if slot is None:
        return False, "That can't be equipped."
    if not char.inventory.has(item_id):
        return False, "You don't have that."
    if char.equipment.get(slot) == item_id:
        return False, "Already equipped."
    char.equipment[slot] = item_id
    return True, f"Equipped {data.item(item_id)['name']}."


def unequip(state, char, slot):
    item_id = char.equipment.get(slot)
    if not item_id:
        return False, "Nothing equipped there."
    char.equipment[slot] = None
    return True, f"Unequipped {state.data.item(item_id)['name']}."


def drop(state, char, item_id, qty=1):
    if not char.inventory.has(item_id, qty):
        return False, "You don't have that many."
    char.inventory.remove(item_id, qty)
    for slot, eq in char.equipment.items():
        if eq == item_id and not char.inventory.has(item_id):
            char.equipment[slot] = None
    return True, f"Dropped {qty}x {state.data.item(item_id)['name']}."


def equipped_weapon(data, char):
    """(weapon_type_id, item_id or None) for the active melee weapon."""
    item_id = char.equipment.get("weapon")
    if item_id and char.inventory.has(item_id):
        return data.item(item_id)["weapon"], item_id
    return "fists", None
