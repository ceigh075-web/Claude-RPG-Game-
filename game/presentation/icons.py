"""Icons for items, elements, spells, stats and actions.

Interface icons come from one 32x32 fantasy icon sheet (assets/icons/fantasy_icons.png, see ASSETS.md), so
every menu speaks the same visual language. Ore-tier gear is recoloured to its metal. Dropped loot in the
world uses the same icons reduced to world pixel density. A few small hand-drawn templates remain for things
the sheet doesn't have (they share its outline-and-shading style).

Each template is a 12x12 grid: '.' empty, 'o' outline, 'd' dark, 'm' mid, 'l' light, 'h' highlight.
"""
import os

import pygame

from . import assets
from ..core.paths import BUNDLE_ROOT

SHEET = os.path.join(BUNDLE_ROOT, "assets", "icons", "fantasy_icons.png")
CELL = 32

# (row, col) on the sheet
ITEM_CELL = {
    "marks": (12, 10), "ration": (15, 3), "bread": (14, 13), "berries": (14, 5), "mushrooms": (14, 12),
    "fish": (16, 3), "meat": (15, 1), "cooked_meat": (15, 0), "kelp": (11, 13), "water": (15, 8), "ale": (15, 14),
    "mana_draught": (9, 1), "bandage": (9, 15), "herbal_salve": (9, 2), "grain": (14, 7), "herbs": (11, 13),
    "mirelight_herb": (11, 15), "fiber": (17, 5), "wood": (17, 0), "thornwood": (17, 0), "stone": (17, 1),
    "leather": (17, 8), "hide": (17, 8), "salt": (15, 10), "scrap": (10, 14), "cloth": (17, 7), "plank": (17, 0),
    "nails": (10, 4), "mana_crystal": (12, 14), "arcane_dust": (12, 13), "enchanted_ink": (9, 14),
    "relic_shard": (11, 0), "trinket": (8, 6), "spire_core": (18, 4), "arrow": (6, 3), "bolt": (6, 4),
    "powder_shot": (10, 12), "pickaxe": (10, 2), "hatchet": (10, 1), "bedroll": (4, 3), "house_deed": (11, 9),
    "voidglass_manual": (13, 6), "stone_block": (17, 1), "seed_grain": (12, 1), "seed_herb": (12, 3), "old_book": (13, 5), "leather_cap": (7, 2), "leather_jerkin": (7, 6),
    "starfall_blade": (5, 2), "skyglass_bow": (6, 3), "emberheart_hammer": (10, 4),
}
ITEM_TINT = {"kelp": (60, 140, 110), "thornwood": (120, 60, 60), "plank": (200, 160, 110), "stone_block": (170, 160, 140)}
WEAPON_CELL = {"longsword": (5, 1), "greatsword": (5, 2), "shortsword": (5, 4), "dagger": (5, 6), "throwing": (5, 7),
               "axe": (5, 10), "battleaxe": (5, 11), "mace": (5, 13), "hammer": (10, 4), "knuckles": (5, 15),
               "spear": (10, 6), "polearm": (10, 6), "bow": (6, 3), "crossbow": (6, 4), "firelock": (10, 7),
               "staff": (6, 7), "wand": (6, 8)}
ARMOR_CELL = {("head", "rustite"): (7, 1), ("head", "greyvein"): (7, 3), ("head", "sunsilver"): (7, 3),
              ("head", "voidglass"): (7, 1), ("body", "rustite"): (7, 4), ("body", "greyvein"): (7, 5),
              ("body", "sunsilver"): (7, 7), ("body", "voidglass"): (7, 7)}
ORE_CELL = {"rustite": (17, 2), "greyvein": (17, 2), "sunsilver": (17, 3), "voidglass": (17, 4)}
ELEMENT_CELL = {"fire": (3, 9), "water": (0, 10), "earth": (3, 13), "air": (3, 12), "light": (3, 15)}
SUB_CELL = {"magma": (0, 9), "plasma": (18, 4), "ash": (4, 2), "ice": (12, 14), "steam": (0, 10), "blood": (3, 0),
            "poison": (0, 1), "metal": (3, 7), "crystal": (12, 15), "sand": (15, 10), "nature": (11, 13),
            "gravity": (3, 14), "wind": (3, 12), "lightning": (3, 2), "sound": (11, 8), "radiance": (3, 15),
            "light": (3, 15), "mending": (3, 5), "sanctuary": (3, 8)}
EFFECT_CELL = {"damage": (3, 1), "heal": (3, 5), "strength": (1, 4), "speed": (2, 2), "dexterity": (3, 3),
               "health": (1, 0), "defense": (3, 8), "knockback": (3, 11), "root": (0, 8), "affliction": (0, 4)}
STAT_CELL = {"strength": (1, 4), "speed": (2, 2), "health": (1, 0), "dexterity": (3, 3), "magic": (4, 7),
             "mana": (18, 1), "food": (15, 2), "water": (15, 8), "gold": (12, 10), "armor": (3, 8), "level": (2, 0),
             "trading": (12, 12), "mining": (4, 5), "woodcutting": (4, 6), "smithing": (4, 4), "blocking": (6, 2),
             "dodging": (0, 5), "archery": (6, 3), "alchemy": (11, 12), "cooking": (4, 2), "stealth": (4, 8),
             "unarmed": (5, 15), "melee": (5, 1), "ranged": (6, 3), "athletics": (8, 3), "gathering": (11, 13),
             "crafting": (4, 4)}
ACTION_CELL = {"talk": (4, 0), "trade": (12, 12), "attack": (3, 1), "steal": (4, 8), "forge": (4, 4),
               "mine": (4, 5), "chop": (4, 6), "spellbook": (4, 7), "campfire": (4, 2), "camp": (4, 3),
               "quest": (13, 11), "map": (13, 12), "journal": (13, 10), "inventory": (10, 0), "party": (4, 1),
               "gift": (8, 5), "prisoner": (11, 2), "look": (11, 1), "guide": (13, 8), "save": (11, 11),
               "pause": (10, 15), "relationship": (0, 6), "join": (4, 1), "bye": (4, 1), "loot": (11, 11),
               "money": (12, 6), "boss": (0, 0), "house": (11, 9), "farm": (12, 5), "research": (13, 8), "duel": (5, 9)}

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


_sheet = None


def _sheet_img():
    global _sheet
    if _sheet is None:
        try:
            _sheet = pygame.image.load(SHEET)
            if pygame.display.get_surface() is not None:
                _sheet = _sheet.convert_alpha()
        except (pygame.error, FileNotFoundError):
            _sheet = False
    return _sheet


def cell(rc, tint=None):
    """A 32x32 icon from the sheet (optionally recoloured), or None if the sheet is missing."""
    key = ("cell", rc, tint)
    s = _cache.get(key)
    if s is None:
        sh = _sheet_img()
        if not sh:
            return None
        s = sh.subsurface((rc[1] * CELL, rc[0] * CELL, CELL, CELL)).copy()
        if tint:
            s = recolor(s, tint)
        _cache[key] = s
    return s


def recolor(img, col):
    """Move an icon's colourful pixels onto `col`, keeping their light and shade (outlines and greys stay)."""
    import colorsys
    out = img.copy()
    th, _, ts = colorsys.rgb_to_hls(*(c / 255 for c in col))
    w, h = out.get_size()
    out.lock()
    for y in range(h):
        for x in range(w):
            r, g, b, a = out.get_at((x, y))
            if a == 0:
                continue
            hh, ll, ss = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
            if ss < 0.12 or ll < 0.12:
                continue
            nr, ng, nb = colorsys.hls_to_rgb(th, ll, max(ts * 0.9, 0.15) if ts > 0.05 else 0.0)
            out.set_at((x, y), (int(nr * 255), int(ng * 255), int(nb * 255), a))
    out.unlock()
    return out


def world(img, size=16):
    """Reduce a 32px icon to world pixel density: averaged colour, crisp alpha, dark 1px outline restored."""
    key = ("world", id(img), size)
    s = _cache.get(key)
    if s is None:
        small = pygame.transform.smoothscale(img, (size, size))
        s = pygame.Surface((size, size), pygame.SRCALPHA)
        for y in range(size):
            for x in range(size):
                r, g, b, a = small.get_at((x, y))
                if a >= 110:
                    f = 255 / a if a < 255 else 1
                    s.set_at((x, y), (min(255, int(r * f)), min(255, int(g * f)), min(255, int(b * f)), 255))
        mask = pygame.mask.from_surface(s)
        for x, y in mask.outline():
            r, g, b, _ = s.get_at((x, y))
            s.set_at((x, y), (r // 3, g // 3, b // 3, 255))
        _cache[key] = s
    return s


def item_cell(data, item):
    """(row, col, tint) for an item, or None when the sheet has nothing suitable."""
    if item in ITEM_TINT:
        return ITEM_CELL[item], ITEM_TINT[item]
    if item in ITEM_CELL:
        return ITEM_CELL[item], None
    it = data.item(item)
    ore = it.get("ore")
    tint = tuple(data.ores[ore]["color"]) if ore in data.ores and ore != "rustite" else None
    t = it["type"]
    if t == "weapon" and it.get("weapon") in WEAPON_CELL:
        return WEAPON_CELL[it["weapon"]], tint
    if t == "armor":
        rc = ARMOR_CELL.get((it.get("slot", "body"), ore))
        if rc:
            return rc, tint if ore in ("voidglass",) else None
    if t == "ore" and item.endswith("_ore") and item[:-4] in data.ores:
        o = item[:-4]
        return ORE_CELL.get(o, (17, 2)), tuple(data.ores[o]["color"]) if o in ("rustite", "greyvein") else None
    if t == "bar" and item.endswith("_bar") and item[:-4] in data.ores:
        o = item[:-4]
        return (17, 3), tuple(data.ores[o]["color"]) if o != "sunsilver" else None
    return None


def ui_icon(data, item):
    """32px interface icon for an item."""
    if item == "marks":
        return cell(ITEM_CELL["marks"])
    found = item_cell(data, item)
    if found:
        img = cell(*found)
        if img is not None:
            return img
    small = icon(data, item, 1, prefer_sheet=False)
    return pygame.transform.scale(small, (small.get_width() * 2, small.get_height() * 2))


def named(table, key):
    """32px icon for an element / sub-element / effect / stat / action name, or None."""
    rc = table.get(key) if key is not None else None
    return cell(rc) if rc else None


def element_icon(data, spell):
    """The icon for a spell's source: its sub-element if it has one, else its element."""
    sub = spell.get("sub") if isinstance(spell, dict) else None
    el = spell.get("element") if isinstance(spell, dict) else spell
    return named(SUB_CELL, sub) if sub else named(ELEMENT_CELL, el)


def icon(data, item, scale=1, prefer_sheet=True):
    """A small world-scale sprite for an item (about 12-16 px at scale 1)."""
    key = (item, scale, prefer_sheet)
    s = _cache.get(key)
    if s is not None:
        return s
    s = None
    if prefer_sheet and item != "sack_marker":
        found = (ITEM_CELL["marks"], None) if item == "marks" else item_cell(data, item)
        if found:
            big = cell(*found)
            if big is not None:
                s = world(big, 16)
                if scale != 1:
                    s = pygame.transform.scale(s, (16 * scale, 16 * scale))
                _cache[key] = s
                return s
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
