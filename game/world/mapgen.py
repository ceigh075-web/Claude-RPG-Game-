"""Deterministic local map generation for towns, wilderness areas and building interiors.

A location always generates the same layout (seeded by its id). Persistent changes (harvested bushes,
mined veins) are stored separately in GameState.location_states and applied on top.
"""
import math

from ..core.rng import stable_rng

TILE = 16

GROUND, ALT, PATH, WATER, FLOOR_WOOD, FLOOR_STONE, WALL, ROOF, VOID, FIELD, PLAZA = range(11)
SOLID_TILES = {WATER, WALL, ROOF, VOID}

BUILDING_SIZES = {
    "house": (5, 4), "farmhouse": (6, 4), "barn": (6, 5), "inn": (7, 5), "provisioner": (6, 4),
    "armorer": (6, 4), "assayer": (6, 4), "smithy": (6, 4), "forge": (5, 4), "workshop": (6, 4),
    "general_store": (7, 4), "market": (8, 5), "warehouse": (7, 5), "barracks": (8, 5), "palace": (11, 7),
    "temple": (6, 6), "guild_hall": (9, 6), "mage_tower": (5, 7), "enchanter": (5, 4), "apothecary": (5, 4),
    "arena": (9, 6), "longhouse": (9, 5), "shaman_hut": (5, 4), "tannery": (6, 4), "watchtower": (4, 6),
    "scavenger_shop": (6, 4), "chapel": (5, 5), "mine_entrance": (6, 4), "property_for_sale": (5, 4),
}
BUILDING_LABELS = {
    "inn": "Inn", "provisioner": "Provisions", "armorer": "Armorer", "assayer": "Assayer", "smithy": "Smithy",
    "forge": "Forge", "workshop": "Workshop", "general_store": "General Store", "market": "Market Hall",
    "warehouse": "Warehouse", "barracks": "Barracks", "palace": "Palace", "temple": "Temple",
    "guild_hall": "Guild Hall", "mage_tower": "Mage Tower", "enchanter": "Enchanter", "apothecary": "Apothecary",
    "arena": "Fighting Pit", "longhouse": "Longhouse", "shaman_hut": "Shaman's Hut", "tannery": "Tannery",
    "watchtower": "Watchtower", "scavenger_shop": "Scavenger's Den", "chapel": "Chapel",
    "mine_entrance": "Mine", "property_for_sale": "House (for sale)", "house": "House",
    "farmhouse": "Farmhouse", "barn": "Barn",
}
SHOP_BUILDINGS = {"inn", "provisioner", "armorer", "assayer", "smithy", "workshop", "general_store", "market",
                  "enchanter", "apothecary", "tannery", "scavenger_shop"}
ORE_VEIN_COUNT = {"rustite": 9, "greyvein": 6, "sunsilver": 4, "voidglass": 3}
BORDER_OBJECT = {
    "grassland": "tree", "forest": "tree", "hills": "rock", "mountain": "rock", "snow": "pine", "desert": "rock",
    "coast": "rock", "swamp": "dead_tree", "canyon": "rock", "volcanic": "rock", "moor": "rock", "ruins": "tree",
    "crystal": "crystal_spire", "cave": "rock",
}
TREE_KIND = {"snow": "pine", "mountain": "pine", "swamp": "dead_tree", "volcanic": "dead_tree", "moor": "dead_tree",
             "crystal": "crystal_spire", "desert": "cactus", "canyon": "cactus"}


class LocalMap:
    def __init__(self, loc_id, name, w, h, biome, kind, fill=GROUND):
        self.loc_id = loc_id
        self.name = name
        self.w, self.h = w, h
        self.biome = biome
        self.kind = kind  # town | wild | interior
        self.tiles = [[fill] * w for _ in range(h)]
        self.objects = []
        self.exits = []          # {"to": loc_id, "x": tx, "y": ty}
        self.buildings = {}      # id -> building dict (towns)
        self.spawns = []         # {"enemy": id, "x": tx, "y": ty}
        self.npc_spots = []      # (tx, ty) where townsfolk loiter
        self.entry = (w // 2, h // 2)
        self.palette = None
        self.building = None     # for interiors: the building dict
        self._solid = None

    # ---------------------------------------------------------------- tiles
    def inb(self, x, y):
        return 0 <= x < self.w and 0 <= y < self.h

    def get(self, x, y):
        return self.tiles[y][x] if self.inb(x, y) else VOID

    def set(self, x, y, t):
        if self.inb(x, y):
            self.tiles[y][x] = t

    def rect(self, x, y, w, h, t):
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                self.set(xx, yy, t)

    # ---------------------------------------------------------------- objects
    def add(self, kind, x, y, solid=True, **kw):
        o = {"key": f"o{len(self.objects)}", "kind": kind, "x": x, "y": y, "solid": solid}
        o.update(kw)
        self.objects.append(o)
        self._solid = None
        return o

    def occupied(self, x, y):
        return any(o["x"] == x and o["y"] == y for o in self.objects)

    def build_solid_grid(self, removed=()):
        grid = [[self.tiles[y][x] in SOLID_TILES for x in range(self.w)] for y in range(self.h)]
        for o in self.objects:
            if o["solid"] and o["key"] not in removed:
                grid[o["y"]][o["x"]] = True
        self._solid = grid
        return grid

    def solid(self, x, y):
        if not self.inb(x, y):
            return True
        if self._solid is None:
            self.build_solid_grid()
        return self._solid[y][x]

    def free_for_object(self, x, y, margin_path=True):
        if not self.inb(x, y) or self.get(x, y) in SOLID_TILES or self.occupied(x, y):
            return False
        if margin_path and self.get(x, y) in (PATH, PLAZA, FIELD, FLOOR_WOOD, FLOOR_STONE):
            return False
        return True

    def find_open_near(self, x, y, radius=6):
        for r in range(radius + 1):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    nx, ny = x + dx, y + dy
                    if self.inb(nx, ny) and not self.solid(nx, ny):
                        return nx, ny
        return x, y


# ===================================================================== helpers
def _edge_point(m, d):
    """Where a ray from the centre in direction d leaves the map (one tile inside the border)."""
    cx, cy = m.w / 2, m.h / 2
    dx, dy = d
    tx = (cx - 1) / abs(dx) if abs(dx) > 1e-6 else 1e9
    ty = (cy - 1) / abs(dy) if abs(dy) > 1e-6 else 1e9
    t = min(tx, ty)
    x = int(round(cx + dx * t))
    y = int(round(cy + dy * t))
    return max(0, min(m.w - 1, x)), max(0, min(m.h - 1, y))


def _draw_path(m, a, b, width=2, tile=PATH, protect=(WALL, ROOF, WATER)):
    (x1, y1), (x2, y2) = a, b
    # L-shaped: horizontal first, then vertical, with width
    step = 1 if x2 >= x1 else -1
    for x in range(x1, x2 + step, step):
        for k in range(width):
            if m.get(x, y1 + k) not in protect:
                m.set(x, y1 + k, tile)
    step = 1 if y2 >= y1 else -1
    for y in range(y1, y2 + step, step):
        for k in range(width):
            if m.get(x2 + k, y) not in protect:
                m.set(x2 + k, y, tile)


def _make_exits(m, world, loc_id, rng, width=2):
    cx, cy = m.w // 2, m.h // 2
    for n in world.neighbors(loc_id):
        d = world.direction(loc_id, n)
        ex, ey = _edge_point(m, d)
        # snap to an actual border
        if min(ex, m.w - 1 - ex) <= min(ey, m.h - 1 - ey):
            ex = 0 if ex < m.w / 2 else m.w - 1
            ey = max(3, min(m.h - 4, ey))
        else:
            ey = 0 if ey < m.h / 2 else m.h - 1
            ex = max(3, min(m.w - 4, ex))
        # avoid two exits on the same spot
        for other in m.exits:
            if abs(other["x"] - ex) + abs(other["y"] - ey) < 5:
                if ex in (0, m.w - 1):
                    ey = min(m.h - 4, ey + 6)
                else:
                    ex = min(m.w - 4, ex + 6)
        m.exits.append({"to": n, "x": ex, "y": ey})
        _draw_path(m, (cx, cy), (ex, ey), width=width)


def _coast(m, depth=7):
    """Put the sea along the map side that has no exits."""
    used = set()
    for e in m.exits:
        used.add("w" if e["x"] == 0 else "e" if e["x"] == m.w - 1 else "n" if e["y"] == 0 else "s")
    side = next((sd for sd in ("e", "w", "s", "n") if sd not in used), None)
    if side == "e":
        m.rect(m.w - depth, 0, depth, m.h, WATER)
    elif side == "w":
        m.rect(0, 0, depth, m.h, WATER)
    elif side == "s":
        m.rect(0, m.h - depth, m.w, depth, WATER)
    elif side == "n":
        m.rect(0, 0, m.w, depth, WATER)


def _clear_exits(m):
    """Guarantee every exit (and a little room around it) is walkable."""
    for e in m.exits:
        for dy in range(-1, 3):
            for dx in range(-1, 3):
                if m.get(e["x"] + dx, e["y"] + dy) in SOLID_TILES:
                    m.set(e["x"] + dx, e["y"] + dy, PATH)


def _border(m, kind, rng):
    exit_cells = set()
    for e in m.exits:
        for dx in range(-2, 4):
            for dy in range(-2, 4):
                exit_cells.add((e["x"] + dx, e["y"] + dy))
    for x in range(m.w):
        for y in (0, m.h - 1):
            if (x, y) not in exit_cells and not m.occupied(x, y):
                m.add(kind, x, y, variant=rng.randint(0, 3))
    for y in range(1, m.h - 1):
        for x in (0, m.w - 1):
            if (x, y) not in exit_cells and not m.occupied(x, y):
                m.add(kind, x, y, variant=rng.randint(0, 3))


def _blob(m, cx, cy, r, tile, rng):
    for y in range(cy - r - 1, cy + r + 2):
        for x in range(cx - r - 1, cx + r + 2):
            if math.hypot(x - cx, (y - cy) * 1.2) <= r + rng.uniform(-0.6, 0.6):
                m.set(x, y, tile)


def _scatter(m, count, rng, fn, avoid_center=4, tries=40):
    placed = 0
    for _ in range(count * tries):
        if placed >= count:
            break
        x, y = rng.randint(2, m.w - 3), rng.randint(2, m.h - 3)
        if abs(x - m.w // 2) < avoid_center and abs(y - m.h // 2) < avoid_center:
            continue
        if m.free_for_object(x, y):
            fn(x, y)
            placed += 1
    return placed


# ===================================================================== towns
def generate_town(data, world, loc_id):
    t = data.towns[loc_id]
    rng = stable_rng("town", loc_id)
    m = LocalMap(loc_id, t["name"], 58, 42, t["biome"], "town")
    m.palette = t.get("palette")
    for _ in range(14):
        _blob(m, rng.randint(3, m.w - 4), rng.randint(3, m.h - 4), rng.randint(1, 3), ALT, rng)
    if t["biome"] == "coast" or "docks" in t["buildings"]:
        m.rect(0, 0, 5, m.h, WATER)
    _make_exits(m, world, loc_id, rng, width=2)
    cx, cy = m.w // 2, m.h // 2
    m.rect(cx - 4, cy - 3, 9, 7, PLAZA)
    m.add("well", cx, cy, solid=True)
    m.entry = (cx, cy + 2)
    for dx, dy in ((-3, -2), (3, -2), (-3, 2), (3, 2), (0, -2), (-2, 1), (2, 1)):
        m.npc_spots.append((cx + dx, cy + dy))
    # buildings
    placed = []
    types = [b for b in t["buildings"] if b not in ("well", "bounty_board", "docks")]
    for i, btype in enumerate(types):
        bw, bh = BUILDING_SIZES.get(btype, (5, 4))
        for attempt in range(400):
            radius = 6 + attempt // 12
            bx = cx + rng.randint(-radius - bw, radius)
            by = cy + rng.randint(-radius - bh, radius)
            if bx < 6 or by < 2 or bx + bw > m.w - 3 or by + bh > m.h - 4:
                continue
            ok = True
            for yy in range(by - 1, by + bh + 2):
                for xx in range(bx - 1, bx + bw + 1):
                    if m.get(xx, yy) in (PATH, PLAZA, WALL, ROOF, WATER, FIELD) or m.occupied(xx, yy):
                        ok = False
                        break
                if not ok:
                    break
            if not ok:
                continue
            bid = f"b{i}"
            m.rect(bx, by, bw, bh - 2, ROOF)
            m.rect(bx, by + bh - 2, bw, 2, WALL)
            door = (bx + bw // 2, by + bh - 1)
            b = {"id": bid, "type": btype, "x": bx, "y": by, "w": bw, "h": bh, "door": door,
                 "label": BUILDING_LABELS.get(btype, btype.title()),
                 "shop": btype if btype in SHOP_BUILDINGS else None}
            m.buildings[bid] = b
            m.add("door", door[0], door[1], solid=False, building=bid)
            _draw_path(m, (door[0], door[1] + 1), (cx, door[1] + 1 if abs(door[1] + 1 - cy) < 2 else cy), width=1)
            m.npc_spots.append((door[0] + 1, door[1] + 2))
            placed.append(b)
            break
    # town-specific details
    if "bounty_board" in t["buildings"]:
        m.add("bounty_board", cx + 4, cy - 3, solid=True)
    if t["specialty"] == "farming":
        for k in range(3):
            fx, fy = rng.randint(6, m.w - 14), rng.randint(4, m.h - 10)
            if all(m.get(x, y) == GROUND or m.get(x, y) == ALT for x in range(fx, fx + 8) for y in range(fy, fy + 5)):
                m.rect(fx, fy, 8, 5, FIELD)
                for yy in range(fy, fy + 5, 2):
                    for xx in range(fx, fx + 8):
                        m.add("crop", xx, yy, solid=False, variant=rng.randint(0, 2))
    # decoration
    _scatter(m, 18, rng, lambda x, y: m.add(TREE_KIND.get(t["biome"], "tree"), x, y, variant=rng.randint(0, 3)), avoid_center=10)
    _scatter(m, 10, rng, lambda x, y: m.add("barrel" if rng.random() < 0.5 else "crate", x, y), avoid_center=5)
    _clear_exits(m)
    _border(m, "palisade" if t["biome"] != "coast" else "fence", rng)
    return m


# ===================================================================== wilderness
def generate_wild(data, world, loc_id):
    w = data.wilderness[loc_id]
    rng = stable_rng("wild", loc_id)
    biome = w["biome"]
    res = w["resources"]
    if biome == "cave":
        m = LocalMap(loc_id, w["name"], 56, 40, biome, "wild", fill=VOID)
        _carve_cave(m, rng)
        _make_exits(m, world, loc_id, rng, width=3)
        for e in m.exits:
            m.rect(e["x"] - 1, e["y"] - 1, 3, 3, GROUND)
    else:
        m = LocalMap(loc_id, w["name"], 64, 46, biome, "wild")
        for _ in range(18):
            _blob(m, rng.randint(3, m.w - 4), rng.randint(3, m.h - 4), rng.randint(1, 4), ALT, rng)
        if res.get("water"):
            px, py = rng.choice([(m.w // 4, m.h // 3), (3 * m.w // 4, 2 * m.h // 3), (m.w // 3, 3 * m.h // 4)])
            _blob(m, px, py, rng.randint(3, 5), WATER, rng)
        _make_exits(m, world, loc_id, rng, width=2)
        if biome == "coast":
            _coast(m)
    cx, cy = m.w // 2, m.h // 2
    m.entry = m.find_open_near(cx, cy)
    tree = TREE_KIND.get(biome, "tree")
    density = {"forest": 70, "grassland": 18, "hills": 14, "swamp": 30, "moor": 12, "snow": 22, "ruins": 20,
               "coast": 10, "mountain": 12, "crystal": 16, "desert": 8, "canyon": 8, "volcanic": 10, "cave": 0}[biome]
    density += res.get("wood", 0) * 8 if biome != "cave" else 0
    _scatter(m, density, rng, lambda x, y: m.add(tree, x, y, variant=rng.randint(0, 3), choppable=res.get("wood", 0) > 0))
    rocks = {"hills": 25, "mountain": 40, "canyon": 35, "volcanic": 30, "cave": 25, "desert": 12, "snow": 15}.get(biome, 8)
    _scatter(m, rocks, rng, lambda x, y: m.add("rock", x, y, variant=rng.randint(0, 3)))
    # forage bushes
    if res.get("forage"):
        _scatter(m, 6 + 3 * len(res["forage"]), rng,
                 lambda x, y: m.add("bush", x, y, solid=False, yields=rng.choice(res["forage"]), harvest=True))
    # ore veins in clusters
    for ore in res.get("ores", []):
        n = ORE_VEIN_COUNT[ore]
        for _ in range(max(1, n // 3)):
            ccx, ccy = rng.randint(6, m.w - 7), rng.randint(5, m.h - 6)
            k = 0
            for _ in range(60):
                if k >= 3:
                    break
                x, y = ccx + rng.randint(-3, 3), ccy + rng.randint(-3, 3)
                if m.free_for_object(x, y) and not (abs(x - cx) < 3 and abs(y - cy) < 3):
                    m.add("ore_vein", x, y, ore=ore, charges=3, harvest=True)
                    k += 1
    if res.get("crystals"):
        _scatter(m, 5, rng, lambda x, y: m.add("mana_crystal_node", x, y, charges=2, harvest=True))
    if res.get("scavenge", 0):
        _scatter(m, res["scavenge"] * 3, rng, lambda x, y: m.add("scavenge", x, y, solid=False, harvest=True))
    # landmarks for each feature
    for i, feat in enumerate(w.get("features", [])):
        x, y = m.find_open_near(rng.randint(8, m.w - 9), rng.randint(6, m.h - 7), 8)
        if not m.free_for_object(x, y):
            continue
        m.add("landmark", x, y, feature=feat, label=feat.replace("_", " ").title())
    # NPC camp spots
    for npc_id in w.get("npcs", []):
        x, y = m.find_open_near(cx + rng.randint(-8, 8), cy + rng.randint(-6, 6), 8)
        if m.free_for_object(x, y, margin_path=False):
            m.add("campfire", x, y, solid=True)
            m.npc_spots.append((x + 1, y))
    # enemy spawn points (used by combat in Phase 3)
    for i, enemy in enumerate(w.get("enemies", [])):
        x, y = rng.randint(5, m.w - 6), rng.randint(4, m.h - 5)
        if abs(x - cx) + abs(y - cy) > 14:
            m.spawns.append({"enemy": enemy, "x": x, "y": y})
    _clear_exits(m)
    _border(m, BORDER_OBJECT.get(biome, "tree"), rng)
    return m


def _carve_cave(m, rng):
    x, y = m.w // 2, m.h // 2
    for _ in range(2600):
        m.rect(x - 1, y - 1, 3, 3, GROUND)
        dx, dy = rng.choice(((1, 0), (-1, 0), (0, 1), (0, -1)))
        x = max(3, min(m.w - 4, x + dx * 2))
        y = max(3, min(m.h - 4, y + dy * 2))
    for _ in range(6):
        _blob(m, rng.randint(6, m.w - 7), rng.randint(5, m.h - 6), rng.randint(3, 5), GROUND, rng)


# ===================================================================== interiors
INTERIOR_SIZES = {"palace": (20, 13), "inn": (15, 11), "market": (16, 11), "guild_hall": (16, 11),
                  "barracks": (16, 10), "arena": (18, 13), "longhouse": (16, 9), "mine_entrance": (40, 28),
                  "temple": (12, 12), "mage_tower": (11, 11)}


def generate_interior(data, loc_id, building):
    rng = stable_rng("interior", loc_id, building["id"])
    btype = building["type"]
    if btype == "mine_entrance":
        return _generate_mine(data, loc_id, building, rng)
    w, h = INTERIOR_SIZES.get(btype, (12, 9))
    m = LocalMap(loc_id, building["label"], w, h, "interior", "interior", fill=FLOOR_WOOD)
    m.building = building
    if btype in ("palace", "temple", "barracks", "guild_hall", "mage_tower", "chapel", "arena"):
        m.rect(0, 0, w, h, FLOOR_STONE)
    m.rect(0, 0, w, 2, WALL)
    for y in range(h):
        m.set(0, y, VOID)
        m.set(w - 1, y, VOID)
    m.rect(0, h - 1, w, 1, VOID)
    ex = w // 2
    m.set(ex, h - 1, FLOOR_WOOD)
    m.add("exit_door", ex, h - 1, solid=False)
    m.entry = (ex, h - 2)
    if building.get("shop"):
        for x in range(2, w - 2):
            if x != w // 2 + 2:
                m.add("counter", x, 4, solid=True)
        m.npc_spots.append((w // 2, 3))  # shopkeeper stands behind the counter
        m.add("shelf", 2, 2, solid=True)
        m.add("shelf", w - 3, 2, solid=True)
    if btype in ("inn", "house", "farmhouse", "property_for_sale", "barracks", "longhouse"):
        beds = 4 if btype in ("inn", "barracks", "longhouse") else 1
        for i in range(beds):
            bx = 2 + i * 3 if btype != "inn" else w - 3 - i * 3
            by = h - 4 if btype == "inn" else 3
            if not m.occupied(bx, by) and bx > 0:
                m.add("bed", bx, by, solid=True)
    if btype in ("inn", "longhouse", "palace", "guild_hall"):
        for i in range(3):
            m.add("table", 3 + i * 3, 7 if h > 9 else 6, solid=True)
            m.npc_spots.append((3 + i * 3, 8 if h > 9 else 7))
    if btype in ("smithy", "forge"):
        m.add("anvil", w - 4, 6, solid=True)
        m.add("furnace", w - 3, 2, solid=True)
    if btype in ("mage_tower", "enchanter", "temple", "chapel"):
        m.add("bookshelf", 2, 2, solid=True)
        m.add("bookshelf", 3, 2, solid=True)
    stations = STATIONS_BY_BUILDING.get(btype, ())
    for kind in stations:
        _place_free(m, kind)
    for _ in range(3):
        x, y = rng.randint(1, w - 2), rng.randint(2, h - 3)
        if m.free_for_object(x, y, margin_path=False) and (x, y) != m.entry and y != 5:
            m.add(rng.choice(("barrel", "crate")), x, y)
    m.npc_spots += [(2 + rng.randint(0, w - 5), 6 + rng.randint(0, max(0, h - 9))) for _ in range(3)]
    return m


STATIONS_BY_BUILDING = {
    "workshop": ("workbench",), "tannery": ("workbench",), "inn": ("stove",), "house": ("stove",),
    "farmhouse": ("stove",), "longhouse": ("stove", "workbench"), "barracks": ("training_dummy", "stove"),
    "apothecary": ("alchemy_table",), "mage_tower": ("alchemy_table", "scribing_table"),
    "enchanter": ("alchemy_table", "scribing_table"), "shaman_hut": ("alchemy_table",),
    "temple": ("scribing_table",), "chapel": ("scribing_table",), "guild_hall": ("anvil", "furnace", "workbench"),
    "arena": ("training_dummy", "training_dummy"), "forge": ("workbench",),
}


def _place_free(m, kind):
    """Put a station against the back wall (row 2) or the first free interior tile."""
    candidates = [(x, 2) for x in range(2, m.w - 2)] + [(x, y) for y in range(6, m.h - 2) for x in (1, m.w - 2)]
    for x, y in candidates:
        if m.free_for_object(x, y, margin_path=False) and (x, y) != m.entry and abs(x - m.w // 2) > 0:
            m.add(kind, x, y, solid=True)
            return True
    return False


def _generate_mine(data, loc_id, building, rng):
    m = LocalMap(loc_id, building["label"], 40, 28, "cave", "interior", fill=VOID)
    m.building = building
    x, y = m.w // 2, m.h - 3
    for _ in range(1400):
        m.rect(x - 1, y - 1, 3, 3, GROUND)
        dx, dy = rng.choice(((1, 0), (-1, 0), (0, -1), (0, -1), (0, 1)))
        x = max(3, min(m.w - 4, x + dx * 2))
        y = max(3, min(m.h - 4, y + dy * 2))
    ex = m.w // 2
    m.rect(ex - 1, m.h - 3, 3, 3, GROUND)
    m.set(ex, m.h - 1, GROUND)
    m.add("exit_door", ex, m.h - 1, solid=False)
    m.entry = (ex, m.h - 3)
    ores = ["rustite"] * 4 + ["greyvein"] * 2
    for i in range(22):
        for _ in range(80):
            vx, vy = rng.randint(2, m.w - 3), rng.randint(2, m.h - 5)
            if m.get(vx, vy) == GROUND and not m.occupied(vx, vy) and any(
                    m.get(vx + a, vy + b) == VOID for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                m.add("ore_vein", vx, vy, ore=rng.choice(ores), charges=3, harvest=True)
                break
    for _ in range(4):
        vx, vy = m.find_open_near(rng.randint(4, m.w - 5), rng.randint(4, m.h - 6), 5)
        if not m.occupied(vx, vy) and (vx, vy) != m.entry:
            m.add("lantern", vx, vy, solid=True)
    return m


ARENA_BIOME = {"road": "grassland"}


def generate_arena(data, terrain, seed):
    """A small open battlefield for fights that happen on the road during travel.
    The left and right edges are open: walking off either side means fleeing."""
    rng = stable_rng("arena", terrain, seed)
    biome = ARENA_BIOME.get(terrain, terrain)
    m = LocalMap("arena", "On the road", 40, 23, biome, "arena")
    for _ in range(8):
        _blob(m, rng.randint(3, m.w - 4), rng.randint(3, m.h - 4), rng.randint(1, 3), ALT, rng)
    m.rect(0, m.h // 2 - 1, m.w, 2, PATH)
    tree = TREE_KIND.get(biome, "tree")
    _scatter(m, 9, rng, lambda x, y: m.add(tree, x, y, variant=rng.randint(0, 3)), avoid_center=6)
    _scatter(m, 7, rng, lambda x, y: m.add("rock", x, y, variant=rng.randint(0, 3)), avoid_center=6)
    border = BORDER_OBJECT.get(biome, "tree")
    for x in range(m.w):
        for y in (0, m.h - 1):
            if not m.occupied(x, y):
                m.add(border, x, y, variant=rng.randint(0, 3))
    m.exits = [{"to": "flee_west", "x": 0, "y": m.h // 2}, {"to": "flee_east", "x": m.w - 1, "y": m.h // 2}]
    m.entry = (8, m.h // 2)
    return m


def generate(data, world, loc_id):
    if loc_id in data.towns:
        return generate_town(data, world, loc_id)
    return generate_wild(data, world, loc_id)
