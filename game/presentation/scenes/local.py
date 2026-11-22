"""Top-down local exploration: towns, wilderness, interiors."""
import math

import pygame

from ...core.rng import stable_rng
from ...core.scene import Scene
from ...gameplay import interactions as inter
from ...gameplay import npcs as npc_mod
from ...gameplay.entity import Actor, Wanderer
from ...set_system import timeflow
from ...world import mapgen as mg
from ...world import weather
from ..art import npc_look, random_look
from ..ui import widgets as ui
from .common import ConfirmScene, MessageScene, PauseScene

T = mg.TILE
CW, CH = 640, 360
W, H = 1280, 720
TIME_SCALE = 1.0          # game minutes per real second while exploring
SPRINT_MULT = 1.6
INTERACT_RANGE = 22
LIGHT_KINDS = {"campfire": 70, "lantern": 54, "furnace": 60, "well": 0}


class LocalScene(Scene):
    def __init__(self, game):
        super().__init__(game)
        self.t = 0.0
        self.minute_acc = 0.0
        self.action = None
        self.leave_cooldown = 0.0
        self.load_map()

    # ================================================================ setup
    def load_map(self, spawn=None):
        st = self.state
        if st.sub_location:
            self.map = self.game.interior_map(st.location, st.sub_location)
            self.loc_key = f"{st.location}/{st.sub_location}"
        else:
            self.map = self.game.local_map(st.location)
            self.loc_key = st.location
        self.rebuild_solid()
        if spawn is None:
            spawn = self._spawn_point()
        p = st.player
        self.player = Actor(spawn[0], spawn[1], p.appearance, p.move_speed(), name=p.name)
        st.local_pos = (self.player.x, self.player.y)
        self.last_hour = st.clock.hour
        self.spawn_npcs()

    def rebuild_solid(self):
        self.depleted = inter.depleted_keys(self.state, self.loc_key, self.map.objects)
        self.map.build_solid_grid()

    def _spawn_point(self):
        st, m = self.state, self.map
        if st.local_pos:
            x, y = st.local_pos
            if not m.solid(int(x // T), int(y // T)):
                return x, y
        origin = st.flags.pop("arrived_from", None)
        tx, ty = m.entry
        if origin and m.kind != "interior":
            ex = next((e for e in m.exits if e["to"] == origin), None)
            if ex:
                tx, ty = ex["x"], ex["y"]
                tx += 2 if tx == 0 else (-2 if tx == m.w - 1 else 0)
                ty += 2 if ty == 0 else (-2 if ty == m.h - 1 else 0)
        tx, ty = m.find_open_near(tx, ty)
        return tx * T + T / 2, ty * T + T - 2

    def spawn_npcs(self):
        st, m = self.state, self.map
        building = m.building
        present = npc_mod.present_npcs(st, st.location, m.kind, building)
        self.npcs = []
        spots = list(m.npc_spots) or [m.entry]
        for i, (npc, act) in enumerate(present):
            rng = stable_rng("npcpos", npc["id"], st.clock.day_index, st.clock.hour)
            stationary = False
            if building is not None and building.get("shop") == npc.get("shop") and act == "work":
                sx, sy = spots[0]
                stationary = True
            else:
                sx, sy = spots[(i + rng.randint(0, len(spots) - 1)) % len(spots)]
            sx, sy = m.find_open_near(sx, sy, 3)
            a = Wanderer(sx * T + 8, sy * T + 14, npc_look(self.data, npc), rng,
                         anchor_radius=1 if building else 4, name=npc["name"])
            a.npc = npc
            a.stationary = stationary
            self.npcs.append(a)
        # anonymous shopkeeper for shops without a named owner
        if building is not None and building.get("shop"):
            keeper, at_work = npc_mod.shopkeeper(st, st.location, building["shop"])
            if keeper is None and at_work:
                sx, sy = spots[0]
                rng = stable_rng("keeper", st.location, building["id"])
                race = rng.choice(list(self.data.races))
                a = Wanderer(sx * T + 8, sy * T + 14, random_look(self.data.races[race], rng, race), rng,
                             name="Shopkeeper")
                a.npc = None
                a.stationary = True
                self.npcs.append(a)

    # ================================================================ input
    def handle(self, ev):
        if ev.type != pygame.KEYDOWN:
            return
        k = ev.key
        if self.action:
            if k == pygame.K_ESCAPE:
                self.game.toast("Stopped.")
                self.action = None
            return
        if k == pygame.K_ESCAPE:
            self.game.scenes.push(PauseScene(self.game))
        elif k in (pygame.K_e, pygame.K_SPACE, pygame.K_RETURN):
            self.interact()
        elif k == pygame.K_i:
            from .inventory import InventoryScene
            self.game.scenes.push(InventoryScene(self.game))
        elif k == pygame.K_c:
            from .character import CharacterScene
            self.game.scenes.push(CharacterScene(self.game))
        elif k == pygame.K_j:
            from .journal import JournalScene
            self.game.scenes.push(JournalScene(self.game))
        elif k == pygame.K_m:
            self.open_map(leaving=self.map.kind != "interior")
        elif k == pygame.K_F5:
            self.game.save_game(1)
        elif k == pygame.K_F9:
            if self.game.saves.exists(1):
                self.game.load_game(1)

    def open_map(self, leaving, preselect=None):
        from .worldmap import WorldMapScene
        self.game.scenes.push(WorldMapScene(self.game, can_travel=leaving, preselect=preselect))

    # ================================================================ interaction
    def target(self):
        """Best interaction target in front of the player: ('npc', actor) | ('obj', obj, Interaction) | ('water', ...)."""
        px, py = self.player.x, self.player.y - 4
        fx, fy = self.player.facing_vec()
        qx, qy = px + fx * 10, py + fy * 10
        best, best_d = None, INTERACT_RANGE
        for a in self.npcs:
            d = math.hypot(a.x - qx, (a.y - 6) - qy)
            reach = best_d + (18 if getattr(a, "stationary", False) else 0)  # talk across a shop counter
            if d < reach:
                best, best_d = ("npc", a), min(d, best_d)
        if best:
            return best
        for o in self.map.objects:
            ox, oy = o["x"] * T + T / 2, o["y"] * T + T / 2
            if abs(ox - qx) > 26 or abs(oy - qy) > 26:
                continue
            d = math.hypot(ox - qx, oy - qy)
            if d < best_d:
                ia = inter.for_object(self.state, self.loc_key, o, self.map)
                if ia is not None:
                    best, best_d = ("obj", o, ia), d
        if best:
            return best
        tx, ty = int(qx // T), int(qy // T)
        if self.map.kind != "interior" and inter.water_adjacent(self.map, tx, ty):
            return ("obj", {"kind": "water", "key": "water"},
                    inter.for_object(self.state, self.loc_key, {"kind": "water", "key": "water"}))
        return None

    def prompt(self, tgt):
        if tgt is None:
            return None
        if tgt[0] == "npc":
            a = tgt[1]
            if a.npc is None:
                return "Trade with the Shopkeeper"
            return f"Talk to {a.npc['name']}"
        o, ia = tgt[1], tgt[2]
        if o["kind"] == "door":
            return f"Enter {self.map.buildings[o['building']]['label']}"
        if o["kind"] == "exit_door":
            return "Go outside"
        if o["kind"] == "counter":
            return "Trade"
        if o["kind"] == "bed":
            return "Sleep"
        if o["kind"] == "ore_vein":
            return ia.label
        if o["kind"] == "bush":
            return f"Forage {self.data.item(o['yields'])['name']}"
        return ia.label

    def interact(self):
        tgt = self.target()
        if tgt is None:
            return
        if tgt[0] == "npc":
            a = tgt[1]
            if a.npc is None:
                self.open_shop(self.map.building["shop"])
                return
            from .dialogue import DialogueScene
            self.game.scenes.push(DialogueScene(self.game, a.npc, self))
            return
        o, ia = tgt[1], tgt[2]
        if ia.kind == "refuse":
            self.game.notify(ia.message)
        elif ia.kind == "timed":
            dur = max(0.6, min(3.0, ia.minutes * 0.06))
            self.action = {"ia": ia, "t": 0.0, "dur": dur}
        elif ia.kind == "instant":
            self.game.notify(ia.run(self.state))
        elif ia.kind == "scene":
            self.scene_interaction(o)

    def scene_interaction(self, o):
        k = o["kind"]
        st = self.state
        if k == "door":
            b = self.map.buildings[o["building"]]
            if b["type"] == "property_for_sale":
                self.game.scenes.push(MessageScene(self.game, b["label"],
                    "Locked. A notice is nailed to the door: 'FOR SALE - 600 marks. Enquire with the town steward.'"))
                return
            self.outdoor_return = (o["x"] * T + T / 2, (o["y"] + 1) * T + T - 2)
            st.flags["door_return"] = list(self.outdoor_return)
            st.sub_location = b["id"]
            st.local_pos = None
            self.load_map()
        elif k == "exit_door":
            back = st.flags.pop("door_return", None)
            st.sub_location = None
            st.local_pos = None
            self.load_map(spawn=tuple(back) if back else None)
        elif k == "counter":
            shop = self.map.building.get("shop") if self.map.building else None
            if shop:
                self.open_shop(shop)
        elif k == "bed":
            self.use_bed()
        elif k == "bounty_board":
            self.read_board()

    def open_shop(self, shop_type):
        keeper, at_work = npc_mod.shopkeeper(self.state, self.state.location, shop_type)
        if not at_work:
            who = keeper["name"] if keeper else "The shopkeeper"
            self.game.notify(f"{who} isn't working right now. Come back during the day.")
            return
        from .shop import ShopScene
        self.game.scenes.push(ShopScene(self.game, self.state.location, shop_type, keeper))

    def use_bed(self):
        b = self.map.building
        st = self.state
        if b and b["type"] == "inn":
            price = self.data.shops["inn"]["room_price"]
            keeper, at_work = npc_mod.shopkeeper(st, st.location, "inn")
            if st.gold < price:
                self.game.notify(f"A room costs {price} marks. You can't afford it.")
                return

            def sleep():
                st.gold -= price
                hours, msgs = timeflow.sleep_until_morning(st)
                self.spawn_npcs()
                self.game.scenes.push(MessageScene(self.game, "Rested",
                    f"You pay {price} marks and sleep for {hours:.0f} hours. It is now {st.clock.time_str()}, "
                    f"{st.clock.date_str()}.\n\n" + " ".join(msgs)))
            self.game.scenes.push(ConfirmScene(self.game, "Rent a bed?", f"Sleep until morning for {price} marks?", sleep))
        else:
            self.game.notify("This isn't your bed.")

    def read_board(self):
        lines = []
        for n in self.game.world.neighbors(self.state.location):
            loc = self.data.location(n)
            if loc["kind"] != "wild":
                continue
            foes = sorted({self.data.enemies[e]["name"] for e in loc["enemies"]})
            lines.append(f"- {loc['name']} (danger {loc['danger']}): {', '.join(foes)} sighted.")
        self.game.scenes.push(MessageScene(self.game, "Notice Board",
            "Warnings pinned to the board:\n" + "\n".join(lines) +
            "\n\nThe Crown pays for proof of Hollow outlaws slain. Ask at the barracks."))

    # ================================================================ update
    def update(self, dt):
        self.t += dt
        st = self.state
        m = self.map
        keys = pygame.key.get_pressed()
        sprint = False
        if self.action:
            self.action["t"] += dt
            self.player.action = True
            self.player.moving = False
            if self.action["t"] >= self.action["dur"]:
                ia = self.action["ia"]
                self.action = None
                self.player.action = False
                msgs = timeflow.advance(st, ia.minutes)
                msgs = ia.run(st) + msgs
                self.game.notify(msgs)
                self.rebuild_solid()
        else:
            dx = (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT])
            dy = (keys[pygame.K_s] or keys[pygame.K_DOWN]) - (keys[pygame.K_w] or keys[pygame.K_UP])
            sprint = (keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]) and (dx or dy)
            self.player.speed = st.player.move_speed() * (SPRINT_MULT if sprint else 1.0)
            self.player.move(m, dx, dy, dt)
            if self.player.moving:
                race = st.race_data
                if sprint:
                    st.player.train("speed", dt * 0.4, race)
                    st.player.train("athletics", dt * 0.4, race)
                else:
                    st.player.train("athletics", dt * 0.05, race)
        st.local_pos = (self.player.x, self.player.y)
        # time
        self.minute_acc += dt * TIME_SCALE
        if self.minute_acc >= 1.0:
            whole = int(self.minute_acc)
            self.minute_acc -= whole
            msgs = timeflow.advance(st, whole, exertion=1.6 if sprint else 1.0)
            if msgs:
                self.game.notify(msgs)
        if st.clock.hour != self.last_hour:
            self.last_hour = st.clock.hour
            self.spawn_npcs()
            self.depleted = inter.depleted_keys(st, self.loc_key, m.objects)
        for a in self.npcs:
            a.update(m, dt, stationary=getattr(a, "stationary", False))
            if getattr(a, "stationary", False):
                a.facing = "down"
        # leaving the map by walking to the edge
        self.leave_cooldown = max(0.0, self.leave_cooldown - dt)
        if m.kind != "interior" and self.leave_cooldown <= 0:
            tx, ty = self.player.tile
            if tx <= 0 or ty <= 0 or tx >= m.w - 1 or ty >= m.h - 1:
                ex = min(m.exits, key=lambda e: abs(e["x"] - tx) + abs(e["y"] - ty)) if m.exits else None
                self.leave_cooldown = 1.0
                # step back inside so closing the map doesn't retrigger
                cx, cy = m.w * T / 2, m.h * T / 2
                self.player.x += (cx - self.player.x) / max(1, abs(cx - self.player.x)) * 10
                self.player.y += (cy - self.player.y) / max(1, abs(cy - self.player.y)) * 10
                self.open_map(leaving=True, preselect=ex["to"] if ex else None)
        if not st.player.alive or st.player.hp <= 0:
            self.collapse()

    def collapse(self):
        """Needs-driven collapse: you wake up later, weak, having lost some coin."""
        st = self.state
        st.player.alive = True
        st.player.hp = max(5.0, st.player.max_hp * 0.1)
        st.player.food = max(st.player.food, 20)
        st.player.water = max(st.player.water, 20)
        lost = st.gold // 3
        st.gold -= lost
        timeflow.advance(st, 6 * 60, resting=True)
        st.memory.record("player", "significant", f"{st.player.name} collapsed from exhaustion and lost {lost} marks.",
                         day=st.clock.day_index, minute=st.clock.total_minutes % 1440, importance=2, location=st.location)
        self.game.scenes.push(MessageScene(self.game, "You collapse",
            f"Your body gives out. You wake hours later, weak and aching. Someone has lightened your purse by {lost} marks."))

    # ================================================================ drawing
    def camera(self):
        m = self.map
        mw, mh = m.w * T, m.h * T
        cx = self.player.x - CW / 2
        cy = self.player.y - 8 - CH / 2
        cx = (mw - CW) / 2 if mw <= CW else max(0, min(mw - CW, cx))
        cy = (mh - CH) / 2 if mh <= CH else max(0, min(mh - CH, cy))
        return int(cx), int(cy)

    def draw(self, screen):
        c = self.game.canvas
        art = self.game.art
        m = self.map
        c.fill((22, 20, 26))
        camx, camy = self.camera()
        biome = m.biome
        pal = m.palette
        x0, y0 = max(0, camx // T), max(0, camy // T)
        x1, y1 = min(m.w, (camx + CW) // T + 2), min(m.h, (camy + CH) // T + 2)
        for ty in range(y0, y1):
            row = m.tiles[ty]
            for tx in range(x0, x1):
                c.blit(art.tile(row[tx], biome, (tx * 7 + ty * 13) % 4, pal), (tx * T - camx, ty * T - camy))
        # sortable sprites
        sprites = []
        for o in m.objects:
            if not (x0 - 2 <= o["x"] < x1 + 2 and y0 - 2 <= o["y"] < y1 + 3):
                continue
            img = self.object_image(o)
            if img is None:
                continue
            bx = o["x"] * T + T // 2 - img.get_width() // 2 - camx
            by = (o["y"] + 1) * T - img.get_height() - camy
            sort_y = (o["y"] + 1) * T - (16 if o["kind"] in ("door", "counter", "crop", "exit_door") else 0)
            sprites.append((sort_y, img, bx, by))
        for a in self.npcs + [self.player]:
            img = art.character(a.look, a.facing, a.frame(), a.action)
            sh = art.shadow(12)
            sprites.append((a.y - 0.5, sh, int(a.x - 6 - camx), int(a.y - 3 - camy)))
            sprites.append((a.y, img, int(a.x - 8 - camx), int(a.y - 23 - camy)))
        sprites.sort(key=lambda s: s[0])
        for _, img, bx, by in sprites:
            c.blit(img, (bx, by))
        self.draw_weather(c)
        self.draw_lighting(c, camx, camy)
        pygame.transform.scale(c, (W, H), screen)
        # NPC names (screen space)
        for a in self.npcs:
            if self.player.dist_to(a.x, a.y) < 70:
                label = a.npc["name"] if a.npc else "Shopkeeper"
                ui.text(screen, label, (int((a.x - camx) * 2), int((a.y - 30 - camy) * 2)), 20, ui.TEXT, center=True)
        self.draw_hud(screen)

    def object_image(self, o):
        art, k, m = self.game.art, o["kind"], self.map
        dep = o["key"] in self.depleted
        if k == "ore_vein":
            col = "depleted" if dep else tuple(self.data.ores[o["ore"]]["color"])
            return art.obj("ore_vein", o["x"] % 4, m.biome, col)
        if k == "bush":
            return art.obj("bush", o["yields"], m.biome, "depleted" if dep else None)
        if k in ("scavenge", "mana_crystal_node"):
            return art.obj(k, 0, m.biome, "depleted" if dep else None)
        if k == "campfire":
            return art.obj("campfire", int(self.t * 6) % 2, m.biome)
        return art.obj(k, o.get("variant", 0), m.biome)

    def draw_weather(self, c):
        if self.map.kind == "interior" or self.map.biome == "cave":
            return
        wid = weather.weather_for(self.state, self.map.biome)
        if wid not in ("rain", "storm", "snow", "fog"):
            return
        r = stable_rng("wx", int(self.t * 12))
        if wid == "fog":
            f = pygame.Surface((CW, CH), pygame.SRCALPHA)
            f.fill((200, 205, 215, 60))
            c.blit(f, (0, 0))
            return
        for _ in range({"rain": 70, "storm": 150, "snow": 60}[wid]):
            x, y = r.randrange(CW), r.randrange(CH)
            if wid == "snow":
                c.fill((240, 242, 255), (x, y, 1, 1))
            else:
                pygame.draw.line(c, (150, 170, 210), (x, y), (x - 2, y + 6))

    def draw_lighting(self, c, camx, camy):
        m = self.map
        if m.kind == "interior" and m.biome != "cave":
            return
        light = self.state.clock.daylight() if m.biome != "cave" else 0.55
        if light >= 0.99:
            return
        alpha = int((1.0 - light) * 230)
        dark = pygame.Surface((CW, CH), pygame.SRCALPHA)
        dark.fill((8, 10, 30, alpha))
        lights = [(self.player.x, self.player.y - 8, 46)]
        for o in m.objects:
            rad = LIGHT_KINDS.get(o["kind"])
            if rad:
                lights.append((o["x"] * T + 8, o["y"] * T + 8, rad))
        if m.kind == "town":
            for b in m.buildings.values():
                lights.append((b["door"][0] * T + 8, b["door"][1] * T, 34))
        for lx, ly, rad in lights:
            sx, sy = lx - camx, ly - camy
            if -rad < sx < CW + rad and -rad < sy < CH + rad:
                g = self.game.art.light(rad)
                dark.blit(g, (int(sx - rad), int(sy - rad)), special_flags=pygame.BLEND_RGBA_MIN)
        c.blit(dark, (0, 0))

    def draw_hud(self, screen):
        st = self.state
        p = st.player
        r = ui.panel(screen, (12, 12, 300, 128), alpha=200)
        ui.text(screen, f"{p.name}  (Lv {p.level})", (r.x + 12, r.y + 8), 24, ui.ACCENT)
        ui.bar(screen, (r.x + 12, r.y + 34, 276, 16), p.hp / p.max_hp, ui.HP, f"Health {p.hp:.0f}/{p.max_hp}")
        ui.bar(screen, (r.x + 12, r.y + 56, 276, 16), p.food / 100, ui.FOOD, f"Food {p.food:.0f}")
        ui.bar(screen, (r.x + 12, r.y + 78, 276, 16), p.water / 100, ui.WATER, f"Water {p.water:.0f}")
        ui.bar(screen, (r.x + 12, r.y + 100, 276, 16), p.mana / max(1, p.max_mana), ui.MANA, f"Mana {p.mana:.0f}/{p.max_mana}")
        from ...set_system import needs
        conds = needs.status(p)
        if p.encumbrance() > 1:
            conds.append("overloaded")
        if conds:
            ui.text(screen, ", ".join(c.title() for c in conds), (r.x + 12, r.bottom + 6), 22, ui.TEXT_BAD)
        # right side info
        loc = self.data.location(st.location)
        place = loc["name"] + (f" - {self.map.name}" if self.map.kind == "interior" else "")
        wid = weather.weather_for(st, self.map.biome if self.map.biome not in ("interior",) else loc["biome"])
        lines = [place, st.clock.date_str(), f"{st.clock.time_str()}   {weather.info(wid)['name']}",
                 f"{st.gold} marks"]
        r2 = ui.panel(screen, (W - 352, 12, 340, 112), alpha=200)
        for i, l in enumerate(lines):
            ui.text(screen, l, (r2.right - 12, r2.y + 8 + i * 25), 24 if i else 26,
                    ui.ACCENT if i in (0, 3) else ui.TEXT, right=True)
        # prompt / action
        if self.action:
            frac = self.action["t"] / self.action["dur"]
            ui.bar(screen, (W // 2 - 160, H - 90, 320, 22), frac, ui.ACCENT, self.action["ia"].label + "...", 20)
            ui.text(screen, "[Esc] stop", (W // 2, H - 62), 18, ui.TEXT_DIM, center=True)
        else:
            pr = self.prompt(self.target())
            if pr:
                w = ui.font(24).size(pr)[0] + 70
                pr_r = pygame.Rect(W // 2 - w // 2, H - 64, w, 34)
                ui.panel(screen, pr_r, alpha=210)
                ui.text(screen, "[E] " + pr, (W // 2, H - 56), 24, ui.TEXT, center=True)
        ui.text(screen, "I inventory   C character   M map   J journal   Esc menu", (12, H - 26), 20, ui.TEXT_DIM)
