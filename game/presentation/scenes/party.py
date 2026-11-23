"""Squad management (stats, equipment, inventory transfer, tasks, dismissal) and the relationships overview."""
import pygame

from ...core.scene import Scene
from ...set_system import companions as comp_mod, items as items_mod, relationships as rel
from ..art import npc_look
from ..ui import widgets as ui
from .common import ConfirmScene, is_close
from .. import visuals

W, H = 1280, 720


class PartyScene(Scene):
    overlay = True

    def __init__(self, game):
        super().__init__(game)
        self.menu = ui.ListMenu([], (70, 120, 330, 520), 24)
        self.refresh()

    def refresh(self):
        st = self.state
        entries = []
        for cid, comp in st.companions.items():
            where = "squad" if comp["active"] else ({"wait": "waiting in " + self.data.location(comp["wait_at"])["name"]
                                                     if comp.get("wait_at") else "waiting"}.get(comp["task"], comp["task"]))
            entries.append((self.data.npcs[cid]["name"], cid, True, where if len(where) < 18 else where[:16] + ".."))
        self.menu.set_entries(entries)

    def handle(self, ev):
        if is_close(ev) or (ev.type == pygame.KEYDOWN and ev.key == pygame.K_p):
            self.close()
            return
        cid = self.menu.selected()
        if ev.type == pygame.KEYDOWN and cid:
            st = self.state
            k = ev.key
            if k == pygame.K_t:
                order = ["follow", "gather", "wait", "home", "guard", "work"]
                cur = st.companions[cid]["task"]
                for i in range(1, len(order) + 1):
                    ok, msg = comp_mod.set_task(st, cid, order[(order.index(cur) + i) % len(order)])
                    if ok:
                        break
                self.game.toast(msg)
                self.refresh()
                return
            if k == pygame.K_g:
                self.game.scenes.push(TransferScene(self.game, cid))
                return
            if k == pygame.K_x:
                def go():
                    ok, msg = comp_mod.dismiss(st, cid)
                    self.game.notify(msg)
                    self.refresh()
                self.game.scenes.push(ConfirmScene(self.game, "Dismiss?", f"Send {self.data.npcs[cid]['name']} home?", go))
                return
        self.menu.handle(ev)

    def on_resume(self):
        self.refresh()

    def draw(self, screen):
        st = self.state
        ui.dim(screen, 150)
        r = ui.panel(screen, (40, 40, W - 80, H - 80), f"Your Company  ({len(comp_mod.squad(st))}/{comp_mod.MAX_SQUAD} in squad)")
        if not st.companions:
            ui.text_block(screen, "Nobody travels with you yet. Every named person in the world can be recruited: "
                                  "talk to them and ask what it would take.", (70, 130, 330, 200), 22, ui.TEXT_DIM)
        self.menu.draw(screen)
        cid = self.menu.selected()
        if not cid:
            return
        comp = st.companions[cid]
        c = comp["char"]
        npc = self.data.npcs[cid]
        x = 450
        spr = pygame.transform.scale(visuals.portrait(self.game.art, npc_look(self.data, npc), "down", 0), (66, 96))
        screen.blit(spr, (x, 110))
        ui.text(screen, npc["name"], (x + 80, 112), 30, ui.ACCENT, bold=True)
        ui.text(screen, f"{self.data.races[npc['race']]['name']} {npc['occupation']}  -  Lv {c.level}  -  task: "
                        f"{comp_mod.TASKS[comp['task']]}", (x + 80, 146), 21, ui.TEXT_DIM)
        ui.bar(screen, (x + 80, 172, 200, 12), c.hp / c.max_hp, ui.HP, f"HP {c.hp:.0f}/{c.max_hp}", 16)
        ui.bar(screen, (x + 290, 172, 130, 12), c.food / 100, ui.FOOD, f"Food {c.food:.0f}", 16)
        ui.bar(screen, (x + 430, 172, 130, 12), c.water / 100, ui.WATER, f"Water {c.water:.0f}", 16)
        y = 220
        for a in ("strength", "speed", "health", "dexterity"):
            ui.text(screen, f"{a.title()} {c.attributes[a]:.0f}", (x, y), 22)
            y += 24
        y = 220
        top = sorted(c.skills.items(), key=lambda kv: -kv[1])[:6]
        for s, v in top:
            ui.text(screen, f"{s.title()} {v:.0f}", (x + 200, y), 22)
            y += 24
        y = 220
        for slot in ("weapon", "ranged", "head", "body"):
            eq = c.equipment.get(slot)
            ui.text(screen, f"{slot.title()}: {self.data.item(eq)['name'] if eq else '-'}", (x + 400, y), 22)
            y += 24
        ui.text(screen, f"Armor {c.armor_value(self.data):.1f}   Carrying {c.inventory.total_weight():.1f}/{c.carry_capacity:.0f} kg",
                (x + 400, y + 4), 20, ui.TEXT_DIM)
        r_ = rel.get(st, cid)
        y = 400
        ui.text(screen, "Relationship", (x, y), 24, ui.ACCENT)
        for i, k in enumerate(("friendship", "trust", "affection", "respect", "conflict")):
            ui.text(screen, k.title(), (x, y + 30 + i * 22), 20, ui.TEXT_DIM)
            ui.bar(screen, (x + 110, y + 34 + i * 22, 220, 10), (r_[k] + 100) / 200, (200, 120, 140) if k == "affection" else (120, 170, 210))
        ui.text(screen, f"Romance: {r_['romance']}", (x, y + 146), 20)
        bonds = [(o, comp_mod.bond(st, cid, o)) for o in st.companions if o != cid]
        ui.text(screen, "With the others", (x + 400, y), 24, ui.ACCENT)
        yy = y + 30
        for o, b in bonds[:7]:
            ui.text(screen, f"{self.data.npcs[o]['name']}: {b['status']} ({b['value']:+d})", (x + 400, yy), 20)
            yy += 22
        ui.text(screen, "[T] change task   [G] give/take items & equip   [X] dismiss   [Esc] close",
                (W // 2, r.bottom - 30), 21, ui.TEXT_DIM, center=True)


class TransferScene(Scene):
    """Move items between you and a companion; equip their gear."""
    overlay = True

    def __init__(self, game, cid):
        super().__init__(game)
        self.cid = cid
        self.focus = 0
        self.mine = ui.ListMenu([], (70, 130, 520, 480), 23)
        self.theirs = ui.ListMenu([], (690, 130, 520, 480), 23)
        self.refresh()

    def refresh(self):
        p = self.state.player
        c = comp_mod.char(self.state, self.cid)
        self.mine.set_entries([(f"{self.data.item(i)['name']} x{q}", i) for i, q in p.inventory.items.items()
                               if i not in p.equipment.values()])
        self.theirs.set_entries([(f"{self.data.item(i)['name']} x{q}" + (" [E]" if i in c.equipment.values() else ""), i)
                                 for i, q in c.inventory.items.items()])

    def handle(self, ev):
        if is_close(ev):
            self.close()
            return
        if ev.type == pygame.KEYDOWN and ev.key in (pygame.K_TAB, pygame.K_LEFT, pygame.K_RIGHT):
            self.focus = 1 - self.focus
            return
        c = comp_mod.char(self.state, self.cid)
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_q and self.focus == 1 and self.theirs.selected():
            item = self.theirs.selected()
            slot = items_mod.weapon_slot(self.data, item)
            if slot and c.equipment.get(slot) == item:
                ok, msg = items_mod.unequip(self.state, c, slot)
            else:
                ok, msg = items_mod.equip(self.state, c, item)
            self.game.toast(msg.replace("Equipped", f"{c.name} equipped"))
            self.refresh()
            return
        menu = self.mine if self.focus == 0 else self.theirs
        v = menu.handle(ev)
        if v:
            qty = 5 if pygame.key.get_mods() & pygame.KMOD_SHIFT else 1
            src = self.state.player.inventory if self.focus == 0 else c.inventory
            qty = min(qty, src.count(v))
            fn = comp_mod.give if self.focus == 0 else comp_mod.take
            ok, msg = fn(self.state, self.cid, v, qty)
            self.game.toast(msg)
            self.refresh()

    def draw(self, screen):
        c = comp_mod.char(self.state, self.cid)
        ui.dim(screen, 150)
        r = ui.panel(screen, (40, 40, W - 80, H - 80), f"Share items with {c.name}")
        for i, (label, x) in enumerate((("You", 70), (c.name, 690))):
            ui.text(screen, label, (x, 96), 28, ui.ACCENT if self.focus == i else ui.TEXT_DIM, bold=True)
        self.mine.draw(screen)
        self.theirs.draw(screen)
        ui.text(screen, "[Enter] move 1   [Shift+Enter] move 5   [Q] equip/unequip their item   [Tab] switch   [Esc] back",
                (W // 2, r.bottom - 30), 21, ui.TEXT_DIM, center=True)


class RelationshipsScene(Scene):
    overlay = True

    def __init__(self, game):
        super().__init__(game)
        st = self.state
        ids = sorted((i for i in st.relationships if i in self.data.npcs),
                     key=lambda i: -(st.relationships[i]["friendship"] + st.relationships[i]["affection"]))
        self.menu = ui.ListMenu([(self.data.npcs[i]["name"], i, True, st.relationships[i]["romance"]
                                  if st.relationships[i]["romance"] != "none" else "") for i in ids],
                                (70, 120, 420, 520), 23)

    def handle(self, ev):
        if is_close(ev) or (ev.type == pygame.KEYDOWN and ev.key == pygame.K_r):
            self.close()
            return
        self.menu.handle(ev)

    def draw(self, screen):
        st = self.state
        ui.dim(screen, 150)
        r = ui.panel(screen, (40, 40, W - 80, H - 80), "Relationships")
        if not self.menu.entries:
            ui.text(screen, "You haven't really met anyone yet.", (70, 130), 24, ui.TEXT_DIM)
        self.menu.draw(screen)
        nid = self.menu.selected()
        if not nid:
            return
        npc = self.data.npcs[nid]
        rr = rel.get(st, nid)
        x = 560
        ui.text(screen, npc["name"], (x, 120), 30, ui.ACCENT, bold=True)
        loc = self.data.location(npc["home"])["name"]
        status = "in your company" if nid in st.companions else f"lives in {loc}"
        ui.text(screen, f"{npc['occupation']} - {status}", (x, 154), 22, ui.TEXT_DIM)
        for i, k in enumerate(("friendship", "trust", "affection", "respect", "conflict")):
            ui.text(screen, k.title(), (x, 196 + i * 30), 22)
            ui.bar(screen, (x + 130, 200 + i * 30, 300, 14), (rr[k] + 100) / 200,
                   (200, 120, 140) if k == "affection" else (120, 170, 210), f"{rr[k]:+d}", 16)
        comp = rel.compatibility(st, npc)
        ui.text(screen, f"Compatibility with you: {comp:.0f}/100", (x, 360), 22)
        ui.text(screen, f"Romance: {rr['romance']}" + ("" if npc.get("romanceable") else " (not interested in romance)"),
                (x, 388), 22)
        if rr["friendship"] >= 20:
            ui.text(screen, f"Likes: {', '.join(npc['likes'])}   Dislikes: {', '.join(npc['dislikes'])}", (x, 416), 22, ui.TEXT_DIM)
        ui.text(screen, "Shared history", (x, 456), 24, ui.ACCENT)
        y = 486
        for m in st.memory.about(nid, limit=6):
            for line in ui.wrap(m["description"], 20, 620)[:2]:
                ui.text(screen, line, (x, y), 20)
                y += 19
