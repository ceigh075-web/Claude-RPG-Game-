"""Game manager: window, main loop, shared services, new/load/save flow."""
import json
import os

import pygame

from .data import GameData
from .events import EventBus
from .save import SaveManager, SaveError
from .scene import SceneManager
from .state import GameState
from ..presentation.art import Art
from ..world.worldmap import WorldMap
from ..world import mapgen

WINDOW = (1280, 720)
CANVAS = (640, 360)
FPS = 60
from .paths import CONFIG_PATH, DEFAULT_CONFIG


def load_config():
    """User config (next to the exe / project) overrides the bundled defaults."""
    cfg = {}
    for path in (DEFAULT_CONFIG, CONFIG_PATH):
        try:
            with open(path, encoding="utf-8") as f:
                cfg.update(json.load(f))
        except (OSError, json.JSONDecodeError):
            pass
    return cfg


class Game:
    def __init__(self, headless=False, save_dir=None):
        if headless:
            os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
            os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        pygame.init()
        pygame.display.set_caption("Kindred Roads")
        try:
            from .paths import BUNDLE_ROOT
            pygame.display.set_icon(pygame.image.load(os.path.join(BUNDLE_ROOT, "assets", "icon32.png")))
        except (pygame.error, FileNotFoundError):
            pass
        flags = 0 if headless else (pygame.SCALED | pygame.RESIZABLE)
        try:
            # SCALED: the 1280x720 layout is scaled to any window size / fullscreen with correct mouse mapping
            self.screen = pygame.display.set_mode(WINDOW, flags, vsync=1 if flags else 0)
        except pygame.error:
            self.screen = pygame.display.set_mode(WINDOW)
        self.canvas = pygame.Surface(CANVAS)
        self.clock = pygame.time.Clock()
        self.config = load_config()
        self.data = GameData()
        self.world = WorldMap(self.data)
        self.art = Art()
        self.saves = SaveManager(save_dir)
        self.events = EventBus()
        from ..presentation import audio
        audio.init(self.config)
        self.events.subscribe("sfx", lambda sound: audio.play(sound))
        self.scenes = SceneManager(self)
        self.state = None
        self.running = True
        self.toasts = []  # [text, seconds_left]
        self._maps = {}

    # ------------------------------------------------------------ maps
    def local_map(self, loc_id):
        if loc_id not in self._maps:
            self._maps[loc_id] = mapgen.generate(self.data, self.world, loc_id)
        return self._maps[loc_id]

    def interior_map(self, loc_id, building_id):
        key = (loc_id, building_id)
        if key not in self._maps:
            b = self.local_map(loc_id).buildings[building_id]
            self._maps[key] = mapgen.generate_interior(self.data, loc_id, b)
        return self._maps[key]

    # ------------------------------------------------------------ flow
    def start(self):
        from ..presentation.scenes.menu import MainMenu
        self.scenes.replace(MainMenu(self))

    def new_game(self, name, race, look, pronouns):
        self.state = GameState.new_game(self.data, name, race, look, pronouns)
        self.enter_world()

    def enter_world(self):
        from ..presentation.scenes.local import LocalScene
        from ..presentation.scenes.travel import TravelScene
        if self.state.mode == "travel" and self.state.travel:
            self.scenes.replace(TravelScene(self))
        else:
            self.scenes.replace(LocalScene(self))

    def save_game(self, slot):
        try:
            self.saves.save(self.state, slot)
            self.last_save_minutes = self.state.clock.total_minutes
            from ..presentation import audio
            audio.play("save")
            self.toast(f"Game saved to slot {slot} - {self.state.clock.date_str()}, {self.state.clock.time_str()}.")
            return True
        except OSError as e:
            self.toast(f"Save failed: {e}")
            return False

    def autosave(self):
        from .save import AUTOSAVE_SLOT
        if self.state is None:
            return
        try:
            self.saves.save(self.state, AUTOSAVE_SLOT)
            self.last_save_minutes = self.state.clock.total_minutes
        except OSError as e:
            self.toast(f"Autosave failed: {e}")

    def load_game(self, slot):
        try:
            self.state = self.saves.load(slot, self.data)
        except SaveError as e:
            self.toast(str(e))
            return False
        self.last_save_minutes = self.state.clock.total_minutes
        self.enter_world()
        self.toast(f"Loaded slot {slot}.")
        return True

    def toast(self, text, seconds=3.5):
        for t in self.toasts:            # the same message again just refreshes its slip
            if t[0] == text:
                t[1] = seconds
                return
        self.toasts.append([text, seconds])
        kind = self._toast_kind(text)
        if kind in ("bad", "gold") or "discovered" in text.lower():
            from ..presentation import audio
            audio.play({"bad": "fail", "gold": "coin"}.get(kind, "discover"))
        if len(self.toasts) > 5:
            self.toasts.pop(0)

    def notify(self, msgs):
        """Log and toast a list of Set System messages."""
        if isinstance(msgs, str):
            msgs = [msgs]
        for m in msgs:
            if self.state:
                self.state.add_log(m)
            self.toast(m)

    # ------------------------------------------------------------ loop
    def step(self, dt, events=()):
        for ev in events:
            if ev.type == pygame.QUIT:
                self.running = False
            elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_F11:
                try:
                    pygame.display.toggle_fullscreen()
                except pygame.error:
                    pass
            else:
                self.scenes.handle(ev)
        self.scenes.update(dt)
        for t in self.toasts:
            t[1] -= dt
        self.toasts = [t for t in self.toasts if t[1] > 0]
        self.screen.fill((0, 0, 0))
        self.scenes.draw(self.screen)
        self._draw_toasts()

    def run(self):
        self.start()
        while self.running:
            dt = min(self.clock.tick(FPS) / 1000.0, 0.05)
            self.step(dt, pygame.event.get())
            pygame.display.flip()
        pygame.quit()

    TOAST_KINDS = (
        ("bad", ("not enough", "can't", "cannot", "won't", "need ", "too ", "no ", "out of", "isn't", "full", "failed",
                 "recharging", "blocked", "only ")),
        ("gold", ("level up", "marks", "+", "xp", "reward", "sold", "bought", "earned")),
        ("good", ("joins", "learned", "discovered", "inscribed", "saved", "crafted", "new ", "found", "healed", "rewritten")),
    )
    TOAST_COL = {"bad": (170, 50, 40), "gold": (200, 150, 40), "good": (60, 130, 60), "info": (90, 70, 50)}

    def _toast_kind(self, text):
        low = text.lower()
        for kind, words in self.TOAST_KINDS:
            if any(w in low for w in words):
                return kind
        return "info"

    def _draw_toasts(self):
        """Parchment slips under the HUD; a coloured seal marks warnings, rewards and discoveries."""
        from ..presentation.ui import widgets as ui
        top = self.scenes.top
        in_menu = top is not None and getattr(top, "overlay", False)
        # exploring: stacked upward above the prompt line; in a menu: a compact strip at the very top
        y = 4 if in_menu else WINDOW[1] - 112
        for text, left in (self.toasts[-2:] if in_menu else reversed(self.toasts[-4:])):
            age = max(0.0, 3.5 - left)
            alpha = min(1.0, left / 0.6)
            slide = int(max(0.0, 1 - age / 0.18) * 18)
            lines = ui.wrap(text, 22, 640)
            w = min(700, max(ui.font(22).size(ln)[0] for ln in lines) + 56)
            h = 12 + 22 * len(lines)
            x = WINDOW[0] // 2 - w // 2
            surf = pygame.Surface((w, h), pygame.SRCALPHA)
            ui.parchment(surf, (0, 0, w, h))
            col = self.TOAST_COL[self._toast_kind(text)]
            pygame.draw.circle(surf, col, (18, h // 2), 7)
            pygame.draw.circle(surf, tuple(min(255, c + 70) for c in col), (16, h // 2 - 2), 2)
            for i, ln in enumerate(lines):
                ui.ink(surf, ln, (34, 7 + i * 22), 22)
            surf.set_alpha(int(255 * alpha))
            if in_menu:
                self.screen.blit(surf, (x, y - slide))
                y += h + 4
            else:
                self.screen.blit(surf, (x, y - h + slide))
                y -= h + 6