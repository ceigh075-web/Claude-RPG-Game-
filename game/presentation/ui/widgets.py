"""UI toolkit: theme, fonts, panels, wrapped text, bars and a keyboard/mouse list menu."""
import pygame

# ---------------------------------------------------------------- theme
# Medieval wood & parchment: dark warm wood panels with brass trim (light text), parchment for notes,
# tooltips, notifications and the guidebook (dark ink text).
BG = (24, 18, 14)
PANEL = (58, 38, 24)
PANEL_LIGHT = (104, 72, 42)
BORDER = (150, 108, 62)
BORDER_HI = (232, 190, 112)
TEXT = (242, 230, 204)
TEXT_DIM = (182, 160, 128)
TEXT_BAD = (240, 120, 100)
TEXT_GOOD = (160, 220, 120)
ACCENT = (244, 200, 112)
HP = (196, 58, 50)
FOOD = (214, 150, 66)
WATER = (74, 146, 214)
MANA = (112, 120, 236)
XP = (226, 196, 92)
# parchment palette
PARCH = (230, 212, 170)
PARCH_DARK = (196, 168, 120)
INK = (58, 38, 22)
INK_DIM = (112, 88, 62)
INK_RED = (140, 40, 30)
INK_GREEN = (40, 100, 40)
INK_BLUE = (40, 60, 130)

_fonts = {}


def font(size, bold=False):
    key = (size, bold)
    if key not in _fonts:
        f = pygame.font.Font(None, size)
        f.set_bold(bold)
        _fonts[key] = f
    return _fonts[key]


_text_cache = {}


def _render(s, size, color, bold, shadow):
    key = (s, size, tuple(color), bold, shadow)
    img = _text_cache.get(key)
    if img is None:
        if len(_text_cache) > 3000:
            _text_cache.clear()
        f = font(size, bold)
        fg = f.render(s, True, color)
        if shadow:
            img = pygame.Surface((fg.get_width() + 1, fg.get_height() + 1), pygame.SRCALPHA)
            img.blit(f.render(s, True, (0, 0, 0)), (1, 1))
            img.blit(fg, (0, 0))
        else:
            img = fg
        _text_cache[key] = img
    return img


def text(surf, s, pos, size=24, color=TEXT, bold=False, center=False, right=False, shadow=True):
    img = _render(str(s), size, color, bold, shadow)
    w = img.get_width() - (1 if shadow else 0)
    x, y = pos
    if center:
        x -= w // 2
    elif right:
        x -= w
    surf.blit(img, (x, y))
    return w


def wrap(s, size, width, bold=False):
    f = font(size, bold)
    lines = []
    for para in str(s).split("\n"):
        words = para.split(" ")
        cur = ""
        for w in words:
            test = (cur + " " + w).strip()
            if f.size(test)[0] <= width:
                cur = test
            else:
                if cur:
                    lines.append(cur)
                cur = w
        lines.append(cur)
    return lines


def text_block(surf, s, rect, size=22, color=TEXT, line_h=None):
    line_h = line_h or int(size * 0.85)
    y = rect[1]
    for line in wrap(s, size, rect[2]):
        if y + line_h > rect[1] + rect[3]:
            break
        text(surf, line, (rect[0], y), size, color)
        y += line_h
    return y


_tex = {}


def _noise_tile(base, spread, size=64, seed=1):
    import random
    key = ("noise", base, spread, size, seed)
    if key not in _tex:
        r = random.Random(seed)
        t = pygame.Surface((size, size))
        t.fill(base)
        for _ in range(size * size // 3):
            v = r.randint(-spread, spread)
            c = tuple(max(0, min(255, b + v)) for b in base)
            t.set_at((r.randrange(size), r.randrange(size)), c)
        _tex[key] = t
    return _tex[key]


def _wood(w, h):
    """Horizontal planks with grain, cached per size."""
    import math
    import random
    key = ("wood", w, h)
    if key in _tex:
        return _tex[key]
    if len(_tex) > 160:
        _tex.clear()
    s = pygame.Surface((w, h))
    r = random.Random(w * 31 + h)
    y = 0
    k = 0
    while y < h:
        ph = r.randint(26, 40)
        base = (PANEL[0] + (6 if k % 2 else -4), PANEL[1] + (4 if k % 2 else -3), PANEL[2] + (2 if k % 2 else -2))
        tile = _noise_tile(base, 5, 64, k % 3 + 1)
        for tx in range(0, w, 64):
            s.blit(tile, (tx, y), (0, 0, min(64, w - tx), min(ph, 64, h - y)))
        if ph > 64:
            s.fill(base, (0, y + 64, w, ph - 64))
        # grain
        for g in range(3):
            gy = y + r.randint(4, max(5, ph - 4))
            amp = r.uniform(0.6, 1.6)
            freq = r.uniform(0.01, 0.025)
            off = r.uniform(0, 6)
            col = tuple(max(0, c - 14) for c in base)
            pts = [(x, gy + amp * math.sin(x * freq + off)) for x in range(0, w + 8, 8)]
            if len(pts) > 1:
                pygame.draw.lines(s, col, False, pts, 1)
        if r.random() < 0.5 and w > 80:           # a knot
            kx, ky = r.randint(20, w - 20), y + ph // 2
            pygame.draw.ellipse(s, tuple(max(0, c - 18) for c in base), (kx - 6, ky - 3, 12, 6), 1)
        pygame.draw.line(s, (28, 18, 12), (0, min(h - 1, y + ph - 1)), (w, min(h - 1, y + ph - 1)))  # plank seam
        pygame.draw.line(s, tuple(min(255, c + 12) for c in base), (0, y), (w, y))
        y += ph
        k += 1
    _tex[key] = s
    return s


def _parchment(w, h):
    key = ("parch", w, h)
    if key in _tex:
        return _tex[key]
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    tile = _noise_tile(PARCH, 7, 64, 7)
    for ty in range(0, h, 64):
        for tx in range(0, w, 64):
            s.blit(tile, (tx, ty))
    # darker, aged edges (straight bands, strongest at the rim)
    edge = pygame.Surface((w, h), pygame.SRCALPHA)
    for i in range(min(6, h // 4, w // 4)):
        a = 64 - i * 11
        edge.fill((*PARCH_DARK, a), (i, i, w - 2 * i, 1))
        edge.fill((*PARCH_DARK, a), (i, h - 1 - i, w - 2 * i, 1))
        edge.fill((*PARCH_DARK, a), (i, i, 1, h - 2 * i))
        edge.fill((*PARCH_DARK, a), (w - 1 - i, i, 1, h - 2 * i))
    s.blit(edge, (0, 0))
    _tex[key] = s
    return s


def frame(surf, r, thick=True):
    """Carved wooden frame with a bevel and brass corner studs."""
    pygame.draw.rect(surf, (20, 12, 8), r.inflate(4, 4), 2, border_radius=5)
    pygame.draw.rect(surf, BORDER, r, 3, border_radius=4)
    pygame.draw.line(surf, (190, 144, 86), (r.x + 3, r.y + 1), (r.right - 4, r.y + 1))
    pygame.draw.line(surf, (92, 62, 36), (r.x + 3, r.bottom - 2), (r.right - 4, r.bottom - 2))
    if thick and r.w > 60 and r.h > 40:
        for cx, cy in ((r.x + 6, r.y + 6), (r.right - 7, r.y + 6), (r.x + 6, r.bottom - 7), (r.right - 7, r.bottom - 7)):
            pygame.draw.circle(surf, (110, 80, 34), (cx, cy), 4)
            pygame.draw.circle(surf, BORDER_HI, (cx, cy), 3)
            surf.set_at((cx - 1, cy - 1), (255, 240, 190))


def panel(surf, rect, title=None, alpha=235):
    """Wooden panel. Titles sit on a carved plaque. Returns the rect."""
    r = pygame.Rect(rect)
    bg = _wood(r.w, r.h)
    if alpha < 255:
        bg = bg.copy()
        bg.set_alpha(alpha)
    surf.blit(bg, r.topleft)
    frame(surf, r)
    if title:
        tw = font(30, True).size(title)[0]
        plaque = pygame.Rect(r.x + 12, r.y + 6, tw + 28, 32)
        pygame.draw.rect(surf, (40, 26, 16), plaque, border_radius=4)
        pygame.draw.rect(surf, BORDER_HI, plaque, 1, border_radius=4)
        text(surf, title, (plaque.x + 14, plaque.y + 5), 30, ACCENT, bold=True)
        y = r.y + 42
        pygame.draw.line(surf, (30, 20, 12), (r.x + 10, y), (r.right - 10, y))
        pygame.draw.line(surf, BORDER, (r.x + 10, y + 1), (r.right - 10, y + 1))
    return r


def parchment(surf, rect, alpha=255):
    """A sheet of parchment (use INK colours for text on it)."""
    r = pygame.Rect(rect)
    p = _parchment(r.w, r.h)
    if alpha < 255:
        p = p.copy()
        p.set_alpha(alpha)
    surf.blit(p, r.topleft)
    pygame.draw.rect(surf, (90, 66, 40), r, 1, border_radius=3)
    return r


def ink(surf, s, pos, size=22, color=INK, bold=False, center=False, right=False):
    """Text on parchment: no shadow."""
    return text(surf, s, pos, size, color, bold=bold, center=center, right=right, shadow=False)


def ink_block(surf, s, rect, size=22, color=INK, line_h=None):
    line_h = line_h or int(size * 0.9)
    y = rect[1]
    for line in wrap(s, size, rect[2]):
        if y + line_h > rect[1] + rect[3]:
            break
        ink(surf, line, (rect[0], y), size, color)
        y += line_h
    return y


def tooltip(surf, title, lines, pos, width=320, color=INK):
    """Parchment tooltip near `pos`, kept on screen. `lines` = list of str or (str, colour)."""
    body = []
    for ln in lines:
        txt, col = (ln if isinstance(ln, tuple) else (ln, color))
        for w in wrap(txt, 20, width - 20):
            body.append((w, col))
    h = 14 + (26 if title else 0) + len(body) * 18 + 8
    x = min(max(4, pos[0]), surf.get_width() - width - 4)
    y = min(max(4, pos[1]), surf.get_height() - h - 4)
    shadow = pygame.Surface((width, h), pygame.SRCALPHA)
    shadow.fill((0, 0, 0, 90))
    surf.blit(shadow, (x + 4, y + 4))
    parchment(surf, (x, y, width, h))
    yy = y + 8
    if title:
        ink(surf, title, (x + 10, yy), 24, INK, bold=True)
        yy += 26
    for txt, col in body:
        ink(surf, txt, (x + 10, yy), 20, col)
        yy += 18
    return pygame.Rect(x, y, width, h)


def keycap(surf, key, pos, size=18):
    """A little key button, e.g. keycap(screen, "E", (x, y)). Returns its width."""
    f = font(size, True)
    w = max(size, f.size(key)[0] + 10)
    r = pygame.Rect(pos[0], pos[1], w, size + 4)
    pygame.draw.rect(surf, (40, 28, 18), r.move(0, 2), border_radius=4)
    pygame.draw.rect(surf, PARCH, r, border_radius=4)
    pygame.draw.rect(surf, (90, 66, 40), r, 1, border_radius=4)
    ink(surf, key, (r.centerx, r.y + 3), size, INK, bold=True, center=True)
    return w


def prompt(surf, key, label, center, size=22, icon=None):
    """'[E] Talk to Hessa' as a keycap + (optional action icon) + label on a small wooden plate."""
    f = font(size)
    kw = font(size - 2, True).size(key)[0] + 10
    iw = size + 6 if icon is not None else 0
    w = kw + 10 + iw + f.size(label)[0] + 24
    r = pygame.Rect(0, 0, w, size + 14)
    r.center = center
    s = pygame.Surface(r.size, pygame.SRCALPHA)
    s.fill((40, 26, 16, 220))
    surf.blit(s, r.topleft)
    pygame.draw.rect(surf, BORDER, r, 1, border_radius=4)
    keycap(surf, key, (r.x + 10, r.y + 5), size - 2)
    if icon is not None:
        ic = fit_icon(icon, size + 4)
        surf.blit(ic, (r.x + 16 + kw, r.y + (r.h - ic.get_height()) // 2))
    text(surf, label, (r.x + 20 + kw + iw, r.y + 8), size, TEXT)
    return r


def bar(surf, rect, frac, color, label=None, size=18):
    r = pygame.Rect(rect)
    pygame.draw.rect(surf, (24, 16, 10), r, border_radius=3)
    frac = max(0.0, min(1.0, frac))
    if frac > 0:
        fill = pygame.Rect(r.x + 1, r.y + 1, max(1, int((r.w - 2) * frac)), r.h - 2)
        pygame.draw.rect(surf, color, fill, border_radius=2)
        hi = tuple(min(255, c + 55) for c in color)
        pygame.draw.line(surf, hi, (fill.x + 1, fill.y), (fill.right - 2, fill.y))
        lo = tuple(int(c * 0.7) for c in color)
        pygame.draw.line(surf, lo, (fill.x + 1, fill.bottom - 1), (fill.right - 2, fill.bottom - 1))
    pygame.draw.rect(surf, (150, 108, 62), r, 1, border_radius=3)
    if label:
        text(surf, label, (r.centerx, r.y + (r.h - size * 0.7) // 2), size, TEXT, center=True)


def dim(surf, alpha=150):
    s = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    s.fill((0, 0, 0, alpha))
    surf.blit(s, (0, 0))


def _click(name):
    from .. import audio
    audio.play(name)


_fit_cache = {}


def fit_icon(img, h):
    """An icon scaled (by whole steps where possible, keeping pixels crisp) to at most `h` px tall."""
    key = (id(img), h)
    out = _fit_cache.get(key)
    if out is None:
        w0, h0 = img.get_size()
        if h0 * 0.74 <= h and h0 * 2 > h:
            out = img           # native size: pixel art stays crisp (the icons carry their own padding)
        elif h0 * 2 <= h:
            k = h // h0
            out = pygame.transform.scale(img, (w0 * k, h0 * k))
        else:
            out = pygame.transform.smoothscale(img, (max(1, w0 * h // h0), h))
        if len(_fit_cache) > 600:
            _fit_cache.clear()
        _fit_cache[key] = out
    return out


class ListMenu:
    """Vertical list of selectable entries. Entries: (label, value, enabled[, right_text[, icon]]).
    `icon` is an optional pygame Surface shown before the label (scaled to the row height)."""

    def __init__(self, entries, rect, size=26, row_h=None, scroll=True):
        self.entries = entries
        self.rect = pygame.Rect(rect)
        self.size = size
        self.row_h = row_h or int(size * 1.15)
        self.index = 0
        self.top = 0
        self.icon_for = None        # optional: value -> Surface, an icon drawn before each label
        self._skip_disabled(1)

    @property
    def visible(self):
        return max(1, self.rect.h // self.row_h)

    def set_entries(self, entries, keep_index=True):
        self.entries = entries
        if not keep_index:
            self.index = 0
        self.index = max(0, min(self.index, len(entries) - 1))
        self._clamp_scroll()

    def selected(self):
        if not self.entries:
            return None
        e = self.entries[self.index]
        return e[1] if len(e) < 3 or e[2] else None

    def _skip_disabled(self, step):
        if not self.entries:
            return
        for _ in range(len(self.entries)):
            e = self.entries[self.index]
            if len(e) < 3 or e[2]:
                return
            self.index = (self.index + step) % len(self.entries)

    def _clamp_scroll(self):
        if self.index < self.top:
            self.top = self.index
        if self.index >= self.top + self.visible:
            self.top = self.index - self.visible + 1
        self.top = max(0, min(self.top, max(0, len(self.entries) - self.visible)))

    def move(self, step):
        if not self.entries:
            return
        _click("ui_move")
        self.index = (self.index + step) % len(self.entries)
        self._skip_disabled(step)
        self._clamp_scroll()

    def handle(self, ev):
        """Returns the chosen value on activation, else None."""
        if ev.type == pygame.KEYDOWN:
            if ev.key in (pygame.K_UP, pygame.K_w):
                self.move(-1)
            elif ev.key in (pygame.K_DOWN, pygame.K_s):
                self.move(1)
            elif ev.key == pygame.K_PAGEUP:
                self.move(-self.visible)
            elif ev.key == pygame.K_PAGEDOWN:
                self.move(self.visible)
            elif ev.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_e, pygame.K_KP_ENTER):
                if self.selected() is not None:
                    _click("ui_ok")
                return self.selected()
        elif ev.type == pygame.MOUSEMOTION:
            i = self._row_at(ev.pos)
            if i is not None:
                self.index = i
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            i = self._row_at(ev.pos)
            if i is not None:
                self.index = i
                return self.selected()
        elif ev.type == pygame.MOUSEWHEEL:
            self.top = max(0, min(self.top - ev.y, max(0, len(self.entries) - self.visible)))
        return None

    def _row_at(self, pos):
        if not self.rect.collidepoint(pos):
            return None
        i = self.top + (pos[1] - self.rect.y) // self.row_h
        if 0 <= i < len(self.entries):
            return i
        return None

    def draw(self, surf):
        for row in range(self.visible):
            i = self.top + row
            if i >= len(self.entries):
                break
            e = self.entries[i]
            enabled = len(e) < 3 or e[2]
            y = self.rect.y + row * self.row_h
            if i == self.index:
                hl = pygame.Rect(self.rect.x - 6, y - 2, self.rect.w + 12, self.row_h)
                band = pygame.Surface(hl.size, pygame.SRCALPHA)
                band.fill((*PANEL_LIGHT, 230))
                surf.blit(band, hl.topleft)
                pygame.draw.rect(surf, BORDER_HI, hl, 1, border_radius=3)
                cy = hl.centery
                pygame.draw.polygon(surf, BORDER_HI, [(hl.x - 8, cy - 5), (hl.x - 2, cy), (hl.x - 8, cy + 5)])
            elif row % 2 == 1:
                stripe = pygame.Surface((self.rect.w + 12, self.row_h), pygame.SRCALPHA)
                stripe.fill((0, 0, 0, 28))
                surf.blit(stripe, (self.rect.x - 6, y - 2))
            col = (TEXT if enabled else TEXT_DIM) if i != self.index else (ACCENT if enabled else TEXT_DIM)
            tx = self.rect.x + 4
            icon = e[4] if len(e) >= 5 else (self.icon_for(e[1]) if self.icon_for else None)
            if icon is not None:
                ic = fit_icon(icon, self.row_h - 2)
                if not enabled:
                    ic = ic.copy()
                    ic.set_alpha(110)
                surf.blit(ic, (tx, y - 1 + (self.row_h - ic.get_height()) // 2))
                tx += ic.get_width() + 6
            text(surf, e[0], (tx, y + 2), self.size, col)
            if len(e) >= 4 and e[3]:
                text(surf, e[3], (self.rect.right - 4, y + 2), self.size, TEXT_DIM if i != self.index else col, right=True)
        if len(self.entries) > self.visible:
            frac = self.visible / len(self.entries)
            h = max(20, int(self.rect.h * frac))
            y = self.rect.y + int((self.rect.h - h) * self.top / max(1, len(self.entries) - self.visible))
            pygame.draw.rect(surf, (30, 20, 12), (self.rect.right + 7, self.rect.y, 6, self.rect.h), border_radius=3)
            pygame.draw.rect(surf, BORDER_HI, (self.rect.right + 8, y, 4, h), border_radius=2)
