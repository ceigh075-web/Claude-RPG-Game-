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
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "config.json")


def load_config():
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


class Game:
    def __init__(self, headless=False, save_dir=None):
        if headless:
            os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
            os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        pygame.init()
        pygame.display.set_caption("Kindred Roads")
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
            self.toast(f"Game saved to slot {slot}.")
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
        except OSError as e:
            self.toast(f"Autosave failed: {e}")

    def load_game(self, slot):
        try:
            self.state = self.saves.load(slot, self.data)
        except SaveError as e:
            self.toast(str(e))
            return False
        self.enter_world()
        self.toast(f"Loaded slot {slot}.")
        return True

    def toast(self, text, seconds=3.5):
        self.toasts.append([text, seconds])
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

    def _draw_toasts(self):
        from ..presentation.ui import widgets as ui
        y = 140
        for text, left in self.toasts[-4:]:
            alpha = min(1.0, left / 0.6)
            w = ui.font(22).size(text)[0] + 24
            s = pygame.Surface((w, 28), pygame.SRCALPHA)
            s.fill((20, 16, 24, int(200 * alpha)))
            self.screen.blit(s, (WINDOW[0] // 2 - w // 2, y))
            ui.text(self.screen, text, (WINDOW[0] // 2, y + 6), 22,
                    tuple(int(c * alpha) for c in ui.TEXT), center=True, shadow=False)
            y += 32
