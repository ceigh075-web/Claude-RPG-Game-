"""Universal targeting, reactions and consequences of violence against non-hostile characters.
Run: python -m unittest -v"""
import random
import unittest

from game.gameplay import npcs as npc_mod
from game.gameplay.combat import CombatWorld
from game.gameplay.entity import Actor
from game.local_ai import context
from game.set_system import aggression, companions as comp_mod, factions, relationships as rel
from tests.test_combat import DATA, FakeGame, arena, new_state

LOOK = {"race": "human", "skin": [190, 150, 110], "hair": [40, 30, 20], "shirt": [60, 90, 150], "pants": [60, 50, 40]}


def world(seed=1):
    st = new_state()
    st.location = "velmora"
    m = arena()
    w = CombatWorld(FakeGame(), st, m, random.Random(seed))
    pc = w.add_player(Actor(8 * 16 + 8, 11 * 16 + 12, LOOK, 70))
    st.player.inventory.add("longsword_greyvein")
    st.player.equipment["weapon"] = "longsword_greyvein"
    return st, m, w, pc


def swing_until(w, m, pc, tgt, cond, seconds=20, dt=1 / 60):
    for _ in range(int(seconds / dt)):
        if cond():
            return True
        pc.x, pc.y = tgt.x - 12, tgt.y
        pc.aim = (1.0, 0.0)
        pc.facing = "right"
        w.attack(pc)
        w.state.player.hp = w.state.player.max_hp
        w.update(dt, m)
    return cond()


def make_companion(st, w, npc_id, x, y):
    npc = DATA.npcs[npc_id]
    st.flags[f"recruited:{npc_id}"] = True
    st.companions[npc_id] = {"char": comp_mod.build_character(DATA, npc), "task": "follow", "active": True,
                             "joined": 0, "wait_at": None, "downed": False}
    return w.add_companion(npc_id, st.companions[npc_id]["char"], x, y, LOOK)


class TestRules(unittest.TestCase):
    def test_reactions_follow_personality_and_are_deterministic(self):
        brave = dict(DATA.npcs["queen_aldra"], personality=dict(DATA.npcs["queen_aldra"]["personality"],
                                                                 aggression=9, confidence=9))
        timid = dict(DATA.npcs["marta"], personality=dict(DATA.npcs["marta"]["personality"], aggression=1,
                                                           confidence=2, sociability=2), skills={})
        self.assertEqual(aggression.reaction(brave, 1.0), "fight")
        self.assertEqual(aggression.reaction(timid, 1.0), "flee")
        self.assertEqual(aggression.reaction(timid, 0.1, cornered=True), "yield")
        for npc in DATA.npcs.values():
            self.assertEqual(aggression.reaction(npc, 0.6), aggression.reaction(npc, 0.6))

    def test_nobody_is_protected_by_default(self):
        self.assertFalse(aggression.PROTECTED)
        for nid, npc in DATA.npcs.items():
            self.assertTrue(aggression.can_kill(new_state(), nid), nid)
            self.assertFalse(npc.get("protected", False))

    def test_assault_consequences(self):
        st = new_state()
        st.location = "velmora"
        before = factions.rep(st, "crown")
        aggression.on_assault(st, "hessa")
        r = rel.get(st, "hessa")
        self.assertLess(r["trust"], 0)
        self.assertLess(factions.rep(st, "crown"), before)
        self.assertTrue(aggression.grudge_active(st, "hessa"))
        self.assertTrue(any(m["event_type"] == "assault" for m in st.memory.about("hessa", 10)))

    def test_defeat_keeps_named_npcs_alive_but_home(self):
        st = new_state()
        npc = DATA.npcs["hessa"]
        aggression.on_defeat(st, "hessa")
        self.assertTrue(npc_mod.is_alive(st, "hessa"))
        self.assertTrue(npc_mod.recovering(st, "hessa"))
        self.assertNotIn("hessa", [n["id"] for n, _ in npc_mod.present_npcs(st, npc["home"], "town")])
        st.clock.minutes += (aggression.INJURY_DAYS + 1) * 1440
        self.assertFalse(npc_mod.recovering(st, "hessa"))

    def test_killing_is_permanent_and_known(self):
        st = new_state()
        st.location = "velmora"
        aggression.on_kill(st, "queen_aldra")
        self.assertFalse(npc_mod.is_alive(st, "queen_aldra"))
        self.assertTrue(st.flags.get("succession:crown"))
        self.assertIn("Queen Aldra Venn", context.dead_npcs(st))
        witness = DATA.npcs["marta"]
        facts = " ".join(context.world_facts(st, witness))
        self.assertIn("killed", facts)
        aggression.on_kill(st, "black_ren")
        self.assertTrue(st.flags.get("hollow_broken"))

    def test_killing_a_shopkeeper_hands_the_shop_to_a_stranger(self):
        st = new_state()
        keeper = next(n for n in DATA.npcs.values() if n.get("shop"))
        aggression.on_kill(st, keeper["id"])
        found, _ = npc_mod.shopkeeper(st, keeper["home"], keeper["shop"])
        self.assertTrue(found is None or found["id"] != keeper["id"])


class TestRuntime(unittest.TestCase):
    def test_townsfolk_are_safe_without_intent_and_attackable_with_it(self):
        st, m, w, pc = world()
        npc = w.add_townsfolk(DATA.npcs["hessa"], pc.x + 12, pc.y, LOOK, random.Random(2))
        swing_until(w, m, pc, npc, lambda: False, seconds=2)
        self.assertEqual(npc.hp, npc.max_hp, "a peaceful swing must not hurt bystanders")
        w.intent = True
        self.assertTrue(swing_until(w, m, pc, npc, lambda: npc.hp < npc.max_hp, seconds=4))
        self.assertIn(pc.cid, npc.grudge)
        self.assertNotEqual(npc.ai.mode, "calm")
        w.intent = False   # once they're hostile, they're a normal foe
        hp = npc.hp
        if npc.alive:
            swing_until(w, m, pc, npc, lambda: npc.hp < hp, seconds=4)
            self.assertLess(npc.hp, hp)

    def test_defeat_then_execution(self):
        st, m, w, pc = world()
        npc = w.add_townsfolk(DATA.npcs["hessa"], pc.x + 12, pc.y, LOOK, random.Random(2))
        w.intent = True
        self.assertTrue(swing_until(w, m, pc, npc, lambda: npc.downed, seconds=40))
        self.assertFalse(npc.killed)
        self.assertTrue(npc_mod.is_alive(st, "hessa"))
        w.intent = False
        swing_until(w, m, pc, npc, lambda: npc.killed, seconds=3)
        self.assertFalse(npc.killed, "finishing blows need hostile intent")
        w.intent = True
        self.assertTrue(swing_until(w, m, pc, npc, lambda: npc.killed, seconds=3))
        self.assertFalse(npc_mod.is_alive(st, "hessa"))

    def test_enemies_ignore_townsfolk(self):
        st, m, w, pc = world()
        npc = w.add_townsfolk(DATA.npcs["hessa"], pc.x + 60, pc.y, LOOK, random.Random(2))
        e = w.spawn_enemy("bandit_cutthroat", pc.x + 75, pc.y)
        self.assertFalse(w.hostile_between(e, npc))
        self.assertIn(pc, w.foes_of(e))
        self.assertNotIn(npc, w.foes_of(e))

    def test_companions_can_be_attacked_and_react(self):
        st, m, w, pc = world()
        comp = make_companion(st, w, "garrow", pc.x + 12, pc.y)
        self.assertNotIn(comp, w.foes_of(pc))
        w.intent = True
        self.assertTrue(swing_until(w, m, pc, comp, lambda: comp.hp < comp.max_hp, seconds=4))
        self.assertIn(pc.cid, comp.grudge)
        self.assertTrue(any(m_["event_type"] == "assault" for m_ in st.memory.about("garrow", 10)))

    def test_companion_reactions_depend_on_personality(self):
        st = new_state()
        victim = DATA.npcs["hessa"]
        results = {cid: aggression.companion_reaction(st, cid, victim_npc=victim)[0] for cid in DATA.npcs}
        self.assertTrue(set(results.values()) <= {"join", "stand", "object", "defend"})
        self.assertGreater(len(set(results.values())), 1, "everyone reacting the same way means personality is ignored")
        self.assertEqual(results, {cid: aggression.companion_reaction(st, cid, victim_npc=victim)[0] for cid in DATA.npcs})

    def test_a_companion_who_fought_you_decides_whether_to_stay(self):
        st, m, w, pc = world()
        comp = make_companion(st, w, "garrow", pc.x + 12, pc.y)
        w.intent = True
        swing_until(w, m, pc, comp, lambda: comp.hp < comp.max_hp, seconds=4)
        rel.change(st, "garrow", friendship=-60, trust=-60)
        w.settle_conflicts()
        self.assertNotIn("garrow", st.companions)
        self.assertTrue(npc_mod.is_alive(st, "garrow"))

    def test_same_fight_same_outcome(self):
        def run():
            st, m, w, pc = world(seed=5)
            npc = w.add_townsfolk(DATA.npcs["garrow"], pc.x + 12, pc.y, LOOK, random.Random(4))
            w.intent = True
            swing_until(w, m, pc, npc, lambda: npc.downed, seconds=30)
            return round(npc.hp, 3), npc.state, npc.ai.mode, [r["event_type"] for r in st.memory.recent(20)]
        self.assertEqual(run(), run())


if __name__ == "__main__":
    unittest.main()
