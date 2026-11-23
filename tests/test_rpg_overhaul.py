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
