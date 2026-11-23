"""Deterministic enemy combat AI.

Every enemy reads the same facts: distance, its reach vs. the target's reach, the target's attack phase
(wind-up = threat, recovery = opening), its own health, nearby allies, and line of sight. Archetypes
(aggressive, defensive, fast, heavy, ranged, intelligent) weight those facts differently. At most two
melee enemies hold an "attack token" at once, so packs take turns instead of swarming.
"""
import math

from ..set_system import combat as rules
from ..set_system import morale as morale_rules
from ..set_system import spells as spell_rules
from .combat import facing_from, norm

TOKEN_LIMIT = 2
ESCAPE_DISTANCE = 300
# pause after each attack before the next one (seconds): gives the player openings to answer
ATTACK_PAUSE = {"aggressive": (0.5, 1.0), "defensive": (0.9, 1.5), "fast": (0.3, 0.6), "heavy": (1.1, 1.8),
                "ranged": (0.0, 0.0), "intelligent": (0.6, 1.2), "caster": (0.6, 1.0)}
HELP_RADIUS = 170        # an alerted enemy rouses others of its kind this close by
DODGE_ARCHS = {"fast": 0.55, "intelligent": 0.6, "ranged": 0.45, "caster": 0.5, "aggressive": 0.2}


class EnemyAI:
    def __init__(self, c, enemy, rng):
        self.c = c
        self.e = enemy
        self.rng = rng
        self.arch = enemy["archetype"]
        self.profile = None
        self.mode = "idle"        # idle | engage | orbit | retreat | flee
        self.mode_t = 0.0
        self.orbit_dir = 1 if rng.random() < 0.5 else -1
        self.think = rng.uniform(0, 0.2)
        self.wander_target = None
        self.react_cd = 0.0
        self.flank_angle = None
        self.shoot_cd = rng.uniform(0.5, 1.5)
        self.attack_cd = 0.0
        # combat overhaul: morale, spells, smarter targeting
        self.morale = morale_rules.initial(enemy)
        self.morale_t = 0.0
        self.seen_down = set()
        self.spells = list(enemy.get("spells", []))
        self._props = {}
        self.mana = float(enemy.get("mana", 40 if self.spells else 0))
        self.cast_cd = rng.uniform(0.8, 2.0)
        self.buff_t = 0.0
        self.dodge_cd = 0.0
        self.sticky = None

    # ------------------------------------------------------------ helpers
    def target(self, world):
        """Threat-based target choice: whoever hurt us, the weak (for ranged/smart foes), spread out across the
        party instead of all piling on one, and sticky so targets don't flicker."""
        c = self.c
        foes = world.foes_of(c)
        if not foes:
            return None, 1e9
        piled = {}
        for a in world.combatants:
            t = getattr(a.ai, "sticky", None) if a is not c and a.alive else None
            if t is not None:
                piled[t.cid] = piled.get(t.cid, 0) + 1

        def score(o):
            s = math.hypot(o.x - c.x, o.y - c.y)
            if o is c.last_attacker:
                s -= 40
            if self.arch in ("ranged", "caster", "intelligent"):
                s -= (1 - o.hp / max(1.0, o.max_hp)) * 50
                if o.state in ("cast", "draw"):
                    s -= 20
            return s + 12 * piled.get(o.cid, 0)
        best = min(foes, key=score)
        if self.sticky in foes and score(self.sticky) <= score(best) + 25:
            best = self.sticky
        self.sticky = best
        return best, math.hypot(best.x - c.x, best.y - c.y)

    def threat(self, tgt, d):
        """Is the target about to hit me?"""
        if tgt.state not in ("windup", "draw") or not tgt.profile:
            return False
        if tgt.profile["class"] == "ranged" or tgt.state == "draw":
            return rules.angle_between(tgt.aim, (self.c.x - tgt.x, self.c.y - tgt.y)) < 25
        return d < tgt.profile["reach"] + 14 and rules.angle_between(tgt.aim, (self.c.x - tgt.x, self.c.y - tgt.y)) < 80

    def opening(self, tgt):
        return tgt.state in ("recovery", "stagger", "cast") or (tgt.state == "idle" and tgt.guard < 25)

    def separation(self, world):
        sx = sy = 0.0
        for o in world.enemies():
            if o is self.c:
                continue
            d = math.hypot(o.x - self.c.x, o.y - self.c.y)
            if 0 < d < 18:
                sx += (self.c.x - o.x) / d * (18 - d) / 18
                sy += (self.c.y - o.y) / d * (18 - d) / 18
        return sx, sy

    def steer(self, world, lmap, dx, dy, dt, speed_mult=1.0):
        c = self.c
        if dx == 0 and dy == 0:
            c.moving = False
            return
        sx, sy = self.separation(world)
        dx, dy = norm(dx + sx * 1.5, dy + sy * 1.5)
        old_speed = c.speed
        c.speed = self.e["speed"] * c.move_mult() * speed_mult
        moved = c.move(lmap, dx, dy, dt)
        if not moved:
            # simple obstacle avoidance: try rotated directions
            for ang in (45, -45, 90, -90):
                r = math.radians(ang * self.orbit_dir)
                rx, ry = dx * math.cos(r) - dy * math.sin(r), dx * math.sin(r) + dy * math.cos(r)
                if c.move(lmap, rx, ry, dt):
                    break
        c.speed = old_speed

    def face(self, tgt):
        c = self.c
        c.aim = norm(tgt.x - c.x, tgt.y - c.y)
        c.facing = facing_from(c.aim)

    def try_attack(self, world, tgt, d):
        c = self.c
        if c.state != "idle":
            return False
        if self.attack_cd > 0 and self.arch != "ranged":
            return False
        prof = rules.enemy_profile(world.data, self.e)
        self.face(tgt)
        if world.attack(c, prof):
            c.telegraph = prof["windup"]
            lo, hi = ATTACK_PAUSE[self.arch]
            self.attack_cd = prof["windup"] + prof["active"] + prof["recovery"] + self.rng.uniform(lo, hi)
            return True
        return False

    # ------------------------------------------------------------ main
    def update(self, world, lmap, dt):
        c = self.c
        self.mode_t += dt
        self.react_cd = max(0.0, self.react_cd - dt)
        self.shoot_cd = max(0.0, self.shoot_cd - dt)
        self.attack_cd = max(0.0, self.attack_cd - dt)
        self.cast_cd -= dt
        self.dodge_cd -= dt
        self.buff_t -= dt
        if self.spells:
            self.mana = min(float(self.e.get("mana", 40)), self.mana + self.e.get("mana_regen", 4) * dt)
        if c.state in ("stagger", "dead", "dodge"):
            return
        tgt, d = self.target(world)
        if tgt is None:
            self.wander(world, lmap, dt)
            return
        # perception
        if not c.alerted:
            aggro = self.e["aggro"] * (1.5 if getattr(c, "remembers", False) else 1.0)
            if c.hostile and d < aggro and (d < 70 or world.line_of_sight(c, tgt)):
                c.alerted = True
                world.alert_group(c)
                world.alert_near(c, HELP_RADIUS)
            else:
                self.wander(world, lmap, dt)
                return
        if not c.hostile:
            self.wander(world, lmap, dt)
            return
        hp_frac = c.hp / max(1.0, c.max_hp)
        # morale: humans may break, flee or surrender (Set System decides)
        if self.morale > 0 and self.mode != "flee":
            self.morale_t += dt
            if self.morale_t >= 0.5:
                self.morale_t = 0.0
                verdict = self.check_morale(world, hp_frac)
                if verdict == "surrender":
                    world.surrender(c)
                    return
                if verdict == "flee":
                    self.mode, self.mode_t = "flee", 0.0
                    world.tokens.discard(c.cid)
                    world.floaters.append(["Run!", c.x, c.y - 34, 0.0, (255, 230, 150)])
        # flee when badly hurt (if this archetype ever flees)
        if self.morale <= 0 and self.e.get("flee_below", 0) and hp_frac < self.e["flee_below"] and self.mode != "flee":
            self.mode, self.mode_t = "flee", 0.0
            world.tokens.discard(c.cid)
        if self.mode == "flee":
            self.steer(world, lmap, c.x - tgt.x, c.y - tgt.y, dt, 1.15)
            if d > ESCAPE_DISTANCE or self.mode_t > 8:
                c.fled = True
                world.tokens.discard(c.cid)
                world.events.append(f"{c.name} escaped.")
                world.escaped = getattr(world, "escaped", []) + [c]
            return
        # busy attacking: keep turning toward target during wind-up only (commitment after that)
        if c.state in ("windup",):
            if self.arch != "heavy":
                self.face(tgt)
            return
        if c.state in ("active", "recovery", "cast"):
            return
        if self.dodge_missile(world):
            return
        if self.try_spell(world, tgt, d, hp_frac):
            return
        # defensive reactions to a threatened hit
        if self.threat(tgt, d) and self.react_cd <= 0:
            self.react_cd = 0.8
            roll = self.rng.random()
            if self.e.get("blocks") and roll < {"defensive": 0.85, "intelligent": 0.6}.get(self.arch, 0.4):
                self.face(tgt)
                world.set_block(c, True)
                self.block_t = 0.7
                return
            dodge_ch = {"intelligent": 0.45, "fast": 0.35, "ranged": 0.3}.get(self.arch, 0.0)
            if roll < dodge_ch:
                side = (-(tgt.y - c.y), tgt.x - c.x)
                if self.rng.random() < 0.5:
                    side = (-side[0], -side[1])
                world.dodge(c, norm(side[0] - (tgt.x - c.x) * 0.5, side[1] - (tgt.y - c.y) * 0.5))
                return
        if c.blocking:
            self.block_t = getattr(self, "block_t", 0) - dt
            self.face(tgt)
            if self.block_t <= 0 or not self.threat(tgt, d) and self.block_t < 0.4:
                world.set_block(c, False)
                # riposte after a held block
                if self.arch in ("defensive", "intelligent") and d < self.reach() + 6:
                    self.try_attack(world, tgt, d)
            return
        kind = {"ranged": "ranged", "caster": "caster"}.get(self.arch, "melee")
        getattr(self, "do_" + kind)(world, lmap, tgt, d, dt, hp_frac)

    # ------------------------------------------------------------ morale, missiles, spells
    def check_morale(self, world, hp_frac):
        c = self.c
        allies = [o for o in world.combatants if o is not c and o.team == c.team and o.group == c.group
                  and o.group is not None]
        newly_down = [o for o in allies if not o.alive and o.cid not in self.seen_down]
        leader_down = any(o.enemy and o.enemy.get("commands_allies") for o in newly_down)
        self.seen_down.update(o.cid for o in newly_down)
        alive = 1 + sum(1 for o in allies if o.alive)
        foes = max(1, len([o for o in world.foes_of(c) if math.hypot(o.x - c.x, o.y - c.y) < 240]))
        self.morale = morale_rules.update(self.morale, hp_frac, len(newly_down), leader_down, alive / foes)
        return morale_rules.decide(self.e, self.morale, hp_frac, cornered=world.map.kind == "interior")

    def dodge_missile(self, world):
        """Sidestep an incoming projectile (agile and clever enemies only)."""
        chance = DODGE_ARCHS.get(self.arch)
        c = self.c
        if not chance or self.dodge_cd > 0 or c.state not in ("idle", "recovery"):
            return False
        for pr in world.projectiles:
            if pr.owner is None or not world.hostile_between(pr.owner, c):
                continue
            spd = math.hypot(pr.vx, pr.vy) or 1
            dx, dy = c.x - pr.x, c.y - 8 - pr.y
            along = (dx * pr.vx + dy * pr.vy) / spd
            if 0 < along < 70 and abs(dx * pr.vy - dy * pr.vx) / spd < 10:
                self.dodge_cd = 1.4
                if self.rng.random() < chance:
                    side = (-pr.vy / spd, pr.vx / spd) if self.rng.random() < 0.5 else (pr.vy / spd, -pr.vx / spd)
                    world.dodge(c, side)
                    return True
                return False
        return False

    def spell_props(self, sp):
        key = sp.get("name")
        if key not in self._props:
            self._props[key] = spell_rules.compute(self.world_data, sp, self.e.get("magic", 20))
        return self._props[key]

    def try_spell(self, world, tgt, d, hp_frac):
        """Pick the most useful spell for this moment, using the same spell framework as the player."""
        c = self.c
        if not self.spells or self.cast_cd > 0 or c.state not in ("idle", "recovery"):
            return False
        self.world_data = world.data
        allies = [o for o in world.combatants if o.alive and o.team == c.team and not world.hostile_between(c, o)]
        foes = world.foes_of(c)
        best, best_score, aim_at = None, 0.0, None
        for sp in self.spells:
            p = self.spell_props(sp)
            if self.mana < p["mana"]:
                continue
            mv, stat = p["move"], p["stat"]
            score, at = 0.0, None
            if stat == "heal":
                hurt = [o for o in allies if o.hp < o.max_hp * 0.55 and
                        math.hypot(o.x - c.x, o.y - c.y) <= max(p["area"], p["range"], 30)]
                if hurt:
                    at = min(hurt, key=lambda o: o.hp / max(1.0, o.max_hp))
                    score = 3.0 + (1 - at.hp / max(1.0, at.max_hp)) * 3
            elif p["target"] == "ally":
                if self.buff_t <= 0 and d < 170:
                    score, at = 2.0, c
            else:
                los = world.line_of_sight(c, tgt)
                if mv in ("burst", "self"):
                    near = sum(1 for o in foes if math.hypot(o.x - c.x, o.y - c.y) <= p["area"])
                    score = 1.5 * near
                elif mv in ("area", "ground", "trap", "wave", "chain"):
                    if d <= max(p["range"], p["area"]) and (los or mv == "chain"):
                        near = sum(1 for o in foes if math.hypot(o.x - tgt.x, o.y - tgt.y) <= max(p["area"], 50))
                        score = 1.2 + 0.8 * near
                elif d <= p["range"] * 0.9 and los:
                    score = 1.6
                if stat == "root" and d < 80:
                    score += 1.5
                if stat == "root" and tgt.has_status("root"):
                    score = 0.0
                if mv in ("ground", "trap", "ward") and any(
                        e.caster is c and e.kind == mv and math.hypot(e.x - tgt.x, e.y - tgt.y) < p["area"]
                        for e in world.effects):
                    score = 0.0                  # one field on them is enough
                at = tgt
            if sp.get("name") == getattr(self, "last_spell", None):
                score -= 0.6                     # vary the spells
            if score > best_score:
                best, best_score, aim_at = sp, score, at
        if best is None or best_score < 1.0:
            return False
        p = self.spell_props(best)
        if aim_at is not None and aim_at is not c:
            c.aim = norm(aim_at.x - c.x, aim_at.y - c.y)
            c.facing = facing_from(c.aim)
        ok, _ = world.cast(c, best)
        if ok:
            self.last_spell = best.get("name")
            self.mana -= p["mana"]
            self.cast_cd = self.rng.uniform(1.0, 1.8) if self.arch == "caster" else self.rng.uniform(6.0, 9.0)
            if p["target"] == "ally" and p["stat"] != "heal":
                self.buff_t = 12.0
        return ok

    # ------------------------------------------------------------ caster archetype
    def do_caster(self, world, lmap, tgt, d, dt, hp_frac):
        """Keep a spell's distance: back off when rushed, close in without line of sight, strafe otherwise."""
        c = self.c
        self.face(tgt)
        lo, hi = self.e.get("keep_distance", [80, 150])
        los = world.line_of_sight(c, tgt)
        if d < 22 and self.attack_cd <= 0:
            self.try_attack(world, tgt, d)        # cornered: lash out
            return
        if d < lo:
            self.steer(world, lmap, c.x - tgt.x, c.y - tgt.y, dt, 1.05)
        elif d > hi or not los:
            self.steer(world, lmap, tgt.x - c.x, tgt.y - c.y, dt, 0.85)
        else:
            self.steer(world, lmap, -(tgt.y - c.y) * self.orbit_dir, (tgt.x - c.x) * self.orbit_dir, dt, 0.5)
            if self.rng.random() < dt * 0.4:
                self.orbit_dir *= -1

    def reach(self):
        return max(self.e["attack_range"], 14)

    # ------------------------------------------------------------ melee archetypes
    def do_melee(self, world, lmap, tgt, d, dt, hp_frac):
        c = self.c
        if hp_frac < 0.35 and self.morale > 0 and self.arch != "heavy" and self.mode != "regroup_done":
            mates = [o for o in world.enemies() if o is not c and o.group == c.group and o.alive
                     and o.hp > o.max_hp * 0.5]
            if mates and self.mode != "regroup":
                self.mode, self.mode_t = "regroup", 0.0
            if self.mode == "regroup":
                m = min(mates, key=lambda o: math.hypot(o.x - c.x, o.y - c.y)) if mates else None
                if m is None or self.mode_t > 1.6:
                    self.mode = "regroup_done"
                else:
                    # fall back behind the healthiest ally
                    bx, by = m.x + (m.x - tgt.x) * 0.3, m.y + (m.y - tgt.y) * 0.3
                    self.steer(world, lmap, bx - c.x, by - c.y, dt, 1.05)
                    world.tokens.discard(c.cid)
                    return
        reach = self.reach()
        arch = self.arch
        tgt_reach = tgt.profile["reach"] if tgt.profile and tgt.profile.get("class") == "melee" else 20
        has_token = world.request_token(c, TOKEN_LIMIT)
        # hit-and-run creatures back off after attacking
        if self.mode == "retreat":
            self.face(tgt)
            self.steer(world, lmap, c.x - tgt.x + (tgt.y - c.y) * self.orbit_dir * 0.6,
                       c.y - tgt.y - (tgt.x - c.x) * self.orbit_dir * 0.6, dt, 0.9)
            if self.mode_t > (1.0 if arch == "fast" else 0.6):
                self.mode, self.mode_t = "engage", 0.0
            return
        punish = self.opening(tgt) and d < reach + 18 and arch in ("aggressive", "intelligent", "fast")
        if self.attack_cd > 0 and not (punish and self.attack_cd < 0.4):
            world.tokens.discard(c.cid)
            if arch == "defensive" and self.e.get("blocks") and d < reach + 20:
                self.face(tgt)
                world.set_block(c, True)
                self.block_t = min(self.attack_cd, 0.6)
                return
            self.orbit(world, lmap, tgt, d, dt, max(reach + 10, tgt_reach + 6))
            return
        if not has_token and not punish:
            # wait our turn: circle at a safe distance outside the target's reach
            self.orbit(world, lmap, tgt, d, dt, max(tgt_reach + 26, reach + 26))
            return
        # intelligent enemies take a flanking angle and wait at the edge of their reach for an opening
        if arch == "intelligent":
            self.commanded_flanks(world, tgt)
            if d > reach + 2:
                fx, fy = self.flank_point(tgt, reach - 2)
                self.steer(world, lmap, fx - c.x, fy - c.y, dt)
                self.face(tgt)
                return
            if not punish and tgt.state not in ("idle",) and self.rng.random() < 0.6:
                self.face(tgt)
                c.moving = False
                return
            self.try_attack(world, tgt, d)
            return
        if arch == "defensive" and d < reach + 30 and not punish and tgt.state == "idle" and self.e.get("blocks"):
            # advance behind a raised guard, then strike
            if d > reach:
                world.set_block(c, False)
                self.steer(world, lmap, tgt.x - c.x, tgt.y - c.y, dt, 0.7)
                self.face(tgt)
                return
        if d > reach:
            speed = 1.0 if arch != "heavy" else 0.85
            if arch == "fast" and d < reach + 40:
                speed = 1.35  # lunge
            self.steer(world, lmap, tgt.x - c.x, tgt.y - c.y, dt, speed)
            self.face(tgt)
            return
        if self.try_attack(world, tgt, d) and arch == "fast":
            self.mode, self.mode_t = "retreat", -0.4

    def orbit(self, world, lmap, tgt, d, dt, radius):
        c = self.c
        self.face(tgt)
        rx, ry = c.x - tgt.x, c.y - tgt.y
        tx, ty = -ry * self.orbit_dir, rx * self.orbit_dir
        radial = (d - radius) / max(1, radius)
        self.steer(world, lmap, tx * 0.6 - rx * radial * 2, ty * 0.6 - ry * radial * 2, dt, 0.6)
        if self.rng.random() < dt * 0.3:
            self.orbit_dir *= -1

    def commanded_flanks(self, world, tgt):
        """A commander spreads its allies around the target so they attack from different sides."""
        if not self.e.get("commands_allies"):
            return
        allies = [o for o in world.enemies() if o is not self.c and o.group == self.c.group and o.ai]
        for i, a in enumerate(allies):
            a.ai.flank_angle = (i + 1) * (math.tau / (len(allies) + 1))

    def flank_point(self, tgt, dist):
        ang = self.flank_angle if self.flank_angle is not None else math.atan2(self.c.y - tgt.y, self.c.x - tgt.x)
        if self.flank_angle is not None:
            ang += math.atan2(tgt.aim[1], tgt.aim[0])
        return tgt.x + math.cos(ang) * dist, tgt.y + math.sin(ang) * dist

    # ------------------------------------------------------------ ranged archetype
    def do_ranged(self, world, lmap, tgt, d, dt, hp_frac):
        c = self.c
        self.face(tgt)
        lo, hi = 90, min(200, self.e["attack_range"] - 10)
        los = world.line_of_sight(c, tgt)
        if d < lo:
            self.steer(world, lmap, c.x - tgt.x, c.y - tgt.y, dt, 1.0)
        elif d > hi or not los:
            self.steer(world, lmap, tgt.x - c.x, tgt.y - c.y, dt, 0.9)
        else:
            # strafe while in the sweet spot
            self.steer(world, lmap, -(tgt.y - c.y) * self.orbit_dir, (tgt.x - c.x) * self.orbit_dir, dt, 0.45)
            if self.rng.random() < dt * 0.4:
                self.orbit_dir *= -1
            if self.shoot_cd <= 0 and los and world.request_token(c, TOKEN_LIMIT + 1):
                if self.try_attack(world, tgt, d):
                    self.shoot_cd = self.rng.uniform(1.2, 2.2)

    # ------------------------------------------------------------ idle
    def wander(self, world, lmap, dt):
        c = self.c
        if self.wander_target is None or self.mode_t > 4:
            hx, hy = getattr(c, "home", (c.x, c.y))
            self.wander_target = (hx + self.rng.uniform(-40, 40), hy + self.rng.uniform(-40, 40))
            self.mode_t = 0.0
        tx, ty = self.wander_target
        if math.hypot(tx - c.x, ty - c.y) < 4:
            c.moving = False
            return
        self.steer(world, lmap, tx - c.x, ty - c.y, dt, 0.4)
