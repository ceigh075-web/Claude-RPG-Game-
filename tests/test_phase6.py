"""Phase 6: recruitment, squad, companion combat, shared needs, bonds, reactions, saves."""
import math
import random
import tempfile
import unittest

from game.core.data import GameData
from game.core.save import SaveManager
from game.core.state import GameState
from game.gameplay.combat import CombatWorld
from game.gameplay.entity import Actor
from game.set_system import companions as comp, factions, favors, relationships as rel, skirmish, timeflow
from game.world import mapgen

DATA = GameData()


class FakeGame:
    data = DATA


def new_state():
    return GameState.new_game(DATA, "Ash", "human", {"race": "human"}, "they/them", seed=21)


def recruit(s, nid):
    npc = DATA.npcs[nid]
    s.gold = 10000
    rel.change(s, nid, friendship=100, trust=100, respect=100)
    for fac in npc["recruit"].get("rep", {}):
        s.reputation[fac] = 100
    for sk, v in npc["recruit"].get("skill", {}).items():
        s.player.skills[sk] = v
    if "favor" in npc["recruit"]:
        s.favors[npc["recruit"]["favor"]] = {"status": "done", "started": 0, "npc": nid}
    return comp.recruit(s, npc)


class TestRecruit(unittest.TestCase):
    def test_every_npc_can_be_recruited(self):
        for nid in DATA.npcs:
            s = new_state()
            ok, msg = recruit(s, nid)
            self.assertTrue(ok, f"{nid}: {msg}")
            self.assertIn(nid, s.companions)

    def test_gold_paid_and_squad_limit(self):
        s = new_state()
        s.gold = 1000
        rel.change(s, "fenna", friendship=1)
        ok, _ = comp.recruit(s, DATA.npcs["fenna"])  # 120 marks
        self.assertTrue(ok)
        self.assertEqual(s.gold, 880)
        for nid in ("tobin", "pell", "rennick", "corwin"):
            recruit(s, nid)
        self.assertEqual(len(comp.squad(s)), comp.MAX_SQUAD)
        self.assertFalse(s.companions["corwin"]["active"])  # fifth waits

    def test_leader_succession_history(self):
        s = new_state()
        recruit(s, "queen_aldra")
        self.assertTrue(s.flags.get("succession:crown"))
        self.assertTrue(any("successor" in m["description"] for m in s.memory.world_history(min_importance=5)))

    def test_dismiss_and_free_rejoin(self):
        s = new_state()
        recruit(s, "pell")
        comp.give(s, "pell", "bandage", 1)
        ok, _ = comp.dismiss(s, "pell")
        self.assertTrue(ok)
        self.assertNotIn("pell", s.companions)
        s.gold = 0
        self.assertTrue(comp.recruit(s, DATA.npcs["pell"])[0])

    def test_tasks_and_transfer(self):
        s = new_state()
        recruit(s, "tobin")
        self.assertTrue(comp.set_task(s, "tobin", "wait")[0])
        self.assertNotIn("tobin", comp.squad(s))
        self.assertFalse(comp.set_task(s, "tobin", "guard")[0])  # no outpost yet
        self.assertFalse(comp.set_task(s, "tobin", "home")[0])   # no house yet
        self.assertTrue(comp.set_task(s, "tobin", "follow")[0])
        s.player.inventory.add("longsword_rustite")
        comp.give(s, "tobin", "longsword_rustite")
        from game.set_system import items
        items.equip(s, comp.char(s, "tobin"), "longsword_rustite")
        self.assertEqual(comp.char(s, "tobin").equipment["weapon"], "longsword_rustite")
        ok, _ = comp.take(s, "tobin", "longsword_rustite")
        self.assertIsNone(comp.char(s, "tobin").equipment["weapon"])


class TestNeedsAndBonds(unittest.TestCase):
    def test_companions_eat_shared_supplies(self):
        s = new_state()
        recruit(s, "tobin")
        c = comp.char(s, "tobin")
        s.player.inventory.add("ration", 5)
        timeflow.advance(s, 30 * 60)
        self.assertGreater(c.food, 0)
        self.assertLess(s.player.inventory.count("ration") + c.inventory.count("ration"), 9)

    def test_daily_bonds_form(self):
        s = new_state()
        recruit(s, "fenna")
        recruit(s, "tobin")
        for _ in range(60):
            timeflow.advance(s, 1440)
        b = comp.bond(s, "fenna", "tobin")
        self.assertNotEqual(b["value"], 0)

    def test_reaction_to_killing_own_faction(self):
        s = new_state()
        recruit(s, "fenna")  # caravans
        f0 = rel.get(s, "fenna")["friendship"]
        comp.react_to_kill(s, "caravans")
        self.assertLess(rel.get(s, "fenna")["friendship"], f0)

    def test_skirmish_with_companions_is_easier(self):
        wins_alone = wins_party = 0
        for seed in range(12):
            s = new_state()
            s.rng.seed(seed)
            wins_alone += skirmish.resolve(s, "bandit_cutthroat", 3)["outcome"] == "victory"
            s = new_state()
            s.rng.seed(seed)
            recruit(s, "rennick")
            recruit(s, "fenna")
            wins_party += skirmish.resolve(s, "bandit_cutthroat", 3)["outcome"] == "victory"
        self.assertGreater(wins_party, wins_alone)


class TestCompanionCombat(unittest.TestCase):
    def setup(self):
        s = new_state()
        recruit(s, "rennick")
        m = mapgen.generate_arena(DATA, "grassland", 1)
        m.build_solid_grid()
        w = CombatWorld(FakeGame(), s, m, random.Random(2))
        pc = w.add_player(Actor(8 * 16, 11 * 16, {"race": "human"}, 70))
        cc = w.add_companion("rennick", comp.char(s, "rennick"), pc.x - 20, pc.y, {"race": "human"})
        return s, m, w, pc, cc

    def test_companion_follows_and_fights(self):
        s, m, w, pc, cc = self.setup()
        pc.x += 150
        for _ in range(180):
            w.update(1 / 60, m)
        self.assertLess(math.hypot(cc.x - pc.x, cc.y - pc.y), 60)
        foe = w.spawn_enemy("wolf", pc.x + 40, pc.y)
        foe.alerted = True
        hp0 = foe.hp
        for _ in range(300):
            w.update(1 / 60, m)
        self.assertTrue(foe.hp < hp0 or not foe.alive)

    def test_companion_heals_and_downs_then_recovers(self):
        s, m, w, pc, cc = self.setup()
        ch = comp.char(s, "rennick")
        ch.skills["magic"] = 30
        ch.mana = ch.max_mana
        s.player.hp = 10
        for _ in range(60):
            w.update(1 / 60, m)
        self.assertGreater(s.player.hp, 10)
        foe = w.spawn_enemy("wolf", cc.x + 10, cc.y)
        w.hit(foe, cc, {"damage": 999, "knockback": 0, "stagger": 0}, (foe.x, foe.y))
        self.assertTrue(cc.downed)
        foe.set_state("dead")
        for _ in range(240):
            w.update(1 / 60, m)
        self.assertFalse(cc.downed)
        self.assertGreater(ch.hp, 0)


class TestSave(unittest.TestCase):
    def test_companions_roundtrip(self):
        s = new_state()
        recruit(s, "tobin")
        recruit(s, "fenna")
        comp.bond(s, "tobin", "fenna")["value"] = 33
        with tempfile.TemporaryDirectory() as d:
            sm = SaveManager(d)
            sm.save(s, 1)
            l = sm.load(1, DATA)
        self.assertEqual(set(l.companions), {"tobin", "fenna"})
        self.assertEqual(l.companions["tobin"]["char"].name, "Tobin Reed")
        self.assertEqual(l.bonds, s.bonds)


if __name__ == "__main__":
    unittest.main()
