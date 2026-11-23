"""Contact sheets of every named NPC, townsfolk roles, humanoid enemy variants, creatures and husks.

    python tools/character_gallery.py OUT_DIR
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.environ["SDL_VIDEODRIVER"] = "dummy"

import pygame  # noqa: E402

pygame.init()
pygame.display.set_mode((1, 1))

from game.core.data import GameData  # noqa: E402
from game.core.rng import stable_rng  # noqa: E402
from game.presentation import charsprites as cs, creatures, looks  # noqa: E402
from game.presentation.ui import widgets as ui  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else "gallery"
os.makedirs(OUT, exist_ok=True)
BG = (64, 96, 64)


def cell(look, d="down", anim="idle", f=0):
    surf, _, _ = cs.compose(look, anim, d, f)
    return surf.subsurface((14, 6, 36, 44))


def sheet(items, cols, cw, ch, scale=3, label=True):
    rows = (len(items) + cols - 1) // cols
    out = pygame.Surface((cols * cw * scale, rows * ch * scale))
    out.fill(BG)
    for i, (name, imgs) in enumerate(items):
        x, y = (i % cols) * cw * scale, (i // cols) * ch * scale
        ox = 0
        for img in imgs:
            big = pygame.transform.scale(img, (img.get_width() * scale, img.get_height() * scale))
            out.blit(big, (x + ox, y + 4))
            ox += img.get_width() * scale - 6 * scale
        if label:
            ui.text(out, name, (x + cw * scale // 2, y + ch * scale - 22), 18, (240, 240, 230), center=True)
    return out


def main():
    data = GameData()
    # 1) named NPCs: front, side, back
    items = []
    for npc in data.npcs.values():
        lk = looks.npc_identity(data, npc)
        items.append((npc["name"].split(" ")[0] + " - " + npc["occupation"][:16],
                      [cell(lk, "down"), cell(lk, "right", "walk", 2), cell(lk, "up")]))
    pygame.image.save(sheet(items, 6, 92, 56, 2), os.path.join(OUT, "named_npcs.png"))
    # 2) townsfolk by town trade
    items = []
    for spec in looks.TOWN_ROLES:
        for i in range(5):
            rng = stable_rng("gal", spec, i)
            lk, role = looks.townsfolk(data, rng, spec)
            items.append((f"{spec[:8]}:{role}", [cell(lk, "down"), cell(lk, "right", "walk", 1)]))
    pygame.image.save(sheet(items, 10, 62, 56, 2), os.path.join(OUT, "townsfolk.png"))
    # 3) humanoid enemies: 6 variants each, plus an attack frame
    items = []
    for eid in looks.ENEMY_ROLE:
        for k in range(6):
            lk = looks.enemy_variant(data, eid, k)
            items.append((f"{eid.split('_')[-1]} {k}", [cell(lk, "down"), cell(lk, "right", "slice", 4)]))
    pygame.image.save(sheet(items, 6, 62, 56, 2), os.path.join(OUT, "enemy_humanoids.png"))
    # 4) creatures: variants x animations, husk variants
    items = []
    for eid, e in data.enemies.items():
        if e["shape"] == "humanoid" or e.get("training"):
            continue
        shape = creatures.shape_for(eid, e)
        for v in range(3):
            imgs = [creatures.frame(shape, e["color"], a, i, v) for a, i in (("idle", 0), ("move", 1), ("windup", 1),
                                                                               ("strike", 1), ("hit", 0), ("death", 3))]
            items.append((f"{eid} v{v}", imgs))
    pygame.image.save(sheet(items, 3, 220, 50, 2), os.path.join(OUT, "creatures.png"))
    items = []
    for v in range(len(creatures.SKELETONS)):
        imgs = [creatures.skeleton(a, i, v)[0] for a, i in (("idle", 0), ("move", 2), ("move", 4), ("death", 7))]
        items.append((creatures.SKELETONS[v], imgs))
    pygame.image.save(sheet(items, 5, 140, 70, 2), os.path.join(OUT, "husks.png"))
    print("saved to", OUT)


if __name__ == "__main__":
    main()
