"""World map: a hand-drawn parchment map of every location and road. Choose where to go next, or set a goal
anywhere (a town, a job's destination) and the map plots the whole route and tells you the next stop."""
import math
import random

import pygame

from ...core.scene import Scene
from ...world import travel
from ...world.worldmap import TERRAIN_SPEED
from .. import icons
from ..ui import widgets as ui
from .common import is_close

W, H = 1280, 720
MAP_RECT = pygame.Rect(36, 70, 836, 590)
MAP_ORIGIN = (MAP_RECT.x + 30, MAP_RECT.y + 40)
SCALE = 8.4
DANGER_COL = [(150, 150, 150), (110, 170, 90), (200, 180, 60), (220, 130, 50), (200, 60, 50), (150, 50, 170)]
# watercolour washes per biome, on parchment
WASH = {"grassland": (170, 190, 120), "forest": (110, 150, 95), "hills": (180, 170, 120), "mountain": (160, 150, 140),
        "snow": (226, 230, 236), "desert": (226, 200, 140), "coast": (200, 196, 160), "swamp": (130, 150, 110),
        "canyon": (205, 140, 100), "volcanic": (150, 100, 90), "moor": (170, 165, 130), "ruins": (180, 172, 150),
        "cave": (150, 140, 135), "crystal": (170, 185, 215)}
PAPER = (232, 216, 178)
INK = (66, 46, 30)
ROAD = (120, 82, 48)


def to_screen(pos):
    return int(MAP_ORIGIN[0] + pos[0] * SCALE), int(MAP_ORIGIN[1] + pos[1] * SCALE)


_markers = {}
_painted = {}


def town_marker(roof, specialty=None):
    """A tiny pixel-art town (two houses, faction-coloured roofs), 24x24."""
    key = (roof, specialty)
    if key in _markers:
        return _markers[key]
    s = pygame.Surface((12, 12), pygame.SRCALPHA)
    dark = (40, 26, 18)
    wall = (240, 226, 196)
    rd = tuple(int(c * 0.65) for c in roof)
    pygame.draw.rect(s, dark, (6, 3, 6, 6))
    pygame.draw.rect(s, wall, (7, 5, 4, 3))
    pygame.draw.polygon(s, rd, [(6, 5), (9, 2), (11, 5)])
    pygame.draw.rect(s, dark, (0, 5, 8, 7))
    pygame.draw.rect(s, wall, (1, 8, 6, 3))
    pygame.draw.polygon(s, roof, [(0, 8), (4, 4), (7, 8)])
    pygame.draw.line(s, dark, (0, 8), (4, 4))
    pygame.draw.line(s, dark, (4, 4), (7, 8))
    s.set_at((3, 9), (90, 60, 40))
    s.set_at((3, 10), (90, 60, 40))
    s.set_at((5, 9), (250, 214, 120))
    if specialty in ("military", "magic"):
        pygame.draw.line(s, dark, (10, 0), (10, 3))
        s.set_at((11, 0), roof)
    out = pygame.transform.scale(s, (24, 24))
    _markers[key] = out
    return out


# ============================================================================ the painted map
def _glyph(surf, biome, x, y, r):
    """One small hand-drawn terrain mark in ink and watercolour."""
    ink = INK
    if biome in ("forest", "grassland", "swamp", "moor") and (biome == "forest" or r.random() < 0.5):
        if biome == "forest" or r.random() < 0.6:          # tree: round canopy or pine
            if r.random() < 0.5:
                pygame.draw.circle(surf, (96, 136, 80), (x, y - 4), 4)
                pygame.draw.circle(surf, ink, (x, y - 4), 4, 1)
                pygame.draw.line(surf, ink, (x, y), (x, y + 3))
            else:
                pts = [(x, y - 8), (x - 4, y + 1), (x + 4, y + 1)]
                pygame.draw.polygon(surf, (86, 126, 84), pts)
                pygame.draw.polygon(surf, ink, pts, 1)
                pygame.draw.line(surf, ink, (x, y + 1), (x, y + 3))
            return
    if biome in ("mountain", "snow", "volcanic", "cave", "crystal"):
        h = r.randint(9, 15)
        w = h - 2
        pts = [(x - w, y + 3), (x, y - h), (x + w, y + 3)]
        fill = {"snow": (236, 240, 246), "volcanic": (120, 80, 70), "crystal": (176, 196, 230)}.get(biome, (176, 166, 150))
        pygame.draw.polygon(surf, fill, pts)
        pygame.draw.polygon(surf, tuple(int(c * 0.78) for c in fill), [(x, y - h), (x + w, y + 3), (x + 1, y + 3)])
        pygame.draw.lines(surf, ink, False, pts, 1)
        if biome in ("mountain", "cave"):
            pygame.draw.polygon(surf, (246, 246, 250), [(x - 3, y - h + 4), (x, y - h), (x + 3, y - h + 4)])
        if biome == "volcanic":
            pygame.draw.line(surf, (220, 80, 40), (x, y - h + 1), (x + 1, y - h - 3), 2)
        if biome == "cave" and r.random() < 0.4:
            pygame.draw.ellipse(surf, (40, 30, 30), (x - 2, y - 2, 5, 4))
        return
    if biome == "hills" or (biome == "moor" and r.random() < 0.5):
        pygame.draw.arc(surf, ink, (x - 7, y - 5, 14, 12), 0.2, math.pi - 0.2, 1)
        pygame.draw.arc(surf, ink, (x - 2, y - 3, 12, 10), 0.3, math.pi - 0.3, 1)
        return
    if biome == "desert":
        pygame.draw.arc(surf, (170, 130, 80), (x - 8, y - 3, 16, 8), 0.3, math.pi - 0.3, 1)
        return
    if biome == "canyon":
        pygame.draw.lines(surf, (150, 80, 50), False, [(x - 7, y), (x - 3, y - 3), (x + 1, y), (x + 6, y - 4)], 1)
        return
    if biome in ("swamp", "coast"):
        for k in range(3):
            pygame.draw.line(surf, (70, 100, 60) if biome == "swamp" else (90, 110, 140),
                             (x - 4 + k * 3, y + 2), (x - 5 + k * 3, y - 4 + k % 2), 1)
        if biome == "swamp":
            pygame.draw.ellipse(surf, (120, 150, 150), (x - 6, y + 2, 12, 4), 1)
        else:
            pygame.draw.arc(surf, (80, 110, 150), (x - 8, y, 8, 5), 0, math.pi, 1)
            pygame.draw.arc(surf, (80, 110, 150), (x, y, 8, 5), 0, math.pi, 1)
        return
    if biome == "ruins":
        for k in range(2):
            pygame.draw.rect(surf, (200, 194, 180), (x - 4 + k * 5, y - 6 + k * 2, 3, 7 - k * 2))
            pygame.draw.rect(surf, ink, (x - 4 + k * 5, y - 6 + k * 2, 3, 7 - k * 2), 1)
        return
    pygame.draw.line(surf, (120, 140, 80), (x - 2, y), (x - 1, y - 3))
    pygame.draw.line(surf, (120, 140, 80), (x + 1, y), (x + 2, y - 3))


def painted_map(data):
    """The base map (washes, terrain marks, coast, compass, border): drawn once, cached."""
    if "map" in _painted:
        return _painted["map"]
    r = random.Random(7)
    surf = pygame.Surface(MAP_RECT.size)
    surf.fill(PAPER)
    # paper grain and stains
    for _ in range(2600):
        x, y = r.randrange(MAP_RECT.w), r.randrange(MAP_RECT.h)
        c = tuple(max(0, min(255, v + r.randint(-14, 8))) for v in PAPER)
        surf.set_at((x, y), c)
    for _ in range(9):
        st = pygame.Surface((r.randint(80, 200), r.randint(60, 140)), pygame.SRCALPHA)
        pygame.draw.ellipse(st, (150, 110, 60, 18), st.get_rect())
        surf.blit(st, (r.randrange(MAP_RECT.w), r.randrange(MAP_RECT.h)))
    locs = list(data.locations.values())
    pts = [(to_screen(l["pos"])[0] - MAP_RECT.x, to_screen(l["pos"])[1] - MAP_RECT.y, l["biome"]) for l in locs]
    # watercolour regions: nearest location's biome, painted at low resolution then softened
    cell = 6
    gw, gh = MAP_RECT.w // cell + 1, MAP_RECT.h // cell + 1
    wash = pygame.Surface((gw, gh), pygame.SRCALPHA)
    owner = {}
    for gy in range(gh):
        for gx in range(gw):
            px, py = gx * cell, gy * cell
            best, bd = None, 1e9
            for (lx, ly, b) in pts:
                d = (lx - px) ** 2 + (ly - py) ** 2
                if d < bd:
                    best, bd = b, d
            owner[(gx, gy)] = best
            fade = max(0.0, 1.0 - math.sqrt(bd) / 150)
            col = WASH.get(best, (180, 170, 140))
            wash.set_at((gx, gy), (*col, int(40 + 120 * fade)))
    surf.blit(pygame.transform.smoothscale(wash, MAP_RECT.size), (0, 0))
    # the sea along the western and southern edges, with a drawn shoreline
    sea = pygame.Surface(MAP_RECT.size, pygame.SRCALPHA)
    for y in range(MAP_RECT.h):
        edge = 18 + int(8 * math.sin(y / 23.0) + 5 * math.sin(y / 9.0))
        pygame.draw.line(sea, (120, 150, 170, 150), (0, y), (edge, y))
        pygame.draw.line(sea, (80, 100, 120, 200), (edge, y), (edge + 1, y))
    surf.blit(sea, (0, 0))
    for k in range(14):
        y = 30 + k * 40
        pygame.draw.arc(surf, (90, 120, 150), (4, y, 9, 5), 0, math.pi, 1)
    # terrain marks, scattered over each region
    for (lx, ly, b) in pts:
        for _ in range(16):
            ang, rad = r.uniform(0, math.tau), r.uniform(18, 66)
            x, y = int(lx + math.cos(ang) * rad), int(ly + math.sin(ang) * rad * 0.75)
            g = owner.get((x // cell, y // cell))
            if g == b and 8 < x < MAP_RECT.w - 8 and 12 < y < MAP_RECT.h - 8:
                _glyph(surf, b, x, y, r)
    # compass rose
    cx, cy = 92, MAP_RECT.h - 62
    pygame.draw.circle(surf, (226, 208, 166), (cx, cy), 34)
    pygame.draw.circle(surf, INK, (cx, cy), 34, 1)
    pygame.draw.circle(surf, INK, (cx, cy), 27, 1)
    for ang, length, col in ((0, 30, (160, 50, 40)), (math.pi, 30, INK), (math.pi / 2, 24, INK), (-math.pi / 2, 24, INK)):
        tip = (cx + math.sin(ang) * length, cy - math.cos(ang) * length)
        side1 = (cx + math.sin(ang + 1.57) * 5, cy - math.cos(ang + 1.57) * 5)
        side2 = (cx + math.sin(ang - 1.57) * 5, cy - math.cos(ang - 1.57) * 5)
        pygame.draw.polygon(surf, col, [tip, side1, (cx, cy)])
        pygame.draw.polygon(surf, (236, 222, 188), [tip, side2, (cx, cy)])
        pygame.draw.polygon(surf, INK, [tip, side1, (cx, cy), side2], 1)
    f = ui.font(18, True)
    n = f.render("N", True, (160, 50, 40))
    surf.blit(n, (cx - n.get_width() // 2, cy - 54))
    # border
    pygame.draw.rect(surf, INK, surf.get_rect(), 3)
    pygame.draw.rect(surf, INK, surf.get_rect().inflate(-10, -10), 1)
    _painted["map"] = surf
    return surf


def _dashed(surf, col, a, b, width=2, dash=7, gap=5, offset=0.0):
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    if length < 1:
        return
    ux, uy = dx / length, dy / length
    d = -offset % (dash + gap)
    d -= dash + gap
    while d < length:
        s0, s1 = max(0.0, d), min(length, d + dash)
        if s1 > s0:
            pygame.draw.line(surf, col, (a[0] + ux * s0, a[1] + uy * s0), (a[0] + ux * s1, a[1] + uy * s1), width)
        d += dash + gap


def _arrow(surf, col, a, b, size=9):
    ang = math.atan2(b[1] - a[1], b[0] - a[0])
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    pts = [(mx + math.cos(ang) * size, my + math.sin(ang) * size),
           (mx + math.cos(ang + 2.5) * size, my + math.sin(ang + 2.5) * size),
           (mx + math.cos(ang - 2.5) * size, my + math.sin(ang - 2.5) * size)]
    pygame.draw.polygon(surf, col, pts)
    pygame.draw.polygon(surf, (40, 20, 14), pts, 1)


def _flag(surf, x, y, col):
    pygame.draw.line(surf, (50, 34, 22), (x, y), (x, y - 22), 2)
    pygame.draw.polygon(surf, col, [(x + 1, y - 22), (x + 14, y - 17), (x + 1, y - 12)])
    pygame.draw.polygon(surf, (40, 20, 14), [(x + 1, y - 22), (x + 14, y - 17), (x + 1, y - 12)], 1)


# ============================================================================ scene
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
            name = loc["name"] if known else f"{loc['name']} (new)"
            entries.append((name, n, True, f"{r['km']:.0f}km {hrs:.0f}h"))
        self.menu = ui.ListMenu(entries, (900, 160, 340, 200), 22)
        self.menu.icon_for = self._dest_icon
        self.goals = self._goal_list()
        cur = st.settings.get("map_goal")
        self.goal_i = next((i for i, g in enumerate(self.goals) if g[1] == cur), 0)
        if preselect in self.options:
            self.menu.index = self.options.index(preselect)
        else:
            self._follow_goal()

    # ------------------------------------------------------------ goals and routes
    def _goal_list(self):
        """(label, location id) for every place worth heading to: job destinations first, then towns, then wilds."""
        st, data = self.state, self.data
        out = [("No goal", None)]
        for j in st.jobs:
            if j.get("status") == "active":
                for k in ("to", "where", "town"):
                    lid = j.get(k)
                    if lid in data.locations and lid != st.location:
                        out.append((f"Job: {j.get('title', 'job')} -> {data.location(lid)['name']}", lid))
                        break
        for prop in getattr(st, "property", {}):
            if prop != st.location:
                out.append((f"Home: your house in {data.location(prop)['name']}", prop))
        if st.base.get("founded") is not None and st.base.get("location") and st.base["location"] != st.location:
            out.append((f"Base: your outpost at {data.location(st.base['location'])['name']}", st.base["location"]))
        for lid, loc in sorted(data.locations.items(), key=lambda kv: (kv[1]["kind"] != "town", kv[1]["name"])):
            if lid != st.location:
                known = lid in st.discovered or loc["kind"] == "town"
                out.append((loc["name"] + ("" if known else " (unexplored)"), lid))
        return out

    def goal(self):
        return self.goals[self.goal_i][1] if self.goals else None

    def plan(self):
        """(path, km) from here to the goal, or (None, None)."""
        g = self.goal()
        if not g:
            return None, None
        return self.game.world.shortest_path(self.state.location, g)

    def _follow_goal(self):
        path, _ = self.plan()
        if path and len(path) > 1 and path[1] in self.options:
            self.menu.index = self.options.index(path[1])

    def _dest_icon(self, lid):
        path, _ = self.plan()
        if path and len(path) > 1 and path[1] == lid:
            return icons.named(icons.ACTION_CELL, "map")
        loc = self.data.location(lid)
        return icons.named(icons.ACTION_CELL, "house") if loc["kind"] == "town" else None

    def set_goal(self, i):
        self.goal_i = i % len(self.goals)
        self.state.settings["map_goal"] = self.goal()
        self._follow_goal()

    def handle(self, ev):
        if is_close(ev) or (ev.type == pygame.KEYDOWN and ev.key == pygame.K_m):
            self.close()
            return
        if ev.type == pygame.KEYDOWN and ev.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_a, pygame.K_d):
            self.set_goal(self.goal_i + (1 if ev.key in (pygame.K_RIGHT, pygame.K_d) else -1))
            return
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and MAP_RECT.collidepoint(ev.pos):
            best, bd = None, 22
            for lid, loc in self.data.locations.items():
                x, y = to_screen(loc["pos"])
                d = math.hypot(x - ev.pos[0], y - ev.pos[1])
                if d < bd:
                    best, bd = lid, d
            if best:
                i = next((k for k, g in enumerate(self.goals) if g[1] == best and not g[0].startswith(("Job", "Home", "Base"))), None)
                if i is not None:
                    self.set_goal(i)
                if best in self.options:
                    self.menu.index = self.options.index(best)
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

    # ------------------------------------------------------------ drawing
    def draw(self, screen):
        st = self.state
        data = self.data
        world = self.game.world
        ui.dim(screen, 170)
        ui.panel(screen, (20, 20, W - 40, H - 40), "World Map", alpha=245)
        screen.blit(painted_map(data), MAP_RECT.topleft)
        screen.set_clip(MAP_RECT.inflate(-4, -4))
        sel = self.menu.selected() if self.can_travel else None
        path, path_km = self.plan()
        on_path = set()
        if path:
            on_path = {frozenset((path[i], path[i + 1])) for i in range(len(path) - 1)}
        # roads
        for a, b, terrain in data.routes:
            pa, pb = to_screen(data.location(a)["pos"]), to_screen(data.location(b)["pos"])
            if terrain == "road":
                pygame.draw.line(screen, ROAD, pa, pb, 3)
                pygame.draw.line(screen, (196, 160, 110), pa, pb, 1)
            else:
                _dashed(screen, (120, 92, 60), pa, pb, 2, 6, 5)
        # the planned route to the goal (marching dashes) and the chosen next stop
        if path:
            for i in range(len(path) - 1):
                pa, pb = to_screen(data.location(path[i])["pos"]), to_screen(data.location(path[i + 1])["pos"])
                _dashed(screen, (176, 50, 40), pa, pb, 4, 9, 6, self.t * 18)
                _arrow(screen, (196, 60, 46), pa, pb)
        if sel:
            pa, pb = to_screen(data.location(st.location)["pos"]), to_screen(data.location(sel)["pos"])
            if frozenset((st.location, sel)) not in on_path:
                _dashed(screen, (40, 70, 150), pa, pb, 4, 9, 6, self.t * 18)
                _arrow(screen, (60, 90, 180), pa, pb)
        # places
        jobs_at = set()
        for j in st.jobs:
            if j.get("status") == "active":
                for k in ("to", "where", "town"):
                    if j.get(k):
                        jobs_at.add(j[k])
        homes = set(getattr(st, "property", {}))
        if st.base.get("founded") is not None and st.base.get("location"):
            homes.add(st.base["location"])
        for lid, loc in data.locations.items():
            x, y = to_screen(loc["pos"])
            known = lid in st.discovered or loc["kind"] == "town"
            if loc["kind"] == "town":
                fcol = tuple(data.factions[loc["faction"]]["color"]) if loc["faction"] in data.factions else (160, 160, 160)
                screen.blit(town_marker(fcol, loc.get("specialty")), (x - 12, y - 16))
            else:
                pygame.draw.circle(screen, (236, 222, 190), (x, y), 6)
                pygame.draw.circle(screen, DANGER_COL[loc["danger"]] if known else (150, 140, 120), (x, y), 4)
                pygame.draw.circle(screen, INK, (x, y), 6, 1)
            if lid in jobs_at:
                screen.blit(ui.fit_icon(icons.named(icons.ACTION_CELL, "quest"), 24), (x + 8, y - 28))
            if lid in homes:
                screen.blit(ui.fit_icon(icons.named(icons.ACTION_CELL, "house"), 22), (x - 30, y - 26))
            col = INK if known else (130, 110, 86)
            if lid == self.goal():
                col = (150, 40, 30)
            size = 19 if loc["kind"] == "wild" else 21
            tw = ui.font(size, loc["kind"] == "town").size(loc["name"])[0]
            plate = pygame.Surface((tw + 10, size), pygame.SRCALPHA)
            pygame.draw.rect(plate, (242, 230, 200, 205), plate.get_rect(), border_radius=5)
            screen.blit(plate, (x - plate.get_width() // 2, y + 8))
            ui.ink(screen, loc["name"], (x, y + 9), size, col, bold=loc["kind"] == "town", center=True)
        # goal flag and you-are-here pin
        if self.goal():
            gx, gy = to_screen(data.location(self.goal())["pos"])
            _flag(screen, gx + 6, gy - 4, (200, 50, 40))
        if st.mode == "travel" and st.travel:
            tr = st.travel
            pa, pb = data.location(tr["from"])["pos"], data.location(tr["to"])["pos"]
            f = tr["done"] / max(0.01, tr["km"])
            pos = (pa[0] + (pb[0] - pa[0]) * f, pa[1] + (pb[1] - pa[1]) * f)
        else:
            pos = data.location(st.location)["pos"]
        px, py = to_screen(pos)
        bob = abs(math.sin(self.t * 3)) * 4
        pygame.draw.circle(screen, (180, 40, 40), (px, int(py - 14 - bob)), 7)
        pygame.draw.circle(screen, (250, 230, 220), (px, int(py - 14 - bob)), 3)
        pygame.draw.polygon(screen, (180, 40, 40), [(px - 5, int(py - 11 - bob)), (px + 5, int(py - 11 - bob)),
                                                     (px, int(py - bob))])
        pygame.draw.circle(screen, (40, 20, 14), (px, int(py - 14 - bob)), 7, 1)
        screen.set_clip(None)
        # cartouche title
        cart = pygame.Rect(MAP_RECT.x + 16, MAP_RECT.y + 14, 230, 40)
        pygame.draw.rect(screen, (240, 226, 192), cart, border_radius=6)
        pygame.draw.rect(screen, INK, cart, 2, border_radius=6)
        ui.ink(screen, "The Kindred Roads", (cart.centerx, cart.y + 8), 24, INK, bold=True, center=True)
        self.draw_panel(screen, st, data, world, sel, path, path_km)

    def draw_panel(self, screen, st, data, world, sel, path, path_km):
        x = 900
        ui.text(screen, f"You are at: {data.location(st.location)['name']}" if st.mode == "local" else "Travelling",
                (x, 70), 24, ui.ACCENT)
        # goal selector
        gl = self.goals[self.goal_i][0]
        ui.text(screen, "Goal", (x, 100), 20, ui.TEXT_DIM)
        ui.text(screen, f"<  {gl if len(gl) < 30 else gl[:28] + '..'}  >", (x + 52, 100), 20,
                (240, 150, 120) if self.goal() else ui.TEXT)
        if path:
            hrs = 0.0
            for i in range(len(path) - 1):
                r = world.route(path[i], path[i + 1])
                hrs += r["km"] / (travel.BASE_KMH * TERRAIN_SPEED.get(r["terrain"], 1))
            stops = len(path) - 1
            nxt = data.location(path[1])["name"] if len(path) > 1 else "-"
            ui.text(screen, f"{path_km:.0f} km, about {hrs:.0f} h, {stops} stop{'s' if stops != 1 else ''}. Next: {nxt}",
                    (x, 126), 18, (240, 200, 160))
        if self.can_travel:
            ui.text(screen, "Set out for (next stop):", (x, 140 if not path else 146), 20)
            self.menu.rect.y = 172
            self.menu.draw(screen)
            if sel:
                loc = data.location(sel)
                r = world.route(st.location, sel)
                from .. import knowledge
                box = pygame.Rect(890, 384, 356, 226)
                ui.parchment(screen, box)
                ui.ink(screen, loc["name"], (box.x + 10, box.y + 6), 22, ui.INK, bold=True)
                hrs = r["km"] / (travel.BASE_KMH * TERRAIN_SPEED.get(r["terrain"], 1))
                ui.ink(screen, f"{r['km']:.0f} km by {r['terrain']}, ~{hrs:.0f} h", (box.x + 10, box.y + 32), 18, ui.INK_DIM)
                if loc.get("danger"):
                    ui.ink(screen, f"Danger {loc['danger']}/5", (box.right - 10, box.y + 32), 18,
                           ui.INK_RED if loc["danger"] >= 3 else ui.INK_DIM, right=True)
                yy = ui.ink_block(screen, loc["description"], (box.x + 10, box.y + 56, box.w - 20, 60), 18, ui.INK_DIM)
                ui.ink_block(screen, knowledge.place_summary(st, sel), (box.x + 10, yy + 4, box.w - 20, box.bottom - yy - 8),
                             18, ui.INK_GREEN if loc["kind"] == "wild" else ui.INK)
            ui.text(screen, "[Enter] set out  [Left/Right] goal  [click] pick place  [Esc] stay", (W - 40, H - 54), 18,
                    ui.TEXT_DIM, right=True)
        else:
            ui.text_block(screen, "Walk to a road at the edge of the map (or press M outdoors) to choose where to go. "
                          "Pick a goal with Left/Right or by clicking a place: the red route shows the way.",
                          (x, 150, 340, 140), 20, ui.TEXT_DIM)
            ui.text(screen, "[Left/Right] goal   [click] pick place   [Esc] close", (W - 40, H - 54), 18, ui.TEXT_DIM,
                    right=True)
        # legend
        lx, ly = x, 620
        ui.text(screen, "Danger", (lx, ly), 18, ui.TEXT_DIM)
        for i in range(1, 6):
            pygame.draw.circle(screen, DANGER_COL[i], (lx + 70 + i * 26, ly + 8), 6)
        ui.text(screen, "Red: route to goal   Blue: next stop   Scroll: job   House: yours", (lx, ly + 22), 16,
                ui.TEXT_DIM)
