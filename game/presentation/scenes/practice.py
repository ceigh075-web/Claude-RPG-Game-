"""Practice yard: hit training dummies to train combat skills, or test a drafted spell before inscribing."""
import random

import pygame

from ...gameplay.combat import CombatWorld
from ...gameplay.entity import Actor
from ...world import mapgen
from .local import LocalScene, T


class PracticeScene(LocalScene):
    def __init__(self, game, test_spell=None):
        self.test_spell = test_spell
        st = game.state
        self.snapshot = (st.player.hp, st.player.mana, st.local_pos, st.sub_location)
        super().__init__(game)

    def load_map(self, spawn=None):
        st = self.state
        self.map = mapgen.generate_arena(self.data, "grassland", "practice")
        self.map.name = "Practice yard"
        self.loc_key = "practice"
        self.depleted = set()
        self.map.build_solid_grid()
        ex, ey = self.map.entry
        actor = Actor(ex * T + 8, ey * T + 12, st.player.appearance, st.player.move_speed(), name=st.player.name)
        self.combat = CombatWorld(self.game, st, self.map, random.Random(1))
        self.player = self.combat.add_player(actor)
        self.player.aim = (1.0, 0.0)
        self.npcs = []
        self.active_groups = set()
        self.last_hour = st.clock.hour
        for dy in (-3, 0, 3):
            self.combat.spawn_enemy("training_dummy", (ex + 7) * T + 8, (ey + dy) * T + 12, hostile=False)

    def hotbar(self):
        book = list(self.state.spellbook)
        return ([self.test_spell] + book[:3]) if self.test_spell else book[:4]

    def spawn_npcs(self):
        self.npcs = []

    def spawn_enemies(self):
        pass

    def check_groups(self):
        self.combat.escaped = []

    def note_escape(self):
        pass

    def place_name(self):
        return "Practice yard" + (f" - testing {self.test_spell['name']}" if self.test_spell else "")

    def on_edge(self, ex):
        self.leave()

    def handle(self, ev):
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
            self.leave()
            return
        if ev.type == pygame.KEYDOWN and pygame.K_1 <= ev.key <= pygame.K_4:
            self.state.player.mana = self.state.player.max_mana  # testing is free
        super().handle(ev)

    def update(self, dt):
        super().update(dt)
        for d in self.combat.enemies():
            d.hp = d.max_hp  # dummies never break

    def leave(self):
        st = self.state
        hp, mana, pos, sub = self.snapshot
        st.player.hp, st.player.mana = max(hp, st.player.hp), mana
        st.local_pos, st.sub_location = pos, sub
        self.game.toast("You leave the practice yard.")
        self.game.enter_world()
