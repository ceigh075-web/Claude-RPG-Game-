"""World map: shows all 29 locations and routes; choose an adjacent destination to set out."""
import pygame

from ...core.scene import Scene
from ...world import travel
from ...world.worldmap import TERRAIN_SPEED
from ..ui import widgets as ui
from .common import is_close

W, H = 1280, 720
MAP_ORIGIN = (52, 92)
SCALE = 8.0
BIOME_COL = {
    "grassland": (120, 160, 80), "forest": (60, 120, 60), "hills": (140, 150, 90), "mountain": (130, 120, 110),
    "snow": (220, 225, 235), "desert": (220, 195, 130), "coast": (200, 190, 140), "swamp": (80, 110, 80),
    "canyon": (190, 110, 80), "volcanic": (90, 60, 60), "moor": (130, 130, 100), "ruins": (150, 150, 140),
    "cave": (90, 85, 90), "crystal": (130, 170, 200),
}
TERRAIN_COL = {"road": (230, 210, 150), "grassland": (170, 200, 120), "forest": (90, 150, 80), "hills": (180, 170, 110),
               "mountain": (170, 160, 150), "snow": (235, 240, 250), "desert": (230, 200, 140), "coast": (220, 210, 170),
               "swamp": (110, 150, 110), "canyon": (210, 130, 90), "volcanic": (180, 90, 70), "moor": (160, 160, 130),
               "ruins": (190, 190, 180)}
DANGER_COL = [(150, 150, 150), (130, 200, 110), (220, 210, 100), (230, 150, 70), (220, 80, 60), (170, 60, 200)]


def to_screen(pos):
    return int(MAP_ORIGIN[0] + pos[0] * SCALE), int(MAP_ORIGIN[1] + pos[1] * SCALE)


class WorldMapScene(Scene):
    overlay = True

    def __init__(self, game, can_travel=False, preselect=None):
        super().__init__(game)
        self.can_travel = can_travel and self.state.mode == "local"
        self.t = 0.0
        st = self.state
        here = st.location
        self.options = self.game.world.neighbors(here) if self.can_travel else []
        entries = []
        for n in self.options:
            r = self.game.world.route(here, n)
            loc = self.data.location(n)
            hrs = r["km"] / (travel.BASE_KMH * TERRAIN_SPEED.get(r["terrain"], 1))
            known = n in st.discovered or loc["kind"] == "town"
            name = loc["name"] if known else f"{loc['name']} (unexplored)"
            entries.append((name, n, True, f"{r['km']:.0f} km ~{hrs:.0f}h"))
        self.menu = ui.ListMenu(entries, (900, 150, 340, 300), 24)
        if preselect in self.options:
            self.menu.index = self.options.index(preselect)

    def handle(self, ev):
        if is_close(ev) or (ev.type == pygame.KEYDOWN and ev.key == pygame.K_m):
            self.close()
            return
        if not self.can_travel:
            return
        v = self.menu.handle(ev)
        if v:
            ok, msg = travel.start(self.state, self.game.world, v)
            self.game.notify(msg)
            if ok:
                self.game.enter_world()

    def update(self, dt):
        self.t += dt

    def draw(self, screen):
        st = self.state
        data = self.data
        world = self.game.world
        ui.dim(screen, 170)
        ui.panel(screen, (20, 20, W - 40, H - 40), "World Map", alpha=245)
        # parchment
        pr = pygame.Rect(MAP_ORIGIN[0] - 20, MAP_ORIGIN[1] - 30, int(100 * SCALE) + 40, int(62 * SCALE) + 40)
        pygame.draw.rect(screen, (58, 52, 44), pr, border_radius=6)
        for loc in data.locations.values():
            x, y = to_screen(loc["pos"])
            pygame.draw.circle(screen, tuple(int(c * 0.55) for c in BIOME_COL.get(loc["biome"], (100, 100, 100))), (x, y), 34)
        # routes
        sel = self.menu.selected() if self.can_travel else None
        for a, b, terrain in data.routes:
            pa, pb = to_screen(data.location(a)["pos"]), to_screen(data.location(b)["pos"])
            col = TERRAIN_COL.get(terrain, (200, 200, 200))
            width = 2
            if sel and {a, b} == {st.location, sel}:
                col, width = ui.ACCENT, 5
            pygame.draw.line(screen, tuple(int(c * 0.8) for c in col), pa, pb, width)
        # nodes
        for lid, loc in data.locations.items():
            x, y = to_screen(loc["pos"])
            known = lid in st.discovered or loc["kind"] == "town"
            if loc["kind"] == "town":
                fcol = tuple(data.factions[loc["faction"]]["color"]) if loc["faction"] in data.factions else (160, 160, 160)
                pygame.draw.rect(screen, (20, 18, 20), (x - 9, y - 9, 18, 18))
                pygame.draw.rect(screen, fcol, (x - 7, y - 7, 14, 14))
            else:
                pygame.draw.circle(screen, (20, 18, 20), (x, y), 8)
                pygame.draw.circle(screen, DANGER_COL[loc["danger"]] if known else (90, 90, 90), (x, y), 6)
            ui.text(screen, loc["name"], (x, y + 11), 19 if loc["kind"] == "wild" else 22,
                    ui.TEXT if known else ui.TEXT_DIM, center=True, bold=loc["kind"] == "town")
        # player marker
        if st.mode == "travel" and st.travel:
            tr = st.travel
            pa, pb = data.location(tr["from"])["pos"], data.location(tr["to"])["pos"]
            f = tr["done"] / max(0.01, tr["km"])
            pos = (pa[0] + (pb[0] - pa[0]) * f, pa[1] + (pb[1] - pa[1]) * f)
        else:
            pos = data.location(st.location)["pos"]
        px, py = to_screen(pos)
        rad = 13 + int(3 * abs((self.t * 2) % 2 - 1))
        pygame.draw.circle(screen, ui.ACCENT, (px, py), rad, 2)
        # side panel
        ui.text(screen, f"You are at: {data.location(st.location)['name']}" if st.mode == "local"
                else "Travelling", (900, 76), 24, ui.ACCENT)
        if self.can_travel:
            ui.text(screen, "Set out for:", (900, 116), 24)
            self.menu.draw(screen)
            if sel:
                loc = data.location(sel)
                r = world.route(st.location, sel)
                y = 470
                ui.text(screen, f"Terrain: {r['terrain']}   Danger: {loc.get('danger', 0) or 'town'}", (900, y), 22)
                y = ui.text_block(screen, loc["description"], (900, y + 26, 340, 110), 21, ui.TEXT_DIM)
                if loc["kind"] == "wild":
                    ui.text_block(screen, "Why go: " + loc["reason"], (900, y + 6, 340, 70), 21, ui.TEXT_GOOD)
            ui.text(screen, "[Enter] set out   [Esc] stay", (W - 40, H - 54), 20, ui.TEXT_DIM, right=True)
        else:
            ui.text_block(screen, "Walk to a road at the edge of the map (or press M outdoors) to choose a destination.",
                          (900, 116, 340, 120), 22, ui.TEXT_DIM)
            ui.text(screen, "[Esc] close", (W - 40, H - 54), 20, ui.TEXT_DIM, right=True)
        # legend
        lx, ly = 60, H - 70
        ui.text(screen, "Danger:", (lx, ly), 20, ui.TEXT_DIM)
        for i in range(1, 6):
            pygame.draw.circle(screen, DANGER_COL[i], (lx + 80 + i * 34, ly + 8), 6)
            ui.text(screen, str(i), (lx + 90 + i * 34, ly), 18, ui.TEXT_DIM)
        ui.text(screen, "Squares are towns (faction colour)", (lx + 300, ly), 20, ui.TEXT_DIM)
