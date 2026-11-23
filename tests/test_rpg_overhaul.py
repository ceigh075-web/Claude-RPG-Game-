"""RPG overhaul: spell customization, NPC attack option, looting, prisoner housing, character creator.
Run: python -m unittest -v"""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from game.set_system import spells  # noqa: E402
from tests.test_combat import DATA, run  # noqa: E402
from tests.test_overhaul import world  # noqa: E402

BOLT = {"name": "B", "element": "fire", "move": "projectile", "stat": "damage", "tier": 1}


class TestSpellCustomization(unittest.TestCase):
    def test_every_slider_moves_cost(self):
        base = spells.compute(DATA, BOLT)["mana"]
        for k in ("potency", "velocity", "reach", "duration", "size"):
            hi = spells.compute(DATA, dict(BOLT, **{k: 2.0}))["mana"]
            lo = spells.compute(DATA, dict(BOLT, **{k: 0.5}))["mana"]
            self.assertGreater(hi, base, k)
            self.assertLessEqual(lo, base, k)

    def test_sliders_change_behaviour(self):
        base = spells.compute(DATA, BOLT)
        self.assertGreater(spells.compute(DATA, dict(BOLT, potency=2.0))["power"], base["power"])
        self.assertGreater(spells.compute(DATA, dict(BOLT, velocity=2.0))["speed"], base["speed"])
        self.assertGreater(spells.compute(DATA, dict(BOLT, reach=2.0))["range"], base["range"])
        f = dict(BOLT, move="ground")
        self.assertGreater(spells.compute(DATA, dict(f, duration=3.0))["zone_duration"], spells.compute(DATA, f)["zone_duration"])
        self.assertLess(spells.compute(DATA, dict(BOLT, behavior="rapid"))["cooldown"], base["cooldown"])

    def test_cost_breakdown_explains_cost(self):
        p = spells.compute(DATA, dict(BOLT, potency=2.0, behavior="volley", size=0.5))
        labels = " ".join(l for l, _ in p["cost_breakdown"])
        self.assertIn("Potency", labels)
        self.assertIn("Volley", labels)
        self.assertTrue(any(f < 1 for _, f in p["cost_breakdown"]))      # small size makes it cheaper

    def test_visual_options_are_free(self):
        base = spells.compute(DATA, BOLT)
        v = spells.compute(DATA, dict(BOLT, hue=3, intensity=1.5))
        self.assertEqual(v["mana"], base["mana"])
        self.assertNotEqual(v["color"], base["color"])
        self.assertIn("#", v["sub"])
        from game.presentation import vfx
        self.assertIsNot(vfx.style(v["sub"]), vfx.DEFAULT)

    def test_invalid_behaviour_rejected(self):
        with self.assertRaises(spells.SpellError):
            spells.validate(DATA, dict(BOLT, move="ward", behavior="volley"))
        with self.assertRaises(spells.SpellError):
            spells.validate(DATA, dict(BOLT, potency=9))

    def test_old_spells_load_with_defaults(self):
        sp = spells.normalize(DATA, {"name": "Old", "element": "fire", "move": "projectile", "stat": "damage", "tier": 1})
        self.assertEqual(sp["behavior"], "standard")
        self.assertEqual(sp["duration"], 1.0)

    def test_volley_and_piercing_runtime(self):
        st, m, w, pc = world()
        pc.aim = (1.0, 0.0)
        ok, _ = w.cast(pc, dict(BOLT, name="V", behavior="volley"))
        self.assertTrue(ok)
        self.assertEqual(len(w.projectiles), 3)
        w.projectiles.clear()
        w.cast(pc, dict(BOLT, name="P", behavior="piercing"))
        self.assertEqual(w.projectiles[0].pierce, 2)

    def test_lingering_leaves_field(self):
        st, m, w, pc = world()
        pc.aim = (1.0, 0.0)
        w.cast(pc, dict(BOLT, name="L", behavior="lingering"))
        run(w, m, 2.0)
        self.assertTrue(any(e.kind == "ground" for e in w.effects) or any(
            e.spell.get("lingered") for e in w.effects))

    def test_duplicate_and_save(self):
        from game.presentation.scenes.spellbook import copy_name
        st, m, w, pc = world()
        ok, _ = spells.save_draft(st, dict(BOLT, name="Fire Bolt X"))
        self.assertTrue(ok)
        n = copy_name("Fire Bolt X", st)
        self.assertEqual(n, "Fire Bolt X (2)")
        ok, _ = spells.save_draft(st, dict(BOLT, name=n))
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()


class TestAttackFromConversation(unittest.TestCase):
    def setUp(self):
        import random
        from tests.test_overhaul import LOOK
        self.st, self.m, self.w, self.pc = world()
        self.LOOK, self.random = LOOK, random

    def test_any_townsperson_can_be_attacked(self):
        a = self.w.add_townsfolk(None, self.pc.x + 20, self.pc.y, self.LOOK, self.random.Random(2))
        self.assertFalse(self.w.hostile_between(self.pc, a))
        self.w.provoke(self.pc, a)
        self.assertIn(self.pc.cid, a.grudge)
        self.assertTrue(self.w.hostile_between(self.pc, a))

    def test_guards_respond_to_witnessed_assault(self):
        a = self.w.add_townsfolk(None, self.pc.x + 20, self.pc.y, self.LOOK, self.random.Random(2))
        g = self.w.add_townsfolk(None, self.pc.x + 80, self.pc.y, self.LOOK, self.random.Random(3), guard=True)
        self.w.provoke(self.pc, a)
        self.assertIn(self.pc.cid, g.grudge)


class TestLooting(unittest.TestCase):
    def test_container_persists_and_no_duplication(self):
        from game.set_system import loot
        st, m, w, pc = world()
        items = loot.container(st, "brackenford", "b1", chest=True)
        snapshot = [dict(e) for e in items]
        self.assertEqual(loot.container(st, "brackenford", "b1", chest=True), snapshot)   # same contents on reopen
        gold0 = st.gold
        msgs, v = loot.take_all(st, items)
        self.assertEqual(items, [])
        self.assertEqual(loot.container(st, "brackenford", "b1"), [])                     # stays empty
        again, v2 = loot.take_all(st, loot.container(st, "brackenford", "b1"))
        self.assertEqual(v2, 0)
        self.assertGreaterEqual(st.gold, gold0)
        st.clock.minutes += 1440 * loot.CONTAINER_REFILL_DAYS
        loot.container(st, "brackenford", "b1", chest=True)                                 # refills later (may roll empty)
        self.assertGreater(st.location_state("brackenford")["containers"]["b1"]["refill"], st.clock.day_index)

    def test_take_one_and_categories(self):
        from game.set_system import loot
        st, m, w, pc = world()
        entries = loot.sort(DATA, [{"item": "bread", "qty": 2}, {"item": "marks", "qty": 9},
                                   {"item": "dagger_rustite", "qty": 1}, {"item": "wood", "qty": 3}])
        self.assertEqual([loot.category(DATA, e["item"]) for e in entries], ["money", "equipment", "consumable", "material"])
        gold0 = st.gold
        loot.take(st, entries, 0)
        self.assertEqual(st.gold, gold0 + 9)
        loot.take_all(st, entries, only="equipment")
        self.assertTrue(st.player.inventory.has("dagger_rustite"))
        self.assertEqual(len(entries), 2)

    def test_enemy_drops_scatter_and_gear_stays_on_body(self):
        import random
        st, m, w, pc = world()
        e = w.spawn_enemy("bandit_cutthroat", pc.x + 60, pc.y)
        w.rng = random.Random(4)
        e.hp = 0
        w.kill(e, pc)
        self.assertTrue(w.pickups)
        self.assertTrue(all("vz" in p for p in w.pickups))
        self.assertIsInstance(e.loot, list)
        run(w, m, 2.5)
        if e.loot:
            self.assertIn(e, w.combatants)            # a body with gear stays until searched

    def test_deposit_materials(self):
        from game.set_system import loot
        from game.set_system.inventory import Inventory
        st, m, w, pc = world()
        st.player.inventory.add("wood", 5)
        st.player.inventory.add("bread", 1)
        inv = Inventory()
        self.assertGreaterEqual(loot.deposit_materials(st, inv), 5)
        self.assertFalse(st.player.inventory.has("wood"))
        self.assertTrue(st.player.inventory.has("bread"))

    def test_icons_for_every_item(self):
        import pygame
        pygame.init()
        from game.presentation import icons
        for item in list(DATA.items) + ["marks"]:
            self.assertIsNotNone(icons.icon(DATA, item))
