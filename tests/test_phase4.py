"""Phase 4: crafting, armor, recipe knowledge, spell drafting and inscribing."""
import unittest

from game.core.data import GameData
from game.core.state import GameState
from game.set_system import crafting, items, spells
from game.world import mapgen
from game.world.worldmap import WorldMap

DATA = GameData()


def new_state():
    return GameState.new_game(DATA, "T", "human", {"race": "human"}, "they/them", seed=4)


class TestCrafting(unittest.TestCase):
    def test_every_weapon_type_and_ore_is_craftable(self):
        for wid, w in DATA.weapons.items():
            if w["bars"]:
                for ore in DATA.ores:
                    self.assertIn(f"{wid}_{ore}", DATA.recipes)
        for ore in DATA.ores:
            self.assertIn(f"smelt_{ore}", DATA.recipes)
            self.assertIn(f"mail_{ore}", DATA.recipes)

    def test_categories_covered(self):
        outs = {DATA.item(r["out"])["type"] for r in DATA.recipes.values()}
        for t in ("weapon", "armor", "tool", "medicine", "food", "material", "magic", "bar", "ammo"):
            self.assertIn(t, outs)

    def test_smelt_and_forge(self):
        s = new_state()
        p = s.player
        p.inventory.add("rustite_ore", 4)
        ok, _ = crafting.craft(s, DATA.recipes["smelt_rustite"], 2)
        self.assertTrue(ok)
        self.assertEqual(p.inventory.count("rustite_bar"), 2)
        p.inventory.add("leather", 1)
        t0 = s.clock.total_minutes
        ok, _ = crafting.craft(s, DATA.recipes["shortsword_rustite"])
        self.assertTrue(ok)
        self.assertTrue(p.inventory.has("shortsword_rustite"))
        self.assertGreater(s.clock.total_minutes, t0)
        self.assertGreater(p.skills["crafting"], 0)

    def test_skill_and_knowledge_gates(self):
        s = new_state()
        p = s.player
        p.inventory.add("sunsilver_bar", 10)
        p.inventory.add("leather", 5)
        ok, why = crafting.check(s, DATA.recipes["dagger_sunsilver"])
        self.assertFalse(ok)
        self.assertIn("Crafting", why)
        p.skills["crafting"] = 60
        self.assertTrue(crafting.check(s, DATA.recipes["dagger_sunsilver"])[0])
        p.inventory.add("voidglass_bar", 3)
        ok, why = crafting.check(s, DATA.recipes["dagger_voidglass"])
        self.assertFalse(ok)
        p.inventory.add("voidglass_manual")
        ok, _ = crafting.learn(s, "voidglass_manual")
        self.assertTrue(ok)
        self.assertTrue(crafting.check(s, DATA.recipes["dagger_voidglass"])[0])

    def test_missing_ingredients(self):
        s = new_state()
        ok, msgs = crafting.craft(s, DATA.recipes["pickaxe"])
        self.assertFalse(ok)
        self.assertFalse(s.player.inventory.has("pickaxe"))

    def test_armor_equips(self):
        s = new_state()
        p = s.player
        p.inventory.add("mail_greyvein")
        p.inventory.add("helm_rustite")
        items.equip(s, p, "mail_greyvein")
        items.equip(s, p, "helm_rustite")
        self.assertAlmostEqual(p.armor_value(DATA), DATA.item("mail_greyvein")["armor"] + DATA.item("helm_rustite")["armor"])

    def test_stations_exist_in_towns(self):
        world = WorldMap(DATA)
        found = set()
        for tid in DATA.towns:
            m = mapgen.generate(DATA, world, tid)
            for b in m.buildings.values():
                im = mapgen.generate_interior(DATA, tid, b)
                found |= {o["kind"] for o in im.objects}
        for k in ("anvil", "furnace", "workbench", "stove", "alchemy_table", "scribing_table", "training_dummy"):
            self.assertIn(k, found)


class TestSpellbook(unittest.TestCase):
    def draft(self, name="Frost Bolt", tier=1):
        return {"name": name, "sub": "ice", "move": "projectile", "stat": "damage", "tier": tier}

    def test_draft_then_inscribe(self):
        """QoL rework: inscribing works anywhere and costs nothing; the book's size still limits it."""
        s = new_state()
        ok, _ = spells.save_draft(s, self.draft())
        self.assertTrue(ok)
        ok, msg = spells.inscribe(s, 0, at_table=False)
        self.assertFalse(ok)  # book full at level 1 (capacity 2) -> must replace
        self.assertIn("full", msg)
        ok, msg = spells.inscribe(s, 0, replace_index=0, at_table=False)
        self.assertTrue(ok, msg)
        self.assertEqual(s.spellbook[0]["name"], "Frost Bolt")
        self.assertEqual(s.spell_drafts, [])

    def test_revise_spell_anywhere(self):
        s = new_state()
        sp = dict(s.spellbook[0])
        sp["tier"] = 1
        sp["name"] = "Renamed Dart"
        ok, msg = spells.revise(s, "book", 0, sp)
        self.assertTrue(ok, msg)
        self.assertEqual(s.spellbook[0]["name"], "Renamed Dart")
        clash = dict(sp, name=s.spellbook[1]["name"])
        ok, _ = spells.revise(s, "book", 0, clash)
        self.assertFalse(ok)

    def test_capacity_with_level(self):
        s = new_state()
        s.player.xp_total = 40 * 9 * 9  # level 10
        s.player.inventory.add("enchanted_ink")
        spells.save_draft(s, self.draft())
        ok, msg = spells.inscribe(s, 0, at_table=True)
        self.assertTrue(ok, msg)
        self.assertEqual(len(s.spellbook), 3)

    def test_tier_gate_and_invalid(self):
        s = new_state()
        with self.assertRaises(spells.SpellError):
            spells.save_draft(s, self.draft(tier=3))
        with self.assertRaises(spells.SpellError):
            spells.save_draft(s, {"name": "x", "sub": "light", "move": "beam", "stat": "root", "tier": 1})
        ok, _ = spells.save_draft(s, dict(self.draft(), name="Ash Dart"))
        self.assertFalse(ok)  # duplicate name


if __name__ == "__main__":
    unittest.main()
