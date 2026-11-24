"""Main menu and new-character creation."""
import math
import random

import pygame

from ...core.scene import Scene
from ...world import mapgen as mg
from .. import visuals
from ..art import random_look
from ..ui import widgets as ui
from .common import ControlsScene, SlotScene

W, H = 1280, 720
PRONOUNS = ["they/them", "she/her", "he/him"]


def draw_backdrop(game, screen, t):
    """Scrolling pixel landscape behind menus."""
    canvas = game.canvas
    art = game.art
    off = int(t * 12) % 16
    for ty in range(0, 24):
        for tx in range(-1, 41):
            tid = mg.GROUND if (tx * 7 + ty * 3) % 11 else mg.ALT
            if 15 <= ty <= 16:
                tid = mg.PATH
            canvas.blit(art.tile(tid, "grassland", (tx + ty) % 4), (tx * 16 - off, ty * 16))
    for i in range(14):
        x = (i * 53 - int(t * 12)) % 700 - 30
        y = 40 + (i * 97) % 180 if i % 3 else 290
        canvas.blit(art.obj("tree", i % 4, "grassland"), (x, y))
    # a little party walking the road
    for i, look in enumerate(getattr(game, "_menu_looks", [])):
        frame = int(t * 8 + i) % 4
        canvas.blit(visuals.portrait(art, look, "right", frame, True), (250 + i * 22, 230))
    dark = pygame.Surface(canvas.get_size(), pygame.SRCALPHA)
    dark.fill((10, 8, 20, 120))
    canvas.blit(dark, (0, 0))
    pygame.transform.scale(canvas, screen.get_size(), screen)


class MainMenu(Scene):
    def __init__(self, game):
        super().__init__(game)
        self.t = 0.0
        rng = random.Random(7)
        game._menu_looks = [random_look(game.data.races[r], rng, r) for r in ("human", "murrok", "sylth", "kethari")]
        self.build()

    def build(self):
        entries = []
        recent = self.game.saves.most_recent_slot()
        if recent:
            entries.append(("Continue", ("continue", recent)))
        entries += [("New Game", ("new",)), ("Load Game", ("load",)), ("Options", ("options",)), ("Controls", ("controls",)),
                    ("Quit", ("quit",))]
        self.menu = ui.ListMenu(entries, (W // 2 - 140, 360, 280, 300), 34, row_h=46)

    def on_resume(self):
        self.build()

    def handle(self, ev):
        v = self.menu.handle(ev)
        if not v:
            return
        if v[0] == "continue":
            self.game.load_game(v[1])
        elif v[0] == "new":
            self.game.scenes.push(NewGameScene(self.game))
        elif v[0] == "load":
            self.game.scenes.push(SlotScene(self.game, "load"))
        elif v[0] == "controls":
            self.game.scenes.push(ControlsScene(self.game))
        elif v[0] == "options":
            from .options import OptionsScene
            self.game.scenes.push(OptionsScene(self.game))
        elif v[0] == "quit":
            self.game.running = False

    def update(self, dt):
        self.t += dt
        from .. import audio
        audio.music("menu")

    def draw(self, screen):
        draw_backdrop(self.game, screen, self.t)
        bob = math.sin(self.t * 1.5) * 4
        ui.text(screen, "KINDRED ROADS", (W // 2, 150 + bob), 110, ui.ACCENT, bold=True, center=True)
        ui.text(screen, "A small world that remembers.", (W // 2, 250), 32, ui.TEXT, center=True)
        r = pygame.Rect(W // 2 - 170, 340, 340, 20 + len(self.menu.entries) * 46 + 10)
        ui.panel(screen, r, alpha=200)
        self.menu.rect.height = len(self.menu.entries) * 46
        self.menu.draw(screen)
        ui.text(screen, "v1.0", (W - 16, H - 28), 20, ui.TEXT_DIM, right=True)


class NewGameScene(Scene):
    overlay = False

    def __init__(self, game):
        super().__init__(game)
        self.t = 0.0
        self.name = ""
        self.races = list(game.data.races)
        self.race_i = 0
        self.pron_i = 0
        self.field = 0  # 0 name, 1 race, 2 pronouns, 3 look, 4 start
        self.rng = random.Random()
        self.reroll()

    def reroll(self):
        race = self.races[self.race_i]
        self.look = random_look(self.data.races[race], self.rng, race)

    def handle(self, ev):
        if ev.type != pygame.KEYDOWN:
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 3:
                self.close()
            return
        k = ev.key
        if k == pygame.K_ESCAPE:
            self.close()
            return
        if k in (pygame.K_UP,) or (k == pygame.K_TAB and ev.mod & pygame.KMOD_SHIFT):
            self.field = (self.field - 1) % 5
            return
        if k in (pygame.K_DOWN, pygame.K_TAB):
            self.field = (self.field + 1) % 5
            return
        if self.field == 0:
            if k == pygame.K_BACKSPACE:
                self.name = self.name[:-1]
            elif k == pygame.K_RETURN:
                self.field = 1
            elif ev.unicode and ev.unicode.isprintable() and len(self.name) < 18:
                self.name += ev.unicode
            return
        if k in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d):
            step = -1 if k in (pygame.K_LEFT, pygame.K_a) else 1
            if self.field == 1:
                self.race_i = (self.race_i + step) % len(self.races)
                self.reroll()
            elif self.field == 2:
                self.pron_i = (self.pron_i + step) % len(PRONOUNS)
            elif self.field == 3:
                self.reroll()
        if k in (pygame.K_RETURN, pygame.K_SPACE):
            if self.field == 3:
                from .creator import CharacterCreatorScene
                self.game.scenes.push(CharacterCreatorScene(self.game, self.look, self.races[self.race_i],
                                                            title="Customize Appearance", pronouns=PRONOUNS[self.pron_i]))
            elif self.field == 4:
                self.start()
            else:
                self.field += 1

    def start(self):
        name = self.name.strip() or "Wanderer"
        self.game.new_game(name, self.races[self.race_i], self.look, PRONOUNS[self.pron_i])

    def update(self, dt):
        self.t += dt

    def draw(self, screen):
        draw_backdrop(self.game, screen, self.t)
        r = ui.panel(screen, (140, 70, 1000, 580), "Create Your Character")
        race_id = self.races[self.race_i]
        race = self.data.races[race_id]
        rows = [("Name", (self.name or "") + ("_" if self.field == 0 and int(self.t * 2) % 2 == 0 else "")),
                ("Race", f"<  {race['name']}  >"), ("Pronouns", f"<  {PRONOUNS[self.pron_i]}  >"),
                ("Appearance", "Customize...  (< > randomize)"), ("", "Begin your journey")]
        y = r.y + 70
        for i, (label, val) in enumerate(rows):
            sel = i == self.field
            if sel:
                pygame.draw.rect(screen, ui.PANEL_LIGHT, (r.x + 24, y - 6, 520, 40), border_radius=4)
                pygame.draw.rect(screen, ui.BORDER_HI, (r.x + 24, y - 6, 520, 40), 1, border_radius=4)
            ui.text(screen, label, (r.x + 40, y), 28, ui.TEXT_DIM)
            ui.text(screen, val, (r.x + 200, y), 28, ui.ACCENT if sel else ui.TEXT, bold=(i == 4))
            y += 56
        # race details
        dy = r.y + 370
        ui.text_block(screen, race["background"], (r.x + 40, dy, 500, 60), 22, ui.TEXT_DIM)
        dy += 60
        for s in race["strengths"]:
            ui.text(screen, "+ " + s, (r.x + 40, dy), 22, ui.TEXT_GOOD)
            dy += 22
        for s in race["weaknesses"]:
            ui.text(screen, "- " + s, (r.x + 40, dy), 22, ui.TEXT_BAD)
            dy += 22
        # portrait
        box = pygame.Rect(r.x + 620, r.y + 70, 320, 400)
        pygame.draw.rect(screen, (24, 22, 30), box)
        pygame.draw.rect(screen, ui.BORDER, box, 2)
        dirs = ("down", "left", "up", "right")
        d = dirs[int(self.t / 1.5) % 4]
        spr = visuals.portrait(self.game.art, self.look, d, int(self.t * 8), True)
        big = pygame.transform.scale(spr, (spr.get_width() * 9, spr.get_height() * 9))
        screen.blit(big, (box.centerx - big.get_width() // 2, box.bottom - big.get_height() - 20))
        ui.text(screen, race["appearance"], (box.centerx, box.bottom + 14), 20, ui.TEXT_DIM, center=True)
        ui.text(screen, "Up/Down: field   Left/Right: change   Enter: confirm   Esc: back",
                (r.centerx, r.bottom - 34), 22, ui.TEXT_DIM, center=True)
