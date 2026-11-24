"""Drawing for combat: combatant poses (attack, block, dodge, hit, death), weapon swings, projectiles,
spell effects, floating numbers, particles, pickups, enemy health bars, and the combat HUD."""
import math

import pygame

from . import vfx, visuals
from ..set_system import combat as rules
from ..set_system import spells as spell_rules
from .ui import widgets as ui

WEAPON_COLOR = {"rustite": (176, 110, 70), "greyvein": (180, 186, 196), "sunsilver": (240, 220, 130),
                "voidglass": (150, 90, 220), None: (200, 200, 205)}


def sprite_entries(world, art, camx, camy, t):
    """(sort_y, image, x, y) tuples for combatants, to merge into the scene's depth-sorted draw list."""
    out = visuals.combatant_entries(world, art, camx, camy, t, getattr(world, "state", None))
    if out is not None:
        return out + pickup_entries(world, art, camx, camy, t)
    out = []
    for c in world.combatants:
        look = c.look
        frame = c.frame()
        acting = c.state in ("windup", "active", "draw", "cast") or c.blocking
        img = art.combatant(look, c.facing, frame, acting)
        w, h = img.get_size()
        x, y = c.x - w / 2 - camx, c.y - h + 1 - camy
        if c.state == "stagger":
            x += math.sin(t * 60) * 1.5
        if c.state == "dead":
            img = pygame.transform.rotate(img, 90 if c.facing != "left" else -90)
            img = img.copy()
            img.set_alpha(max(0, int(255 * (1 - c.dead_t / 1.6))))
            w, h = img.get_size()
            x, y = c.x - w / 2 - camx, c.y - h + 2 - camy
        elif c.state == "dodge":
            img = pygame.transform.scale(img, (w, int(h * 0.75)))
            y += h * 0.25
            ghost = img.copy()
            ghost.set_alpha(90)
            out.append((c.y - 1, ghost, int(x - c.dodge_vec[0] * 8), int(y - c.dodge_vec[1] * 8)))
        shadow = art.shadow(14 if w > 18 else 12)
        out.append((c.y - 0.5, shadow, int(c.x - shadow.get_width() / 2 - camx), int(c.y - 3 - camy)))
        out.append((c.y, img, int(x), int(y)))
        if c.flash > 0:
            out.append((c.y + 0.01, art.white(img), int(x), int(y)))
    return out + pickup_entries(world, art, camx, camy, t)


_TW = {}


def _twinkle(frame):
    s = _TW.get(frame)
    if s is None:
        import pygame
        s = pygame.Surface((7, 7), pygame.SRCALPHA)
        r = (1, 2, 3, 2)[min(3, frame)]
        for d in range(-r, r + 1):
            s.set_at((3 + d, 3), (255, 255, 230, 230 - abs(d) * 50))
            s.set_at((3, 3 + d), (255, 255, 230, 230 - abs(d) * 50))
        _TW[frame] = s
    return s


def pickup_entries(world, art, camx, camy, t):
    out = []
    from . import icons
    for c in world.combatants:              # a fallen foe still carrying gear: a loot bag floats over them
        if c.state == "dead" and getattr(c, "loot", None) and not getattr(c, "looted", False) and c.team != "npc":
            img = icons.icon(world.data, "marks" if all(e["item"] == "marks" for e in c.loot) else "sack_marker")
            bob = math.sin(t * 3 + c.x) * 2
            out.append((c.y + 0.02, img, int(c.x - 6 - camx), int(c.y - 30 + bob - camy)))
    for pk in world.pickups:
        img = icons.icon(world.data, pk["item"])
        z = pk.get("z", 0.0)
        settled = z <= 0 and not pk.get("vz")
        bob = math.sin(t * 3 + pk["x"]) * 1.0 if settled else 0.0
        w, h = img.get_size()
        sh = art.shadow(8)
        out.append((pk["y"] - 0.6, sh, int(pk["x"] - 4 - camx), int(pk["y"] - 2 - camy)))
        out.append((pk["y"], img, int(pk["x"] - w / 2 - camx), int(pk["y"] - h - z + bob - camy)))
        ph = (t * 1.3 + pk["x"] * 0.07) % 3.0
        if settled and ph < 0.3:                           # a brief twinkle so drops catch the eye
            out.append((pk["y"] + 0.01, _twinkle(int(ph * 10)), int(pk["x"] - 3 + w / 4 - camx),
                        int(pk["y"] - h - 2 + bob - camy)))
    return out


def _weapon_line(c):
    """Angle (radians) and length of the weapon for the current attack phase, or None."""
    p = c.profile
    if not p or c.state not in ("windup", "active", "recovery", "draw"):
        return None
    base = math.atan2(c.aim[1], c.aim[0])
    arc = math.radians(max(p["arc"], 20))
    length = min(p["reach"], 30) if p["class"] == "melee" else 10
    if p["weapon"] in ("fists", "knuckles", "kick"):
        length = 8
    if p["class"] == "ranged" or c.state == "draw":
        return base, length, 0.0
    if p["weapon"] in ("spear", "dagger") or p["arc"] <= 60:  # thrusting weapons extend instead of sweep
        ext = {"windup": 0.45, "active": 1.0, "recovery": 0.8}[c.state]
        return base, length * ext, 0.0
    side = 1 if c.combo % 2 else -1
    if c.state == "windup":
        a = base - side * arc / 2
        frac = 0.0
    elif c.state == "active":
        frac = min(1.0, c.state_t / max(0.01, p["active"]))
        a = base - side * arc / 2 + side * arc * frac
    else:
        a = base + side * arc / 2
        frac = 1.0
    return a, length, frac


def draw_under(canvas, world, camx, camy, t):
    """Ground-level combat visuals (spell zones, telegraphs, rune circles, shockwaves), drawn under sprites."""
    if visuals.enabled():
        vfx.update(world, t)
        vfx.draw_under(canvas, world, camx, camy, t)
    draw_telegraphs(canvas, world, camx, camy, t)


def draw_telegraphs(canvas, world, camx, camy, t):
    """Boss warning rings: an outline that fills in as the strike approaches (the edge flashes at the end)."""
    for tg in getattr(world, "telegraphs", []):
        x, y, r = int(tg["x"] - camx), int(tg["y"] - camy), int(tg["r"])
        f = min(1.0, tg["t"] / max(0.01, tg["delay"]))
        ring = pygame.Surface((r * 2 + 4, r + 4), pygame.SRCALPHA)
        rect = pygame.Rect(2, 2, r * 2, r)
        pygame.draw.ellipse(ring, (*tg["color"], int(40 + 90 * f)), rect.inflate(-int(r * 2 * (1 - f)), -int(r * (1 - f))))
        edge = (255, 240, 200) if f > 0.8 and int(t * 20) % 2 else tg["color"]
        pygame.draw.ellipse(ring, (*edge, 220), rect, 2)
        canvas.blit(ring, (x - r - 2, y - r // 2 - 2))


def draw_boss_bar(screen, world, W):
    """Top-of-screen health bar for an engaged boss, with phase notches."""
    for b in getattr(world, "bosses", []):
        c = b.c
        if not b.engaged or b.done or not c.alive:
            continue
        bw = 560
        x, y = W // 2 - bw // 2, 52
        ui.text(screen, b.name, (W // 2, y - 26), 26, (240, 180, 120), bold=True, center=True)
        pygame.draw.rect(screen, (20, 12, 10), (x - 3, y - 3, bw + 6, 22), border_radius=4)
        frac = max(0.0, c.hp / max(1.0, c.max_hp))
        pygame.draw.rect(screen, (90, 20, 20), (x, y, bw, 16), border_radius=3)
        pygame.draw.rect(screen, (220, 60, 46) if not b.enraged else (255, 120, 40), (x, y, int(bw * frac), 16),
                         border_radius=3)
        pygame.draw.rect(screen, (240, 200, 140), (x - 3, y - 3, bw + 6, 22), 2, border_radius=4)
        for ph in b.d["phases"]:
            px = x + int(bw * ph["at"])
            pygame.draw.line(screen, (250, 230, 190), (px, y - 2), (px, y + 17), 2)
        break


def vfx_lights(world):
    return vfx.lights(world) if visuals.enabled() else []


def draw_fx(canvas, world, art, camx, camy, t):
    new = visuals.enabled()
    if new:
        vfx.draw(canvas, world, camx, camy, t)
    # spell zones (under everything else)
    for e in ([] if new else world.effects):
        col = e.spell["color"]
        x, y = e.x - camx, e.y - camy
        if e.kind == "wave":
            r = min(e.spell["area"], e.t * max(60, e.spell["speed"]))
            pygame.draw.circle(canvas, col, (int(x), int(y)), int(r), 2)
        elif e.kind == "area":
            r = e.spell["area"]
            if e.t < 0.6:
                pygame.draw.circle(canvas, col, (int(x), int(y)), int(r * e.t / 0.6), 1)
                pygame.draw.circle(canvas, col, (int(x), int(y)), int(r), 1)
            else:
                _glow(canvas, x, y, r, col, 140)
        elif e.kind in ("ground", "ward", "aura"):
            r = e.spell["area"] if e.kind != "aura" else 34
            _glow(canvas, x, y + (6 if e.kind == "aura" else 0), r, col, 55 + int(25 * math.sin(t * 6)))
            if e.kind == "ward":
                pygame.draw.rect(canvas, col, (int(x) - 2, int(y) - 14, 4, 14))
        elif e.kind == "orbit":
            for k in range(3):
                a = e.t * 4 + k * math.tau / 3
                _glow(canvas, x + math.cos(a) * 24, y + math.sin(a) * 24, 5, col, 220)
        elif e.kind == "beam":
            ex, ey = e.end
            alpha = max(0, 1 - e.t / e.duration)
            pygame.draw.line(canvas, col, (x, y), (ex - camx, ey - camy), max(1, int(4 * alpha)))
            pygame.draw.line(canvas, (255, 255, 255), (x, y), (ex - camx, ey - camy), 1)
        elif e.kind == "aura_flash":
            _glow(canvas, x, y - 8, 10 + e.t * 40, col, int(180 * (1 - e.t / e.duration)))
    # weapon swings, blocks and telegraphs
    for c in world.combatants:
        if not c.alive:
            continue
        cx, cy = c.x - camx, c.y - 8 - camy
        wl = None if visuals.enabled() else _weapon_line(c)
        if wl:
            a, length, frac = wl
            ore = None
            item = getattr(c, "weapon_item", None)
            if item:
                ore = world.data.item(item).get("ore")
            col = WEAPON_COLOR.get(ore, (200, 200, 205)) if c.team == "player" else (150, 150, 150)
            ex, ey = cx + math.cos(a) * length, cy + math.sin(a) * length
            if c.profile["weapon"] in ("fists", "knuckles", "kick"):
                if c.state == "active":
                    pygame.draw.circle(canvas, (255, 240, 220), (int(cx + c.aim[0] * 12), int(cy + c.aim[1] * 12)), 3)
            elif c.profile["class"] == "ranged":
                pygame.draw.line(canvas, (120, 90, 60), (cx, cy), (ex, ey), 2)
                if c.state == "draw":
                    pull = min(1.0, c.charge / 0.9)
                    pygame.draw.circle(canvas, (255, 230, 150), (int(ex), int(ey)), 1 + int(pull * 2))
            else:
                pygame.draw.line(canvas, col, (cx, cy), (ex, ey), 2)
                if c.state == "active" and c.profile["arc"] > 60:
                    # slash trail
                    side = 1 if c.combo % 2 else -1
                    arc = math.radians(c.profile["arc"])
                    start = math.atan2(c.aim[1], c.aim[0]) - side * arc / 2
                    pts = [(cx, cy)]
                    for i in range(8):
                        aa = start + side * arc * frac * i / 7
                        pts.append((cx + math.cos(aa) * length, cy + math.sin(aa) * length))
                    if len(pts) > 2:
                        surf = pygame.Surface(canvas.get_size(), pygame.SRCALPHA)
                        pygame.draw.polygon(surf, (255, 255, 255, 70), pts)
                        canvas.blit(surf, (0, 0))
        if c.blocking:
            bx, by = cx + c.aim[0] * 9, cy + c.aim[1] * 9
            pygame.draw.arc(canvas, (170, 200, 255), (bx - 7, by - 7, 14, 14),
                            -math.atan2(c.aim[1], c.aim[0]) - 1.1, -math.atan2(c.aim[1], c.aim[0]) + 1.1, 2)
        if c.telegraph > 0 and c.team == "enemy" and c.state == "windup" and c.enemy["archetype"] in ("heavy", "intelligent"):
            ui.text(canvas, "!", (int(cx), int(cy - 24)), 18, (255, 90, 60), center=True)
        for s in ([] if new else c.statuses):
            if s["kind"] in ("dot", "slow", "root"):
                col = {"bleed": (200, 30, 40), "burn": (255, 140, 40), "poison": (110, 200, 60), "chill": (170, 220, 250),
                       "root": (90, 160, 70), "entangle": (90, 160, 70), "scald": (230, 230, 240)}.get(s["name"], (255, 255, 255))
                canvas.fill(col, (int(cx) - 1 + int(math.sin(t * 9 + c.cid) * 5), int(cy) - 14, 2, 2))
        if c.shield > 0 and not new:
            pygame.draw.circle(canvas, (150, 220, 230), (int(cx), int(cy + 2)), 11, 1)
    # projectiles
    for pr in ([] if new else world.projectiles):
        x, y = pr.x - camx, pr.y - camy
        dx, dy = rules_norm(pr.vx, pr.vy)
        if pr.kind == "spell":
            _glow(canvas, x, y, 6, pr.color, 160)
            pygame.draw.circle(canvas, (255, 255, 255), (int(x), int(y)), 2)
        elif pr.kind == "pellet":
            canvas.fill((255, 220, 140), (int(x), int(y), 2, 2))
        elif pr.kind == "knife":
            a = pr.t * 20
            pygame.draw.line(canvas, (210, 210, 220), (x - math.cos(a) * 3, y - math.sin(a) * 3), (x + math.cos(a) * 3, y + math.sin(a) * 3), 2)
        else:
            ln = 7 if pr.kind == "arrow" else 6
            pygame.draw.line(canvas, (120, 90, 60), (x - dx * ln, y - dy * ln), (x, y), 2 if pr.kind == "bolt" else 1)
            canvas.fill((220, 220, 230), (int(x), int(y), 2, 2))
    for p in ([] if new else world.particles):
        canvas.fill(p[5], (int(p[0] - camx), int(p[1] - camy), 2, 2))
    # enemy health bars
    for c in world.combatants:
        if c.team in ("enemy", "npc") and c.alive and (c.hp < c.max_hp or (c.alerted and c.team == "enemy")) \
                and not (c.enemy and c.enemy.get("boss")):
            w = 18 if c.max_hp < 120 else 26
            top = {"brute": 40, "worm": 30, "beast": 26, "bug": 20, "dummy": 30}.get(c.enemy["shape"], 30)
            if new and c.enemy["shape"] == "humanoid":
                top = 45                     # above a chibi head
            x, y = int(c.x - w / 2 - camx), int(c.y - top - camy)
            pygame.draw.rect(canvas, (20, 16, 20), (x - 1, y - 1, w + 2, 4))
            pygame.draw.rect(canvas, (200, 60, 50) if c.hostile else (200, 180, 80), (x, y, int(w * c.hp / c.max_hp), 2))
            if c.guard < rules.GUARD_MAX and c.blocking:
                pygame.draw.rect(canvas, (150, 180, 240), (x, y + 3, int(w * c.guard / rules.GUARD_MAX), 1))


def draw_floaters(screen, world, camx, camy, scale=2):
    """Damage numbers: pop in, drift up, fade. Big hits and backstabs ("!") are larger; labels are outlined."""
    fancy = visuals.enabled()
    for text, x, y, t, col in world.floaters:
        if t < 0:
            continue                      # staggered pop-ups wait their turn
        alpha = max(0.0, min(1.0, 1 - t / 0.9))
        rise = t * 20 if not fancy else 26 * (1 - (1 - min(1.0, t / 0.6)) ** 2)
        sx, sy = (x - camx) * scale, (y - camy - rise) * scale
        size = 22 if not text.endswith("!") else 28
        if fancy:
            try:
                n = float(text.rstrip("!"))
                size += min(10, int(n / 6))
            except ValueError:
                pass
            pop = 1.0 + max(0.0, 0.35 - t) * 1.6
            size = int(size * pop)
        c = tuple(int(v * (0.4 + 0.6 * alpha)) for v in col)
        if fancy:
            f = ui.font(size, True)
            img = f.render(text, True, c)
            out = f.render(text, True, (16, 10, 14))
            px, py = int(sx - img.get_width() / 2), int(sy)
            for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
                screen.blit(out, (px + dx, py + dy))
            screen.blit(img, (px, py))
        else:
            ui.text(screen, text, (int(sx), int(sy)), size, c, bold=True, center=True)
    if fancy:
        vfx.draw_screen(screen, world, screen.get_width(), screen.get_height())


def draw_combat_hud(screen, world, state, data, W, H, hotbar=None):
    p = state.player
    pc = world.player
    # guard
    if pc and pc.guard < rules.GUARD_MAX - 0.5:
        ui.bar(screen, (24, 121, 276, 6), pc.guard / rules.GUARD_MAX, (150, 180, 240))
    # weapon
    wt, item = world.player_weapon()
    name = data.item(item)["name"] if item else "Fists"
    ammo = data.weapons[wt].get("ammo")
    extra = ""
    if ammo == "self":
        extra = f"  x{p.inventory.count(item)}"
    elif ammo:
        extra = f"  {data.item(ammo)['name']}: {p.inventory.count(ammo)}"
    from . import icons
    r = ui.panel(screen, (W - 352, H - 128, 340, 116), alpha=200)
    wic = icons.ui_icon(data, item) if item else icons.named(icons.WEAPON_CELL, "knuckles")
    if wic is not None:
        screen.blit(ui.fit_icon(wic, 24), (r.x + 8, r.y + 4))
    ui.text(screen, f"{name}{extra}", (r.x + 36, r.y + 8), 22, ui.ACCENT)
    if p.equipment.get("ranged"):
        ui.text(screen, "[Q] switch", (r.right - 12, r.y + 8), 18, ui.TEXT_DIM, right=True)
    # spells
    for i, sp in enumerate((hotbar if hotbar is not None else state.spellbook)[:4]):
        props = spell_rules.compute(data, sp, p.skills["magic"])
        y = r.y + 34 + i * 20
        cd = world.spell_cd.get((pc.cid, sp["name"]), 0) if pc else 0
        short = p.mana < props["mana"]
        ok = not short and cd <= 0
        sic = icons.element_icon(data, sp)
        if sic is not None:
            ic = ui.fit_icon(sic, 18)
            if not ok:
                ic = ic.copy()
                ic.set_alpha(110)
            screen.blit(ic, (r.x + 10, y))
        ui.text(screen, f"[{i + 1}] {sp['name']}", (r.x + 32, y), 20, ui.TEXT if ok else ui.TEXT_DIM)
        tag = f"{props['mana']} mp"
        if cd > 0:
            tag += f"  {cd:.1f}s"
        elif short:
            tag = f"need {props['mana'] - p.mana:.0f} more"
        ui.text(screen, tag, (r.right - 12, y), 20,
                tuple(props["color"]) if ok else ((220, 120, 120) if short else ui.TEXT_DIM), right=True)
    if world.in_combat and not any(b.engaged and not b.done for b in getattr(world, "bosses", [])):
        ui.text(screen, "IN COMBAT", (W // 2, 14), 26, (240, 110, 90), bold=True, center=True)


def _glow(canvas, x, y, r, col, alpha):
    r = max(1, int(r))
    s = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
    pygame.draw.circle(s, col + (max(0, min(255, alpha)),), (r + 1, r + 1), r)
    canvas.blit(s, (int(x - r - 1), int(y - r - 1)))


def rules_norm(dx, dy):
    d = math.hypot(dx, dy) or 1.0
    return dx / d, dy / d
