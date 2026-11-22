"""Shared overlay scenes: message box, confirm dialog, save/load slot picker, pause menu, controls help."""
import pygame

from ...core.scene import Scene
from ...core.save import NUM_SLOTS
from ..ui import widgets as ui

W, H = 1280, 720

CONTROLS = [
    ("WASD / Arrows", "Move (8 directions)"),
    ("Shift", "Sprint (tires you: more thirst)"),
    ("E / Enter", "Interact, talk, confirm"),
    ("K / Left mouse", "Attack (repeat for combos; hold to draw a bow)"),
    ("L / Right mouse", "Block (hold)"),
    ("F / Space", "Kick / dodge roll"),
    ("Q", "Switch melee / ranged weapon"),
    ("1 - 4", "Cast spell from your spell book"),
    ("I", "Inventory"),
    ("C", "Character & factions"),
    ("M", "World map / leave for travel"),
    ("J", "Journal & world history"),
    ("Esc", "Pause menu / close window"),
    ("F5 / F9", "Quick save / quick load (slot 1)"),
]


def is_close(ev):
    return ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE or (
        ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 3)


class MessageScene(Scene):
    overlay = True

    def __init__(self, game, title, body, on_close=None, width=760):
        super().__init__(game)
        self.title, self.body, self.on_close = title, body, on_close
        lines = ui.wrap(body, 24, width - 40)
        h = min(600, 110 + len(lines) * 21)
        self.rect = pygame.Rect((W - width) // 2, (H - h) // 2, width, h)

    def handle(self, ev):
        if is_close(ev) or (ev.type == pygame.KEYDOWN and ev.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_e)) \
                or (ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1):
            self.close()
            if self.on_close:
                self.on_close()

    def draw(self, screen):
        ui.dim(screen, 110)
        r = ui.panel(screen, self.rect, self.title)
        ui.text_block(screen, self.body, (r.x + 20, r.y + 52, r.w - 40, r.h - 90), 24)
        ui.text(screen, "[Enter] OK", (r.right - 16, r.bottom - 28), 20, ui.TEXT_DIM, right=True)


class ConfirmScene(Scene):
    overlay = True

    def __init__(self, game, title, body, on_yes, on_no=None, yes="Yes", no="No"):
        super().__init__(game)
        self.title, self.body, self.on_yes, self.on_no = title, body, on_yes, on_no
        self.rect = pygame.Rect((W - 640) // 2, (H - 260) // 2, 640, 260)
        self.menu = ui.ListMenu([(yes, True), (no, False)], (self.rect.x + 30, self.rect.bottom - 90, 300, 70), 26)

    def handle(self, ev):
        if is_close(ev):
            self.close()
            if self.on_no:
                self.on_no()
            return
        v = self.menu.handle(ev)
        if v is not None:
            self.close()
            if v:
                self.on_yes()
            elif self.on_no:
                self.on_no()

    def draw(self, screen):
        ui.dim(screen, 110)
        r = ui.panel(screen, self.rect, self.title)
        ui.text_block(screen, self.body, (r.x + 20, r.y + 52, r.w - 40, 90), 24)
        self.menu.draw(screen)


class SlotScene(Scene):
    """Pick a save slot to save into or load from."""
    overlay = True

    def __init__(self, game, mode):
        super().__init__(game)
        self.mode = mode  # "save" | "load"
        self.rect = pygame.Rect((W - 760) // 2, 160, 760, 330)
        self.menu = ui.ListMenu([], (self.rect.x + 30, self.rect.y + 60, 700, 240), 24, row_h=70)
        self.refresh()

    def refresh(self):
        entries = []
        for s in range(1, NUM_SLOTS + 1):
            info = self.game.saves.summary(s)
            if info:
                label = f"Slot {s}:  {info['name']}  -  Lv {info['level']}  -  {info['location']}  -  {info['date']}"
                entries.append((label, s, True, info["saved_at"].replace("T", " ")))
            else:
                entries.append((f"Slot {s}:  (empty)", s, self.mode == "save"))
        self.menu.set_entries(entries)

    def handle(self, ev):
        if is_close(ev):
            self.close()
            return
        slot = self.menu.handle(ev)
        if slot is None:
            return
        if self.mode == "save":
            if self.game.saves.exists(slot):
                self.game.scenes.push(ConfirmScene(self.game, "Overwrite?", f"Overwrite save slot {slot}?",
                                                   lambda: self._save(slot)))
            else:
                self._save(slot)
        else:
            self.game.load_game(slot)

    def _save(self, slot):
        self.game.save_game(slot)
        self.refresh()

    def draw(self, screen):
        ui.dim(screen, 120)
        r = ui.panel(screen, self.rect, "Save Game" if self.mode == "save" else "Load Game")
        self.menu.draw(screen)
        ui.text(screen, "[Enter] choose   [Esc] back", (r.right - 16, r.bottom - 26), 20, ui.TEXT_DIM, right=True)


class ControlsScene(Scene):
    overlay = True

    def handle(self, ev):
        if ev.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
            self.close()

    def draw(self, screen):
        ui.dim(screen, 120)
        r = ui.panel(screen, ((W - 700) // 2, 90, 700, 540), "Controls")
        y = r.y + 56
        for k, d in CONTROLS:
            ui.text(screen, k, (r.x + 30, y), 24, ui.ACCENT)
            ui.text(screen, d, (r.x + 210, y), 24)
            y += 34


class PauseScene(Scene):
    overlay = True

    def __init__(self, game):
        super().__init__(game)
        self.rect = pygame.Rect((W - 420) // 2, 150, 420, 400)
        self.menu = ui.ListMenu([("Resume", "resume"), ("Save game", "save"), ("Load game", "load"),
                                 ("Journal", "journal"), ("Controls", "controls"), ("Quit to main menu", "menu"),
                                 ("Quit game", "quit")], (self.rect.x + 40, self.rect.y + 60, 340, 320), 30)

    def handle(self, ev):
        if is_close(ev):
            self.close()
            return
        v = self.menu.handle(ev)
        if v == "resume":
            self.close()
        elif v in ("save", "load"):
            self.game.scenes.push(SlotScene(self.game, v))
        elif v == "journal":
            from .journal import JournalScene
            self.game.scenes.push(JournalScene(self.game))
        elif v == "controls":
            self.game.scenes.push(ControlsScene(self.game))
        elif v == "menu":
            self.game.scenes.push(ConfirmScene(self.game, "Quit to menu?", "Unsaved progress will be lost.",
                                               self.game.start))
        elif v == "quit":
            self.game.scenes.push(ConfirmScene(self.game, "Quit?", "Unsaved progress will be lost.",
                                               lambda: setattr(self.game, "running", False)))

    def draw(self, screen):
        ui.dim(screen, 120)
        ui.panel(screen, self.rect, "Paused")
        self.menu.draw(screen)
