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


class TestPrisonerHousing(unittest.TestCase):
    def setUp(self):
        from tests.test_combat import new_state
        self.st = new_state()

    def found_outpost(self, stockades=1):
        st = self.st
        st.base["founded"] = 0
        st.base.setdefault("buildings", {})
        for i in range(stockades):
            st.base["buildings"][str(i)] = {"type": "stockade", "done": True, "damaged": False, "crop": None}

    def test_no_facility_blocks_capture(self):
        from game.set_system import morale
        self.found_outpost(0)                                   # an outpost without a stockade has no cells
        self.assertEqual(morale.prison_capacity(self.st), (0, 0))
        opts = {k: (ok, why) for _, k, ok, why in morale.options(self.st, "bandit_cutthroat")}
        self.assertFalse(opts["prisoner"][0])
        self.assertIn("stockade", opts["prisoner"][1])
        self.assertIn("can't", morale.resolve(self.st, "bandit_cutthroat", "prisoner"))

    def test_capacity_counts_and_fills(self):
        from game.set_system import morale
        self.st.property["brackenford"] = {"building": "b5", "bought": 0, "storage": {}}
        self.found_outpost(1)
        self.assertEqual(morale.prison_capacity(self.st), (0, 5))
        for _ in range(5):
            morale.resolve(self.st, "bandit_cutthroat", "prisoner")
        self.assertEqual(morale.prison_capacity(self.st), (5, 5))
        self.assertFalse(morale.can_hold_prisoners(self.st))
        held = [p["held_at"] for p in morale.prisoners(self.st)]
        self.assertEqual(held[:4], ["stockade:0"] * 4)           # decent cells fill first
        self.assertEqual(held[4], "house:brackenford")

    def test_conditions_change_feelings(self):
        from game.set_system import morale
        self.st.property["brackenford"] = {"building": "b5", "bought": 0, "storage": {}}
        self.found_outpost(1)
        morale.resolve(self.st, "bandit_cutthroat", "prisoner")
        p = morale.prisoners(self.st)[0]
        morale.set_treatment(self.st, p["id"], False)
        morale.daily(self.st)
        good = dict(p)
        q = dict(p, id="x", held_at="house:brackenford", loyalty=10.0, resentment=20.0)
        p.update(loyalty=10.0, resentment=20.0)
        morale.prisoners(self.st).append(q)
        morale.daily(self.st)
        self.assertGreater(p["loyalty"], q["loyalty"])
        self.assertLess(p["resentment"], q["resentment"])
        self.assertTrue(good)

    def test_retainer_beds(self):
        from game.set_system import morale
        self.st.property["brackenford"] = {"building": "b5", "bought": 0, "storage": {}}
        self.assertEqual(morale.retainer_capacity(self.st), (0, 1))
        morale.retainers(self.st).append({"name": "x", "enemy": "bandit_cutthroat", "since": 0, "loyalty": 60})
        self.assertFalse(morale.bed_free(self.st))
        morale.resolve(self.st, "bandit_cutthroat", "prisoner")
        p = morale.prisoners(self.st)[0]
        p["loyalty"] = 99
        self.assertIn("bed", morale.recruit_prisoner(self.st, p["id"]))

    def test_old_save_prisoner_gets_a_cell(self):
        from game.set_system import morale
        self.st.property["brackenford"] = {"building": "b5", "bought": 0, "storage": {}}
        morale.prisoners(self.st).append({"id": "old", "enemy": "bandit_cutthroat", "name": "B", "loyalty": 10.0,
                                          "resentment": 20.0, "kind": True, "since": 0, "talked": -1})
        morale.daily(self.st)
        self.assertEqual(morale.prisoners(self.st)[0]["held_at"], "house:brackenford")


class TestCharacterCreator(unittest.TestCase):
    def test_every_option_renders_in_every_animation(self):
        import pygame
        pygame.init()
        try:
            pygame.display.set_mode((1, 1))
        except pygame.error:
            pass
        from game.presentation import charsprites
        from game.presentation.scenes import creator
        base = {"race": "human", "skin": [200, 160, 120], "hair": [40, 30, 20], "shirt": [90, 60, 120],
                "pants": [50, 40, 40]}
        looks = [dict(base, face=f, eye=[40, 90, 160]) for f in creator.FACE_MARKS]
        looks += [dict(base, hat=h, hat_col=[90, 60, 40]) for h in creator.HATS if h]
        looks += [dict(base, outfit=o, outfit_col=[120, 40, 40], cape=[60, 60, 120]) for o in creator.OUTFITS]
        looks += [dict(base, hair_style=i, beard=i % 5, build="stout", height="tall") for i in range(10)]
        looks += [dict(base, acc=list(creator.ACCESSORIES), warpaint=[170, 40, 40], eye_style=0)]
        for look in looks:
            for anim in ("idle", "walk", "slice"):
                for d in ("down", "left", "up", "right"):
                    surf, _, _ = charsprites.compose(look, anim, d, 1)
                    self.assertGreater(surf.get_bounding_rect().w, 0)

    def test_face_marks_change_the_sprite(self):
        import pygame
        pygame.init()
        from game.presentation import charsprites
        base = {"race": "human", "skin": [200, 160, 120], "hair": [40, 30, 20]}
        plain = charsprites.compose(dict(base, face="none"), "idle", "down", 0)[0]
        blush = charsprites.compose(dict(base, face="blush"), "idle", "down", 0)[0]
        self.assertNotEqual(pygame.image.tobytes(plain, "RGBA"), pygame.image.tobytes(blush, "RGBA"))


class TestSaveMigration(unittest.TestCase):
    def test_v104_save_loads_with_new_systems(self):
        """A save from before this update: spells without sliders, prisoners without cells, looks without faces."""
        import json
        from game.core.state import GameState
        from game.set_system import loot, morale
        from tests.test_combat import new_state
        st = new_state()
        st.property["brackenford"] = {"building": "b5", "bought": 0, "storage": {}}
        d = json.loads(json.dumps(st.to_dict()))
        d["spellbook"] = [{"name": "Old Bolt", "element": "fire", "move": "projectile", "stat": "damage", "tier": 1}]
        d.setdefault("stats", {})["prisoners"] = [{"id": "pr1", "enemy": "bandit_cutthroat", "name": "Cutthroat",
                                                  "loyalty": 30.0, "resentment": 10.0, "kind": True, "since": 0,
                                                  "talked": -1}]
        st2 = GameState.from_dict(DATA, d)
        p = spells.compute(DATA, st2.spellbook[0])
        self.assertGreater(p["mana"], 0)
        self.assertEqual(st2.spellbook[0].get("behavior", "standard"), "standard")
        morale.daily(st2)
        self.assertEqual(morale.prisoners(st2)[0]["held_at"], "house:brackenford")
        self.assertEqual(morale.prison_capacity(st2), (1, 1))
        self.assertIsInstance(loot.container(st2, "brackenford", "c1"), list)
        st3 = GameState.from_dict(DATA, json.loads(json.dumps(st2.to_dict())))    # and round-trips
        self.assertEqual(morale.prisoners(st3)[0]["held_at"], "house:brackenford")
        self.assertEqual(st3.location_state("brackenford")["containers"]["c1"]["items"],
                         st2.location_state("brackenford")["containers"]["c1"]["items"])
