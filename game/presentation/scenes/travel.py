"""Text-based travel screen (Oregon-Trail style) with a scrolling scenery strip."""
import math

import pygame

from ...core.rng import stable_rng
from ...core.scene import Scene
from ...set_system import needs, timeflow
from ...world import effects, travel, weather
from ...world import mapgen as mg
from ..ui import widgets as ui
from .common import PauseScene
from .. import env, visuals


_dim_cache = {}


def _dim(img, f):
    """A darker, slightly hazier copy for distant scenery (cached)."""
    key = (id(img), f)
    out = _dim_cache.get(key)
    if out is None:
        out = img.copy()
        out.fill((int(255 * f), int(255 * f), int(255 * f), 255), special_flags=pygame.BLEND_RGBA_MULT)
        out = pygame.transform.scale(out, (max(1, out.get_width() * 2 // 3), max(1, out.get_height() * 2 // 3)))
        if len(_dim_cache) > 300:
            _dim_cache.clear()
        _dim_cache[key] = out
    return out

W, H = 1280, 720
STRIP = (640, 150)
AUTO_STEP = 0.45
SKY_DAY = (120, 170, 220)
SKY_NIGHT = (16, 20, 44)
TERRAIN_BIOME = {"road": "grassland"}
SCENERY = {"forest": "tree", "grassland": "tree", "road": "tree", "hills": "rock", "mountain": "pine", "snow": "pine",
           "desert": "cactus", "coast": "rock", "swamp": "dead_tree", "canyon": "cactus", "volcanic": "rock",
           "moor": "dead_tree", "ruins": "landmark"}


def lerp(a, b, f):
    return tuple(int(a[i] + (b[i] - a[i]) * f) for i in range(3))


class TravelScene(Scene):
    def __init__(self, game):
        super().__init__(game)
        self.t = 0.0
        self.auto = False
        self.auto_t = 0.0
        self.scroll = 0.0
        self.strip = pygame.Surface(STRIP)
        self.event_menu = None
        self.menu = ui.ListMenu([], (900, 500, 340, 207), 22, row_h=23)
        self.build_menu()
        self.check_event()

    @property
    def tr(self):
        return self.state.travel

    # ------------------------------------------------------------ menus
    def build_menu(self):
        st = self.state
        tr = self.tr
        if tr is None:
            return
        if tr["arrived"]:
            entries = [(f"Enter {self.data.location(tr['to'])['name']}", "enter")]
        else:
            entries = [("Stop travelling" if self.auto else "Continue travelling", "auto"),
                       ("Travel 1 hour", "step"), ("Rest 1 hour", "rest1"), ("Make camp until morning", "camp")]
        entries += [(f"Pace: {st.settings['pace']}", "pace"), (f"Rations: {st.settings['rations']}", "rations"),
                    ("Supplies / use item", "inv")]
        if not tr["arrived"]:
            entries.append(("Turn back", "back"))
        entries.append(("World map", "map"))
        self.menu.set_entries(entries)

    def check_event(self):
        tr = self.tr
        if tr and tr.get("pending_combat"):
            pc = tr["pending_combat"]
            e = self.data.enemies[pc["enemy"]]
            self.event = {"text": f"{pc['count']} {e['name']}{'s' if pc['count'] > 1 else ''} block your way. "
                                  f"Fight them yourself, or let the fight play out?"}
            self.event_menu = ui.ListMenu([("Fight it out (real-time)", "fight"), ("Let it play out (auto-resolve)", "auto")],
                                          (260, 330, 760, 200), 26, row_h=34)
            self.combat_choice = True
            self.auto = False
            self.build_menu()
            return
        self.combat_choice = False
        if tr and tr["pending_event"]:
            ev = travel.event_by_id(self.state, tr["pending_event"])
            entries = [(c["label"], i, effects.requirement_met(self.state, c.get("requires")))
                       for i, c in enumerate(ev["choices"])]
            self.event = ev
            self.event_menu = ui.ListMenu(entries, (260, 330, 760, 200), 26, row_h=34)
            self.auto = False
            self.build_menu()
        else:
            self.event_menu = None

    # ------------------------------------------------------------ input
    def handle(self, ev):
        if self.event_menu:
            v = self.event_menu.handle(ev)
            if v is not None and getattr(self, "combat_choice", False):
                if v == "fight":
                    from .arena import ArenaScene
                    self.game.scenes.replace(ArenaScene(self.game))
                else:
                    res = travel.auto_resolve_combat(self.state)
                    self.game.notify(res["messages"][-1:])
                    self.check_event()
                    self.after_step()
                return
            if v is not None:
                msgs = travel.choose(self.state, v)
                self.game.notify(msgs[-1:] if msgs else [])
                self.check_event()
                self.after_step()
            return
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_ESCAPE:
                self.auto = False
                self.build_menu()
                self.game.scenes.push(PauseScene(self.game))
                return
            if ev.key == pygame.K_i:
                self.action("inv")
                return
            if ev.key == pygame.K_c:
                from .character import CharacterScene
                self.game.scenes.push(CharacterScene(self.game))
                return
            if ev.key == pygame.K_j:
                from .journal import JournalScene
                self.game.scenes.push(JournalScene(self.game))
                return
            if ev.key == pygame.K_m:
                self.action("map")
                return
            if ev.key == pygame.K_F5:
                self.game.save_game(1)
                return
        v = self.menu.handle(ev)
        if v:
            self.action(v)

    def action(self, v):
        st = self.state
        if v == "enter":
            first = travel.arrive(st)
            if first:
                self.game.toast(f"Discovered {self.data.location(st.location)['name']}!")
            self.game.enter_world()
            self.game.autosave()
            return
        if v == "auto":
            self.auto = not self.auto
            self.auto_t = AUTO_STEP
        elif v == "step":
            self.do_step()
        elif v == "rest1":
            travel.rest(st, 1)
        elif v == "camp":
            hours = (7 - st.clock.hour_float) % 24
            hours = max(1, round(hours))
            exposed = not st.player.inventory.has("bedroll")
            travel.rest(st, hours)
            if exposed:
                st.player.damage(3)
                st.player.hp = max(st.player.hp, 1)
                travel.log(st, "Sleeping without a bedroll leaves you stiff and cold (-3 health).")
        elif v == "pace":
            keys = list(travel.PACES)
            st.settings["pace"] = keys[(keys.index(st.settings["pace"]) + 1) % len(keys)]
            travel.log(st, f"Pace set to {st.settings['pace']}: {travel.PACES[st.settings['pace']][3]}")
        elif v == "rations":
            keys = list(travel.RATIONS)
            st.settings["rations"] = keys[(keys.index(st.settings["rations"]) + 1) % len(keys)]
            travel.log(st, f"Rations set to {st.settings['rations']}.")
        elif v == "inv":
            from .inventory import InventoryScene
            self.auto = False
            self.game.scenes.push(InventoryScene(self.game))
        elif v == "back":
            travel.turn_back(st)
        elif v == "map":
            from .worldmap import WorldMapScene
            self.auto = False
            self.game.scenes.push(WorldMapScene(self.game))
        self.build_menu()

    def do_step(self):
        travel.step(self.state)
        self.check_event()
        self.after_step()

    def after_step(self):
        st = self.state
        p = st.player
        if self.tr and self.tr["arrived"]:
            self.auto = False
        if p.hp < p.max_hp * 0.25 and self.auto:
            self.auto = False
            travel.log(st, "You are badly hurt. You stop to consider your options.")
        conds = needs.status(p)
        if self.auto and ("starving" in conds or "dehydrated" in conds):
            self.auto = False
            travel.log(st, "You are out of supplies and suffering. You stop.")
        if p.hp <= 0 or not p.alive:
            self.collapse()
        self.build_menu()

    def collapse(self):
        st = self.state
        p = st.player
        p.alive = True
        p.hp = max(5.0, p.max_hp * 0.1)
        p.food, p.water = max(p.food, 25.0), max(p.water, 25.0)
        timeflow.advance(st, 8 * 60, resting=True)
        travel.log(st, "You collapse by the road. A passing shepherd shares water and food. You wake hours later, weak but alive.")
        st.memory.record("player", "significant", f"{p.name} collapsed on the road and was saved by a stranger.",
                         day=st.clock.day_index, minute=st.clock.total_minutes % 1440, importance=2)

    def update(self, dt):
        self.t += dt
        from .. import audio
        audio.music("travel")
        if self.auto and not self.event_menu and self.tr and not self.tr["arrived"]:
            self.scroll += dt * 40
            self.auto_t += dt
            if self.auto_t >= AUTO_STEP:
                self.auto_t = 0.0
                self.do_step()

    # ------------------------------------------------------------ drawing
    def draw_strip(self):
        """The road ahead: sky by time of day, three parallax layers by terrain, the party walking, weather."""
        st = self.state
        tr = self.tr
        s = self.strip
        art = self.game.art
        light = st.clock.daylight()
        hour = st.clock.hour_float
        biome = TERRAIN_BIOME.get(tr["terrain"], tr["terrain"])
        wid = weather.weather_for(st, tr["terrain"])
        moving = self.auto and not self.event_menu and not tr["arrived"]
        # sky: vertical gradient, warmer at dawn and dusk
        top = lerp(SKY_NIGHT, (90, 150, 220), max(0.0, (light - 0.3) / 0.7))
        bottom = lerp((40, 36, 70), (200, 222, 240), max(0.0, (light - 0.3) / 0.7))
        if 5 <= hour < 8 or 17 <= hour < 20:
            bottom = lerp(bottom, (250, 170, 110), 0.55)
        if wid in ("rain", "storm", "fog", "overcast", "snow"):
            top, bottom = lerp(top, (100, 104, 116), 0.55 * light), lerp(bottom, (150, 150, 160), 0.55 * light)
        for y in range(STRIP[1]):
            pygame.draw.line(s, lerp(top, bottom, y / STRIP[1]), (0, y), (STRIP[0], y))
        # stars, sun / moon on an arc across the day
        if light < 0.5:
            r = stable_rng("stars")
            for _ in range(70):
                x, y = r.randrange(STRIP[0]), r.randrange(80)
                tw = 150 + int(80 * abs(((self.t * 0.7 + x * 0.13) % 2) - 1))
                s.set_at((x, y), (tw, tw, min(255, tw + 30)))
        day_f = ((hour - 6) % 24) / 12.0
        body_col, rad = ((255, 236, 160), 10) if 6 <= hour < 18 else ((230, 230, 245), 8)
        if not 6 <= hour < 18:
            day_f = ((hour - 18) % 24) / 12.0
        bx = int(40 + day_f * (STRIP[0] - 80))
        by = int(70 - 55 * (1 - (2 * day_f - 1) ** 2))
        if wid not in ("storm", "overcast", "fog"):
            glow = pygame.Surface((rad * 6, rad * 6), pygame.SRCALPHA)
            pygame.draw.circle(glow, (*body_col, 50), (rad * 3, rad * 3), rad * 3)
            s.blit(glow, (bx - rad * 3, by - rad * 3))
            pygame.draw.circle(s, body_col, (bx, by), rad)
        # clouds
        r = stable_rng("clouds", tr["from"], tr["to"])
        cl = lerp((60, 60, 80), (250, 250, 255), light)
        for i in range(6):
            cx = (r.randint(0, 900) - int(self.scroll * 0.08 + self.t * 4)) % 900 - 120
            cy = r.randint(10, 60)
            for k in range(4):
                pygame.draw.ellipse(s, cl, (cx + k * 14, cy - (k % 2) * 5, 34, 14))
        # far range: jagged silhouettes in the terrain's colour
        ground = art.tile(mg.GROUND, biome).get_at((0, 0))[:3]
        far = lerp(ground, bottom, 0.55)
        mid = lerp(ground, bottom, 0.3)
        peaks = {"mountain": 46, "snow": 50, "volcanic": 44, "canyon": 36, "hills": 26, "desert": 16, "coast": 12,
                 "swamp": 14, "moor": 20, "ruins": 22, "forest": 24}.get(biome, 20)
        off = self.scroll * 0.15
        pts = [(0, STRIP[1])]
        for x in range(-20, STRIP[0] + 40, 20):
            n = math.sin((x + off) * 0.021) * 0.6 + math.sin((x + off) * 0.053 + 1.3) * 0.4
            pts.append((x, 92 - peaks * (0.55 + 0.45 * n)))
        pts.append((STRIP[0], STRIP[1]))
        pygame.draw.polygon(s, far, pts)
        if biome in ("snow", "mountain"):
            for (x, y) in pts[1:-1]:
                if y < 92 - peaks * 0.8:
                    pygame.draw.polygon(s, (236, 240, 248), [(x - 5, y + 6), (x, y), (x + 5, y + 6)])
        if biome == "volcanic":
            pygame.draw.line(s, (240, 110, 50), (pts[len(pts) // 2][0], pts[len(pts) // 2][1]),
                             (pts[len(pts) // 2][0] + 2, pts[len(pts) // 2][1] - 10), 2)
        # middle band: rolling ground with distant trees
        off = self.scroll * 0.45
        pts = [(0, STRIP[1])]
        for x in range(-20, STRIP[0] + 40, 16):
            pts.append((x, 104 - 8 * math.sin((x + off) * 0.035)))
        pts.append((STRIP[0], STRIP[1]))
        pygame.draw.polygon(s, mid, pts)
        kind = SCENERY.get(tr["terrain"], "tree")
        rng = stable_rng("scenery", tr["from"], tr["to"])
        for i in range(10):
            o = rng.randint(0, 1000)
            x = (o - int(self.scroll * 0.45)) % 1000 - 80
            img = env.prop(kind if kind != "landmark" else "rock", i % 4, biome) or art.obj(kind, i % 4, biome)
            if img is None:
                continue
            sm = _dim(img, 0.75)
            s.blit(sm, (x, 106 - sm.get_height() + (i % 3) * 2))
        # near ground: tiles, the road, close props
        for tx in range(-1, 42):
            x = tx * 16 - int(self.scroll) % 16
            for ty in range(7, 11):
                tid = mg.PATH if ty == 8 else mg.GROUND
                s.blit(art.tile(tid, biome, (tx + ty) % 4), (x, ty * 16 - 14))
        for i in range(7):
            o = rng.randint(0, 1100)
            x = (o - int(self.scroll * 1.25)) % 1100 - 100
            img = env.prop(kind if kind != "landmark" else "tree", (i + 1) % 4, biome) or art.obj(kind, i % 4, biome)
            if img is not None and (x < 230 or x > 420):          # keep the party in view
                s.blit(img, (x, STRIP[1] + 6 - img.get_height()))
        # the party walking (companions follow), campfire when stopped at night
        squad = [st.player.appearance]
        from ...set_system import companions as comp_mod
        from ..art import npc_look
        for cid in comp_mod.squad(st)[:3]:
            npc = self.data.npcs.get(cid)
            if npc:
                squad.append(npc_look(self.data, npc))
        for k, look in enumerate(squad):
            frame = int(self.t * 8 + k * 2) % 6 if moving else 0
            spr = visuals.portrait(art, look, "right", frame, moving)
            s.blit(spr, (330 - k * 30, 136 - spr.get_height() + 10 + (k % 2) * 2))
        # weather
        if wid in ("rain", "storm", "snow"):
            r = stable_rng("p", int(self.t * 10))
            for _ in range(90 if wid == "storm" else 45):
                x, y = r.randrange(STRIP[0]), r.randrange(STRIP[1])
                if wid == "snow":
                    s.set_at((x, y), (240, 240, 255))
                else:
                    pygame.draw.line(s, (170, 190, 220), (x, y), (x - 2, y + 5))
        if wid == "fog":
            fog = pygame.Surface(STRIP, pygame.SRCALPHA)
            fog.fill((200, 200, 210, 90))
            s.blit(fog, (0, 0))
        if light < 0.95:
            d = pygame.Surface(STRIP, pygame.SRCALPHA)
            d.fill((8, 10, 30, int((1 - light) * 170)))
            s.blit(d, (0, 0))
        if not moving and light < 0.6:                      # camp for the night: a fire and its warm light
            fire = env.campfire(int(self.t * 10) % 8)
            if fire is not None:
                glow = pygame.Surface((140, 70), pygame.SRCALPHA)
                for k in range(6, 0, -1):
                    pygame.draw.ellipse(glow, (60 - k * 6, 34 - k * 4, 10, 255),
                                        (70 - k * 11, 35 - k * 5, k * 22, k * 10))
                s.blit(glow, (306, 100), special_flags=pygame.BLEND_RGB_ADD)
                s.blit(fire, (360, 146 - fire.get_height()))
        return s

    def draw_route(self, screen):
        """A ribbon under the title: from -> you -> to, and the goal beyond if one is set on the map."""
        st, tr, data = self.state, self.tr, self.data
        r = pygame.Rect(W // 2 - 360, 56, 720, 34)
        plate = pygame.Surface(r.size, pygame.SRCALPHA)
        pygame.draw.rect(plate, (40, 26, 16, 190), plate.get_rect(), border_radius=8)
        screen.blit(plate, r.topleft)
        x0, x1, y = r.x + 120, r.right - 120, r.centery
        pygame.draw.line(screen, (200, 170, 120), (x0, y), (x1, y), 3)
        f = tr["done"] / max(0.01, tr["km"])
        px = int(x0 + (x1 - x0) * f)
        pygame.draw.line(screen, ui.ACCENT, (x0, y), (px, y), 3)
        for xx in (x0, x1):
            pygame.draw.circle(screen, (240, 220, 170), (xx, y), 6)
            pygame.draw.circle(screen, (40, 26, 16), (xx, y), 6, 1)
        pygame.draw.circle(screen, (200, 50, 40), (px, y), 7)
        pygame.draw.circle(screen, (255, 240, 230), (px, y), 3)
        ui.text(screen, data.location(tr["from"])["name"], (x0 - 12, y - 10), 18, ui.TEXT_DIM, right=True)
        ui.text(screen, data.location(tr["to"])["name"], (x1 + 12, y - 10), 18, ui.ACCENT)
        goal = st.settings.get("map_goal")
        if goal and goal in data.locations and goal != tr["to"]:
            path, km = self.game.world.shortest_path(tr["to"], goal)
            if path:
                ui.text(screen, f"Goal: {data.location(goal)['name']} ({len(path) - 1} more stop"
                                f"{'s' if len(path) != 2 else ''} after this)", (W // 2, r.bottom + 4), 18,
                        (240, 200, 160), center=True)

    def draw(self, screen):
        st = self.state
        tr = self.tr
        if tr is None:
            return
        screen.fill(ui.BG)
        pygame.transform.scale(self.draw_strip(), (W, 300), screen.subsurface((0, 0, W, 300)))
        frm, to = self.data.location(tr["from"])["name"], self.data.location(tr["to"])["name"]
        ui.text(screen, f"{frm}  ->  {to}", (W // 2, 14), 34, ui.ACCENT, bold=True, center=True)
        self.draw_route(screen)
        # log
        r = ui.panel(screen, (20, 312, 850, 396), "Journey")
        lines = []
        for entry in tr["log"][-40:]:
            lines += ui.wrap(entry, 22, r.w - 30)
        y = r.y + 48
        for line in lines[-17:]:
            ui.text(screen, line, (r.x + 14, y), 22, ui.TEXT if not line.startswith("[") else ui.TEXT)
            y += 20
        # status
        p = st.player
        sr = ui.panel(screen, (888, 312, 372, 396), "Status")
        frac = tr["done"] / max(0.01, tr["km"])
        ui.bar(screen, (sr.x + 14, sr.y + 46, sr.w - 28, 18), frac, ui.ACCENT, f"{tr['done']:.1f} / {tr['km']:.1f} km", 18)
        spd, _ = travel.speed_kmh(st)
        eta = (tr["km"] - tr["done"]) / max(0.1, spd)
        wid = weather.weather_for(st, tr["terrain"])
        info = [f"{st.clock.date_str()}  {st.clock.time_str()}",
                f"Weather: {weather.info(wid)['name']}   Terrain: {tr['terrain']}",
                f"Speed {spd:.1f} km/h   ETA {eta:.1f} h",
                f"Rations: {p.inventory.count('ration')}  Water: {p.inventory.count('water')}  Marks: {st.gold}"]
        y = sr.y + 70
        for l in info:
            ui.text(screen, l, (sr.x + 14, y), 21)
            y += 21
        ui.bar(screen, (sr.x + 14, y + 4, 110, 12), p.hp / p.max_hp, ui.HP, None)
        ui.bar(screen, (sr.x + 132, y + 4, 110, 12), p.food / 100, ui.FOOD, None)
        ui.bar(screen, (sr.x + 250, y + 4, 106, 12), p.water / 100, ui.WATER, None)
        ui.text(screen, f"HP {p.hp:.0f}", (sr.x + 14, y + 18), 18, ui.TEXT_DIM)
        ui.text(screen, f"Food {p.food:.0f}", (sr.x + 132, y + 18), 18, ui.TEXT_DIM)
        ui.text(screen, f"Water {p.water:.0f}", (sr.x + 250, y + 18), 18, ui.TEXT_DIM)
        self.menu.draw(screen)
        if self.event_menu:
            ui.dim(screen, 140)
            er = ui.panel(screen, (220, 160, 840, 400), "Something happens...")
            ui.text_block(screen, self.event["text"], (er.x + 24, er.y + 54, er.w - 48, 110), 26)
            self.event_menu.draw(screen)
