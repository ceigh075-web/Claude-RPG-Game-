"""Town job board: local warnings, news, open jobs to accept, and active jobs to turn in."""
import pygame

from ...core.clock import format_stamp
from ...core.scene import Scene
from ...set_system import jobs, world_events
from ..ui import widgets as ui
from .common import is_close

W, H = 1280, 720


class JobBoardScene(Scene):
    overlay = True

    def __init__(self, game, town):
        super().__init__(game)
        self.town = town
        self.focus = 0
        self.open_menu = ui.ListMenu([], (70, 250, 540, 330), 23)
        self.active_menu = ui.ListMenu([], (690, 250, 520, 330), 23)
        self.refresh()

    def refresh(self):
        st = self.state
        b = jobs.board(st, self.town)
        self.open_menu.set_entries([(j["title"], j["id"], True, f"{j['reward']}m") for j in b["jobs"] if j["status"] == "open"])
        self.active_menu.set_entries([(j["title"], j["id"], True, "ready" if jobs.progress(st, j)[0] else "")
                                      for j in st.jobs if j["status"] == "active"])

    def selected_job(self):
        st = self.state
        if self.focus == 0:
            jid = self.open_menu.selected()
            return next((j for j in jobs.board(st, self.town)["jobs"] if j["id"] == jid), None)
        jid = self.active_menu.selected()
        return next((j for j in st.jobs if j["id"] == jid), None)

    def handle(self, ev):
        if is_close(ev):
            self.close()
            return
        if ev.type == pygame.KEYDOWN and ev.key in (pygame.K_TAB, pygame.K_LEFT, pygame.K_RIGHT):
            self.focus = 1 - self.focus
            return
        menu = self.open_menu if self.focus == 0 else self.active_menu
        v = menu.handle(ev)
        if v is None:
            return
        if self.focus == 0:
            ok, msg = jobs.accept(self.state, self.town, v)
        else:
            ok, msg = jobs.turn_in(self.state, v)
        self.game.notify(msg)
        self.refresh()

    def draw(self, screen):
        st = self.state
        ui.dim(screen, 150)
        r = ui.panel(screen, (40, 40, W - 80, H - 80), f"Job Board - {self.data.location(self.town)['name']}")
        y = 92
        lines = []
        for n in self.game.world.neighbors(self.town):
            loc = self.data.location(n)
            if loc["kind"] == "wild":
                foes = sorted({self.data.enemies[e]["name"] for e in loc["enemies"]})
                lines.append(f"Warning - {loc['name']} (danger {loc['danger']}): {', '.join(foes)}.")
        for e in world_events.world(st)["active_events"][-3:]:
            lines.append("News - " + e["headline"])
        for l in lines[:6]:
            ui.text(screen, l, (70, y), 20, ui.TEXT_DIM if l.startswith("Warning") else ui.ACCENT)
            y += 21
        for i, (label, x) in enumerate((("Posted jobs", 70), ("Your jobs", 690))):
            ui.text(screen, label, (x, 218), 26, ui.ACCENT if self.focus == i else ui.TEXT_DIM, bold=True)
        self.open_menu.draw(screen)
        self.active_menu.draw(screen)
        j = self.selected_job()
        if j:
            done, detail = jobs.progress(st, j) if j["status"] == "active" else (False, "")
            ui.text_block(screen, j["desc"], (70, 594, 1000, 44), 22)
            due = f"due {format_stamp(j['deadline'])}" if j.get("deadline") is not None and j["status"] == "active" \
                else f"{j.get('deadline_days', j.get('days', 7))} days to complete"
            ui.text(screen, f"Reward {j['reward']} marks  -  {due}" + (f"  -  {detail}" if detail else ""), (70, 640), 21,
                    ui.TEXT_GOOD if done else ui.TEXT)
        ui.text(screen, "[Enter] accept / turn in   [Tab] switch   [Esc] close", (r.right - 30, r.bottom - 30), 20,
                ui.TEXT_DIM, right=True)
