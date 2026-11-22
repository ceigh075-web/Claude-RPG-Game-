"""Unit tests for the Set System, Set AI memory, saves, world and travel. Run: python -m unittest -v"""
import os
import sqlite3
import tempfile
import unittest

from game.core.clock import GameClock, DAYS_PER_YEAR, MIN_PER_DAY
from game.core.data import GameData
from game.core.rng import GameRNG
from game.core.save import SaveManager, SaveError
from game.core.state import GameState
from game.set_ai.memory import MemoryStore
from game.set_system import economy, factions, items, needs, skirmish, timeflow
from game.set_system.stats import Character
from game.world import effects, mapgen, travel
from game.world.worldmap import WorldMap

DATA = GameData()
WORLD = WorldMap(DATA)


def new_state(seed=1234):
    return GameState.new_game(DATA, "Tester", "human", {"race": "human"}, "they/them", seed=seed)


class TestData(unittest.TestCase):
    def test_scope_counts(self):
        self.assertEqual(len(DATA.towns), 9)
        self.assertEqual(len(DATA.wilderness), 20)
        self.assertEqual(len(DATA.ores), 4)
        self.assertEqual(sum(w["class"] == "melee" for w in DATA.weapons.values()), 12)
        self.assertEqual(sum(w["class"] == "ranged" for w in DATA.weapons.values()), 4)
        self.assertEqual(len(DATA.magic["elements"]), 4)
        self.assertEqual(len(DATA.magic["subelements"]), 16)
        self.assertTrue(40 <= len(DATA.npcs) <= 50)

    def test_every_npc_recruitable(self):
        for n in DATA.npcs.values():
            self.assertTrue(n["recruit"], n["id"])

    def test_generated_weapon_items(self):
        # every craftable weapon type exists in all four ores
        for wid, w in DATA.weapons.items():
            if w["bars"]:
                for ore in DATA.ores:
                    self.assertIn(f"{wid}_{ore}", DATA.items)
        self.assertGreater(DATA.item("longsword_voidglass")["damage"], DATA.item("longsword_rustite")["damage"])


class TestClock(unittest.TestCase):
    def test_calendar(self):
        c = GameClock(0)
        self.assertEqual((c.day_of_month, c.month_name, c.year, c.hour), (1, "Thawmoon", 412, 0))
        c.advance(DAYS_PER_YEAR * MIN_PER_DAY + 28 * MIN_PER_DAY + 90)
        self.assertEqual((c.year, c.month_name, c.day_of_month, c.hour, c.minute), (413, "Seedmoon", 1, 1, 30))

    def test_night(self):
        self.assertTrue(GameClock(23 * 60).is_night)
        self.assertFalse(GameClock(12 * 60).is_night)


class TestRNG(unittest.TestCase):
    def test_roundtrip(self):
        r = GameRNG(99)
        r.random()
        r2 = GameRNG.from_dict(r.to_dict())
        self.assertEqual([r.random() for _ in range(5)], [r2.random() for _ in range(5)])


class TestStatsNeeds(unittest.TestCase):
    def test_training_diminishing(self):
        c = Character("x", "X", "human")
        g1 = c.train("mining", 10)["gain"]
        c.skills["mining"] = 80
        g2 = c.train("mining", 10)["gain"]
        self.assertGreater(g1, g2)
        self.assertLessEqual(c.skills["mining"], 100)

    def test_hunger_penalty_and_starvation(self):
        c = Character("x", "X", "human")
        c.food = 10
        needs.apply_modifiers(c)
        self.assertLess(c.attr("strength"), c.attributes["strength"])
        c.food, c.water = 0, 50
        hp = c.hp
        needs.tick(c, 2)
        self.assertLess(c.hp, hp)

    def test_resting_heals(self):
        c = Character("x", "X", "human")
        c.hp = 10
        needs.tick(c, 4, resting=True)
        self.assertGreater(c.hp, 10)


class TestItemsEconomy(unittest.TestCase):
    def test_eat(self):
        s = new_state()
        s.player.food = 20
        ok, _ = items.use_item(s, s.player, "ration")
        self.assertTrue(ok)
        self.assertEqual(s.player.food, 55)
        self.assertEqual(s.player.inventory.count("ration"), 2)

    def test_equip_weapon(self):
        s = new_state()
        s.player.inventory.add("axe_rustite")
        ok, _ = items.equip(s, s.player, "axe_rustite")
        self.assertTrue(ok)
        self.assertEqual(items.equipped_weapon(DATA, s.player), ("axe", "axe_rustite"))
        items.drop(s, s.player, "axe_rustite")
        self.assertIsNone(s.player.equipment["weapon"])

    def test_buy_sell(self):
        s = new_state()
        gold = s.gold
        ok, _ = economy.buy(s, "brackenford", "provisioner", "pickaxe")
        self.assertTrue(ok)
        self.assertLess(s.gold, gold)
        self.assertTrue(s.player.inventory.has("pickaxe"))
        ok, msg = economy.buy(s, "brackenford", "provisioner", "pickaxe")
        self.assertFalse(ok)  # out of stock (1)
        s.player.inventory.add("rustite_ore", 5)
        g = s.gold
        ok, _ = economy.sell(s, "cinderdeep", "assayer", "rustite_ore", 5)
        self.assertTrue(ok)
        self.assertGreater(s.gold, g)
        ok, _ = economy.sell(s, "cinderdeep", "assayer", "bread", 1)
        self.assertFalse(ok)  # assayer doesn't buy food

    def test_restock(self):
        s = new_state()
        st = economy.shop_state(s, "brackenford", "provisioner")
        st["stock"]["ration"] = 0
        s.clock.advance(8 * MIN_PER_DAY)
        st = economy.shop_state(s, "brackenford", "provisioner")
        self.assertEqual(st["stock"]["ration"], 12)

    def test_reputation_prices(self):
        s = new_state()
        base = economy.buy_price(s, "velmora", "provisioner", "ration")
        factions.change_rep(s, "crown", 80)
        self.assertLess(economy.buy_price(s, "velmora", "provisioner", "ration"), base)


class TestMemory(unittest.TestCase):
    def test_append_only(self):
        m = MemoryStore()
        rid = m.record("garrow", "witnessed", "Saw the player save a child.", day=3, importance=3, related=["player"])
        with self.assertRaises(sqlite3.DatabaseError):
            m.conn.execute("UPDATE records SET description='lie' WHERE id=?", (rid,))
        with self.assertRaises(sqlite3.DatabaseError):
            m.conn.execute("DELETE FROM records")
        self.assertEqual(m.about("player")[0]["description"], "Saw the player save a child.")

    def test_chatter_diverted_and_bounded(self):
        m = MemoryStore()
        for i in range(30):
            m.record("tobin", "conversation", f"small talk {i}", day=1, importance=1)
        self.assertEqual(m.count(), 0)
        self.assertEqual(len(m.chatter("tobin", 100)), 12)

    def test_facts_latest_wins(self):
        m = MemoryStore()
        m.set_fact("npc:garrow:alive", True, 1)
        m.set_fact("npc:garrow:alive", False, 5)
        self.assertFalse(m.fact("npc:garrow:alive"))
        self.assertEqual(m.fact("missing", "d"), "d")

    def test_importance_ordering(self):
        m = MemoryStore()
        m.record("x", "gift", "minor", day=1, importance=1)
        m.record("x", "promise_broken", "major", day=0, importance=4)
        self.assertEqual(m.about("x")[0]["description"], "major")


class TestSave(unittest.TestCase):
    def test_roundtrip(self):
        s = new_state()
        s.player.inventory.add("greyvein_ore", 3)
        s.gold = 321
        s.clock.advance(1000)
        factions.change_rep(s, "ironhold", 12, "test")
        economy.shop_state(s, "brackenford", "provisioner")
        with tempfile.TemporaryDirectory() as d:
            sm = SaveManager(d)
            sm.save(s, 2)
            self.assertTrue(sm.exists(2))
            l = sm.load(2, DATA)
            self.assertEqual(l.gold, 321)
            self.assertEqual(l.player.inventory.count("greyvein_ore"), 3)
            self.assertEqual(l.clock.total_minutes, s.clock.total_minutes)
            self.assertEqual(l.reputation["ironhold"], 12)
            self.assertEqual(l.memory.count(), s.memory.count())
            self.assertEqual(l.rng.random(), s.rng.random())
            with self.assertRaises(sqlite3.DatabaseError):
                l.memory.conn.execute("DELETE FROM records")

    def test_future_version_rejected(self):
        import json
        s = new_state()
        with tempfile.TemporaryDirectory() as d:
            sm = SaveManager(d)
            sm.save(s, 1)
            p = os.path.join(sm.slot_dir(1), "state.json")
            payload = json.load(open(p))
            payload["version"] = 999
            json.dump(payload, open(p, "w"))
            with self.assertRaises(SaveError):
                sm.load(1, DATA)


class TestWorld(unittest.TestCase):
    def test_paths_between_all_towns(self):
        for a in DATA.towns:
            for b in DATA.towns:
                path, km = WORLD.shortest_path(a, b)
                self.assertIsNotNone(path)

    def test_mapgen_deterministic_and_exits(self):
        for lid in DATA.locations:
            m1 = mapgen.generate(DATA, WORLD, lid)
            m2 = mapgen.generate(DATA, WORLD, lid)
            self.assertEqual(m1.tiles, m2.tiles)
            self.assertEqual(len(m1.exits), len(WORLD.neighbors(lid)))
            self.assertFalse(m1.solid(*m1.entry), lid)
            for e in m1.exits:
                self.assertFalse(m1.solid(e["x"], e["y"]), f"{lid} exit to {e['to']} blocked")

    def test_town_buildings_have_interiors(self):
        for tid in DATA.towns:
            m = mapgen.generate(DATA, WORLD, tid)
            for b in m.buildings.values():
                im = mapgen.generate_interior(DATA, tid, b)
                exits = [o for o in im.objects if o["kind"] == "exit_door"]
                self.assertEqual(len(exits), 1)
                self.assertFalse(im.solid(*im.entry))


class TestTravel(unittest.TestCase):
    def test_journey_consumes_and_arrives(self):
        s = new_state(seed=5)
        ok, _ = travel.start(s, WORLD, "meadowrun")
        self.assertTrue(ok)
        food_items = s.player.inventory.count("ration") + s.player.inventory.count("bread")
        for _ in range(200):
            if s.travel["pending_event"]:
                ev = travel.event_by_id(s, s.travel["pending_event"])
                travel.choose(s, len(ev["choices"]) - 1)
                continue
            if s.travel["arrived"]:
                break
            travel.step(s)
        self.assertTrue(s.travel["arrived"])
        self.assertGreater(s.clock.total_minutes, 8 * 60)
        travel.arrive(s)
        self.assertEqual(s.location, "meadowrun")
        self.assertIn("meadowrun", s.discovered)
        self.assertEqual(s.mode, "local")

    def test_cannot_travel_to_non_neighbor(self):
        s = new_state()
        ok, _ = travel.start(s, WORLD, "shattered_spire")
        self.assertFalse(ok)

    def test_auto_consume_respects_rations(self):
        s = new_state()
        travel.start(s, WORLD, "meadowrun")
        s.player.food = 30
        s.settings["rations"] = "meager"
        travel.auto_consume(s)
        self.assertEqual(s.player.food, 30)  # above meager threshold
        s.settings["rations"] = "normal"
        travel.auto_consume(s)
        self.assertGreater(s.player.food, 30)

    def test_every_event_choice_executes(self):
        """Every choice in every travel event must run without error (with requirements satisfied)."""
        for ev in DATA.travel_events:
            for i, ch in enumerate(ev["choices"]):
                s = new_state(seed=i + 1)
                s.gold = 500
                for it in ("ration", "bandage", "pickaxe"):
                    s.player.inventory.add(it, 5)
                travel.start(s, WORLD, "meadowrun")
                s.travel["pending_event"] = ev["id"]
                travel.choose(s, i)
                self.assertTrue(s.player.alive or s.player.hp > 0)

    def test_skirmish_outcomes(self):
        s = new_state(seed=3)
        res = skirmish.resolve(s, "wolf", 1)
        self.assertIn(res["outcome"], ("victory", "defeat"))
        s = new_state(seed=3)
        s.gold = 100
        res = skirmish.resolve(s, "stone_brute", 4)
        self.assertEqual(res["outcome"], "defeat")
        self.assertLess(s.gold, 100)
        self.assertGreater(s.player.hp, 0)


class TestEffects(unittest.TestCase):
    def test_requirements(self):
        s = new_state()
        s.gold = 3
        self.assertFalse(effects.requirement_met(s, {"gold": 5}))
        self.assertTrue(effects.requirement_met(s, {"item": ["ration", 1]}))

    def test_refill_water(self):
        s = new_state()
        n = effects.refill_water(s)
        self.assertEqual(s.player.inventory.count("water"), effects.WATER_CARRY_LIMIT)
        self.assertEqual(n, effects.WATER_CARRY_LIMIT - 4)

    def test_sleep(self):
        s = new_state()
        s.clock.minutes = 22 * 60
        hours, _ = timeflow.sleep_until_morning(s)
        self.assertEqual(s.clock.hour, 7)
        self.assertAlmostEqual(hours, 9)


if __name__ == "__main__":
    unittest.main()


class TestReachability(unittest.TestCase):
    def test_all_exits_reachable_from_entry(self):
        from collections import deque
        for lid in DATA.locations:
            m = mapgen.generate(DATA, WORLD, lid)
            seen = {m.entry}
            q = deque([m.entry])
            while q:
                x, y = q.popleft()
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    n = (x + dx, y + dy)
                    if n not in seen and m.inb(*n) and not m.solid(*n):
                        seen.add(n)
                        q.append(n)
            for e in m.exits:
                self.assertIn((e["x"], e["y"]), seen, f"{lid}: exit to {e['to']} unreachable")
            if lid in DATA.towns:
                for b in m.buildings.values():
                    dx, dy = b["door"]
                    self.assertIn((dx, dy + 1), seen, f"{lid}: door of {b['label']} unreachable")
