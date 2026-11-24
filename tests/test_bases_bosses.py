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


class TestBosses(unittest.TestCase):
    def setUp(self):
        self.g = new_game()
        st = self.g.state
        st.location, st.local_pos, st.sub_location = "hollow_fort", None, None
        st.discovered.add("hollow_fort")
        st.player.hp = st.player.max_hp
        self.g.enter_world()
        self.loc = self.g.scenes.top
        self.w = self.loc.combat

    def boss(self):
        return self.w.bosses[0]

    def test_boss_spawns_with_controller(self):
        self.assertEqual(len(self.w.bosses), 1)
        b = self.boss()
        self.assertEqual(b.c.enemy["boss"], "hollow_warlord")
        self.assertEqual(b.c.max_hp, 900)

    def test_phases_summon_enrage_and_telegraph(self):
        b = self.boss()
        p = self.w.player
        p.x, p.y = b.c.x - 60, b.c.y
        n0 = len(self.w.enemies())
        for _ in range(10):
            self.w.update(1 / 30, self.loc.map)
        self.assertTrue(b.engaged)
        b.c.hp = b.c.max_hp * 0.65
        self.w.update(1 / 30, self.loc.map)
        self.assertGreater(len(self.w.enemies()), n0)          # minions arrived
        b.c.hp = b.c.max_hp * 0.35
        self.w.update(1 / 30, self.loc.map)
        self.assertTrue(b.enraged)
        b.timer = 0
        self.w.update(1 / 30, self.loc.map)
        self.assertTrue(self.w.telegraphs)
        hp0 = p.char.hp if p.char else None
        tg = self.w.telegraphs[0]
        p.x, p.y = tg["x"], tg["y"] + 4
        for _ in range(60):
            self.w.update(1 / 30, self.loc.map)
        self.assertFalse(any(t["src"] is b.c for t in self.w.telegraphs if t["t"] > t["delay"]))
        if hp0 is not None:
            self.assertLess(p.char.hp, hp0)

    def test_defeat_is_permanent_and_rewarding(self):
        from game.set_system import bosses
        b = self.boss()
        st = self.g.state
        rep0 = st.reputation["crown"]
        b.c.hp = 0
        self.w.kill(b.c, self.w.player)
        self.assertTrue(bosses.defeated(st, "hollow_warlord"))
        self.assertGreater(st.reputation["crown"], rep0)
        self.assertTrue(any(e["item"] == "sunsilver_bar" for e in b.c.loot))
        self.assertTrue(self.w.pickups)                       # marks burst out
        self.g.enter_world()
        self.assertEqual(self.g.scenes.top.combat.bosses, [])  # gone for good

    def test_every_boss_lair_spawns(self):
        for bid, bd in self.g.data.bosses.items():
            st = self.g.state
            st.location, st.local_pos, st.sub_location = bd["location"], None, None
            self.g.enter_world()
            w = self.g.scenes.top.combat
            self.assertEqual([x.id for x in w.bosses], [bid])
            for _ in range(30):
                self.g.step(1 / 30, [])
