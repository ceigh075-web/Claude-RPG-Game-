"""UI toolkit: theme, fonts, panels, wrapped text, bars and a keyboard/mouse list menu."""
import pygame

# ---------------------------------------------------------------- theme
BG = (18, 16, 24)
PANEL = (34, 30, 42)
PANEL_LIGHT = (50, 44, 60)
BORDER = (120, 98, 70)
BORDER_HI = (214, 176, 102)
TEXT = (232, 224, 208)
TEXT_DIM = (160, 150, 140)
TEXT_BAD = (230, 110, 100)
TEXT_GOOD = (140, 210, 120)
ACCENT = (230, 190, 110)
HP = (200, 64, 60)
FOOD = (210, 150, 70)
WATER = (80, 150, 220)
MANA = (130, 110, 230)

_fonts = {}


def font(size, bold=False):
    key = (size, bold)
    if key not in _fonts:
        f = pygame.font.Font(None, size)
        f.set_bold(bold)
        _fonts[key] = f
    return _fonts[key]


def text(surf, s, pos, size=24, color=TEXT, bold=False, center=False, right=False, shadow=True):
    f = font(size, bold)
    img = f.render(str(s), True, color)
    x, y = pos
    if center:
        x -= img.get_width() // 2
    elif right:
        x -= img.get_width()
    if shadow:
        sh = f.render(str(s), True, (0, 0, 0))
        surf.blit(sh, (x + 1, y + 1))
    surf.blit(img, (x, y))
    return img.get_width()


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


def panel(surf, rect, title=None, alpha=235):
    r = pygame.Rect(rect)
    bg = pygame.Surface(r.size, pygame.SRCALPHA)
    bg.fill(PANEL + (alpha,))
    surf.blit(bg, r.topleft)
    pygame.draw.rect(surf, BORDER, r, 2, border_radius=4)
    pygame.draw.rect(surf, (0, 0, 0), r.inflate(4, 4), 1, border_radius=5)
    if title:
        text(surf, title, (r.x + 14, r.y + 10), 30, ACCENT, bold=True)
        pygame.draw.line(surf, BORDER, (r.x + 10, r.y + 38), (r.right - 10, r.y + 38))
    return r


def bar(surf, rect, frac, color, label=None, size=18):
    r = pygame.Rect(rect)
    pygame.draw.rect(surf, (20, 18, 24), r)
    frac = max(0.0, min(1.0, frac))
    if frac > 0:
        pygame.draw.rect(surf, color, (r.x, r.y, int(r.w * frac), r.h))
        pygame.draw.line(surf, tuple(min(255, c + 50) for c in color), (r.x, r.y), (r.x + int(r.w * frac) - 1, r.y))
    pygame.draw.rect(surf, (0, 0, 0), r, 1)
    if label:
        text(surf, label, (r.centerx, r.y + (r.h - size * 0.7) // 2), size, TEXT, center=True)


def dim(surf, alpha=150):
    s = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    s.fill((0, 0, 0, alpha))
    surf.blit(s, (0, 0))


class ListMenu:
    """Vertical list of selectable entries. Entries: (label, value, enabled[, right_text])."""

    def __init__(self, entries, rect, size=26, row_h=None, scroll=True):
        self.entries = entries
        self.rect = pygame.Rect(rect)
        self.size = size
        self.row_h = row_h or int(size * 1.15)
        self.index = 0
        self.top = 0
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
                pygame.draw.rect(surf, PANEL_LIGHT, hl, border_radius=3)
                pygame.draw.rect(surf, BORDER_HI, hl, 1, border_radius=3)
            col = (TEXT if enabled else TEXT_DIM) if i != self.index else (ACCENT if enabled else TEXT_DIM)
            text(surf, e[0], (self.rect.x + 4, y + 2), self.size, col)
            if len(e) >= 4 and e[3]:
                text(surf, e[3], (self.rect.right - 4, y + 2), self.size, TEXT_DIM if i != self.index else col, right=True)
        if len(self.entries) > self.visible:
            frac = self.visible / len(self.entries)
            h = max(20, int(self.rect.h * frac))
            y = self.rect.y + int((self.rect.h - h) * self.top / max(1, len(self.entries) - self.visible))
            pygame.draw.rect(surf, BORDER, (self.rect.right + 8, y, 4, h))
