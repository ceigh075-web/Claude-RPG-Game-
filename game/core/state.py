"""GameState: everything that is saved. Owned by the Game; mutated only through Set System functions."""
from .clock import GameClock
from .rng import GameRNG
from ..set_ai.memory import MemoryStore
from ..set_system import factions
from ..set_system.spells import starter_spellbook
from ..set_system.stats import Character, new_player

START_LOCATION = "brackenford"
START_GOLD = 25
LOG_LIMIT = 60


class GameState:
    def __init__(self, data):
        self.data = data
        self.rng = GameRNG()
        self.clock = GameClock()
        self.player = None
        self.gold = START_GOLD
        self.location = START_LOCATION
        self.local_pos = None          # (x, y) pixel position inside the current location map
        self.sub_location = None       # building interior key, or None when outdoors
        self.mode = "local"            # "local" | "travel"
        self.travel = None             # dict while travelling (see world/travel.py)
        self.discovered = {START_LOCATION}
        self.location_states = {}
        self.reputation = {}
        self.faction_relations = {}
        self.flags = {}
        self.settings = {"pace": "steady", "rations": "normal", "weapon_mode": "melee"}
        self.spellbook = starter_spellbook()   # permanently inscribed spells (first 4 are hotkeyed)
        self.spell_drafts = []                 # created but not yet inscribed spells
        self.known_recipes = []                # gated recipe families learned (e.g. "voidglass")
        self.relationships = {}                # npc_id -> relationship record (set_system/relationships.py)
        self.favors = {}                       # favor_id -> {"status", "started", "npc"}
        self.companions = {}                   # npc_id -> {"char": Character, "task", "active", "joined", "wait_at"}
        self.bonds = {}                        # "a|b" -> {"value", "status"} between companions
        self.property = {}                     # town_id -> owned house info (Phase 8)
        self.base = {}                         # outpost state (Phase 8)
        self.world = {"active_events": [], "modifiers": [], "history_days": []}  # world simulation (Phase 7)
        self.jobs = []                         # accepted jobs/bounties (Phase 7)
        self.stats = {"km_travelled": 0.0, "days": 0}
        self.log = []
        self.memory = MemoryStore()

    # ---------------------------------------------------------------- creation
    @classmethod
    def new_game(cls, data, name, race, appearance=None, pronouns="they/them", seed=None):
        s = cls(data)
        s.rng = GameRNG(seed)
        s.player = new_player(name, race, data, appearance, pronouns)
        s.reputation = factions.init_reputation(data)
        s.faction_relations = factions.init_relations(data)
        s.memory.record("player", "arrival", f"{name} arrived in Brackenford with almost nothing.",
                        day=s.clock.day_index, minute=s.clock.total_minutes % 1440, importance=3,
                        location=START_LOCATION)
        s.add_log(f"You arrive in Brackenford with {START_GOLD} marks and the clothes on your back.")
        return s

    # ---------------------------------------------------------------- helpers
    def location_state(self, loc_id):
        return self.location_states.setdefault(loc_id, {})

    def add_log(self, text):
        self.log.append({"t": self.clock.time_str(), "text": text})
        if len(self.log) > LOG_LIMIT:
            del self.log[: len(self.log) - LOG_LIMIT]

    def discover(self, loc_id):
        if loc_id not in self.discovered:
            self.discovered.add(loc_id)
            self.memory.record("player", "discovery", f"Discovered {self.data.location(loc_id)['name']}.",
                               day=self.clock.day_index, minute=self.clock.total_minutes % 1440,
                               importance=2, location=loc_id)
            return True
        return False

    @property
    def race_data(self):
        return self.data.races[self.player.race]

    # ---------------------------------------------------------------- persistence
    def to_dict(self):
        return {
            "rng": self.rng.to_dict(), "clock": self.clock.to_dict(), "player": self.player.to_dict(),
            "gold": self.gold, "location": self.location, "local_pos": self.local_pos,
            "sub_location": self.sub_location, "mode": self.mode, "travel": self.travel,
            "discovered": sorted(self.discovered), "location_states": self.location_states,
            "reputation": self.reputation, "faction_relations": self.faction_relations,
            "flags": self.flags, "settings": self.settings, "stats": self.stats, "log": self.log,
            "spellbook": self.spellbook, "spell_drafts": self.spell_drafts, "known_recipes": self.known_recipes,
            "relationships": self.relationships, "favors": self.favors,
            "companions": {k: dict(v, char=v["char"].to_dict()) for k, v in self.companions.items()},
            "bonds": self.bonds, "property": self.property, "base": self.base, "world": self.world, "jobs": self.jobs,
        }

    @classmethod
    def from_dict(cls, data, d, memory=None):
        s = cls(data)
        s.rng = GameRNG.from_dict(d["rng"])
        s.clock = GameClock.from_dict(d["clock"])
        s.player = Character.from_dict(d["player"], data)
        s.gold = d["gold"]
        s.location = d["location"]
        s.local_pos = tuple(d["local_pos"]) if d.get("local_pos") else None
        s.sub_location = d.get("sub_location")
        s.mode = d["mode"]
        s.travel = d.get("travel")
        s.discovered = set(d["discovered"])
        s.location_states = d["location_states"]
        s.reputation = d["reputation"]
        s.faction_relations = d["faction_relations"]
        s.flags = d["flags"]
        s.settings = d["settings"]
        s.stats = d["stats"]
        s.log = d["log"]
        s.spellbook = d.get("spellbook", starter_spellbook())
        s.spell_drafts = d.get("spell_drafts", [])
        s.known_recipes = d.get("known_recipes", [])
        s.relationships = d.get("relationships", {})
        s.favors = d.get("favors", {})
        s.companions = {k: dict(v, char=Character.from_dict(v["char"], data)) for k, v in d.get("companions", {}).items()}
        s.bonds = d.get("bonds", {})
        s.property = d.get("property", {})
        s.base = d.get("base", {})
        s.world = d.get("world", s.world)
        s.jobs = d.get("jobs", [])
        s.settings.setdefault("weapon_mode", "melee")
        if memory is not None:
            s.memory = memory
        return s
