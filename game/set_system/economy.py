"""Shops: stock, merchant cash, prices, weekly restocking, buying and selling."""
import math

from . import factions


def shop_state(state, location_id, shop_id):
    """Get (creating on first visit) the persistent state of a shop in a location."""
    ls = state.location_state(location_id)
    shops = ls.setdefault("shops", {})
    if shop_id not in shops:
        sdef = state.data.shops[shop_id]
        shops[shop_id] = {"stock": {k: v[0] for k, v in sdef["stock"].items()}, "cash": sdef["cash"],
                          "week": state.clock.week_index}
    restock(state, location_id, shop_id)
    return shops[shop_id]


def restock(state, location_id, shop_id):
    s = state.location_state(location_id)["shops"][shop_id]
    sdef = state.data.shops[shop_id]
    weeks = state.clock.week_index - s["week"]
    if weeks <= 0:
        return
    for item, (base, per_week) in sdef["stock"].items():
        s["stock"][item] = min(base, s["stock"].get(item, 0) + per_week * weeks)
    s["cash"] = max(s["cash"], min(sdef["cash"], s["cash"] + sdef["cash"] // 2 * weeks))
    s["week"] = state.clock.week_index


def _faction_of(state, location_id):
    return state.data.location(location_id).get("faction") if location_id in state.data.locations else None


def regional(state, location_id, item_id):
    """Regional supply/demand multiplier times active world-event modifiers (shortages, caravans, wars...)."""
    t = state.data.item(item_id)["type"]
    m = state.data.economy.get(location_id, {}).get(t, 1.0)
    for mod in state.world.get("modifiers", []):
        if mod["kind"] == "price" and mod["location"] in (location_id, "*") and mod.get("type") in (t, "*"):
            m *= mod["mult"]
    return m


def buy_price(state, location_id, shop_id, item_id):
    sdef = state.data.shops[shop_id]
    value = state.data.item(item_id)["value"]
    trade = state.player.skills["trading"]
    p = value * sdef["markup"] * (1 - trade / 400) * factions.price_factor(state, _faction_of(state, location_id))
    return max(1, math.ceil(p * regional(state, location_id, item_id)))


def sell_price(state, location_id, shop_id, item_id):
    sdef = state.data.shops[shop_id]
    value = state.data.item(item_id)["value"]
    trade = state.player.skills["trading"]
    p = value * sdef["sell_rate"] * (1 + trade / 300) / factions.price_factor(state, _faction_of(state, location_id))
    return max(0, math.floor(p * regional(state, location_id, item_id)))


def will_buy(state, shop_id, item_id):
    t = state.data.item(item_id)["type"]
    return t in state.data.shops[shop_id]["buys"] and t != "key"


def buy(state, location_id, shop_id, item_id, qty=1):
    s = shop_state(state, location_id, shop_id)
    if s["stock"].get(item_id, 0) < qty:
        return False, "They don't have that many."
    price = buy_price(state, location_id, shop_id, item_id) * qty
    if state.gold < price:
        return False, f"You need {price} marks."
    state.gold -= price
    s["cash"] += price
    s["stock"][item_id] -= qty
    state.player.inventory.add(item_id, qty)
    state.player.train("trading", 0.5 * qty, state.data.races[state.player.race])
    state.stats["marks_spent"] = state.stats.get("marks_spent", 0) + price
    return True, f"Bought {qty}x {state.data.item(item_id)['name']} for {price} marks."


def sell(state, location_id, shop_id, item_id, qty=1):
    s = shop_state(state, location_id, shop_id)
    if not will_buy(state, shop_id, item_id):
        return False, "They don't deal in that."
    if not state.player.inventory.has(item_id, qty):
        return False, "You don't have that many."
    price = sell_price(state, location_id, shop_id, item_id) * qty
    if price <= 0:
        return False, "That's worthless to them."
    if s["cash"] < price:
        return False, f"The merchant only has {s['cash']} marks."
    state.player.inventory.remove(item_id, qty)
    for slot, eq in state.player.equipment.items():
        if eq == item_id and not state.player.inventory.has(item_id):
            state.player.equipment[slot] = None
    state.gold += price
    s["cash"] -= price
    s["stock"][item_id] = s["stock"].get(item_id, 0) + qty
    state.player.train("trading", 0.8 * qty, state.data.races[state.player.race])
    state.stats["marks_earned"] = state.stats.get("marks_earned", 0) + price
    return True, f"Sold {qty}x {state.data.item(item_id)['name']} for {price} marks."
