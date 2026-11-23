"""Text-based travel screen (Oregon-Trail style) with a scrolling scenery strip."""
import pygame

from ...core.rng import stable_rng
from ...core.scene import Scene
from ...set_system import needs, timeflow
from ...world import effects, travel, weather
from ...world import mapgen as mg
from ..ui import widgets as ui
from .common import PauseScene
from .. import visuals

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
        self.menu = ui.ListMenu([], (900, 476, 340, 220), 24, row_h=27)
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
        st = self.state
        tr = self.tr
        s = self.strip
        art = self.game.art
        light = st.clock.daylight()
        sky = lerp(SKY_NIGHT, SKY_DAY, (light - 0.35) / 0.65)
        wid = weather.weather_for(st, tr["terrain"])
        if wid in ("rain", "storm", "fog", "overcast", "snow"):
            sky = lerp(sky, (110, 110, 120), 0.5 * light)
        s.fill(sky)
        biome = TERRAIN_BIOME.get(tr["terrain"], tr["terrain"])
        # far hills
        far = tuple(int(c * 0.6) for c in art.tile(mg.GROUND, biome).get_at((0, 0))[:3])
        for i in range(12):
            x = (i * 70 - int(self.scroll * 0.3)) % 760 - 60
            pygame.draw.circle(s, far, (x, 108), 50)
        # ground
        for tx in range(-1, 42):
            x = tx * 16 - int(self.scroll) % 16
            for ty in range(6, 10):
                tid = mg.PATH if ty == 7 else mg.GROUND
                s.blit(art.tile(tid, biome, (tx + ty) % 4), (x, ty * 16 - 4))
        # scenery objects
        kind = SCENERY.get(tr["terrain"], "tree")
        rng = stable_rng("scenery", tr["from"], tr["to"])
        offs = [rng.randint(0, 900) for _ in range(9)]
        for i, o in enumerate(offs):
            x = (o - int(self.scroll)) % 900 - 60
            img = art.obj(kind, i % 4, biome)
            y = 100 - img.get_height() + (i % 3) * 3 if i % 2 else 150 - img.get_height()
            s.blit(img, (x, y))
        # party
        frame = int(self.t * 8) % 4 if self.auto else 0
        s.blit(visuals.portrait(art, st.player.appearance, "right", frame, True), (300, 98))
        # weather particles
        if wid in ("rain", "storm", "snow"):
            r = stable_rng("p", int(self.t * 10))
            for _ in range(60 if wid == "storm" else 30):
                x, y = r.randrange(640), r.randrange(150)
                if wid == "snow":
                    s.set_at((x, y), (240, 240, 255))
                else:
                    pygame.draw.line(s, (170, 190, 220), (x, y), (x - 2, y + 5))
        if light < 0.95:
            d = pygame.Surface(STRIP, pygame.SRCALPHA)
            d.fill((8, 10, 30, int((1 - light) * 200)))
            s.blit(d, (0, 0))
        return s

    def draw(self, screen):
        st = self.state
        tr = self.tr
        if tr is None:
            return
        screen.fill(ui.BG)
        pygame.transform.scale(self.draw_strip(), (W, 300), screen.subsurface((0, 0, W, 300)))
        frm, to = self.data.location(tr["from"])["name"], self.data.location(tr["to"])["name"]
        ui.text(screen, f"{frm}  ->  {to}", (W // 2, 14), 34, ui.ACCENT, bold=True, center=True)
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
