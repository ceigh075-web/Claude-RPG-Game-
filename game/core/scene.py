"""Scene base class and a stack-based scene manager (overlays draw on top of the scene below)."""


class Scene:
    overlay = False      # if True, the scene below is drawn first
    pauses_below = True  # if False, the scene below keeps updating

    def __init__(self, game):
        self.game = game

    @property
    def state(self):
        return self.game.state

    @property
    def data(self):
        return self.game.data

    def on_enter(self):
        pass

    def on_exit(self):
        pass

    def on_resume(self):
        """Called when a scene above this one is popped."""
        pass

    def handle(self, ev):
        pass

    def update(self, dt):
        pass

    def draw(self, screen):
        pass

    def close(self):
        self.game.scenes.pop(self)


class SceneManager:
    def __init__(self, game):
        self.game = game
        self.stack = []

    @property
    def top(self):
        return self.stack[-1] if self.stack else None

    def push(self, scene):
        self.stack.append(scene)
        scene.on_enter()
        return scene

    def pop(self, scene=None):
        if not self.stack:
            return
        if scene is not None and scene in self.stack:
            # pop everything above and including `scene`
            while self.stack:
                s = self.stack.pop()
                s.on_exit()
                if s is scene:
                    break
        else:
            self.stack.pop().on_exit()
        if self.stack:
            self.stack[-1].on_resume()

    def replace(self, scene):
        while self.stack:
            self.stack.pop().on_exit()
        return self.push(scene)

    def handle(self, ev):
        if self.stack:
            self.stack[-1].handle(ev)

    def update(self, dt):
        if not self.stack:
            return
        self.stack[-1].update(dt)
        i = len(self.stack) - 1
        while i > 0 and not self.stack[i].pauses_below:
            i -= 1
            self.stack[i].update(dt)

    def draw(self, screen):
        if not self.stack:
            return
        start = len(self.stack) - 1
        while start > 0 and self.stack[start].overlay:
            start -= 1
        for s in self.stack[start:]:
            s.draw(screen)
