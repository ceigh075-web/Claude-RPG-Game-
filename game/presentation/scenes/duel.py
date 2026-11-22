"""Non-lethal one-on-one fight with a named NPC (sparring, pit fights, the Hollow chief's challenge)."""
import random

from ...gameplay.combat import CombatWorld, npc_fighter
from ...gameplay.entity import Actor
from ...set_system import relationships as rel
from ...world import mapgen
from ..art import npc_look
from .common import MessageScene
from .local import LocalScene, T

YIELD_AT = 0.15


class DuelScene(LocalScene):
    def __init__(self, game, npc):
        self.npc = npc
        self.ended = False
        st = game.state
        self.snapshot = (st.local_pos, st.sub_location)
        super().__init__(game)

    def load_map(self, spawn=None):
        st = self.state
        biome = self.data.location(st.location)["biome"]
        self.map = mapgen.generate_arena(self.data, biome, f"duel-{self.npc['id']}")
        self.map.name = "Duel"
        self.loc_key = "duel"
        self.depleted = set()
        self.map.build_solid_grid()
        ex, ey = self.map.entry
        actor = Actor((ex + 6) * T + 8, ey * T + 12, st.player.appearance, st.player.move_speed(), name=st.player.name)
        self.combat = CombatWorld(self.game, st, self.map, random.Random(st.rng.random()))
        self.player = self.combat.add_player(actor)
        self.player.aim = (1.0, 0.0)
        self.npcs = []
        self.active_groups = set()
        self.last_hour = st.clock.hour
        edef = npc_fighter(self.data, self.npc)
        self.foe = self.combat.spawn_enemy(self.npc["id"], (ex + 16) * T + 8, ey * T + 12, edef=edef,
                                           look=npc_look(self.data, self.npc))
        self.foe.alerted = True
        self.foe.enemy_id = self.npc["id"]

    def spawn_npcs(self):
        self.npcs = []

    def spawn_enemies(self):
        pass

    def check_groups(self):
        self.combat.escaped = []

    def note_escape(self):
        pass

    def place_name(self):
        return f"Duel with {self.npc['name']}"

    def on_edge(self, ex):
        self.end(False, "You step out of the ring. That counts as a loss.")

    def update(self, dt):
        if self.ended:
            return
        super().update(dt)
        if self.ended:
            return
        if self.foe.hp <= self.foe.max_hp * YIELD_AT or not self.foe.alive:
            self.end(True)
        elif self.state.player.hp <= self.state.player.max_hp * YIELD_AT:
            self.end(False)

    def defeated(self):
        self.end(False)

    def end(self, won, msg=None):
        if self.ended:
            return
        self.ended = True
        st, npc = self.state, self.npc
        p = st.player
        p.alive = True
        p.hp = max(p.hp, p.max_hp * 0.3)
        if won:
            st.flags[f"duel_won:{npc['id']}"] = True
            rel.change(st, npc["id"], reason=f"{p.name} beat them in a duel", respect=20, friendship=3)
            rel.note(st, "bravery", 2)
            st.memory.record(npc["id"], "battle", f"{p.name} defeated {npc['name']} in a duel and let them yield.",
                             day=st.clock.day_index, minute=st.clock.total_minutes % 1440, importance=3,
                             related=["player"], location=st.location)
            body = f"{npc['name']} raises a hand and yields. \"Well fought.\""
        else:
            rel.change(st, npc["id"], respect=4)
            st.memory.record(npc["id"], "battle", f"{npc['name']} beat {p.name} in a duel.", day=st.clock.day_index,
                             minute=st.clock.total_minutes % 1440, importance=2, related=["player"], location=st.location)
            body = msg or f"You yield to {npc['name']}. They help you up. \"Come back when you're ready.\""
        st.local_pos, st.sub_location = self.snapshot
        self.game.scenes.push(MessageScene(self.game, "Victory" if won else "Defeat", body, on_close=self.game.enter_world))
