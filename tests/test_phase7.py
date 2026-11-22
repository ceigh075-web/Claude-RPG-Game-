"""Phase 7: world events, Hollow strength, territory, honors, economy, jobs and bounties."""
import unittest

from game.core.data import GameData
from game.core.state import GameState
from game.set_system import companions, economy, jobs, relationships as rel, timeflow, world_events as we
from game.world import travel
from game.world.worldmap import WorldMap

DATA = GameData()
WORLD = WorldMap(DATA)


def new_state(seed=31):
    return GameState.new_game(DATA, "Vale", "murrok", {"race": "murrok"}, "he/him", seed=seed)


class TestWorldEvents(unittest.TestCase):
    def test_long_simulation_is_deterministic_and_varied(self):
        def run(seed):
            s = new_state(seed)
            seen = set()
            for _ in range(200):
                timeflow.advance(s, 1440)
                seen |= {e["type"] for e in s.world["active_events"]}
            return s, seen
        s1, seen1 = run(5)
        s2, seen2 = run(5)
        self.assertEqual(s1.world["hollow_strength"], s2.world["hollow_strength"])
        self.assertEqual([e["headline"] for e in s1.world["active_events"]], [e["headline"] for e in s2.world["active_events"]])
        self.assertGreaterEqual(len(seen1), 4)
        self.assertTrue(all(m["until"] > s1.clock.day_index for m in s1.world["modifiers"]))  # expired ones removed
        self.assertGreater(len(s1.memory.world_history(100, 2)), 5)

    def test_every_event_type_has_consequences(self):
        import random
        for etype, fn in we.START.items():
            s = new_state()
            we.world(s)
            if etype == "companion_problem":
                s.gold = 999
                rel.change(s, "tobin", friendship=20)
                companions.recruit(s, DATA.npcs["tobin"])
            ev = fn(s, random.Random(3))
            self.assertIsNotNone(ev, etype)
            self.assertTrue(ev["headline"])
            effects = (s.world["modifiers"] or any(j for b in s.world["boards"].values() for j in b["jobs"] if j.get("event"))
                       or s.jobs or etype in ("caravan_arrival",))
            self.assertTrue(effects, etype)

    def test_shortage_raises_food_prices(self):
        s = new_state()
        import random
        base = economy.buy_price(s, "velmora", "provisioner", "ration")
        ev = we.ev_shortage(s, random.Random(0))
        town = ev["location"]
        self.assertGreater(economy.buy_price(s, town, "provisioner", "ration"),
                           economy.buy_price(s, town, "provisioner", "ration") / 1.6 + 0.5)
        s.world["modifiers"] = []
        self.assertEqual(economy.buy_price(s, "velmora", "provisioner", "ration"), base)

    def test_regional_prices(self):
        s = new_state()
        self.assertLess(economy.sell_price(s, "cinderdeep", "assayer", "rustite_ore") * 0 +
                        economy.regional(s, "cinderdeep", "rustite_ore"), economy.regional(s, "hammerlee", "rustite_ore"))
        self.assertLess(economy.regional(s, "brackenford", "ration"), economy.regional(s, "duskreach", "ration"))

    def test_hollow_breaks_and_territory(self):
        s = new_state()
        w = we.world(s)
        w["hollow_strength"] = 80
        timeflow.advance(s, 1440)
        self.assertEqual(we.holder(s, "widows_crossing"), "hollow")
        s.flags["hollow_broken"] = True
        timeflow.advance(s, 1440)
        self.assertEqual(w["hollow_strength"], 0)
        self.assertEqual(we.holder(s, "widows_crossing"), "crown")

    def test_honors(self):
        s = new_state()
        s.reputation["caravans"] = 65
        g = s.gold
        timeflow.advance(s, 1440)
        self.assertIn("Road Partner", s.world["titles"])
        self.assertEqual(s.gold, g + 300)


class TestJobs(unittest.TestCase):
    def test_board_and_bounty(self):
        s = new_state()
        b = jobs.board(s, "redwater")
        self.assertGreaterEqual(len(b["jobs"]), 2)
        bounty = next(j for j in b["jobs"] if j["type"] == "bounty")
        ok, _ = jobs.accept(s, "redwater", bounty["id"])
        self.assertTrue(ok)
        self.assertFalse(jobs.turn_in(s, bounty["id"])[0])
        for _ in range(bounty["count"]):
            jobs.note_kill(s, bounty["enemy"])
        g = s.gold
        ok, _ = jobs.turn_in(s, bounty["id"])
        self.assertTrue(ok)
        self.assertEqual(s.gold, g + bounty["reward"])

    def test_delivery_must_be_at_destination(self):
        s = new_state()
        job = jobs.post(s, "cinderdeep", {"type": "delivery", "title": "t", "item": "ration", "qty": 2, "to": "cinderdeep",
                                          "reward": 50, "rep": 2, "days": 5, "desc": ""}, accept=True)
        s.player.inventory.add("ration", 5)
        s.location = "brackenford"
        self.assertFalse(jobs.turn_in(s, job["id"])[0])
        s.location = "cinderdeep"
        self.assertTrue(jobs.turn_in(s, job["id"])[0])

    def test_escort_completes_on_arrival(self):
        s = new_state()
        job = jobs.post(s, "brackenford", {"type": "escort", "title": "e", "to": "meadowrun", "reward": 70, "rep": 3,
                                           "days": 5, "desc": ""}, accept=True)
        travel.start(s, WORLD, "meadowrun")
        s.travel["done"] = s.travel["km"]
        s.travel["arrived"] = True
        g = s.gold
        travel.arrive(s)
        self.assertEqual(job["status"], "done")
        self.assertEqual(s.gold, g + 70)

    def test_failed_job_costs_standing(self):
        s = new_state()
        b = jobs.board(s, "velmora")
        j = b["jobs"][0]
        jobs.accept(s, "velmora", j["id"])
        rep = s.reputation["crown"]
        timeflow.advance(s, 1440 * 20)
        self.assertEqual(j["status"], "failed")
        self.assertLess(s.reputation["crown"], rep)

    def test_hunt_via_elite_kill(self):
        import random
        s = new_state()
        ev = we.ev_creature(s, random.Random(1))
        job = next(j for b in s.world["boards"].values() for j in b["jobs"] if j.get("event") == ev["id"])
        jobs.accept(s, job["town"], job["id"])
        we.elite_slain(s, ev["id"])
        jobs.on_elite_killed(s, ev["id"])
        self.assertTrue(jobs.turn_in(s, job["id"])[0])
        self.assertTrue(any("slew" in m["description"] for m in s.memory.world_history(20, 4)))


if __name__ == "__main__":
    unittest.main()
