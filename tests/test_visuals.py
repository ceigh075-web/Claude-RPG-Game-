"""Visual overhaul safety nets: drawing must never change gameplay, every element must look distinct, and the
game must still draw if the art folder is missing. Run: python -m unittest -v"""
import os
import random
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from game.gameplay.combat import CombatWorld  # noqa: E402
from game.gameplay.entity import Actor  # noqa: E402
from game.presentation import assets, charsprites, combat_draw, creatures, env, visuals, vfx  # noqa: E402
from game.presentation.art import Art  # noqa: E402
from game.set_system import spells  # noqa: E402
from tests.test_combat import DATA, FakeGame, arena, new_state  # noqa: E402

pygame.init()
pygame.display.set_mode((1, 1))


def _battle(seed, draw):
    st = new_state()
    m = arena()
    w = CombatWorld(FakeGame(), st, m, random.Random(seed))
    pc = w.add_player(Actor(8 * 16 + 8, 11 * 16 + 12, {"race": "human"}, 70))
    st.player.inventory.add("longsword_greyvein")
    st.player.equipment["weapon"] = "longsword_greyvein"
    for i, eid in enumerate(("wolf", "bandit_cutthroat", "stone_brute", "husk")):
        w.spawn_enemy(eid, pc.x + 30 + i * 14, pc.y + (i % 2) * 18 - 9)
    art = Art()
    canvas = pygame.Surface((640, 360))
    sub_cycle = list(DATA.magic["subelements"])
    t = 0.0
    for i in range(600):
        if i % 30 == 0:
            st.player.hp = st.player.max_hp   # keep the player standing so every effect type gets drawn
        foes = [c for c in w.enemies() if c.alive]
        if foes:
            f = foes[0]
            d = max(1.0, ((f.x - pc.x) ** 2 + (f.y - pc.y) ** 2) ** 0.5)
            pc.aim = ((f.x - pc.x) / d, (f.y - pc.y) / d)
            if i % 50 == 0:
                sub = sub_cycle[(i // 50) % len(sub_cycle)]
                stats = DATA.magic["subelements"][sub]["stats"]
                spell = {"name": f"s{i}", "sub": sub, "move": ("projectile", "wave", "area", "beam")[i // 50 % 4],
                         "stat": "damage" if "damage" in stats else stats[0], "tier": 1}
                st.player.mana = 999
                w.cast(pc, spell)
            elif i % 9 == 0:
                w.attack(pc)
        w.update(1 / 60, m)
        t += 1 / 60
        if draw:
            combat_draw.draw_under(canvas, w, 0, 0, t)
            for _, img, x, y in combat_draw.sprite_entries(w, art, 0, 0, t):
                canvas.blit(img, (x, y))
            combat_draw.draw_fx(canvas, w, art, 0, 0, t)
            combat_draw.draw_floaters(canvas, w, 0, 0, 1)
    return [(round(c.x, 4), round(c.y, 4), round(c.hp, 4), c.state) for c in w.combatants], st.player.hp


class TestPresentationIsReadOnly(unittest.TestCase):
    def test_rendering_does_not_change_the_fight(self):
        self.assertEqual(_battle(3, draw=False), _battle(3, draw=True))

    def test_vfx_queue_is_bounded_without_a_renderer(self):
        st = new_state()
        m = arena()
        w = CombatWorld(FakeGame(), st, m, random.Random(1))
        pc = w.add_player(Actor(100, 100, {"race": "human"}, 70))
        e = w.spawn_enemy("training_dummy", 120, 100)
        prof = {"damage": 1, "knockback": 0, "stagger": 0, "skill": "melee", "scaling": []}
        for _ in range(500):
            e.hp = e.max_hp
            w.hit(pc, e, prof, (pc.x, pc.y))
        self.assertLessEqual(len(w.vfx_events), 65)


@unittest.skipUnless(assets.available(), "art folder missing")
class TestArt(unittest.TestCase):
    def test_every_subelement_has_its_own_style(self):
        subs = DATA.magic["subelements"]
        self.assertEqual(set(subs), set(vfx.ELEMENT))
        sigs = {(s.glyph, s.beam, s.ground, s.particle) for s in vfx.ELEMENT.values()}
        self.assertEqual(len(sigs), len(vfx.ELEMENT), "two sub-elements share the same look")

    def test_every_enemy_has_animation_frames(self):
        for eid, e in DATA.enemies.items():
            if e["shape"] == "humanoid":
                continue
            shape = creatures.shape_for(eid, e)
            for anim, n in creatures.FRAMES.items():
                for i in range(n):
                    self.assertGreater(creatures.frame(shape, e["color"], anim, i).get_bounding_rect().w, 0, (eid, anim))

    def test_humanoid_frames_for_all_races_and_directions(self):
        for race in DATA.races:
            for d in ("down", "up", "left", "right"):
                for anim in charsprites.ANIMS:
                    surf, _, _ = charsprites.compose({"race": race}, anim, d, 0)
                    self.assertEqual(surf.get_size(), (64, 64))
                    self.assertGreater(surf.get_bounding_rect().h, 10, (race, d, anim))

    def test_ground_tiles_are_opaque(self):
        art = Art()
        from game.world import mapgen as mg
        for biome in env.BIOME_TEX:
            for tid in (mg.GROUND, mg.ALT, mg.PATH, mg.PLAZA, mg.WATER):
                img = art.tile(tid, biome, 1, None)
                for x in range(0, 16, 3):
                    for y in range(0, 16, 3):
                        self.assertEqual(img.get_at((x, y)).a, 255, (biome, tid))


class TestFallback(unittest.TestCase):
    def test_draws_without_art_folder(self):
        old = (visuals._enabled, env._ok)
        visuals._enabled, env._ok = False, False
        try:
            st = new_state()
            m = arena()
            w = CombatWorld(FakeGame(), st, m, random.Random(1))
            w.add_player(Actor(100, 100, {"race": "human", "skin": [190, 150, 110], "hair": [40, 30, 20],
                                          "shirt": [60, 90, 150], "pants": [60, 50, 40]}, 70))
            w.spawn_enemy("wolf", 130, 100)
            ents = combat_draw.sprite_entries(w, Art(), 0, 0, 0.0)
            self.assertTrue(ents)
            combat_draw.draw_fx(pygame.Surface((640, 360)), w, Art(), 0, 0, 0.0)
        finally:
            visuals._enabled, env._ok = old


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(assets.available(), "art folder missing")
class TestCharacterVariety(unittest.TestCase):
    def test_named_npcs_have_distinct_looks(self):
        from game.presentation import looks
        sigs = {}
        for nid, npc in DATA.npcs.items():
            lk = looks.npc_identity(DATA, npc)
            sig = (lk["race"], lk.get("hair_style"), lk.get("hat"), lk.get("outfit"), lk.get("beard"),
                   tuple(lk.get("outfit_col", ())), tuple(lk.get("hair", ())), tuple(sorted(lk.get("acc", []))))
            self.assertNotIn(sig, sigs, f"{nid} looks identical to {sigs.get(sig)}")
            sigs[sig] = nid
        # and the silhouettes vary: several kinds of headwear, outfits and hairstyles in use
        all_looks = [looks.npc_identity(DATA, n) for n in DATA.npcs.values()]
        self.assertGreaterEqual(len({lk.get("hat") for lk in all_looks}), 6)
        self.assertGreaterEqual(len({lk.get("outfit") for lk in all_looks}), 6)
        self.assertGreaterEqual(len({lk.get("hair_style") for lk in all_looks}), 7)

    def test_identity_is_stable(self):
        from game.presentation import looks
        npc = DATA.npcs["garrow"]
        self.assertEqual(looks.npc_identity(DATA, npc), looks.npc_identity(DATA, npc))

    def test_every_named_npc_has_every_combat_animation(self):
        from game.presentation import looks
        for npc in DATA.npcs.values():
            lk = looks.npc_identity(DATA, npc)
            for anim in ("idle", "walk", "slice", "pierce", "crush", "hit", "death"):
                for d in ("down", "up", "left", "right"):
                    surf, _, _ = charsprites.compose(lk, anim, d, 3)
                    self.assertGreater(surf.get_bounding_rect().h, 8, (npc["id"], anim, d))

    def test_enemy_variants_differ(self):
        from game.presentation import looks
        for eid in looks.ENEMY_ROLE:
            variants = {repr(sorted(looks.enemy_variant(DATA, eid, k).items())) for k in range(6)}
            self.assertGreaterEqual(len(variants), 5, eid)

    def test_husk_variants_load(self):
        for v in range(len(creatures.SKELETONS)):
            for anim in ("idle", "move", "death"):
                img, w, foot = creatures.skeleton(anim, 2, v)
                self.assertIsNotNone(img)
                self.assertGreater(img.get_bounding_rect().h, 3)
