"""The loot panel: what a body or container holds, sorted by kind, taken one at a time or all at once.
Rules live in set_system/loot.py; this screen only shows the list and forwards the player's choices."""
import pygame

from ...core.scene import Scene
from ...set_system import loot
from .. import audio, icons
from ..ui import widgets as ui
from .common import is_close

W, H = 1280, 720
ROW = 34


class LootScene(Scene):
    overlay = True

    def __init__(self, game, title, entries, on_close=None, subtitle=None, owned=True):
        super().__init__(game)
        self.title, self.entries, self.on_close, self.subtitle = title, entries, on_close, subtitle
        self.owned = owned          # False: taking from someone else (shown as a warning)
        self.index = 0
        self.taken_value = 0
        self.taken = []

    # ------------------------------------------------------------ actions
    def _done(self, msgs, value):
        msgs = [m for m in msgs if m]
        if not msgs:
            return
        self.taken_value += value
        self.taken += msgs
        audio.play("coin" if any("marks" in m for m in msgs) else "pickup")
        self.game.toast(", ".join(msgs[:4]) + (f" and {len(msgs) - 4} more" if len(msgs) > 4 else ""))
        self.index = max(0, min(self.index, len(self.entries) - 1))

    def take_one(self):
        m, v = loot.take(self.state, self.entries, self.index)
        self._done([m], v)

    def take_all(self, only=None):
        msgs, v = loot.take_all(self.state, self.entries, only)
        self._done(msgs, v)

    def close(self):
        super().close()
        if self.on_close:
            self.on_close(self.taken_value, self.taken)

    def handle(self, ev):
        if is_close(ev):
            self.close()
            return
        if ev.type != pygame.KEYDOWN:
            return
        k = ev.key
        n = len(self.entries)
        if k in (pygame.K_UP, pygame.K_w) and n:
            self.index = (self.index - 1) % n
        elif k in (pygame.K_DOWN, pygame.K_s) and n:
            self.index = (self.index + 1) % n
        elif k in (pygame.K_RETURN, pygame.K_e) and n:
            self.take_one()
            if not self.entries:
                self.close()
        elif k in (pygame.K_a, pygame.K_SPACE, pygame.K_r) and n:
            self.take_all()
            self.close()
        elif k == pygame.K_m and n:
            self.take_all("money")
            if not self.entries:
                self.close()

    # ------------------------------------------------------------ drawing
    def draw(self, screen):
        ui.dim(screen, 90)
        n = max(1, len(self.entries))
        h = min(520, 150 + ROW * n + (26 if self.subtitle else 0))
        r = ui.panel(screen, ((W - 640) // 2, (H - h) // 2, 640, h), self.title)
        y = r.y + 50
        if self.subtitle:
            ui.text(screen, self.subtitle, (r.x + 24, y), 19, ui.TEXT_BAD if not self.owned else ui.TEXT_DIM)
            y += 26
        if not self.entries:
            ui.text(screen, "Empty.", (r.centerx, y + 20), 24, ui.TEXT_DIM, center=True)
        visible = (r.bottom - 60 - y) // ROW
        top = max(0, min(self.index - visible + 1, len(self.entries) - visible))
        last_cat = None
        for i, e in enumerate(self.entries[top:top + visible], start=top):
            cat = loot.category(self.data, e["item"])
            sel = i == self.index
            row = pygame.Rect(r.x + 18, y, r.w - 36, ROW - 4)
            if sel:
                pygame.draw.rect(screen, ui.PANEL_LIGHT, row, border_radius=4)
                pygame.draw.rect(screen, ui.BORDER_HI, row, 1, border_radius=4)
            screen.blit(ui.fit_icon(icons.ui_icon(self.data, e["item"]), ROW - 6), (row.x + 6, row.y + 1))
            ui.text(screen, loot.label(self.data, e), (row.x + 44, row.y + 4), 22, ui.ACCENT if sel else ui.TEXT)
            tag = loot.CATEGORY_NAME[cat]
            if cat != last_cat or sel:
                ui.text(screen, tag, (row.right - 120, row.y + 6), 18, loot.CATEGORY_COLOR[cat], right=True)
            last_cat = cat
            if e["item"] != "marks":
                ui.text(screen, f"{loot.value(self.data, e)} mk", (row.right - 10, row.y + 6), 18, ui.TEXT_DIM, right=True)
            y += ROW
        ui.text(screen, "[Enter/E] take   [A/Space] take all   [M] money only   [Esc] leave the rest",
                (r.centerx, r.bottom - 28), 19, ui.TEXT_DIM, center=True)

