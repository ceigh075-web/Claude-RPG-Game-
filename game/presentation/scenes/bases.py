"""Bases of operations: your houses and outpost, what each holds, your home base, and the carter between them."""
import pygame

from ...core.scene import Scene
from ...set_system import bases, morale
from .. import icons
from ..ui import widgets as ui
from .common import ConfirmScene, is_close

W, H = 1280, 720


class BasesScene(Scene):
    overlay = True

    def __init__(self, game):
        super().__init__(game)
        self.menu = ui.ListMenu([], (70, 130, 520, 400), 24, row_h=34)
        self.menu.icon_for = lambda v: icons.named(icons.ACTION_CELL, "house" if v.startswith("house") else "camp")
        self.refresh()

    def refresh(self):
        rows = []
        for b in bases.list_bases(self.state):
            here = b["location"] == self.state.location
            rows.append((b["name"], b["id"], True, ("HOME " if b["home"] else "") + ("(here)" if here else "")))
        self.menu.set_entries(rows)

    def selected(self):
        v = self.menu.selected()
        return next((b for b in bases.list_bases(self.state) if b["id"] == v), None)

    def handle(self, ev):
        if is_close(ev):
            self.close()
            return
        b = self.selected()
        if ev.type == pygame.KEYDOWN and b:
            if ev.key == pygame.K_h:
                ok, msg = bases.set_home(self.state, b["id"])
                self.game.notify(msg)
                self.refresh()
                return
            if ev.key == pygame.K_g:
                self.state.settings["map_goal"] = b["location"]
                self.game.notify(f"Map goal set: {self.data.location(b['location'])['name']}. Open the map (M) for the route.")
                return
            if ev.key == pygame.K_c:
                ok, km, hours, marks, why = bases.carter_quote(self.state, self.game.world, b["id"])
                if not ok:
                    self.game.notify(why)
                    return

                def ride():
                    done, msg = bases.ride_carter(self.state, self.game.world, b["id"])
                    self.game.notify(msg)
                    if done:
                        self.close()
                        self.game.enter_world()
                self.game.scenes.push(ConfirmScene(self.game, "Hire the carter?",
                                                   f"Ride {km:.0f} km to your {b['name'].lower()}: about {hours:.0f} hours "
                                                   f"on a safe wagon road, {marks} marks.", ride))
                return
        self.menu.handle(ev)

    def draw(self, screen):
        st = self.state
        ui.dim(screen, 150)
        r = ui.panel(screen, (40, 40, W - 80, H - 80), "Bases of Operations")
        used, cap = morale.prison_capacity(st)
        rused, rcap = morale.retainer_capacity(st)
        ui.text(screen, f"Cells {used}/{cap}    Retainer beds {rused}/{rcap}", (70, 96), 22, ui.ACCENT)
        if not self.menu.entries:
            ui.text_block(screen, "You have no bases yet. Buy a house in a town (look for 'House for sale') or found an "
                          "outpost at Widow's Crossing.", (70, 140, 520, 120), 22, ui.TEXT_DIM)
        self.menu.draw(screen)
        b = self.selected()
        box = ui.parchment(screen, (640, 110, 560, 470))
        y = box.y + 14
        if b:
            ui.ink(screen, b["name"], (box.x + 16, y), 26, ui.INK_RED, bold=True)
            y += 34
            lines = [f"Where: {self.data.location(b['location'])['name']}" + ("  (you are here)" if b["location"] == st.location else ""),
                     f"Beds: {b['beds']}    Prisoner cells: {b['cells']}",
                     f"Stored goods: {b['storage']} item{'s' if b['storage'] != 1 else ''}",
                     "Facilities: " + ", ".join(b["stations"]),
                     "Your home base: companions told to wait go here, and it's where the map's Home goal points."
                     if b["home"] else "Press H to make this your home base."]
            for line in lines:
                y = ui.ink_block(screen, line, (box.x + 16, y, box.w - 32, 90), 20, ui.INK) + 8
            ok, km, hours, marks, why = bases.carter_quote(st, self.game.world, b["id"])
            y += 6
            ui.ink(screen, "Carter", (box.x + 16, y), 22, ui.INK_RED, bold=True)
            y += 28
            ui.ink_block(screen, f"{km:.0f} km, about {hours:.0f} h, {marks} marks. Safe: no road events." if ok else why,
                         (box.x + 16, y, box.w - 32, 60), 20, ui.INK_GREEN if ok else ui.INK_DIM)
        ui.text(screen, "[H] home base   [G] route on the map   [C] ride the carter   [Esc] close",
                (r.centerx, r.bottom - 32), 21, ui.TEXT_DIM, center=True)
