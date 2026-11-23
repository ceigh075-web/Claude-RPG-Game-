"""Combat and spell visual effects.

A presentation-only layer. It *reads* the CombatWorld (projectiles, spell effects, combatant states and the
`vfx_events` notification queue) and keeps its own particles, using its own random generator so it can never
change gameplay outcomes.

Reusable building blocks:
  * ELEMENT  - one style record per sub-element (palette, particle kind, glyph, beam style, ground pattern)
  * glyph()  - draws a small element-specific shape (shard, bolt, flame, bubble, leaf, gem...) anywhere
  * Particle kinds (spark, ember, flake, bubble, drop, puff, shard, leaf, grain, ring, streak, star, glint,
    dust, debris, rune) shared by spells, weapons and statuses
  * movement renderers (projectile, homing, beam, wave, area, ground, orbit, ward, aura) that combine the two
"""
import math
import random
import weakref

import pygame

MAX_PARTICLES = 450
_rng = random.Random(7)
_glow_cache = {}
_circle_cache = {}


# ============================================================================ elements
def _c(*v):
    return tuple(max(0, min(255, int(x))) for x in v)


def _mix(a, b, f):
    return _c(*(a[i] + (b[i] - a[i]) * f for i in range(3)))


class Style:
    def __init__(self, core, bright, dark, particle, glyph, beam="line", ground="glow", glow=1.0, jag=0.0,
                 trail_rate=40, rise=0.0, gravity=0.0):
        self.core, self.bright, self.dark = core, bright, dark
        self.particle, self.glyph, self.beam, self.ground = particle, glyph, beam, ground
        self.glow, self.jag, self.trail_rate, self.rise, self.gravity = glow, jag, trail_rate, rise, gravity


ELEMENT = {
    # fire family
    "lightning": Style((250, 240, 120), (255, 255, 240), (120, 120, 230), "spark", "bolt", beam="lightning",
                       ground="arcs", glow=1.2, trail_rate=70),
    "plasma": Style((240, 120, 240), (255, 220, 255), (120, 40, 160), "glint", "orb", beam="pulse",
                    ground="glow", glow=1.4, trail_rate=50),
    "magma": Style((240, 100, 30), (255, 210, 90), (70, 30, 24), "ember", "rock", beam="molten", ground="lava",
                   glow=1.1, trail_rate=45, gravity=120),
    "ash": Style((140, 130, 128), (230, 120, 60), (60, 56, 56), "flake", "cinder", beam="smoke", ground="smoke",
                 glow=0.4, trail_rate=60, rise=-10),
    # water family
    "ice": Style((170, 220, 250), (245, 252, 255), (70, 120, 190), "shard", "shard", beam="shards", ground="frost",
                 glow=0.8, trail_rate=40, gravity=40),
    "steam": Style((220, 230, 235), (255, 255, 255), (150, 160, 170), "puff", "cloud", beam="mist",
                   ground="mist", glow=0.5, trail_rate=45, rise=-25),
    "blood": Style((180, 24, 44), (240, 90, 100), (70, 6, 18), "drop", "drop", beam="tendril", ground="pool",
                   glow=0.6, trail_rate=40, gravity=160),
    "poison": Style((110, 200, 60), (200, 250, 120), (40, 80, 30), "bubble", "glob", beam="drip", ground="bog",
                    glow=0.7, trail_rate=35, rise=-18),
    # earth family
    "metal": Style((176, 182, 194), (250, 250, 255), (80, 84, 96), "spark", "blade", beam="chain", ground="spikes",
                   glow=0.5, trail_rate=30),
    "crystal": Style((150, 230, 220), (240, 255, 255), (60, 130, 150), "glint", "gem", beam="prism",
                     ground="crystals", glow=1.0, trail_rate=35),
    "sand": Style((222, 200, 140), (250, 236, 190), (150, 120, 70), "grain", "swirl", beam="sandblast",
                  ground="dunes", glow=0.3, trail_rate=80),
    "nature": Style((80, 180, 70), (190, 240, 130), (40, 90, 40), "leaf", "leaf", beam="vine", ground="vines",
                    glow=0.6, trail_rate=30, gravity=30),
    # air family
    "wind": Style((210, 240, 230), (255, 255, 255), (130, 180, 170), "streak", "crescent", beam="gust",
                  ground="whirl", glow=0.4, trail_rate=50),
    "sound": Style((240, 200, 250), (255, 240, 255), (150, 100, 180), "ring", "arcs", beam="waves",
                   ground="pulse", glow=0.6, trail_rate=12),
    "gravity": Style((110, 80, 170), (200, 170, 255), (24, 12, 40), "void", "well", beam="distort",
                     ground="well", glow=0.9, trail_rate=45),
    "light": Style((255, 250, 200), (255, 255, 255), (230, 190, 90), "glint", "star", beam="radiant",
                   ground="halo", glow=1.5, trail_rate=40, rise=-15),
    # pure-element spells (no sub-element) and the light family's new sub-elements
    "fire": Style((240, 120, 40), (255, 220, 120), (120, 40, 20), "ember", "cinder", beam="molten", ground="lava",
                  glow=1.3, trail_rate=55, rise=-20),
    "water": Style((70, 150, 230), (200, 235, 255), (30, 70, 140), "drop", "drop", beam="tendril", ground="pool",
                   glow=0.6, trail_rate=45, gravity=120),
    "earth": Style((150, 116, 70), (210, 180, 120), (80, 60, 36), "grain", "rock", beam="spikes", ground="spikes",
                   glow=0.3, trail_rate=40, gravity=80),
    "air": Style((215, 238, 240), (255, 255, 255), (140, 190, 200), "streak", "crescent", beam="gust", ground="whirl",
                 glow=0.4, trail_rate=60),
    "mending": Style((255, 214, 150), (255, 250, 220), (220, 160, 80), "glint", "star", beam="radiant", ground="pulse",
                     glow=1.4, trail_rate=45, rise=-25),
    "sanctuary": Style((228, 234, 255), (255, 255, 255), (150, 160, 210), "ring", "gem", beam="prism", ground="halo",
                       glow=1.1, trail_rate=25),
}
DEFAULT = ELEMENT["light"]


def style(sub):
    st = ELEMENT.get(sub)
    if st is None and sub and "#" in sub:
        st = ELEMENT[sub] = _variant(sub)
    return st or DEFAULT


def _variant(key):
    """A designer colour / intensity variant of an element style ('fire#2#1.25')."""
    import copy
    from ..set_system.spells import variant_color
    base, hue, inten = key.split("#")
    hue, inten = int(hue), float(inten)
    st = copy.copy(ELEMENT.get(base, DEFAULT))
    for attr in ("core", "bright", "dark"):
        v = getattr(st, attr, None)
        if isinstance(v, tuple) and len(v) == 3:
            setattr(st, attr, variant_color(v, hue))
    for attr in ("glow", "trail_rate"):
        v = getattr(st, attr, None)
        if isinstance(v, (int, float)):
            setattr(st, attr, v * inten)
    return st


# ============================================================================ primitives
def glow(r, col):
    """Cached additive radial glow."""
    r = max(2, int(r))
    key = (r, col)
    g = _glow_cache.get(key)
    if g is None:
        g = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        for i in range(r, 0, -1):
            f = (1 - i / r) ** 1.6
            pygame.draw.circle(g, (*_c(*(v * f for v in col)), 255), (r, r), i)
        if len(_glow_cache) > 400:
            _glow_cache.clear()
        _glow_cache[key] = g
    return g


def add_glow(canvas, x, y, r, col, strength=1.0):
    if strength <= 0.02:
        return
    c = col if strength >= 1 else _c(*(v * strength for v in col))
    g = glow(r, c)
    canvas.blit(g, (int(x - r), int(y - r)), special_flags=pygame.BLEND_RGB_ADD)


def disc(r, col, alpha):
    """Cached translucent circle."""
    r = max(1, int(r))
    a = max(0, min(255, int(alpha) // 16 * 16))
    key = (r, col, a)
    s = _circle_cache.get(key)
    if s is None:
        s = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*col, a), (r, r), r)
        if len(_circle_cache) > 600:
            _circle_cache.clear()
        _circle_cache[key] = s
    return s


def ellipse_alpha(canvas, rect, col, alpha, width=0):
    x, y, w, h = [int(v) for v in rect]
    if w <= 1 or h <= 1:
        return
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.ellipse(s, (*col, max(0, min(255, int(alpha)))), (0, 0, w, h), width)
    canvas.blit(s, (x, y))


def _rot(px, py, a):
    ca, sa = math.cos(a), math.sin(a)
    return px * ca - py * sa, px * sa + py * ca


def _poly(canvas, col, x, y, pts, a, width=0):
    q = [(x + rx, y + ry) for rx, ry in (_rot(px, py, a) for px, py in pts)]
    pygame.draw.polygon(canvas, col, q, width)


def jagged(x0, y0, x1, y1, amp, rng, segs=None):
    d = math.hypot(x1 - x0, y1 - y0)
    n = segs or max(2, int(d / 7))
    nx, ny = (-(y1 - y0) / d, (x1 - x0) / d) if d else (0, 0)
    pts = [(x0, y0)]
    for i in range(1, n):
        f = i / n
        o = rng.uniform(-amp, amp) * math.sin(f * math.pi) ** 0.5
        pts.append((x0 + (x1 - x0) * f + nx * o, y0 + (y1 - y0) * f + ny * o))
    pts.append((x1, y1))
    return pts


# ============================================================================ glyphs
def glyph(canvas, sub, x, y, size, ang, t, alpha=1.0):
    """Draw an element-identifying shape. size ~ radius in px, ang = travel direction (radians)."""
    st = style(sub)
    g = st.glyph
    s = max(1.0, size)
    core, bright, dark = st.core, st.bright, st.dark
    if g == "bolt":
        r = random.Random(int(t * 30) + int(x) * 7)
        for k in range(3):
            a = ang + math.pi + r.uniform(-0.9, 0.9)
            pts = jagged(x, y, x + math.cos(a) * s * 2.2, y + math.sin(a) * s * 2.2, s * 0.6, r, 3)
            pygame.draw.lines(canvas, core, False, pts, 1)
        pygame.draw.circle(canvas, bright, (int(x), int(y)), max(1, int(s * 0.6)))
    elif g == "orb":
        pul = 1 + 0.25 * math.sin(t * 18)
        pygame.draw.circle(canvas, dark, (int(x), int(y)), max(1, int(s * pul)))
        pygame.draw.circle(canvas, core, (int(x), int(y)), max(1, int(s * 0.75 * pul)))
        pygame.draw.circle(canvas, bright, (int(x), int(y)), max(1, int(s * 0.35)))
        for k in range(2):
            a = t * 9 + k * math.pi
            canvas.fill(bright, (int(x + math.cos(a) * s * 1.4), int(y + math.sin(a) * s * 0.8), 2, 2))
    elif g == "rock":
        pts = [(s, 0), (s * 0.4, s * 0.9), (-s * 0.7, s * 0.7), (-s, -0.1 * s), (-s * 0.3, -s), (s * 0.6, -s * 0.7)]
        _poly(canvas, dark, x, y, pts, t * 6)
        _poly(canvas, (20, 10, 10), x, y, pts, t * 6, 1)
        for k in range(3):
            a = t * 6 + k * 2.1
            pygame.draw.line(canvas, core, (x, y), (x + math.cos(a) * s * 0.8, y + math.sin(a) * s * 0.8), 1)
        canvas.fill(bright, (int(x), int(y), 1, 1))
    elif g == "cinder":
        r = random.Random(int(x * 3 + y))
        for k in range(6):
            a = t * 4 + k * 1.05
            rr = s * (0.5 + 0.5 * ((k * 37) % 5) / 5)
            col = dark if k % 3 else core
            canvas.fill(col, (int(x + math.cos(a) * rr), int(y + math.sin(a) * rr), 2, 2))
        canvas.fill(st.bright, (int(x + r.uniform(-s, s) / 2), int(y + r.uniform(-s, s) / 2), 1, 1))
    elif g == "shard":
        pts = [(s * 2.0, 0), (0, s * 0.55), (-s * 1.2, 0), (0, -s * 0.55)]
        _poly(canvas, core, x, y, pts, ang)
        _poly(canvas, bright, x, y, [(s * 2.0, 0), (0, -s * 0.55), (-s * 0.2, 0)], ang)
        _poly(canvas, dark, x, y, pts, ang, 1)
    elif g == "cloud":
        for k in range(4):
            a = t * 3 + k * 1.57
            rr = s * 0.7
            canvas.blit(disc(s * 0.75, core, 150 * alpha), (int(x + math.cos(a) * rr - s * 0.75), int(y + math.sin(a) * rr * 0.6 - s * 0.75)))
        canvas.blit(disc(s * 0.6, bright, 200 * alpha), (int(x - s * 0.6), int(y - s * 0.6)))
    elif g == "drop":
        pts = [(s * 1.6, 0), (s * 0.2, s * 0.8), (-s * 0.9, s * 0.3), (-s * 0.9, -s * 0.3), (s * 0.2, -s * 0.8)]
        _poly(canvas, core, x, y, [(-px, py) for px, py in pts], ang)
        canvas.fill(bright, (int(x - math.cos(ang) * s * 0.3), int(y - math.sin(ang) * s * 0.3) - 1, 2, 1))
    elif g == "glob":
        wob = math.sin(t * 14) * s * 0.15
        pygame.draw.ellipse(canvas, dark, (x - s - wob, y - s + wob, (s + wob) * 2, (s - wob) * 2))
        pygame.draw.ellipse(canvas, core, (x - s * 0.8, y - s * 0.8, s * 1.6, s * 1.4))
        pygame.draw.circle(canvas, bright, (int(x - s * 0.3), int(y - s * 0.3)), max(1, int(s * 0.25)))
    elif g == "blade":
        spin = t * 22
        for k in range(3):
            a = spin + k * math.tau / 3
            _poly(canvas, core, x, y, [(0, 0), (s * 1.4, -s * 0.25), (s * 1.1, s * 0.35)], a)
        pygame.draw.circle(canvas, dark, (int(x), int(y)), max(1, int(s * 0.4)))
        canvas.fill(bright, (int(x + math.cos(spin) * s), int(y + math.sin(spin) * s), 1, 1))
    elif g == "gem":
        pts = [(math.cos(a) * s, math.sin(a) * s * 1.2) for a in [k * math.tau / 6 + math.pi / 6 for k in range(6)]]
        _poly(canvas, core, x, y, pts, 0)
        _poly(canvas, bright, x, y, [pts[4], pts[5], (0, 0)], 0)
        _poly(canvas, dark, x, y, [pts[1], pts[2], (0, 0)], 0)
        _poly(canvas, dark, x, y, pts, 0, 1)
        if int(t * 8) % 3 == 0:
            canvas.fill((255, 255, 255), (int(x + s * 0.3), int(y - s * 0.6), 1, 1))
    elif g == "swirl":
        for k in range(10):
            a = t * 10 + k * 0.63
            rr = s * (0.3 + 0.07 * k)
            canvas.fill(core if k % 2 else dark, (int(x + math.cos(a) * rr), int(y + math.sin(a) * rr * 0.7), 1, 1))
    elif g == "leaf":
        a = ang + math.sin(t * 10) * 0.4
        _poly(canvas, core, x, y, [(s * 1.4, 0), (0, s * 0.6), (-s * 0.9, 0), (0, -s * 0.6)], a)
        pygame.draw.line(canvas, dark, (x - math.cos(a) * s * 0.9, y - math.sin(a) * s * 0.9),
                         (x + math.cos(a) * s * 1.3, y + math.sin(a) * s * 1.3), 1)
        for k in (-1, 1):
            canvas.fill(st.bright, (int(x + math.cos(a + k * 2.3) * s * 1.3), int(y + math.sin(a + k * 2.3) * s * 1.3), 1, 1))
    elif g == "crescent":
        rect = (x - s * 1.4, y - s * 1.4, s * 2.8, s * 2.8)
        for w, col, off in ((2, core, 0), (1, bright, 0.25)):
            pygame.draw.arc(canvas, col, rect, -ang - 1.1 + off, -ang + 1.1 - off, w)
        for k in (-1, 1):
            a = ang + math.pi + k * 0.3
            pygame.draw.line(canvas, st.dark, (x + math.cos(a) * s, y + math.sin(a) * s),
                             (x + math.cos(a) * s * 2.6, y + math.sin(a) * s * 2.6), 1)
    elif g == "arcs":
        for k in range(3):
            rr = s * (0.6 + k * 0.55) + (t * 20 % 3)
            rect = (x - rr, y - rr, rr * 2, rr * 2)
            pygame.draw.arc(canvas, core if k else bright, rect, -ang - 0.8, -ang + 0.8, 1)
    elif g == "well":
        pygame.draw.circle(canvas, dark, (int(x), int(y)), max(1, int(s)))
        pygame.draw.circle(canvas, core, (int(x), int(y)), max(2, int(s * 1.25)), 1)
        for k in range(4):
            a = -t * 8 + k * math.pi / 2
            rr = s * (1.9 - (t * 3 + k * 0.25) % 1.0)
            canvas.fill(st.bright, (int(x + math.cos(a) * rr), int(y + math.sin(a) * rr), 1, 1))
    elif g == "star":
        L = s * (1.6 + 0.3 * math.sin(t * 20))
        pygame.draw.line(canvas, core, (x - L, y), (x + L, y), 1)
        pygame.draw.line(canvas, core, (x, y - L), (x, y + L), 1)
        d = L * 0.55
        pygame.draw.line(canvas, st.dark, (x - d, y - d), (x + d, y + d), 1)
        pygame.draw.line(canvas, st.dark, (x - d, y + d), (x + d, y - d), 1)
        pygame.draw.circle(canvas, bright, (int(x), int(y)), max(1, int(s * 0.55)))
    else:
        pygame.draw.circle(canvas, core, (int(x), int(y)), max(1, int(s)))


# ============================================================================ particles
class P:
    __slots__ = ("x", "y", "vx", "vy", "life", "max", "kind", "col", "size", "a", "floor", "drag")

    def __init__(self, x, y, vx, vy, life, kind, col, size=1.0, a=0.0, floor=None, drag=0.0):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.life = self.max = life
        self.kind, self.col, self.size, self.a, self.floor, self.drag = kind, col, size, a, floor, drag


GRAV = {"drop": 260, "debris": 300, "ember": -40, "flake": 18, "bubble": -26, "leaf": 25, "puff": -12,
        "dust": -6, "grain": 60, "shard": 120, "spark": 80, "smoke": -20}


def _draw_particle(canvas, p, camx, camy):
    x, y = p.x - camx, p.y - camy
    f = p.life / p.max
    k = p.kind
    col = p.col
    if k == "spark":
        L = max(1.5, math.hypot(p.vx, p.vy) * 0.03)
        n = math.hypot(p.vx, p.vy) or 1
        pygame.draw.line(canvas, col, (x, y), (x - p.vx / n * L, y - p.vy / n * L), 1)
    elif k == "streak":
        n = math.hypot(p.vx, p.vy) or 1
        L = 3 + 5 * f
        pygame.draw.line(canvas, col, (x, y), (x - p.vx / n * L, y - p.vy / n * L), 1)
    elif k == "ember":
        s = 2 if f > 0.5 else 1
        canvas.fill(col if f > 0.4 else _mix(col, (60, 30, 20), 1 - f), (int(x), int(y), s, s))
    elif k in ("puff", "dust", "smoke"):
        r = p.size * (1.6 - f)
        canvas.blit(disc(r, col, 170 * f), (int(x - r), int(y - r)))
    elif k == "bubble":
        r = max(1, int(p.size * (1.2 - 0.4 * f)))
        if f < 0.12:
            canvas.fill(col, (int(x) - r, int(y), 1, 1))
            canvas.fill(col, (int(x) + r, int(y), 1, 1))
        else:
            pygame.draw.circle(canvas, col, (int(x), int(y)), r, 1)
            canvas.fill((255, 255, 255), (int(x) - 1, int(y) - 1, 1, 1))
    elif k in ("shard", "debris"):
        s = max(1.0, p.size)
        _poly(canvas, col, x, y, [(s * 1.4, 0), (0, s * 0.6), (-s, 0), (0, -s * 0.6)], p.a)
    elif k == "leaf":
        _poly(canvas, col, x, y, [(2, 0), (0, 1), (-2, 0), (0, -1)], p.a)
    elif k == "flake":
        canvas.fill(col, (int(x), int(y), 1, 1))
        if p.size > 1:
            canvas.fill(_mix(col, (0, 0, 0), 0.3), (int(x) + 1, int(y), 1, 1))
    elif k == "ring":
        r = int(p.size * (1 - f) + 2)
        pygame.draw.circle(canvas, col, (int(x), int(y)), r, 1)
    elif k == "star":
        a = p.a
        for j in range(3):
            aa = a + j * math.tau / 3
            canvas.fill(col, (int(x + math.cos(aa) * 6), int(y + math.sin(aa) * 2), 2, 2))
    elif k == "glint":
        L = 1 + int(2 * math.sin(f * math.pi))
        pygame.draw.line(canvas, col, (x - L, y), (x + L, y))
        pygame.draw.line(canvas, col, (x, y - L), (x, y + L))
    elif k == "rune":
        r = p.size * (0.6 + 0.4 * (1 - f))
        ellipse_alpha(canvas, (x - r, y - r * 0.45, r * 2, r * 0.9), col, 220 * f, 1)
        for j in range(6):
            aa = p.a + j * math.tau / 6
            canvas.fill(col, (int(x + math.cos(aa) * r * 0.8), int(y + math.sin(aa) * r * 0.36), 1, 1))
    elif k == "void":
        canvas.fill(col, (int(x), int(y), 2, 2))
    elif k == "drop":
        canvas.fill(col, (int(x), int(y), 1, 2))
    elif k == "grain":
        canvas.fill(col, (int(x), int(y), 1, 1))
    elif k == "slash":
        # a bright cut line that shrinks to nothing
        L = p.size * f
        ca, sa = math.cos(p.a), math.sin(p.a)
        pygame.draw.line(canvas, (255, 255, 255), (x - ca * L, y - sa * L), (x + ca * L, y + sa * L), 2 if f > 0.5 else 1)
        pygame.draw.line(canvas, col, (x - ca * L * 1.2, y - sa * L * 1.2 + 1), (x + ca * L * 1.2, y + sa * L * 1.2 + 1), 1)
    elif k == "shock":
        r = p.size * (1 - f) + 3
        ellipse_alpha(canvas, (x - r, y - r * 0.5, r * 2, r), col, 255 * f, 2 if f > 0.5 else 1)
    else:
        canvas.fill(col, (int(x), int(y), 1, 1))


# ============================================================================ per-world state
class FXState:
    def __init__(self):
        self.parts = []
        self.last_t = None
        self.seen_proj = {}      # projectile -> (x, y, sub/kind)
        self.seen_eff = {}       # effect -> flags
        self.cast_sub = {}       # combatant -> (sub, time)
        self.hurt = 0.0
        self.time = 0.0
        self.emit_acc = {}

    def add(self, p):
        if len(self.parts) < MAX_PARTICLES:
            self.parts.append(p)


_states = weakref.WeakKeyDictionary()


def state_for(world):
    s = _states.get(world)
    if s is None:
        s = FXState()
        _states[world] = s
    return s


def _emit(fx, key, rate, dt):
    """How many particles to emit this frame for a continuous source (rate per second)."""
    acc = fx.emit_acc.get(key, 0.0) + rate * dt
    n = int(acc)
    fx.emit_acc[key] = acc - n
    return n


def element_particle(fx, sub, x, y, spread=3, speed=20, n=1, life=(0.3, 0.6), vx0=0.0, vy0=0.0):
    st = style(sub)
    for _ in range(n):
        a = _rng.uniform(0, math.tau)
        sp = _rng.uniform(0.3, 1.0) * speed
        col = _rng.choice((st.core, st.core, st.bright, st.dark))
        kind = st.particle
        size = 1.0
        if kind == "puff":
            size = _rng.uniform(2, 4)
        elif kind in ("shard",):
            size = _rng.uniform(1, 1.8)
        elif kind == "ring":
            size = _rng.uniform(6, 10)
        elif kind == "void":
            # gravity particles fall *inward*
            r = _rng.uniform(6, 12)
            px, py = x + math.cos(a) * r, y + math.sin(a) * r
            fx.add(P(px, py, -math.cos(a) * r * 3, -math.sin(a) * r * 3, 0.3, "void", col))
            continue
        if kind == "flake":
            col = _rng.choice((st.core, st.dark, st.dark, st.bright))
        fx.add(P(x + _rng.uniform(-spread, spread), y + _rng.uniform(-spread, spread),
                 vx0 + math.cos(a) * sp, vy0 + math.sin(a) * sp + st.rise, _rng.uniform(*life), kind, col, size,
                 a=_rng.uniform(0, math.tau), drag=1.5))


def burst(fx, sub, x, y, n=14, speed=70, ring=True, flash=True):
    """Element impact: particles, flash, and an element-shaped signature."""
    st = style(sub)
    element_particle(fx, sub, x, y, 2, speed, n, (0.25, 0.6))
    for _ in range(n // 3):
        a = _rng.uniform(0, math.tau)
        sp = _rng.uniform(40, speed * 1.3)
        fx.add(P(x, y, math.cos(a) * sp, math.sin(a) * sp, _rng.uniform(0.15, 0.3), "spark", st.bright))
    if ring and st.glyph not in ("arcs",):
        fx.add(P(x, y, 0, 0, 0.3, "ring", st.core, size=12))
    if flash:
        fx.add(P(x, y, 0, 0, 0.16, "flash", st.core, size=8 * min(1.2, st.glow + 0.3)))
    g = st.glyph
    if g in ("shard", "gem"):           # crystalline fragments fly out
        for k in range(6):
            a = k * math.tau / 6 + _rng.uniform(-0.2, 0.2)
            fx.add(P(x, y, math.cos(a) * 90, math.sin(a) * 90 - 20, 0.45, "shard", st.core, 1.6, a=a, drag=3))
    elif g == "bolt":
        fx.add(P(x, y, 0, 0, 0.2, "zap", st.core, size=18))
    elif g == "rock":
        for k in range(6):
            a = _rng.uniform(math.pi, math.tau)
            fx.add(P(x, y, math.cos(a) * 70, math.sin(a) * 90, 0.6, "debris", st.dark, 1.5, a=a, floor=y + 8))
            fx.add(P(x, y, math.cos(a) * 50, math.sin(a) * 60, 0.7, "ember", st.core))
    elif g in ("cloud", "cinder"):
        for k in range(6):
            a = _rng.uniform(0, math.tau)
            fx.add(P(x, y, math.cos(a) * 30, math.sin(a) * 20, 0.6, "puff", st.core, 4))
    elif g == "drop":
        for k in range(8):
            a = _rng.uniform(math.pi * 1.1, math.pi * 1.9)
            fx.add(P(x, y, math.cos(a) * 60, math.sin(a) * 80, 0.6, "drop", st.core, floor=y + 10))
    elif g == "glob":
        for k in range(6):
            fx.add(P(x + _rng.uniform(-6, 6), y + _rng.uniform(-3, 3), 0, -15, 0.7, "bubble", st.core, 2))
    elif g == "blade":
        for k in range(10):
            a = _rng.uniform(0, math.tau)
            fx.add(P(x, y, math.cos(a) * 120, math.sin(a) * 120, 0.2, "spark", (255, 240, 200)))
    elif g == "swirl":
        for k in range(18):
            a = _rng.uniform(0, math.tau)
            fx.add(P(x, y, math.cos(a) * 80, math.sin(a) * 40, 0.5, "grain", st.core, drag=2.5))
    elif g == "leaf":
        for k in range(7):
            a = _rng.uniform(0, math.tau)
            fx.add(P(x, y, math.cos(a) * 50, math.sin(a) * 40 - 20, 0.9, "leaf", _rng.choice((st.core, st.bright)), a=a, drag=2))
    elif g == "crescent":
        for k in range(8):
            a = k * math.tau / 8
            fx.add(P(x, y, math.cos(a) * 110, math.sin(a) * 60, 0.3, "streak", st.core, drag=3))
    elif g == "arcs":
        for k in range(3):
            fx.add(P(x, y, 0, 0, 0.25 + k * 0.12, "ring", st.core, size=12 + k * 8))
    elif g == "well":
        for k in range(14):
            a = _rng.uniform(0, math.tau)
            r = _rng.uniform(14, 22)
            fx.add(P(x + math.cos(a) * r, y + math.sin(a) * r, -math.cos(a) * r * 3, -math.sin(a) * r * 3, 0.3, "void", st.bright))
    elif g == "star":
        for k in range(8):
            a = k * math.tau / 8
            fx.add(P(x, y, math.cos(a) * 60, math.sin(a) * 60, 0.4, "glint", st.bright, drag=3))


# ============================================================================ melee / combat feedback
SLASH = {"shortsword", "longsword", "greatsword", "axe", "battleaxe", "polearm", "dagger"}
BLUNT = {"hammer", "mace", "kick", "fists", "knuckles"}
HEAVY = {"greatsword", "battleaxe", "hammer", "polearm"}
STATUS_FX = {"burn": ("ember", (255, 140, 40)), "bleed": ("drop", (190, 20, 30)), "poison": ("bubble", (120, 210, 70)),
             "scald": ("puff", (235, 235, 240)), "chill": ("flake", (200, 235, 255)), "root": ("leaf", (90, 160, 70)),
             "entangle": ("leaf", (90, 160, 70)), "blind": ("puff", (70, 70, 80)), "pierce": ("glint", (230, 230, 240))}


def _on_event(fx, ev):
    x, y = ev["x"], ev["y"] - 10
    src = ev["src"]
    if ev["kind"] == "mana":           # weapon hit fed the attacker's mana: blue motes rise into them
        for _ in range(3 + int(ev["dmg"] // 3)):
            fx.add(P(x + _rng.uniform(-6, 6), y + _rng.uniform(0, 8), 0, -_rng.uniform(15, 35), 0.5, "glint",
                     _rng.choice(((120, 170, 255), (180, 210, 255)))))
        return
    if ev["kind"] == "dodge":
        for k in range(6):
            fx.add(P(x + _rng.uniform(-5, 5), y + 9, _rng.uniform(-30, 30), _rng.uniform(-10, 0), 0.4, "dust", (190, 175, 150), 2.5))
        return
    w = ev.get("weapon") or ""
    ox, oy = ev["origin"]
    ang = math.atan2(y - oy, x - ox)
    if ev["blocked"]:
        cx, cy = x - math.cos(ang) * 6, y - math.sin(ang) * 6
        for k in range(10):
            a = ang + math.pi + _rng.uniform(-1.1, 1.1)
            sp = _rng.uniform(60, 150)
            fx.add(P(cx, cy, math.cos(a) * sp, math.sin(a) * sp, _rng.uniform(0.12, 0.3), "spark",
                     _rng.choice(((200, 220, 255), (255, 255, 255), (150, 180, 255)))))
        fx.add(P(cx, cy, 0, 0, 0.22, "ring", (190, 210, 255), size=12))
        fx.add(P(cx, cy, 0, 0, 0.12, "flash", (200, 220, 255), size=9))
        if ev["guard_broken"]:
            for k in range(8):
                a = _rng.uniform(0, math.tau)
                fx.add(P(cx, cy, math.cos(a) * 110, math.sin(a) * 110 - 30, 0.6, "shard", (170, 190, 230), 2, a=a, floor=y + 10))
            fx.add(P(cx, cy, 0, 0, 0.35, "shock", (255, 170, 90), size=22))
        return
    if ev.get("sub"):
        burst(fx, ev["sub"], x, y, 10, 60)
    elif ev["skill"] in ("archery", "throwing", "firearms") or w in ("bow", "crossbow", "throwing", "firelock"):
        for k in range(6):
            a = ang + _rng.uniform(-0.5, 0.5)
            fx.add(P(x, y, math.cos(a) * 90, math.sin(a) * 90, 0.25, "spark", (255, 230, 200)))
        if w == "firelock":
            for k in range(4):
                fx.add(P(x, y, _rng.uniform(-20, 20), _rng.uniform(-20, 0), 0.6, "smoke", (150, 150, 150), 3))
    elif w in BLUNT:
        heavy = w in HEAVY
        fx.add(P(x, y + 8, 0, 0, 0.35, "shock", (230, 220, 200), size=18 if heavy else 11))
        for k in range(9 if heavy else 5):
            a = _rng.uniform(math.pi, math.tau)
            fx.add(P(x + _rng.uniform(-4, 4), y + 9, math.cos(a) * 60, math.sin(a) * 50, 0.5, "dust", (180, 165, 140), 3))
        if heavy:
            for k in range(5):
                a = _rng.uniform(math.pi * 1.15, math.pi * 1.85)
                fx.add(P(x, y + 8, math.cos(a) * 80, math.sin(a) * 120, 0.7, "debris", (120, 105, 90), 1.4, a=a, floor=y + 10))
        for k in range(3):
            fx.add(P(x, y, 0, 0, 0.5, "star", (255, 240, 150), a=k * 2.1))
    else:
        # cutting / thrusting: bright cut line across the target + blood/sparks along the swing
        cut = ang + (math.pi / 2 if w not in ("spear", "dagger") else 0)
        size = 13 if w in HEAVY else 9
        fx.add(P(x, y, 0, 0, 0.16, "slash", (255, 200, 190), size=size, a=cut + _rng.uniform(-0.3, 0.3)))
        for k in range(6 if ev["dmg"] > 4 else 3):
            a = ang + _rng.uniform(-0.6, 0.6)
            sp = _rng.uniform(50, 120)
            fx.add(P(x, y, math.cos(a) * sp, math.sin(a) * sp - 20, 0.5, "drop", (200, 30, 40), floor=y + 10))
    if ev["dmg"] > 0 and not ev.get("sub"):
        fx.add(P(x, y, 0, 0, 0.1, "flash", (150, 140, 130), size=6 + min(8, ev["dmg"] / 4)))
    if ev["stagger"] > 0.3:
        fx.add(P(x, y + 8, 0, 0, 0.3, "shock", (255, 255, 255), size=16))
    if ev.get("backstab"):
        fx.add(P(x, y, 0, 0, 0.3, "ring", (255, 230, 120), size=18))
    if getattr(ev["tgt"], "team", "") == "player" and getattr(ev["tgt"], "char", None) is not None \
            and getattr(ev["tgt"], "companion_id", None) is None:
        fx.hurt = 0.35


def update(world, t, camx=0, camy=0):
    fx = state_for(world)
    dt = 0.0 if fx.last_t is None else max(0.0, min(0.05, t - fx.last_t))
    fx.last_t = t
    fx.time += dt
    fx.hurt = max(0.0, fx.hurt - dt)
    # notifications from gameplay
    evs = getattr(world, "vfx_events", None)
    if evs:
        for ev in evs:
            _on_event(fx, ev)
        evs.clear()
    # projectiles: trails, launch flourishes, impacts when they vanish
    alive = {}
    for pr in world.projectiles:
        sub = pr.payload.get("sub") if pr.kind == "spell" and pr.payload else None
        if pr not in fx.seen_proj and sub:
            _cast_flourish(fx, pr.owner, sub)
        alive[pr] = (pr.x, pr.y, sub, pr.kind, pr.vx, pr.vy)
        if dt > 0:
            if sub:
                st = style(sub)
                n = _emit(fx, id(pr), st.trail_rate * (1.3 if pr.homing else 1), dt)
                spd = math.hypot(pr.vx, pr.vy) or 1
                for _ in range(n):
                    element_particle(fx, sub, pr.x, pr.y, 2, 14, 1, (0.2, 0.5), -pr.vx / spd * 20, -pr.vy / spd * 20)
            elif pr.kind == "pellet":
                if _emit(fx, id(pr), 30, dt):
                    fx.add(P(pr.x, pr.y, 0, -8, 0.4, "smoke", (170, 170, 170), 1.5))
    for pr, (x, y, sub, kind, vx, vy) in fx.seen_proj.items():
        if pr not in alive:
            fx.emit_acc.pop(id(pr), None)
            if sub:
                burst(fx, sub, x, y, 16, 80)
            elif kind in ("arrow", "bolt", "knife"):
                a = math.atan2(vy, vx)
                for k in range(3):
                    aa = a + math.pi + _rng.uniform(-0.8, 0.8)
                    fx.add(P(x, y, math.cos(aa) * 50, math.sin(aa) * 50 - 30, 0.4, "debris", (150, 115, 75), 0.8, a=aa, floor=y + 8))
    fx.seen_proj = alive
    # spell effects
    eff_alive = {}
    for e in world.effects:
        sub = e.spell.get("sub")
        flags = fx.seen_eff.get(e)
        if flags is None:
            flags = {"burst": False}
            if e.kind not in ("aura_flash",):
                _cast_flourish(fx, e.caster, sub)
            if e.kind == "aura_flash":
                _aura_flash(fx, e, sub)
        eff_alive[e] = flags
        if dt > 0:
            _effect_emit(fx, e, sub, flags, dt)
    fx.seen_eff = eff_alive
    if len(fx.cast_sub) > 40:
        live = set(world.combatants)
        fx.cast_sub = {k: v for k, v in fx.cast_sub.items() if k in live}
    # combatants: cast charge, statuses, knockback dust, footsteps, stagger
    for c in world.combatants:
        if dt <= 0:
            break
        _combatant_emit(fx, c, dt, t)
    # integrate particles
    if dt > 0:
        keep = []
        for p in fx.parts:
            p.life -= dt
            if p.life <= 0:
                continue
            g = GRAV.get(p.kind, 0)
            p.vy += g * dt
            if p.drag:
                k = max(0.0, 1 - p.drag * dt)
                p.vx *= k
                p.vy *= k
            p.x += p.vx * dt
            p.y += p.vy * dt
            if p.floor is not None and p.y > p.floor:
                p.y = p.floor
                p.vy = -p.vy * 0.3
                p.vx *= 0.5
            p.a += dt * 8
            keep.append(p)
        fx.parts = keep
    return fx


def _cast_flourish(fx, caster, sub):
    if caster is None or sub is None:
        return
    st = style(sub)
    fx.cast_sub[caster] = (sub, fx.time)
    fx.add(P(caster.x, caster.y - 1, 0, 0, 0.5, "rune", st.core, size=14, a=_rng.uniform(0, 6)))
    for k in range(8):
        a = k * math.tau / 8
        fx.add(P(caster.x + math.cos(a) * 3, caster.y - 14 + math.sin(a) * 3, math.cos(a) * 50, math.sin(a) * 50,
                 0.3, "spark", st.bright))


def _aura_flash(fx, e, sub):
    st = style(sub)
    tgt = e.caster
    for k in range(14):
        fx.add(P(tgt.x + _rng.uniform(-8, 8), tgt.y + _rng.uniform(-2, 2), 0, -_rng.uniform(20, 50),
                 _rng.uniform(0.5, 0.9), "glint", _rng.choice((st.core, st.bright))))
    fx.add(P(tgt.x, tgt.y, 0, 0, 0.6, "rune", st.core, size=14))
    element_particle(fx, sub, tgt.x, tgt.y - 10, 8, 20, 8)


def _effect_emit(fx, e, sub, flags, dt):
    st = style(sub)
    k = e.kind
    if k == "burst" and not flags["burst"]:
        flags["burst"] = True
        burst(fx, sub, e.x, e.y, 18, 60 + e.spell["area"] * 1.5)
        return
    if k == "chain" and not flags["burst"]:
        flags["burst"] = True
        for px, py in getattr(e, "points", [])[1:]:
            burst(fx, sub, px, py, 6, 50, ring=False)
        return
    if k == "trap" and getattr(e, "sprung", False) and not flags["burst"]:
        flags["burst"] = True
        burst(fx, sub, e.x, e.y, 20, 90)
        return
    if k == "area":
        if e.t >= 0.6 and not flags["burst"]:
            flags["burst"] = True
            r = e.spell["area"]
            burst(fx, sub, e.x, e.y, 22, 60 + r * 2)
            fx.add(P(e.x, e.y + 4, 0, 0, 0.4, "shock", st.bright, size=r * 1.2))
            for i in range(8):
                a = i * math.tau / 8
                burst(fx, sub, e.x + math.cos(a) * r * 0.6, e.y + math.sin(a) * r * 0.35, 3, 40, ring=False, flash=False)
        elif e.t < 0.6:
            n = _emit(fx, id(e), 40, dt)
            r = e.spell["area"]
            for _ in range(n):            # particles gather toward the impact point
                a = _rng.uniform(0, math.tau)
                px, py = e.x + math.cos(a) * r, e.y + math.sin(a) * r * 0.5
                element_particle(fx, sub, px, py, 1, 4, 1, (0.45, 0.55), (e.x - px) * 1.8, (e.y - py) * 1.8)
    elif k in ("ground", "aura"):
        r = e.spell["area"] if k == "ground" else 30
        cy = e.y if k == "ground" else e.caster.y
        cx = e.x if k == "ground" else e.caster.x
        n = _emit(fx, id(e), st.trail_rate * (0.5 + r / 60), dt)
        for _ in range(n):
            a = _rng.uniform(0, math.tau)
            rr = r * math.sqrt(_rng.random())
            element_particle(fx, sub, cx + math.cos(a) * rr, cy + math.sin(a) * rr * 0.5, 1, 10, 1, (0.4, 0.9))
    elif k == "wave":
        r = min(e.spell["area"], e.t * max(60, e.spell["speed"]))
        n = _emit(fx, id(e), 90, dt)
        for _ in range(n):
            a = _rng.uniform(0, math.tau)
            element_particle(fx, sub, e.x + math.cos(a) * r, e.y + math.sin(a) * r * 0.6, 1, 15, 1, (0.2, 0.4),
                             math.cos(a) * 30, math.sin(a) * 18)
    elif k == "orbit":
        n = _emit(fx, id(e), 45, dt)
        for _ in range(n):
            j = _rng.randrange(3)
            a = e.t * 4 + j * math.tau / 3
            element_particle(fx, sub, e.caster.x + math.cos(a) * 24, e.caster.y - 8 + math.sin(a) * 24, 1, 8, 1, (0.2, 0.35))
    elif k == "ward":
        n = _emit(fx, id(e), 14, dt)
        for _ in range(n):
            element_particle(fx, sub, e.x, e.y - 14, 2, 12, 1, (0.4, 0.8))
    elif k == "beam":
        if not flags["burst"]:
            flags["burst"] = True
            ex, ey = e.end
            burst(fx, sub, ex, ey, 12, 70)
            d = math.hypot(ex - e.x, ey - e.y)
            for i in range(int(d / 10)):
                f = _rng.random()
                element_particle(fx, sub, e.x + (ex - e.x) * f, e.y + (ey - e.y) * f, 2, 20, 1, (0.2, 0.5))


def _combatant_emit(fx, c, dt, t):
    x, y = c.x, c.y
    if c.state == "cast":
        sub = fx.cast_sub.get(c, (None, 0))[0]
        if sub:
            st = style(sub)
            for _ in range(_emit(fx, ("cast", c.cid), 60, dt)):
                a = _rng.uniform(0, math.tau)
                r = _rng.uniform(10, 16)
                fx.add(P(x + math.cos(a) * r, y - 14 + math.sin(a) * r, -math.cos(a) * r * 4, -math.sin(a) * r * 4,
                         0.22, "glint", _rng.choice((st.core, st.bright))))
    if not c.alive:
        return
    speed = math.hypot(c.kvx, c.kvy)
    if speed > 60:
        for _ in range(_emit(fx, ("kb", c.cid), min(50, speed / 3), dt)):
            fx.add(P(x + _rng.uniform(-4, 4), y, -c.kvx * 0.1, -8, 0.45, "dust", (185, 170, 145), 2.5))
    if c.state == "dodge":
        for _ in range(_emit(fx, ("dg", c.cid), 40, dt)):
            fx.add(P(x + _rng.uniform(-3, 3), y, _rng.uniform(-10, 10), -6, 0.35, "dust", (190, 178, 150), 2))
    elif c.moving and getattr(c, "speed", 60) > 105:
        for _ in range(_emit(fx, ("run", c.cid), 7, dt)):
            fx.add(P(x + _rng.uniform(-3, 3), y, _rng.uniform(-6, 6), -4, 0.35, "dust", (180, 168, 140), 1.6))
    if c.state == "stagger":
        for _ in range(_emit(fx, ("stg", c.cid), 6, dt)):
            fx.add(P(x, y - 30, 0, 0, 0.4, "star", (255, 235, 140), a=t * 6))
    for s in c.statuses:
        spec = STATUS_FX.get(s["name"])
        if not spec:
            continue
        kind, col = spec
        for _ in range(_emit(fx, (s["name"], c.cid), 9, dt)):
            px, py = x + _rng.uniform(-5, 5), y - _rng.uniform(2, 22)
            if kind in ("root", "leaf") and s["name"] in ("root", "entangle"):
                py = y - _rng.uniform(0, 4)
            fx.add(P(px, py, _rng.uniform(-6, 6), -_rng.uniform(4, 16), _rng.uniform(0.4, 0.8), kind, col,
                     2 if kind in ("bubble", "puff") else 1, a=_rng.uniform(0, 6), floor=y + 1 if kind == "drop" else None))


# ============================================================================ drawing
def draw_under(canvas, world, camx, camy, t):
    """Ground-level layers drawn before sprites: zones, telegraphs, ward circles, rune circles."""
    fx = state_for(world)
    for e in world.effects:
        sub = e.spell.get("sub")
        st = style(sub)
        x, y = e.x - camx, e.y - camy
        k = e.kind
        if k == "area":
            r = e.spell["area"]
            if e.t < 0.6:
                f = e.t / 0.6
                ellipse_alpha(canvas, (x - r, y - r * 0.5, r * 2, r), st.dark, 60 + 60 * f)
                ellipse_alpha(canvas, (x - r * f, y - r * f * 0.5, r * 2 * f, r * f), st.core, 90)
                _dashed_ellipse(canvas, x, y, r, st.bright, t)
            else:
                f = (e.t - 0.6) / max(0.01, e.duration - 0.6)
                ellipse_alpha(canvas, (x - r, y - r * 0.5, r * 2, r), st.core, 160 * (1 - f))
        elif k == "ground":
            _ground_zone(canvas, e, sub, x, y, e.spell["area"], t)
        elif k == "ward":
            r = e.spell["area"]
            ellipse_alpha(canvas, (x - r, y - r * 0.5, r * 2, r), st.core, 40)
            _dashed_ellipse(canvas, x, y, r, st.core, t * 0.5)
            pulse = (t * 0.8) % 1.0
            ellipse_alpha(canvas, (x - r * pulse, y - r * pulse * 0.5, r * 2 * pulse, r * pulse), st.bright, 140 * (1 - pulse), 1)
        elif k == "trap":
            r = e.spell["area"] * 0.6
            if getattr(e, "sprung", False):
                f = min(1.0, (e.t - (e.duration - 0.35)) / 0.35)
                ellipse_alpha(canvas, (x - r * 1.6, y - r * 0.8, r * 3.2, r * 1.6), st.bright, 220 * (1 - f), 3)
            else:
                pulse = 0.5 + 0.5 * math.sin(t * 3 + id(e) % 7)
                ellipse_alpha(canvas, (x - r, y - r * 0.45, r * 2, r * 0.9), st.core, 50 + 40 * pulse, 1)
                for j in range(5):
                    a = t * 0.8 + j * math.tau / 5
                    canvas.fill(st.core, (int(x + math.cos(a) * r * 0.6), int(y + math.sin(a) * r * 0.27), 1, 1))
        elif k == "aura":
            cx, cy = e.caster.x - camx, e.caster.y - camy
            r = 18 + 2 * math.sin(t * 5)
            ellipse_alpha(canvas, (cx - r, cy - r * 0.45, r * 2, r * 0.9), st.core, 80)
            ellipse_alpha(canvas, (cx - r, cy - r * 0.45, r * 2, r * 0.9), st.bright, 160, 1)
    for p in fx.parts:
        if p.kind == "rune":
            _draw_particle(canvas, p, camx, camy)
        elif p.kind == "shock":
            _draw_particle(canvas, p, camx, camy)


def _dashed_ellipse(canvas, x, y, r, col, t):
    n = max(12, int(r / 2))
    for i in range(n):
        if i % 2:
            continue
        a0 = i * math.tau / n + t * 0.6
        a1 = a0 + math.tau / n
        pygame.draw.line(canvas, col, (x + math.cos(a0) * r, y + math.sin(a0) * r * 0.5),
                         (x + math.cos(a1) * r, y + math.sin(a1) * r * 0.5), 1)


def _ground_zone(canvas, e, sub, x, y, r, t):
    st = style(sub)
    fade = min(1.0, e.t / 0.25, max(0.0, (e.duration - e.t) / 0.4))
    g = st.ground
    ellipse_alpha(canvas, (x - r, y - r * 0.5, r * 2, r), st.dark, 90 * fade)
    rng = random.Random(id(e) % 9973)
    if g == "lava":
        for i in range(7):
            a, rr = rng.uniform(0, math.tau), r * math.sqrt(rng.random()) * 0.85
            px, py = x + math.cos(a) * rr, y + math.sin(a) * rr * 0.5
            w = 4 + 2 * math.sin(t * 3 + i)
            ellipse_alpha(canvas, (px - w, py - w * 0.4, w * 2, w * 0.8), st.core, 200 * fade)
            canvas.fill(st.bright, (int(px), int(py), 2, 1))
    elif g == "frost":
        for i in range(10):
            a = rng.uniform(0, math.tau)
            rr = r * rng.uniform(0.3, 0.95)
            pygame.draw.line(canvas, st.bright if i % 2 else st.core, (x, y),
                             (x + math.cos(a) * rr, y + math.sin(a) * rr * 0.5), 1)
            if i % 3 == 0:
                glyph(canvas, sub, x + math.cos(a) * rr, y + math.sin(a) * rr * 0.5 - 3, 2, -math.pi / 2, t)
    elif g == "bog":
        ellipse_alpha(canvas, (x - r * 0.8, y - r * 0.4, r * 1.6, r * 0.8), st.core, 110 * fade)
    elif g == "pool":
        ellipse_alpha(canvas, (x - r * 0.75, y - r * 0.38, r * 1.5, r * 0.75), st.core, 150 * fade)
        ellipse_alpha(canvas, (x - r * 0.4, y - r * 0.25, r * 0.6, r * 0.2), st.bright, 120 * fade)
    elif g == "vines":
        for i in range(8):
            a = i * math.tau / 8 + rng.uniform(-0.2, 0.2)
            pts = []
            for j in range(6):
                rr = r * j / 6
                w = math.sin(j * 1.3 + t * 2 + i) * 2
                pts.append((x + math.cos(a) * rr + w, y + math.sin(a) * rr * 0.5))
            pygame.draw.lines(canvas, st.core, False, pts, 1)
            canvas.fill(st.bright, (int(pts[-1][0]), int(pts[-1][1]) - 1, 2, 2))
    elif g == "crystals":
        for i in range(6):
            a, rr = rng.uniform(0, math.tau), r * rng.uniform(0.3, 0.9)
            px, py = x + math.cos(a) * rr, y + math.sin(a) * rr * 0.5
            h = 4 + rng.randint(0, 4)
            pygame.draw.polygon(canvas, st.core, [(px - 2, py), (px, py - h), (px + 2, py)])
            pygame.draw.line(canvas, st.bright, (px, py - h), (px, py - 1))
    elif g == "spikes":
        for i in range(8):
            a, rr = rng.uniform(0, math.tau), r * rng.uniform(0.2, 0.9)
            px, py = x + math.cos(a) * rr, y + math.sin(a) * rr * 0.5
            up = 3 + 3 * abs(math.sin(t * 4 + i))
            pygame.draw.polygon(canvas, st.core, [(px - 1.5, py), (px, py - up), (px + 1.5, py)])
            canvas.fill(st.bright, (int(px), int(py - up), 1, 1))
    elif g == "dunes":
        for i in range(3):
            rr = r * (0.3 + 0.3 * i)
            a0 = t * (1.5 - i * 0.3)
            pygame.draw.arc(canvas, st.core, (x - rr, y - rr * 0.5, rr * 2, rr), a0, a0 + 2.2, 1)
    elif g == "whirl":
        for i in range(3):
            rr = r * (0.35 + 0.3 * i)
            a0 = -t * (3 - i)
            pygame.draw.arc(canvas, st.bright, (x - rr, y - rr * 0.5, rr * 2, rr), a0, a0 + 1.8, 1)
    elif g == "pulse":
        for i in range(3):
            f = (t * 0.9 + i / 3) % 1.0
            ellipse_alpha(canvas, (x - r * f, y - r * f * 0.5, r * 2 * f, r * f), st.core, 200 * (1 - f) * fade, 1)
    elif g == "well":
        ellipse_alpha(canvas, (x - r * 0.5, y - r * 0.25, r, r * 0.5), (10, 4, 20), 200 * fade)
        for i in range(4):
            rr = r * (1 - ((t * 0.7 + i / 4) % 1.0))
            ellipse_alpha(canvas, (x - rr, y - rr * 0.5, rr * 2, rr), st.core, 180 * fade, 1)
    elif g == "halo":
        ellipse_alpha(canvas, (x - r, y - r * 0.5, r * 2, r), st.core, 70 * fade)
        ellipse_alpha(canvas, (x - r, y - r * 0.5, r * 2, r), st.bright, 200 * fade, 1)
    elif g == "arcs":
        rr_ = random.Random(int(t * 12) + id(e) % 97)
        for i in range(3):
            a0, a1 = rr_.uniform(0, math.tau), rr_.uniform(0, math.tau)
            p0 = (x + math.cos(a0) * r * 0.9, y + math.sin(a0) * r * 0.45)
            p1 = (x + math.cos(a1) * r * 0.9, y + math.sin(a1) * r * 0.45)
            pygame.draw.lines(canvas, st.core, False, jagged(*p0, *p1, 4, rr_), 1)
    elif g in ("mist", "smoke"):
        for i in range(5):
            a = t * 0.5 + i * 1.25
            px, py = x + math.cos(a) * r * 0.5, y + math.sin(a) * r * 0.25
            canvas.blit(disc(r * 0.45, st.core, 90 * fade), (int(px - r * 0.45), int(py - r * 0.45)))
    _dashed_ellipse(canvas, x, y, r, st.core, t)


def draw(canvas, world, camx, camy, t):
    """Effects drawn above sprites: projectiles, beams, waves, orbiters, particles."""
    fx = state_for(world)
    for e in world.effects:
        sub = e.spell.get("sub")
        st = style(sub)
        x, y = e.x - camx, e.y - camy
        k = e.kind
        if k == "beam":
            _beam(canvas, e, sub, x, y, e.end[0] - camx, e.end[1] - camy, t)
        elif k == "wave":
            r = min(e.spell["area"], e.t * max(60, e.spell["speed"]))
            f = e.t / max(0.01, e.duration)
            _wave(canvas, sub, x, y, r, f, t)
        elif k == "orbit":
            cx, cy = e.caster.x - camx, e.caster.y - 8 - camy
            for j in range(3):
                a = e.t * 4 + j * math.tau / 3
                ox, oy = cx + math.cos(a) * 24, cy + math.sin(a) * 24
                add_glow(canvas, ox, oy, 8, st.core, 0.5 * st.glow)
                glyph(canvas, sub, ox, oy, 2.5, a + math.pi / 2, t)
        elif k == "ward":
            _ward_totem(canvas, sub, x, y, t)
        elif k == "burst":
            f = e.t / max(0.01, e.duration)
            r = e.spell["area"] * (0.35 + 0.65 * f)
            ellipse_alpha(canvas, (x - r, y - r * 0.6, r * 2, r * 1.2), st.bright, 230 * (1 - f), 3)
            ellipse_alpha(canvas, (x - r * 0.8, y - r * 0.48, r * 1.6, r * 0.96), st.core, 160 * (1 - f), 2)
            n = max(6, int(r / 5))
            for i in range(n):
                a = i * math.tau / n
                glyph(canvas, sub, x + math.cos(a) * r, y + math.sin(a) * r * 0.6, 2 + r / 40, a, t)
            add_glow(canvas, x, y, 10 + r * 0.4, st.core, (1 - f) * st.glow)
        elif k == "chain":
            pts = [(px - camx, py - camy) for px, py in getattr(e, "points", [])]
            f = max(0.0, 1 - e.t / max(0.01, e.duration))
            rr = random.Random(int(t * 30))
            for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                line = jagged(ax, ay, bx, by, 5 if st.beam == "lightning" else 2.5, rr)
                pygame.draw.lines(canvas, st.dark, False, line, 3)
                pygame.draw.lines(canvas, st.core, False, line, 2)
                pygame.draw.lines(canvas, st.bright, False, line, 1)
                add_glow(canvas, bx, by, 9, st.core, f * st.glow)
                glyph(canvas, sub, bx, by, 2.5, 0, t)
        elif k == "barrier":
            px, py = -e.aim[1], e.aim[0]
            half = e.spell["area"] / 2
            ax, ay, bx, by = x - px * half, y - py * half, x + px * half, y + py * half
            fade = min(1.0, (e.duration - e.t) / 0.5)
            n = max(4, int(half / 4))
            for i in range(n + 1):
                q = i / n
                gx, gy = ax + (bx - ax) * q, ay + (by - ay) * q
                hgt = 10 + 3 * math.sin(t * 6 + i)
                pygame.draw.line(canvas, st.core, (gx, gy), (gx, gy - hgt), 2)
                canvas.fill(st.bright, (int(gx), int(gy - hgt), 2, 2))
            pygame.draw.line(canvas, st.bright, (ax, ay), (bx, by), 2)
            if st.glow > 0.4:
                add_glow(canvas, x, y - 6, half * 0.6, st.core, 0.25 * fade * st.glow)
        elif k == "trap":
            r = e.spell["area"] * 0.6
            if getattr(e, "sprung", False):
                f = min(1.0, (e.t - (e.duration - 0.35)) / 0.35)
                ellipse_alpha(canvas, (x - r * 1.6, y - r * 0.8, r * 3.2, r * 1.6), st.bright, 220 * (1 - f), 3)
            else:
                pulse = 0.5 + 0.5 * math.sin(t * 3 + id(e) % 7)
                ellipse_alpha(canvas, (x - r, y - r * 0.45, r * 2, r * 0.9), st.core, 50 + 40 * pulse, 1)
                for j in range(5):
                    a = t * 0.8 + j * math.tau / 5
                    canvas.fill(st.core, (int(x + math.cos(a) * r * 0.6), int(y + math.sin(a) * r * 0.27), 1, 1))
        elif k == "aura":
            cx, cy = e.caster.x - camx, e.caster.y - camy
            for j in range(4):
                a = t * 3 + j * math.pi / 2
                h = (t * 18 + j * 6) % 24
                px, py = cx + math.cos(a) * 12, cy + math.sin(a) * 5 - h
                glyph(canvas, sub, px, py, 1.6, -math.pi / 2, t)
        elif k == "aura_flash":
            f = e.t / max(0.01, e.duration)
            cx, cy = e.caster.x - camx, e.caster.y - camy
            for j in range(5):                  # a soft column of light rising from the feet
                add_glow(canvas, cx, cy - 4 - j * 7 - f * 10, 9 - j, st.core, (1 - f) * 0.5 * st.glow)
            ellipse_alpha(canvas, (cx - 12, cy - 4, 24, 8), st.bright, 180 * (1 - f), 1)
    # spell projectiles
    for pr in world.projectiles:
        x, y = pr.x - camx, pr.y - camy
        ang = math.atan2(pr.vy, pr.vx)
        if pr.kind == "spell":
            sub = pr.payload.get("sub") if pr.payload else None
            st = style(sub)
            size = pr.payload.get("size", 1.0) if pr.payload else 1.0
            add_glow(canvas, x, y, 11 * size ** 0.5, st.core, 0.6 * st.glow)
            if pr.homing:
                # homing spells leave a fluid ribbon
                for j in range(1, 6):
                    tx = x - pr.vx * 0.012 * j + math.sin(t * 20 + j) * 1.5
                    ty = y - pr.vy * 0.012 * j + math.cos(t * 20 + j) * 1.5
                    canvas.fill(st.core if j % 2 else st.dark, (int(tx), int(ty), 2, 2))
            glyph(canvas, sub, x, y, 3.2 * size ** 0.5, ang, t)
        elif pr.kind in ("arrow", "bolt"):
            ca, sa = math.cos(ang), math.sin(ang)
            ln = 8 if pr.kind == "arrow" else 6
            pygame.draw.line(canvas, (230, 230, 240), (x - ca * (ln + 6), y - sa * (ln + 6)), (x - ca * ln, y - sa * ln), 1)
            pygame.draw.line(canvas, (130, 92, 56), (x - ca * ln, y - sa * ln), (x, y), 2 if pr.kind == "bolt" else 1)
            canvas.fill((225, 225, 235), (int(x), int(y), 2, 2))
            fx_y = y - sa * ln
            canvas.fill((235, 235, 235), (int(x - ca * ln - sa * 2), int(fx_y + ca * 2), 1, 1))
            canvas.fill((235, 235, 235), (int(x - ca * ln + sa * 2), int(fx_y - ca * 2), 1, 1))
        elif pr.kind == "knife":
            a = pr.t * 25
            _poly(canvas, (215, 215, 225), x, y, [(4, 0), (0, 1), (-3, 0), (0, -1)], a)
        elif pr.kind == "pellet":
            canvas.fill((255, 230, 150), (int(x), int(y), 2, 2))
            add_glow(canvas, x, y, 4, (120, 90, 30))
    # charge glows on casters / bow draw
    for c in world.combatants:
        if not c.alive:
            continue
        if c.state == "cast":
            sub = fx.cast_sub.get(c, (None, 0))[0]
            if sub:
                st = style(sub)
                f = max(0.0, 1 - c.state_t / 0.35)
                add_glow(canvas, c.x - camx, c.y - 16 - camy, 12, st.core, f * st.glow)
        elif c.state == "draw":
            pull = min(1.0, c.charge / 0.9)
            add_glow(canvas, c.x + c.aim[0] * 10 - camx, c.y - 12 + c.aim[1] * 10 - camy, 3 + int(pull * 5),
                     (255, 220, 140), 0.3 + pull * 0.6)
        if c.shield > 0:
            cx, cy = c.x - camx, c.y - 12 - camy
            for j in range(6):
                a = t * 1.5 + j * math.tau / 6
                a2 = a + math.tau / 6
                pygame.draw.line(canvas, (150, 220, 235), (cx + math.cos(a) * 13, cy + math.sin(a) * 15),
                                 (cx + math.cos(a2) * 13, cy + math.sin(a2) * 15), 1)
    # particles (runes/shockwaves are drawn on the ground layer)
    for p in fx.parts:
        k = p.kind
        if k in ("rune", "shock"):
            continue
        if k == "flash":
            f = p.life / p.max
            add_glow(canvas, p.x - camx, p.y - camy, p.size * (1.5 - f * 0.5), p.col, f)
            continue
        if k == "zap":
            rr = random.Random(int(p.life * 100))
            for j in range(4):
                a = rr.uniform(0, math.tau)
                pts = jagged(p.x - camx, p.y - camy, p.x - camx + math.cos(a) * p.size,
                             p.y - camy + math.sin(a) * p.size, 4, rr, 4)
                pygame.draw.lines(canvas, p.col, False, pts, 1)
            continue
        _draw_particle(canvas, p, camx, camy)


def draw_screen(screen, world, W, H):
    """Screen-space feedback: a brief red edge when the player is hurt."""
    fx = state_for(world)
    if fx.hurt <= 0:
        return
    a = int(110 * fx.hurt / 0.35)
    s = pygame.Surface((W, H), pygame.SRCALPHA)
    for i in range(6):
        pygame.draw.rect(s, (200, 20, 20, max(0, a - i * 18)), (i * 6, i * 6, W - i * 12, H - i * 12), 6)
    screen.blit(s, (0, 0))


def _beam(canvas, e, sub, x, y, ex, ey, t):
    st = style(sub)
    f = max(0.0, 1 - e.t / max(0.01, e.duration))
    b = st.beam
    w = max(1, int(5 * f))
    rr = random.Random(int(t * 40))
    d = math.hypot(ex - x, ey - y) or 1
    nx, ny = -(ey - y) / d, (ex - x) / d
    if b == "lightning":
        main = jagged(x, y, ex, ey, 7, rr)
        pygame.draw.lines(canvas, st.dark, False, main, 3)
        pygame.draw.lines(canvas, st.core, False, main, 2)
        pygame.draw.lines(canvas, (255, 255, 255), False, main, 1)
        for i in range(1, len(main) - 1, 2):       # branching forks
            px, py = main[i]
            a = math.atan2(ey - y, ex - x) + rr.choice((-1, 1)) * rr.uniform(0.5, 1.1)
            fork = jagged(px, py, px + math.cos(a) * 14, py + math.sin(a) * 14, 3, rr, 3)
            pygame.draw.lines(canvas, st.core, False, fork, 1)
    elif b in ("shards", "prism", "chain", "spikes"):
        pygame.draw.line(canvas, st.dark, (x, y), (ex, ey), 1)
        n = int(d / 7)
        for i in range(n):
            q = (i + 0.5) / n
            px, py = x + (ex - x) * q, y + (ey - y) * q
            glyph(canvas, sub, px, py, 2.4 * (0.6 + 0.4 * f), math.atan2(ey - y, ex - x), t + i)
            if b == "prism" and i % 2:
                canvas.fill(rr.choice(((255, 120, 120), (120, 255, 160), (140, 160, 255))), (int(px + nx * 3), int(py + ny * 3), 1, 1))
    elif b in ("waves",):
        n = int(d / 9)
        for i in range(n):
            q = (i + (t * 6) % 1) / n
            px, py = x + (ex - x) * q, y + (ey - y) * q
            glyph(canvas, sub, px, py, 2, math.atan2(ey - y, ex - x), t)
    elif b == "distort":
        pygame.draw.line(canvas, st.dark, (x, y), (ex, ey), w + 3)
        pygame.draw.line(canvas, st.core, (x, y), (ex, ey), 1)
        for i in range(10):
            q = rr.random()
            px, py = x + (ex - x) * q, y + (ey - y) * q
            o = rr.uniform(4, 9)
            pygame.draw.line(canvas, st.bright, (px + nx * o, py + ny * o), (px + nx * o * 0.3, py + ny * o * 0.3), 1)
    elif b in ("vine", "tendril"):
        for s_ in (-1, 1):
            pts = []
            n = max(3, int(d / 4))
            for i in range(n + 1):
                q = i / n
                o = math.sin(q * 12 + t * 15) * 3 * s_
                pts.append((x + (ex - x) * q + nx * o, y + (ey - y) * q + ny * o))
            pygame.draw.lines(canvas, st.core if s_ > 0 else st.dark, False, pts, 2)
        if b == "vine":
            for i in range(0, int(d), 8):
                q = i / d
                canvas.fill(st.bright, (int(x + (ex - x) * q + nx * 3), int(y + (ey - y) * q + ny * 3), 2, 2))
    elif b in ("mist", "smoke", "sandblast", "gust", "drip"):
        n = int(d / 5)
        for i in range(n):
            q = i / n
            px = x + (ex - x) * q + nx * rr.uniform(-3, 3)
            py = y + (ey - y) * q + ny * rr.uniform(-3, 3)
            if b in ("mist", "smoke"):
                canvas.blit(disc(3 + q * 2, st.core, 140 * f), (int(px - 3), int(py - 3)))
            elif b == "gust":
                pygame.draw.line(canvas, st.core, (px, py), (px - (ex - x) / d * 6, py - (ey - y) / d * 6), 1)
            else:
                canvas.fill(rr.choice((st.core, st.dark, st.bright)), (int(px), int(py), 1 + (b == "drip"), 1 + (b == "drip")))
    else:  # radiant / pulse / molten: thick glowing core
        pygame.draw.line(canvas, st.dark, (x, y), (ex, ey), w + 2)
        pygame.draw.line(canvas, st.core, (x, y), (ex, ey), w)
        pygame.draw.line(canvas, st.bright, (x, y), (ex, ey), max(1, w // 2))
        if b == "pulse":
            q = (t * 5) % 1.0
            add_glow(canvas, x + (ex - x) * q, y + (ey - y) * q, 7, st.core, 1.0)
        if b == "molten":
            for i in range(0, int(d), 9):
                q = i / d
                canvas.fill((40, 16, 10), (int(x + (ex - x) * q), int(y + (ey - y) * q), 2, 2))
    if st.glow > 0.5:
        for i in range(0, int(d), 18):
            q = i / d
            add_glow(canvas, x + (ex - x) * q, y + (ey - y) * q, 8, st.core, 0.35 * f * st.glow)


def _wave(canvas, sub, x, y, r, f, t):
    st = style(sub)
    alpha = 1 - f * 0.7
    ellipse_alpha(canvas, (x - r, y - r * 0.6, r * 2, r * 1.2), st.core, 200 * alpha, 2)
    if r > 6:
        ellipse_alpha(canvas, (x - r + 3, y - r * 0.6 + 2, r * 2 - 6, r * 1.2 - 4), st.bright, 120 * alpha, 1)
    n = max(6, int(r / 4))
    for i in range(n):
        a = i * math.tau / n + t * 0.5
        px, py = x + math.cos(a) * r, y + math.sin(a) * r * 0.6
        glyph(canvas, sub, px, py, 2.0 + r / 30, a, t + i * 0.1)
    if style(sub).glyph == "arcs":      # sound: echoing rings behind the front
        for k in (0.55, 0.8):
            rr = r * k
            ellipse_alpha(canvas, (x - rr, y - rr * 0.6, rr * 2, rr * 1.2), st.core, 120 * alpha, 1)


def _ward_totem(canvas, sub, x, y, t):
    st = style(sub)
    bob = math.sin(t * 3) * 1.5
    pygame.draw.polygon(canvas, (60, 55, 60), [(x - 3, y), (x - 2, y - 10), (x + 2, y - 10), (x + 3, y)])
    pygame.draw.line(canvas, (20, 18, 22), (x - 3, y), (x + 3, y))
    add_glow(canvas, x, y - 16 + bob, 10, st.core, 0.8 * st.glow)
    glyph(canvas, sub, x, y - 16 + bob, 3, -math.pi / 2, t)


def lights(world):
    """(x, y, radius) light sources from active spells, for night-time lighting."""
    out = []
    for pr in world.projectiles:
        if pr.kind == "spell":
            out.append((pr.x, pr.y, 22 if style(pr.payload.get("sub") if pr.payload else None).glow > 0.6 else 14))
    for e in world.effects:
        st = style(e.spell.get("sub"))
        if st.glow < 0.5:
            continue
        if e.kind in ("ground", "area", "ward"):
            out.append((e.x, e.y, min(60, e.spell["area"] + 10)))
        elif e.kind in ("orbit", "aura", "aura_flash"):
            out.append((e.caster.x, e.caster.y - 8, 34))
        elif e.kind == "beam":
            out.append(((e.x + e.end[0]) / 2, (e.y + e.end[1]) / 2, 40))
    return out[:24]
