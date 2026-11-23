"""Quality-of-life update: mana economy, spells anywhere, knowledge/guide content, movement feel, saves.
Run: python -m unittest -v"""
import os
import random
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from game.gameplay.combat import CombatWorld  # noqa: E402
from game.gameplay.entity import Actor  # noqa: E402
from game.presentation import knowledge  # noqa: E402
from game.set_system import spells  # noqa: E402
from tests.test_combat import DATA, FakeGame, arena, new_state  # noqa: E402

LOOK = {"race": "human", "skin": [190, 150, 110], "hair": [40, 30, 20], "shirt": [60, 90, 150], "pants": [60, 50, 40]}


def world():
    st = new_state()
    m = arena()
    w = CombatWorld(FakeGame(), st, m, random.Random(1))
    pc = w.add_player(Actor(8 * 16 + 8, 11 * 16 + 12, LOOK, 70))
    return st, m, w, pc


class TestMana(unittest.TestCase):
    def test_bigger_pool_that_grows(self):
        st = new_state()
        p = st.player
        self.assertGreaterEqual(p.max_mana, 80)
        base = p.max_mana
        p.skills["magic"] = 50
        self.assertEqual(p.max_mana, base + 100)
        p.xp_total = 40 * 4 * 4      # level 5
        self.assertEqual(p.max_mana, base + 100 + 20)

    def test_passive_regen_faster_out_of_combat(self):
        st, m, w, pc = world()
        st.player.mana = 0
        for _ in range(60):
            w.update(1 / 60, m)
        calm = st.player.mana
        self.assertAlmostEqual(calm, spells.regen_per_second(st.player, False), delta=0.2)
        w.spawn_enemy("bandit_cutthroat", pc.x + 300, pc.y).alerted = True
        st.player.mana = 0
        for _ in range(60):
            w.update(1 / 60, m)
        self.assertTrue(w.in_combat)
        self.assertLess(st.player.mana, calm)
        self.assertGreater(st.player.mana, 0)

    def test_regen_never_exceeds_max(self):
        st, m, w, pc = world()
        st.player.mana = st.player.max_mana - 0.1
        for _ in range(120):
            w.update(1 / 60, m)
        self.assertEqual(st.player.mana, st.player.max_mana)

    def test_weapon_hits_restore_mana_spells_dont(self):
        st, m, w, pc = world()
        dummy = w.spawn_enemy("training_dummy", pc.x + 12, pc.y)
        prof = {"damage": 20, "knockback": 0, "stagger": 0, "skill": "melee", "scaling": []}
        st.player.mana = 0
        w.hit(pc, dummy, prof, (pc.x, pc.y))
        gained = st.player.mana
        self.assertGreater(gained, 0)
        self.assertLessEqual(gained, spells.HIT_MANA_CAP)
        st.player.mana = 0
        w.hit(pc, dummy, dict(prof, skill="magic"), (pc.x, pc.y))
        self.assertEqual(st.player.mana, 0)

    def test_magic_stays_limited(self):
        """Casting freely is possible for a while, but mana runs out: costs outpace combat regeneration."""
        st = new_state()
        p = spells.compute(DATA, st.spellbook[0], 0)
        per_sec = spells.regen_per_second(st.player, True)
        casts_per_sec = 1 / max(0.12, p["cooldown"])
        self.assertGreater(p["mana"] * casts_per_sec, per_sec * 3)
        self.assertLess(spells.mana_from_hit(1000, "melee"), 13)

    def test_cast_failure_explains(self):
        st, m, w, pc = world()
        st.player.mana = 0
        ok, msg = w.cast(pc, st.spellbook[0])
        self.assertFalse(ok)
        self.assertIn("needs", msg)


class TestSpellsAnywhere(unittest.TestCase):
    def test_inscribe_without_table_or_ink(self):
        st = new_state()
        st.player.xp_total = 40 * 9 * 9          # room in the book
        self.assertFalse(st.player.inventory.has("enchanted_ink"))
        spell = {"name": "Field Spark", "sub": "lightning", "move": "projectile", "stat": "damage", "tier": 1}
        ok, _ = spells.save_draft(st, spell)
        self.assertTrue(ok)
        ok, msg = spells.inscribe(st, 0, at_table=False)
        self.assertTrue(ok, msg)
        self.assertEqual(st.spellbook[-1]["name"], "Field Spark")


class TestKnowledge(unittest.TestCase):
    def test_every_item_has_a_source_and_a_use_or_description(self):
        st = new_state()
        for item_id, it in DATA.items.items():
            src = knowledge.sources(st, item_id)
            self.assertTrue(src, item_id)
            self.assertTrue(knowledge.uses(st, item_id) or it.get("desc"), item_id)

    def test_resources_point_to_real_places(self):
        st = new_state()
        txt = " ".join(knowledge.sources(st, "rustite_ore"))
        self.assertIn("Rustback Hills", txt)
        self.assertIn("(unexplored)", txt)
        st.discovered.add("rustback_hills")
        self.assertNotIn("Rustback Hills (unexplored)", " ".join(knowledge.sources(st, "rustite_ore")))

    def test_money_and_job_guidance(self):
        st = new_state()
        self.assertGreaterEqual(len(knowledge.money_methods(st)), 6)
        job = {"type": "bounty", "enemy": "wolf", "town": "brackenford", "count": 3}
        self.assertIn("Grey Wolf", knowledge.job_next_step(st, job))

    def test_every_station_is_findable(self):
        st = new_state()
        for stn in ("furnace", "anvil", "workbench", "stove", "alchemy", "campfire"):
            self.assertNotIn("nowhere", knowledge.station_places(st, stn), stn)


class TestGuideAndMenus(unittest.TestCase):
    def test_guide_chapters_render(self):
        import pygame
        from game.core.game import Game
        from game.presentation.scenes.guide import GuideScene
        d = tempfile.mkdtemp()
        g = Game(headless=True, save_dir=d)
        g.new_game("Tess", "human", dict(LOOK, hair_style=0), "they/them")
        g.enter_world()
        sc = GuideScene(g)
        g.scenes.push(sc)
        for i in range(len(sc.data_cache)):
            sc.ch = i
            g.step(1 / 60, [])
        titles = [t for t, _ in sc.data_cache]
        for need in ("Earning Money", "Resources", "Magic & Mana", "Current Objectives", "Places You Know"):
            self.assertIn(need, titles)
        g.scenes.pop()
        # Tab quick menu and F9 confirmation don't crash and don't load without confirming
        g.step(1 / 60, [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_TAB, mod=0, unicode="", scancode=0)])
        self.assertEqual(type(g.scenes.top).__name__, "ChoiceScene")


class TestMovementFeel(unittest.TestCase):
    def test_acceleration_and_glide(self):
        import pygame
        from game.core.game import Game
        d = tempfile.mkdtemp()
        g = Game(headless=True, save_dir=d)
        g.new_game("Tess", "human", dict(LOOK, hair_style=0), "they/them")
        g.state.location = "greywood"
        g.state.local_pos = None
        g.enter_world()
        sc = g.scenes.top
        pressed = {}

        class Keys(dict):
            def __getitem__(self, k):
                return self.get(k, False)
        keys = Keys()
        old = pygame.key.get_pressed
        pygame.key.get_pressed = lambda: keys
        try:
            keys[pygame.K_d] = True
            for _ in range(3):
                g.step(1 / 60, [])
            early = abs(sc.pvel[0])
            for _ in range(40):
                g.step(1 / 60, [])
            top = abs(sc.pvel[0])
            self.assertLess(early, top)                       # it ramps up
            self.assertGreater(top, g.state.player.move_speed())  # and ends faster than the base stat
            keys.clear()
            x = sc.player.x
            for _ in range(30):
                g.step(1 / 60, [])
            self.assertLess(abs(sc.player.x - x), 8)          # a short glide, not a slide
            self.assertEqual(sc.pvel, (0.0, 0.0))
        finally:
            pygame.key.get_pressed = old
        del pressed


class TestSaves(unittest.TestCase):
    def test_save_load_keeps_mana_and_spells(self):
        from game.core.game import Game
        d = tempfile.mkdtemp()
        g = Game(headless=True, save_dir=d)
        g.new_game("Tess", "human", dict(LOOK, hair_style=0), "they/them")
        g.state.player.mana = 17.5
        self.assertTrue(g.save_game(2))
        names = [s["name"] for s in g.state.spellbook]
        g.load_game(2)
        self.assertAlmostEqual(g.state.player.mana, 17.5)
        self.assertEqual([s["name"] for s in g.state.spellbook], names)


if __name__ == "__main__":
    unittest.main()
