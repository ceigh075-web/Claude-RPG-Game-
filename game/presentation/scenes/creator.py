"""Character creator: every part of the look, with a live animated preview (idle, walk and attack in all four
directions). Used for a new character and, any time later, from the Tab menu ("Appearance").

The look is a plain dict (see wardrobe.py for the keys), the same one the in-game sprite compositor reads,
so whatever you pick here is exactly what you see in the world, in every animation.
"""
import copy
import random

import pygame

from ...core.scene import Scene
from .. import charsprites, visuals
from ..looks import BOOTS, BRIGHT, EARTH, MUTED, PANTS, RICH, build
from ..ui import widgets as ui
from .common import is_close

W, H = 1280, 720

HAIR_STYLES = ["Short", "Long", "Cropped", "Bald", "Ponytail", "Bun", "Mohawk", "Curly", "Braids", "Spiky"]
BEARDS = ["None", "Stubble", "Full beard", "Moustache", "Long beard"]
HATS = [None, "cap", "wide", "wizard", "bandana", "circlet", "feather_cap", "hood_up", "miner", "horns", "crown"]
OUTFITS = ["tunic", "robe", "dress", "coat", "vest", "apron", "tabard", "bare"]
ACCESSORIES = ["necklace", "scarf", "satchel", "earring", "glasses", "eyepatch", "pauldrons", "quiver", "fur"]
FACE_MARKS = list(charsprites.FACE_MARKS)
BUILDS = [None, "slim", "stout"]
HEIGHTS = [None, "short", "tall"]
EYES = [(64, 44, 36), (40, 90, 160), (60, 130, 80), (120, 80, 40), (130, 60, 160), (180, 50, 60), (40, 150, 160),
        (200, 160, 40), (90, 90, 100), (20, 20, 24)]
EXTRA_HAIR = [(20, 18, 22), (240, 230, 220), (230, 140, 170), (110, 190, 210), (70, 90, 190), (150, 90, 200),
              (90, 160, 90), (200, 60, 50), (240, 200, 110)]
CLOTH = RICH + BRIGHT + MUTED + EARTH + [(230, 226, 214), (36, 34, 40)]
PAINT = [None, (170, 40, 40), (40, 80, 170), (230, 230, 230), (30, 30, 30), (220, 170, 40)]
CAPES = [None] + RICH + MUTED[:3]
BELTS = [None, (70, 50, 36), (40, 34, 30), (150, 110, 60), (120, 40, 40)]


def _skin_tones(race):
    """The race's own tones plus lighter and darker variations of each (races keep their identity)."""
    out = []
    for s in race["skin"]:
        for f in (1.0, 1.12, 0.85):
            c = tuple(max(0, min(255, int(v * f))) for v in s)
            if c not in out:
                out.append(c)
    return out


def _name(c):
    return c.replace("_", " ").title() if isinstance(c, str) else "None"


class CharacterCreatorScene(Scene):
    """Edits `look` in place when confirmed; `on_done(look)` is called with the result (or None if cancelled)."""
    overlay = False

    def __init__(self, game, look, race_id, on_done=None, title="Appearance", pronouns="they/them"):
        super().__init__(game)
        self.race_id = race_id
        self.race = self.data.races[race_id]
        self.original = look
        self.look = copy.deepcopy(look)
        self.look["race"] = race_id
        self.on_done = on_done
        self.title = title
        self.pronouns = pronouns
        self.t = 0.0
        self.index = 0
        self.acc_i = 0
        self.anim = 0                   # 0 idle, 1 walk, 2 attack
        self.turn = 0
        self.rows = self.build_rows()
        self.overlay = getattr(game, "state", None) is not None

    # ------------------------------------------------------------ rows: (group, label, kind, key, options)
    def build_rows(self):
        hair_cols = [tuple(c) for c in self.race["hair"]] + EXTRA_HAIR
        return [
            ("Body", "Skin tone", "cycle", "skin", _skin_tones(self.race)),
            ("Body", "Build", "cycle", "build", BUILDS),
            ("Body", "Height", "cycle", "height", HEIGHTS),
            ("Face", "Eye colour", "cycle", "eye", EYES),
            ("Face", "Eye style", "cycle", "eye_style", [1, 0]),
            ("Face", "Face mark", "cycle", "face", FACE_MARKS),
            ("Face", "Face paint", "cycle", "warpaint", PAINT),
            ("Face", "Facial hair", "cycle", "beard", list(range(len(BEARDS)))),
            ("Hair", "Hairstyle", "cycle", "hair_style", list(range(len(HAIR_STYLES)))),
            ("Hair", "Hair colour", "cycle", "hair", hair_cols),
            ("Clothes", "Outfit", "cycle", "outfit", OUTFITS),
            ("Clothes", "Outfit colour", "cycle", "outfit_col", CLOTH),
            ("Clothes", "Trim colour", "cycle", "accent", CLOTH),
            ("Clothes", "Trousers", "cycle", "pants", PANTS + MUTED[:3]),
            ("Clothes", "Boots", "cycle", "boots", BOOTS),
            ("Clothes", "Belt", "cycle", "belt", BELTS),
            ("Clothes", "Cape", "cycle", "cape", CAPES),
            ("Headwear", "Hat", "cycle", "hat", HATS),
            ("Headwear", "Hat colour", "cycle", "hat_col", CLOTH),
            ("Extras", "Accessories", "acc", "acc", ACCESSORIES),
            ("", "Randomize everything", "action", "random", None),
            ("", "Undo all changes", "action", "reset", None),
            ("", "Done", "action", "done", None),
        ]

    # ------------------------------------------------------------ editing
    def value(self, key):
        v = self.look.get(key)
        if key == "eye_style":
            return 1 if v is None else v
        if key == "face":
            return v or "none"
        if key in ("beard", "hair_style"):
            return v or 0
        return tuple(v) if isinstance(v, list) else v

    def cycle(self, row, step):
        _, _, kind, key, opts = row
        if kind == "acc":
            self.acc_i = (self.acc_i + step) % len(opts)
            return
        cur = self.value(key)
        try:
            i = opts.index(cur)
        except ValueError:
            i = -1 if step > 0 else 0
        v = opts[(i + step) % len(opts)]
        if v is None:
            self.look.pop(key, None)
            if key == "hat":
                self.look.pop("hat_col", None)
        else:
            self.look[key] = list(v) if isinstance(v, tuple) else v
            if key == "outfit_col":
                self.look["shirt"] = list(v)        # the sleeves follow the outfit
            if key == "hat" and "hat_col" not in self.look:
                self.look["hat_col"] = list(EARTH[0])

    def toggle_acc(self):
        a = ACCESSORIES[self.acc_i]
        acc = list(self.look.get("acc", []))
        if a in acc:
            acc.remove(a)
        else:
            acc.append(a)
            if a == "scarf":
                self.look.setdefault("scarf", list(RICH[0]))
        self.look["acc"] = acc

    def randomize(self):
        rng = random.Random()
        new = build(rng, self.race, self.race_id, "citizen", None, rng.randint(18, 40), self.pronouns)
        new["eye"] = list(rng.choice(EYES))
        if rng.random() < 0.3:
            new["face"] = rng.choice(FACE_MARKS[1:])
        self.look = new

    def finish(self, keep):
        if keep:
            if isinstance(self.original, dict):
                self.original.clear()
                self.original.update(self.look)       # in place: the in-game sprite follows at once
            if self.on_done:
                self.on_done(self.original)
        elif self.on_done:
            self.on_done(None)
        self.close()

    def handle(self, ev):
        if is_close(ev):
            self.finish(False)
            return
        if ev.type != pygame.KEYDOWN:
            return
        k = ev.key
        row = self.rows[self.index]
        if k in (pygame.K_UP, pygame.K_w):
            self.index = (self.index - 1) % len(self.rows)
        elif k in (pygame.K_DOWN, pygame.K_s, pygame.K_TAB):
            self.index = (self.index + 1) % len(self.rows)
        elif k in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d):
            step = -1 if k in (pygame.K_LEFT, pygame.K_a) else 1
            if row[2] in ("cycle", "acc"):
                self.cycle(row, step)
        elif k == pygame.K_q:
            self.turn = (self.turn + 1) % 4
        elif k == pygame.K_v:
            self.anim = (self.anim + 1) % 3
        elif k == pygame.K_r:
            self.randomize()
        elif k in (pygame.K_RETURN, pygame.K_SPACE):
            if row[2] == "acc":
                self.toggle_acc()
            elif row[3] == "random":
                self.randomize()
            elif row[3] == "reset":
                self.look = copy.deepcopy(self.original)
            elif row[3] == "done":
                self.finish(True)
            else:
                self.cycle(row, 1)

    def update(self, dt):
        self.t += dt

    # ------------------------------------------------------------ drawing
    def value_text(self, row):
        _, _, kind, key, opts = row
        if kind == "action":
            return ""
        if kind == "acc":
            a = ACCESSORIES[self.acc_i]
            on = a in self.look.get("acc", [])
            return f"<  {a.title()}: {'worn' if on else 'off'}  >   (Enter toggles)"
        v = self.value(key)
        if key == "hair_style":
            return f"<  {HAIR_STYLES[v]}  >"
        if key == "beard":
            return f"<  {BEARDS[v]}  >"
        if key == "eye_style":
            return "<  Bright (with shine)  >" if v else "<  Plain  >"
        if isinstance(v, tuple) or (v is None and key in ("cape", "belt", "warpaint", "hat_col")):
            return None if v is not None else "<  None  >"
        if v is None and key in ("build", "height", "hat"):
            return "<  " + {"build": "Average", "height": "Average", "hat": "None"}[key] + "  >"
        return f"<  {_name(v)}  >"

    def draw(self, screen):
        if self.overlay:
            ui.dim(screen, 170)
        else:
            from .menu import draw_backdrop
            draw_backdrop(self.game, screen, self.t)
        r = ui.panel(screen, (40, 20, 1200, 680), self.title)
        y = r.y + 46
        group = None
        row_h = 25
        for i, row in enumerate(self.rows):
            g, label, kind, key, opts = row
            if g != group and g:
                ui.text(screen, g, (r.x + 24, y + 2), 17, ui.TEXT_DIM, bold=True)
                group = g
            sel = i == self.index
            rx = r.x + 110
            if sel:
                pygame.draw.rect(screen, ui.PANEL_LIGHT, (rx - 8, y - 2, 560, row_h - 1), border_radius=4)
                pygame.draw.rect(screen, ui.BORDER_HI, (rx - 8, y - 2, 560, row_h - 1), 1, border_radius=4)
            col = ui.ACCENT if sel else ui.TEXT
            ui.text(screen, label, (rx, y), 20, col if kind == "action" else ui.TEXT_DIM, bold=kind == "action")
            vt = self.value_text(row)
            if vt is None:                       # a colour: show a swatch
                v = self.value(key)
                ui.text(screen, "<", (rx + 200, y), 20, col)
                pygame.draw.rect(screen, v, (rx + 222, y + 2, 60, 16), border_radius=3)
                pygame.draw.rect(screen, ui.BORDER, (rx + 222, y + 2, 60, 16), 1, border_radius=3)
                ui.text(screen, ">", (rx + 292, y), 20, col)
                if kind == "cycle" and sel:
                    ui.text(screen, f"{opts.index(v) + 1 if v in opts else '-'}/{len(opts)}", (rx + 320, y), 17,
                            ui.TEXT_DIM)
            elif vt:
                ui.text(screen, vt, (rx + 200, y), 20, col)
            y += row_h
        # preview
        box = pygame.Rect(r.x + 700, r.y + 50, 470, 520)
        pygame.draw.rect(screen, (28, 24, 22), box, border_radius=6)
        pygame.draw.rect(screen, ui.BORDER, box, 2, border_radius=6)
        dirs = ("down", "side", "up", "side")
        flip = self.turn == 3
        d = dirs[self.turn]
        anim = ("idle", "walk", "slice")[self.anim]
        try:
            n = {"idle": 4, "walk": 6, "slice": 8}[anim]
            surf, _, _ = charsprites.compose(self.look, anim, d, int(self.t * 8) % n)
            spr = surf.subsurface((14, 8, 36, 40))
        except Exception:
            spr = visuals.portrait(self.game.art, self.look, "down", int(self.t * 8), self.anim == 1)
        if flip:
            spr = pygame.transform.flip(spr, True, False)
        big = pygame.transform.scale(spr, (spr.get_width() * 10, spr.get_height() * 10))
        screen.blit(big, (box.centerx - big.get_width() // 2, box.bottom - big.get_height() - 70))
        # small turnaround strip
        for k, dd in enumerate(("down", "side", "up")):
            sp = visuals.portrait(self.game.art, self.look, dd, int(self.t * 6), False)
            sm = pygame.transform.scale(sp, (sp.get_width() * 2, sp.get_height() * 2))
            screen.blit(sm, (box.x + 16 + k * 52, box.y + 12))
        ui.text(screen, f"[Q] turn   [V] {('idle', 'walking', 'attacking')[self.anim]}", (box.centerx, box.bottom - 40),
                19, ui.TEXT_DIM, center=True)
        ui.text(screen, "Up/Down choose   Left/Right change   Enter toggle/confirm   R randomize   Esc cancel",
                (r.centerx, r.bottom - 26), 19, ui.TEXT_DIM, center=True)
