"""Behaviour for non-hostile characters (townsfolk, shopkeepers, camp NPCs) once they are combatants.

Calm: loiter around an anchor (or stand behind a counter). When attacked, the Set System
(`set_system/aggression.py`) decides the reaction from personality and skills; this class only carries it
out: fight back (reusing the enemy combat brain), flee, call for help, cower/yield, or keep a wary distance
from someone they hold a grudge against. No Local AI is involved.
"""
import math

from ..set_system import aggression
from .combat import facing_from, norm

CALM_SPEED = 34.0
FLEE_GONE = 230          # px away from every threat: they've escaped (removed from the scene)


def civilian_def(name):
    """Enemy-style combat numbers for an anonymous townsperson (no character sheet)."""
    return {"name": name, "archetype": "defensive", "faction": None, "hp": 45, "damage": 4.0, "weapon": "fists",
            "speed": 70, "armor": 1.0, "attack_range": 14, "aggro": 600, "flee_below": 0, "pack": [1, 1],
            "loot": {}, "xp": 5, "color": [120, 120, 120], "shape": "humanoid", "blocks": False}


class BystanderAI:
    def __init__(self, c, rng, anchor_radius=4, stationary=False, wary=False):
        self.c = c
        self.rng = rng
        self.anchor = (c.x, c.y)
        self.radius = anchor_radius * 16
        self.stationary = stationary
        self.mode = "wary" if wary else "calm"
        self.mode_t = 0.0
        self.target = None
        self.wait = rng.uniform(0.5, 3.0)
        self.brain = None
        self.barked = False

    @property
    def fighting(self):
        return self.mode == "fight"

    # ------------------------------------------------------------ events from the combat runtime
    def provoked(self, world, src):
        c = self.c
        kind = aggression.reaction(c.npc, c.hp / max(1.0, c.max_hp), cornered=self._cornered(world))
        if kind == "call_help":
            self._bark(world, "Help! Guards!")
            self._rally(world, src)
            kind = "flee"
        self._set(kind)

    def join(self, world, against):
        self.c.grudge.add(against.cid)
        self.c.alerted = True
        self._set("fight")

    def terrified(self, world, killer):
        if self.mode in ("fight",):
            return
        self.c.grudge.add(killer.cid)
        self._set("flee")

    def recovered(self, world):
        self._bark(world, "...")
        self._set("leave")

    # ------------------------------------------------------------ helpers
    def _set(self, mode):
        if mode == "yield":
            mode = "cower"
        if mode != self.mode:
            self.mode, self.mode_t = mode, 0.0
            if mode == "fight":
                from .enemy_ai import EnemyAI
                self.c.hostile = True
                self.c.alerted = True
                self.c.home = self.anchor
                self.brain = EnemyAI(self.c, self.c.enemy, self.rng)

    def _bark(self, world, text):
        world.floaters.append([text, self.c.x, self.c.y - 34, 0.0, (255, 230, 150)])

    def _cornered(self, world):
        return world.map.kind == "interior"

    def _rally(self, world, attacker):
        st = world.state
        for o in world.combatants:
            if o is self.c or o.team != "npc" or not o.alive or not isinstance(o.ai, BystanderAI):
                continue
            if o.ai.mode not in ("calm", "wary") or math.hypot(o.x - self.c.x, o.y - self.c.y) > aggression.HELP_RADIUS:
                continue
            resp = aggression.bystander_response(st, o.npc, self.c.npc)
            if resp == "help":
                o.ai.join(world, attacker)
                o.ai._bark(world, "Leave them be!")
            elif resp == "flee":
                o.grudge.add(attacker.cid)
                o.ai._set("flee")

    def _threats(self, world):
        return [o for o in world.combatants if o.alive and o.cid in self.c.grudge]

    def _steer(self, lmap, dx, dy, dt, speed):
        c = self.c
        if dx == 0 and dy == 0:
            c.moving = False
            return
        c.speed = speed * c.move_mult()
        dx, dy = norm(dx, dy)
        if not c.move(lmap, dx, dy, dt):
            for ang in (50, -50, 90, -90):
                r = math.radians(ang)
                if c.move(lmap, dx * math.cos(r) - dy * math.sin(r), dx * math.sin(r) + dy * math.cos(r), dt):
                    break

    # ------------------------------------------------------------ main
    def update(self, world, lmap, dt):
        c = self.c
        self.mode_t += dt
        if c.state in ("dead", "stagger", "dodge"):
            return
        hp = c.hp / max(1.0, c.max_hp)
        if self.mode == "fight":
            if not self._threats(world):
                self._set("calm" if not c.grudge else "wary")
                world.set_block(c, False)
                return
            if aggression.reaction(c.npc, hp, cornered=self._cornered(world)) == "yield":
                self._bark(world, "I yield! Please!")
                self._set("cower")
                return
            self.brain.update(world, lmap, dt)
            return
        if c.state in ("windup", "active", "recovery", "cast", "draw"):
            return
        threats = self._threats(world)
        near = min(threats, key=lambda o: math.hypot(o.x - c.x, o.y - c.y)) if threats else None
        dist = math.hypot(near.x - c.x, near.y - c.y) if near else 1e9
        if self.mode in ("flee", "leave"):
            if near is None and self.mode == "flee":
                self._set("calm")
                return
            if dist > FLEE_GONE or self.mode_t > (6.0 if self.mode == "leave" else 9.0):
                if self._cornered(world):
                    self._set("cower")
                else:
                    c.fled = True         # ran off: gone from this scene (still alive in the world)
                return
            if near is not None:
                self._steer(lmap, c.x - near.x, c.y - near.y, dt, c.enemy["speed"] * 1.05)
            else:
                self._steer(lmap, c.x - world.player.x, c.y - world.player.y, dt, c.enemy["speed"] * 0.7)
            c.aim = norm(c.x - (near or world.player).x, c.y - (near or world.player).y)
            c.facing = facing_from(c.aim)
            return
        if self.mode == "cower":
            c.moving = False
            if near is not None:
                c.aim = norm(near.x - c.x, near.y - c.y)
                c.facing = facing_from(c.aim)
            world.set_block(c, True)
            return
        if self.mode == "wary":
            p = world.player
            dp = math.hypot(p.x - c.x, p.y - c.y)
            if dp < 70 and p.alive:
                kind = aggression.reaction(c.npc, hp, cornered=self._cornered(world))
                if kind == "fight":
                    c.grudge.add(p.cid)
                    self._bark(world, "You again!")
                    self._set("fight")
                else:
                    c.grudge.add(p.cid)
                    self._set("flee")
                return
        self._calm(lmap, dt)

    def _calm(self, lmap, dt):
        c = self.c
        if self.stationary:
            c.moving = False
            c.facing = "down"
            return
        if self.target is None:
            self.wait -= dt
            c.moving = False
            if self.wait <= 0:
                ax, ay = self.anchor
                for _ in range(8):
                    tx = ax + self.rng.uniform(-self.radius, self.radius)
                    ty = ay + self.rng.uniform(-self.radius, self.radius)
                    if not lmap.solid(int(tx // 16), int(ty // 16)):
                        self.target = (tx, ty)
                        break
                self.wait = self.rng.uniform(1.5, 5.0)
            return
        tx, ty = self.target
        if math.hypot(tx - c.x, ty - c.y) < 3:
            self.target = None
            c.moving = False
            return
        before = (c.x, c.y)
        self._steer(lmap, tx - c.x, ty - c.y, dt, CALM_SPEED)
        if (c.x, c.y) == before:
            self.target = None
