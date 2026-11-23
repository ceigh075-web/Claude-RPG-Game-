"""Find individual sprites in a texture atlas (connected opaque regions) and write a labelled preview.

    python tools/atlas_components.py ATLAS.png OUT.png [--gap N]

The index printed on each sprite is what `game/presentation/assets.py` manifests refer to as
("atlas", index). Indices are sorted top-to-bottom, left-to-right, so they are stable for an atlas.
"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402


def components(surf, gap=1, min_px=6):
    """Bounding boxes of connected opaque regions; boxes closer than `gap` px are merged."""
    w, h = surf.get_size()
    mask = pygame.mask.from_surface(surf, 1)
    boxes = [pygame.Rect(r) for r in mask.get_bounding_rects()]
    boxes = [b for b in boxes if b.w * b.h >= min_px]
    merged = True
    while merged:
        merged = False
        out = []
        while boxes:
            b = boxes.pop()
            for i, o in enumerate(out):
                if b.inflate(gap * 2, gap * 2).colliderect(o):
                    out[i] = o.union(b)
                    merged = True
                    break
            else:
                out.append(b)
        boxes = out
    boxes.sort(key=lambda r: (r.y // 8, r.x))
    return boxes


def preview(path, out, gap=1, scale=2):
    pygame.init()
    if not pygame.display.get_surface():
        pygame.display.set_mode((1, 1))
    img = pygame.image.load(path).convert_alpha()
    boxes = components(img, gap)
    w, h = img.get_size()
    s = pygame.Surface((w * scale, h * scale))
    s.fill((55, 55, 65))
    s.blit(pygame.transform.scale(img, (w * scale, h * scale)), (0, 0))
    f = pygame.font.Font(None, 16)
    for i, b in enumerate(boxes):
        pygame.draw.rect(s, (255, 60, 60), (b.x * scale, b.y * scale, b.w * scale, b.h * scale), 1)
        t = f.render(str(i), True, (255, 255, 0), (0, 0, 0))
        s.blit(t, (b.x * scale, b.y * scale))
    pygame.image.save(s, out)
    return boxes


if __name__ == "__main__":
    gap = int(sys.argv[sys.argv.index("--gap") + 1]) if "--gap" in sys.argv else 1
    bs = preview(sys.argv[1], sys.argv[2], gap)
    for i, b in enumerate(bs):
        print(i, tuple(b))
