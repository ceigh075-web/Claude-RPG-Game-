"""Renders every sub-element x movement combination through the real scene into one contact sheet.

    python tools/vfx_gallery.py OUT.png
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame  # noqa: E402

from game.core.game import Game  # noqa: E402
from game.set_system import spells as spell_rules  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else "vfx_gallery.png"
DT = 1 / 60
MOVES = [("projectile", 0.22), ("homing", 0.3), ("beam", 0.06), ("wave", 0.25), ("area", 0.66), ("ground", 0.7),
         ("orbit", 0.5), ("ward", 0.6), ("aura", 0.4), ("burst", 0.1), ("chain", 0.1), ("trap", 0.6), ("barrier", 0.3),
         ("self", 0.2)]
CW, CH = 120, 84


def main():
    g = Game(headless=True, save_dir=os.path.join(os.path.dirname(OUT) or ".", "vfx_saves"))
    g.new_game("Rook", "human", {"race": "human", "skin": [198, 146, 104], "hair": [40, 30, 20],
                                 "shirt": [60, 90, 150], "pants": [60, 50, 40], "hair_style": 0}, "they/them")
    st = g.state
    st.location = "greywood"
    st.clock.minutes = 13 * 60
    st.local_pos = None
    g.enter_world()
    scene = g.scenes.top
    w = scene.combat
    w.enemies_list = None
    for c in list(w.enemies()):
        w.combatants.remove(c)
    pc = scene.player
    sp = scene.map.spawns[0]
    pc.x, pc.y = sp["x"] * 16 - 120, sp["y"] * 16
    pc.facing, pc.aim = "right", (1.0, 0.0)
    magic = g.data.magic
    only = sys.argv[2].split(",") if len(sys.argv) > 2 else None
    subs = [k for k in list(magic["elements"]) + list(magic["subelements"]) if not only or k in only]
    sheet = pygame.Surface((CW * len(MOVES) + 70, CH * len(subs) + 20))
    sheet.fill((20, 20, 26))
    from game.presentation.ui import widgets as ui
    for j, (mv, _) in enumerate(MOVES):
        ui.text(sheet, mv, (70 + j * CW + 4, 2), 16, (230, 230, 230))
    for i, sub in enumerate(subs):
        ui.text(sheet, sub, (4, 20 + i * CH + CH // 2), 16, (230, 230, 230))
        is_el = sub in magic["elements"]
        stats = magic["elements"][sub]["effects"] if is_el else magic["subelements"][sub]["stats"]
        for j, (mv, when) in enumerate(MOVES):
            w.projectiles.clear()
            w.effects.clear()
            for c in list(w.enemies()):
                w.combatants.remove(c)
            dummy = w.spawn_enemy("training_dummy", pc.x + (28 if mv in ("barrier", "self") else 50), pc.y)
            dummy.hp = dummy.max_hp
            stat = "damage" if "damage" in stats else stats[0]
            if mv == "aura" and "heal" in stats:
                stat = "heal"
            spell = {"name": "t", "move": mv, "stat": stat, "tier": 2}
            if is_el:
                spell["element"] = sub
                spell["sub"] = None
            else:
                spell["sub"] = sub
            try:
                p = spell_rules.compute(g.data, spell, 40, 0.0)
            except Exception as e:  # noqa: BLE001 - gallery tolerates invalid combos
                print("skip", sub, mv, e)
                continue
            pc.state = "idle"
            pc.set_state("cast")
            w._launch_spell(pc, p, (1.0, 0.0))
            t = 0.0
            while t < when:
                g.step(DT, [])
                pc.x, pc.y = sp["x"] * 16 - 120, sp["y"] * 16
                t += DT
            g.scenes.top.draw(g.screen)
            camx, camy = scene.camera()
            cx, cy = int(pc.x - camx) - 24, int(pc.y - camy) - CH + 22
            sheet.blit(g.canvas, (70 + j * CW, 20 + i * CH), (cx, cy, CW, CH))
    pygame.image.save(pygame.transform.scale_by(sheet, 2), OUT)
    print("saved", OUT)


if __name__ == "__main__":
    main()
