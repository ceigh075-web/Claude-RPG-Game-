"""Character statistics, training (learn-by-doing) and derived values. Used for the player and all NPCs."""
import math

from .inventory import Inventory

ATTRIBUTES = ("strength", "speed", "health", "dexterity")
SKILLS = ("unarmed", "melee", "ranged", "blocking", "dodging", "athletics",
          "mining", "gathering", "crafting", "magic", "trading")
STAT_CAP = 100.0
TRAIN_RATE = 0.05

ATTR_DESC = {
    "strength": "Physical damage, carry capacity, heavy weapons.",
    "speed": "Movement and sprint speed, travel pace.",
    "health": "Maximum health and toughness.",
    "dexterity": "Attack speed, accuracy and handling.",
}


class Character:
    def __init__(self, cid, name, race, attributes=None, skills=None, pronouns="they/them", appearance=None):
        self.id = cid
        self.name = name
        self.race = race
        self.pronouns = pronouns
        self.attributes = {a: float((attributes or {}).get(a, 10)) for a in ATTRIBUTES}
        self.skills = {s: float((skills or {}).get(s, 0)) for s in SKILLS}
        self.appearance = appearance or {}
        self.inventory = Inventory()
        self.equipment = {"weapon": None, "ranged": None, "head": None, "body": None}
        self.xp_total = 0.0
        self.food = 80.0
        self.water = 80.0
        self.hp = self.max_hp
        self.mana = self.max_mana
        self.alive = True
        self.modifiers = {}  # temporary {attr: delta} from spells/needs, recomputed by needs.py

    # ------------------------------------------------------------ derived values
    def attr(self, name, race_data=None):
        """Effective attribute including temporary modifiers."""
        v = self.attributes[name] + self.modifiers.get(name, 0.0)
        return max(1.0, v)

    @property
    def max_hp(self):
        return round(40 + self.attributes["health"] * 3)

    @property
    def max_mana(self):
        return round(20 + self.skills["magic"] * 0.8)

    @property
    def carry_capacity(self):
        return round(25 + self.attr("strength") * 1.2, 1)

    @property
    def level(self):
        return 1 + int(math.sqrt(self.xp_total / 40.0))

    def move_speed(self):
        """Pixels per second when walking."""
        s = 62 + self.attr("speed") * 0.9
        if self.encumbrance() > 1.0:
            s *= 0.6
        return s

    def encumbrance(self, data=None):
        """Carried weight / capacity (>1 means overloaded). Needs item data bound via Inventory."""
        w = self.inventory.total_weight()
        return w / max(1.0, self.carry_capacity)

    def armor_value(self, data):
        total = 0.0
        for slot in ("head", "body"):
            item = self.equipment.get(slot)
            if item and self.inventory.has(item):
                total += data.item(item).get("armor", 0.0)
        return total

    # ------------------------------------------------------------ training
    def train(self, name, xp, race_data=None):
        """Increase an attribute or skill by doing. Diminishing returns at higher values."""
        mult = 1.0
        if race_data:
            mult *= race_data.get("xp_mult", 1.0)
            if name == "magic":
                mult *= race_data.get("magic_mult", 1.0)
            if name == "crafting":
                mult *= race_data.get("craft_mult", 1.0)
        table = self.attributes if name in self.attributes else self.skills
        v = table[name]
        gain = xp * TRAIN_RATE * mult / (1 + v / 15.0)
        old_level = self.level
        old_int = int(v)
        table[name] = min(STAT_CAP, v + gain)
        self.xp_total += xp * mult
        return {"stat": name, "gain": gain, "level_up": self.level > old_level,
                "point_up": int(table[name]) > old_int}

    # ------------------------------------------------------------ health
    def damage(self, amount):
        self.hp = max(0.0, self.hp - amount)
        if self.hp <= 0:
            self.alive = False
        return self.hp

    def heal(self, amount):
        self.hp = min(self.max_hp, self.hp + amount)
        if self.hp > 0:
            self.alive = True

    # ------------------------------------------------------------ persistence
    def to_dict(self):
        return {
            "id": self.id, "name": self.name, "race": self.race, "pronouns": self.pronouns,
            "attributes": self.attributes, "skills": self.skills, "appearance": self.appearance,
            "inventory": self.inventory.to_dict(), "equipment": self.equipment,
            "xp_total": self.xp_total, "food": self.food, "water": self.water,
            "hp": self.hp, "mana": self.mana, "alive": self.alive,
        }

    @classmethod
    def from_dict(cls, d, data=None):
        c = cls(d["id"], d["name"], d["race"], d["attributes"], d["skills"], d.get("pronouns", "they/them"),
                d.get("appearance"))
        c.inventory = Inventory.from_dict(d["inventory"], data)
        c.equipment = {"weapon": None, "ranged": None, "head": None, "body": None}
        c.equipment.update(d["equipment"])
        c.xp_total = d["xp_total"]
        c.food, c.water, c.hp, c.mana = d["food"], d["water"], d["hp"], d["mana"]
        c.alive = d.get("alive", True)
        return c


def new_player(name, race, data, appearance=None, pronouns="they/them"):
    """Create the starting player character: weak, poor, with basic supplies."""
    rd = data.races[race]
    attrs = {a: 10 + rd["attribute_mods"].get(a, 0) for a in ATTRIBUTES}
    skills = {s: rd["skill_mods"].get(s, 0) for s in SKILLS}
    c = Character("player", name, race, attrs, skills, pronouns, appearance)
    c.inventory.bind(data)
    for item, qty in (("ration", 3), ("water", 4), ("bandage", 2), ("bread", 1), ("dagger_rustite", 1)):
        c.inventory.add(item, qty)
    c.equipment["weapon"] = "dagger_rustite"  # an old knife: better than bare fists, not by much
    c.hp = c.max_hp
    c.mana = c.max_mana
    return c
