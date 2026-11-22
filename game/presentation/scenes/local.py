"""Top-down local exploration and real-time combat: towns, wilderness, interiors."""
import math
import random

import pygame

from ...core.rng import stable_rng
from ...core.scene import Scene
from ...gameplay import interactions as inter
from ...gameplay import npcs as npc_mod
from ...gameplay.combat import CombatWorld, facing_from, norm
from ...gameplay.entity import Actor, Wanderer
from ...set_system import base as base_mod
from ...set_system import factions, skirmish, timeflow
from ...world import mapgen as mg
from ...world import weather
from .. import combat_draw
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
GROUP_RESPAWN_DAYS = 4
ATTACK_KEYS = (pygame.K_k,)
BLOCK_KEYS = (pygame.K_l,)


class LocalScene(Scene):
    def __init__(self, game):
        super().__init__(game)
        self.t = 0.0
        self.minute_acc = 0.0
        self.action = None
        self.leave_cooldown = 0.0
        self.mouse_aim_t = 0.0
        self.mouse_pos = (0, 0)
        self.combat = None
        self.last_level = game.state.player.level
        self.hint = None
        self.load_map()

    # ================================================================ setup
    def load_map(self, spawn=None):
        st = self.state
        if self.combat is not None:
            self.note_escape()
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
        actor = Actor(spawn[0], spawn[1], p.appearance, p.move_speed(), name=p.name)
        self.combat = CombatWorld(self.game, st, self.map, random.Random(st.rng.random()))
        self.player = self.combat.add_player(actor)
        st.local_pos = (self.player.x, self.player.y)
        self.last_hour = st.clock.hour
        self.active_groups = set()
        self.apply_base()
        self.spawn_npcs()
        self.spawn_companions()
        self.spawn_base_people()
        self.spawn_enemies()

    def spawn_companions(self):
        """Squad members follow the player; companions told to wait here stand where they were left."""
        from ...set_system import companions as comp_mod
        st = self.state
        px, py = self.player.x, self.player.y
        for i, cid in enumerate(comp_mod.squad(st)):
            ch = comp_mod.char(st, cid)
            x, y = px - 14 + (i % 2) * 28, py + 10 + (i // 2) * 12
            tx, ty = self.map.find_open_near(int(x // T), int(y // T), 3)
            self.combat.add_companion(cid, ch, tx * T + 8, ty * T + 12, npc_look(self.data, self.data.npcs[cid]))
        if self.at_home():
            spots = list(self.map.npc_spots) or [self.map.entry]
            for i, (cid, comp) in enumerate((c, v) for c, v in st.companions.items() if v["task"] == "home"):
                sx, sy = self.map.find_open_near(*spots[i % len(spots)], 3)
                spot = (sx * T + 8, sy * T + 12)
                self.combat.add_companion(cid, comp["char"], spot[0], spot[1], npc_look(self.data, self.data.npcs[cid]),
                                          wait_spot=spot)
        if st.sub_location is None and self.loc_key == st.location:
            for cid, comp in st.companions.items():
                if not comp["active"] and comp["task"] == "wait" and comp.get("wait_at") == st.location:
                    spot = comp.get("wait_pos")
                    if not spot:
                        ex, ey = self.map.find_open_near(*self.map.entry, 4)
                        spot = (ex * T + 8 + len(cid) % 5 * 10, ey * T + 12)
                        comp["wait_pos"] = list(spot)
                    self.combat.add_companion(cid, comp["char"], spot[0], spot[1],
                                              npc_look(self.data, self.data.npcs[cid]), wait_spot=tuple(spot))

    # ================================================================ enemies
    def spawn_enemies(self):
        """Spawn this wilderness area's enemy groups that aren't currently defeated."""
        st, m = self.state, self.map
        if m.kind != "wild" or st.sub_location:
            return
        groups = st.location_state(self.loc_key).setdefault("groups", {})
        st.location_state(self.loc_key)["group_count"] = len(m.spawns)
        now = st.clock.total_minutes
        for i, sp in enumerate(m.spawns):
            gid = f"{st.location}:{i}"
            g = groups.get(gid, {})
            if g.get("until", 0) > now:
                continue
            e = self.data.enemies[sp["enemy"]]
            rng = stable_rng("pack", gid, st.clock.day_index)
            n = rng.randint(*e["pack"])
            fac = e.get("faction")
            if fac and "hostile_rep" in e:
                hostile = st.reputation.get(fac, 0) < e["hostile_rep"]
            else:
                hostile = factions.is_hostile(st, fac) if fac else True
            if fac == "hollow" and st.flags.get("hollow_broken"):
                n = max(1, n // 2)
            for _ in range(n):
                tx, ty = m.find_open_near(sp["x"] + rng.randint(-2, 2), sp["y"] + rng.randint(-2, 2), 4)
                c = self.combat.spawn_enemy(sp["enemy"], tx * T + 8, ty * T + 12, group=gid, hostile=hostile)
                c.remembers = bool(g.get("remembers"))
            self.active_groups.add(gid)
        self.spawn_world_enemies(groups, now)

    def spawn_world_enemies(self, groups, now):
        """Enemies created by world events (raids, war patrols, named monsters) and Hollow-held territory."""
        from ...set_system import world_events
        st, m = self.state, self.map
        extra = list(world_events.spawn_modifiers(st, st.location))
        if world_events.holder(st, st.location) == "hollow":
            extra.append({"enemy": "bandit_cutthroat", "count": 3, "event": "territory"})
            extra.append({"enemy": "hollow_captain", "count": 1, "event": "territory2"})
        for k, mod in enumerate(extra):
            gid = f"{st.location}:ev:{mod['event']}:{k}"
            if groups.get(gid, {}).get("until", 0) > now:
                continue
            rng = stable_rng("evspawn", gid)
            sx, sy = rng.randint(6, m.w - 7), rng.randint(5, m.h - 6)
            edef = None
            if mod.get("elite"):
                base = self.data.enemies[mod["enemy"]]
                edef = dict(base, name=mod["elite"], hp=base["hp"] * 4, damage=round(base["damage"] * 1.5, 1),
                            armor=base["armor"] + 4, xp=base["xp"] * 5, flee_below=0,
                            loot=dict(base["loot"], marks=[120, 220]), elite_event=mod["event"])
            for _ in range(mod.get("count", 1)):
                tx, ty = m.find_open_near(sx + rng.randint(-2, 2), sy + rng.randint(-2, 2), 5)
                c = self.combat.spawn_enemy(mod["enemy"], tx * T + 8, ty * T + 12, group=gid, hostile=True, edef=edef)
                if edef:
                    c.poise, c.mass = 0.9, 3.0
            self.active_groups.add(gid)

    def check_groups(self):
        """Record defeated or scattered groups (Set System state + Set AI memory)."""
        st = self.state
        groups = st.location_state(self.loc_key).setdefault("groups", {})
        for c in getattr(self.combat, "escaped", []):
            st.memory.record(c.enemy_id, "escaped", f"A {c.name} fled from a fight with {st.player.name}.",
                             day=st.clock.day_index, minute=st.clock.total_minutes % 1440, importance=1,
                             related=["player"], location=st.location)
        self.combat.escaped = []
        for gid in list(self.active_groups):
            members = [c for c in self.combat.combatants if c.group == gid]
            if any(c.alive for c in members):
                continue
            self.active_groups.discard(gid)
            groups[gid] = {"until": st.clock.total_minutes + GROUP_RESPAWN_DAYS * 1440,
                           "defeated_at": st.clock.total_minutes}
            eid = next((sp["enemy"] for i, sp in enumerate(self.map.spawns) if f"{st.location}:{i}" == gid), None)
            if eid:
                e = self.data.enemies[eid]
                from ...set_system import companions as comp_mod
                comp_mod.shared_victory(st, len([c for c in self.combat.kills if c == eid]))
                st.memory.record("player", "battle", f"Cleared a group of {e['name']}s at {self.data.location(st.location)['name']}.",
                                 day=st.clock.day_index, minute=st.clock.total_minutes % 1440,
                                 importance=2 if e.get("faction") else 1, related=[eid], location=st.location)

    def note_escape(self):
        """Leaving while hostiles are hunting you: they remember (unkilled enemies keep memories)."""
        st = self.state
        if getattr(self, "raid_active", False):
            self.raid_over(fought=False)
        if self.combat is None or not self.combat.in_combat:
            return
        groups = st.location_state(self.loc_key).setdefault("groups", {})
        for gid in {c.group for c in self.combat.enemies() if c.alerted and c.hostile and c.group}:
            if gid not in self.active_groups:
                continue
            groups.setdefault(gid, {})["remembers"] = True
            eid = next(c.enemy_id for c in self.combat.enemies() if c.group == gid)
            st.memory.record(eid, "escaped", f"{st.player.name} fled from a fight with {self.data.enemies[eid]['name']}s.",
                             day=st.clock.day_index, minute=st.clock.total_minutes % 1440, importance=2,
                             related=["player"], location=st.location)

    def on_exit(self):
        self.note_escape()

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
    def mouse_world(self):
        camx, camy = self.camera()
        return self.mouse_pos[0] / 2 + camx, self.mouse_pos[1] / 2 + camy

    def aim_at_mouse(self):
        mx, my = self.mouse_world()
        self.player.aim = norm(mx - self.player.x, my - (self.player.y - 8))

    def handle(self, ev):
        pc = self.player
        cw = self.combat
        if ev.type == pygame.MOUSEMOTION:
            self.mouse_pos = ev.pos
            self.mouse_aim_t = 3.0
            return
        if ev.type == pygame.MOUSEBUTTONDOWN and not self.action:
            self.mouse_pos = ev.pos
            self.mouse_aim_t = 3.0
            if ev.button == 1:
                self.aim_at_mouse()
                cw.attack(pc)
            return
        if ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
            cw.release_draw(pc)
            return
        if ev.type == pygame.KEYUP and ev.key in ATTACK_KEYS:
            cw.release_draw(pc)
            return
        if ev.type != pygame.KEYDOWN:
            return
        k = ev.key
        if self.action:
            if k == pygame.K_ESCAPE:
                self.game.toast("Stopped.")
                self.action = None
            return
        if k in ATTACK_KEYS:
            cw.attack(pc)
        elif k == pygame.K_f:
            cw.kick(pc)
        elif k == pygame.K_SPACE:
            keys = pygame.key.get_pressed()
            dx = (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT])
            dy = (keys[pygame.K_s] or keys[pygame.K_DOWN]) - (keys[pygame.K_w] or keys[pygame.K_UP])
            cw.dodge(pc, (dx, dy))
        elif k == pygame.K_q:
            cw.switch_weapon()
        elif pygame.K_1 <= k <= pygame.K_4:
            i = k - pygame.K_1
            bar = self.hotbar()
            if i < len(bar):
                if self.mouse_aim_t > 0:
                    self.aim_at_mouse()
                ok, msg = cw.cast(pc, bar[i])
                if msg:
                    self.game.toast(msg)
        elif k == pygame.K_ESCAPE:
            self.game.scenes.push(PauseScene(self.game))
        elif k in (pygame.K_e, pygame.K_RETURN):
            self.interact()
        elif k == pygame.K_p:
            from .party import PartyScene
            self.game.scenes.push(PartyScene(self.game))
        elif k == pygame.K_r:
            from .party import RelationshipsScene
            self.game.scenes.push(RelationshipsScene(self.game))
        elif k == pygame.K_b:
            from .spellbook import SpellbookScene
            self.game.scenes.push(SpellbookScene(self.game, at_table=False))
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

    def hotbar(self):
        return self.state.spellbook[:4]

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
        # companions follow you closely, so they are only targeted when nothing else is in front of you
        for a in self.combat.companions():
            if a.alive and math.hypot(a.x - qx, (a.y - 6) - qy) < INTERACT_RANGE:
                return ("npc", a)
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
            if b["type"] == "property_for_sale" and not base_mod.owns_house(st, st.location, b["id"]):
                price = base_mod.house_price(st, st.location)

                def buy():
                    ok, msg = base_mod.buy_house(st, st.location, b["id"])
                    self.game.notify(msg)
                    if ok:
                        self.scene_interaction(o)
                self.game.scenes.push(ConfirmScene(self.game, "House for sale",
                    f"A notice on the door: 'FOR SALE - {price} marks.' Buy this house? (You have {st.gold}.)", buy))
                return
            from .. import audio
            audio.play("door")
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
        elif k in ("anvil", "furnace", "workbench", "stove", "alchemy_table", "campfire"):
            from ...set_system.crafting import OBJECT_STATION
            from .crafting import CraftingScene
            self.game.scenes.push(CraftingScene(self.game, OBJECT_STATION[k]))
        elif k == "landmark" and o.get("feature") in inter.TREASURES:
            if self.combat.in_combat:
                self.game.notify("Not while enemies are hunting you.")
                return
            self.game.notify(inter.take_treasure(st, o["feature"]))
        elif k == "scribing_table" and self.at_home():
            self.study_menu()
        elif k == "scribing_table":
            from .spellbook import SpellbookScene
            self.game.scenes.push(SpellbookScene(self.game, at_table=True))
        elif k == "chest":
            if not self.at_home():
                self.game.notify("Not your chest.")
                return
            from .base import StorageScene
            self.game.scenes.push(StorageScene(self.game, st.property[st.location], "Your house chest"))
        elif k == "landmark" and o.get("feature") == "outpost_site":
            self.outpost_site()
        elif k.startswith("base_"):
            self.base_object(o)
        elif k == "training_dummy":
            from .practice import PracticeScene
            self.game.scenes.replace(PracticeScene(self.game))

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
        if b and b["type"] == "property_for_sale" and self.at_home():
            self.sleep_free("your own bed")
            return
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
                self.game.autosave()
                self.game.scenes.push(MessageScene(self.game, "Rested",
                    f"You pay {price} marks and sleep for {hours:.0f} hours. It is now {st.clock.time_str()}, "
                    f"{st.clock.date_str()}.\n\n" + " ".join(msgs)))
            self.game.scenes.push(ConfirmScene(self.game, "Rent a bed?", f"Sleep until morning for {price} marks?", sleep))
        else:
            self.game.notify("This isn't your bed.")

    # ================================================================ property & outpost
    def at_home(self):
        b = self.map.building
        return bool(b) and b["type"] == "property_for_sale" and base_mod.owns_house(self.state, self.state.location, b["id"])

    def sleep_free(self, where):
        st = self.state

        def sleep():
            hours, msgs = timeflow.sleep_until_morning(st)
            self.spawn_npcs()
            self.game.autosave()
            self.game.scenes.push(MessageScene(self.game, "Rested", f"You sleep in {where} for {hours:.0f} hours. It is now "
                                  f"{st.clock.time_str()}, {st.clock.date_str()}.\n\n" + " ".join(msgs)))
        self.game.scenes.push(ConfirmScene(self.game, "Sleep?", f"Sleep in {where} until morning?", sleep))

    def study_menu(self):
        from .base import ResearchScene
        from .common import ChoiceScene
        from .spellbook import SpellbookScene
        self.game.scenes.push(ChoiceScene(self.game, "Your desk", [("Spell book (inscribe spells)", "book"),
                                                                   ("Research projects", "research")],
            lambda v: self.game.scenes.push(SpellbookScene(self.game, at_table=True) if v == "book" else ResearchScene(self.game))))

    def compute_plots(self):
        site = next((o for o in self.map.objects if o.get("feature") == "outpost_site"), None)
        cx, cy = (site["x"], site["y"]) if site else self.map.entry
        cands = []
        for dy in range(-9, 10, 3):
            for dx in range(-12, 13, 3):
                x, y = cx + dx, cy + dy
                if (dx, dy) != (0, 0) and self.map.free_for_object(x, y) and not self.map.solid(x, y + 1):
                    cands.append((abs(dx) + abs(dy), x, y))
        cands.sort()
        return [(x, y) for _, x, y in cands[:self.data.base["outpost"]["plots"]]]

    def outpost_site(self):
        st = self.state
        if base_mod.founded(st):
            from .base import BaseScene
            self.game.scenes.push(BaseScene(self.game, self))
            return
        marks, items = base_mod.outpost_cost(st)
        need = ", ".join(f"{q} {self.data.item(i)['name']}" for i, q in items.items())

        def found():
            ok, msg = base_mod.found_outpost(st, self.compute_plots())
            self.game.notify(msg)
            if ok:
                self.apply_base()
        self.game.scenes.push(ConfirmScene(self.game, "Found an outpost?",
            f"Claim Widow's Crossing for your own outpost: {marks} marks and {need}. "
            "You can then build storage, workshops, farms, bunkhouses, walls and more.", found))

    def base_object(self, o):
        st = self.state
        k = o["kind"]
        from .base import BaseScene, ResearchScene, StorageScene
        from .common import ChoiceScene
        b = base_mod.building_at(st, o["plot"]) if "plot" in o else None
        if b and not b["done"]:
            left = max(0, (b["ready_at"] - st.clock.total_minutes) / 60)
            self.game.notify(f"Under construction: {left:.0f} hours left.")
            return
        if k == "base_storage":
            self.game.scenes.push(StorageScene(self.game, st.base, "Outpost storage"))
        elif k == "base_workshop":
            from .crafting import CraftingScene
            self.game.scenes.push(ChoiceScene(self.game, "Workshop", [("Furnace", "furnace"), ("Anvil", "anvil"),
                                                                     ("Workbench", "workbench")],
                                              lambda v: self.game.scenes.push(CraftingScene(self.game, v))))
        elif k == "base_farm":
            opts = [(f"Plant {self.data.item(sd)['name']} (2)", ("plant", sd)) for sd in self.data.base["crops"]] + \
                   [("Harvest", ("harvest", None))]

            def act(v):
                res = base_mod.plant(st, o["plot"], v[1]) if v[0] == "plant" else base_mod.harvest(st, o["plot"])
                self.game.notify(res[1])
                self.apply_base()
            crop = b.get("crop") if b else None
            body = "Empty field." if not crop else (f"{self.data.item(crop['seed'])['name']} - ripe!" if st.clock.day_index >= crop["ready_day"]
                                                    else f"{self.data.item(crop['seed'])['name']} - ready on day {crop['ready_day'] + 1}.")
            self.game.scenes.push(ChoiceScene(self.game, "Farm plot", opts, act, body=body))
        elif k == "base_research":
            self.study_menu()
        elif k == "base_training":
            from .practice import PracticeScene
            self.game.scenes.replace(PracticeScene(self.game))
        elif k == "base_bunkhouse":
            self.sleep_free("the outpost bunkhouse")
        else:
            self.game.scenes.push(BaseScene(self.game, self))

    def apply_base(self):
        """Place outpost buildings (and empty plot markers) on the Widow's Crossing map."""
        st, m = self.state, self.map
        if st.sub_location or not base_mod.founded(st) or st.location != st.base.get("location"):
            return
        m.objects = [o for o in m.objects if not o.get("base")]
        for i, (x, y) in enumerate(st.base["plots"]):
            b = base_mod.building_at(st, i)
            if not b:
                kind = "base_plot"
            elif not b["done"]:
                kind = "base_construction"
            else:
                kind = f"base_{b['type']}"
            o = m.add(kind, x, y, solid=kind not in ("base_plot", "base_farm"), base=True, plot=i)
            o["key"] = f"base{i}"
        m.build_solid_grid()

    def spawn_base_people(self):
        """Workers stand by their buildings, guards by the centre; raiders arrive if a raid is under way."""
        st = self.state
        if st.sub_location or not base_mod.founded(st) or st.location != st.base.get("location"):
            return
        plots = st.base["plots"]
        for cid, comp in st.companions.items():
            if comp["task"] not in ("work", "guard"):
                continue
            if comp["task"] == "work" and comp.get("post") is not None:
                px, py = plots[int(comp["post"])]
                spot = ((px + 1) * T + 8, (py + 1) * T + 10)
            else:
                site = next((o for o in self.map.objects if o.get("feature") == "outpost_site"), None)
                sx, sy = (site["x"], site["y"]) if site else self.map.entry
                spot = ((sx + 1 + len(cid) % 3) * T + 8, (sy + 1) * T + 10)
            self.combat.add_companion(cid, comp["char"], spot[0], spot[1], npc_look(self.data, self.data.npcs[cid]),
                                      wait_spot=spot)
        self.raid_active = False
        self.check_raid()

    def check_raid(self):
        st = self.state
        raid = st.base.get("raid") if base_mod.founded(st) else None
        if not raid or getattr(self, "raid_active", False) or st.location != st.base.get("location") or st.sub_location \
                or self.loc_key != st.location:
            return
        self.raid_active = True
        n = max(2, int(raid["strength"] // 15))
        rng = stable_rng("raid", raid["day"])
        ex = min(self.map.exits, key=lambda e: e["x"]) if self.map.exits else {"x": 2, "y": self.map.h // 2}
        for i in range(n):
            eid = "hollow_captain" if i == 0 and raid["strength"] > 50 else rng.choice(["bandit_cutthroat", "bandit_cutthroat", "bandit_archer"])
            tx, ty = self.map.find_open_near(ex["x"] + 3 + rng.randint(0, 3), ex["y"] + rng.randint(-3, 3), 5)
            c = self.combat.spawn_enemy(eid, tx * T + 8, ty * T + 12, group="raid", hostile=True)
            c.alerted = True
        self.game.toast("The Hollow is attacking your outpost!")
        from .. import audio
        audio.play("alarm")

    def raid_over(self, fought):
        st = self.state
        if getattr(self, "raid_active", False) and st.base.get("raid"):
            self.raid_active = False
            msg = base_mod.resolve_raid(st, st.base["raid"]["strength"], self.combat.rng, fought=fought)
            self.game.notify(msg)

    def read_board(self):
        from .jobs import JobBoardScene
        self.game.scenes.push(JobBoardScene(self.game, self.state.location))

    # ================================================================ update
    def update(self, dt):
        self.t += dt
        st = self.state
        m = self.map
        keys = pygame.key.get_pressed()
        sprint = False
        pc = self.player
        if self.action and pc.flash > 0:
            self.action = None
            pc.action = False
            self.game.toast("Interrupted!")
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
                from .. import audio
                audio.play("mine" if "Mine" in ia.label or "rock" in ia.label else ("chop" if "Chop" in ia.label else "pickup"))
                self.game.notify(msgs)
                self.rebuild_solid()
        else:
            dx = (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT])
            dy = (keys[pygame.K_s] or keys[pygame.K_DOWN]) - (keys[pygame.K_w] or keys[pygame.K_UP])
            mouse = pygame.mouse.get_pressed()
            block = any(keys[k] for k in BLOCK_KEYS) or (mouse[2] if len(mouse) > 2 else False)
            if block != pc.blocking:
                self.combat.set_block(pc, block)
            busy = pc.state not in ("idle",) or pc.blocking
            sprint = (keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]) and (dx or dy) and not busy
            self.mouse_aim_t = max(0.0, self.mouse_aim_t - dt)
            if self.mouse_aim_t > 0 and pc.state in ("idle", "windup", "draw") or pc.blocking and self.mouse_aim_t > 0:
                self.aim_at_mouse()
            elif (dx or dy) and pc.state in ("idle", "draw") :
                pc.aim = norm(dx, dy)
            spd_buff = 1 + pc.buffs.get("speed", [0])[0] / 50.0
            self.player.speed = st.player.move_speed() * (SPRINT_MULT if sprint else 1.0) * pc.move_mult() * spd_buff
            if pc.state not in ("dodge", "stagger", "dead"):
                self.player.move(m, dx, dy, dt)
            if busy or self.mouse_aim_t > 0:
                pc.facing = facing_from(pc.aim)
            if self.player.moving:
                race = st.race_data
                if sprint:
                    st.player.train("speed", dt * 0.4, race)
                    st.player.train("athletics", dt * 0.4, race)
                else:
                    st.player.train("athletics", dt * 0.05, race)
        pc.armor = st.player.armor_value(self.data)
        self.combat.update(dt, m)
        if self.combat.events:
            for msg in self.combat.events:
                self.game.toast(msg)
                st.add_log(msg)
            self.combat.events = []
        self.check_groups()
        self.polish_update(dt)
        if base_mod.founded(st):
            self.check_raid()
            if getattr(self, "raid_active", False) and not any(c.alive and c.group == "raid" for c in self.combat.enemies()):
                self.raid_over(fought=True)
        st.local_pos = (self.player.x, self.player.y)
        # time
        self.minute_acc += dt * TIME_SCALE
        if self.minute_acc >= 1.0:
            whole = int(self.minute_acc)
            self.minute_acc -= whole
            msgs = timeflow.advance(st, whole, exertion=1.6 if sprint or self.combat.in_combat else 1.0)
            if msgs:
                self.game.notify(msgs)
        if st.clock.hour != self.last_hour:
            self.last_hour = st.clock.hour
            if self.map.kind == "wild":
                from ...set_system import companions as comp_mod
                for msg in comp_mod.gather(st, 1, self.combat.rng):
                    self.game.toast(msg)
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
                self.on_edge(ex)
        if pc.state == "dead":
            self.defeated()
        elif not st.player.alive or st.player.hp <= 0:
            self.collapse()

    def polish_update(self, dt):
        """Music mood, level-up fanfare and first-time hints."""
        from .. import audio
        from . import hints
        st = self.state
        audio.music("combat" if self.combat.in_combat else ("town" if self.map.kind in ("town", "interior") else "wild"))
        if st.player.level > self.last_level:
            self.last_level = st.player.level
            audio.play("levelup")
            from ...set_system import spells
            self.game.toast(f"Level up! You are now level {st.player.level}. "
                            f"Spell book capacity {spells.capacity(self.data, st.player.level)}.", 5)
            st.memory.record("player", "accomplishment", f"{st.player.name} reached level {st.player.level}.",
                             day=st.clock.day_index, minute=st.clock.total_minutes % 1440, importance=2)
        if self.hint:
            self.hint[1] -= dt
            if self.hint[1] <= 0:
                self.hint = None
        if not self.hint:
            h = hints.next_hint(self)
            if h:
                self.hint = [h, 9.0]

    def on_edge(self, ex):
        self.open_map(leaving=True, preselect=ex["to"] if ex else None)

    def strongest_foe(self):
        foes = [c for c in self.combat.enemies(alive=False) if c.alerted] or self.combat.enemies(alive=False)
        if not foes:
            return None
        return max(foes, key=lambda c: c.enemy["xp"]).enemy_id

    def defeated(self):
        """Beaten in combat: robbed (by outlaws) and left; wake at the area entrance."""
        st = self.state
        eid = self.strongest_foe() or "bandit_cutthroat"
        if getattr(self, "raid_active", False):
            self.raid_over(fought=False)
        msg = skirmish.apply_defeat(st, eid)
        st.player.hp = max(st.player.hp, st.player.max_hp * 0.2)
        timeflow.advance(st, 3 * 60, resting=True)
        groups = st.location_state(self.loc_key).setdefault("groups", {})
        for gid in self.active_groups:
            groups.setdefault(gid, {})["remembers"] = True
        st.local_pos = None
        self.combat = None  # no escape record: they won
        self.load_map(spawn=self._entry_spawn())
        self.game.scenes.push(MessageScene(self.game, "Defeated", msg + " Hours later you drag yourself back to your feet."))

    def _entry_spawn(self):
        tx, ty = self.map.find_open_near(*self.map.entry)
        return tx * T + T / 2, ty * T + T - 2

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
        if self.combat.shake > 0:
            camx += int(random.uniform(-1, 1) * self.combat.shake)
            camy += int(random.uniform(-1, 1) * self.combat.shake)
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
        sprites += combat_draw.sprite_entries(self.combat, art, camx, camy, self.t)
        for a in self.npcs:
            img = art.character(a.look, a.facing, a.frame(), a.action)
            sh = art.shadow(12)
            sprites.append((a.y - 0.5, sh, int(a.x - 6 - camx), int(a.y - 3 - camy)))
            sprites.append((a.y, img, int(a.x - 8 - camx), int(a.y - 23 - camy)))
        sprites.sort(key=lambda s: s[0])
        for _, img, bx, by in sprites:
            c.blit(img, (bx, by))
        combat_draw.draw_fx(c, self.combat, art, camx, camy, self.t)
        self.draw_weather(c)
        self.draw_lighting(c, camx, camy)
        pygame.transform.scale(c, (W, H), screen)
        combat_draw.draw_floaters(screen, self.combat, camx, camy)
        # NPC names (screen space)
        for a in self.npcs + self.combat.companions():
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
        if k.startswith("base_"):
            b = base_mod.building_at(self.state, o["plot"])
            extra = None
            if b and b.get("damaged"):
                extra = "damaged"
            elif b and b["type"] == "farm" and b.get("crop"):
                extra = "ripe" if self.state.clock.day_index >= b["crop"]["ready_day"] else "growing"
            return art.obj(k, 0, m.biome, extra)
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
        from ...set_system import companions as comp_mod
        y = r.bottom + 32
        for cid in comp_mod.squad(st):
            ch = comp_mod.char(st, cid)
            ui.text(screen, ch.name.split()[0] if len(ch.name) > 14 else ch.name, (r.x + 4, y), 18, ui.TEXT)
            ui.bar(screen, (r.x + 110, y + 3, 120, 9), ch.hp / ch.max_hp, ui.HP)
            if ch.food < 25 or ch.water < 25:
                ui.text(screen, "needs supplies", (r.x + 236, y), 16, ui.TEXT_BAD)
            y += 18
        # right side info
        loc = self.data.location(st.location)
        place = self.place_name()
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
        combat_draw.draw_combat_hud(screen, self.combat, st, self.data, W, H, self.hotbar())
        if p.hp < p.max_hp * 0.3:
            pulse = 0.5 + 0.5 * math.sin(self.t * 5)
            v = pygame.Surface((W, H), pygame.SRCALPHA)
            a = int(60 + 60 * pulse * (1 - p.hp / max(1, p.max_hp * 0.3)))
            for i in range(6):
                pygame.draw.rect(v, (150, 0, 0, max(0, a - i * 10)), (i * 8, i * 8, W - i * 16, H - i * 16), 8)
            screen.blit(v, (0, 0))
        if self.hint:
            lines = ui.wrap(self.hint[0], 21, 440)
            hr = ui.panel(screen, (12, H - 70 - len(lines) * 19, 470, 30 + len(lines) * 19), alpha=225)
            ui.text(screen, "Tip", (hr.x + 10, hr.y + 6), 20, ui.ACCENT, bold=True)
            for i, l in enumerate(lines):
                ui.text(screen, l, (hr.x + 50, hr.y + 6 + i * 19), 21)
        ui.text(screen, "K/LMB attack  L/RMB block  F kick  Space dodge  1-4 spells  B book  I inv  C char  M map  J journal",
                (12, H - 26), 20, ui.TEXT_DIM)

    def place_name(self):
        loc = self.data.location(self.state.location)
        return loc["name"] + (f" - {self.map.name}" if self.map.kind == "interior" else "")
