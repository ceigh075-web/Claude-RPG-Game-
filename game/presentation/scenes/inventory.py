"""Inventory & equipment screen."""
import pygame

from ...core.scene import Scene
from ...set_system import items as items_mod
from ..ui import widgets as ui
from .common import is_close

W, H = 1280, 720


class InventoryScene(Scene):
    overlay = True

    def __init__(self, game):
        super().__init__(game)
        self.menu = ui.ListMenu([], (70, 140, 560, 500), 24)
        self.refresh()

    def refresh(self):
        p = self.state.player
        entries = []
        for item_id, qty in p.inventory.items.items():
            it = self.data.item(item_id)
            eq = " [E]" if item_id in p.equipment.values() else ""
            entries.append((f"{it['name']}{eq}", item_id, True, f"x{qty}   {it['weight'] * qty:.1f}kg"))
        self.menu.set_entries(entries)

    def handle(self, ev):
        if is_close(ev) or (ev.type == pygame.KEYDOWN and ev.key == pygame.K_i):
            self.close()
            return
        p = self.state.player
        sel = self.menu.selected()
        if ev.type == pygame.KEYDOWN and sel:
            if ev.key == pygame.K_x:
                ok, msg = items_mod.drop(self.state, p, sel, 1)
                self.game.notify(msg)
                self.refresh()
                return
            if ev.key == pygame.K_q:
                slot = items_mod.weapon_slot(self.data, sel)
                if slot and p.equipment.get(slot) == sel:
                    ok, msg = items_mod.unequip(self.state, p, slot)
                else:
                    ok, msg = items_mod.equip(self.state, p, sel)
                self.game.notify(msg)
                self.refresh()
                return
        v = self.menu.handle(ev)
        if v:
            if items_mod.can_use(self.data, v):
                ok, msg = items_mod.use_item(self.state, p, v)
            elif items_mod.weapon_slot(self.data, v):
                ok, msg = items_mod.equip(self.state, p, v)
            else:
                ok, msg = False, "Nothing to do with that here."
            self.game.notify(msg)
            self.refresh()

    def draw(self, screen):
        st = self.state
        p = st.player
        ui.dim(screen, 150)
        r = ui.panel(screen, (40, 40, W - 80, H - 80), "Inventory")
        weight, cap = p.inventory.total_weight(), p.carry_capacity
        ui.text(screen, f"Carrying {weight:.1f} / {cap:.0f} kg", (r.x + 30, r.y + 52), 24,
                ui.TEXT_BAD if weight > cap else ui.TEXT)
        ui.text(screen, f"{st.gold} marks", (r.x + 600, r.y + 52), 24, ui.ACCENT, right=True)
        if not self.menu.entries:
            ui.text(screen, "Your pack is empty.", (r.x + 30, r.y + 110), 24, ui.TEXT_DIM)
        self.menu.draw(screen)
        # details
        dx = 700
        ui.text(screen, "Equipped", (dx, r.y + 52), 26, ui.ACCENT)
        y = r.y + 84
        for slot, label in (("weapon", "Melee"), ("ranged", "Ranged")):
            eq = p.equipment.get(slot)
            ui.text(screen, f"{label}: {self.data.item(eq)['name'] if eq else ('Fists' if slot == 'weapon' else '-')}",
                    (dx, y), 24)
            y += 28
        sel = self.menu.selected()
        if sel:
            it = self.data.item(sel)
            y += 20
            pygame.draw.line(screen, ui.BORDER, (dx, y), (r.right - 30, y))
            y += 12
            ui.text(screen, it["name"], (dx, y), 30, ui.ACCENT, bold=True)
            y += 36
            ui.text(screen, f"{it['type'].title()}   Value {it['value']}   Weight {it['weight']} kg", (dx, y), 22, ui.TEXT_DIM)
            y += 30
            y = ui.text_block(screen, it.get("desc", ""), (dx, y, r.right - dx - 30, 120), 23)
            y += 10
            stats = []
            for k in ("food", "water", "heal", "mana"):
                if it.get(k):
                    stats.append(f"+{it[k]} {k}")
            if it["type"] == "weapon":
                w = self.data.weapons[it["weapon"]]
                stats.append(f"Damage {it['damage']}  Speed {it['speed']}/s  Reach {w['reach']}")
                stats.append(f"+ {w['pros']}")
                stats.append(f"- {w['cons']}")
            for s in stats:
                col = ui.TEXT_GOOD if s.startswith("+") else (ui.TEXT_BAD if s.startswith("-") else ui.TEXT)
                ui.text(screen, s, (dx, y), 22, col)
                y += 24
        ui.text(screen, "[Enter] use/equip   [Q] equip/unequip   [X] drop one   [Esc] close",
                (r.centerx, r.bottom - 32), 22, ui.TEXT_DIM, center=True)
