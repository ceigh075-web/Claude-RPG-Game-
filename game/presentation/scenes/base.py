"""Outpost management, storage transfer and research screens."""
import pygame

from ...core.scene import Scene
from ...set_system import base
from .. import icons
from ..ui import widgets as ui
from .common import ChoiceScene, ConfirmScene, is_close

W, H = 1280, 720


class StorageScene(Scene):
    """Move items between your pack and a storage container (house chest or outpost shed)."""
    overlay = True

    def __init__(self, game, holder, title):
        super().__init__(game)
        self.holder, self.title = holder, title
        self.focus = 0
        self.mine = ui.ListMenu([], (70, 130, 520, 480), 23)
        self.store = ui.ListMenu([], (690, 130, 520, 480), 23)
        self.mine.icon_for = self.store.icon_for = lambda v: icons.ui_icon(self.data, v) if v in self.data.items or v == 'marks' else None
        self.refresh()

    def refresh(self):
        p = self.state.player
        inv = base.storage(self.state, self.holder)
        self.mine.set_entries([(f"{self.data.item(i)['name']} x{q}", i) for i, q in p.inventory.items.items()
                               if i not in p.equipment.values() and i != "house_deed"])
        self.store.set_entries([(f"{self.data.item(i)['name']} x{q}", i) for i, q in inv.items.items()])

    def handle(self, ev):
        if is_close(ev):
            self.close()
            return
        if ev.type == pygame.KEYDOWN and ev.key in (pygame.K_TAB, pygame.K_LEFT, pygame.K_RIGHT):
            self.focus = 1 - self.focus
            return
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_q:
            from ...set_system import loot
            inv = base.storage(self.state, self.holder)
            n = loot.deposit_materials(self.state, inv)
            base.save_storage(self.holder, inv)
            self.game.toast(f"Stored {n} materials." if n else "No materials to store.")
            self.refresh()
            return
        menu = self.mine if self.focus == 0 else self.store
        v = menu.handle(ev)
        if not v:
            return
        inv = base.storage(self.state, self.holder)
        p = self.state.player.inventory
        src, dst = (p, inv) if self.focus == 0 else (inv, p)
        qty = src.count(v) if pygame.key.get_mods() & pygame.KMOD_SHIFT else 1
        src.remove(v, qty)
        dst.add(v, qty)
        base.save_storage(self.holder, inv)
        self.refresh()

    def draw(self, screen):
        ui.dim(screen, 150)
        r = ui.panel(screen, (40, 40, W - 80, H - 80), self.title)
        for i, (label, x) in enumerate((("Your pack", 70), ("Storage", 690))):
            ui.text(screen, label, (x, 96), 28, ui.ACCENT if self.focus == i else ui.TEXT_DIM, bold=True)
        self.mine.draw(screen)
        self.store.draw(screen)
        ui.text(screen, "[Enter] move 1   [Shift+Enter] move all   [Q] store all materials   [Tab] switch   [Esc] close",
                (W // 2, r.bottom - 30), 21, ui.TEXT_DIM, center=True)


class ResearchScene(Scene):
    overlay = True

    def __init__(self, game):
        super().__init__(game)
        self.menu = ui.ListMenu([], (70, 130, 600, 400), 24)
        self.refresh()

    def refresh(self):
        st = self.state
        res = st.base.get("research", {})
        entries = []
        for pid, d in self.data.base["research"].items():
            r = res.get(pid)
            status = "done" if r and r["done"] else (f"{max(0, (r['ready_at'] - st.clock.total_minutes) // 60)} h left" if r else "")
            entries.append((d["name"], pid, not r, status))
        self.menu.set_entries(entries)

    def handle(self, ev):
        if is_close(ev):
            self.close()
            return
        v = self.menu.handle(ev)
        if v:
            ok, msg = base.start_research(self.state, v)
            self.game.notify(msg)
            self.refresh()

    def draw(self, screen):
        ui.dim(screen, 150)
        r = ui.panel(screen, (40, 40, W - 80, H - 80), "Research")
        self.menu.draw(screen)
        pid = self.menu.entries[self.menu.index][1] if self.menu.entries else None
        if pid:
            d = self.data.base["research"][pid]
            x = 720
            ui.text(screen, d["name"], (x, 130), 30, ui.ACCENT, bold=True)
            ui.text_block(screen, d["desc"], (x, 170, 480, 60), 22)
            ui.text(screen, "Needs:", (x, 240), 24, ui.ACCENT)
            y = 270
            inv = self.state.player.inventory
            for item, q in d["items"].items():
                have = inv.count(item) + base.storage(self.state, self.state.base).count(item)
                ui.text(screen, f"{self.data.item(item)['name']}  {have}/{q}", (x + 10, y), 22,
                        ui.TEXT if have >= q else ui.TEXT_BAD)
                y += 24
            ui.text(screen, f"Time: {d['hours']} hours (continues while you're away)", (x, y + 10), 22, ui.TEXT_DIM)
        ui.text(screen, "[Enter] start   [Esc] close", (W // 2, r.bottom - 30), 21, ui.TEXT_DIM, center=True)


class BaseScene(Scene):
    overlay = True

    def __init__(self, game, local=None):
        super().__init__(game)
        self.local = local
        self.menu = ui.ListMenu([], (70, 170, 520, 380), 24)
        self.refresh()

    def refresh(self):
        st = self.state
        entries = []
        for i, _ in enumerate(st.base.get("plots", [])):
            b = base.building_at(st, i)
            if not b:
                entries.append((f"Plot {i + 1}: empty", i, True, ""))
                continue
            name = self.data.base["buildings"][b["type"]]["name"]
            if not b["done"]:
                left = max(0, (b["ready_at"] - st.clock.total_minutes) / 60)
                status = f"building, {left:.0f} h"
            elif b.get("damaged"):
                status = "DAMAGED"
            elif b["type"] == "farm":
                c = b.get("crop")
                status = "empty field" if not c else ("ripe!" if st.clock.day_index >= c["ready_day"] else
                                                      f"growing ({c['ready_day'] - st.clock.day_index} d)")
            else:
                status = ", ".join(self.data.npcs[w]["name"].split()[0] for w in base.worker_at(st, i)) or "no worker"
            entries.append((f"Plot {i + 1}: {name}", i, True, status))
        self.menu.set_entries(entries)

    def on_resume(self):
        self.refresh()
        if self.local is not None:
            self.local.apply_base()

    def handle(self, ev):
        if is_close(ev):
            self.close()
            return
        st = self.state
        plot = self.menu.selected()
        if ev.type == pygame.KEYDOWN:
            k = ev.key
            if k == pygame.K_s:
                self.game.scenes.push(StorageScene(self.game, st.base, "Outpost storage"))
                return
            if k == pygame.K_t:
                self.game.scenes.push(ResearchScene(self.game))
                return
            if k == pygame.K_g:
                cands = [(self.data.npcs[c]["name"], c, True, st.companions[c]["task"]) for c in st.companions]
                self.game.scenes.push(ChoiceScene(self.game, "Who should guard the outpost?", cands,
                                                  lambda cid: self._msg(base.assign(st, cid, guard=True))))
                return
            if plot is None:
                return
            b = base.building_at(st, plot)
            if k in (pygame.K_RETURN, pygame.K_b) and not b:
                entries = []
                for bt, d in self.data.base["buildings"].items():
                    cost = f"{d['marks']}m + " + ", ".join(f"{q} {self.data.item(i)['name']}" for i, q in d["items"].items())
                    entries.append((d["name"], bt, True, cost if len(cost) < 48 else cost[:46] + ".."))
                self.game.scenes.push(ChoiceScene(self.game, f"Build on plot {plot + 1}", entries,
                                                  lambda bt: self._msg(base.build(st, plot, bt)),
                                                  body="Materials come from your pack and the outpost storage."))
                return
            if not b:
                return
            if k in (pygame.K_a, pygame.K_RETURN) and b["done"] and b["type"] not in ("palisade", "watchtower", "well"):
                cands = [(self.data.npcs[c]["name"], c, True, st.companions[c]["task"]) for c in st.companions]
                if not cands:
                    self.game.toast("You have no companions to assign.")
                    return
                self.game.scenes.push(ChoiceScene(self.game, f"Assign a worker to the {self.data.base['buildings'][b['type']]['name']}",
                                                  cands, lambda cid: self._msg(base.assign(st, cid, plot))))
                return
            if k == pygame.K_p and b["type"] == "farm":
                seeds = [(self.data.item(sd)["name"], sd) for sd in self.data.base["crops"]]
                self.game.scenes.push(ChoiceScene(self.game, "Plant what?", seeds, lambda sd: self._msg(base.plant(st, plot, sd))))
                return
            if k == pygame.K_h and b["type"] == "farm":
                self._msg(base.harvest(st, plot))
                return
            if k == pygame.K_r:
                self._msg(base.repair(st, plot))
                return
            if k == pygame.K_x:
                self.game.scenes.push(ConfirmScene(self.game, "Tear down?", "Demolish this building? Materials are lost.",
                                                   lambda: self._msg(base.demolish(st, plot))))
                return
        self.menu.handle(ev)

    def _msg(self, res):
        ok, msg = res
        self.game.notify(msg)
        self.refresh()
        if self.local is not None:
            self.local.apply_base()

    def draw(self, screen):
        st = self.state
        ui.dim(screen, 150)
        r = ui.panel(screen, (40, 40, W - 80, H - 80), "Outpost - Widow's Crossing")
        inv = base.storage(st, st.base)
        workers = base.workers(st)
        res_done = [self.data.base["research"][k]["name"] for k, v in st.base.get("research", {}).items() if v["done"]]
        info = [f"Defense {base.defense(st):.0f}   Workers/guards {len(workers)}/{base.capacity(st)}   "
                f"Stored items {sum(inv.items.values())}   Founded day {st.base['founded'] + 1}",
                "Research: " + (", ".join(res_done) or "none") + ("   RAID IN PROGRESS!" if st.base.get("raid") else "")]
        for i, l in enumerate(info):
            ui.text(screen, l, (70, 96 + i * 26), 22, ui.TEXT_BAD if "RAID" in l else ui.TEXT)
        ui.text(screen, "Plots", (70, 140), 26, ui.ACCENT, bold=True)
        self.menu.draw(screen)
        plot = self.menu.selected()
        x = 640
        b = base.building_at(st, plot) if plot is not None else None
        if b:
            d = self.data.base["buildings"][b["type"]]
            ui.text(screen, d["name"], (x, 170), 28, ui.ACCENT, bold=True)
            ui.text_block(screen, d["desc"], (x, 206, 560, 70), 22)
            ws = base.worker_at(st, plot)
            ui.text(screen, "Worker: " + (", ".join(self.data.npcs[w]["name"] for w in ws) or "none"), (x, 280), 22)
            keys = ["[A] assign worker", "[R] repair", "[X] demolish"]
            if b["type"] == "farm":
                keys = ["[P] plant", "[H] harvest"] + keys
            ui.text(screen, "   ".join(keys), (x, 312), 20, ui.TEXT_DIM)
        elif plot is not None:
            ui.text(screen, "Empty plot - press Enter to build.", (x, 170), 24, ui.TEXT_DIM)
        ui.text(screen, "Recent", (x, 360), 24, ui.ACCENT)
        y = 390
        for l in st.base.get("log", [])[-8:]:
            ui.text(screen, l[:80], (x, y), 20)
            y += 22
        ui.text(screen, "[Enter/B] build   [S] storage   [T] research   [G] assign a guard   [Esc] close",
                (W // 2, r.bottom - 30), 21, ui.TEXT_DIM, center=True)
