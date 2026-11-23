"""Every valid spell configuration can be computed, described, drawn in every spell screen, saved, loaded
and cast. Regression for: KeyError 'ash#0#1.5' in the spell book (visual style key used as a sub-element)."""
import itertools
import json
import os
import random
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from game.set_system import spells  # noqa: E402
from tests.test_combat import DATA, run  # noqa: E402
from tests.test_overhaul import world  # noqa: E402

M = DATA.magic


def configurations():
    """(element, sub, move, effect, behaviour) for every valid combination."""
    for el, ed in M["elements"].items():
        for sub in [None] + list(ed["subs"]):
            for mv in M["movements"]:
                for stat in spells.allowed_effects(DATA, el, sub):
                    for bh, b in M["behaviors"].items():
                        if b["moves"] and mv not in b["moves"]:
                            continue
                        yield el, sub, mv, stat, bh


class TestSpellMatrix(unittest.TestCase):
    def test_every_configuration_computes(self):
        n = 0
        for el, sub, mv, stat, bh in configurations():
            sp = {"name": "x", "element": el, "sub": sub, "move": mv, "stat": stat, "tier": 1, "behavior": bh}
            p = spells.compute(DATA, sp)
            self.assertEqual(p["sub"], sub)
            self.assertTrue(p["description"])
            self.assertGreater(p["mana"], 0)
            self.assertEqual(spells.source_name(DATA, p),
                             M["subelements"][sub]["name"] if sub else M["elements"][el]["name"])
            n += 1
        self.assertGreater(n, 1000)

    def test_slider_extremes_and_variants(self):
        for el, ed in M["elements"].items():
            for sub in [None] + list(ed["subs"]):
                for hue in range(len(M["appearance"]["hues"])):
                    for lo_hi in ("min", "max"):
                        sp = {"name": "x", "element": el, "sub": sub, "move": "ground",
                              "stat": spells.allowed_effects(DATA, el, sub)[0], "tier": 1, "hue": hue,
                              "intensity": M["appearance"]["intensity"][lo_hi], "size": M["sizes"][lo_hi]}
                        for k in spells.TUNING_KEYS:
                            sp[k] = M["tuning"][k][lo_hi]
                        p = spells.compute(DATA, sp)
                        from game.presentation import vfx
                        self.assertIsNotNone(vfx.style(p["style"]))

    def test_every_source_draws_in_spell_screens(self):
        pygame.init()
        screen = pygame.display.set_mode((1280, 720))
        from game.core.game import Game
        from game.presentation.scenes.spellbook import SpellbookScene, SpellCraftScene
        g = Game(headless=True, save_dir=os.path.join(os.environ.get("TMPDIR", "/tmp"), "matrix_saves"))
        g.new_game("M", "human", {"race": "human"}, "they/them")
        st = g.state
        for el, ed in M["elements"].items():
            for sub in [None] + list(ed["subs"]):
                for hue, inten in ((0, 1.0), (3, 1.5), (5, 0.5)):
                    sp = {"name": f"{el}-{sub}-{hue}", "element": el, "sub": sub, "move": "projectile",
                          "stat": spells.allowed_effects(DATA, el, sub)[0], "tier": 1, "hue": hue, "intensity": inten}
                    st.spellbook = [sp]
                    st.spell_drafts = [dict(sp, name="d")]
                    book = SpellbookScene(g)
                    for focus in (0, 1):
                        book.focus = focus
                        book.draw(screen)
                    for where in ("book", "draft"):
                        craft = SpellCraftScene(g, book, edit=(where, 0))
                        for f in range(len(craft.FIELDS)):
                            craft.field = f
                            craft.draw(screen)

    def test_save_load_and_cast_every_source(self):
        from game.core.state import GameState
        st, m, w, pc = world()
        st.spellbook = []
        for el, ed in M["elements"].items():
            for sub in [None] + list(ed["subs"]):
                st.spellbook.append({"name": f"{el}/{sub}", "element": el, "sub": sub, "move": "projectile",
                                     "stat": spells.allowed_effects(DATA, el, sub)[0], "tier": 1, "hue": 2,
                                     "intensity": 1.25, "duration": 2.0, "behavior": "volley"})
        st2 = GameState.from_dict(DATA, json.loads(json.dumps(st.to_dict())))
        self.assertEqual(len(st2.spellbook), len(st.spellbook))
        self.assertEqual(st2.load_notes, [])
        pc.aim = (1.0, 0.0)
        for sp in st2.spellbook:
            w.spell_cd.clear()
            st.player.mana = st.player.hp = 999
            pc.set_state("idle")
            ok, msg = w.cast(pc, sp)
            self.assertTrue(ok, msg)
        run(w, m, 1.0)

    def test_every_movement_casts(self):
        for mv in M["movements"]:
            st, m, w, pc = world()
            pc.aim = (1.0, 0.0)
            for el in M["elements"]:
                stat = spells.allowed_effects(DATA, el)[0]
                w.spell_cd.clear()
                pc.set_state("idle")
                st.player.mana = 999
                ok, msg = w.cast(pc, {"name": f"{el}{mv}", "element": el, "move": mv, "stat": stat, "tier": 1,
                                      "behavior": "lingering" if mv in M["behaviors"]["lingering"]["moves"] else "standard"})
                self.assertTrue(ok, msg)
            run(w, m, 0.5)

    def test_broken_old_spells_are_repaired_not_lost(self):
        report = []
        old = [{"name": "Wrong home", "element": "fire", "sub": "lightning", "move": "projectile", "stat": "damage", "tier": 1},
               {"name": "Bad behaviour", "element": "fire", "move": "ward", "stat": "damage", "tier": 1, "behavior": "volley"},
               {"name": "Too big", "element": "earth", "move": "area", "stat": "damage", "tier": 9, "size": 12, "potency": 7},
               {"name": "Bad effect", "element": "light", "move": "projectile", "stat": "nonsense", "tier": 1},
               {"name": "Nothing", "move": "projectile", "stat": "damage", "tier": 1}]
        out = spells.migrate(DATA, old, report)
        self.assertEqual([s["name"] for s in out], ["Wrong home", "Bad behaviour", "Too big", "Bad effect"])
        for s in out:
            spells.compute(DATA, s)
        self.assertEqual(out[0]["element"], "air")
        self.assertEqual(out[1]["behavior"], "standard")
        self.assertTrue(any("Nothing" in r for r in report))


if __name__ == "__main__":
    unittest.main()


class TestIcons(unittest.TestCase):
    def test_every_item_element_effect_and_action_has_an_icon(self):
        pygame.init()
        from game.presentation import icons
        for item in list(DATA.items) + ["marks"]:
            img = icons.ui_icon(DATA, item)
            self.assertEqual(img.get_size(), (32, 32), item)
            self.assertGreater(img.get_bounding_rect().w, 4, item)
            self.assertIsNotNone(icons.icon(DATA, item))
        for el in M["elements"]:
            self.assertIsNotNone(icons.named(icons.ELEMENT_CELL, el), el)
        for sub in M["subelements"]:
            self.assertIsNotNone(icons.named(icons.SUB_CELL, sub), sub)
        for stat in M["stats"]:
            self.assertIsNotNone(icons.named(icons.EFFECT_CELL, stat), stat)
        from game.set_system.stats import ATTRIBUTES, SKILLS
        for k in list(ATTRIBUTES) + list(SKILLS):
            self.assertIsNotNone(icons.named(icons.STAT_CELL, k), k)
