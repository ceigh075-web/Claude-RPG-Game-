"""Animated humanoid sprites built on the Pixel Crawler "Body_A" rig.

For every base frame we analyse the body once (cached):
  * body pixels vs. the baked-in tool vs. the white smear arc,
  * body regions (head / torso / arms / legs / feet) found by eroding and re-growing the silhouette, so
    clothing, sleeves, boots and hair follow every pose of every animation automatically,
  * the tool's grip and tip points, which tell us where to draw the character's *actual* weapon.

A `look` (skin, hair, outfit, race, armour) is then applied per character and cached per frame.
Directions: down / up / right / left (left = mirrored side view).
"""
import math

import pygame

from . import assets, wardrobe

BODY = "Entities/Characters/Body_A/Animations/"
ANIMS = {  # name: (folder, file stem, frames, up-file override)
    "idle": ("Idle_Base", "Idle", 4, None), "walk": ("Walk_Base", "Walk", 6, None),
    "run": ("Run_Base", "Run", 6, None), "slice": ("Slice_Base", "Slice", 8, None),
    "pierce": ("Pierce_Base", "Pierce", 8, "Top"), "crush": ("Crush_Base", "Crush", 8, None),
    "hit": ("Hit_Base", "Hit", 4, None), "death": ("Death_Base", "Death", 8, None),
    "collect": ("Collect_Base", "Collect", 8, None),
}
FW = 64
OUTLINE = (0, 0, 0)
EYE = (76, 181, 40)
SKIN_BASE = (217, 160, 102)

_base = {}      # (anim, dir) -> list of FrameInfo
_body_pal = None
_looks = {}     # (look_key, anim, dir, idx) -> (surface, smear)
FOOT_Y = 41     # feet row inside a 64x64 frame (measured from the idle frames on first load)


class FrameInfo:
    __slots__ = ("body", "smear", "grip", "tip", "regions", "bbox")


def _sheet(anim, d):
    folder, stem, n, up = ANIMS[anim]
    suffix = {"down": "Down", "up": up or "Up", "side": "Side"}[d]
    return assets.frames(f"{BODY}{folder}/{stem}_{suffix}-Sheet.png", FW, FW)[:n]


def _palette():
    """Colours that belong to the bare body (collected from tool-free animations)."""
    global _body_pal, FOOT_Y
    if _body_pal is None:
        pal = set()
        bottoms = []
        for anim in ("idle", "walk", "run", "hit"):
            for d in ("down", "up", "side"):
                for f in _sheet(anim, d):
                    for y in range(FW):
                        for x in range(FW):
                            c = f.get_at((x, y))
                            if c.a:
                                pal.add((c.r, c.g, c.b))
                    if anim == "idle":
                        m = pygame.mask.from_surface(f, 1)
                        rects = m.get_bounding_rects()
                        if rects:
                            bottoms.append(max(r.bottom for r in rects) - 1)
        pal.discard(OUTLINE)
        _body_pal = pal
        if bottoms:
            FOOT_Y = max(set(bottoms), key=bottoms.count)
    return _body_pal


def _is_smear(c):
    # the pack's swing arcs are flat light grey (231,231,231); tool highlights are never neutral
    return c[0] == c[1] == c[2] and c[0] >= 225


def _analyse(src):
    """Separate body / tool / smear and label body regions for one base frame."""
    pal = _palette()
    W = H = FW
    body, tool, smear = set(), [], set()
    blacks = []
    for y in range(H):
        for x in range(W):
            c = src.get_at((x, y))
            if not c.a:
                continue
            rgb = (c.r, c.g, c.b)
            if rgb == OUTLINE:
                blacks.append((x, y))
            elif _is_smear(rgb):
                smear.add((x, y))
            elif rgb in pal:
                body.add((x, y))
            else:
                tool.append((x, y))
    near_body = lambda p: any((p[0] + dx, p[1] + dy) in body for dx in (-1, 0, 1) for dy in (-1, 0, 1))
    outline = {p for p in blacks if near_body(p)}
    # tool outline pixels (black, touching tool, not body) count as tool for anchoring
    toolset = set(tool)
    tool_outline = [p for p in blacks if p not in outline and any((p[0] + dx, p[1] + dy) in toolset
                                                                  for dx in (-1, 0, 1) for dy in (-1, 0, 1))]
    info = FrameInfo()
    out = pygame.Surface((W, H), pygame.SRCALPHA)
    for p in body | outline:
        out.set_at(p, src.get_at(p))
    info.body = out
    sm = pygame.Surface((W, H), pygame.SRCALPHA)
    for p in smear:
        sm.set_at(p, (255, 255, 255, 235))
    info.smear = sm if smear else None
    # grip = tool pixel nearest to the body; tip = tool pixel farthest from the grip
    pts = tool + tool_outline
    info.grip = info.tip = None
    if len(pts) >= 4 and body:
        grip = min(pts, key=lambda p: min(abs(p[0] - b[0]) + abs(p[1] - b[1]) for b in _sample(body)))
        tip = max(pts, key=lambda p: (p[0] - grip[0]) ** 2 + (p[1] - grip[1]) ** 2)
        if math.hypot(tip[0] - grip[0], tip[1] - grip[1]) >= 3:
            info.grip, info.tip = grip, tip
    info.regions = _regions(body)
    rs = pygame.mask.from_surface(out, 1).get_bounding_rects()
    info.bbox = rs[0].unionall(rs[1:]) if rs else pygame.Rect(0, 0, 0, 0)
    return info


def _sample(body, n=60):
    lst = list(body)
    step = max(1, len(lst) // n)
    return lst[::step]


def _erode(px, r):
    s = set(px)
    for _ in range(r):
        s = {p for p in s if all((p[0] + dx, p[1] + dy) in s for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))}
    return s


def _grow(seed, limit, r):
    s = set(seed)
    for _ in range(r):
        s |= {(p[0] + dx, p[1] + dy) for p in s for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))} & limit
    return s


def _blobs(px):
    px = set(px)
    out = []
    while px:
        start = px.pop()
        comp, stack = {start}, [start]
        while stack:
            x, y = stack.pop()
            for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if n in px:
                    px.discard(n)
                    comp.add(n)
                    stack.append(n)
        out.append(comp)
    return out


def _regions(body):
    """Label body pixels: head, torso, arms, legs, feet (dict region -> set of pixels)."""
    if not body:
        return {"head": set(), "torso": set(), "arms": set(), "legs": set(), "feet": set()}
    core = _erode(body, 2)
    blobs = sorted(_blobs(core), key=lambda b: min(p[1] for p in b))
    head_core = blobs[0] if blobs else set()
    head = _grow(head_core, body, 3)
    # Upright frames: the whole head (forehead to chin) ends at the neck, a 0-3 px wide row ~12 rows down.
    top = min(p[1] for p in body)
    if head and min(p[1] for p in head) <= top + 2:
        hx0, hx1 = min(p[0] for p in head), max(p[0] for p in head)
        for y in range(top + 9, top + 15):
            if sum(1 for p in body if p[1] == y and hx0 - 1 <= p[0] <= hx1 + 1) <= 3:
                head = {p for p in body if p[1] < y and hx0 - 1 <= p[0] <= hx1 + 1}
                break
    hb = max(p[1] for p in head) if head else 0
    rest_blobs = [b - head for b in blobs[1:] if len(b - head) >= 3]
    torso_core = max(rest_blobs, key=len) if rest_blobs else set()
    torso = _grow(torso_core, body - head, 2)
    if torso:
        tb = max(p[1] for p in torso)
    else:
        tb = hb + 6
        torso = {p for p in body - head if p[1] <= tb}
    legs = {p for p in body - head - torso if p[1] > tb - 1}
    arms = body - head - torso - legs
    by = max(p[1] for p in body)
    feet = {p for p in legs if p[1] >= by - 1}
    legs -= feet
    return {"head": head, "torso": torso, "arms": arms, "legs": legs, "feet": feet}


def base(anim, d):
    key = (anim, d)
    if key not in _base:
        _base[key] = [_analyse(f) for f in _sheet(anim, d)]
    return _base[key]


# ------------------------------------------------------------------------- looks
def _shade_map(rgb, target, light_bias=0):
    """Map a body pixel's shade onto `target` keeping relative lightness."""
    L = assets.luminance(rgb) / assets.luminance(SKIN_BASE)
    f = max(0.35, min(1.45, L + light_bias))
    return tuple(max(0, min(255, int(c * f))) for c in target)


def look_key(look):
    return tuple(sorted((k, tuple(v) if isinstance(v, list) else v) for k, v in look.items()))


def compose(look, anim, d, idx):
    """(surface 64x64, smear surface or None, FrameInfo) for a character look; left is mirrored."""
    side = d in ("left", "right")
    bd = "side" if side else d
    frames = base(anim, bd)
    idx = idx % len(frames)
    key = (look_key(look), anim, bd, idx)
    if key not in _looks:
        _looks[key] = _paint(look, frames[idx], bd, anim, idx)
    surf, smear = _looks[key]
    info = frames[idx]
    if d == "left":
        fkey = key + ("L",)
        if fkey not in _looks:
            _looks[fkey] = (pygame.transform.flip(surf, True, False),
                            pygame.transform.flip(smear, True, False) if smear else None)
        surf, smear = _looks[fkey]
    return surf, smear, info


def _paint(look, info, d, anim="idle", idx=0):
    src = info.body
    out = src.copy()
    R = info.regions
    skin = tuple(look.get("skin", SKIN_BASE))
    hair = tuple(look.get("hair", (60, 40, 30)))
    shirt = tuple(look.get("shirt", (90, 90, 140)))
    pants = tuple(look.get("pants", (70, 60, 50)))
    boots = tuple(look.get("boots", (54, 40, 32)))
    armor = look.get("armor")
    helm = look.get("helm")
    race = look.get("race", "human")

    def put(p, col):
        c = src.get_at(p)
        out.set_at(p, (*_shade_map((c.r, c.g, c.b), col), 255))

    for p in R["head"]:
        put(p, skin)
    for p in R["torso"]:
        put(p, tuple(armor) if armor else shirt)
    # sleeves near the torso, bare forearms / gloves beyond
    torso = R["torso"]
    for p in R["arms"]:
        near = any((p[0] + dx, p[1] + dy) in torso for dx in (-2, -1, 0, 1, 2) for dy in (-2, -1, 0, 1, 2))
        put(p, (tuple(armor) if armor else shirt) if near else (tuple(look["gloves"]) if look.get("gloves") else skin))
    for p in R["legs"]:
        put(p, pants)
    for p in R["feet"]:
        put(p, boots)
    head = R["head"]
    if head:
        hx0 = min(p[0] for p in head)
        hx1 = max(p[0] for p in head)
        hy0 = min(p[1] for p in head)
        hy1 = max(p[1] for p in head)
        cx = (hx0 + hx1) / 2
        eye_row = None
        for p in head:
            c = src.get_at(p)
            if (c.r, c.g, c.b) == EYE:
                eye_row = p[1] if eye_row is None else min(eye_row, p[1])
        style = look.get("hair_style", 0)
        cap = tuple(helm) if helm else (tuple(look["hood"]) if isinstance(look.get("hood"), (list, tuple)) else None)
        rows = 3 if style != 2 else 2
        for p in head:
            x, y = p
            c = src.get_at(p)
            if (c.r, c.g, c.b) == EYE:
                if look.get("eye"):
                    out.set_at(p, (*look["eye"], 255))
                continue
            top = y < hy0 + rows
            back = False
            if d == "up":
                back = y < hy1 - 1
            elif d == "side":
                back = x < cx - 1 and y < hy1 - 2       # side frames face right: hair at the back (left)
            elif d == "down" and style == 1:
                back = (x <= hx0 + 1 or x >= hx1 - 1) and y < hy1 - 1
            if cap is not None:
                if top or back or (d != "down" and y < hy0 + 4) or (x in (hx0, hx1) and y < hy1 - 1):
                    put(p, cap)
            elif style != 3 and (top or back):
                # glossy anime-style sheen: a lighter band across the crown
                if top and d != "up" and y == hy0 + 1 and cx - 3 <= x <= cx - 1 + (d == "side"):
                    put(p, tuple(min(255, int(v * 1.45 + 30)) for v in hair))
                else:
                    put(p, hair)
        if cap is None and style != 3:
            _bangs(out, src, put, head, d, style, hair, hx0, hx1, hy0, hy1, rows, eye_row)
        _mouth(out, src, head, d, hx0, hx1, hy1, skin, look)
        # race features
        _race_features(out, src, race, d, head, hx0, hx1, hy0, hy1, eye_row, skin, look)
    eye_px = {p for p in R["head"] if src.get_at(p)[:3] == EYE}
    if CHIBI and head:
        out = wardrobe.apply(out, src, look, R, d, eye_px, chibi=True)
        anchor = _erase_head(out, src, R)
        out = wardrobe.reshape(out, look, FOOT_Y)
        out = _place_chibi_head(out, look, d, anim, idx, anchor)
    else:
        if head and d in ("down", "side") and not look.get("helm"):
            _face(out, src, d, head, eye_px, skin, look)
        out = wardrobe.apply(out, src, look, R, d, eye_px)
        out = wardrobe.reshape(out, look, FOOT_Y)
    smear = None
    if info.smear is not None:
        smear = info.smear.copy()
        tintc = look.get("smear")
        if tintc:
            smear.fill((*tintc, 255), special_flags=pygame.BLEND_RGBA_MULT)
    return out, smear


CHIBI = True       # big-headed chibi characters (see chibi.py); False draws the rig's own small head


def _erase_head(out, src, R):
    """Remove the rig's head (and its outline) from a painted frame. Returns where the new head goes:
    (centre x, chin y, rotation in degrees) - rotated when the body lies down (death, knockdowns)."""
    head = R["head"]
    hx0 = min(p[0] for p in head)
    hx1 = max(p[0] for p in head)
    hy0 = min(p[1] for p in head)
    hy1 = max(p[1] for p in head)
    clear = set(head)
    for (x, y) in head:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            q = (x + dx, y + dy)
            if 0 <= q[0] < FW and 0 <= q[1] < FW and q not in clear and src.get_at(q)[:3] == OUTLINE \
                    and q not in R["torso"] and q not in R["arms"]:
                clear.add(q)
    for q in clear:
        out.set_at(q, (0, 0, 0, 0))
    cx, cy = (hx0 + hx1) / 2, (hy0 + hy1) / 2
    torso = R["torso"]
    rot = 0
    if torso:
        tx = sum(p[0] for p in torso) / len(torso)
        ty = sum(p[1] for p in torso) / len(torso)
        dx, dy = cx - tx, cy - ty
        if abs(dx) > abs(dy) * 1.3:
            rot = 90 if dx < 0 else -90
        elif dy > 2:
            rot = 180
    return cx, hy1 + 1, cy, rot


def _place_chibi_head(out, look, d, anim, idx, anchor):
    from . import chibi
    cx, chin, cy, rot = anchor
    mood = "hurt" if anim == "hit" else ("ko" if anim == "death" and idx >= 3 else "normal")
    back, front = chibi.head(look, d, mood)
    dy = {"tall": -1, "short": 1}.get(look.get("height"), 0)
    final = pygame.Surface((FW, FW), pygame.SRCALPHA)
    if rot:
        front = pygame.transform.rotate(front, rot)
        back = pygame.transform.rotate(back, rot) if back is not None else None
        pos = (int(round(cx - front.get_width() / 2)), int(round(cy + dy - front.get_height() / 2)))
    else:
        ax, ay = chibi.ANCHOR
        pos = (int(round(cx + 0.5 - ax)), int(chin + dy - ay))
    if back is not None:
        final.blit(back, pos)
    final.blit(out, (0, 0))
    final.blit(front, pos)
    return final


LONG_STYLES = (1, 4, 5, 7, 8)     # long, ponytail, bun, curly, braids: side locks reach the jaw
EXPRESSIONS = ("neutral", "smile", "grin", "stern", "sad")


def _bangs(out, src, put, head, d, style, hair, hx0, hx1, hy0, hy1, rows, eye_row):
    """Anime-style fringe: a jagged row of locks over the forehead and side locks framing the face."""
    if d == "up":
        return
    er = eye_row if eye_row is not None else hy0 + 8
    brow = er - 2                               # keep the brows and eyes clear
    top = hy0 + rows
    pattern = {0: (2, 1, 2, 1), 1: (2, 2, 1, 2), 2: (1, 0, 1, 0), 4: (2, 1, 1, 2), 5: (1, 2, 1, 2), 6: (0, 0, 0, 0),
               7: (2, 1, 2, 2), 8: (1, 2, 2, 1), 9: (2, 1, 3, 1)}.get(style, (2, 1, 2, 1))
    deep = tuple(int(c * 0.78) for c in hair)

    def paint(x, y, col):
        if (x, y) in head and y < brow:
            c = src.get_at((x, y))
            if (c.r, c.g, c.b) != (0, 0, 0):
                put((x, y), col)

    if d == "down":
        for i, x in enumerate(range(hx0 + 1, hx1)):
            depth = pattern[i % len(pattern)]
            for k in range(depth):
                paint(x, top + k, hair if k < depth - 1 else deep)
        if style not in (2, 6):
            lock_end = er + 1 if style in LONG_STYLES else er - 1
            for y in range(top, lock_end + 1):
                for x in (hx0 + 1, hx1 - 1):
                    if (x, y) in head:
                        put((x, y), deep if y > er - 2 else hair)
    else:   # side: fringe over the brow at the front of the face (side frames face right)
        cx = (hx0 + hx1) // 2
        for i, x in enumerate(range(cx, hx1)):
            depth = pattern[i % len(pattern)]
            for k in range(depth):
                paint(x, top + k, hair if k < depth - 1 else deep)


def _mouth(out, src, head, d, hx0, hx1, hy1, skin, look):
    """A tiny mouth gives the face an expression (look key 'expression')."""
    if d == "up":
        return
    expr = look.get("expression", "neutral")
    lip = (196, 112, 108)
    dark = tuple(int(c * 0.62) for c in skin)
    y = hy1 - 1

    def px(x, yy, col):
        if (x, yy) in head:
            c = src.get_at((x, yy))
            if (c.r, c.g, c.b) not in ((0, 0, 0), EYE):
                out.set_at((x, yy), (*col, 255))

    if d == "down":
        cx = (hx0 + hx1) // 2
        if expr == "smile":
            px(cx, y, lip)
            px(cx + 1, y, lip)
        elif expr == "grin":
            px(cx, y, (250, 245, 240))
            px(cx + 1, y, (250, 245, 240))
            px(cx - 1, y - 1, dark)
            px(cx + 2, y - 1, dark)
        elif expr == "stern":
            px(cx, y, dark)
            px(cx + 1, y, dark)
            px(cx - 1, y, dark)
        elif expr == "sad":
            px(cx, y, dark)
            px(cx + 1, y, dark)
            px(cx - 1, y + 1, dark)
            px(cx + 2, y + 1, dark)
        else:
            px(cx, y, dark)
    else:
        x = hx1 - 2
        px(x, y, lip if expr in ("smile", "grin") else dark)


FACE_MARKS = ("none", "freckles", "blush", "scar", "beauty_mark", "tattoo")


def _face(out, src, d, head, eye_px, skin, look):
    """Eyes with an iris colour and a catch-light (the anime-style 'shine'), plus optional face marks.
    Works from the eye pixels the rig provides, so it follows every frame and both front/side views."""
    if not eye_px:
        return
    cx = (min(p[0] for p in head) + max(p[0] for p in head)) / 2

    def skin_at(x, y):
        if (x, y) not in head:
            return False
        c = src.get_at((x, y))
        return (c.r, c.g, c.b) not in (EYE, (0, 0, 0))

    def blend(x, y, col, a):
        if skin_at(x, y):
            c = out.get_at((x, y))
            out.set_at((x, y), (int(c.r + (col[0] - c.r) * a), int(c.g + (col[1] - c.g) * a), int(c.b + (col[2] - c.b) * a), 255))

    iris = tuple(look.get("eye") or (64, 44, 36))
    shine = look.get("eye_style", 1) != 0
    mark = look.get("face", "none")
    mcol = tuple(look.get("face_col") or (190, 60, 60))
    for ex, ey in sorted(eye_px):
        out_dir = -1 if (d == "side" or ex < cx) else 1          # towards the cheek
        if shine:
            out.set_at((ex, ey), (*iris, 255))
            if (ex, ey - 1) in head and src.get_at((ex, ey - 1))[:3] == (0, 0, 0):
                out.set_at((ex, ey - 1), (*tuple(int(c * 0.45) for c in iris), 255))
            sx = ex - 1 if d != "side" else ex - 1
            if skin_at(sx, ey - 1):
                out.set_at((sx, ey - 1), (250, 250, 255, 255))
        cheek = ex + out_dir * 1
        if mark == "blush":
            blend(cheek, ey + 1, (240, 110, 120), 0.55)
            blend(cheek + out_dir, ey + 1, (240, 110, 120), 0.35)
        elif mark == "freckles":
            blend(cheek, ey + 1, tuple(int(c * 0.6) for c in skin), 0.8)
            blend(cheek + out_dir * 2, ey + 1, tuple(int(c * 0.6) for c in skin), 0.8)
            blend(ex, ey + 2, tuple(int(c * 0.65) for c in skin), 0.6)
        elif mark == "tattoo":
            blend(cheek + out_dir, ey, mcol, 0.85)
            blend(cheek + out_dir, ey + 1, mcol, 0.85)
    eyes = sorted(eye_px)
    if mark == "scar":
        ex, ey = eyes[-1]
        for k, y in enumerate(range(ey - 3, ey + 3)):
            x = ex + (1 if k < 3 else 0)
            if (x, y) != (ex, ey):
                blend(x, y, (210, 120, 110), 0.75)
    elif mark == "beauty_mark":
        ex, ey = eyes[0]
        blend(ex + (1 if d == "side" else -1), ey + 2, (60, 36, 30), 0.9)


def _px(out, x, y, col):
    if 0 <= x < FW and 0 <= y < FW:
        out.set_at((x, y), (*col, 255))


def _race_features(out, src, race, d, head, hx0, hx1, hy0, hy1, eye_row, skin, look):
    er = eye_row if eye_row is not None else hy0 + 4
    dark = tuple(int(c * 0.6) for c in skin)
    if race == "sylth" and d != "up":
        # long swept-back ears
        if d == "down":
            for side, x in ((-1, hx0 - 1), (1, hx1 + 1)):
                _px(out, x, er - 1, skin)
                _px(out, x + side, er - 2, skin)
                _px(out, x + side, er - 1, OUTLINE)
                _px(out, x + 2 * side, er - 3, OUTLINE)
                _px(out, x, er, OUTLINE)
        else:
            x = int((hx0 + hx1) / 2) - 1
            _px(out, x, er - 1, skin)
            _px(out, x - 1, er - 2, skin)
            _px(out, x - 2, er - 3, OUTLINE)
    elif race == "murrok":
        if d == "down":
            mid = (hx0 + hx1) // 2
            for x in (mid - 2, mid + 2):
                _px(out, x, hy1 - 1, (240, 236, 220))
            _px(out, hx0, hy0 - 1, dark)
            _px(out, hx1, hy0 - 1, dark)
        elif d == "side":
            _px(out, hx1 - 1, hy1 - 1, (240, 236, 220))
    elif race == "kethari":
        for i, p in enumerate(sorted(head)):
            if i % 9 == 4 and p[1] > hy0 + 2:
                c = out.get_at(p)
                if (c.r, c.g, c.b) != OUTLINE and (c.r, c.g, c.b) != EYE:
                    out.set_at(p, (*dark, 255))
    if look.get("warpaint") and d != "up":
        for x in range(hx0 + 1, hx1):
            if (x + er) % 2 == 0:
                c = out.get_at((x, er + 1)) if 0 <= er + 1 < FW else None
                if c and c.a and (c.r, c.g, c.b) != OUTLINE:
                    out.set_at((x, er + 1), (*look["warpaint"], 255))


def clear_cache():
    _looks.clear()
