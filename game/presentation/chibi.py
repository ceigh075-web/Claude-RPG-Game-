"""Chibi heads: big round heads with large shining anime eyes and voluminous hair, drawn as pixel art for
every look, in three views (front, side facing right, back) and three moods (normal, hurt, knocked out).

The body still comes from the Body_A rig (so every animation, outfit and weapon keeps working); charsprites
removes the rig's small head and places one of these at the same spot every frame, so it bobs, leans and
falls with the body. Each head has two layers: `back` (hair that hangs behind the body, e.g. long hair seen
from the front) and `front` (everything else).

Skull coordinates: the face box is 16 x 14 px (x 0..15, rows 0..13, chin on row 13). The canvas leaves room
around it for hats, spikes, buns and long hair.
"""
import pygame

OX, OY = 9, 16                 # skull origin inside the canvas
CW, CH = 34, 44                # canvas size
OUTLINE = (30, 20, 26)
LASH = (22, 14, 20)
WHITE = (252, 252, 255)

# skull silhouettes: per row, (first x, last x)
FRONT = [(4, 11), (2, 13), (1, 14), (0, 15), (0, 15), (0, 15), (0, 15), (0, 15), (0, 15), (0, 15),
         (1, 14), (2, 13), (3, 12), (5, 10)]
SIDE = [(4, 11), (2, 13), (1, 14), (0, 14), (0, 14), (0, 14), (0, 14), (0, 14), (0, 14), (0, 15),
        (1, 14), (2, 13), (4, 12), (6, 10)]
BACK = FRONT

LONG = (1, 8)                  # long, braids
SIDE_LEN = {0: 9, 1: 21, 2: 6, 3: -1, 4: 8, 5: 8, 6: -1, 7: 11, 8: 9, 9: 9}


def _shade(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c)


def _mix(a, b, t):
    return tuple(int(x + (y - x) * t) for x, y in zip(a, b))


class Layer:
    def __init__(self):
        self.px = {}

    def set(self, x, y, col):
        self.px[(x, y)] = tuple(int(v) for v in col[:3])

    def get(self, x, y):
        return self.px.get((x, y))

    def has(self, x, y):
        return (x, y) in self.px

    def outline(self, col=OUTLINE, only=None):
        """1px outline around everything in the layer (or around the `only` set)."""
        pts = set(self.px) if only is None else only
        add = []
        for (x, y) in pts:
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                q = (x + dx, y + dy)
                if q not in self.px:
                    add.append(q)
        for q in add:
            self.px[q] = col

    def surface(self):
        s = pygame.Surface((CW, CH), pygame.SRCALPHA)
        for (x, y), c in self.px.items():
            cx, cy = x + OX, y + OY
            if 0 <= cx < CW and 0 <= cy < CH:
                s.set_at((cx, cy), (*c, 255))
        return s


def skull(view):
    rows = SIDE if view == "side" else FRONT
    return {(x, r) for r, (a, b) in enumerate(rows) for x in range(a, b + 1)}


# ============================================================================ hair
def hair_mask(style, view):
    """(front set, back set) of hair pixels in skull coordinates for a style and view."""
    sk = skull(view)
    front, back = set(), set()
    if style == 3:
        return front, back
    side_len = SIDE_LEN.get(style, 9)
    cap_rows = 2 if style == 2 else 3

    def dilate(points, n=1, rows=None):
        out = set(points)
        for _ in range(n):
            nxt = set(out)
            for (x, y) in out:
                for dx, dy in ((1, 0), (-1, 0), (0, -1)):
                    if rows is None or y <= rows:
                        nxt.add((x + dx, y + dy))
            out = nxt
        return out

    if style == 6:          # mohawk: shaved, a tall crest down the middle
        for y in range(-5, 6):
            for x in range(6, 10):
                if y >= -1 or (x in (7, 8)) or (y >= -3 and x in (6, 9)):
                    front.add((x, y))
        if view == "side":
            front = {(x - 1, y) for x, y in front} | {(x, y) for x in range(3, 9) for y in range(-2, 4)}
        return front, back

    if view == "up":                         # back of the head: all hair
        base = {p for p in sk if p[1] <= 12}
        vol = dilate(base, 2 if style == 7 else 1, 12)
        front = vol
        if side_len > 13:
            for y in range(12, side_len + 1):
                w = 6 if y < side_len - 2 else 4
                for x in range(8 - w, 8 + w):
                    front.add((x, y))
    elif view == "down":                     # front
        cap = {p for p in sk if p[1] < cap_rows}
        sides = {p for p in sk if p[1] <= min(side_len, 12) and (p[0] <= 1 or p[0] >= 14)}
        front = dilate(cap | sides, 2 if style == 7 else (0 if style == 2 else 1), max(side_len, 3))
        # fringe: jagged locks over the forehead
        pattern = {0: (3, 2, 3, 2), 1: (3, 3, 2, 3), 2: (1, 0, 1, 0), 4: (3, 2, 2, 3), 5: (2, 3, 2, 3),
                   7: (3, 2, 3, 3), 8: (2, 3, 3, 2), 9: (3, 1, 4, 1)}.get(style, (3, 2, 3, 2))
        for i, x in enumerate(range(1, 15)):
            for k in range(pattern[i % len(pattern)]):
                if cap_rows + k <= 5:          # never over the eyes
                    front.add((x, cap_rows + k))
        if side_len > 13:                    # long hair: curtains in front of the shoulders, mass behind
            for y in range(10, side_len + 1):
                taper = 1 if y > side_len - 3 else 2
                for x in range(-1, -1 + taper):
                    front.add((x, y))
                for x in range(17 - taper, 17):
                    front.add((x, y))
            for y in range(12, side_len - 1):
                for x in range(-1, 17):
                    back.add((x, y))
    else:                                    # side, facing right
        cap = {p for p in sk if p[1] < cap_rows}
        rear = {p for p in sk if p[0] <= 5 - (1 if p[1] > 6 else 0) and p[1] <= min(side_len, 12)}
        front = dilate(cap | rear, 2 if style == 7 else (0 if style == 2 else 1), max(side_len, 3))
        pattern = (3, 2, 3, 2) if style != 9 else (3, 1, 4, 1)
        for i, x in enumerate(range(6, 15)):
            for k in range(pattern[i % len(pattern)] if style != 2 else 1):
                if cap_rows + k <= 5:
                    front.add((x, cap_rows + k))
        if side_len > 13:
            for y in range(10, side_len + 1):
                for x in range(-1, 5 if y < side_len - 2 else 3):
                    front.add((x, y))
    # style extras
    if style == 5:                           # bun on top
        cx = 8 if view != "side" else 5
        for y in range(-5, 0):
            for x in range(cx - 3, cx + 3):
                if not (y == -5 and x in (cx - 3, cx + 2)):
                    front.add((x, y))
    elif style == 4:                         # ponytail
        if view == "down":
            for y in range(3, 14):
                back.add((16 + (1 if y > 6 else 0), y))
                back.add((17 + (1 if y > 6 else 0), y))
        elif view == "side":
            for y in range(2, 15):
                for x in range(-3 + (y // 6), 0 + (y // 6)):
                    front.add((x, y))
        else:
            for y in range(4, 17):
                for x in range(7, 10):
                    front.add((x, y))
    elif style == 9:                         # spikes
        tips = [(1, -2), (4, -4), (7, -5), (10, -4), (13, -2)] if view != "side" else [(1, -1), (4, -4), (7, -5), (10, -3)]
        for tx, ty in tips:
            for k in range(0, -ty + 1):
                w = k // 2
                for x in range(tx - w, tx + w + 1):
                    front.add((x, ty + k))
        if view == "down":
            for y in range(4, 10):
                front.add((-2, y + (y % 2)))
                front.add((17, y + (y % 2)))
    elif style == 8 and view == "down":      # two braids over the shoulders
        for y in range(9, 21):
            for x in (-1, 0):
                front.add((x, y))
            for x in (15, 16):
                front.add((x, y))
    return front, back


def paint_hair(layer, pts, hair, style, view, face):
    """Shade hair pixels: base, darker underside and strand lines, a glossy 'angel ring' highlight."""
    dark = _shade(hair, 0.68)
    deep = _shade(hair, 0.5)
    light = _mix(hair, (255, 255, 255), 0.35)
    for (x, y) in pts:
        col = hair
        if (x, y) in face:                   # fringe over the face: darker tips
            col = dark if not (x, y - 1) in face else deep
        elif y >= 10 or x <= -1 or x >= 16:
            col = dark if (x + y) % 3 else hair
        if y in (1, 2) and view != "up" and (2 <= x <= 5 or 9 <= x <= 12) and (x, y) not in face:
            col = light if y == 1 else _mix(hair, light, 0.5)
        if view == "up" and y in (2, 3) and 3 <= x <= 12:
            col = light if y == 2 else _mix(hair, light, 0.5)
        if style == 7 and (x * 3 + y * 5) % 7 == 0:
            col = dark
        if style == 8 and (y + x) % 3 == 0 and (x <= 0 or x >= 15):
            col = deep
        layer.set(x, y, col)


# ============================================================================ face
def eyes(layer, view, iris, mood, expr):
    """Large anime eyes (4x5 front, 3x5 side): thick upper lash with a flick, iris in three tones,
    a big catch-light top-left and a small one lower down."""
    dark = _shade(iris, 0.42)
    light = _mix(iris, (255, 255, 255), 0.35)
    spots = [2, 10] if view == "down" else [11]
    w = 4 if view == "down" else 3
    for i, ex in enumerate(spots):
        if mood in ("hurt", "ko") or expr == "grin":
            # squeezed shut: '>' '<' when hurt, '^' when laughing, flat line when knocked out
            if mood == "ko":
                for x in range(ex, ex + w):
                    layer.set(x, 9, LASH)
            elif mood == "hurt":
                outer = ex if i == 0 else ex + w - 1
                step = 1 if i == 0 else -1
                for k, y in enumerate((7, 8, 9, 10)):
                    layer.set(outer + step * (k if k < 2 else 3 - k), y, LASH)
            else:
                for k in range(w):
                    layer.set(ex + k, 8 if k in (0, w - 1) else 7, LASH)
            continue
        for x in range(ex, ex + w):
            layer.set(x, 6, LASH)
        outer = ex - 1 if (i == 0 and view == "down") else ex + w
        layer.set(outer, 6 if expr != "stern" else 5, LASH)
        if expr == "sad":
            layer.set(outer, 7, LASH)
        inner = ex + w - 1 if i == 0 else ex
        if expr == "stern":
            layer.set(inner, 5, LASH)
            layer.set(inner + (1 if i == 0 else -1), 5, LASH)
        elif expr == "sad":
            layer.set(inner, 4, LASH)
        if w == 4:
            rows = [[WHITE, WHITE, dark, dark], [WHITE, iris, iris, dark], [iris, iris, light, iris],
                    [None, light, light, None]]
        else:
            rows = [[WHITE, dark, dark], [iris, iris, dark], [iris, light, iris], [None, light, None]]
        for r, row in enumerate(rows):
            for k, c in enumerate(row):
                if c is not None:
                    layer.set(ex + k, 7 + r, c)
        layer.set(ex + w - 2, 9, _mix(light, WHITE, 0.6))


def mouth(layer, view, expr, mood, skin):
    dark = _shade(skin, 0.45)
    lip = (196, 98, 100)
    if view == "side":
        x = 13
        if mood == "hurt" or expr == "grin":
            layer.set(x, 12, (120, 40, 50))
            layer.set(x, 13, lip)
        else:
            layer.set(x, 12, lip if expr == "smile" else dark)
        return
    if mood == "hurt":
        for x in (7, 8):
            layer.set(x, 12, (110, 36, 46))
        layer.set(7, 13, lip)
        layer.set(8, 13, lip)
        return
    if mood == "ko":
        layer.set(7, 12, dark)
        layer.set(8, 12, dark)
        return
    if expr == "smile":
        layer.set(6, 11, dark)
        layer.set(9, 11, dark)
        layer.set(7, 12, lip)
        layer.set(8, 12, lip)
    elif expr == "grin":
        layer.set(6, 11, dark)
        layer.set(9, 11, dark)
        layer.set(7, 12, (110, 36, 46))
        layer.set(8, 12, (110, 36, 46))
        layer.set(7, 13, lip)
        layer.set(8, 13, lip)
    elif expr == "stern":
        for x in (6, 7, 8, 9):
            layer.set(x, 12, dark)
    elif expr == "sad":
        layer.set(7, 12, dark)
        layer.set(8, 12, dark)
        layer.set(6, 13, dark)
        layer.set(9, 13, dark)
    else:
        layer.set(7, 12, dark)
        layer.set(8, 12, _shade(skin, 0.6))


def face_marks(layer, view, look, skin):
    mark = look.get("face", "none")
    mcol = tuple(look.get("face_col") or (190, 60, 60))
    pink = (240, 120, 130)
    cheeks = [(1, 11), (2, 11), (13, 11), (14, 11)] if view == "down" else [(10, 11), (11, 11)]

    def blend(x, y, col, a):
        c = layer.get(x, y)
        if c is not None:
            layer.set(x, y, _mix(c, col, a))
    if mark == "blush":
        for x, y in cheeks:
            blend(x, y, pink, 0.6)
    elif mark == "freckles":
        for x, y in cheeks[::2] + [(c[0] + 1, c[1] + 1) for c in cheeks[::2]]:
            blend(x, y, _shade(skin, 0.6), 0.85)
    elif mark == "scar":
        x0 = 12 if view == "down" else 10
        for k, y in enumerate(range(4, 12)):
            if layer.get(x0 + (k % 2), y) not in (LASH, WHITE):
                blend(x0 + (k % 2), y, (220, 140, 130), 0.75)
    elif mark == "beauty_mark":
        blend(11 if view == "down" else 12, 12, (60, 36, 30), 0.9)
    elif mark == "tattoo":
        for x, y in ((14, 8), (14, 9), (13, 10)) if view == "down" else ((9, 8), (9, 9), (8, 10)):
            blend(x, y, mcol, 0.85)
    paint = look.get("warpaint")
    if paint:
        stripes = [(1, 11), (2, 11), (3, 11), (12, 11), (13, 11), (14, 11)] if view == "down" else [(10, 11), (11, 11), (12, 11)]
        for x, y in stripes:
            blend(x, y, tuple(paint), 0.9)


# ============================================================================ head wear
def headwear(layer, look, view):
    hat = look.get("hat")
    helm = look.get("helm")
    hood = look.get("hood") if isinstance(look.get("hood"), (list, tuple)) else None
    col = tuple(look.get("hat_col") or (110, 80, 50))
    if helm:
        _helm(layer, tuple(helm), view)
        return
    if hood or hat == "hood_up":
        _hood(layer, tuple(hood or col), view)
        return
    if not hat:
        return
    hi, lo = _shade(col, 1.25), _shade(col, 0.7)
    if hat in ("cap", "miner", "feather_cap", "bandana"):
        for y in range(-2, 4):
            a, b = (FRONT if view != "side" else SIDE)[max(0, y)]
            a, b = a - 1, b + 1
            if y < 0:
                a, b = (4, 11) if y == -2 else (2, 13)
            for x in range(a, b + 1):
                layer.set(x, y, hi if y <= -1 else (col if y < 3 else lo))
        if hat == "bandana":
            if view != "up":
                for x, y in ((16, 3), (17, 4), (17, 5), (18, 6)):
                    layer.set(x if view == "down" else x - 18, y, lo)
        elif view == "down":
            for x in range(-1, 17):
                layer.set(x, 4, lo)
        elif view == "side":
            for x in range(10, 19):
                layer.set(x, 4, lo)
        if hat == "miner" and view != "up":
            lx = 7 if view == "down" else 13
            layer.set(lx, 0, (255, 236, 140))
            layer.set(lx + 1, 0, (255, 220, 100))
            layer.set(lx, 1, (220, 180, 80))
        if hat == "feather_cap":
            for k in range(6):
                layer.set(13 + (k % 2), -1 - k, (200, 50, 50) if k < 5 else (240, 120, 100))
    elif hat == "wide":
        for y in range(-4, 2):
            for x in range(3, 13):
                layer.set(x, y, hi if y < -1 else col)
        for x in range(-4, 20) if view != "side" else range(-3, 20):
            layer.set(x, 2, lo)
            if -2 <= x <= 17:
                layer.set(x, 3, _shade(col, 0.55))
        for x in range(3, 13):
            layer.set(x, 1, (60, 40, 30))
    elif hat == "wizard":
        for y in range(-11, 4):
            t = (y + 11) / 14
            w = int(1 + t * 9)
            cx = 8 + (2 if y < -7 else 0)
            for x in range(cx - w, cx + w):
                layer.set(x, y, hi if x < cx else col)
        for x in range(-2, 18):
            layer.set(x, 3, lo)
            layer.set(x, 2, (230, 200, 90))
        layer.set(10, -11, (250, 230, 140))
    elif hat == "crown":
        gold, gdark = (240, 200, 70), (180, 130, 40)
        for x in range(1, 15):
            layer.set(x, 1, gdark)
            layer.set(x, 0, gold)
        for x in (1, 4, 7, 8, 11, 14):
            layer.set(x, -1, gold)
            if x in (1, 7, 8, 14):
                layer.set(x, -2, gold)
        layer.set(7, 0, (220, 50, 70))
        layer.set(8, 0, (220, 50, 70))
    elif hat == "circlet":
        for x in range(0, 16):
            layer.set(x, 3, (230, 200, 90))
        if view == "down":
            layer.set(7, 3, (90, 200, 230))
            layer.set(8, 3, (90, 200, 230))
    elif hat == "horns":
        bone, bdark = (236, 226, 200), (170, 150, 120)
        sides = ((1, -1), (14, 1)) if view != "side" else ((5, -1),)
        for hx, dirn in sides:
            for k in range(6):
                x = hx + dirn * (k // 2)
                y = 1 - k
                layer.set(x, y, bone if k < 4 else bdark)
                layer.set(x + dirn, y, bdark)


def _helm(layer, metal, view):
    hi, lo = _shade(metal, 1.3), _shade(metal, 0.7)
    rows = FRONT if view != "side" else SIDE
    for y in range(-1, 10):
        a, b = rows[max(0, y)]
        a, b = a - 1, b + 1
        for x in range(a, b + 1):
            face_open = view == "down" and 2 <= x <= 13 and y >= 5
            face_open = face_open or (view == "side" and x >= 8 and y >= 5)
            if face_open or (view != "up" and y > 7 and 2 < x < 13):
                continue
            layer.set(x, y, hi if y <= 1 else (metal if (x + y) % 5 else lo))
    if view == "down":
        for y in range(4, 10):
            layer.set(7, y, lo)
            layer.set(8, y, metal)
        for x in range(-1, 17):
            layer.set(x, 4, lo)
    elif view == "side":
        for x in range(7, 16):
            layer.set(x, 4, lo)
    layer.set(7 if view != "side" else 6, -2, (200, 60, 60))
    layer.set(8 if view != "side" else 6, -3, (220, 80, 80))


def _hood(layer, col, view):
    hi, lo = _shade(col, 1.2), _shade(col, 0.7)
    rows = FRONT if view != "side" else SIDE
    for y in range(-2, 16):
        a, b = rows[min(13, max(0, y))]
        a, b = a - 2, b + 2
        for x in range(a, b + 1):
            if view == "down" and 2 <= x <= 13 and 3 <= y <= 13:
                continue
            if view == "side" and x >= 7 and 3 <= y <= 13:
                continue
            if y > 13 and not (-2 <= x <= 17):
                continue
            layer.set(x, y, hi if y < 2 else (col if (x + y) % 6 else lo))
    if view == "down":
        for x in range(2, 14):
            layer.set(x, 3, lo)


# ============================================================================ race features
def ears(layer, look, view, skin, hair_pts):
    race = look.get("race", "human")
    dark = _shade(skin, 0.75)
    if view == "up" and race != "sylth":
        return
    if race == "sylth":                      # long swept-back ears
        pts = [(-1, 8), (-2, 7), (-3, 6), (-4, 5), (-1, 9), (-2, 8), (-3, 7)]
        sides = [pts, [(15 - x, y) for x, y in pts]] if view != "side" else [[(x + 7, y) for x, y in pts]]
        for side in sides:
            for x, y in side:
                layer.set(x, y, skin if (x, y) not in side[:1] else dark)
    elif race == "murrok":                   # furry rounded ears on top
        tops = [(1, -1), (2, -2), (3, -2), (2, -1), (3, -1)]
        sides = [tops, [(15 - x, y) for x, y in tops]] if view != "side" else [[(x + 3, y) for x, y in tops]]
        fur = tuple(look.get("hair", (90, 60, 40)))
        for side in sides:
            for x, y in side:
                layer.set(x, y, fur if y == -2 else _mix(fur, (240, 200, 180), 0.4))
    elif view == "side" and not (look.get("hood") or look.get("helm") or look.get("hat") == "hood_up"):
        rim = _shade(skin, 0.55)
        for x, y in ((6, 7), (7, 7), (6, 8), (6, 9)):
            layer.set(x, y, skin)
        layer.set(7, 8, _shade(skin, 0.78))
        for x, y in ((6, 6), (7, 6), (8, 7), (8, 8), (7, 9), (6, 10)):
            layer.set(x, y, rim)
        if "earring" in look.get("acc", ()):
            layer.set(6, 10, (240, 200, 70))
    elif view == "down" and not (look.get("hood") or look.get("helm")):
        for x, y in ((-1, 7), (-1, 8), (16, 7), (16, 8)):
            if (x, y) not in hair_pts:
                layer.set(x, y, skin)
        if "earring" in look.get("acc", ()):
            layer.set(-1, 9, (240, 200, 70))
            layer.set(16, 9, (240, 200, 70))


def race_face(layer, look, view, skin):
    race = look.get("race", "human")
    if race == "murrok" and view != "up":
        tusk = (244, 238, 220)
        for x in ((5, 10) if view == "down" else (12,)):  # lower tusks at the mouth corners
            layer.set(x, 13 if view == "down" else 12, tusk)
            layer.set(x, 12 if view == "down" else 11, tusk)
    elif race == "kethari" and view != "up":
        fleck = _shade(skin, 0.7)
        for x, y in ((3, 4), (12, 3), (1, 11), (14, 11), (5, 12), (11, 5)) if view == "down" else ((4, 4), (11, 11), (6, 5)):
            if layer.get(x, y) == skin:
                layer.set(x, y, fleck)


# ============================================================================ beard and face accessories
def beard(layer, look, view, hair):
    b = look.get("beard", 0)
    if not b or view == "up":
        return
    dark = _shade(hair, 0.72)
    xs = range(1, 15) if view == "down" else range(8, 15)
    if b == 1:
        for x in xs:
            for y in (11, 12, 13):
                if (x + y) % 2 == 0 and layer.get(x, y) not in (None,) and not (6 <= x <= 9 and y == 12 and view == "down"):
                    layer.set(x, y, _mix(layer.get(x, y), dark, 0.6))
        return
    if b == 3:
        for x in (range(5, 11) if view == "down" else range(11, 15)):
            layer.set(x, 11, hair)
        return
    bottom = 14 if b == 2 else 18
    for y in range(11, bottom + 1):
        for x in xs:
            if y > 13:
                if view == "down" and not (4 + (y - 14) <= x <= 11 - (y - 14)):
                    continue
                if view == "side" and not (9 <= x <= 13 - (y - 14) // 2):
                    continue
            elif layer.get(x, y) is None:
                continue
            if view == "down" and y in (12, 13) and 6 <= x <= 9:
                continue                     # mouth shows through
            layer.set(x, y, hair if (x + y) % 3 else dark)


def face_acc(layer, look, view):
    acc = set(look.get("acc", ()))
    if view == "up":
        return
    if "glasses" in acc:
        frame = (60, 50, 50)
        for ex in ([2, 10] if view == "down" else [11]):
            w = 4 if view == "down" else 3
            for x in range(ex - 1, ex + w + 1):
                layer.set(x, 6, frame)
                layer.set(x, 11, frame)
            for y in range(6, 12):
                layer.set(ex - 1, y, frame)
                layer.set(ex + w, y, frame)
        if view == "down":
            layer.set(7, 8, frame)
            layer.set(8, 8, frame)
    if "eyepatch" in acc:
        ex = 10 if view == "down" else 11
        for y in range(6, 11):
            for x in range(ex - 1 if view == "down" else ex, ex + 4):
                layer.set(x, y, (30, 26, 28))
        for k in range(6):
            layer.set(ex - 3 - k if view == "down" else ex - 2 - k, 5 - k // 3, (30, 26, 28))


# ============================================================================ assembly
_cache = {}


def head(look, view, mood="normal"):
    """(back surface, front surface) for a look; view: 'down' | 'side' | 'up'; mood: normal | hurt | ko."""
    key = (_key(look), view, mood)
    hit = _cache.get(key)
    if hit is not None:
        return hit
    skin = tuple(look.get("skin", (217, 170, 130)))
    hair = tuple(look.get("hair", (60, 40, 30)))
    style = look.get("hair_style", 0)
    expr = look.get("expression", "neutral")
    iris = tuple(look.get("eye") or (70, 48, 40))
    covered = bool(look.get("helm")) or isinstance(look.get("hood"), (list, tuple)) or look.get("hat") == "hood_up"
    front, back = Layer(), Layer()
    sk = skull(view)
    # skin with soft shading: darker under the hair line and along the jaw
    for (x, y) in sk:
        col = skin
        if y >= 12 or (view == "down" and (x <= 0 or x >= 15)) or (view == "side" and x <= 1):
            col = _shade(skin, 0.9)
        front.set(x, y, col)
    hf, hb = hair_mask(style, view) if not covered else (set(), set())
    if covered and style in LONG and view == "down":
        hb = hair_mask(style, view)[1]
    if view != "up":
        face = {p for p in sk if p[1] >= 3}
        eyes(front, view, iris, mood, expr)
        mouth(front, view, expr, mood, skin)
        if view == "down":
            front.set(8, 10, _shade(skin, 0.82))        # nose
        else:
            front.set(15, 9, skin)
            front.set(15, 10, _shade(skin, 0.8))
        face_marks(front, view, look, skin)
        race_face(front, look, view, skin)
        beard(front, look, view, hair)
    else:
        face = set()
    # shadow cast by the fringe
    for (x, y) in list(hf):
        if (x, y + 1) in sk and (x, y + 1) not in hf and front.get(x, y + 1) == skin:
            front.set(x, y + 1, _shade(skin, 0.86))
    paint_hair(front, hf, hair, style, view, face & sk)
    paint_hair(back, hb, hair, style, view, set())
    ears(front, look, view, skin, hf)
    face_acc(front, look, view)
    headwear(front, look, view)
    front.outline()
    back.outline(_shade(hair, 0.3))
    out = (enlarge(back.surface()) if back.px else None, enlarge(front.surface()))
    if len(_cache) > 3000:
        _cache.clear()
    _cache[key] = out
    return out


def _key(look):
    keys = ("skin", "hair", "hair_style", "expression", "eye", "eye_style", "hat", "hat_col", "helm", "hood", "beard",
            "face", "face_col", "warpaint", "race", "acc")
    return tuple((k, tuple(look[k]) if isinstance(look.get(k), list) else look.get(k)) for k in keys)


ANCHOR = (OX + 8, OY + 13)      # canvas point that sits on the rig's chin (front/back views), unscaled
HEAD_SCALE = 1.15               # heads are drawn on a 16px face grid, then enlarged to suit the bigger bodies
ANCHOR_S = (ANCHOR[0] * HEAD_SCALE, ANCHOR[1] * HEAD_SCALE)


def enlarge(surf, k=None):
    """Scale pixel art by a non-integer factor without ragged edges: Scale2x first, then sample."""
    k = HEAD_SCALE if k is None else k
    if k == 1:
        return surf
    two = pygame.transform.scale2x(surf)
    w, h = surf.get_size()
    W, H = int(w * k) + 1, int(h * k) + 1
    out = pygame.Surface((W, H), pygame.SRCALPHA)
    for y in range(H):
        sy = int((y + 0.5) / k * 2)
        if sy >= h * 2:
            continue
        for x in range(W):
            sx = int((x + 0.5) / k * 2)
            if sx < w * 2:
                c = two.get_at((sx, sy))
                if c.a:
                    out.set_at((x, y), c)
    return out
