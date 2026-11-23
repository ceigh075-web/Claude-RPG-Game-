"""Spell book (inscribed spells + drafts), spell creation and editing - all usable anywhere, any time."""
import pygame

from ...core.scene import Scene
from ...set_system import spells
from ..ui import widgets as ui
from .common import ConfirmScene, is_close

W, H = 1280, 720


class SpellbookScene(Scene):
    overlay = True

    def __init__(self, game, at_table=False):
        super().__init__(game)
        self.at_table = at_table
        self.focus = 0  # 0 book, 1 drafts
        self.replace_for = None  # draft index waiting for a book slot to replace
        self.book = ui.ListMenu([], (70, 150, 520, 240), 24)
        self.drafts = ui.ListMenu([], (690, 150, 520, 240), 24)
        self.refresh()

    def refresh(self):
        st = self.state
        mag = st.player.skills["magic"]
        self.book.set_entries([(f"[{i + 1}] {s['name']}" if i < 4 else s["name"], i, True,
                                f"{spells.compute(self.data, s, mag)['mana']} mp") for i, s in enumerate(st.spellbook)])
        self.drafts.set_entries([(s["name"], i, True, f"{spells.compute(self.data, s, mag)['mana']} mp")
                                 for i, s in enumerate(st.spell_drafts)])

    def selected_spell(self):
        if self.focus == 0 and self.book.selected() is not None:
            return self.state.spellbook[self.book.selected()]
        if self.focus == 1 and self.drafts.selected() is not None:
            return self.state.spell_drafts[self.drafts.selected()]
        return None

    def handle(self, ev):
        st = self.state
        if is_close(ev) or (ev.type == pygame.KEYDOWN and ev.key == pygame.K_b):
            if self.replace_for is not None:
                self.replace_for = None
                return
            self.close()
            return
        if ev.type == pygame.KEYDOWN:
            k = ev.key
            if k in (pygame.K_TAB, pygame.K_LEFT, pygame.K_RIGHT):
                self.focus = 1 - self.focus
                return
            if k == pygame.K_n:
                self.game.scenes.push(SpellCraftScene(self.game, self))
                return
            if k == pygame.K_e:
                menu = self.book if self.focus == 0 else self.drafts
                i = menu.selected()
                if i is not None:
                    self.game.scenes.push(SpellCraftScene(self.game, self, edit=("book" if self.focus == 0 else "draft", i)))
                return
            if k == pygame.K_t:
                sp = self.selected_spell()
                if sp and self.state.mode == "local":
                    from .practice import PracticeScene
                    self.game.scenes.replace(PracticeScene(self.game, test_spell=sp))
                elif sp:
                    self.game.toast("You can only practise spells while exploring, not on the road.")
                return
            if k == pygame.K_x and self.focus == 1 and self.drafts.selected() is not None:
                i = self.drafts.selected()
                name = st.spell_drafts[i]["name"]
                del st.spell_drafts[i]
                self.game.toast(f"Discarded draft '{name}'.")
                self.refresh()
                return
            if k == pygame.K_u and self.focus == 0:
                i = self.book.selected()
                if i:
                    st.spellbook[i - 1], st.spellbook[i] = st.spellbook[i], st.spellbook[i - 1]
                    self.book.index = i - 1
                    self.refresh()
                return
        menu = self.book if self.focus == 0 else self.drafts
        v = menu.handle(ev)
        if v is None:
            return
        if self.replace_for is not None and self.focus == 0:
            d, self.replace_for = self.replace_for, None
            old = st.spellbook[v]["name"]
            self.game.scenes.push(ConfirmScene(self.game, "Replace spell?",
                f"Erase '{old}' and inscribe '{st.spell_drafts[d]['name']}' in its place?",
                lambda: self._inscribe(d, v)))
            return
        if self.focus == 1:
            cap = spells.capacity(self.data, st.player.level)
            if len(st.spellbook) >= cap:
                self.replace_for = v
                self.focus = 0
                self.game.toast(f"Spell book full ({cap}). Choose a spell to replace.")
                return
            self.game.scenes.push(ConfirmScene(self.game, "Inscribe?",
                f"Inscribe '{st.spell_drafts[v]['name']}' into your spell book? Inscribed spells go on the 1-4 hotbar.",
                lambda: self._inscribe(v, None)))

    def _inscribe(self, d, replace):
        ok, msg = spells.inscribe(self.state, d, replace, self.at_table)
        self.game.notify(msg)
        self.refresh()

    def draw(self, screen):
        st = self.state
        ui.dim(screen, 150)
        r = ui.panel(screen, (40, 40, W - 80, H - 80), "Spell Book")
        cap = spells.capacity(self.data, st.player.level)
        for i, (label, x) in enumerate(((f"Inscribed {len(st.spellbook)}/{cap}", 70),
                                        (f"Drafts {len(st.spell_drafts)}/{spells.MAX_DRAFTS}", 690))):
            ui.text(screen, label, (x, 110), 28, ui.ACCENT if self.focus == i else ui.TEXT_DIM, bold=True)
        self.book.draw(screen)
        self.drafts.draw(screen)
        if not st.spell_drafts:
            ui.text(screen, "No drafts. Press N to design a spell.", (690, 156), 22, ui.TEXT_DIM)
        sp = self.selected_spell()
        if sp:
            p = spells.compute(self.data, sp, st.player.skills["magic"])
            y = 410
            pygame.draw.line(screen, ui.BORDER, (70, y - 8), (W - 70, y - 8))
            ui.text(screen, p["name"], (70, y), 28, tuple(p["color"]), bold=True)
            ui.text(screen, f"Tier {p['tier']}  {self.data.magic['subelements'][p['sub']]['name']} / "
                            f"{self.data.magic['movements'][p['move']]['name']} / {self.data.magic['stats'][p['stat']]['name']}",
                    (70, y + 32), 22, ui.TEXT_DIM)
            ui.text_block(screen, p["description"], (70, y + 58, W - 160, 60), 22)
            stats = (f"Power {p['power']}   Mana {p['mana']}   Range {p['range']}   Area {p['area']}   "
                     f"Duration {p['duration']}s   Cooldown {p['cooldown']}s")
            ui.text(screen, stats, (70, y + 120), 22, ui.TEXT)
        if self.replace_for is not None:
            ui.text(screen, "Choose the spell to replace (Esc cancels)", (W // 2, r.bottom - 64), 24, ui.TEXT_BAD, center=True)
        ui.text(screen, "[N] new  [E] edit  [T] test  [Enter] inscribe draft  [X] discard  [U] move up  [Tab] switch  [Esc] close",
                (W // 2, r.bottom - 32), 21, ui.TEXT_DIM, center=True)


class SpellCraftScene(Scene):
    """Design (or edit) a spell: Element > optional Sub-element > Movement > Effect > Focus > Size > Tier.
    Free, possible anywhere; the live preview shows the mana cost and every number as you change things."""
    overlay = True
    FIELDS = ["Element", "Sub-element", "Movement", "Effect", "Focus", "Size", "Tier", "Name", "Save"]

    def __init__(self, game, book_scene, edit=None):
        super().__init__(game)
        self.book_scene = book_scene
        self.edit = edit            # ("book" | "draft", index) when rewriting an existing spell
        m = self.data.magic
        self.elements = list(m["elements"])
        self.moves = list(m["movements"])
        self.focuses = list(m["focuses"])
        self.el, self.sub, self.mv, self.eff, self.foc, self.tier = 0, 0, 0, 0, 0, 1
        self.size = 1.0
        self.field = 0
        self.custom_name = None
        if edit:
            sp = spells.normalize(self.data, (self.state.spellbook if edit[0] == "book" else self.state.spell_drafts)[edit[1]])
            self.el = self.elements.index(sp["element"])
            self.sub = (self.subs().index(sp["sub"]) + 1) if sp["sub"] else 0
            self.mv = self.moves.index(sp["move"])
            self.eff = self.effects().index(sp["stat"]) if sp["stat"] in self.effects() else 0
            self.foc = self.focuses.index(sp["focus"])
            self.size = sp["size"]
            self.tier = min(sp["tier"], self.max_tier())
            self.custom_name = sp["name"]

    def subs(self):
        return self.data.magic["elements"][self.elements[self.el]]["subs"]

    def sub_id(self):
        return self.subs()[self.sub - 1] if self.sub else None

    def effects(self):
        return spells.allowed_effects(self.data, self.elements[self.el], self.sub_id())

    def spell(self):
        eff = self.effects()[self.eff % len(self.effects())]
        sp = {"element": self.elements[self.el], "sub": self.sub_id(), "move": self.moves[self.mv], "stat": eff,
              "tier": self.tier, "focus": self.focuses[self.foc], "size": self.size}
        sp["name"] = self.custom_name or auto_name(self.data, sp)
        return sp

    def max_tier(self):
        lvl = self.state.player.level
        return max(int(t) for t, d in self.data.magic["tiers"].items() if d["level"] <= lvl)

    def handle(self, ev):
        if is_close(ev):
            self.close()
            return
        if ev.type != pygame.KEYDOWN:
            return
        k = ev.key
        if k in (pygame.K_UP,):
            self.field = (self.field - 1) % len(self.FIELDS)
            return
        if k in (pygame.K_DOWN, pygame.K_TAB):
            self.field = (self.field + 1) % len(self.FIELDS)
            return
        if self.field == 7:  # name typing
            if k == pygame.K_BACKSPACE:
                self.custom_name = (self.custom_name or self.spell()["name"])[:-1] or None
            elif k == pygame.K_RETURN:
                self.field = 8
            elif ev.unicode and ev.unicode.isprintable() and len(self.custom_name or "") < 24:
                self.custom_name = (self.custom_name or "") + ev.unicode
            return
        step = {pygame.K_LEFT: -1, pygame.K_a: -1, pygame.K_RIGHT: 1, pygame.K_d: 1}.get(k)
        if step:
            m = self.data.magic
            if self.field == 0:
                self.el = (self.el + step) % len(self.elements)
                self.sub = 0
                self.eff = 0
            elif self.field == 1:
                self.sub = (self.sub + step) % (len(self.subs()) + 1)
                self.eff = 0
            elif self.field == 2:
                self.mv = (self.mv + step) % len(self.moves)
            elif self.field == 3:
                self.eff = (self.eff + step) % len(self.effects())
            elif self.field == 4:
                self.foc = (self.foc + step) % len(self.focuses)
            elif self.field == 5:
                sz = m["sizes"]
                self.size = max(sz["min"], min(sz["max"], round(self.size + step * sz["step"], 2)))
            elif self.field == 6:
                self.tier = (self.tier - 1 + step) % self.max_tier() + 1
            return
        if k in (pygame.K_RETURN, pygame.K_SPACE) and self.field == 8:
            try:
                if self.edit:
                    ok, msg = spells.revise(self.state, self.edit[0], self.edit[1], self.spell())
                else:
                    ok, msg = spells.save_draft(self.state, self.spell())
            except spells.SpellError as e:
                ok, msg = False, str(e)
            self.game.notify(msg)
            if ok:
                self.book_scene.refresh()
                self.book_scene.focus = 0 if self.edit and self.edit[0] == "book" else 1
                self.close()

    def draw(self, screen):
        m = self.data.magic
        st = self.state
        ui.dim(screen, 120)
        r = ui.panel(screen, (60, 30, 1160, 660), "Edit Spell" if self.edit else "Design a Spell")
        sp = self.spell()
        el = m["elements"][sp["element"]]
        vals = [el["name"] + f"  ({el['identity']})",
                m["subelements"][sp["sub"]]["name"] if sp["sub"] else f"None - pure {el['name']}",
                m["movements"][sp["move"]]["name"], m["stats"][sp["stat"]]["name"],
                m["focuses"][sp["focus"]]["name"] + ("  *" if sp["focus"] == el["focus_affinity"] and sp["focus"] != "balanced" else ""),
                None, f"Tier {self.tier} (max {self.max_tier()})", sp["name"] + ("_" if self.field == 7 else ""),
                "Save changes" if self.edit else "Save as draft (free)"]
        y = r.y + 60
        for i, (f, v) in enumerate(zip(self.FIELDS, vals)):
            sel = i == self.field
            if sel:
                pygame.draw.rect(screen, ui.PANEL_LIGHT, (r.x + 20, y - 5, 520, 36), border_radius=4)
                pygame.draw.rect(screen, ui.BORDER_HI, (r.x + 20, y - 5, 520, 36), 1, border_radius=4)
            ui.text(screen, f, (r.x + 32, y), 23, ui.TEXT_DIM)
            if i == 5:     # size slider
                sz = m["sizes"]
                bx, bw = r.x + 170, 300
                frac = (self.size - sz["min"]) / (sz["max"] - sz["min"])
                pygame.draw.rect(screen, (30, 20, 12), (bx, y + 8, bw, 8), border_radius=4)
                pygame.draw.rect(screen, tuple(el["color"]), (bx, y + 8, int(bw * frac), 8), border_radius=4)
                kx = bx + int(bw * frac)
                pygame.draw.circle(screen, ui.BORDER_HI if sel else ui.BORDER, (kx, y + 12), 9)
                pygame.draw.circle(screen, (40, 26, 16), (kx, y + 12), 5)
                ui.text(screen, f"x{self.size:.2f}", (bx + bw + 14, y), 23, ui.ACCENT if sel else ui.TEXT)
            else:
                ui.text(screen, (f"<  {v}  >" if i < 7 else v), (r.x + 170, y), 23, ui.ACCENT if sel else ui.TEXT)
            y += 44
        # what the selected field means
        hint = {0: f"{el['desc']} Strengths: {el['strengths']}. Weaknesses: {el['weaknesses']}.",
                1: (m["subelements"][sp["sub"]]["note"] if sp["sub"] else
                    f"No sub-element: a pure {el['name']} spell with the element's own identity."),
                2: m["movements"][sp["move"]]["desc"], 3: m["stats"][sp["stat"]]["desc"],
                4: m["focuses"][sp["focus"]]["desc"] + (f"  ({el['name']} favours {m['focuses'][el['focus_affinity']]['name']}: +10%.)"),
                5: "Bigger spells cover more ground and hit a little harder, but cost much more mana.",
                6: "Higher tiers unlock as you level up: more power, more mana.", 7: "Type to rename.",
                8: "Spell creation is free and works anywhere."}[self.field]
        box = pygame.Rect(r.x + 20, y + 6, 520, r.bottom - y - 60)
        ui.parchment(screen, box)
        ui.ink_block(screen, hint, (box.x + 12, box.y + 10, box.w - 24, box.h - 16), 20, ui.INK)
        # live preview
        try:
            p = spells.compute(self.data, sp, st.player.skills["magic"])
        except spells.SpellError as e:
            ui.text_block(screen, str(e), (r.x + 580, r.y + 70, 540, 60), 22, ui.TEXT_BAD)
            return
        x = r.x + 580
        ui.text(screen, "Preview", (x, r.y + 60), 28, tuple(p["color"]), bold=True)
        # visual size preview: the spell's footprint drawn to scale
        cx, cy = x + 420, r.y + 150
        pygame.draw.circle(screen, (36, 24, 14), (cx, cy), 64)
        rad = max(3, min(62, int(p["area"] * 0.45 if p["area"] > 14 else p["radius"] * 2.5)))
        col = tuple(p["color"])
        pygame.draw.circle(screen, tuple(int(c * 0.5) for c in col), (cx, cy), rad)
        pygame.draw.circle(screen, col, (cx, cy), rad, 2)
        pygame.draw.circle(screen, ui.BORDER, (cx, cy), 64, 1)
        ui.text(screen, "footprint", (cx, cy + 68), 16, ui.TEXT_DIM, center=True)
        cost_col = ui.TEXT_GOOD if p["mana"] <= st.player.mana else ui.TEXT_BAD
        ui.text(screen, f"{p['mana']} mana", (x, r.y + 100), 34, cost_col, bold=True)
        ui.text(screen, f"you have {st.player.mana:.0f}/{st.player.max_mana}", (x, r.y + 138), 20, ui.TEXT_DIM)
        ui.text_block(screen, p["description"], (x, r.y + 230, 540, 90), 21)
        rows = [("Power", p["power"]), ("Range", p["range"]), ("Area", p["area"]), ("Speed", p["speed"]),
                ("Duration", f"{p['duration']}s"), ("Lasts (fields/traps)", f"{p['zone_duration']}s"),
                ("Recast", f"{p['cooldown']}s")]
        if p["move"] == "chain":
            rows.append(("Chain jumps", p["chain_jumps"]))
        if p["hp_cost"]:
            rows.append(("Health cost", p["hp_cost"]))
        yy = r.y + 330
        for k, v in rows:
            ui.text(screen, k, (x, yy), 22, ui.TEXT_DIM)
            ui.text(screen, str(v), (x + 230, yy), 22)
            yy += 26
        ui.text(screen, "Up/Down field   Left/Right change   type a name   Enter save   Esc back",
                (r.centerx, r.bottom - 32), 21, ui.TEXT_DIM, center=True)


MOVE_WORD = {"projectile": "Bolt", "homing": "Seeker", "beam": "Lance", "wave": "Wave", "area": "Blast",
             "ground": "Field", "orbit": "Halo", "ward": "Ward", "aura": "Mantle", "burst": "Nova", "chain": "Arc",
             "trap": "Snare", "barrier": "Wall", "self": "Blessing"}


def auto_name(data, sp):
    m = data.magic
    sp = spells.normalize(data, sp)
    stat_word = {"damage": "", "heal": "Mending ", "strength": "Mighty ", "speed": "Swift ", "dexterity": "Deft ",
                 "health": "Vital ", "defense": "Warding ", "knockback": "Hurling ", "root": "Binding ",
                 "affliction": "Cursed "}[sp["stat"]]
    tier = {1: "", 2: "Greater ", 3: "Grand "}[int(sp["tier"])]
    big = "Vast " if sp["size"] >= 2.25 else ("Wide " if sp["size"] >= 1.5 else ("Small " if sp["size"] <= 0.75 else ""))
    src = m["subelements"][sp["sub"]]["name"] if sp["sub"] else m["elements"][sp["element"]]["name"]
    return f"{tier}{big}{stat_word}{src} {MOVE_WORD.get(sp['move'], sp['move'].title())}"
