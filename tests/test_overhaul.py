"""Combat overhaul: magic system, faster combat, smarter enemies, encounters, towns/crime/conquest, morale and
prisoners. Run: python -m unittest -v"""
import os
import random
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from game.core.rng import stable_rng  # noqa: E402
from game.gameplay.combat import CombatWorld  # noqa: E402
from game.gameplay.entity import Actor  # noqa: E402
from game.set_system import combat as rules  # noqa: E402
from game.set_system import crime, economy, encounters, morale, spells  # noqa: E402
from tests.test_combat import DATA, FakeGame, arena, new_state, run  # noqa: E402

LOOK = {"race": "human", "skin": [190, 150, 110], "hair": [40, 30, 20], "shirt": [60, 90, 150], "pants": [60, 50, 40]}


def world(seed=1):
    st = new_state()
    m = arena()
    w = CombatWorld(FakeGame(), st, m, random.Random(seed))
    pc = w.add_player(Actor(8 * 16 + 8, 11 * 16 + 12, LOOK, 70))
    st.player.mana = 999
    return st, m, w, pc


class TestMagicModel(unittest.TestCase):
    def test_every_sub_belongs_to_its_element(self):
        m = DATA.magic
        for eid, el in m["elements"].items():
            for s in el["subs"]:
                self.assertEqual(m["subelements"][s]["element"], eid)
        self.assertEqual(m["subelements"]["lightning"]["element"], "air")
        self.assertEqual(m["subelements"]["gravity"]["element"], "earth")
        self.assertIn("mending", m["elements"]["light"]["subs"])

    def test_element_only_spells(self):
        for eid, el in DATA.magic["elements"].items():
            for stat in el["effects"]:
                p = spells.compute(DATA, {"element": eid, "move": "projectile", "stat": stat, "tier": 1})
                self.assertGreater(p["mana"], 0)
                self.assertIsNone(p["sub_id"])

    def test_sub_must_match_element(self):
        with self.assertRaises(spells.SpellError):
            spells.validate(DATA, {"element": "fire", "sub": "ice", "move": "beam", "stat": "damage", "tier": 1})

    def test_identities(self):
        def power(el, stat, sub=None):
            return spells.compute(DATA, {"element": el, "sub": sub, "move": "projectile", "stat": stat, "tier": 1})["power"]
        self.assertGreater(power("fire", "damage"), power("water", "damage"))
        self.assertGreater(power("light", "heal"), power("water", "heal"))
        self.assertGreater(power("earth", "defense"), power("light", "defense"))
        air = spells.compute(DATA, {"element": "air", "move": "projectile", "stat": "damage", "tier": 1})
        earth = spells.compute(DATA, {"element": "earth", "move": "projectile", "stat": "damage", "tier": 1})
        self.assertGreater(air["speed"], earth["speed"])

    def test_size_scales_cost_and_area_with_a_cap(self):
        base = {"element": "fire", "move": "area", "stat": "damage", "tier": 1}
        small = spells.compute(DATA, dict(base, size=0.5))
        big = spells.compute(DATA, dict(base, size=3.0))
        self.assertGreater(big["mana"], small["mana"] * 3)
        self.assertGreater(big["area"], small["area"])
        self.assertLessEqual(big["area"], DATA.magic["movements"]["area"]["max_area"])
        with self.assertRaises(spells.SpellError):
            spells.validate(DATA, dict(base, size=9.0))

    def test_focus_changes_numbers(self):
        base = {"element": "water", "move": "projectile", "stat": "damage", "tier": 1}
        plain = spells.compute(DATA, dict(base, focus="balanced"))
        cheap = spells.compute(DATA, dict(base, focus="efficiency"))
        strong = spells.compute(DATA, dict(base, focus="power"))
        self.assertLess(cheap["mana"], plain["mana"])
        self.assertGreater(strong["power"], plain["power"])

    def test_old_spells_migrate(self):
        old = {"name": "Old Bolt", "sub": "plasma", "move": "projectile", "stat": "damage", "tier": 1}
        sp = spells.normalize(DATA, old)
        self.assertEqual((sp["element"], sp["focus"], sp["size"]), ("fire", "balanced", 1.0))
        st = new_state()
        d = st.to_dict()
        d["spellbook"] = [old]
        st2 = type(st).from_dict(DATA, d, st.memory)
        self.assertEqual(st2.spellbook[0]["element"], "fire")

    def test_no_long_cooldowns(self):
        for mv, d in DATA.magic["movements"].items():
            self.assertLessEqual(d["cooldown"], 1.2, mv)


class TestNewMovements(unittest.TestCase):
    def test_chain_hits_several(self):
        st, m, w, pc = world()
        foes = [w.spawn_enemy("bandit_cutthroat", pc.x + 50 + i * 30, pc.y) for i in range(3)]
        for f in foes:
            f.ai = None
        pc.aim = (1.0, 0.0)
        ok, msg = w.cast(pc, {"name": "Arc", "element": "air", "sub": "lightning", "move": "chain", "stat": "damage", "tier": 1})
        self.assertTrue(ok, msg)
        self.assertGreaterEqual(sum(f.hp < f.max_hp for f in foes), 2)

    def test_trap_waits_then_springs(self):
        st, m, w, pc = world()
        pc.aim = (1.0, 0.0)
        w.cast(pc, {"name": "Snare", "element": "fire", "move": "trap", "stat": "damage", "tier": 1})
        trap = next(e for e in w.effects if e.kind == "trap")
        run(w, m, 1.0)
        self.assertFalse(trap.hit)
        foe = w.spawn_enemy("bandit_cutthroat", trap.x, trap.y)
        foe.ai = None
        run(w, m, 0.3)
        self.assertLess(foe.hp, foe.max_hp)

    def test_barrier_stops_missiles(self):
        st, m, w, pc = world()
        pc.aim = (1.0, 0.0)
        w.cast(pc, {"name": "Wall", "element": "earth", "move": "barrier", "stat": "defense", "tier": 1, "size": 2.0})
        archer = w.spawn_enemy("bandit_archer", pc.x + 120, pc.y)
        archer.alerted = True
        hp0 = st.player.hp
        run(w, m, 4.0)
        self.assertEqual(st.player.hp, hp0)

    def test_self_heal(self):
        st, m, w, pc = world()
        st.player.hp = 10
        ok, _ = w.cast(pc, {"name": "Mend", "element": "light", "sub": "mending", "move": "self", "stat": "heal", "tier": 1})
        self.assertTrue(ok)
        self.assertGreater(st.player.hp, 10)

    def test_persistent_effects_capped(self):
        st, m, w, pc = world()
        for _ in range(6):
            w.spell_cd.clear()
            w.cast(pc, {"name": "Snare", "element": "fire", "move": "trap", "stat": "damage", "tier": 1})
            pc.set_state("idle")
            run(w, m, 0.05)
        self.assertLessEqual(sum(1 for e in w.effects if e.kind == "trap"), spells.MAX_PERSISTENT)


class TestFasterCombat(unittest.TestCase):
    def test_cycles_are_faster(self):
        p = rules.attack_profile(DATA, {}, {}, "longsword")
        w = DATA.weapons["longsword"]
        old_cycle = 1.0 / (w["speed"] * 1.1)
        self.assertLess(p["windup"] + p["active"] + p["recovery"], old_cycle * 0.8)

    def test_recovery_can_be_cancelled(self):
        st, m, w, pc = world()
        st.player.inventory.add("longsword_greyvein")
        st.player.equipment["weapon"] = "longsword_greyvein"
        w.attack(pc)
        while pc.state != "recovery":
            run(w, m, 1 / 60)
        pc.combo_window = 0
        pc.state_t = pc.profile["recovery"] * 0.5
        self.assertTrue(w.attack(pc))
        self.assertEqual(pc.state, "windup")

    def test_cast_flows_into_attack(self):
        st, m, w, pc = world()
        w.cast(pc, st.spellbook[0])
        self.assertEqual(pc.state, "cast")
        self.assertTrue(w.attack(pc))


class TestSmarterEnemies(unittest.TestCase):
    def test_caster_heals_hurt_ally(self):
        st, m, w, pc = world()
        shaman = w.spawn_enemy("thornblood_shaman", pc.x + 120, pc.y)
        ally = w.spawn_enemy("thornblood_raider", pc.x + 130, pc.y + 10)
        ally.ai = None
        ally.hp = ally.max_hp * 0.3
        shaman.alerted = ally.alerted = True
        hp0 = ally.hp
        run(w, m, 4.0)
        self.assertGreater(ally.hp, hp0)

    def test_encounters_mix_and_respect_biome(self):
        rng = stable_rng("t", 1)
        mixed = set()
        for i in range(30):
            mixed.update(encounters.compose(DATA, "bandit_cutthroat", 3, stable_rng("t", i)))
        self.assertGreaterEqual(len(mixed), 3)
        for i in range(20):
            self.assertNotIn("cave_skitterer", encounters.compose(DATA, "stone_brute", 5, stable_rng("b", i), "ruins"))
        self.assertLessEqual(len(encounters.compose(DATA, "cave_skitterer", 5, rng)), encounters.MAX_GROUP)

    def test_morale_breaks(self):
        e = DATA.enemies["bandit_cutthroat"]
        m = morale.update(morale.initial(e), 0.2, allies_down=2, leader_down=False, outnumber=0.5)
        self.assertLessEqual(m, morale.BREAK_POINT)
        self.assertEqual(morale.decide(e, m, 0.2), "surrender")
        self.assertEqual(morale.decide(DATA.enemies["husk"], 0, 0.1), "fight")
        self.assertEqual(morale.decide(DATA.enemies["hollow_captain"], 10, 0.2), "flee")

    def test_surrender_in_battle(self):
        st, m, w, pc = world()
        foes = [w.spawn_enemy("bandit_cutthroat", pc.x + 60 + i * 12, pc.y, group="g") for i in range(3)]
        for f in foes:
            f.alerted = True
        foes[0].hp = foes[0].max_hp * 0.15
        for f in foes[1:]:
            w.kill(f, pc)
        run(w, m, 1.5)
        self.assertTrue(getattr(foes[0], "surrendered", False) or foes[0].fled)


class TestPrisoners(unittest.TestCase):
    def test_needs_somewhere_to_hold_them(self):
        st = new_state()
        self.assertFalse(morale.can_hold_prisoners(st))
        self.assertIn("nowhere", morale.resolve(st, "bandit_cutthroat", "prisoner"))
        st.property["brackenford"] = {"building": "b5", "bought": 0, "storage": {}}
        morale.resolve(st, "bandit_cutthroat", "prisoner")
        self.assertEqual(len(morale.prisoners(st)), 1)

    def test_loyalty_grows_and_resentment_escapes(self):
        st = new_state()
        st.property["brackenford"] = {"building": "b5", "bought": 0, "storage": {}}
        morale.resolve(st, "bandit_cutthroat", "prisoner")
        p = morale.prisoners(st)[0]
        st.player.inventory.add("ration", 20)
        for _ in range(12):
            morale.daily(st)
            morale.talk(st, p["id"])
            st.clock.minutes += 1440
        self.assertGreaterEqual(p["loyalty"], morale.RECRUIT_LOYALTY)
        self.assertIn("joins", morale.recruit_prisoner(st, p["id"]))
        self.assertEqual(len(morale.retainers(st)), 1)
        morale.resolve(st, "bandit_cutthroat", "prisoner")
        q = morale.prisoners(st)[0]
        morale.set_treatment(st, q["id"], False)
        st.player.inventory.remove("ration", st.player.inventory.count("ration"))
        for _ in range(15):
            morale.daily(st)
        self.assertEqual(morale.prisoners(st), [])     # escaped

    def test_choices_are_deterministic_and_released_goodwill(self):
        st = new_state()
        before = st.reputation["hollow"]
        morale.resolve(st, "bandit_cutthroat", "release")
        self.assertGreater(st.reputation["hollow"], before)


class TestTownsAndCrime(unittest.TestCase):
    def test_every_town_has_an_equipment_shop(self):
        gear = {"armorer", "smithy", "outfitter", "forge"}
        for t in DATA.towns.values():
            self.assertTrue(gear & set(t["shops"] + t["buildings"]), t["id"])

    def test_stock_scales_with_town(self):
        st = new_state()
        small = economy.stock_def(st, "brackenford", "outfitter")
        big = economy.stock_def(st, "thornhollow", "outfitter")
        self.assertIn("axe_greyvein", big)            # Thornblood specialities
        self.assertNotIn("axe_greyvein", small)
        self.assertGreater(len(economy.stock_def(st, "velmora", "armorer")), len(DATA.shops["armorer"]["stock"]))

    def test_theft_bounty_and_fine(self):
        st = new_state()
        st.location = "brackenford"
        before = st.reputation["crown"]
        crime.crime(st, "theft", 20, ["hessa"])
        self.assertGreater(crime.bounty(st, "brackenford"), 0)
        self.assertLess(st.reputation["crown"], before)
        st.gold = 1000
        ok, _ = crime.pay_fine(st, "brackenford")
        self.assertTrue(ok)
        self.assertEqual(crime.bounty(st, "brackenford"), 0)

    def test_containers_once_a_day(self):
        st = new_state()
        msgs, v = crime.loot_container(st, "brackenford", "obj1")
        msgs2, v2 = crime.loot_container(st, "brackenford", "obj1")
        self.assertEqual(v2, 0)
        self.assertIn("already", msgs2[0])

    def test_seize_town(self):
        st = new_state()
        ok, why = crime.can_seize(st, "brackenford", guards_standing=2, guards_seen=3)
        self.assertFalse(ok)
        ok, _ = crime.can_seize(st, "brackenford", guards_standing=0, guards_seen=3)
        self.assertTrue(ok)
        before = st.reputation["crown"]
        crime.seize(st, "brackenford")
        self.assertEqual(crime.owner(st, "brackenford"), "player")
        self.assertLess(st.reputation["crown"], before - 30)
        price_owned = economy.buy_price(st, "brackenford", "provisioner", "ration")
        gold0 = st.gold
        crime.daily(st, random.Random(99))
        self.assertGreater(st.gold, gold0)
        st2 = new_state()
        self.assertLess(price_owned, economy.buy_price(st2, "brackenford", "provisioner", "ration") + 1)

    def test_guards_respond_to_crime(self):
        st, m, w, pc = world()
        st.location = "brackenford"
        guard = w.add_townsfolk(None, pc.x + 60, pc.y, LOOK, random.Random(3), guard=True)
        victim = w.add_townsfolk(DATA.npcs["hessa"], pc.x + 14, pc.y, LOOK, random.Random(4))
        w.intent = True
        pc.aim = (1.0, 0.0)
        for _ in range(120):
            w.attack(pc)
            w.update(1 / 60, m)
            if victim.hp < victim.max_hp:
                break
        self.assertIn(pc.cid, guard.grudge)
        self.assertGreater(crime.bounty(st, "brackenford"), 0)


class TestSaves(unittest.TestCase):
    def test_new_state_survives_save_load(self):
        from game.core.game import Game
        d = tempfile.mkdtemp()
        g = Game(headless=True, save_dir=d)
        g.new_game("Tess", "human", dict(LOOK, hair_style=0), "they/them")
        st = g.state
        st.property["brackenford"] = {"building": "b5", "bought": 0, "storage": {}}
        morale.resolve(st, "bandit_cutthroat", "prisoner")
        st.location = "brackenford"
        crime.crime(st, "theft", 10, [])
        st.spell_drafts.append({"name": "Vast Fire Blast", "element": "fire", "sub": None, "move": "area",
                                "stat": "damage", "tier": 1, "focus": "area", "size": 2.5})
        self.assertTrue(g.save_game(3))
        g.load_game(3)
        self.assertEqual(len(morale.prisoners(g.state)), 1)
        self.assertGreater(crime.bounty(g.state, "brackenford"), 0)
        self.assertEqual(g.state.spell_drafts[-1]["size"], 2.5)


if __name__ == "__main__":
    unittest.main()
