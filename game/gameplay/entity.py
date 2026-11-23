"""Moving actors (player, NPCs) with tile collision and simple animation state."""
import math

from ..world.mapgen import TILE

HB_W, HB_H = 10, 6  # feet hitbox


class Actor:
    def __init__(self, x, y, look, speed=60.0, name=""):
        self.x, self.y = float(x), float(y)  # feet centre in pixels
        self.look = look
        self.speed = speed
        self.name = name
        self.facing = "down"
        self.moving = False
        self.anim_t = 0.0
        self.action = False

    @property
    def tile(self):
        return int(self.x // TILE), int(self.y // TILE)

    def frame(self):
        if not self.moving:
            return 0
        return int(self.anim_t * 8) % 4

    def _blocked(self, lmap, x, y):
        left, right = x - HB_W / 2, x + HB_W / 2 - 0.01
        top, bottom = y - HB_H, y - 0.01
        for ty in range(int(top // TILE), int(bottom // TILE) + 1):
            for tx in range(int(left // TILE), int(right // TILE) + 1):
                if lmap.solid(tx, ty):
                    return True
        return False

    def move(self, lmap, dx, dy, dt, slide=False):
        """Move by direction (dx, dy) at self.speed with axis-separated collision. Returns True if moved.
        With `slide`, bumping a wall corner nudges sideways (up to 5 px) so you glide around it."""
        if dx == 0 and dy == 0:
            self.moving = False
            return False
        n = math.hypot(dx, dy)
        dx, dy = dx / n, dy / n
        step = self.speed * dt
        moved = False
        nx = self.x + dx * step
        if not self._blocked(lmap, nx, self.y):
            self.x = nx
            moved = True
        elif slide and abs(dx) > 0.7:
            for off in (1, 2, 3, 4, 5):
                for sgn in (-1, 1):
                    if not self._blocked(lmap, nx, self.y + sgn * off) and not self._blocked(lmap, self.x, self.y + sgn * min(off, step)):
                        self.y += sgn * min(off, step)
                        moved = True
                        break
                if moved:
                    break
        ny = self.y + dy * step
        if not self._blocked(lmap, self.x, ny):
            self.y = ny
            moved = True
        elif slide and abs(dy) > 0.7:
            for off in (1, 2, 3, 4, 5):
                done = False
                for sgn in (-1, 1):
                    if not self._blocked(lmap, self.x + sgn * off, ny) and not self._blocked(lmap, self.x + sgn * min(off, step), self.y):
                        self.x += sgn * min(off, step)
                        moved = done = True
                        break
                if done:
                    break
        if abs(dx) > abs(dy):
            self.facing = "right" if dx > 0 else "left"
        else:
            self.facing = "down" if dy > 0 else "up"
        self.moving = moved
        if moved:
            self.anim_t += dt * (self.speed / 60.0)
        return moved

    def facing_vec(self):
        return {"down": (0, 1), "up": (0, -1), "left": (-1, 0), "right": (1, 0)}[self.facing]

    def dist_to(self, px, py):
        return math.hypot(px - self.x, py - self.y)


class Wanderer(Actor):
    """NPC that loiters around an anchor point, walking between random nearby tiles."""

    def __init__(self, x, y, look, rng, anchor_radius=4, **kw):
        super().__init__(x, y, look, speed=34.0, **kw)
        self.rng = rng
        self.anchor = (x, y)
        self.radius = anchor_radius * TILE
        self.target = None
        self.wait = rng.uniform(0.5, 3.0)
        self.stuck = 0.0

    def update(self, lmap, dt, stationary=False):
        if stationary:
            self.moving = False
            return
        if self.target is None:
            self.wait -= dt
            self.moving = False
            if self.wait <= 0:
                ax, ay = self.anchor
                for _ in range(8):
                    tx = ax + self.rng.uniform(-self.radius, self.radius)
                    ty = ay + self.rng.uniform(-self.radius, self.radius)
                    if not lmap.solid(int(tx // TILE), int(ty // TILE)):
                        self.target = (tx, ty)
                        break
                self.wait = self.rng.uniform(1.5, 5.0)
            return
        tx, ty = self.target
        dx, dy = tx - self.x, ty - self.y
        if math.hypot(dx, dy) < 3:
            self.target = None
            self.moving = False
            return
        before = (self.x, self.y)
        self.move(lmap, dx, dy, dt)
        if (self.x, self.y) == before:
            self.stuck += dt
            if self.stuck > 0.6:
                self.target, self.stuck = None, 0.0
        else:
            self.stuck = 0.0
