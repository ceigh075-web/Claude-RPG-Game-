"""Procedural audio: sound effects and ambient music synthesized at runtime (no asset files, no numpy).

If no audio device is available the game runs silently. Music is rendered lazily on a worker thread so
startup stays fast.
"""
import array
import math
import random
import threading

import pygame

RATE = 22050
_state = {"ok": False, "sfx": {}, "music": {}, "volume": {"master": 0.8, "sfx": 0.8, "music": 0.5},
          "current": None, "channel": None, "rendering": set()}


def init(config=None):
    vol = (config or {}).get("audio", {})
    _state["volume"].update({k: float(v) for k, v in vol.items() if k in _state["volume"]})
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init(frequency=RATE, size=-16, channels=1, buffer=512)
        _state["ok"] = True
        pygame.mixer.set_num_channels(16)
        _state["channel"] = pygame.mixer.Channel(15)
    except pygame.error:
        _state["ok"] = False
    return _state["ok"]


def volumes():
    return dict(_state["volume"])


def set_volume(kind, value):
    _state["volume"][kind] = max(0.0, min(1.0, value))
    if _state["channel"] is not None:
        _state["channel"].set_volume(_state["volume"]["master"] * _state["volume"]["music"])


# ------------------------------------------------------------------ synthesis helpers
def _render(samples):
    buf = array.array("h", (max(-32767, min(32767, int(s * 32767))) for s in samples))
    return pygame.mixer.Sound(buffer=buf.tobytes())


def _env(i, n, attack=0.01, release=0.3):
    t = i / RATE
    a = min(1.0, t / attack) if attack > 0 else 1.0
    r = max(0.0, min(1.0, (n - i) / (RATE * release))) if release > 0 else 1.0
    return a * r


def _tone(freq, dur, wave="sine", vol=0.5, attack=0.005, release=None, slide=0.0, noise=0.0, seed=1):
    n = int(RATE * dur)
    release = dur * 0.8 if release is None else release
    rnd = random.Random(seed)
    out = []
    phase = 0.0
    for i in range(n):
        f = freq * (1 + slide * i / n)
        phase += f / RATE
        p = phase % 1.0
        if wave == "sine":
            v = math.sin(2 * math.pi * p)
        elif wave == "square":
            v = 1.0 if p < 0.5 else -1.0
        elif wave == "tri":
            v = 4 * abs(p - 0.5) - 1
        else:  # saw
            v = 2 * p - 1
        if noise:
            v = v * (1 - noise) + rnd.uniform(-1, 1) * noise
        out.append(v * vol * _env(i, n, attack, release))
    return out


def _mix(*parts):
    n = max(len(p) for p in parts)
    return [sum(p[i] for p in parts if i < len(p)) for i in range(n)]


SFX = {
    "swing":   lambda: _tone(320, 0.12, "saw", 0.18, slide=-0.6, noise=0.7, seed=2),
    "hit":     lambda: _mix(_tone(140, 0.14, "square", 0.25, slide=-0.5, noise=0.5, seed=3), _tone(80, 0.1, "sine", 0.4)),
    "heavy":   lambda: _mix(_tone(70, 0.3, "square", 0.35, slide=-0.6, noise=0.6, seed=4), _tone(45, 0.3, "sine", 0.5)),
    "block":   lambda: _mix(_tone(900, 0.12, "tri", 0.25, slide=-0.2), _tone(1350, 0.08, "sine", 0.15)),
    "dodge":   lambda: _tone(500, 0.18, "saw", 0.12, slide=-0.7, noise=0.85, seed=5),
    "kick":    lambda: _tone(110, 0.12, "square", 0.3, slide=-0.6, noise=0.3, seed=6),
    "bow":     lambda: _tone(700, 0.15, "tri", 0.2, slide=-0.8),
    "firelock": lambda: _mix(_tone(60, 0.45, "saw", 0.5, noise=0.9, seed=7), _tone(40, 0.4, "sine", 0.5)),
    "spell":   lambda: _mix(_tone(520, 0.35, "sine", 0.22, slide=0.6), _tone(780, 0.35, "sine", 0.12, slide=0.6)),
    "heal":    lambda: _mix(_tone(660, 0.4, "sine", 0.2, slide=0.3), _tone(990, 0.4, "sine", 0.1, slide=0.3)),
    "pickup":  lambda: _mix(_tone(880, 0.07, "sine", 0.25), _tone(1320, 0.1, "sine", 0.2)),
    "coin":    lambda: _mix(_tone(1500, 0.08, "square", 0.12), _tone(2000, 0.15, "sine", 0.15)),
    "ui_move": lambda: _tone(660, 0.03, "sine", 0.08, release=0.02),
    "ui_ok":   lambda: _mix(_tone(660, 0.05, "sine", 0.12), _tone(990, 0.07, "sine", 0.1)),
    "mine":    lambda: _mix(_tone(1800, 0.09, "tri", 0.2, noise=0.3, seed=8), _tone(900, 0.12, "sine", 0.15)),
    "chop":    lambda: _tone(220, 0.1, "square", 0.25, noise=0.6, slide=-0.4, seed=9),
    "door":    lambda: _tone(180, 0.25, "saw", 0.15, slide=-0.3, noise=0.4, seed=10),
    "levelup": lambda: _mix(*[_pad(f, 0.18 * (k + 1)) for k, f in enumerate((523, 659, 784, 1046))]),
    "alarm":   lambda: _mix(_tone(330, 0.9, "saw", 0.25, attack=0.15, release=0.4), _tone(220, 0.9, "saw", 0.2, attack=0.15)),
    "death":   lambda: _tone(200, 0.6, "square", 0.25, slide=-0.7, noise=0.3, seed=11),
}


def _pad(freq, delay):
    return [0.0] * int(RATE * delay) + _tone(freq, 0.3, "tri", 0.18)


def play(name):
    if not _state["ok"]:
        return
    snd = _state["sfx"].get(name)
    if snd is None:
        if name not in SFX:
            return
        snd = _state["sfx"][name] = _render(SFX[name]())
    snd.set_volume(_state["volume"]["master"] * _state["volume"]["sfx"])
    snd.play()


# ------------------------------------------------------------------ music
SCALES = {"town": [0, 2, 4, 7, 9], "wild": [0, 3, 5, 7, 10], "combat": [0, 1, 3, 5, 7, 8],
          "travel": [0, 2, 4, 5, 7, 9, 11], "menu": [0, 2, 4, 7, 9]}
ROOTS = {"town": 220.0, "wild": 196.0, "combat": 164.8, "travel": 246.9, "menu": 220.0}
TEMPO = {"town": 0.42, "wild": 0.6, "combat": 0.22, "travel": 0.38, "menu": 0.5}


def _render_music(mood):
    rnd = random.Random(mood)
    scale, root, beat = SCALES[mood], ROOTS[mood], TEMPO[mood]
    bars = 8
    total = int(RATE * beat * 4 * bars)
    out = [0.0] * total
    step = int(RATE * beat)
    # bass drone on chord roots
    chords = [0, 5, 3, 4] if mood != "combat" else [0, 0, 1, 0]
    for b in range(bars):
        deg = chords[b % len(chords)]
        f = root / 2 * 2 ** (scale[deg % len(scale)] / 12)
        note = _tone(f, beat * 4, "tri", 0.10, attack=0.2, release=1.2)
        start = b * step * 4
        for i, v in enumerate(note):
            if start + i < total:
                out[start + i] += v
    # wandering melody
    idx = 2
    for s in range(bars * 4):
        if rnd.random() < (0.55 if mood != "combat" else 0.8):
            idx = max(0, min(len(scale) * 2 - 1, idx + rnd.choice((-2, -1, 1, 1, 2))))
            octave, deg = divmod(idx, len(scale))
            f = root * 2 ** ((scale[deg] + 12 * octave) / 12)
            note = _tone(f, beat * (1.5 if mood != "combat" else 0.8), "sine" if mood != "combat" else "square",
                         0.07 if mood != "combat" else 0.04, attack=0.02, release=beat)
            start = s * step
            for i, v in enumerate(note):
                if start + i < total:
                    out[start + i] += v
    if mood == "combat":
        for s in range(bars * 8):
            hit = _tone(60, 0.08, "sine", 0.25, slide=-0.5)
            start = s * step // 2
            for i, v in enumerate(hit):
                if start + i < total:
                    out[start + i] += v
    return out


def music(mood):
    """Switch the ambient loop (rendered in the background the first time)."""
    if not _state["ok"] or _state["current"] == mood or mood not in SCALES:
        return
    _state["current"] = mood
    snd = _state["music"].get(mood)
    if snd is None:
        if mood in _state["rendering"]:
            return
        _state["rendering"].add(mood)

        def work():
            try:
                samples = _render_music(mood)
                _state["music"][mood] = _render(samples)
            finally:
                _state["rendering"].discard(mood)
                if _state["current"] == mood:
                    _state["current"] = None
                    music(mood)
        threading.Thread(target=work, daemon=True).start()
        return
    ch = _state["channel"]
    ch.set_volume(_state["volume"]["master"] * _state["volume"]["music"])
    ch.fadeout(400)
    ch.play(snd, loops=-1, fade_ms=1500)
