"""Prisoners and retainers: how they feel about you, and what you do with them (Set System: morale.py)."""
import pygame

from ...core.scene import Scene
from ...set_system import morale
from ..ui import widgets as ui
from .common import is_close

W, H = 1280, 720


class PrisonersScene(Scene):
    overlay = True

    def __init__(self, game):
        super().__init__(game)
        self.menu = ui.ListMenu([], (70, 196, 560, 360), 24)
        self.refresh()

    def refresh(self):
        rows = []
        for p in morale.prisoners(self.state):
            cond = morale.CONDITIONS[morale.conditions_of(self.state, p)]["name"]
            rows.append((f"{p['name']}  ({cond})", ("p", p["id"]), True,
                         f"loyalty {p['loyalty']:.0f}  resent {p['resentment']:.0f}"))
        for i, r in enumerate(morale.retainers(self.state)):
            rows.append((f"{r['name']}  (retainer)", ("r", i), True, f"loyalty {r['loyalty']:.0f}"))
        self.menu.set_entries(rows)

    def handle(self, ev):
        if is_close(ev):
            self.close()
            return
        sel = self.menu.selected()
        if ev.type == pygame.KEYDOWN and sel and sel[0] == "p":
            msg = None
            if ev.key == pygame.K_t:
                msg = morale.talk(self.state, sel[1])
            elif ev.key == pygame.K_k:
                p = next(p for p in morale.prisoners(self.state) if p["id"] == sel[1])
                msg = morale.set_treatment(self.state, sel[1], not p["kind"])
            elif ev.key == pygame.K_r:
                msg = morale.recruit_prisoner(self.state, sel[1])
            elif ev.key == pygame.K_x:
                msg = morale.release_prisoner(self.state, sel[1])
            elif ev.key == pygame.K_m:
                msg = morale.move_prisoner(self.state, sel[1])
            if msg:
                self.game.notify(msg)
                self.refresh()
                return
        self.menu.handle(ev)

    def draw(self, screen):
        ui.dim(screen, 150)
        r = ui.panel(screen, (40, 40, W - 80, H - 80), "Prisoners & Retainers")
        if not self.menu.entries:
            ui.text_block(screen, "No prisoners or retainers. Human foes whose morale breaks may surrender: approach "
                          "them (E) to take them prisoner, recruit them, take their purse or let them go. Holding "
                          "prisoners needs a free cell.", (70, 200, 560, 200), 22, ui.TEXT_DIM)
        used, cap = morale.prison_capacity(self.state)
        rused, rcap = morale.retainer_capacity(self.state)
        ui.text(screen, f"Cells {used}/{cap}", (70, 100), 26, ui.TEXT_BAD if cap and used >= cap else ui.ACCENT, bold=True)
        ui.text(screen, f"Retainer beds {rused}/{rcap}", (330, 100), 26, ui.TEXT_BAD if rcap and rused >= rcap else ui.ACCENT,
                bold=True)
        fs = morale.facilities(self.state)
        line = "   ".join(f"{f['name']}: {f['used']}/{f['cap']}" for f in fs) or \
            "No cells: buy a house (1 cramped cell) or build a Stockade at your outpost (4 decent cells)."
        ui.text_block(screen, line, (70, 134, 580, 50), 19, ui.TEXT_DIM)
        self.menu.draw(screen)
        box = ui.parchment(screen, (680, 120, 520, 440))
        lines = [("How it works", True),
                 ("Captives grow loyal over time, faster if you treat them kindly (a ration a day from your pack) and "
                  "talk with them. Without food their resentment builds, and at 75 they escape.", False),
                 (f"At {morale.RECRUIT_LOYALTY} loyalty a captive will serve your outpost as a retainer. Retainers "
                  "bring in a few marks a day and help hold towns you've seized.", False),
                 ("Releasing captives earns goodwill with their faction.", False)]
        sel = self.menu.selected()
        if sel and sel[0] == "p":
            p = next(p for p in morale.prisoners(self.state) if p["id"] == sel[1])
            lines = [(p["name"], True),
                     (f"Captive since day {p['since'] + 1}. Treated {'kindly' if p['kind'] else 'plainly'}. Kept in a "
                      f"{morale.CONDITIONS[morale.conditions_of(self.state, p)]['name']}"
                      f"{' - decent conditions help.' if morale.conditions_of(self.state, p) == 'decent' else ' - cramped conditions breed resentment.'}",
                      False),
                     (f"Loyalty {p['loyalty']:.0f}/100 - ready to serve at {morale.RECRUIT_LOYALTY}.", False),
                     (f"Resentment {p['resentment']:.0f}/100 - escapes at {morale.ESCAPE_RESENTMENT}.", False)] + lines
        y = box.y + 12
        for text, head in lines:
            if head:
                ui.ink(screen, text, (box.x + 14, y), 24, ui.INK_RED, bold=True)
                y += 28
            else:
                y = ui.ink_block(screen, text, (box.x + 14, y, box.w - 28, 120), 20, ui.INK) + 8
        ui.text(screen, "[T] talk   [K] kind / plain   [M] move cell   [R] recruit   [X] release   [Esc] close",
                (r.centerx, r.bottom - 32), 21, ui.TEXT_DIM, center=True)
