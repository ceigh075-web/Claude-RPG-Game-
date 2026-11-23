"""Render every named sprite in the asset manifest into one labelled sheet (to verify crops).

    python tools/preview_assets.py OUT.png
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

pygame.init()
pygame.display.set_mode((1, 1))
from game.presentation import assets  # noqa: E402

names = list(assets.MANIFEST)
cell = 104
cols = 14
rows = (len(names) + cols - 1) // cols
sheet = pygame.Surface((cols * cell, rows * cell))
sheet.fill((50, 52, 60))
font = pygame.font.Font(None, 14)
for i, n in enumerate(names):
    x, y = (i % cols) * cell, (i // cols) * cell
    pygame.draw.rect(sheet, (70, 72, 82), (x, y, cell - 2, cell - 2), 1)
    try:
        s = assets.sprite(n)
        k = min(2, (cell - 16) / max(s.get_width(), s.get_height()))
        s2 = pygame.transform.scale(s, (max(1, int(s.get_width() * k)), max(1, int(s.get_height() * k))))
        sheet.blit(s2, (x + (cell - s2.get_width()) // 2, y + 14 + (cell - 16 - s2.get_height()) // 2))
        label = f"{n} {s.get_width()}x{s.get_height()}"
    except Exception as e:  # show failures in the sheet
        label = f"{n} ERR {e}"[:28]
    sheet.blit(font.render(label, True, (255, 230, 120)), (x + 2, y + 2))
pygame.image.save(sheet, sys.argv[1] if len(sys.argv) > 1 else "assets_preview.png")
print(len(names), "sprites")
