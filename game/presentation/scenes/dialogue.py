"""Conversation with a named NPC: free text or topics, answered by the Local AI (or fallback templates).
Everything that changes the game goes through Set System calls / the AI action bridge."""
import pygame

from ...core.scene import Scene
from ...gameplay import npcs as npc_mod
from ...local_ai import fallback, personality
from ...local_ai.dialogue import DialogueEngine
from ...set_system import factions, favors, recruitment, relationships as rel
from ..art import npc_look
from ..ui import widgets as ui
from .common import ConfirmScene, MessageScene, is_close

W, H = 1280, 720
TOPIC_LINES = {"about": "Tell me about yourself.", "place": "What is this place like?", "rumor": "Heard any news?",
               "favor": "Is there anything I can help you with?", "join": "Would you travel with me?",
               "trade": "Let's trade."}
PEACE_COST = 300


class DialogueScene(Scene):
    overlay = True

    def __init__(self, game, npc, local_scene=None):
        super().__init__(game)
        self.npc = npc
        self.local = local_scene
        st = self.state
        r = rel.get(st, npc["id"])
        first = r["met"] is None and not st.flags.get(f"met:{npc['id']}")
        if first:
            st.flags[f"met:{npc['id']}"] = True
            r["met"] = st.clock.day_index
            st.memory.record(npc["id"], "conversation", f"{npc['name']} met {st.player.name} for the first time.",
                             day=st.clock.day_index, minute=st.clock.total_minutes % 1440, importance=2,
                             related=["player"], location=st.location)
        self.engine = DialogueEngine(st, npc, game.config)
        self.log = [(npc["name"], fallback.greeting(npc, st, first))]
        self.typing = None
        self.waiting = False
        self.source = "ai" if self.engine.client.enabled else "fallback"
        self.menu = ui.ListMenu([], (360, 548, 840, 140), 24, row_h=28)
        self.build()

    # ------------------------------------------------------------ menu
    def build(self):
        st, npc = self.state, self.npc
        e = [("Say something...", "type"), ("Who are you?", "about"), ("Tell me about this place.", "place"),
             ("Heard any news?", "rumor")]
        fid = favors.favor_of(npc)
        fst = favors.status(st, fid) if fid else None
        if fid and fst is None:
            e.append(("Can I help you with anything?", "favor"))
        elif fid and fst == "active":
            d = favors.defs(self.data)[fid]
            if d["type"] == "duel" and st.mode == "local" and d["npc"] == npc["id"] and not st.flags.get(f"duel_won:{npc['id']}"):
                e.append(("I'm ready for our fight.", "duel"))
            e.append((f"About your request ({d['title']})...", "favor"))
        e.append(("Give a gift", "gift"))
        if npc["id"] == "gruka":
            e.append((f"Broker peace with the Crown ({PEACE_COST} marks tribute)", "peace", self.peace_possible()))
        e += self.extra_entries()
        if npc.get("shop"):
            _, at_work = npc_mod.shopkeeper(st, st.location, npc["shop"])
            e.append(("Let's trade.", "trade", at_work))
        e.append(("Goodbye.", "bye"))
        self.menu.set_entries(e)

    def extra_entries(self):
        """Recruitment, companion orders and romance options."""
        from ...set_system import companions as comp_mod
        st, npc = self.state, self.npc
        e = []
        if npc["id"] in st.companions:
            comp = st.companions[npc["id"]]
            if comp["task"] != "follow":
                e.append(("Come with me.", "c_follow"))
            if comp["task"] == "follow":
                e.append(("Gather supplies as we travel.", "c_gather"))
                e.append(("Wait here for me.", "c_wait"))
            e.append(("It's time we parted ways.", "c_dismiss"))
        else:
            e.append(("Would you travel with me?", "join"))
        r = rel.get(st, npc["id"])
        if rel.can_ask_out(st, npc):
            e.append(("Would you like to spend more time together... just us?", "r_ask"))
        if r["romance"] in ("dating", "partners") and r.get("last_date") != st.clock.day_index:
            e.append(("Let's spend the evening together (2 hours).", "r_date"))
        if rel.can_commit(st, npc):
            e.append(("I want to be with you. Only you.", "r_commit"))
        if r["romance"] in ("dating", "partners"):
            e.append(("I think we should end things.", "r_break"))
        return e

    def peace_possible(self):
        st = self.state
        return (not st.flags.get("peace_crown_thornblood") and st.reputation.get("crown", 0) >= 30
                and st.reputation.get("thornblood", 0) >= 30 and st.gold >= PEACE_COST)

    # ------------------------------------------------------------ actions
    def send(self, line, topic=None):
        self.log.append(("You", line))
        self.waiting = True
        self.engine.start(line, topic)

    def handle(self, ev):
        if self.waiting:
            if is_close(ev):  # never trap the player behind a slow model
                self.engine.pending = None
                self.close()
            return
        if self.typing is not None:
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    self.typing = None
                elif ev.key == pygame.K_RETURN:
                    line = self.typing.strip()
                    self.typing = None
                    if line:
                        self.send(line)
                elif ev.key == pygame.K_BACKSPACE:
                    self.typing = self.typing[:-1]
                elif ev.unicode and ev.unicode.isprintable() and len(self.typing) < 160:
                    self.typing += ev.unicode
            return
        if is_close(ev):
            self.close()
            return
        v = self.menu.handle(ev)
        if not v:
            return
        npc, st = self.npc, self.state
        if v == "type":
            self.typing = ""
        elif v in TOPIC_LINES:
            if v == "join" and not recruitment.can_recruit(self.state, self.npc)[0]:
                self.show_requirements()
            self.send(TOPIC_LINES[v], v)
        elif v == "duel":
            from .duel import DuelScene
            self.close()
            self.game.scenes.replace(DuelScene(self.game, npc))
        elif v == "gift":
            self.game.scenes.push(GiftScene(self.game, npc, self))
        elif v == "peace":
            self.broker_peace()
        elif v == "bye":
            self.close()
            self.game.toast(f"{npc['name']}: \"{fallback.farewell(npc)}\"")
        else:
            self.extra_action(v)

    def extra_action(self, v):
        from ...set_system import companions as comp_mod, timeflow
        st, npc = self.state, self.npc
        msg = None
        if v in ("c_follow", "c_gather", "c_wait"):
            ok, msg = comp_mod.set_task(st, npc["id"], {"c_follow": "follow", "c_gather": "gather", "c_wait": "wait"}[v])
            if ok and self.local is not None:
                self.local.load_map(spawn=(self.local.player.x, self.local.player.y))
        elif v == "c_dismiss":
            def go():
                ok, m = comp_mod.dismiss(st, npc["id"])
                self.game.notify(m)
                if self.local is not None:
                    self.local.load_map(spawn=(self.local.player.x, self.local.player.y))
                self.close()
            self.game.scenes.push(ConfirmScene(self.game, "Part ways?", f"Send {npc['name']} home? They will take their "
                                               "own gear; shared supplies come back to you.", go))
            return
        elif v == "r_ask":
            ok, msg = rel.ask_out(st, npc)
        elif v == "r_commit":
            ok, msg = rel.commit(st, npc)
        elif v == "r_break":
            ok, msg = rel.breakup(st, npc["id"])
        elif v == "r_date":
            r = rel.get(st, npc["id"])
            r["last_date"] = st.clock.day_index
            timeflow.advance(st, 120)
            rel.change(st, npc["id"], affection=5, trust=3, friendship=2)
            st.memory.record(npc["id"], "relationship", f"{npc['name']} and {st.player.name} spent an evening together.",
                             day=st.clock.day_index, minute=st.clock.total_minutes % 1440, importance=2,
                             related=["player"], location=st.location)
            msg = f"You spend a quiet evening with {npc['name']}."
        if msg:
            self.log.append((npc["name"] if v.startswith("r_") else "", msg))
            self.game.toast(msg)
        self.build()

    def show_requirements(self):
        main, alt = recruitment.requirements(self.state, self.npc)
        lines = [("[x] " if ok else "[ ] ") + label for label, ok in main]
        if alt:
            lines += ["", "Or instead:"] + [("[x] " if ok else "[ ] ") + label for label, ok in alt]
        fid = favors.favor_of(self.npc)
        if fid:
            done, detail = favors.progress(self.state, fid) if favors.status(self.state, fid) else (False, "")
            if detail:
                lines += ["", f"Favor progress: {detail}"]
        self.game.scenes.push(MessageScene(self.game, f"Recruiting {self.npc['name']}", "\n".join(lines)))

    def broker_peace(self):
        st = self.state

        def do():
            st.gold -= PEACE_COST
            st.flags["peace_crown_thornblood"] = True
            key = "crown|thornblood"
            st.faction_relations[key] = st.faction_relations.get(key, -40) + 60
            factions.change_rep(st, "thornblood", 10, "brokered peace")
            factions.change_rep(st, "crown", 10, "brokered peace")
            rel.change(st, "gruka", reason="the player brought peace to the clans", respect=20, trust=15)
            st.memory.record("world", "political", f"{st.player.name} brokered a peace between the Crown and the "
                             "Thornblood Clans.", day=st.clock.day_index, minute=st.clock.total_minutes % 1440,
                             importance=5, related=["player", "gruka", "queen_aldra"], location=st.location)
            self.log.append((self.npc["name"], "Then let it be peace. The clans will remember who carried the word."))
            self.build()
        self.game.scenes.push(ConfirmScene(self.game, "Broker peace?",
            f"Pay {PEACE_COST} marks in tribute and carry the terms between Velmora and Thornhollow?", do))

    def on_result(self, out):
        self.waiting = False
        self.source = out["source"]
        self.log.append((self.npc["name"], out["say"]))
        for r in out["results"]:
            if r.get("ui") == "trade":
                from .shop import ShopScene
                self.game.scenes.push(ShopScene(self.game, self.state.location, self.npc["shop"], self.npc))
            elif r.get("ui") == "recruit":
                self.offer_recruit()
            elif r.get("ui") == "end":
                self.close()
                return
            if r["action"] in ("offer_favor", "check_favor") and r["ok"]:
                self.game.toast(r["result"])
        self.build()

    def offer_recruit(self):
        from ...set_system import companions as comp_mod
        st, npc = self.state, self.npc
        ok, path = recruitment.can_recruit(st, npc)
        if not ok:
            return
        req = {"main": npc["recruit"], "alt": npc["recruit"].get("alt", {}), "rejoin": {}}[path]
        cost = req.get("gold", 0)

        def go():
            ok2, msg = comp_mod.recruit(st, npc)
            self.game.notify(msg)
            if ok2 and self.local is not None:
                self.local.spawn_npcs()
                self.local.load_map(spawn=(self.local.player.x, self.local.player.y))
            self.close()
        self.game.scenes.push(ConfirmScene(self.game, f"Recruit {npc['name']}?",
            f"{npc['name']} is ready to join you" + (f" for {cost} marks." if cost else ".")
            + (" They lead a faction: their people will choose a successor." if npc.get("leader") else ""), go))

    def update(self, dt):
        if self.waiting:
            out = self.engine.poll()
            if out:
                self.on_result(out)

    # ------------------------------------------------------------ drawing
    def draw(self, screen):
        npc, st = self.npc, self.state
        ui.dim(screen, 90)
        ui.panel(screen, (40, 330, W - 80, 370))
        spr = self.game.art.character(npc_look(self.data, npc), "down", 0)
        screen.blit(pygame.transform.scale(spr, (160, 240)), (90, 380))
        ui.text(screen, npc["name"], (360, 342), 32, ui.ACCENT, bold=True)
        race = self.data.races[npc["race"]]["name"]
        fac = self.data.factions[npc["faction"]]["name"] if npc.get("faction") else "Independent"
        r = rel.get(st, npc["id"])
        ui.text(screen, f"{race} {npc['occupation']}  -  {fac}  -  {personality.mood_for(r)}"
                        + (f"  -  {r['romance']}" if r["romance"] != "none" else ""), (360, 374), 21, ui.TEXT_DIM)
        bx = W - 330
        for i, k in enumerate(("friendship", "trust", "affection", "respect")):
            v = r[k]
            ui.text(screen, k.title(), (bx, 344 + i * 18), 18, ui.TEXT_DIM)
            ui.bar(screen, (bx + 90, 348 + i * 18, 160, 9), (v + 100) / 200, (200, 120, 140) if k == "affection" else (120, 170, 210))
        tag = "local AI" if self.source == "ai" else "offline dialogue"
        ui.text(screen, tag, (W - 60, 680), 16, ui.TEXT_DIM, right=True)
        # conversation log
        lines = []
        for who, text in self.log[-6:]:
            lines += [(who if i == 0 else "", l) for i, l in enumerate(ui.wrap(text, 23, 760))]
        y = 400
        for who, l in lines[-7:]:
            x = 360
            if who:
                x += ui.text(screen, who + ": ", (360, y), 22, ui.ACCENT if who != "You" else ui.TEXT_GOOD) + 6
            ui.text(screen, l, (x if who else 372, y), 23)
            y += 20
        if self.waiting:
            dots = "." * (1 + int(pygame.time.get_ticks() / 400) % 3)
            ui.text(screen, f"{npc['name']} is thinking{dots}", (360, 528), 22, ui.TEXT_DIM)
        elif self.typing is not None:
            pygame.draw.rect(screen, (20, 18, 26), (356, 520, 850, 28))
            pygame.draw.rect(screen, ui.BORDER_HI, (356, 520, 850, 28), 1)
            ui.text(screen, "> " + self.typing + "_", (362, 524), 22)
            ui.text(screen, "[Enter] say   [Esc] cancel", (W - 60, 552), 18, ui.TEXT_DIM, right=True)
        if self.typing is None:
            self.menu.draw(screen)


class GiftScene(Scene):
    overlay = True

    def __init__(self, game, npc, parent):
        super().__init__(game)
        self.npc, self.parent = npc, parent
        p = self.state.player
        entries = [(f"{self.data.item(i)['name']} x{q}", i, True, ", ".join(sorted(self.data.item_tags(i))))
                   for i, q in p.inventory.items.items() if i not in p.equipment.values() and self.data.item(i)["type"] != "key"]
        self.menu = ui.ListMenu(entries, (W // 2 - 300, 170, 600, 380), 24)

    def handle(self, ev):
        if is_close(ev):
            self.close()
            return
        v = self.menu.handle(ev)
        if v:
            ok, msg, d = rel.gift(self.state, self.npc, v)
            self.game.toast(msg)
            if ok:
                self.parent.log.append((self.npc["name"], msg))
            self.close()

    def draw(self, screen):
        ui.dim(screen, 120)
        r = ui.panel(screen, (W // 2 - 330, 110, 660, 480), f"Give {self.npc['name']} a gift")
        ui.text(screen, f"Likes: {', '.join(self.npc['likes'])}" if rel.get(self.state, self.npc["id"])["friendship"] >= 20
                else "You don't know their tastes yet.", (r.x + 20, r.bottom - 40), 22, ui.TEXT_DIM)
        if not self.menu.entries:
            ui.text(screen, "You have nothing to give.", (r.x + 30, r.y + 60), 24, ui.TEXT_DIM)
        self.menu.draw(screen)
