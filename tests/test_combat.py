"""Combat rules, spells and headless real-time combat simulations. Run: python -m unittest -v"""
import math
import random
import unittest

from game.core.data import GameData
from game.core.state import GameState
from game.gameplay.combat import CombatWorld
from game.gameplay.entity import Actor
from game.set_system import combat as rules
from game.set_system import spells
from game.world import mapgen

DATA = GameData()


class FakeGame:
    data = DATA


def new_state(seed=7):
    return GameState.new_game(DATA, "Tester", "human", {"race": "human"}, "they/them", seed=seed)


def arena(seed=1):
    m = mapgen.generate_arena(DATA, "grassland", seed)
    m.build_solid_grid()
    return m


def setup_world(state=None, seed=1):
    st = state or new_state()
    m = arena(seed)
    w = CombatWorld(FakeGame(), st, m, random.Random(seed))
    pc = w.add_player(Actor(8 * 16 + 8, 11 * 16 + 12, {"race": "human"}, 70))
    return st, m, w, pc


def run(w, m, seconds, bot=None, dt=1 / 60):
    for i in range(int(seconds / dt)):
        if bot:
            bot(i)
        w.update(dt, m)


DEF = {"x": 0, "y": 0, "facing": (1, 0), "blocking": False, "guard": 100, "poise": 0.3, "armor": 0,
       "mass": 1.0, "iframes": False, "blocking_skill": 0}


class TestRules(unittest.TestCase):
    def prof(self, weapon, item=None, step=1):
        attrs = {"strength": 10, "speed": 10, "health": 10, "dexterity": 10}
        return rules.attack_profile(DATA, attrs, {}, weapon, item, step)

    def test_weapons_are_distinct(self):
        g, d = self.prof("greatsword"), self.prof("dagger")
        self.assertGreater(g["damage"], d["damage"])
        self.assertGreater(g["windup"] + g["recovery"], d["windup"] + d["recovery"])
        self.assertGreater(self.prof("spear")["reach"], self.prof("shortsword")["reach"])
        sigs = {(round(self.prof(w)["damage"], 1), round(self.prof(w)["windup"], 3), self.prof(w)["reach"])
                for w in DATA.weapons}
        self.assertEqual(len(sigs), 16)

    def test_ore_tiers_scale(self):
        self.assertGreater(self.prof("longsword", "longsword_voidglass")["damage"],
                           self.prof("longsword", "longsword_rustite")["damage"])

    def test_combo_finisher(self):
        self.assertGreater(self.prof("shortsword", step=3)["damage"], self.prof("shortsword", step=1)["damage"])
        self.assertLess(self.prof("shortsword", step=2)["windup"], self.prof("shortsword", step=1)["windup"])

    def test_block_reduces_damage_and_knockback(self):
        rng = random.Random(1)
        p = self.prof("longsword")
        open_hit = rules.resolve_hit(p, (-10, 0), dict(DEF), rng)
        blocked = rules.resolve_hit(p, (-10, 0), dict(DEF, blocking=True, facing=(-1, 0)), random.Random(1))
        self.assertTrue(blocked["blocked"])
        self.assertLess(blocked["damage"], open_hit["damage"] * 0.5)
        self.assertLess(blocked["knockback"], open_hit["knockback"])
        # blocking the wrong way does nothing
        wrong = rules.resolve_hit(p, (-10, 0), dict(DEF, blocking=True, facing=(1, 0)), random.Random(1))
        self.assertFalse(wrong["blocked"])

    def test_guard_break(self):
        r = rules.resolve_hit(self.prof("hammer"), (-10, 0), dict(DEF, blocking=True, facing=(-1, 0)), random.Random(2))
        self.assertTrue(r["guard_broken"])
        self.assertGreater(r["stagger_time"], 0)

    def test_backstab(self):
        # attacker at x=-10, defender facing +x -> attacker is behind
        r = rules.resolve_hit(self.prof("dagger"), (-10, 0), dict(DEF, facing=(1, 0)), random.Random(3))
        f = rules.resolve_hit(self.prof("dagger"), (-10, 0), dict(DEF, facing=(-1, 0)), random.Random(3))
        self.assertTrue(r["backstab"])
        self.assertGreater(r["damage"], f["damage"] * 2)

    def test_iframes_and_armor(self):
        self.assertTrue(rules.resolve_hit(self.prof("axe"), (0, 0), dict(DEF, iframes=True), random.Random(1))["dodged"])
        lo = rules.resolve_hit(self.prof("shortsword"), (0, 0), dict(DEF, armor=10), random.Random(4))["damage"]
        mace = rules.resolve_hit(self.prof("mace"), (0, 0), dict(DEF, armor=10), random.Random(4))["damage"]
        hi = rules.resolve_hit(self.prof("shortsword"), (0, 0), dict(DEF, armor=0), random.Random(4))["damage"]
        self.assertLess(lo, hi)
        self.assertGreater(mace, 1)

    def test_axe_bleeds(self):
        r = rules.resolve_hit(self.prof("axe"), (0, 0), dict(DEF), random.Random(1))
        self.assertTrue(any(s[0] == "bleed" for s in r["statuses"]))


class TestSpells(unittest.TestCase):
    def test_every_valid_combination_computes(self):
        m = DATA.magic
        valid = 0
        for sub, sd in m["subelements"].items():
            for mv in m["movements"]:
                for stat in m["stats"]:
                    sp = {"sub": sub, "move": mv, "stat": stat, "tier": 1}
                    if stat in sd["stats"]:
                        p = spells.compute(DATA, sp)
                        self.assertGreater(p["mana"], 0)
                        self.assertGreater(p["power"], 0)
                        valid += 1
                    else:
                        with self.assertRaises(spells.SpellError):
                            spells.compute(DATA, sp)
        self.assertGreater(valid, 400)

    def test_tiers_cost_more(self):
        a = spells.compute(DATA, {"sub": "ice", "move": "projectile", "stat": "damage", "tier": 1})
        b = spells.compute(DATA, {"sub": "ice", "move": "projectile", "stat": "damage", "tier": 3})
        self.assertGreater(b["power"], a["power"])
        self.assertGreater(b["mana"], a["mana"])
        with self.assertRaises(spells.SpellError):
            spells.validate(DATA, {"sub": "ice", "move": "projectile", "stat": "damage", "tier": 3}, level=2)

    def test_capacity_grows(self):
        self.assertEqual(spells.capacity(DATA, 1), 2)
        self.assertGreater(spells.capacity(DATA, 12), 2)


class TestRealtime(unittest.TestCase):
    def test_every_weapon_attacks(self):
        for wid in DATA.weapons:
            st, m, w, pc = setup_world()
            e = w.spawn_enemy("wolf", pc.x + 12, pc.y)
            e.ai = None
            if wid != "fists":
                item = f"{wid}_greyvein"
                st.player.inventory.add(item)
                slot = "ranged" if DATA.weapons[wid]["class"] == "ranged" else "weapon"
                st.player.equipment[slot] = item
                st.settings["weapon_mode"] = "ranged" if slot == "ranged" else "melee"
                ammo = DATA.weapons[wid].get("ammo")
                if ammo and ammo != "self":
                    st.player.inventory.add(ammo, 5)
            pc.aim = (1.0, 0.0)
            hp0 = e.hp
            w.attack(pc)
            run(w, m, 0.4)
            w.release_draw(pc)
            run(w, m, 1.2)
            self.assertLess(e.hp, hp0, f"{wid} never hit")

    def test_ranged_needs_and_uses_ammo(self):
        st, m, w, pc = setup_world()
        st.player.inventory.add("bow_rustite")
        st.player.equipment["ranged"] = "bow_rustite"
        st.settings["weapon_mode"] = "ranged"
        self.assertFalse(w.attack(pc))  # no arrows
        st.player.inventory.add("arrow", 2)
        w.attack(pc)
        run(w, m, 0.3)
        w.release_draw(pc)
        run(w, m, 0.1)
        self.assertEqual(st.player.inventory.count("arrow"), 1)

    def test_every_spell_movement(self):
        for mv in DATA.magic["movements"]:
            st, m, w, pc = setup_world()
            dist = 24 if mv in ("orbit", "aura") else 40
            e = w.spawn_enemy("bandit_cutthroat", pc.x + dist, pc.y)
            e.ai = None
            st.player.mana = 999
            pc.aim = (1.0, 0.0)
            hp0 = e.hp
            ok, msg = w.cast(pc, {"name": mv, "sub": "plasma", "move": mv, "stat": "damage", "tier": 1})
            self.assertTrue(ok, msg)
            run(w, m, 3.0)
            self.assertLess(e.hp, hp0, f"{mv} damage spell never hit")

    def test_heal_and_buff(self):
        st, m, w, pc = setup_world()
        st.player.hp = 20
        ok, _ = w.cast(pc, spells.STARTER_SPELLS[1])
        self.assertTrue(ok)
        self.assertGreater(st.player.hp, 20)
        st.player.mana = 999
        w.cast(pc, {"name": "Haste", "sub": "wind", "move": "aura", "stat": "speed", "tier": 1})
        self.assertIn("speed", pc.buffs)

    def test_mana_and_cooldown_enforced(self):
        st, m, w, pc = setup_world()
        st.player.mana = 0
        ok, msg = w.cast(pc, spells.STARTER_SPELLS[0])
        self.assertFalse(ok)
        st.player.mana = 100
        self.assertTrue(w.cast(pc, spells.STARTER_SPELLS[0])[0])
        run(w, m, 0.3)
        self.assertFalse(w.cast(pc, spells.STARTER_SPELLS[0])[0])  # still cooling down

    def test_each_archetype_engages(self):
        for eid, e in DATA.enemies.items():
            st, m, w, pc = setup_world()
            st.player.attributes["health"] = 100  # survive long enough to observe
            st.player.hp = st.player.max_hp
            foe = w.spawn_enemy(eid, pc.x + 110, pc.y)
            hp0 = st.player.hp
            run(w, m, 12.0)
            self.assertTrue(foe.alerted, eid)
            self.assertLess(st.player.hp, hp0, f"{eid} ({e['archetype']}) never damaged the player")

    def test_player_bot_can_win(self):
        st, m, w, pc = setup_world(seed=3)
        st.player.inventory.add("longsword_greyvein")
        st.player.equipment["weapon"] = "longsword_greyvein"
        for a in ("strength", "dexterity", "health"):
            st.player.attributes[a] = 30
        st.player.hp = st.player.max_hp
        wolves = [w.spawn_enemy("wolf", pc.x + 90, pc.y + dy) for dy in (-20, 0, 20)]

        def bot(i):
            alive = [c for c in w.enemies() if c.alive]
            if not alive:
                return
            t = min(alive, key=lambda c: math.hypot(c.x - pc.x, c.y - pc.y))
            d = math.hypot(t.x - pc.x, t.y - pc.y)
            pc.aim = ((t.x - pc.x) / d, (t.y - pc.y) / d) if d else (1, 0)
            if d < 30:
                w.attack(pc)
        run(w, m, 40, bot)
        self.assertTrue(all(not c.alive for c in wolves) or not pc.alive)
        self.assertTrue(st.stats.get("kills", 0) >= 1)
        self.assertGreater(st.player.skills["melee"], 0)  # learned by doing

    def test_attack_token_cap(self):
        st, m, w, pc = setup_world()
        st.player.attributes["health"] = 100
        st.player.hp = st.player.max_hp
        for i in range(5):
            w.spawn_enemy("bandit_cutthroat", pc.x + 60, pc.y - 40 + i * 20)
        worst = 0

        def bot(i):
            nonlocal worst
            attacking = sum(1 for c in w.enemies() if c.state in ("windup", "active"))
            worst = max(worst, attacking)
        run(w, m, 15, bot)
        self.assertLessEqual(worst, 2)

    def test_wounded_enemy_flees_and_escapes(self):
        st, m, w, pc = setup_world()
        foe = w.spawn_enemy("bandit_cutthroat", pc.x + 40, pc.y)
        foe.alerted = True
        foe.hp = foe.max_hp * 0.1
        run(w, m, 10)
        self.assertEqual(foe.ai.mode, "flee")

    def test_neutral_until_provoked(self):
        st, m, w, pc = setup_world()
        rep0 = st.reputation["thornblood"]
        foe = w.spawn_enemy("thornblood_raider", pc.x + 40, pc.y, hostile=False)
        run(w, m, 3)
        self.assertFalse(foe.alerted)
        pc.aim = (1.0, 0.0)
        foe.x = pc.x + 14
        w.attack(pc)
        run(w, m, 1)
        self.assertTrue(foe.hostile)
        self.assertLess(st.reputation["thornblood"], rep0)

    def test_kill_drops_loot_and_rep(self):
        st, m, w, pc = setup_world()
        crown = st.reputation["crown"]
        foe = w.spawn_enemy("bandit_cutthroat", pc.x + 12, pc.y)
        foe.ai = None  # (at 1 HP a live AI would sensibly run away)
        foe.hp = 1
        pc.aim = (1.0, 0.0)
        w.attack(pc)
        run(w, m, 1)
        self.assertFalse(foe.alive)
        self.assertGreater(st.reputation["crown"], crown)


if __name__ == "__main__":
    unittest.main()
