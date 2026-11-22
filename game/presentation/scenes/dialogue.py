"""Conversation with a named NPC. Uses fallback dialogue (Local AI integration arrives in Phase 5)."""
import pygame

from ...core.scene import Scene
from ...gameplay import npcs as npc_mod
from ...local_ai import fallback
from ..art import npc_look
from ..ui import widgets as ui
from .common import is_close

W, H = 1280, 720


class DialogueScene(Scene):
    overlay = True

    def __init__(self, game, npc, local_scene=None):
        super().__init__(game)
        self.npc = npc
        self.local = local_scene
        st = self.state
        key = f"met:{npc['id']}"
        first = not st.flags.get(key)
        if first:
            st.flags[key] = st.clock.day_index
            st.memory.record(npc["id"], "conversation", f"{npc['name']} met {st.player.name} for the first time.",
                             day=st.clock.day_index, minute=st.clock.total_minutes % 1440, importance=2,
                             related=["player"], location=st.location)
        self.line = fallback.greeting(npc, st, first)
        self.menu = ui.ListMenu([], (360, 520, 840, 150), 25, row_h=30)
        self.build()

    def build(self):
        npc = self.npc
        entries = [("Who are you?", "about"), ("Tell me about this place.", "place"), ("Heard any news?", "rumor"),
                   ("Would you travel with me?", "recruit")]
        if npc.get("shop"):
            _, at_work = npc_mod.shopkeeper(self.state, self.state.location, npc["shop"])
            entries.append(("Let's trade.", "trade", at_work))
        entries.append(("Goodbye.", "bye"))
        self.menu.set_entries(entries)

    def say(self, topic, text):
        self.line = text
        self.state.memory.add_chatter(self.npc["id"], f"Player asked about {topic}.", self.state.clock.day_index)

    def handle(self, ev):
        if is_close(ev):
            self.close()
            return
        v = self.menu.handle(ev)
        if not v:
            return
        npc = self.npc
        if v == "about":
            self.say("them", fallback.about(npc))
        elif v == "place":
            self.say("the town", fallback.place(npc, self.state))
        elif v == "rumor":
            self.say("news", fallback.rumor(npc, self.state))
        elif v == "recruit":
            self.say("recruitment", fallback.recruit_hint(npc))
        elif v == "trade":
            from .shop import ShopScene
            self.close()
            self.game.scenes.push(ShopScene(self.game, self.state.location, npc["shop"], npc))
        elif v == "bye":
            self.line = fallback.farewell(npc)
            self.close()
            self.game.toast(f"{npc['name']}: \"{self.line}\"")

    def draw(self, screen):
        npc = self.npc
        ui.dim(screen, 90)
        r = ui.panel(screen, (40, 380, W - 80, 310))
        spr = self.game.art.character(npc_look(self.data, npc), "down", 0)
        screen.blit(pygame.transform.scale(spr, (160, 240)), (90, 400))
        ui.text(screen, npc["name"], (360, 396), 32, ui.ACCENT, bold=True)
        race = self.data.races[npc["race"]]["name"]
        fac = self.data.factions[npc["faction"]]["name"] if npc.get("faction") else "Independent"
        ui.text(screen, f"{race} {npc['occupation']}  -  {fac}", (360, 428), 22, ui.TEXT_DIM)
        ui.text_block(screen, f"\"{self.line}\"", (360, 456, 840, 64), 25)
        self.menu.draw(screen)
