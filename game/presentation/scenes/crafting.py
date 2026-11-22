"""Crafting at a station: pick a recipe, see ingredients, craft (time passes, Crafting trains)."""
import pygame

from ...core.scene import Scene
from ...set_system import crafting, timeflow
from ..ui import widgets as ui
from .common import is_close

W, H = 1280, 720


class CraftingScene(Scene):
    overlay = True

    def __init__(self, game, station):
        super().__init__(game)
        self.station = station
        self.menu = ui.ListMenu([], (70, 130, 560, 500), 23)
        self.refresh()

    def refresh(self):
        entries = []
        if self.station == "campfire":
            entries.append(("Rest by the fire (1 hour)", "__rest", True, ""))
        recs = crafting.recipes_for(self.data, self.station)
        outs = [r["out"] for r in recs]
        for r in recs:
            ok, why = crafting.check(self.state, r)
            name = self.data.item(r["out"])["name"] + (f" x{r['qty']}" if r["qty"] > 1 else "")
            if outs.count(r["out"]) > 1:
                name += f" (from {self.data.item(next(iter(r['inputs'])))['name']})"
            hidden = r.get("requires") and r["requires"] not in self.state.known_recipes
            entries.append((name, r["id"], True, "unknown" if hidden else ("ready" if ok else "")))
        self.menu.set_entries(entries)

    def handle(self, ev):
        if is_close(ev):
            self.close()
            return
        v = self.menu.handle(ev)
        if not v:
            return
        if v == "__rest":
            self.game.notify(["You rest by the fire for an hour."] + timeflow.advance(self.state, 60, resting=True))
            return
        r = self.data.recipes[v]
        times = 1
        if pygame.key.get_mods() & pygame.KMOD_SHIFT:
            times = 5
            while times > 1 and not crafting.check(self.state, r, times)[0]:
                times -= 1
        ok, msgs = crafting.craft(self.state, r, times)
        self.game.notify(msgs)
        self.refresh()

    def draw(self, screen):
        st = self.state
        p = st.player
        ui.dim(screen, 150)
        r = ui.panel(screen, (40, 40, W - 80, H - 80), crafting.STATIONS[self.station])
        ui.text(screen, f"Crafting skill {p.skills['crafting']:.1f}", (r.right - 30, r.y + 12), 24, ui.ACCENT, right=True)
        self.menu.draw(screen)
        sel = self.menu.selected()
        x, y = 700, 130
        if sel and sel != "__rest":
            rec = self.data.recipes[sel]
            it = self.data.item(rec["out"])
            ui.text(screen, it["name"], (x, y), 30, ui.ACCENT, bold=True)
            y = ui.text_block(screen, it.get("desc", ""), (x, y + 36, 500, 90), 22, ui.TEXT_DIM) + 10
            ui.text(screen, "Ingredients", (x, y), 24, ui.ACCENT)
            y += 28
            for item, qty in rec["inputs"].items():
                have = p.inventory.count(item)
                ui.text(screen, f"{self.data.item(item)['name']}", (x + 10, y), 22, ui.TEXT if have >= qty else ui.TEXT_BAD)
                ui.text(screen, f"{have}/{qty}", (x + 480, y), 22, ui.TEXT if have >= qty else ui.TEXT_BAD, right=True)
                y += 24
            y += 10
            ui.text(screen, f"Time: {crafting.craft_minutes(st, rec)} min    Crafting needed: {rec.get('skill', 0)}", (x, y), 22)
            ok, why = crafting.check(st, rec)
            if not ok:
                ui.text_block(screen, why, (x, y + 30, 500, 50), 22, ui.TEXT_BAD)
            if it["type"] == "weapon":
                w = self.data.weapons[it["weapon"]]
                ui.text(screen, f"Damage {it['damage']}  Speed {it['speed']}  Reach {w['reach']}", (x, y + 70), 22)
            elif it["type"] == "armor":
                ui.text(screen, f"Armor {it['armor']}  ({it['slot']})", (x, y + 70), 22)
        ui.text(screen, "[Enter] craft   [Shift+Enter] craft up to 5   [Esc] close", (r.centerx, r.bottom - 32), 22,
                ui.TEXT_DIM, center=True)
