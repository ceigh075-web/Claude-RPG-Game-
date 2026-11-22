"""Deterministic companion behaviour: follow, fight what threatens the party, block, heal, retreat.
Companions never use the Local AI for combat decisions."""
import math

from ..set_system import combat as rules
from ..set_system import spells
from .combat import facing_from, norm

HEAL_SPELL = {"name": "Laying of Hands", "sub": "light", "move": "aura", "stat": "heal", "tier": 1}
FOLLOW_DIST = 34
ENGAGE_RADIUS = 190


class CompanionAI:
    def __init__(self, c, rng, wait_spot=None):
        self.c = c
        self.rng = rng
        self.wait_spot = wait_spot
        self.heal_cd = 0.0
        self.block_t = 0.0
        self.react_cd = 0.0
        self.offset = (rng.uniform(-18, 18), rng.uniform(6, 20))

    def weapon(self):
        ch = self.c.char
        data = self.world.data
        rng_item = ch.equipment.get("ranged")
        if rng_item and ch.inventory.has(rng_item):
            ammo = data.weapons[data.item(rng_item)["weapon"]].get("ammo")
            need = rng_item if ammo == "self" else ammo
            if need and ch.inventory.has(need):
                return data.item(rng_item)["weapon"], rng_item
        item = ch.equipment.get("weapon")
        if item and ch.inventory.has(item):
            return data.item(item)["weapon"], item
        return "fists", None

    def steer(self, lmap, dx, dy, dt, mult=1.0):
        c = self.c
        c.speed = c.char.move_speed() * c.move_mult() * mult
        if not c.move(lmap, dx, dy, dt):
            for ang in (50, -50, 90, -90):
                r = math.radians(ang)
                if c.move(lmap, dx * math.cos(r) - dy * math.sin(r), dx * math.sin(r) + dy * math.cos(r), dt):
                    break

    def update(self, world, lmap, dt):
        self.world = world
        c = self.c
        self.heal_cd = max(0.0, self.heal_cd - dt)
        self.react_cd = max(0.0, self.react_cd - dt)
        if c.state in ("dead", "stagger", "dodge", "windup", "active", "recovery", "cast", "draw"):
            return
        p = world.player
        # 1) heal a hurt ally (validated spell numbers, paid with the companion's own mana)
        if c.char.skills["magic"] >= 15 and self.heal_cd <= 0:
            props = spells.compute(world.data, HEAL_SPELL, c.char.skills["magic"])
            allies = [a for a in world.combatants if a.team == c.team and a.alive and a.hp < a.max_hp * 0.45
                      and math.hypot(a.x - c.x, a.y - c.y) < 70]
            if allies and c.char.mana >= props["mana"]:
                tgt = min(allies, key=lambda a: a.hp / a.max_hp)
                c.char.mana -= props["mana"]
                world.apply_payload(c, tgt, props, (c.x, c.y))
                c.set_state("cast")
                self.heal_cd = props["cooldown"] + 2.0
                world.events.append(f"{c.name} heals {tgt.name or 'you'}.")
                return
        foes = [e for e in world.enemies() if e.alive and e.hostile and e.alerted and
                math.hypot(e.x - p.x, e.y - p.y) < ENGAGE_RADIUS and not e.enemy.get("training")]
        # 2) retreat toward the player when badly hurt
        if foes and c.hp < c.max_hp * 0.25:
            f = min(foes, key=lambda e: math.hypot(e.x - c.x, e.y - c.y))
            world.set_block(c, False)
            self.steer(lmap, (c.x - f.x) + (p.x - c.x) * 0.5, (c.y - f.y) + (p.y - c.y) * 0.5, dt, 1.1)
            return
        if foes:
            f = min(foes, key=lambda e: math.hypot(e.x - c.x, e.y - c.y))
            d = math.hypot(f.x - c.x, f.y - c.y)
            c.aim = norm(f.x - c.x, f.y - c.y)
            c.facing = facing_from(c.aim)
            # block a telegraphed hit aimed at me
            if f.state == "windup" and f.profile and d < f.profile["reach"] + 14 and self.react_cd <= 0:
                self.react_cd = 0.9
                if self.rng.random() < 0.25 + c.char.skills["blocking"] / 100:
                    world.set_block(c, True)
                    self.block_t = 0.6
                    return
            if c.blocking:
                self.block_t -= dt
                if self.block_t <= 0:
                    world.set_block(c, False)
                return
            wt, item = self.weapon()
            prof = rules.attack_profile(world.data, c.attrs(), c.skills(), wt, item, 1)
            reach = prof["reach"] if prof["class"] == "melee" else 160
            if d > reach:
                self.steer(lmap, f.x - c.x, f.y - c.y, dt)
            else:
                c.weapon_item = item
                if prof["class"] == "ranged" and prof.get("chargeable"):
                    prof = dict(prof, chargeable=False)
                world.attack(c, prof)
            return
        world.set_block(c, False)
        # 3) idle: follow the player or hold a waiting spot
        if self.wait_spot:
            tx, ty = self.wait_spot
        else:
            tx, ty = p.x + self.offset[0] - p.aim[0] * 14, p.y + self.offset[1] - p.aim[1] * 14
        dist = math.hypot(tx - c.x, ty - c.y)
        if dist > (FOLLOW_DIST if not self.wait_spot else 6):
            self.steer(lmap, tx - c.x, ty - c.y, dt, 1.5 if dist > 120 else 1.0)
            if dist > 400 and not self.wait_spot:  # teleport-catch-up if left far behind
                c.x, c.y = p.x - p.aim[0] * 16, p.y - p.aim[1] * 16
        else:
            c.moving = False
