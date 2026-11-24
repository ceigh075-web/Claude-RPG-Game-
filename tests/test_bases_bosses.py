"""Starter house, bases of operations, the carter, and boss fights. Run: python -m unittest -v"""
import os
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from game.core.game import Game  # noqa: E402
from game.set_system import bases, morale  # noqa: E402


def new_game():
    g = Game(headless=True, save_dir=tempfile.mkdtemp())
    g.new_game("B", "human", {"race": "human"}, "they/them")
    return g


class TestBases(unittest.TestCase):
    def test_starter_house(self):
        g = new_game()
        st = g.state
        self.assertIn(st.location, st.property)
        self.assertTrue(st.property[st.location].get("starter"))
        self.assertTrue(st.player.inventory.has("house_deed"))
        self.assertEqual(morale.prison_capacity(st), (0, 1))
        b = bases.list_bases(st)
        self.assertEqual(len(b), 1)
        self.assertTrue(b[0]["home"])
        self.assertGreater(b[0]["storage"], 0)
        # the house is the town's for-sale house, so its door leads inside
        m = g.local_map(st.location)
        self.assertIn(st.property[st.location]["building"], m.buildings)
        self.assertEqual(m.buildings[st.property[st.location]["building"]]["type"], "property_for_sale")

    def test_home_and_carter(self):
        g = new_game()
        st = g.state
        st.property["duskreach"] = {"building": "b1", "bought": 0, "storage": {}}
        ok, _ = bases.set_home(st, "house:duskreach")
        self.assertTrue(ok)
        self.assertEqual(bases.home_location(st), "duskreach")
        ok, km, hours, marks, why = bases.carter_quote(st, g.world, "house:duskreach")
        self.assertTrue(ok, why)
        st.gold = 1000
        day0, gold0 = st.clock.total_minutes, st.gold
        ok, msg = bases.ride_carter(st, g.world, "house:duskreach")
        self.assertTrue(ok, msg)
        self.assertEqual(st.location, "duskreach")
        self.assertEqual(st.gold, gold0 - marks)
        self.assertGreaterEqual(st.clock.total_minutes - day0, int(hours * 60) - 1)

    def test_carter_needs_a_base(self):
        g = new_game()
        st = g.state
        st.property["duskreach"] = {"building": "b1", "bought": 0, "storage": {}}
        st.location = "velmora"
        ok, *_ , why = bases.carter_quote(st, g.world, "house:duskreach")
        self.assertFalse(ok)
        self.assertIn("bases", why)

    def test_bases_screen_draws(self):
        import pygame
        g = new_game()
        from game.presentation.scenes.bases import BasesScene
        sc = BasesScene(g)
        g.scenes.push(sc)
        g.step(1 / 30, [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_h, mod=0, unicode="h", scancode=0)])
        g.step(1 / 30, [])


if __name__ == "__main__":
    unittest.main()
