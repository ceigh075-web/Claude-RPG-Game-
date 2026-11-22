"""Phase 8: town houses, outpost founding, construction, workers, farming, production, research, raids."""
import random
import unittest

from game.core.data import GameData
from game.core.state import GameState
from game.set_system import base, companions, favors, relationships as rel, timeflow

DATA = GameData()


def new_state():
    s = GameState.new_game(DATA, "Bo", "kethari", {"race": "kethari"}, "she/her", seed=41)
    s.gold = 20000
    return s


def found(s):
    s.location = "widows_crossing"
    s.player.inventory.add("wood", 20)
    s.player.inventory.add("stone", 10)
    ok, msg = base.found_outpost(s, [(10 + i * 3, 10) for i in range(8)])
    assert ok, msg
    return s


def give_mats(s, btype, times=1):
    for item, q in DATA.base["buildings"][btype]["items"].items():
        s.player.inventory.add(item, q * times)


def finish(s, hours=30):
    timeflow.advance(s, hours * 60)
    base.update_construction(s)


def hire(s, nid):
    rel.change(s, nid, friendship=100, trust=100, respect=100)
    npc = DATA.npcs[nid]
    if "favor" in npc["recruit"]:
        s.favors[npc["recruit"]["favor"]] = {"status": "done", "started": 0, "npc": nid}
    for f in npc["recruit"].get("rep", {}):
        s.reputation[f] = 100
    ok, _ = companions.recruit(s, npc)
    assert ok


class TestHouse(unittest.TestCase):
    def test_buy_and_store(self):
        s = new_state()
        g = s.gold
        ok, _ = base.buy_house(s, "brackenford", "b6")
        self.assertTrue(ok)
        self.assertEqual(s.gold, g - 600)
        self.assertFalse(base.buy_house(s, "brackenford", "b6")[0])
        inv = base.storage(s, s.property["brackenford"])
        inv.add("ration", 3)
        base.save_storage(s.property["brackenford"], inv)
        self.assertEqual(base.storage(s, s.property["brackenford"]).count("ration"), 3)

    def test_home_task_heals(self):
        s = new_state()
        base.buy_house(s, "brackenford", "b6")
        hire(s, "tobin")
        self.assertTrue(companions.set_task(s, "tobin", "home")[0])
        c = companions.char(s, "tobin")
        c.hp = 1
        timeflow.advance(s, 1440)
        self.assertEqual(c.hp, c.max_hp)


class TestOutpost(unittest.TestCase):
    def test_found_and_corin_favor(self):
        s = found(new_state())
        self.assertTrue(base.founded(s))
        s.favors["corin_settle"] = {"status": "active", "started": 0, "npc": "corin"}
        self.assertTrue(favors.progress(s, "corin_settle")[0])

    def test_construction_takes_time_and_materials(self):
        s = found(new_state())
        self.assertFalse(base.build(s, 0, "storage")[0])  # no materials
        give_mats(s, "storage")
        self.assertTrue(base.build(s, 0, "storage")[0])
        self.assertFalse(base.building_at(s, 0)["done"])
        finish(s)
        self.assertTrue(base.building_at(s, 0)["done"])

    def test_storage_materials_count(self):
        s = found(new_state())
        inv = base.storage(s, s.base)
        for item, q in DATA.base["buildings"]["farm"]["items"].items():
            inv.add(item, q)
        base.save_storage(s.base, inv)
        self.assertTrue(base.build(s, 1, "farm")[0])
        self.assertEqual(sum(base.storage(s, s.base).items.values()), 0)

    def test_workers_need_bunkhouse_and_produce(self):
        s = found(new_state())
        hire(s, "tobin")
        give_mats(s, "workshop")
        base.build(s, 0, "workshop")
        finish(s)
        self.assertFalse(base.assign(s, "tobin", 0)[0])   # no beds
        give_mats(s, "bunkhouse")
        base.build(s, 1, "bunkhouse")
        finish(s)
        self.assertTrue(base.assign(s, "tobin", 0)[0])
        inv = base.storage(s, s.base)
        inv.add("rustite_ore", 6)
        inv.add("ration", 5)
        base.save_storage(s.base, inv)
        timeflow.advance(s, 1440)
        self.assertGreaterEqual(base.storage(s, s.base).count("rustite_bar"), 3)

    def test_farming_manual_and_worked(self):
        s = found(new_state())
        give_mats(s, "farm")
        base.build(s, 2, "farm")
        finish(s)
        s.player.inventory.add("seed_grain", 4)
        self.assertTrue(base.plant(s, 2, "seed_grain")[0])
        self.assertFalse(base.harvest(s, 2)[0])
        timeflow.advance(s, 1440 * 3)
        ok, _ = base.harvest(s, 2)
        self.assertTrue(ok)
        self.assertEqual(s.player.inventory.count("grain"), 5)

    def test_trading_post_income(self):
        s = found(new_state())
        hire(s, "fenna")
        for b, p in (("bunkhouse", 0), ("trading", 1)):
            give_mats(s, b)
            base.build(s, p, b)
        finish(s)
        base.assign(s, "fenna", 1)
        g = s.gold
        inv = base.storage(s, s.base)
        inv.add("ration", 3)
        base.save_storage(s.base, inv)
        timeflow.advance(s, 1440)
        self.assertGreater(s.gold, g)

    def test_research_unlocks_voidglass(self):
        s = found(new_state())
        give_mats(s, "research")
        base.build(s, 0, "research")
        finish(s)
        s.player.inventory.add("relic_shard", 3)
        s.player.inventory.add("voidglass_ore", 2)
        self.assertTrue(base.start_research(s, "voidglass")[0])
        timeflow.advance(s, 25 * 60)
        base.update_research(s)
        self.assertIn("voidglass", s.known_recipes)

    def test_raids_win_and_lose(self):
        s = found(new_state())
        inv = base.storage(s, s.base)
        inv.add("grain", 10)
        base.save_storage(s.base, inv)
        give_mats(s, "storage")
        base.build(s, 0, "storage")
        finish(s)
        msg = base.resolve_raid(s, 999, random.Random(1))  # hopeless
        self.assertIn("plundered", msg)
        self.assertLess(base.storage(s, s.base).count("grain"), 10)
        self.assertTrue(base.building_at(s, 0)["damaged"])
        give_mats(s, "storage")
        self.assertTrue(base.repair(s, 0)[0])
        self.assertFalse(base.building_at(s, 0)["damaged"])
        for i, b in enumerate(("palisade", "watchtower")):
            give_mats(s, b)
            base.build(s, 3 + i, b)
        finish(s)
        self.assertGreaterEqual(base.defense(s), 30)
        msg = base.resolve_raid(s, 5, random.Random(1))
        self.assertIn("beaten back", msg)

    def test_raids_happen_over_time(self):
        s = found(new_state())
        s.location = "brackenford"
        s.world["hollow_strength"] = 100
        for _ in range(60):
            timeflow.advance(s, 1440)
        self.assertTrue(any("raid" in l.lower() for l in s.base["log"]))


if __name__ == "__main__":
    unittest.main()
