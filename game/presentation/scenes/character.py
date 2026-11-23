"""Character sheet: attributes, skills, needs and faction standing."""
import pygame

from ...core.scene import Scene
from ...set_system import factions, needs
from ...set_system.stats import ATTR_DESC, ATTRIBUTES, SKILLS
from .. import icons
from ..ui import widgets as ui
from .common import is_close
from .. import visuals

W, H = 1280, 720


class CharacterScene(Scene):
    overlay = True

    def handle(self, ev):
        if is_close(ev) or (ev.type == pygame.KEYDOWN and ev.key == pygame.K_c):
            self.close()

    def draw(self, screen):
        st = self.state
        p = st.player
        race = self.data.races[p.race]
        ui.dim(screen, 150)
        r = ui.panel(screen, (40, 40, W - 80, H - 80), f"{p.name} - {race['name']} ({p.pronouns})")
        # portrait
        spr = pygame.transform.scale(visuals.portrait(self.game.art, p.appearance, "down", 0), (99, 144))
        screen.blit(spr, (r.x + 30, r.y + 60))
        nxt = (p.level ** 2) * 40
        lines = [f"Level {p.level}", f"Experience {p.xp_total:.0f} / {nxt}", f"Max health {p.max_hp}",
                 f"Carry {p.carry_capacity:.0f} kg", f"Walk speed {p.move_speed():.0f}"]
        for i, l in enumerate(lines):
            ui.text(screen, l, (r.x + 140, r.y + 64 + i * 26), 24, ui.ACCENT if i == 0 else ui.TEXT)
        # attributes
        y = r.y + 230
        ui.text(screen, "Attributes", (r.x + 30, y), 28, ui.ACCENT)
        y += 34
        for a in ATTRIBUTES:
            base, eff = p.attributes[a], p.attr(a)
            ic = icons.named(icons.STAT_CELL, a)
            if ic is not None:
                screen.blit(ui.fit_icon(ic, 24), (r.x + 2, y - 2))
            ui.text(screen, a.title(), (r.x + 30, y), 24)
            ui.bar(screen, (r.x + 150, y + 2, 200, 16), base / 100, (170, 140, 90), f"{base:.1f}", 18)
            if abs(eff - base) > 0.05:
                ui.text(screen, f"({eff:.1f})", (r.x + 360, y), 22, ui.TEXT_BAD if eff < base else ui.TEXT_GOOD)
            ui.text(screen, ATTR_DESC[a], (r.x + 30, y + 22), 18, ui.TEXT_DIM)
            y += 50
        conds = needs.status(p)
        ui.text(screen, "Condition: " + (", ".join(c.title() for c in conds) if conds else "Fine"),
                (r.x + 30, y + 6), 22, ui.TEXT_BAD if conds else ui.TEXT_GOOD)
        # skills
        x = r.x + 470
        y = r.y + 60
        ui.text(screen, "Skills", (x, y), 28, ui.ACCENT)
        y += 34
        for s in SKILLS:
            v = p.skills[s]
            ic = icons.named(icons.STAT_CELL, s)
            if ic is not None:
                screen.blit(ui.fit_icon(ic, 22), (x - 26, y - 2))
            ui.text(screen, s.title(), (x, y), 22)
            ui.bar(screen, (x + 120, y + 2, 180, 14), v / 100, (110, 140, 180), f"{v:.1f}", 16)
            y += 26
        # factions
        x = r.x + 850
        y = r.y + 60
        ui.text(screen, "Factions", (x, y), 28, ui.ACCENT)
        y += 34
        for fid, f in self.data.factions.items():
            rep = st.reputation.get(fid, 0)
            col = ui.TEXT_GOOD if rep >= 10 else (ui.TEXT_BAD if rep <= -10 else ui.TEXT)
            ui.text(screen, f["name"], (x, y), 22)
            ui.text(screen, f"{rep:+d}  {factions.standing_label(rep)}", (x + 20, y + 20), 20, col)
            y += 48
        ui.text(screen, f"Days on the road: {st.stats.get('days', 0)}   Distance travelled: "
                        f"{st.stats.get('km_travelled', 0):.0f} km   Locations found: {len(st.discovered)}/29",
                (r.centerx, r.bottom - 34), 22, ui.TEXT_DIM, center=True)
