"""Real-time fight that breaks out during travel. Win, lose, or flee off either side of the road."""
import random

from ...gameplay.combat import CombatWorld
from ...gameplay.entity import Actor
from ...set_system import skirmish
from ...world import mapgen, travel
from .common import MessageScene
from .local import LocalScene, T


class ArenaScene(LocalScene):
    def __init__(self, game):
        pc = game.state.travel["pending_combat"]
        self.enemy_id, self.count = pc["enemy"], pc["count"]
        self.ended = False
        super().__init__(game)

    def load_map(self, spawn=None):
        st = self.state
        tr = st.travel
        self.map = mapgen.generate_arena(self.data, tr["terrain"], f"{tr['from']}-{tr['to']}-{int(tr['done'])}")
        self.loc_key = "arena"
        self.depleted = set()
        self.map.build_solid_grid()
        p = st.player
        ex, ey = self.map.entry
        actor = Actor(ex * T + 8, ey * T + 12, p.appearance, p.move_speed(), name=p.name)
        actor.facing = "right"
        self.combat = CombatWorld(self.game, st, self.map, random.Random(st.rng.random()))
        self.player = self.combat.add_player(actor)
        self.player.aim = (1.0, 0.0)
        self.npcs = []
        self.active_groups = {"arena"}
        self.last_hour = st.clock.hour
        rng = random.Random(st.rng.random())
        for i in range(self.count):
            tx, ty = self.map.find_open_near(self.map.w - 10 + rng.randint(-2, 3), self.map.h // 2 + rng.randint(-4, 4), 4)
            c = self.combat.spawn_enemy(self.enemy_id, tx * T + 8, ty * T + 12, group="arena", hostile=True)
            c.alerted = True

    def spawn_npcs(self):
        self.npcs = []

    def spawn_enemies(self):
        pass

    def check_groups(self):
        self.combat.escaped = []

    def note_escape(self):
        pass

    def place_name(self):
        return "On the road"

    def on_edge(self, ex):
        self.end("fled")

    def update(self, dt):
        if self.ended:
            return
        super().update(dt)
        if not self.ended and self.player.alive and not any(c.alive for c in self.combat.enemies()):
            self.end("victory")

    def defeated(self):
        msg = skirmish.apply_defeat(self.state, self.enemy_id)
        self.end("defeat", msg)

    def end(self, outcome, msg=None):
        if self.ended:
            return
        self.ended = True
        st = self.state
        p = st.player
        p.alive = True
        p.hp = max(p.hp, 5.0)
        killed = sum(1 for k in self.combat.kills if k == self.enemy_id)
        travel.finish_combat(st, outcome, self.enemy_id, self.count, killed)
        # loot left lying on the road is gathered up if you won
        if outcome == "victory":
            for pk in self.combat.pickups:
                if pk["item"] == "marks":
                    st.gold += pk["qty"]
                else:
                    p.inventory.add(pk["item"], pk["qty"])
            self.combat.pickups = []
        body = {"victory": "The road is yours again. You gather what they dropped and continue.",
                "fled": "You break away and put distance between you and them. They won't forget your face.",
                "defeat": (msg or "") + " You limp back onto the road."}[outcome]
        title = {"victory": "Victory", "fled": "Escaped", "defeat": "Defeated"}[outcome]
        self.game.scenes.push(MessageScene(self.game, title, body, on_close=self.game.enter_world))
