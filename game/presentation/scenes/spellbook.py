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
    """Design a spell from Element > Sub-element > Movement > Effect > Tier. Free; saves a draft."""
    overlay = True
    FIELDS = ["Element", "Sub-element", "Movement", "Effect", "Tier", "Name", "Save draft"]

    def __init__(self, game, book_scene, edit=None):
        super().__init__(game)
        self.book_scene = book_scene
        self.edit = edit            # ("book" | "draft", index) when rewriting an existing spell
        m = self.data.magic
        self.elements = list(m["elements"])
        self.moves = list(m["movements"])
        self.el, self.sub, self.mv, self.eff, self.tier = 0, 0, 0, 0, 1
        self.field = 0
        self.custom_name = None
        if edit:
            sp = (self.state.spellbook if edit[0] == "book" else self.state.spell_drafts)[edit[1]]
            el = m["subelements"][sp["sub"]]["element"]
            self.el = self.elements.index(el)
            self.sub = self.subs().index(sp["sub"])
            self.mv = self.moves.index(sp["move"])
            self.eff = self.effects().index(sp["stat"]) if sp["stat"] in self.effects() else 0
            self.tier = min(sp["tier"], self.max_tier())
            self.custom_name = sp["name"]

    def subs(self):
        return self.data.magic["elements"][self.elements[self.el]]["subs"]

    def effects(self):
        return self.data.magic["subelements"][self.subs()[self.sub]]["stats"]

    def spell(self):
        sub = self.subs()[self.sub]
        eff = self.effects()[self.eff % len(self.effects())]
        sp = {"sub": sub, "move": self.moves[self.mv], "stat": eff, "tier": self.tier}
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
        if self.field == 5:  # name typing
            if k == pygame.K_BACKSPACE:
                self.custom_name = (self.custom_name or self.spell()["name"])[:-1] or None
            elif k == pygame.K_RETURN:
                self.field = 6
            elif ev.unicode and ev.unicode.isprintable() and len(self.custom_name or "") < 22:
                self.custom_name = (self.custom_name or "") + ev.unicode
            return
        step = {pygame.K_LEFT: -1, pygame.K_a: -1, pygame.K_RIGHT: 1, pygame.K_d: 1}.get(k)
        if step:
            if self.field == 0:
                self.el = (self.el + step) % 4
                self.sub = 0
                self.eff = 0
            elif self.field == 1:
                self.sub = (self.sub + step) % 4
                self.eff = 0
            elif self.field == 2:
                self.mv = (self.mv + step) % len(self.moves)
            elif self.field == 3:
                self.eff = (self.eff + step) % len(self.effects())
            elif self.field == 4:
                self.tier = (self.tier - 1 + step) % self.max_tier() + 1
            return
        if k in (pygame.K_RETURN, pygame.K_SPACE) and self.field == 6:
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
        ui.dim(screen, 120)
        r = ui.panel(screen, (140, 60, 1000, 600), "Edit Spell" if self.edit else "Design a Spell")
        sp = self.spell()
        vals = [m["elements"][self.elements[self.el]]["name"], m["subelements"][sp["sub"]]["name"],
                m["movements"][sp["move"]]["name"], m["stats"][sp["stat"]]["name"], f"Tier {self.tier} (max {self.max_tier()})",
                sp["name"] + ("_" if self.field == 5 else ""), "Save changes" if self.edit else "Save as draft (free)"]
        y = r.y + 64
        for i, (f, v) in enumerate(zip(self.FIELDS, vals)):
            sel = i == self.field
            if sel:
                pygame.draw.rect(screen, ui.PANEL_LIGHT, (r.x + 24, y - 5, 460, 36), border_radius=4)
                pygame.draw.rect(screen, ui.BORDER_HI, (r.x + 24, y - 5, 460, 36), 1, border_radius=4)
            ui.text(screen, f, (r.x + 36, y), 24, ui.TEXT_DIM)
            ui.text(screen, (f"<  {v}  >" if i < 5 else v), (r.x + 190, y), 24, ui.ACCENT if sel else ui.TEXT)
            y += 46
        p = spells.compute(self.data, sp, self.state.player.skills["magic"])
        x = r.x + 520
        ui.text(screen, "Preview", (x, r.y + 64), 28, tuple(p["color"]), bold=True)
        ui.text_block(screen, m["subelements"][sp["sub"]]["note"], (x, r.y + 100, 440, 50), 22, ui.TEXT_DIM)
        ui.text_block(screen, p["description"], (x, r.y + 150, 440, 110), 22)
        rows = [("Mana", p["mana"]), ("Power", p["power"]), ("Range", p["range"]), ("Area", p["area"]),
                ("Speed", p["speed"]), ("Duration", f"{p['duration']}s"), ("Cooldown", f"{p['cooldown']}s")]
        if p["hp_cost"]:
            rows.append(("Health cost", p["hp_cost"]))
        yy = r.y + 270
        for k, v in rows:
            ui.text(screen, k, (x, yy), 22, ui.TEXT_DIM)
            ui.text(screen, str(v), (x + 200, yy), 22)
            yy += 26
        ui.text(screen, "Up/Down field   Left/Right change   type a name   Enter save   Esc back",
                (r.centerx, r.bottom - 32), 21, ui.TEXT_DIM, center=True)


def auto_name(data, sp):
    m = data.magic
    move_word = {"projectile": "Bolt", "homing": "Seeker", "beam": "Lance", "wave": "Nova", "area": "Burst",
                 "ground": "Field", "orbit": "Halo", "ward": "Ward", "aura": "Mantle"}[sp["move"]]
    stat_word = {"damage": "", "heal": "Mending ", "strength": "Mighty ", "speed": "Swift ", "dexterity": "Deft ",
                 "health": "Vital ", "defense": "Warding ", "knockback": "Hurling ", "root": "Binding ",
                 "affliction": "Cursed "}[sp["stat"]]
    tier = {1: "", 2: "Greater ", 3: "Grand "}[int(sp["tier"])]
    return f"{tier}{stat_word}{m['subelements'][sp['sub']]['name']} {move_word}"
