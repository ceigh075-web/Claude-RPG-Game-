"""Item icons: weapons and tools come from the Pixel Crawler weapon sheet; everything else is small hand-made
pixel art in the same style (dark outline, 2-3 tone shading). Used for dropped loot, the loot panel and lists.

Each template is a 12x12 grid: '.' empty, 'o' outline, 'd' dark, 'm' mid, 'l' light, 'h' highlight.
"""
import pygame

from . import assets

T = {
    "coins": [
        "............",
        "............",
        "....oooo....",
        "...ollllo...",
        "..ohhllmmo..",
        "..ommmmddo..",
        "..ooooooooo.",
        ".ollllmmo.o.",
        ".ohllmmmdo..",
        ".odddddddo..",
        "..ooooooo...",
        "............"],
    "sack": [
        "............",
        ".....oo.....",
        "....odmo....",
        ".....oo.....",
        "....ommo....",
        "...ollmmo...",
        "..ollmmmdo..",
        "..ohlmmmdo..",
        "..olmmmmdo..",
        "..ommmmddo..",
        "...oooooo...",
        "............"],
    "bottle": [
        "............",
        ".....oo.....",
        "....oddo....",
        ".....oo.....",
        "....omlo....",
        "...ommllo...",
        "..ommmmlho..",
        "..ommmmmlo..",
        "..odmmmmmo..",
        "..oddmmmmo..",
        "...oooooo...",
        "............"],
    "food": [
        "............",
        "............",
        "....oooo....",
        "...ollllo...",
        "..olhhllmo..",
        ".ollllllmmo.",
        ".ommmmmmmdo.",
        ".odmmmmmddo.",
        "..oddddddo..",
        "...oooooo...",
        "............",
        "............"],
    "ore": [
        "............",
        "............",
        ".....ooo....",
        "....ohlmo...",
        "...olllmdo..",
        "..ohlmmmddo.",
        "..ollmmdddo.",
        ".olmmmdddo..",
        ".oddmmddo...",
        "..ooooooo...",
        "............",
        "............"],
    "bar": [
        "............",
        "............",
        "............",
        "....ooooooo.",
        "...ohhllllo.",
        "..ohlllllmo.",
        ".oooooooomo.",
        ".ollllllomo.",
        ".ommmmmmdo..",
        ".oooooooo...",
        "............",
        "............"],
    "leaf": [
        "............",
        "........oo..",
        "......oollo.",
        ".....olhlmo.",
        "....olllmdo.",
        "...olllmdo..",
        "..ollmmdo...",
        "..olmmdo....",
        ".oommoo.....",
        ".o.oo.......",
        "o...........",
        "............"],
    "cloth": [
        "............",
        "............",
        "..oooooooo..",
        ".ohllllllmo.",
        ".olmmmmmmdo.",
        ".oooooooooo.",
        ".ohllllllmo.",
        ".olmmmmmmdo.",
        ".oooooooooo.",
        "............",
        "............",
        "............"],
    "gem": [
        "............",
        "............",
        "....oooo....",
        "...ohllmo...",
        "..ohhllmmo..",
        "..oooooooo..",
        "..olllmmdo..",
        "...olmmdo...",
        "....omdo....",
        ".....oo.....",
        "............",
        "............"],
    "book": [
        "............",
        "..ooooooo...",
        "..ommmmmdo..",
        "..omlhlmdo..",
        "..ommmmmdo..",
        "..omllllmo..",
        "..ommmmmdo..",
        "..ommmmmdo..",
        "..ooooooolo.",
        "...ollllllo.",
        "....oooooo..",
        "............"],
    "helm": [
        "............",
        "............",
        "....oooo....",
        "...ohllmo...",
        "..ohllmmdo..",
        "..olmmmmdo..",
        "..ommmmmdo..",
        "..oooddooo..",
        "..om.oo.do..",
        "..oo....oo..",
        "............",
        "............"],
    "mail": [
        "............",
        "..oo....oo..",
        ".ohlo..olmo.",
        ".olloooolmo.",
        ".olmlmlmmdo.",
        "..olmlmmdo..",
        "..ommmmmdo..",
        "..olmlmmdo..",
        "..ommmmmdo..",
        "..oooooooo..",
        "............",
        "............"],
    "key": [
        "............",
        "............",
        "..ooo.......",
        ".ohlmo......",
        ".ol.mooooooo",
        ".ommdolllmmo",
        "..ooo.oo.oo.",
        "............",
        "............",
        "............",
        "............",
        "............"],
    "roll": [
        "............",
        "............",
        "..oooooooo..",
        ".ollllllllo.",
        ".ohmmmmmmlo.",
        ".olmdmdmmlo.",
        ".olmmmmmmlo.",
        ".ollllllllo.",
        "..oooooooo..",
        "............",
        "............",
        "............"],
}

PALETTE = {
    "coins": (238, 196, 72), "sack": (170, 128, 80), "bottle": (200, 80, 80), "food": (196, 140, 80),
    "ore": (150, 120, 100), "bar": (200, 170, 140), "leaf": (110, 180, 80), "cloth": (190, 170, 210),
    "gem": (120, 220, 230), "book": (150, 70, 60), "helm": (170, 170, 180), "mail": (160, 160, 175),
    "key": (220, 190, 90), "roll": (225, 210, 170)}

WEAPON_SPRITE = {"longsword": "w_sword", "shortsword": "w_sword", "greatsword": "w_sword", "dagger": "w_dagger",
                 "knuckles": "w_mallet", "hammer": "w_warhammer", "mace": "w_mallet", "axe": "w_axe",
                 "battleaxe": "w_axe", "spear": "w_spear", "polearm": "w_spear", "bow": "w_bow", "crossbow": "w_bow",
                 "throwing": "w_dagger", "firelock": "w_staff", "staff": "w_staff", "wand": "w_wand"}
TOOL_SPRITE = {"pickaxe": "w_pickaxe", "hatchet": "w_axe"}

_cache = {}


def _shade(col, f):
    return tuple(max(0, min(255, int(c * f))) for c in col)


def _from_template(name, col):
    rows = T[name]
    ramp = {"o": (34, 24, 20), "d": _shade(col, 0.6), "m": col, "l": _shade(col, 1.25), "h": _shade(col, 1.6)}
    s = pygame.Surface((12, 12), pygame.SRCALPHA)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch in ramp:
                s.set_at((x, y), (*ramp[ch], 255))
    return s


def _template_for(data, item):
    if item == "marks":
        return "coins", None
    it = data.item(item)
    t = it["type"]
    ore_col = tuple(data.ores[it["ore"]]["color"]) if it.get("ore") in data.ores else None
    if t == "armor":
        return ("helm" if it.get("slot") == "head" else "mail"), ore_col if it.get("ore") else (150, 110, 70)
    if t == "ore":
        return "ore", ore_col or tuple(data.ores[item[:-4]]["color"]) if item[:-4] in data.ores else None
    if t == "bar":
        return "bar", ore_col or (tuple(data.ores[item[:-4]]["color"]) if item[:-4] in data.ores else None)
    if t in ("drink", "medicine"):
        return "bottle", {"water": (90, 150, 220), "mana_draught": (110, 110, 240), "ale": (200, 150, 60),
                          "bandage": (230, 225, 210), "herbal_salve": (110, 180, 90)}.get(item)
    if t == "food":
        return "food", {"berries": (170, 60, 110), "fish": (130, 160, 190), "kelp": (70, 140, 90),
                        "mushrooms": (190, 150, 120), "meat": (190, 80, 70), "cooked_meat": (150, 80, 50)}.get(item)
    if t == "magic":
        return "gem", {"arcane_dust": (190, 150, 240), "enchanted_ink": (90, 90, 200)}.get(item)
    if t == "valuable":
        return "gem", {"trinket": (230, 190, 90)}.get(item)
    if t in ("book", "recipe"):
        return "book", None
    if t == "key":
        return "key", None
    if t == "material":
        if item in ("herbs", "mirelight_herb", "fiber", "grain"):
            return "leaf", {"mirelight_herb": (120, 200, 210), "grain": (210, 190, 100), "fiber": (170, 190, 110)}.get(item)
        if item in ("cloth", "leather", "hide"):
            return "cloth", {"leather": (150, 100, 60), "hide": (160, 130, 100)}.get(item)
        if item in ("stone", "scrap", "salt"):
            return "ore", {"stone": (150, 150, 150), "salt": (230, 230, 230), "scrap": (140, 130, 120)}.get(item)
        if item in ("wood", "thornwood", "plank"):
            return "roll", {"wood": (160, 115, 70), "thornwood": (120, 70, 70), "plank": (200, 160, 110)}.get(item)
        return "sack", None
    return "sack", None


def icon(data, item, scale=1):
    """A small sprite for an item (12px at scale 1)."""
    key = (item, scale)
    s = _cache.get(key)
    if s is not None:
        return s
    s = None
    if item == "sack_marker":
        s = _from_template("sack", (210, 170, 90))
        _cache[key] = s
        return s
    it = data.item(item) if item != "marks" else None
    spr = None
    if it is not None and it["type"] == "weapon":
        spr = WEAPON_SPRITE.get(it.get("weapon"), "w_sword")
    elif it is not None and it["type"] == "tool":
        spr = TOOL_SPRITE.get(item)
    elif it is not None and it["type"] == "ammo":
        spr = "w_arrow"
    if spr:
        try:
            img = assets.sprite(spr)
        except Exception:
            img = None
        if img is not None:
            w, h = img.get_size()
            f = 14 / max(w, h)
            s = pygame.transform.scale(img, (max(1, int(w * f)), max(1, int(h * f))))
    if s is None:
        name, col = _template_for(data, item)
        s = _from_template(name, col or PALETTE[name])
    if scale != 1:
        s = pygame.transform.scale(s, (s.get_width() * scale, s.get_height() * scale))
    _cache[key] = s
    return s
