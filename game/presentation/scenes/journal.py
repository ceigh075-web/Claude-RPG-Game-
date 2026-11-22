"""Journal: recent log, Set AI world history, and discovered places."""
import pygame

from ...core.clock import format_stamp
from ...core.scene import Scene
from ..ui import widgets as ui
from .common import is_close

W, H = 1280, 720
TABS = ["Log", "News", "History", "Places", "Jobs"]


class JournalScene(Scene):
    overlay = True

    def __init__(self, game):
        super().__init__(game)
        self.tab = 0
        self.scroll = 0

    def handle(self, ev):
        if is_close(ev) or (ev.type == pygame.KEYDOWN and ev.key == pygame.K_j):
            self.close()
        elif ev.type == pygame.KEYDOWN:
            if ev.key in (pygame.K_TAB, pygame.K_RIGHT, pygame.K_d):
                self.tab, self.scroll = (self.tab + 1) % len(TABS), 0
            elif ev.key in (pygame.K_LEFT, pygame.K_a):
                self.tab, self.scroll = (self.tab - 1) % len(TABS), 0
            elif ev.key in (pygame.K_UP, pygame.K_w):
                self.scroll = max(0, self.scroll - 1)
            elif ev.key in (pygame.K_DOWN, pygame.K_s):
                self.scroll += 1
        elif ev.type == pygame.MOUSEWHEEL:
            self.scroll = max(0, self.scroll - ev.y)

    def lines(self):
        st = self.state
        if self.tab == 0:
            return [f"[{e['t']}] {e['text']}" for e in reversed(st.log)]
        if self.tab == 1:
            from ...set_system import world_events
            w = world_events.world(st)
            out = [f"Hollow strength: {w['hollow_strength']:.0f}/100" + ("  (broken)" if st.flags.get("hollow_broken") else ""),
                   f"Titles: {', '.join(w['titles']) or 'none'}", ""]
            for ev in reversed(w["active_events"]):
                out.append(f"NOW: {ev['headline']} (until {format_stamp(ev['until'])})")
            out.append("")
            for rec in st.memory.world_history(40, 3):
                out.append(f"{format_stamp(rec['day'], rec['minute'])}  {rec['description']}")
            return out
        if self.tab == 4:
            from ...set_system import favors, jobs
            out = ["ACTIVE JOBS"]
            for j in st.jobs:
                if j["status"] == "active":
                    done, detail = jobs.progress(st, j)
                    out.append(f"- {j['title']} [{self.data.location(j['town'])['name']}] {detail}; due {format_stamp(j['deadline'])}"
                               + ("  READY" if done else ""))
            out += ["", "FAVORS"]
            for fid, f in st.favors.items():
                d = favors.defs(self.data)[fid]
                done, detail = favors.progress(st, fid) if f["status"] == "active" else (True, "done")
                out.append(f"- {d['title']} for {self.data.npcs[f['npc']]['name']}: {f['status']} - {detail}")
            return out
        if self.tab == 2:
            out = []
            for rec in st.memory.recent(200):
                stars = "*" * rec["importance"]
                out.append(f"{format_stamp(rec['day'], rec['minute'])}  {stars:<5} {rec['description']}")
            return out or ["Nothing of note has happened yet."]
        out = []
        for lid in sorted(st.discovered, key=lambda i: self.data.location(i)["name"]):
            loc = self.data.location(lid)
            kind = "Town" if loc["kind"] == "town" else f"Wilds (danger {loc['danger']})"
            out.append(f"{loc['name']} - {kind}: {loc['description']}")
        return out

    def draw(self, screen):
        ui.dim(screen, 150)
        r = ui.panel(screen, (40, 40, W - 80, H - 80), "Journal")
        x = r.x + 200
        for i, t in enumerate(TABS):
            ui.text(screen, t, (x, r.y + 10), 28, ui.ACCENT if i == self.tab else ui.TEXT_DIM, bold=i == self.tab)
            x += 140
        wrapped = []
        for l in self.lines():
            wrapped += ui.wrap(l, 22, r.w - 60)
        self.scroll = min(self.scroll, max(0, len(wrapped) - 24))
        y = r.y + 52
        for l in wrapped[self.scroll:self.scroll + 26]:
            ui.text(screen, l, (r.x + 30, y), 22)
            y += 21
        ui.text(screen, "[Tab] switch tab   [Up/Down] scroll   [Esc] close", (r.centerx, r.bottom - 28), 20,
                ui.TEXT_DIM, center=True)
