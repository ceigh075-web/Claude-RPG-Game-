"""Options: audio volumes, hints, local AI settings with a live connection test. Saved to config.json."""
import json
import threading

import pygame

from ...core.game import CONFIG_PATH
from ...core.scene import Scene
from ...local_ai.client import LLMClient
from .. import audio
from ..ui import widgets as ui
from .common import is_close

W, H = 1280, 720


class OptionsScene(Scene):
    overlay = True

    def __init__(self, game):
        super().__init__(game)
        self.rows = ["master", "music", "sfx", "hints", "ai", "backend", "model", "test"]
        self.i = 0
        self.status = ""
        self.editing = False

    @property
    def ai(self):
        return self.game.config.setdefault("ai", {"enabled": True, "backend": "ollama",
                                                  "endpoint": "http://localhost:11434", "model": "llama3.2:3b"})

    def save(self):
        cfg = self.game.config
        cfg["audio"] = audio.volumes()
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)
        except OSError as e:
            self.status = f"Could not save settings: {e}"

    def test_ai(self):
        self.status = "Testing connection..."
        client = LLMClient(self.ai)

        def work():
            if not client.enabled:
                self.status = "Local AI is turned off: NPCs use offline dialogue."
                return
            ok = client.available(ttl=0)
            if not ok:
                self.status = f"No model server at {client.cfg['endpoint']}. NPCs will use offline dialogue."
                return
            try:
                out = client.chat([{"role": "system", "content": 'Reply ONLY with JSON {"say": "..."}'},
                                   {"role": "user", "content": "Say hello in five words."}])
                self.status = "Connected! Model says: " + out[:80]
            except Exception as e:
                self.status = f"Server found but the model failed: {str(e)[:80]}"
        threading.Thread(target=work, daemon=True).start()

    def handle(self, ev):
        if self.editing:
            if ev.type == pygame.KEYDOWN:
                if ev.key in (pygame.K_RETURN, pygame.K_ESCAPE):
                    self.editing = False
                    self.save()
                elif ev.key == pygame.K_BACKSPACE:
                    self.ai["model"] = self.ai.get("model", "")[:-1]
                elif ev.unicode and ev.unicode.isprintable():
                    self.ai["model"] = self.ai.get("model", "") + ev.unicode
            return
        if is_close(ev):
            self.save()
            self.close()
            return
        if ev.type != pygame.KEYDOWN:
            return
        k = ev.key
        if k in (pygame.K_UP, pygame.K_w):
            self.i = (self.i - 1) % len(self.rows)
        elif k in (pygame.K_DOWN, pygame.K_s):
            self.i = (self.i + 1) % len(self.rows)
        else:
            row = self.rows[self.i]
            step = {pygame.K_LEFT: -0.1, pygame.K_a: -0.1, pygame.K_RIGHT: 0.1, pygame.K_d: 0.1}.get(k, 0)
            enter = k in (pygame.K_RETURN, pygame.K_SPACE)
            if row in ("master", "music", "sfx") and step:
                audio.set_volume(row, audio.volumes()[row] + step)
                audio.play("ui_move")
            elif row == "hints" and (step or enter):
                self.game.config["hints"] = not self.game.config.get("hints", True)
            elif row == "ai" and (step or enter):
                self.ai["enabled"] = not self.ai.get("enabled", True)
            elif row == "backend" and (step or enter):
                b = "openai" if self.ai.get("backend") == "ollama" else "ollama"
                self.ai["backend"] = b
                self.ai["endpoint"] = "http://localhost:11434" if b == "ollama" else "http://localhost:8080"
            elif row == "model" and enter:
                self.editing = True
            elif row == "test" and enter:
                self.test_ai()
            self.save()

    def draw(self, screen):
        ui.dim(screen, 140)
        r = ui.panel(screen, ((W - 760) // 2, 120, 760, 460), "Options")
        v = audio.volumes()
        labels = [("Master volume", f"{v['master']:.0%}"), ("Music volume", f"{v['music']:.0%}"),
                  ("Effects volume", f"{v['sfx']:.0%}"), ("Tips", "on" if self.game.config.get("hints", True) else "off"),
                  ("Local AI dialogue", "on" if self.ai.get("enabled", True) else "off (offline dialogue)"),
                  ("AI server", f"{self.ai.get('backend', 'ollama')} at {self.ai.get('endpoint')}"),
                  ("AI model", self.ai.get("model", "") + ("_" if self.editing else "")),
                  ("Test AI connection", "")]
        y = r.y + 64
        for i, (a, b) in enumerate(labels):
            sel = i == self.i
            if sel:
                pygame.draw.rect(screen, ui.PANEL_LIGHT, (r.x + 20, y - 4, r.w - 40, 34), border_radius=4)
                pygame.draw.rect(screen, ui.BORDER_HI, (r.x + 20, y - 4, r.w - 40, 34), 1, border_radius=4)
            ui.text(screen, a, (r.x + 36, y), 24, ui.ACCENT if sel else ui.TEXT)
            ui.text(screen, b, (r.right - 36, y), 24, ui.TEXT, right=True)
            y += 40
        if self.status:
            ui.text_block(screen, self.status, (r.x + 36, y + 6, r.w - 72, 50), 21, ui.TEXT_DIM)
        ui.text(screen, "Up/Down select   Left/Right change   Enter toggle/edit/test   Esc close",
                (r.centerx, r.bottom - 30), 20, ui.TEXT_DIM, center=True)
