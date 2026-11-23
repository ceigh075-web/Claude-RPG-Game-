"""Modular clothing, hair, headwear, accessories and body builds layered onto the Body_A rig.

Each piece is drawn per animation frame from the body regions found by charsprites (head / torso / arms /
legs / feet), so it follows every pose of every animation - idle, walk, run, attacks, hit and death -
in all four directions. Pieces may extend past the bare silhouette (hats, hair volume, capes, robes,
beards) and get the same 1px dark outline as the pack art.

Look keys read here (all optional, so older looks keep working):
  hair_style  0 short | 1 long | 2 cropped | 3 bald | 4 ponytail | 5 bun | 6 mohawk | 7 curly | 8 braids | 9 spiky
  beard       0 none | 1 stubble | 2 full | 3 moustache | 4 long
  hat, hat_col     cap | wide | wizard | crown | bandana | horns | circlet | miner | feather_cap | hood_up
  outfit, outfit_col   tunic | robe | dress | coat | vest | apron | tabard | bare
  accent      second outfit colour (vest panels, trim, tabard emblem)
  cape        colour of a cape/cloak
  belt        colour
  acc         list of: necklace, scarf, satchel, eyepatch, glasses, pauldrons, quiver, earring, fur
  build       stout | slim ;  height  tall | short
"""
import pygame

OUT = (0, 0, 0)
GOLD = (232, 196, 82)


def _shade(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c)


class Canvas:
    """Tracks pixels added outside the original silhouette so they can be outlined afterwards."""

    def __init__(self, out, src):
        self.out, self.src = out, src
        self.added = set()

    def opaque(self, x, y):
        return 0 <= x < 64 and 0 <= y < 64 and self.out.get_at((x, y)).a > 0

    def body(self, x, y):
        return 0 <= x < 64 and 0 <= y < 64 and self.src.get_at((x, y)).a > 0

    def set(self, x, y, col, behind=False):
        if not (0 <= x < 64 and 0 <= y < 64):
            return
        if behind and self.opaque(x, y):
            return
        if not self.body(x, y):
            self.added.add((x, y))
        self.out.set_at((x, y), (*(max(0, min(255, int(v))) for v in col[:3]), 255))

    def recolor(self, x, y, col, keep_outline=True):
        """Recolour a body pixel keeping its shading."""
        if not self.body(x, y):
            return
        c = self.src.get_at((x, y))
        if keep_outline and (c.r, c.g, c.b) == OUT:
            return
        L = (c.r * 0.3 + c.g * 0.59 + c.b * 0.11) / 150.0
        f = max(0.5, min(1.3, L))
        self.out.set_at((x, y), (*_shade(col, f), 255))

    def outline(self):
        for (x, y) in list(self.added):
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < 64 and 0 <= ny < 64 and self.out.get_at((nx, ny)).a == 0:
                    self.out.set_at((nx, ny), (*OUT, 255))


def _bbox(px):
    if not px:
        return None
    xs = [p[0] for p in px]
    ys = [p[1] for p in px]
    return min(xs), min(ys), max(xs), max(ys)


def apply(out, src, look, R, d, eye_px):
    """Draw all wardrobe pieces onto `out` (64x64, side views face right)."""
    cv = Canvas(out, src)
    head, torso, legs, feet, arms = R["head"], R["torso"], R["legs"], R["feet"], R["arms"]
    hb = _bbox(head)
    tb = _bbox(torso)
    lb = _bbox(legs | feet) if (legs or feet) else None
    if not hb or not tb:
        return out
    hx0, hy0, hx1, hy1 = hb
    hcx = (hx0 + hx1) // 2
    tx0, ty0, tx1, ty1 = tb
    tcx = (tx0 + tx1) // 2
    hair = tuple(look.get("hair", (60, 40, 30)))
    acc = set(look.get("acc", ()))
    eyes = sorted(eye_px)
    eye_row = eyes[0][1] if eyes else hy0 + 4

    # ---------------------------------------------------------------- cape (behind everything)
    cape = look.get("cape")
    if cape:
        cape = tuple(cape)
        bottom = (lb[3] - 2) if lb else ty1 + 6
        if d == "up":
            core = torso | legs
            for y in range(ty0, bottom + 1):
                row = [p[0] for p in core if p[1] == y]
                if not row:
                    continue
                spread = 1 + (y - ty0) // 5
                for x in range(min(row) - spread, max(row) + spread + 1):
                    cv.set(x, y, _shade(cape, 0.9 if (x + y) % 5 else 0.8))
        elif d == "down":
            core = torso | legs
            for y in range(ty0 + 1, bottom + 1):
                row = [p[0] for p in core if p[1] == y]
                if not row:
                    continue
                spread = 1 + (y - ty0) // 6
                cv.set(min(row) - spread, y, _shade(cape, 0.75), behind=True)
                cv.set(max(row) + spread, y, _shade(cape, 0.75), behind=True)
            for x in range(tx0, tx1 + 1):      # clasp / collar
                cv.recolor(x, ty0, cape)
            cv.set(tcx, ty0, GOLD)
        else:
            core = torso | legs
            for y in range(ty0, bottom + 1):
                row = [p[0] for p in core if p[1] == y]
                if not row:
                    continue
                back = min(row)
                spread = 1 + (y - ty0) // 4
                for x in range(back - spread, back + 1):
                    cv.set(x, y, _shade(cape, 0.85 if (y % 4) else 0.72), behind=True)

    # ---------------------------------------------------------------- quiver on the back
    if "quiver" in acc:
        qc = (110, 72, 40)
        if d == "up":
            for y in range(ty0 - 3, ty0 + 6):
                cv.set(tcx + 2, y, qc)
                cv.set(tcx + 3, y, _shade(qc, 0.8))
            for x in (tcx + 1, tcx + 2, tcx + 3):
                cv.set(x, ty0 - 4, (230, 230, 230))
        elif d == "side":
            for y in range(ty0 - 3, ty0 + 6):
                cv.set(tx0 - 1, y, qc, behind=True)
            cv.set(tx0 - 1, ty0 - 4, (230, 230, 230), behind=True)
            cv.set(tx0 - 2, ty0 - 4, (200, 60, 50), behind=True)
        else:
            cv.set(tx1 + 1, ty0 - 2, (230, 230, 230), behind=True)
            cv.set(tx1 + 1, ty0 - 1, qc, behind=True)

    # ---------------------------------------------------------------- outfit
    outfit = look.get("outfit", "tunic")
    ocol = tuple(look.get("outfit_col", look.get("shirt", (90, 90, 140))))
    accent = tuple(look.get("accent", _shade(ocol, 0.7)))
    if outfit in ("robe", "dress", "coat") and lb:
        lx0, ly0, lx1, ly1 = lb
        hem = ly1 - (1 if outfit == "robe" else (2 if outfit == "dress" else 3))
        top = ty1 - 1
        for y in range(top, hem + 1):
            flare = 0 if outfit == "coat" else (y - top) // (3 if outfit == "dress" else 5)
            row = [p[0] for p in (legs | torso) if p[1] == y]
            if not row:
                continue
            x0, x1 = min(row) - flare, max(row) + flare
            for x in range(x0, x1 + 1):
                if cv.body(x, y):
                    cv.recolor(x, y, ocol if outfit != "coat" or (x - x0) % 6 else _shade(ocol, 0.85))
                else:
                    cv.set(x, y, _shade(ocol, 0.85))
        # hem trim
        row = [x for x in range(64) if cv.opaque(x, hem) and (x, hem) in cv.added or cv.body(x, hem)]
        for x in row:
            if (x, hem) in legs or (x, hem) in cv.added:
                cv.set(x, hem, accent)
        for p in torso:
            cv.recolor(*p, ocol)
    elif outfit == "vest":
        for p in torso:
            x, y = p
            centre = abs(x - tcx) <= 1 if d != "side" else x >= tx1 - 1
            cv.recolor(x, y, tuple(look.get("shirt", ocol)) if centre else ocol)
    elif outfit == "apron":
        ac = look.get("accent", (214, 204, 182))
        lim_y = (lb[1] + 3) if lb else ty1 + 3
        for p in torso | legs:
            x, y = p
            if y < ty0 + 2 or y > lim_y:
                continue
            if d == "up":
                if y == ty0 + 3:
                    cv.recolor(x, y, ac)
                continue
            front = abs(x - tcx) <= 2 if d == "down" else x >= tcx
            if front:
                cv.recolor(x, y, ac)
    elif outfit == "tabard":
        for p in torso | legs:
            x, y = p
            if lb and y > lb[1] + 3:
                continue
            band = abs(x - tcx) <= 1 if d in ("down", "up") else x >= tx1 - 2
            if band:
                cv.recolor(x, y, ocol)
        if d == "down":
            cv.set(tcx, ty0 + 2, accent)
            cv.set(tcx, ty0 + 3, accent)
            cv.set(tcx - 1, ty0 + 3, accent)
            cv.set(tcx + 1, ty0 + 3, accent)
    elif outfit == "bare":
        for p in torso:
            cv.recolor(*p, tuple(look.get("skin", (200, 150, 110))))
        for p in arms:
            cv.recolor(*p, tuple(look.get("skin", (200, 150, 110))))

    # ---------------------------------------------------------------- belt
    belt = look.get("belt")
    if belt:
        for x in range(tx0, tx1 + 1):
            if (x, ty1) in torso:
                cv.recolor(x, ty1, tuple(belt))
        if d == "down":
            cv.set(tcx, ty1, GOLD)

    # ---------------------------------------------------------------- shoulder / neck accessories
    if "pauldrons" in acc:
        pc = tuple(look.get("armor") or (150, 154, 166))
        if d in ("down", "up"):
            for x0 in (tx0 - 1, tx1):
                for dx in range(2):
                    for dy in range(2):
                        cv.set(x0 + dx, ty0 + dy, _shade(pc, 1.1 if dy == 0 else 0.85))
        else:
            for dx in range(3):
                cv.set(tcx - 1 + dx, ty0, _shade(pc, 1.1))
                cv.set(tcx - 1 + dx, ty0 + 1, _shade(pc, 0.85))
    if "fur" in acc:
        fc = (150, 120, 90)
        for x in range(tx0 - 1, tx1 + 2):
            cv.set(x, ty0, _shade(fc, 1.0 if x % 2 else 0.8))
            if x % 2 == 0:
                cv.set(x, ty0 - 1, fc, behind=True)
    if "scarf" in acc:
        sc = tuple(look.get("scarf", (180, 60, 50)))
        for x in range(tx0, tx1 + 1):
            cv.recolor(x, ty0, sc)
        if d == "side":
            cv.set(tx0 - 1, ty0, sc, behind=True)
            cv.set(tx0 - 2, ty0 + 1, sc, behind=True)
        elif d == "down":
            cv.recolor(tcx + 1, ty0 + 1, sc)
            cv.recolor(tcx + 1, ty0 + 2, sc)
    if "necklace" in acc and d != "up":
        col = tuple(look.get("necklace", GOLD))
        if d == "down":
            for x in range(tcx - 2, tcx + 3):
                if abs(x - tcx) == 2:
                    cv.recolor(x, ty0, col)
                else:
                    cv.recolor(x, ty0 + 1, col)
            cv.set(tcx, ty0 + 2, col)
        else:
            cv.recolor(tx1, ty0 + 1, col)
    if "satchel" in acc:
        strap = (96, 64, 40)
        if d == "down":
            for i in range(ty1 - ty0 + 1):
                cv.recolor(tx0 + i * (tx1 - tx0) // max(1, ty1 - ty0), ty0 + i, strap, keep_outline=True)
            for dx in range(3):
                for dy in range(3):
                    cv.set(tx1 + dx, ty1 + dy - 1, _shade((150, 104, 60), 1.0 if dy else 1.2))
        elif d == "side":
            for dx in range(3):
                for dy in range(3):
                    cv.set(tx0 - 1 + dx, ty1 + dy, _shade((150, 104, 60), 1.0 if dy else 1.2))
        else:
            for i in range(ty1 - ty0 + 1):
                cv.recolor(tx1 - i * (tx1 - tx0) // max(1, ty1 - ty0), ty0 + i, strap)

    # ---------------------------------------------------------------- hair volume & styles
    style = look.get("hair_style", 0)
    hat = look.get("hat")
    hairy = style not in (3,) and not look.get("helm") and not (isinstance(look.get("hood"), (list, tuple)))
    if hairy:
        if style == 1 or style == 8:          # long hair / braids fall past the head
            ln = 5 if style == 1 else 6
            if d == "down":
                for y in range(hy0 + 2, hy1 + ln):
                    if style == 1:
                        cv.set(hx0 - 1, y, hair, behind=True)
                        cv.set(hx1 + 1, y, hair, behind=True)
                    else:
                        cv.set(hx0, y, _shade(hair, 0.85 if y % 2 else 1.0))
                        cv.set(hx1, y, _shade(hair, 0.85 if y % 2 else 1.0))
            elif d == "up":
                for y in range(hy1 - 1, hy1 + ln):
                    for x in range(hx0 + 1, hx1):
                        cv.set(x, y, _shade(hair, 0.9 if (x + y) % 3 else 0.75))
            else:
                for y in range(hy0 + 2, hy1 + ln):
                    cv.set(hx0 - 1, y, hair, behind=True)
                    if y < hy1 + ln - 1:
                        cv.set(hx0, y, hair)
        elif style == 4:                       # ponytail
            if d == "side":
                for i, y in enumerate(range(hy0 + 2, hy0 + 9)):
                    cv.set(hx0 - 1 - (1 if 2 <= i <= 4 else 0), y, hair, behind=True)
            elif d == "up":
                for y in range(hy0 + 3, hy1 + 4):
                    cv.set(hcx, y, hair)
                    cv.set(hcx + 1, y, _shade(hair, 0.8))
            else:
                cv.set(hx1 + 1, hy0 + 3, hair, behind=True)
                cv.set(hx1 + 1, hy0 + 4, hair, behind=True)
        elif style == 5:                       # bun
            bx = hcx if d != "side" else hx0 + 1
            for dx in (-1, 0, 1):
                for dy in (-2, -1):
                    cv.set(bx + dx, hy0 + dy, _shade(hair, 1.0 if dy == -1 else 1.15))
        elif style == 6:                       # mohawk
            for x in ((hcx - 1, hcx, hcx + 1) if d == "side" else (hcx, hcx + 1)):
                for dy in range(1, 4):
                    cv.set(x, hy0 - dy, _shade(hair, 1.0 if dy < 3 else 1.2))
        elif style == 7:                       # curly / big hair: a ring of volume around the crown
            for x in range(hx0 - 1, hx1 + 2):
                cv.set(x, hy0 - 1, _shade(hair, 0.85 if x % 2 else 1.05))
            for y in range(hy0, hy0 + 5):
                cv.set(hx0 - 1, y, _shade(hair, 0.9), behind=True)
                cv.set(hx1 + 1, y, _shade(hair, 0.9), behind=True)
        elif style == 9:                       # spiky
            for x in range(hx0, hx1 + 1, 2):
                cv.set(x, hy0 - 1, _shade(hair, 1.1))
            cv.set(hcx, hy0 - 2, hair)

    # ---------------------------------------------------------------- beard
    beard = look.get("beard", 0)
    if beard and d != "up":
        bc = _shade(hair, 0.95)
        mouth = eye_row + 3
        if d == "down":
            if beard == 1:
                for x in range(hx0 + 2, hx1 - 1):
                    if (x + mouth) % 2 == 0:
                        cv.recolor(x, mouth, _shade(bc, 0.8))
            elif beard == 3:
                for x in range(hcx - 2, hcx + 3):
                    cv.recolor(x, mouth - 1, bc)
            else:
                for y in range(mouth - 1, hy1 + 1):
                    for x in range(hx0 + 1, hx1):
                        if y == mouth - 1 and (abs(x - hcx) > 2 or (x - hcx) in (0,)):
                            continue            # moustache row: leave the cheeks, part in the middle
                        if y == mouth and abs(x - hcx) <= 1 and y < hy1:
                            continue            # mouth stays visible
                        if cv.body(x, y) and (y > mouth - 1 or abs(x - hcx) <= 2):
                            cv.recolor(x, y, bc)
                extra = 2 if beard == 2 else 5
                for y in range(hy1 + 1, hy1 + extra):
                    w = max(0, (hx1 - hx0) // 2 - (y - hy1) - 1)
                    for x in range(hcx - w, hcx + w + 1):
                        cv.set(x, y, _shade(bc, 0.9 if (x + y) % 2 else 1.0))
        else:
            if beard in (2, 4):
                for y in range(mouth - 1, hy1 + (1 if beard == 2 else 4)):
                    for x in range(hcx, hx1 + 1):
                        if cv.body(x, y):
                            cv.recolor(x, y, bc)
                        elif beard == 4 and y > hy1:
                            cv.set(x - 1, y, bc)
            elif beard == 3:
                cv.recolor(hx1 - 1, mouth - 1, bc)
                cv.recolor(hx1, mouth - 1, bc)

    # ---------------------------------------------------------------- face accessories
    if eyes and d != "up":
        if "glasses" in acc:
            gc = (60, 50, 40)
            for (x, y) in eyes:
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    if (x + dx, y + dy) not in eye_px:
                        cv.recolor(x + dx, y + dy, gc, keep_outline=False)
            for (x, y) in eyes:
                cv.set(x, y, (200, 230, 240))
        if "eyepatch" in acc:
            ex, ey = eyes[0] if d == "down" else eyes[-1]
            cv.set(ex, ey, (20, 18, 20))
            for x in range(hx0, hx1 + 1):
                if cv.body(x, ey - 1):
                    cv.recolor(x, ey - 1, (30, 26, 26), keep_outline=False)
        if "earring" in acc:
            cv.set(hx0 - 1 if d == "down" else hcx - 1, eye_row + 2, GOLD)

    # ---------------------------------------------------------------- headwear
    if hat:
        hc = tuple(look.get("hat_col", (120, 80, 50)))
        light, dark = _shade(hc, 1.2), _shade(hc, 0.7)
        if hat == "wide":
            y = hy0 + 2
            for x in range(hx0 - 3, hx1 + 4):
                cv.set(x, y, dark if x in (hx0 - 3, hx1 + 3) else hc)
            for yy in range(hy0 - 2, y):
                for x in range(hx0 + 1, hx1):
                    cv.set(x, yy, light if yy == hy0 - 2 else hc)
            for x in range(hx0 + 1, hx1):
                cv.set(x, y - 1, tuple(look.get("hat_band", dark)))
        elif hat in ("cap", "miner", "feather_cap"):
            for yy in range(hy0 - 1, hy0 + 3):
                for x in range(hx0, hx1 + 1):
                    if yy >= hy0 and not cv.body(x, yy):
                        continue
                    cv.set(x, yy, light if yy == hy0 - 1 else hc)
            if d == "side":
                for x in range(hx1, hx1 + 3):
                    cv.set(x, hy0 + 2, dark)
            elif d == "down":
                for x in range(hx0, hx1 + 1):
                    cv.set(x, hy0 + 3, dark)
            if hat == "miner" and d != "up":
                lx = hcx if d == "down" else hx1 - 1
                cv.set(lx, hy0, (255, 240, 160))
                cv.set(lx, hy0 + 1, (255, 220, 120))
            if hat == "feather_cap":
                fx = hx0 if d != "side" else hx0 + 1
                for i in range(4):
                    cv.set(fx - i // 2, hy0 - 2 - i, tuple(look.get("feather", (220, 60, 50))))
        elif hat == "wizard":
            base_y = hy0 + 2
            for x in range(hx0 - 2, hx1 + 3):
                cv.set(x, base_y, dark)
            height = 9
            for i in range(height):
                y = base_y - 1 - i
                half = max(0, (hx1 - hx0 + 2) // 2 - (i * (hx1 - hx0 + 2)) // (2 * height) - 0)
                lean = i // 4 if d != "up" else 0
                for x in range(hcx - half + lean, hcx + half + 1 + lean):
                    cv.set(x, y, light if x == hcx - half + lean else hc)
            cv.set(hcx + 2, base_y - 1, tuple(look.get("hat_band", GOLD)))
        elif hat == "crown":
            for x in range(hx0, hx1 + 1):
                cv.set(x, hy0, GOLD)
                cv.set(x, hy0 + 1, _shade(GOLD, 0.8))
            for x in range(hx0, hx1 + 1, 2):
                cv.set(x, hy0 - 1, GOLD)
            if d == "down":
                cv.set(hcx, hy0 + 1, (200, 40, 60))
                cv.set(hcx, hy0 - 2, GOLD)
        elif hat == "circlet":
            for x in range(hx0, hx1 + 1):
                if cv.body(x, hy0 + 2):
                    cv.set(x, hy0 + 2, tuple(look.get("hat_col", (210, 210, 230))))
            if d == "down":
                cv.set(hcx, hy0 + 2, (120, 220, 240))
        elif hat == "bandana":
            for x in range(hx0, hx1 + 1):
                for yy in (hy0, hy0 + 1, hy0 + 2):
                    if cv.body(x, yy):
                        cv.recolor(x, yy, hc, keep_outline=False)
            if d in ("side", "up"):
                kx = hx0 - 1 if d == "side" else hcx
                cv.set(kx, hy0 + 2, hc)
                cv.set(kx - (1 if d == "side" else 0), hy0 + 3, dark)
        elif hat == "horns":
            for x in range(hx0, hx1 + 1):
                if cv.body(x, hy0 + 1):
                    cv.set(x, hy0 + 1, (110, 80, 50))
            bone = (230, 220, 196)
            if d == "side":
                for i in range(3):
                    cv.set(hcx - i, hy0 - i, bone)
            else:
                for s, x in ((-1, hx0), (1, hx1)):
                    cv.set(x + s, hy0, bone)
                    cv.set(x + s, hy0 - 1, bone)
                    cv.set(x + 2 * s, hy0 - 2, bone)
        elif hat == "hood_up":
            for p in head:
                x, y = p
                if y < eye_row - 1 or x in (hx0, hx1) or (d == "up") or (d == "side" and x < hcx):
                    cv.recolor(x, y, hc, keep_outline=False) if cv.src.get_at(p)[:3] != OUT else None
            for x in range(hx0 - 1, hx1 + 2):
                cv.set(x, hy0 - 1, hc)
            if d == "side":
                cv.set(hx0 - 1, hy0, dark, behind=True)
                cv.set(hx0 - 2, hy0 + 1, dark, behind=True)

    cv.outline()
    return out


def reshape(surf, look, foot_y):
    """Body proportions: stout widens the torso/legs by a column, slim removes one; tall/short add or remove
    rows between the shoulders and the feet. Feet stay on the same baseline."""
    build = look.get("build")
    height = look.get("height")
    if not build and not height:
        return surf
    r = surf.get_bounding_rect()
    if r.w == 0:
        return surf
    out = surf
    if build in ("stout", "slim"):
        cx = r.x + r.w // 2
        top = r.y + r.h // 3
        new = pygame.Surface((64, 64), pygame.SRCALPHA)
        new.blit(out, (0, 0), (0, 0, 64, top))
        if build == "stout":
            new.blit(out, (0, top), (0, top, cx + 1, 64 - top))
            new.blit(out, (cx + 1, top), (cx, top, 64 - cx - 1, 64 - top))
            new.blit(out, (0, 0), (0, 0, 64, top))
        else:
            new.blit(out, (0, top), (0, top, cx, 64 - top))
            new.blit(out, (cx, top), (cx + 1, top, 64 - cx - 1, 64 - top))
        out = new
    if height in ("tall", "short"):
        mid = r.y + int(r.h * 0.55)
        new = pygame.Surface((64, 64), pygame.SRCALPHA)
        if height == "tall":       # duplicate one row near the waist: everything above moves up 1px
            new.blit(out, (0, 0), (0, 1, 64, mid))
            new.blit(out, (0, mid), (0, mid, 64, 64 - mid))
        else:
            new.blit(out, (0, 1), (0, 0, 64, mid))
            new.blit(out, (0, mid + 1), (0, mid + 1, 64, 63 - mid))
        out = new
    return out
