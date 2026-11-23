"""Inventory & equipment screen: filters, sorting, comparison with what you're wearing, and an item card that
says where things come from and what they're for."""
import pygame

from ...core.scene import Scene
from ...set_system import items as items_mod
from .. import knowledge
from .. import icons
from ..ui import widgets as ui
from .common import is_close

W, H = 1280, 720
FILTERS = [("All", None), ("Gear", ("weapon", "armor", "tool", "ammo")),
           ("Supplies", ("food", "drink", "medicine", "magic")),
           ("Materials", ("material", "ore", "bar")), ("Other", ("valuable", "key", "recipe", "book"))]
SORTS = ["type", "name", "value", "weight"]
TYPE_ORDER = ["weapon", "armor", "ammo", "tool", "food", "drink", "medicine", "magic", "ore", "bar", "material",
              "valuable", "recipe", "book", "key"]


class InventoryScene(Scene):
    overlay = True

    def __init__(self, game):
        super().__init__(game)
        self.menu = ui.ListMenu([], (70, 168, 540, 456), 24)
        self.menu.icon_for = lambda v: icons.ui_icon(self.data, v) if v in self.data.items or v == 'marks' else None
        self.filter = 0
        self.sort = 0
        self.refresh()

    def refresh(self):
        p = self.state.player
        allowed = FILTERS[self.filter][1]
        rows = []
        for item_id, qty in p.inventory.items.items():
            it = self.data.item(item_id)
            if allowed and it["type"] not in allowed:
                continue
            rows.append((item_id, qty, it))
        key = SORTS[self.sort]
        if key == "type":
            rows.sort(key=lambda r: (TYPE_ORDER.index(r[2]["type"]) if r[2]["type"] in TYPE_ORDER else 99, r[2]["name"]))
        elif key == "name":
            rows.sort(key=lambda r: r[2]["name"])
        elif key == "value":
            rows.sort(key=lambda r: -r[2]["value"] * r[1])
        else:
            rows.sort(key=lambda r: -r[2]["weight"] * r[1])
        entries = []
        for item_id, qty, it in rows:
            eq = "  (worn)" if item_id in p.equipment.values() else ""
            right = f"x{qty}  " + (f"{it['value'] * qty}m" if key == "value" else f"{it['weight'] * qty:.1f}kg")
            entries.append((f"{it['name']}{eq}", item_id, True, right))
        self.menu.set_entries(entries)

    def handle(self, ev):
        if is_close(ev) or (ev.type == pygame.KEYDOWN and ev.key == pygame.K_i):
            self.close()
            return
        p = self.state.player
        if ev.type == pygame.KEYDOWN and ev.key in (pygame.K_TAB, pygame.K_RIGHT, pygame.K_LEFT):
            self.filter = (self.filter + (-1 if ev.key == pygame.K_LEFT else 1)) % len(FILTERS)
            self.menu.index = 0
            self.refresh()
            return
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_r:
            self.sort = (self.sort + 1) % len(SORTS)
            self.refresh()
            return
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
            if self.data.item(v)["type"] == "recipe":
                from ...set_system import crafting
                ok, msg = crafting.learn(self.state, v)
            elif items_mod.can_use(self.data, v):
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
        ui.bar(screen, (r.x + 260, r.y + 14, 220, 18), weight / max(1, cap), ui.TEXT_BAD if weight > cap else (150, 120, 80),
               f"{weight:.1f} / {cap:.0f} kg", 17)
        ui.text(screen, f"{st.gold} marks", (r.right - 30, r.y + 14), 26, ui.ACCENT, right=True)
        # filter tabs + sort
        x = r.x + 30
        for i, (name, _) in enumerate(FILTERS):
            on = i == self.filter
            w = ui.font(22, on).size(name)[0] + 20
            tab = pygame.Rect(x, r.y + 52, w, 28)
            pygame.draw.rect(screen, ui.PANEL_LIGHT if on else (44, 30, 18), tab, border_radius=4)
            pygame.draw.rect(screen, ui.BORDER_HI if on else ui.BORDER, tab, 1, border_radius=4)
            ui.text(screen, name, (tab.centerx, tab.y + 5), 22, ui.ACCENT if on else ui.TEXT_DIM, bold=on, center=True)
            x += w + 6
        ui.text(screen, f"Sort: {SORTS[self.sort]}", (r.x + 580, r.y + 57), 20, ui.TEXT_DIM, right=True)
        if not self.menu.entries:
            ui.text(screen, "Nothing here." if p.inventory.items else "Your pack is empty.", (r.x + 30, r.y + 130), 24,
                    ui.TEXT_DIM)
        self.menu.draw(screen)
        # equipped strip
        dx = 680
        y = r.y + 52
        ui.text(screen, "Worn", (dx, y), 24, ui.ACCENT, bold=True)
        y += 28
        for slot, label in (("weapon", "Melee"), ("ranged", "Ranged"), ("head", "Head"), ("body", "Body")):
            eq = p.equipment.get(slot)
            ui.text(screen, label, (dx, y), 21, ui.TEXT_DIM)
            ui.text(screen, self.data.item(eq)["name"] if eq else ("Fists" if slot == "weapon" else "-"), (dx + 80, y), 21)
            y += 22
        ui.text(screen, f"Armour {p.armor_value(self.data):.1f}", (dx + 330, r.y + 80), 21, ui.TEXT)
        sel = self.menu.selected()
        if sel:
            self.draw_card(screen, sel, pygame.Rect(dx, y + 10, r.right - dx - 24, r.bottom - y - 60))
        ui.text(screen, "[Enter] use / equip   [Q] equip / unequip   [X] drop one   [Tab] filter   [R] sort   [Esc] close",
                (r.centerx, r.bottom - 32), 21, ui.TEXT_DIM, center=True)

    def draw_card(self, screen, sel, box):
        """Parchment item card: description, stats, comparison, where to get it, what it's for."""
        p = self.state.player
        it = self.data.item(sel)
        ui.parchment(screen, box)
        x, y, w = box.x + 14, box.y + 10, box.w - 28
        screen.blit(icons.ui_icon(self.data, sel), (x - 2, y - 2))
        x += 38
        w -= 38
        ui.ink(screen, it["name"], (x, y), 28, ui.INK, bold=True)
        ui.ink(screen, f"{it['type'].title()}   {it['value']} marks   {it['weight']} kg", (x + w, y + 6), 19, ui.INK_DIM, right=True)
        x, w = x - 38, w + 38
        y += 30
        y = ui.ink_block(screen, it.get("desc", ""), (x, y, w, 60), 20, ui.INK_DIM)
        y += 4
        lines = []
        if it["type"] == "weapon":
            wd = self.data.weapons[it["weapon"]]
            lines.append((f"Damage {it['damage']}   Speed {it['speed']}/s   Reach {wd['reach']}", ui.INK))
            slot = items_mod.weapon_slot(self.data, sel)
            cur = p.equipment.get(slot)
            if cur and cur != sel:
                c = self.data.item(cur)
                dd, ds = it["damage"] - c["damage"], it["speed"] - c["speed"]
                lines.append((f"vs {c['name']}: damage {dd:+.1f}, speed {ds:+.2f}",
                              ui.INK_GREEN if dd * it["speed"] + ds * it["damage"] > 0 else ui.INK_RED))
            lines.append(("+ " + wd["pros"], ui.INK_GREEN))
            lines.append(("- " + wd["cons"], ui.INK_RED))
        elif it["type"] == "armor":
            lines.append((f"Armour {it['armor']} ({it['slot']})", ui.INK))
            cur = p.equipment.get(it["slot"])
            if cur and cur != sel:
                da = it["armor"] - self.data.item(cur)["armor"]
                lines.append((f"vs {self.data.item(cur)['name']}: armour {da:+.1f}", ui.INK_GREEN if da > 0 else ui.INK_RED))
        for ln, col in lines:
            y = ui.ink_block(screen, ln, (x, y, w, 40), 20, col)
        y += 6
        st = self.state
        key = (sel, len(st.discovered))
        if getattr(self, "_kn_key", None) != key:
            self._kn_key = key
            self._kn = (knowledge.uses(st, sel)[:3], knowledge.sources(st, sel)[:3])
        for title, items in (("What it's for", self._kn[0]), ("Where to get it", self._kn[1])):
            if y > box.bottom - 50 or not items:
                continue
            ui.ink(screen, title, (x, y), 21, ui.INK_RED, bold=True)
            y += 22
            for ln in items:
                if y > box.bottom - 24:
                    break
                y = ui.ink_block(screen, "- " + ln, (x + 6, y, w - 6, box.bottom - y - 6), 19, ui.INK)
            y += 6
