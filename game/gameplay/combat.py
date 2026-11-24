"""Real-time combat runtime: combatants, attack phases, projectiles, spell effects, pickups and feedback.

Collision/timing lives here; every number (damage, knockback, stagger, spell power) comes from the
Set System (set_system/combat.py, set_system/spells.py). Health, items and reputation changes go through
the Character / Inventory / factions APIs.
"""
import math

from ..set_system import aggression
from ..set_system import combat as rules
from ..set_system import factions, spells as spell_rules
from ..world.mapgen import TILE
from .entity import Actor

FRICTION = 9.0          # knockback velocity decay per second (exponential)
PICKUP_RADIUS = 14
SPEED_MULT = {"idle": 1.0, "windup": 0.5, "active": 0.35, "recovery": 0.8, "stagger": 0.0, "dodge": 0.0,
              "draw": 0.6, "dead": 0.0, "cast": 0.85}
CAST_TIME = 0.12        # brief casting pose; can be cancelled into anything
DIRS = {"right": (1, 0), "left": (-1, 0), "down": (0, 1), "up": (0, -1)}


def norm(dx, dy):
    d = math.hypot(dx, dy)
    return (dx / d, dy / d) if d > 1e-6 else (0.0, 1.0)


def facing_from(vec):
    dx, dy = vec
    if abs(dx) > abs(dy):
        return "right" if dx > 0 else "left"
    return "down" if dy > 0 else "up"


class Combatant(Actor):
    """Anything that can fight. The player wraps a Character; enemies carry their own numbers."""

    _ids = 0

    def __init__(self, x, y, look, speed, name="", team="enemy", char=None, enemy=None, race=None):
        super().__init__(x, y, look, speed, name)
        Combatant._ids += 1
        self.cid = Combatant._ids
        self.team = team
        self.char = char
        self.enemy = enemy
        self.race_data = race
        self._hp = float(enemy["hp"]) if enemy else 0.0
        self.max_hp_base = float(enemy["hp"]) if enemy else 0.0
        self.armor = float(enemy["armor"]) if enemy else 0.0
        self.mass = {"heavy": 2.5, "defensive": 1.6}.get(enemy["archetype"], 1.0) if enemy else 1.0
        self.poise = {"heavy": 0.75, "defensive": 0.5}.get(enemy["archetype"], 0.25) if enemy else 0.3
        self.guard = rules.GUARD_MAX
        self.state = "idle"
        self.state_t = 0.0
        self.profile = None
        self.combo = 0
        self.queued = False
        self.combo_window = 0.0
        self.blocking = False
        self.aim = DIRS[self.facing]
        self.kvx = self.kvy = 0.0
        self.statuses = []      # {"name","kind","mag","t"}
        self.buffs = {}         # attr -> [amount, seconds]
        self.shield = 0.0
        self.flash = 0.0
        self.dead_t = 0.0
        self.hit_ids = set()
        self.dodge_cd = 0.0
        self.dodge_vec = (0.0, 0.0)
        self.kick_cd = 0.0
        self.charge = 0.0
        self.alerted = False
        self.ai = None
        self.group = None
        self.hostile = True
        self.last_attacker = None
        self.fled = False
        self.telegraph = 0.0
        self.attackers = 0
        self.grudge = set()     # cids this combatant is hostile to regardless of teams (personal conflicts)
        self.downed = False     # defeated (0 HP) but alive; can recover
        self.killed = False     # finished off: permanent
        self.npc = None         # named NPC record, if any

    # ------------------------------------------------------------ stats
    @property
    def hp(self):
        return self.char.hp if self.char else self._hp

    @hp.setter
    def hp(self, v):
        if self.char:
            self.char.hp = max(0.0, min(self.max_hp, v))
        else:
            self._hp = max(0.0, min(self.max_hp, v))

    @property
    def max_hp(self):
        base = self.char.max_hp if self.char else self.max_hp_base
        return base + self.buffs.get("health", [0])[0] * 3

    def attrs(self):
        if self.char:
            a = {k: self.char.attr(k) for k in ("strength", "speed", "health", "dexterity")}
        else:
            a = {"strength": 10.0, "speed": 10.0, "health": 10.0, "dexterity": 10.0}
        for k, (amt, _) in self.buffs.items():
            if k in a:
                a[k] += amt
        return a

    def skills(self):
        return self.char.skills if self.char else {}

    @property
    def alive(self):
        return self.state != "dead"

    @property
    def iframes(self):
        return self.state == "dodge" and self.state_t < rules.DODGE_IFRAMES

    def has_status(self, kind):
        return any(s["kind"] == kind for s in self.statuses)

    def move_mult(self):
        m = SPEED_MULT.get(self.state, 1.0)
        if self.blocking:
            m *= 0.45
        if self.has_status("root"):
            return 0.0
        for s in self.statuses:
            if s["kind"] == "slow":
                m *= 1 - s["mag"]
        return m

    def defender_view(self):
        return {"x": self.x, "y": self.y - 6, "facing": self.aim, "blocking": self.blocking and self.state in ("idle", "recovery"),
                "guard": self.guard, "poise": self.poise, "armor": self.armor, "mass": self.mass,
                "iframes": self.iframes, "blocking_skill": self.skills().get("blocking", 0),
                "armor_break": self.has_status("armor_break")}

    def set_state(self, s):
        self.state = s
        self.state_t = 0.0


class Projectile:
    def __init__(self, x, y, vx, vy, team, owner, profile=None, rng_left=200, kind="arrow", color=(230, 220, 200),
                 radius=3, pierce=0, payload=None, homing=0.0, charge=1.0):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.team, self.owner, self.profile, self.range_left = team, owner, profile, rng_left
        self.kind, self.color, self.radius, self.pierce = kind, color, radius, pierce
        self.payload, self.homing, self.charge = payload, homing, charge
        self.hit = set()
        self.dead = False
        self.t = 0.0


class SpellEffect:
    """Persistent spell shapes: wave, area (delayed burst), ground, orbit, ward, beam visual, aura pulse."""

    def __init__(self, kind, caster, spell, x, y, duration, aim=(1, 0)):
        self.kind, self.caster, self.spell = kind, caster, spell
        self.x, self.y = x, y
        self.t = 0.0
        self.duration = duration
        self.aim = aim
        self.hit = set()
        self.tick = 0.0
        self.cooldowns = {}
        self.dead = False


class CombatWorld:
    def sfx(self, name):
        ev = getattr(self.game, "events", None)
        if ev is not None:
            ev.publish("sfx", sound=name)

    def __init__(self, game, state, lmap, rng):
        self.game, self.state, self.data, self.map, self.rng = game, state, game.data, lmap, rng
        self.combatants = []
        self.projectiles = []
        self.effects = []
        self.floaters = []      # [text, x, y, t, color]
        self.particles = []     # [x, y, vx, vy, t, color]
        self.intent = bool(state.settings.get("hostile_intent", False)) if state is not None else False
        self.vfx_events = []    # purely visual notifications (hits, dodges) consumed by the renderer
        self.pickups = []       # {"item","qty","x","y"}
        self.shake = 0.0
        self.hitstop = 0.0
        self.spell_cd = {}
        self.player = None
        self.tokens = set()
        self.events = []        # messages for the scene to notify
        self.kills = []         # enemy ids killed this session

    # ================================================================ setup
    def add_player(self, actor):
        st = self.state
        c = Combatant(actor.x, actor.y, actor.look, actor.speed, actor.name, team="player", char=st.player,
                      race=st.race_data)
        c.facing = actor.facing
        c.aim = DIRS[c.facing]
        c.armor = st.player.armor_value(self.data)
        self.player = c
        self.combatants.append(c)
        return c

    def add_companion(self, cid, char, x, y, look, wait_spot=None):
        from .companion_ai import CompanionAI
        c = Combatant(x, y, look, char.move_speed(), char.name, team="player", char=char,
                      race=self.data.races[char.race])
        c.companion_id = cid
        c.npc = self.data.npcs[cid]
        c.armor = char.armor_value(self.data)
        c.ai = CompanionAI(c, self.rng, wait_spot)
        c.hostile = True
        self.combatants.append(c)
        return c

    def add_townsfolk(self, npc, x, y, look, rng, anchor_radius=4, stationary=False, name=None, guard=False):
        """A non-hostile character (named NPC, shopkeeper, townsperson or guard) who can still be attacked."""
        from .bystander_ai import BystanderAI, civilian_def, guard_def
        e = npc_fighter(self.data, npc) if npc else (guard_def() if guard else civilian_def(name or "Townsperson"))
        c = Combatant(x, y, look, 34.0, npc["name"] if npc else (name or "Townsperson"), team="npc", enemy=e,
                      race=self.data.races.get(npc["race"]) if npc else None)
        c.npc = npc
        c.enemy_id = None
        c.hostile = False
        c.stationary = stationary
        c.is_guard = guard
        if guard:
            c.mass, c.poise = 1.6, 0.5
        wary = bool(npc) and aggression.grudge_active(self.state, npc["id"])
        c.ai = BystanderAI(c, rng, anchor_radius, stationary, wary=wary)
        self.combatants.append(c)
        return c

    def companions(self):
        return [c for c in self.combatants if getattr(c, "companion_id", None)]

    def spawn_enemy(self, enemy_id, x, y, group=None, hostile=True, edef=None, look=None):
        from .enemy_ai import EnemyAI
        e = edef or self.data.enemies[enemy_id]
        look = look or enemy_look(e)
        c = Combatant(x, y, look, e["speed"], e["name"], team="enemy", enemy=e)
        c.enemy_id = enemy_id
        c.group = group
        c.hostile = hostile
        c.home = (x, y)
        c.ai = None if e.get("training") else EnemyAI(c, e, self.rng)
        if e.get("training"):
            c.mass, c.poise = 50.0, 5.0
        self.combatants.append(c)
        return c

    def enemies(self, alive=True):
        return [c for c in self.combatants if c.team == "enemy" and (c.alive or not alive)]

    # ---------------------------------------------------------------- who may hurt whom
    @staticmethod
    def hostile_between(a, b):
        """Teams decide the default (party vs enemies); personal grudges override it either way.
        'npc' team characters (townsfolk, shopkeepers, camp NPCs) are nobody's enemy until a grudge forms."""
        if a is b:
            return False
        if b.cid in a.grudge or a.cid in b.grudge:
            return True
        if a.team == b.team or "npc" in (a.team, b.team):
            return False
        return True

    def foes_of(self, c):
        return [o for o in self.combatants if o.alive and self.hostile_between(c, o)]

    def strike_targets(self, c):
        """Everyone this combatant's attacks can connect with. With hostile intent on, the player's attacks
        connect with anyone at all - friends, neutrals and companions included."""
        if c is self.player and self.intent:
            return [o for o in self.combatants if o.alive and o is not c]
        return self.foes_of(c)

    def can_hit(self, owner, o, team=None):
        if owner is None:
            return o.team != team
        if o is owner:
            return False
        return self.hostile_between(owner, o) or (owner is self.player and self.intent)

    def threatens_party(self, o):
        """A non-enemy currently fighting the player's side."""
        if not o.alive or o.team == "enemy" or o is self.player:
            return False
        if not any(cid in o.grudge for cid in self._party_ids()):
            return False
        return getattr(o.ai, "fighting", True)

    def _party_ids(self):
        ids = {c.cid for c in self.companions() if not c.grudge}
        if self.player is not None:
            ids.add(self.player.cid)
        return ids

    @property
    def in_combat(self):
        if any(c.alive and c.alerted and c.hostile and not c.enemy.get("training") for c in self.enemies()):
            return True
        return self.player is not None and any(self.threatens_party(o) for o in self.combatants)

    # ================================================================ player commands
    def player_weapon(self):
        st = self.state
        p = st.player
        mode = st.settings.get("weapon_mode", "melee")
        if mode == "ranged":
            item = p.equipment.get("ranged")
            if item and p.inventory.has(item):
                return self.data.item(item)["weapon"], item
            st.settings["weapon_mode"] = "melee"
        item = p.equipment.get("weapon")
        if item and p.inventory.has(item):
            return self.data.item(item)["weapon"], item
        return "fists", None

    def switch_weapon(self):
        st = self.state
        if not st.player.equipment.get("ranged"):
            self.events.append("No ranged weapon equipped.")
            return
        st.settings["weapon_mode"] = "ranged" if st.settings.get("weapon_mode") != "ranged" else "melee"
        wt, item = self.player_weapon()
        self.events.append(f"Switched to {self.data.item(item)['name'] if item else 'fists'}.")

    def attack(self, c, profile=None, item=None):
        """Start (or queue the next combo hit of) an attack."""
        if not c.alive or c.state in ("stagger", "dodge", "dead"):
            return False
        if c.state in ("windup", "active", "draw"):
            c.queued = True
            return False
        if c.state == "cast":
            c.set_state("idle")              # a cast flows straight into an attack
        if c.state == "recovery":
            p0 = c.profile or {}
            if c.combo_window > 0 and c.combo < rules.COMBO_MAX:
                pass
            elif c.state_t >= p0.get("recovery", 0.3) * rules.CANCEL_AFTER:
                c.combo = 0                  # cut the recovery short with a fresh attack
                c.set_state("idle")
            else:
                c.queued = True
                return False
        if c is self.player and profile is None:
            wt, item = self.player_weapon()
            if not self._has_ammo(wt, item):
                return False
            nxt = c.combo + 1 if c.state == "recovery" and c.combo_window > 0 else 1
            profile = rules.attack_profile(self.data, c.attrs(), c.skills(), wt, item, nxt)
            if self.data.weapons[wt]["class"] == "ranged":
                nxt = 1
            c.combo = nxt
            c.weapon_item = item
        c.profile = profile
        c.blocking = False
        c.hit_ids = set()
        c.queued = False
        if profile.get("chargeable") and c is self.player:
            c.set_state("draw")
            c.charge = 0.0
        else:
            c.set_state("windup")
        return True

    def release_draw(self, c):
        if c.state == "draw":
            c.set_state("active")
            self._fire(c, charge=1.0 + 0.8 * min(1.0, c.charge / 0.9))

    def kick(self, c):
        if not c.alive or c.state not in ("idle", "recovery") or c.kick_cd > 0:
            return
        c.profile = rules.kick_profile(c.attrs())
        c.combo = 0
        c.blocking = False
        c.hit_ids = set()
        c.kick_cd = 1.0
        c.set_state("windup")

    def dodge(self, c, vec):
        if not c.alive or c.dodge_cd > 0 or c.state in ("dodge", "stagger", "dead", "active") or c.has_status("root"):
            return
        if vec == (0, 0):
            vec = (-c.aim[0], -c.aim[1])
        c.dodge_vec = norm(*vec)
        c.blocking = False
        c.dodge_cd = rules.DODGE_COOLDOWN
        c.set_state("dodge")
        if c is self.player:
            self.sfx("dodge")

    def set_block(self, c, on):
        c.blocking = bool(on) and c.guard > 5 and c.state in ("idle", "recovery", "windup")
        if c.blocking and c.state == "windup":
            c.set_state("idle")

    def _has_ammo(self, wt, item):
        w = self.data.weapons[wt]
        ammo = w.get("ammo")
        inv = self.state.player.inventory
        if not ammo:
            return True
        need = item if ammo == "self" else ammo
        if need and inv.has(need):
            return True
        self.events.append(f"Out of {self.data.item(ammo)['name'] if ammo != 'self' else 'throwing weapons'}!")
        return False

    # ================================================================ spells
    def cast(self, c, spell, aim=None):
        st = self.state
        key = (c.cid, spell["name"])
        if self.spell_cd.get(key, 0) > 0:
            return False, f"{spell['name']} is recharging ({self.spell_cd[key]:.1f}s)."
        if not c.alive or c.state in ("stagger", "dodge", "active"):
            return False, None
        if c.state in ("windup", "draw"):
            c.profile = None                 # cancel a wind-up or bow draw into the spell
            c.charge = 0.0
            c.set_state("idle")
        conduct = 0.0
        if c.char:
            wt, item = self.player_weapon()
            if item:
                conduct = self.data.ores[self.data.item(item)["ore"]]["equipment"]["mana_conduct"]
        p = spell_rules.compute(self.data, spell, c.skills().get("magic", 0), conduct)
        if c.char:
            if c.char.mana < p["mana"]:
                return False, (f"Not enough mana for {spell['name']}: needs {p['mana']}, you have "
                               f"{c.char.mana:.0f}. Mana refills over time and when your weapon hits.")
            if p["hp_cost"] and c.char.hp <= p["hp_cost"]:
                return False, "Too weak to pay the blood price."
            c.char.mana -= p["mana"]
            if p["hp_cost"]:
                c.char.hp -= p["hp_cost"]
            c.char.train("magic", 2 + p["tier"] * 2, c.race_data)
        self.spell_cd[key] = p["cooldown"]
        self.sfx("heal" if p["stat"] == "heal" else "spell")
        aim = aim or c.aim
        c.blocking = False
        c.set_state("cast")
        c.profile = None
        self._launch_spell(c, p, aim)
        return True, None

    def _launch_spell(self, c, p, aim):
        mv = p["move"]
        x, y = c.x, c.y - 8
        if mv in ("projectile", "homing"):
            spd = max(120, p["speed"])
            bh = p.get("behavior", "standard")
            angles = (-0.21, 0.0, 0.21) if bh == "volley" else (0.0,)
            pay = dict(p, power=round(p["power"] * 0.6, 1)) if bh == "volley" else p
            base = math.atan2(aim[1], aim[0])
            for da in angles:
                ax, ay = math.cos(base + da), math.sin(base + da)
                pr = Projectile(x + ax * 8, y + ay * 8, ax * spd, ay * spd, c.team, c, rng_left=p["range"],
                                kind="spell", color=p["color"], radius=p.get("radius", 4), payload=pay,
                                homing=3.0 if mv == "homing" else 0.0, pierce=2 if bh == "piercing" else 0)
                self.projectiles.append(pr)
        elif mv == "beam":
            ex, ey = x + aim[0] * p["range"], y + aim[1] * p["range"]
            ex, ey = self._ray_end(x, y, ex, ey)
            eff = SpellEffect("beam", c, p, x, y, 0.25, aim)
            eff.end = (ex, ey)
            self.effects.append(eff)
            self.linger(c, p, ex, ey + 6)
            for o in self._spell_targets(c, p):
                if _seg_dist(x, y, ex, ey, o.x, o.y - 6) <= p["area"] + 6:
                    self.apply_payload(c, o, p, (x, y))
        elif mv == "wave":
            self.effects.append(SpellEffect("wave", c, p, x, y, p["area"] / max(60, p["speed"]) + 0.1))
        elif mv == "area":
            tx, ty = self._target_point(c, p["range"], aim)
            self.effects.append(SpellEffect("area", c, p, tx, ty, 0.7))
        elif mv == "ground":
            tx, ty = self._target_point(c, p["range"], aim)
            self._limit_persistent(c, "ground")
            self.effects.append(SpellEffect("ground", c, p, tx, ty, p["zone_duration"]))
        elif mv == "orbit":
            self.effects.append(SpellEffect("orbit", c, p, x, y, p["zone_duration"]))
        elif mv == "ward":
            self._limit_persistent(c, "ward")
            self.effects.append(SpellEffect("ward", c, p, c.x, c.y, p["zone_duration"]))
        elif mv == "burst" or (mv == "self" and p["target"] != "ally"):
            eff = SpellEffect("burst", c, p, c.x, c.y - 6, 0.3)
            self.effects.append(eff)
            for o in self._spell_targets(c, p):
                if (o is not c or p["target"] == "ally") and math.hypot(o.x - c.x, o.y - 6 - (c.y - 6)) <= p["area"]:
                    self.apply_payload(c, o, p, (c.x, c.y - 6))
            self.shake = max(self.shake, 1.0 + p["area"] / 80)
            self.linger(c, p, c.x, c.y)
        elif mv == "self":
            self.apply_payload(c, c, p, (c.x, c.y))
            self.effects.append(SpellEffect("aura_flash", c, p, c.x, c.y, 0.5))
        elif mv == "chain":
            pts = [(x, y)]
            hit = []
            cur = self._chain_first(c, p, aim)
            power = 1.0
            while cur is not None and len(hit) < p["chain_jumps"]:
                hit.append(cur)
                pts.append((cur.x, cur.y - 8))
                self.apply_payload(c, cur, dict(p, power=round(p["power"] * power, 1)), pts[-2])
                power *= 0.85
                cur = min((o for o in self._spell_targets(c, p) if o not in hit and o is not c
                           and math.hypot(o.x - cur.x, o.y - cur.y) <= p["area"]),
                          key=lambda o: math.hypot(o.x - cur.x, o.y - cur.y), default=None)
            if len(pts) == 1:
                pts.append((x + aim[0] * p["range"] * 0.6, y + aim[1] * p["range"] * 0.6))
            if len(hit):
                self.linger(c, p, pts[-1][0], pts[-1][1] + 8)
            eff = SpellEffect("chain", c, p, x, y, 0.35, aim)
            eff.points = pts
            self.effects.append(eff)
        elif mv == "trap":
            tx, ty = self._target_point(c, p["range"], aim)
            self._limit_persistent(c, "trap")
            self.effects.append(SpellEffect("trap", c, p, tx, ty + 4, p["zone_duration"]))
        elif mv == "barrier":
            self._limit_persistent(c, "barrier")
            eff = SpellEffect("barrier", c, p, c.x + aim[0] * p["range"], c.y - 4 + aim[1] * p["range"], p["zone_duration"], aim)
            self.effects.append(eff)
        elif mv == "aura":
            if p["target"] == "ally":
                self.apply_payload(c, c, p, (c.x, c.y))
                self.effects.append(SpellEffect("aura_flash", c, p, c.x, c.y, 0.5))
            else:
                self.effects.append(SpellEffect("aura", c, p, c.x, c.y, max(3.0, p["zone_duration"])))
        self._burst(x, y, p["color"], 8)

    def linger(self, c, p, x, y):
        """'Lingering' behaviour: a small, short-lived field where the spell struck."""
        if p.get("behavior") != "lingering" or c is None or p.get("lingered"):
            return
        f = dict(p, move="ground", lingered=True, power=round(p["power"] * 0.3, 1), area=max(18.0, p["area"] * 0.6),
                 zone_duration=round(2.5 * p.get("duration_mult", 1.0), 1))
        self._limit_persistent(c, "ground")
        self.effects.append(SpellEffect("ground", c, f, x, y, f["zone_duration"]))

    def _limit_persistent(self, c, kind):
        """Keep at most MAX_PERSISTENT lingering effects of one kind per caster (oldest fades first)."""
        mine = [e for e in self.effects if e.caster is c and e.kind == kind and not e.dead]
        for e in mine[:max(0, len(mine) - spell_rules.MAX_PERSISTENT + 1)]:
            e.dead = True

    def _chain_first(self, c, p, aim):
        best, bd = None, p["range"]
        for o in self._spell_targets(c, p):
            if o is c:
                continue
            d = math.hypot(o.x - c.x, o.y - c.y)
            if d < bd and rules.angle_between(aim, (o.x - c.x, o.y - c.y)) < 40:
                best, bd = o, d
        return best

    def _spell_targets(self, c, p):
        if p["target"] == "ally":
            return [o for o in self.combatants if o.alive and o.team == c.team and not self.hostile_between(c, o)]
        return self.strike_targets(c)

    def _target_point(self, c, rng, aim):
        best, bd = None, rng
        for o in self.foes_of(c):
            d = math.hypot(o.x - c.x, o.y - c.y)
            if d < bd and rules.angle_between(aim, (o.x - c.x, o.y - c.y)) < 50:
                best, bd = o, d
        if best:
            return best.x, best.y - 4
        return c.x + aim[0] * rng * 0.6, c.y + aim[1] * rng * 0.6

    def apply_payload(self, src, tgt, p, origin):
        """Apply a computed spell's effect to one target."""
        stat = p["stat"]
        if stat == "damage":
            prof = {"damage": p["power"], "knockback": 50, "stagger": 0.25, "skill": "magic", "scaling": [], "vfx_sub": p["style"],
                    "statuses": [(p["status"], *self._status_mag(p, 0.5))] if p["status"] not in ("none",) else []}
            self.hit(src, tgt, prof, origin)
        elif stat == "heal":
            tgt.hp = tgt.hp + p["power"]
            self.floaters.append([f"+{p['power']:.0f}", tgt.x, tgt.y - 26, 0.0, (120, 230, 120)])
        elif stat in ("strength", "speed", "dexterity", "health"):
            tgt.buffs[stat] = [p["power"], p["duration"]]
            self.floaters.append([f"+{stat[:3].upper()}", tgt.x, tgt.y - 26, 0.0, p["color"]])
        elif stat == "defense":
            tgt.shield = max(tgt.shield, p["power"] * 4)
            tgt.buffs["shield"] = [0, p["duration"]]
            self.floaters.append(["SHIELD", tgt.x, tgt.y - 26, 0.0, p["color"]])
        elif stat == "knockback":
            prof = {"damage": 1, "knockback": p["power"] * 2.2, "stagger": 0.5, "skill": "magic", "scaling": [],
                    "vfx_sub": p["style"]}
            self.hit(src, tgt, prof, origin)
        elif stat == "root":
            self.add_status(tgt, "root", 1.0, p["duration"])
            self.provoke(src, tgt)
        elif stat == "affliction":
            mag, dur = self._status_mag(p, 1.0)
            prof = {"damage": 1, "knockback": 10, "stagger": 0.1, "skill": "magic", "scaling": [], "vfx_sub": p["style"],
                    "statuses": [(p["status"], mag, dur)]}
            self.hit(src, tgt, prof, origin)

    def _status_mag(self, p, scale):
        kind, mag, dur = rules.status_info(p["status"])
        if kind == "dot":
            return p["power"] * 0.35 * scale + mag * scale, max(dur, p["duration"] if p["stat"] == "affliction" else dur)
        if kind == "pull":
            return p["power"] * 6 * scale, 0.0
        return mag, (p["duration"] if p["stat"] == "affliction" else dur * scale)

    # ================================================================ damage
    def hit(self, src, tgt, profile, origin, charge=1.0):
        if not tgt.alive:
            return None
        if src is not None and src.has_status("blind"):
            profile = dict(profile, miss_chance=0.5)
        res = rules.resolve_hit(profile, origin, tgt.defender_view(), self.rng, charge)
        self.provoke(src, tgt)
        if res["dodged"]:
            self.sfx("dodge")
            self.floaters.append(["dodge", tgt.x, tgt.y - 26, 0.0, (200, 200, 255)])
            self._vfx("dodge", src, tgt, profile, res, origin)
            if tgt.char:
                tgt.char.train("dodging", 3, tgt.race_data)
            return res
        if res["missed"]:
            self.floaters.append(["miss", tgt.x, tgt.y - 26, 0.0, (200, 200, 200)])
            return res
        dmg = res["damage"]
        if tgt.shield > 0:
            absorbed = min(tgt.shield, dmg)
            tgt.shield -= absorbed
            dmg -= absorbed
        tgt.hp = tgt.hp - dmg
        tgt.guard = max(0.0, tgt.guard - res["guard_damage"])
        if res["guard_broken"]:
            tgt.blocking = False
            self.floaters.append(["GUARD BREAK", tgt.x, tgt.y - 40, 0.0, (255, 160, 80)])
        # knockback away from origin
        kx, ky = norm(tgt.x - origin[0], (tgt.y - 6) - origin[1])
        tgt.kvx += kx * res["knockback"]
        tgt.kvy += ky * res["knockback"]
        if res["stagger_time"] > 0 and tgt.state != "dead":
            tgt.set_state("stagger")
            tgt.stagger_for = res["stagger_time"]
            tgt.profile = None
            tgt.charge = 0
        for name, mag, dur in res["statuses"]:
            self.add_status(tgt, name, mag, dur, origin)
        tgt.flash = 0.12
        self._vfx("hit", src, tgt, profile, res, origin, dmg)
        # weapon hits feed the attacker's mana (Set System rule in spells.mana_from_hit)
        if src is not None and src.char is not None and not res["blocked"] and src is not tgt:
            gain = spell_rules.mana_from_hit(dmg, profile.get("skill"))
            if gain > 0 and src.char.mana < src.char.max_mana:
                src.char.mana = min(src.char.max_mana, src.char.mana + gain)
                self._vfx("mana", src, src, profile, res, origin, gain)
        self.sfx("block" if res["blocked"] else ("heavy" if profile.get("knockback", 0) > 100 or res["stagger_time"] > 0.3 else "hit"))
        col = (255, 255, 255) if src and src.team == "player" else (255, 120, 100)
        if res["blocked"]:
            col = (160, 190, 255)
        label = f"{dmg:.0f}" + ("!" if res["backstab"] else "")
        self.floaters.append([label, tgt.x + self.rng.uniform(-4, 4), tgt.y - 28, 0.0, col])
        self._burst(tgt.x, tgt.y - 8, (230, 60, 50) if not res["blocked"] else (200, 210, 255), 5 if dmg > 3 else 2)
        if profile.get("knockback", 0) > 100 or res["stagger_time"] > 0.3:
            self.hitstop = 0.06
            self.shake = max(self.shake, 3.0 if tgt is self.player else 2.0)
        # training (Set System)
        if src is not None and src.char:
            for k, v in rules.xp_for_hit(profile, res).items():
                src.char.train(k, v, src.race_data)
        if tgt.char:
            tgt.char.train("health", dmg / 6, tgt.race_data)
            if res["blocked"]:
                tgt.char.train("blocking", 3, tgt.race_data)
        if tgt.hp <= 0:
            self.kill(tgt, src)
        return res

    def provoke(self, src, tgt):
        if src is None or src is tgt:
            return
        if tgt.team == "npc" or tgt.team == src.team or src.team == "npc" or src.cid in tgt.grudge:
            self._personal_violence(src, tgt)
            return
        tgt.last_attacker = src
        if not tgt.alerted:
            tgt.alerted = True
            if tgt.team == "enemy":
                self.alert_group(tgt)
        if not tgt.hostile and src.team == "player":
            tgt.hostile = True
            fac = tgt.enemy.get("faction") if tgt.enemy else None
            if fac:
                factions.change_rep(self.state, fac, -3, f"attacked a {tgt.name}")
            self.alert_group(tgt)

    def _personal_violence(self, src, tgt):
        """Someone hit a character who is not a team enemy. Reactions are decided by the Set System
        (aggression.py) and the victim's AI; this only routes them."""
        tgt.last_attacker = src
        tgt.alerted = True
        if src.cid in tgt.grudge:
            return
        tgt.grudge.add(src.cid)
        if tgt.ai is not None and hasattr(tgt.ai, "provoked"):
            tgt.ai.provoked(self, src)
        if src is not self.player or tgt is self.player:
            return
        st = self.state
        npc_id = tgt.npc["id"] if tgt.npc else None
        comp_id = getattr(tgt, "companion_id", None)
        near = [o for o in self.combatants if o.alive and o is not tgt and o is not src and o.team == "npc"
                and math.hypot(o.x - tgt.x, o.y - tgt.y) < 170]
        witnessed = bool(near) or npc_id is not None or comp_id is not None
        self.events += aggression.on_assault(st, npc_id or comp_id, tgt.name or "a stranger",
                                             is_companion=comp_id is not None, witnessed=witnessed)
        for o in near:
            if o.npc:
                aggression.witness(st, o.npc["id"], tgt.name or "a stranger")
        if witnessed or getattr(tgt, "is_guard", False):
            self.guards_respond(tgt.x, tgt.y)
        self._companions_react(tgt, killed=False)

    def guards_respond(self, x, y, radius=280):
        """Town guards who see or hear a crime come for the player (not in a town the player holds)."""
        from ..set_system import crime
        if crime.owner(self.state, crime.town_of(self.state)) == "player" or self.player is None:
            return 0
        n = 0
        for o in self.combatants:
            if getattr(o, "is_guard", False) and o.alive and math.hypot(o.x - x, o.y - y) <= radius \
                    and hasattr(o.ai, "join") and self.player.cid not in o.grudge:
                o.ai.join(self, self.player)
                o.ai._bark(self, "Halt, criminal!")
                n += 1
        return n

    def _companions_react(self, victim, killed):
        st = self.state
        victim_cid = getattr(victim, "companion_id", None)
        for co in self.companions():
            if co is victim or not co.alive or co.grudge or co.companion_id not in st.companions:
                continue
            kind, msg = aggression.companion_reaction(st, co.companion_id, victim_npc=victim.npc if not victim_cid else None,
                                                      victim_cid=victim_cid, killed=killed)
            aggression.companion_reacts(st, co.companion_id, kind, victim.name or "a stranger")
            if kind == "join" and not killed:
                co.grudge.add(victim.cid)
            elif kind == "defend":
                co.grudge.add(self.player.cid)
                co.alerted = True
            elif kind == "leave":
                co.companion_id = None
                co.fled = True
            if msg:
                self.events.append(msg)
                self.floaters.append([msg.split(":")[0] if ":" in msg else "!", co.x, co.y - 40, 0.0, (240, 220, 160)])

    def settle_conflicts(self):
        """Leaving the map mid-quarrel: companions who fought the player decide whether they stay (Set System)."""
        msgs = []
        if self.player is None:
            return msgs
        for c in self.companions():
            if c.alive and (self.player.cid in c.grudge or c.cid in self.player.grudge):
                verdict, msg = aggression.after_conflict(self.state, c.companion_id)
                if msg:
                    msgs.append(msg)
            c.grudge.clear()
        return msgs

    def execute(self, src, tgt):
        """A finishing blow on a defeated character. Permanent for named NPCs and companions."""
        st = self.state
        npc_id = tgt.npc["id"] if tgt.npc else getattr(tgt, "companion_id", None)
        if not aggression.can_kill(st, npc_id):
            self.events.append(f"{tgt.name} cannot be killed.")
            return False
        tgt.killed = True
        tgt.flash = 0.2
        self.sfx("heavy")
        self.shake = max(self.shake, 2.0)
        self._vfx("hit", src, tgt, {"weapon": (src.profile or {}).get("weapon"), "skill": "melee"},
                  {"stagger_time": 0.5}, (src.x, src.y - 6), 1.0)
        near = [o for o in self.combatants if o.alive and o.team == "npc" and math.hypot(o.x - tgt.x, o.y - tgt.y) < 200]
        was_companion = getattr(tgt, "companion_id", None)
        if was_companion and tgt.char:
            tgt.char.alive = False
        self.events += aggression.on_kill(st, npc_id, tgt.name or "a stranger", witnessed=bool(near) or npc_id is not None)
        for o in near:
            if o.npc:
                aggression.witness(st, o.npc["id"], tgt.name or "a stranger", "a killing")
            if o.ai is not None and hasattr(o.ai, "terrified"):
                o.ai.terrified(self, src)
        tgt.companion_id = None
        self._companions_react(tgt, killed=True)
        return True

    def alert_near(self, c, radius):
        """An alerted enemy rouses others of its kind nearby (same faction, or the same creature)."""
        for o in self.enemies():
            if o is c or o.alerted or not o.hostile:
                continue
            same = (c.enemy.get("faction") and o.enemy.get("faction") == c.enemy.get("faction")) or \
                getattr(o, "enemy_id", None) == getattr(c, "enemy_id", None)
            if same and math.hypot(o.x - c.x, o.y - c.y) <= radius:
                o.alerted = True
                self.alert_group(o)

    def surrender(self, c):
        """A broken human foe yields: stops fighting, joins the neutral side, waits for the player's decision."""
        from .bystander_ai import SurrenderedAI
        c.surrendered = True
        c.hostile = False
        c.alerted = False
        c.team = "npc"
        c.grudge = set()
        for o in self.combatants:
            o.grudge.discard(c.cid)
        c.blocking = False
        c.profile = None
        c.set_state("idle")
        self.tokens.discard(c.cid)
        c.ai = SurrenderedAI(c)
        self.floaters.append(["I yield!", c.x, c.y - 40, 0.0, (255, 235, 160)])
        self.events.append(f"{c.name} surrenders! Approach and press E to decide their fate.")

    def alert_group(self, c):
        for o in self.enemies():
            if o.group == c.group and o.group is not None:
                o.alerted = True
                o.hostile = o.hostile or c.hostile

    def add_status(self, tgt, name, mag, dur, origin=None):
        kind, _, _ = rules.status_info(name)
        if kind == "none":
            return
        if kind == "stagger":
            if tgt.alive:
                tgt.set_state("stagger")
                tgt.stagger_for = 0.35 + mag * 0.3
            return
        if kind == "pull" and origin:
            kx, ky = norm(origin[0] - tgt.x, origin[1] - tgt.y)
            tgt.kvx += kx * mag
            tgt.kvy += ky * mag
            return
        for s in tgt.statuses:
            if s["name"] == name:
                s["t"] = max(s["t"], dur)
                s["mag"] = max(s["mag"], mag)
                return
        tgt.statuses.append({"name": name, "kind": kind, "mag": mag, "t": dur, "tick": 0.0})

    def kill(self, tgt, src):
        tgt.set_state("dead")
        tgt.blocking = False
        self.tokens.discard(tgt.cid)
        if tgt is self.player:
            self.sfx("death")
            return
        if getattr(tgt, "companion_id", None):
            tgt.downed = True
            tgt.char.hp = 0.0
            self.events.append(f"{tgt.name} is down!")
            if src is self.player:
                aggression.on_defeat(self.state, tgt.companion_id, tgt.name, by_player=True)
            return
        if tgt.team == "npc":
            # townsfolk are beaten down, not killed (see aggression.py persistence rules)
            tgt.downed = True
            tgt.statuses = []
            self.events += aggression.on_defeat(self.state, tgt.npc["id"] if tgt.npc else None, tgt.name or "a stranger",
                                                by_player=src is self.player)
            return
        self.kills.append(tgt.enemy_id)
        st = self.state
        e = tgt.enemy
        from ..set_system import jobs, world_events
        jobs.note_kill(st, tgt.enemy_id)
        if e.get("faction") == "hollow":
            world_events.hollow_kill(st)
        if e.get("elite_event"):
            world_events.elite_slain(st, e["elite_event"])
            jobs.on_elite_killed(st, e["elite_event"])
            self.events.append(f"{e['name']} is slain!")
        # loot drops
        wealth = 1.0 + 0.15 * self.data.location(st.location).get("danger", 1) if st.location in self.data.locations else 1.0
        for item, (lo, hi) in e["loot"].items():
            n = self.rng.randint(lo, hi)
            if item == "marks":
                n = int(round(n * wealth))      # richer pickings in more dangerous places
            if n > 0:
                if item == "marks" and n >= 6:       # coins burst out in a few piles
                    piles = min(4, 1 + n // 8)
                    for k in range(piles):
                        self.drop(item, n // piles + (n % piles if k == 0 else 0), tgt.x, tgt.y)
                else:
                    self.drop(item, n, tgt.x, tgt.y)
        # gear stays on the body: search it (E) to see what they carried
        from ..set_system import loot as loot_rules
        danger = self.data.location(st.location).get("danger", 1) if st.location in self.data.locations else 1
        tgt.loot = loot_rules.enemy_gear(self.data, e, self.rng, danger)
        if src is not None and src.char:
            src.char.train("health", 1.0, src.race_data)
            src.char.xp_total += e["xp"] * 0.5
        st.stats["kills"] = st.stats.get("kills", 0) + 1
        fac = e.get("faction")
        if fac:
            factions.change_rep(st, fac, -2, f"killed a {e['name']}")
            from ..set_system import companions as comp_mod
            self.events += comp_mod.react_to_kill(st, fac)
            if fac == "hollow":
                factions.change_rep(st, "crown", 1, "killed Hollow outlaws")
                factions.change_rep(st, "caravans", 1, "killed Hollow outlaws")
        self.events.append(f"{e['name']} defeated.")

    # ================================================================ update
    def update(self, dt, lmap):
        if self.hitstop > 0:
            self.hitstop -= dt
            return
        self.shake = max(0.0, self.shake - dt * 12)
        fighting = self.in_combat
        for c in self.combatants:
            if c.char is not None and c.alive and c.char.mana < c.char.max_mana:
                c.char.mana = min(c.char.max_mana, c.char.mana + spell_rules.regen_per_second(c.char, fighting) * dt)
        for c in self.combatants:
            self._update_combatant(c, dt, lmap)
        for c in self.combatants:
            if c.ai and c.alive:
                c.ai.update(self, lmap, dt)
        self._update_projectiles(dt, lmap)
        self._update_effects(dt)
        for k in list(self.spell_cd):
            self.spell_cd[k] -= dt
            if self.spell_cd[k] <= 0:
                del self.spell_cd[k]
        for f in self.floaters:
            f[3] += dt
        self.floaters = [f for f in self.floaters if f[3] < 0.9]
        for p in self.particles:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[3] += 140 * dt
            p[4] -= dt
        self.particles = [p for p in self.particles if p[4] > 0]
        self._move_pickups(dt, lmap)
        self._collect_pickups()
        # downed companions get back up once the fighting is over
        if not self.in_combat:
            self.calm_t = getattr(self, "calm_t", 0.0) + dt
            if self.calm_t > 3.0:
                for c in self.combatants:
                    if c.team == "npc" and c.downed and not c.killed and c.state == "dead" and self.calm_t > 5.0:
                        c.downed = False
                        c.hp = max(1.0, c.max_hp * 0.25)
                        c.set_state("idle")
                        c.dead_t = 0.0
                        if c.ai is not None and hasattr(c.ai, "recovered"):
                            c.ai.recovered(self)
                for c in self.companions():
                    if c.grudge and c.alive and self.calm_t > 3.0:
                        with_player = self.player is not None and (self.player.cid in c.grudge or c.cid in self.player.grudge)
                        for o in self.combatants:
                            o.grudge.discard(c.cid)
                        c.grudge.clear()
                        if not with_player:
                            continue
                        verdict, msg = aggression.after_conflict(self.state, c.companion_id)
                        if verdict == "leave":
                            c.companion_id = None
                            c.fled = True
                        if msg:
                            self.events.append(msg)
                for c in self.companions():
                    if getattr(c, "downed", False) and not c.killed:
                        c.downed = False
                        c.char.hp = max(1.0, c.char.max_hp * 0.2)
                        c.char.alive = True
                        c.set_state("idle")
                        c.dead_t = 0.0
                        self.events.append(f"{c.name} staggers back to their feet.")
        else:
            self.calm_t = 0.0
        # remove faded corpses and escaped enemies
        self.combatants = [c for c in self.combatants if not (c.state == "dead" and c.dead_t > 1.6 and c is not self.player
                                                                 and not c.char and c.team != "npc"
                                                                 and not getattr(c, "loot", None)) and not c.fled]

    def _update_combatant(self, c, dt, lmap):
        c.state_t += dt
        c.flash = max(0.0, c.flash - dt)
        c.dodge_cd = max(0.0, c.dodge_cd - dt)
        c.kick_cd = max(0.0, c.kick_cd - dt)
        c.combo_window = max(0.0, c.combo_window - dt)
        c.telegraph = max(0.0, c.telegraph - dt)
        if c.state == "dead":
            c.dead_t += dt
            c.moving = False
            return
        if not c.blocking:
            c.guard = min(rules.GUARD_MAX, c.guard + rules.GUARD_REGEN * dt)
        # statuses
        for s in c.statuses:
            s["t"] -= dt
            if s["kind"] == "dot":
                s["tick"] += dt
                if s["tick"] >= 0.5:
                    s["tick"] -= 0.5
                    c.hp = c.hp - s["mag"] * 0.5
                    self.floaters.append([f"{s['mag'] * 0.5:.0f}", c.x, c.y - 26, 0.0, (230, 160, 60)])
                    if c.hp <= 0 and c.alive:
                        self.kill(c, c.last_attacker)
                        return
        c.statuses = [s for s in c.statuses if s["t"] > 0]
        for k in list(c.buffs):
            c.buffs[k][1] -= dt
            if c.buffs[k][1] <= 0:
                del c.buffs[k]
                if k == "shield":
                    c.shield = 0
        # knockback motion
        if abs(c.kvx) + abs(c.kvy) > 1:
            self._push(c, lmap, c.kvx * dt, c.kvy * dt)
            decay = math.exp(-FRICTION * dt)
            c.kvx *= decay
            c.kvy *= decay
        else:
            c.kvx = c.kvy = 0.0
        # state machine
        p = c.profile
        if c.state == "dodge":
            spd = 210 * (1 + c.attrs()["speed"] / 150)
            self._push(c, lmap, c.dodge_vec[0] * spd * dt, c.dodge_vec[1] * spd * dt)
            c.anim_t += dt * 3
            if c.state_t >= rules.DODGE_TIME:
                c.set_state("idle")
        elif c.state == "stagger":
            if c.state_t >= getattr(c, "stagger_for", 0.3):
                c.set_state("idle")
        elif c.state == "draw":
            c.charge += dt
        elif c.state == "cast":
            if c.state_t >= CAST_TIME:
                c.set_state("idle")
                if c.queued and c is self.player:
                    c.queued = False
                    self.attack(c)
        elif c.state == "windup" and p:
            if c.state_t >= p["windup"]:
                c.set_state("active")
                if p["class"] == "melee" and c is self.player:
                    self.sfx("kick" if p["weapon"] == "kick" else "swing")
                if p["class"] == "ranged":
                    self._fire(c)
        elif c.state == "active" and p:
            if p["class"] == "melee":
                self._melee_sweep(c)
            if c.state_t >= p["active"]:
                c.set_state("recovery")
                c.combo_window = rules.COMBO_WINDOW
        elif c.state == "recovery" and p:
            if c.queued and c.combo_window > 0 and c.combo < rules.COMBO_MAX and p["class"] == "melee" \
                    and p["weapon"] != "kick" and c is self.player:
                c.queued = False
                c.set_state("idle")
                self.attack(c)
            elif c.state_t >= p["recovery"]:
                c.set_state("idle")
                c.combo = 0 if c.combo >= rules.COMBO_MAX else c.combo
                self.tokens.discard(c.cid)
                if c.queued and c is self.player:
                    c.queued = False
                    self.attack(c)
        elif c.state == "idle" and c.combo and c.combo_window <= 0:
            c.combo = 0

    def _push(self, c, lmap, dx, dy):
        if not c._blocked(lmap, c.x + dx, c.y):
            c.x += dx
        else:
            c.kvx *= -0.3
        if not c._blocked(lmap, c.x, c.y + dy):
            c.y += dy
        else:
            c.kvy *= -0.3

    def _melee_sweep(self, c):
        p = c.profile
        origin = (c.x, c.y - 6)
        landed = False
        for o in self.strike_targets(c):
            if o.cid in c.hit_ids or not o.alive:
                continue
            if rules.in_arc(origin, c.aim, (o.x, o.y - 6), p["reach"], p["arc"]):
                c.hit_ids.add(o.cid)
                landed = True
                self.hit(c, o, p, origin)
                if not (p["arc"] >= 100):  # narrow weapons hit one target per swing
                    break
        # a deliberate blow on someone lying defeated finishes them (player, hostile intent only)
        if not landed and c is self.player and self.intent and p.get("weapon") != "kick":
            for o in self.combatants:
                if o.downed and not o.killed and o.state == "dead" and o.cid not in c.hit_ids \
                        and rules.in_arc(origin, c.aim, (o.x, o.y - 2), p["reach"] + 4, max(60, p["arc"])):
                    c.hit_ids.add(o.cid)
                    self.execute(c, o)
                    break

    def _fire(self, c, charge=1.0):
        p = c.profile
        st = self.state
        wt = p["weapon"]
        if c.char:
            w = self.data.weapons[wt]
            ammo = w.get("ammo")
            inv = c.char.inventory
            item = getattr(c, "weapon_item", None)
            used = item if ammo == "self" else ammo
            if used and inv.has(used):
                inv.remove(used)
                if ammo == "self" and not inv.has(used):
                    c.char.equipment["ranged"] = None
                    if c is self.player:
                        st.settings["weapon_mode"] = "melee"
        pellets = p.get("pellets", 1)
        spread = math.radians(p["arc"]) if pellets > 1 else 0.0
        base = math.atan2(c.aim[1], c.aim[0])
        kind = {"bow": "arrow", "crossbow": "bolt", "throwing": "knife", "firelock": "pellet"}.get(wt, "arrow")
        for i in range(pellets):
            a = base + (spread * (i / (pellets - 1) - 0.5) if pellets > 1 else 0.0) + self.rng.uniform(-0.03, 0.03)
            spd = p["projectile_speed"] or 260
            prof = dict(p)
            if pellets > 1:
                prof["knockback"] = p["knockback"] / pellets * 1.6
            pr = Projectile(c.x + math.cos(a) * 8, c.y - 8 + math.sin(a) * 8, math.cos(a) * spd, math.sin(a) * spd,
                            c.team, c, prof, rng_left=p["reach"], kind=kind, pierce=p.get("pierce", 0), charge=charge)
            pr.drop_item = getattr(c, "weapon_item", None) if kind == "knife" and c.char else None
            self.projectiles.append(pr)
        self.sfx("firelock" if wt == "firelock" else "bow")
        if wt == "firelock":
            self.shake = max(self.shake, 2.5)
            self._burst(c.x + c.aim[0] * 12, c.y - 8 + c.aim[1] * 12, (255, 200, 90), 10)

    def _update_projectiles(self, dt, lmap):
        for pr in self.projectiles:
            pr.t += dt
            if pr.homing:
                tgt = self._nearest_foe(pr.owner, pr.x, pr.y, 200)
                if tgt:
                    dx, dy = norm(tgt.x - pr.x, tgt.y - 8 - pr.y)
                    spd = math.hypot(pr.vx, pr.vy)
                    cx, cy = norm(pr.vx, pr.vy)
                    nx, ny = norm(cx + dx * pr.homing * dt, cy + dy * pr.homing * dt)
                    pr.vx, pr.vy = nx * spd, ny * spd
            step = math.hypot(pr.vx, pr.vy) * dt
            pr.x += pr.vx * dt
            pr.y += pr.vy * dt
            pr.range_left -= step
            if lmap.solid(int(pr.x // TILE), int(pr.y // TILE)) or pr.range_left <= 0:
                self._projectile_end(pr)
                continue
            blocked = False
            for e in self.effects:
                if e.kind == "barrier" and pr.owner is not None and pr.owner is not e.caster \
                        and self.hostile_between(pr.owner, e.caster) and self._barrier_dist(e, pr.x, pr.y) < 5:
                    blocked = True
                    break
            if blocked:
                self._projectile_end(pr)
                continue
            for o in self.combatants:
                if not o.alive or o.cid in pr.hit or not self.can_hit(pr.owner, o, pr.team):
                    continue
                if math.hypot(o.x - pr.x, (o.y - 7) - pr.y) <= pr.radius + 6:
                    pr.hit.add(o.cid)
                    if pr.payload:
                        self.apply_payload(pr.owner, o, pr.payload, (pr.x - pr.vx * 0.05, pr.y - pr.vy * 0.05))
                    else:
                        self.hit(pr.owner, o, pr.profile, (pr.x - pr.vx * 0.05, pr.y - pr.vy * 0.05), pr.charge)
                    if pr.pierce > 0:
                        pr.pierce -= 1
                    else:
                        self._projectile_end(pr, on_target=True)
                        break
        self.projectiles = [p for p in self.projectiles if not p.dead]

    def _projectile_end(self, pr, on_target=False):
        pr.dead = True
        if getattr(pr, "drop_item", None):
            self.pickups.append({"item": pr.drop_item, "qty": 1, "x": pr.x - pr.vx * 0.03, "y": pr.y - pr.vy * 0.03 + 8})
        if pr.payload:
            self._burst(pr.x, pr.y, pr.payload["color"], 6)
            self.linger(pr.owner, pr.payload, pr.x, pr.y + 6)

    def _nearest_foe(self, c, x, y, radius):
        best, bd = None, radius
        for o in self.foes_of(c) if c else []:
            d = math.hypot(o.x - x, o.y - y)
            if d < bd:
                best, bd = o, d
        return best

    def _update_effects(self, dt):
        for e in self.effects:
            e.t += dt
            p = e.spell
            c = e.caster
            if e.kind == "wave":
                r = min(p["area"], e.t * max(60, p["speed"]))
                for o in self._spell_targets(c, p):
                    if o.cid not in e.hit and abs(math.hypot(o.x - e.x, o.y - 6 - e.y) - r) < 10:
                        e.hit.add(o.cid)
                        self.apply_payload(c, o, p, (e.x, e.y))
            elif e.kind == "area" and not e.hit and e.t >= 0.6:
                e.hit.add(-1)
                for o in self._spell_targets(c, p):
                    if math.hypot(o.x - e.x, o.y - 6 - e.y) <= p["area"]:
                        self.apply_payload(c, o, p, (e.x, e.y))
                self._burst(e.x, e.y, p["color"], 16)
                self.shake = max(self.shake, 1.5)
                self.linger(c, p, e.x, e.y)
            elif e.kind in ("ground", "ward", "aura"):
                if e.kind == "aura":
                    e.x, e.y = c.x, c.y
                e.tick += dt
                if e.tick >= (0.5 if e.kind == "ground" else 1.0):
                    e.tick = 0.0
                    rad = p["area"] if e.kind != "aura" else 34
                    for o in self._spell_targets(c, p):
                        if math.hypot(o.x - e.x, o.y - 6 - e.y) <= rad:
                            self.apply_payload(c, o, p, (e.x, e.y))
            elif e.kind == "trap":
                if not e.hit and e.t > 0.4:
                    trigger = [o for o in self.foes_of(c) if math.hypot(o.x - e.x, o.y - e.y) <= p["area"] * 0.6]
                    if trigger:
                        e.hit.add(-1)
                        for o in self._spell_targets(c, p):
                            if (o is not c or p["target"] == "ally") and math.hypot(o.x - e.x, o.y - 6 - e.y) <= p["area"]:
                                self.apply_payload(c, o, p, (e.x, e.y))
                        self._burst(e.x, e.y, p["color"], 14)
                        self.shake = max(self.shake, 1.5)
                        e.duration = e.t + 0.35          # linger briefly for the burst visual
                        e.sprung = True
            elif e.kind == "barrier":
                e.tick += dt
                if e.tick >= 0.4:
                    e.tick = 0.0
                    for o in self._spell_targets(c, p):
                        if o is not c and self._barrier_dist(e, o.x, o.y - 6) < 8:
                            if p["target"] == "ally":
                                if e.cooldowns.get(o.cid, 0) <= e.t:
                                    e.cooldowns[o.cid] = e.t + 2.0
                                    self.apply_payload(c, o, p, (e.x, e.y))
                            else:
                                nx, ny = norm(o.x - e.x, o.y - e.y)
                                o.kvx += nx * 120
                                o.kvy += ny * 120
                                if e.cooldowns.get(o.cid, 0) <= e.t:
                                    e.cooldowns[o.cid] = e.t + 1.0
                                    self.apply_payload(c, o, p, (e.x, e.y))
            elif e.kind == "orbit":
                e.x, e.y = c.x, c.y - 8
                for k in range(3):
                    a = e.t * 4 + k * math.tau / 3
                    mx, my = e.x + math.cos(a) * 24, e.y + math.sin(a) * 24
                    for o in self._spell_targets(c, p):
                        if o is c:
                            continue
                        if e.cooldowns.get(o.cid, 0) <= e.t and math.hypot(o.x - mx, o.y - 6 - my) < p["area"] + 6:
                            e.cooldowns[o.cid] = e.t + 0.6
                            self.apply_payload(c, o, p, (mx, my))
            if e.t >= e.duration or (not c.alive and e.kind not in ("trap", "barrier", "ground", "ward")):
                e.dead = True
        self.effects = [e for e in self.effects if not e.dead]

    @staticmethod
    def _barrier_ends(e):
        """The barrier is a straight wall across the caster's aim, `area` long."""
        px, py = -e.aim[1], e.aim[0]
        half = e.spell["area"] / 2
        return (e.x - px * half, e.y - py * half), (e.x + px * half, e.y + py * half)

    def _barrier_dist(self, e, x, y):
        (ax, ay), (bx, by) = self._barrier_ends(e)
        return _seg_dist(ax, ay, bx, by, x, y)

    def drop(self, item, qty, x, y, speed=55.0):
        """Spill an item out of a body or container: it pops up, bounces and settles where the player can grab it."""
        ang = self.rng.uniform(0, math.tau)
        sp = self.rng.uniform(0.5, 1.0) * speed
        self.pickups.append({"item": item, "qty": qty, "x": x, "y": y + 2, "vx": math.cos(ang) * sp,
                             "vy": math.sin(ang) * sp * 0.6, "z": 6.0, "vz": self.rng.uniform(70, 110), "t": 0.0})

    def _move_pickups(self, dt, lmap):
        for pk in self.pickups:
            if "vz" not in pk:
                continue
            pk["t"] += dt
            if pk["z"] > 0 or pk["vz"] > 0:
                nx, ny = pk["x"] + pk["vx"] * dt, pk["y"] + pk["vy"] * dt
                if lmap is None or not lmap.solid(int(nx // TILE), int(ny // TILE)):
                    pk["x"], pk["y"] = nx, ny
                else:
                    pk["vx"], pk["vy"] = -pk["vx"] * 0.4, -pk["vy"] * 0.4
                pk["vz"] -= 420 * dt
                pk["z"] += pk["vz"] * dt
                if pk["z"] <= 0:
                    pk["z"] = 0.0
                    if pk["vz"] < -40:              # bounce
                        pk["vz"] = -pk["vz"] * 0.35
                        pk["vx"] *= 0.5
                        pk["vy"] *= 0.5
                    else:
                        pk["vz"] = 0.0
                        pk["vx"] = pk["vy"] = 0.0

    def _collect_pickups(self):
        p = self.player
        if p is None or not p.alive:
            return
        keep = []
        for pk in self.pickups:
            if pk.get("t", 1.0) > 0.35 and math.hypot(pk["x"] - p.x, pk["y"] - p.y) < PICKUP_RADIUS:
                self.sfx("coin" if pk["item"] == "marks" else "pickup")
                if pk["item"] == "marks":
                    self.state.gold += pk["qty"]
                    self.events.append(f"+{pk['qty']} marks")
                else:
                    self.state.player.inventory.add(pk["item"], pk["qty"])
                    self.events.append(f"+{pk['qty']} {self.data.item(pk['item'])['name']}")
            else:
                keep.append(pk)
        self.pickups = keep

    def _vfx(self, kind, src, tgt, profile, res, origin, dmg=0.0):
        """Record a presentation-only event; never read by gameplay code."""
        if len(self.vfx_events) > 64:
            del self.vfx_events[:32]
        self.vfx_events.append({"kind": kind, "src": src, "tgt": tgt, "weapon": profile.get("weapon"),
                                "sub": profile.get("vfx_sub"), "skill": profile.get("skill"), "blocked": res.get("blocked", False),
                                "guard_broken": res.get("guard_broken", False), "backstab": res.get("backstab", False),
                                "stagger": res.get("stagger_time", 0.0), "knockback": res.get("knockback", 0.0),
                                "dmg": dmg, "origin": origin, "x": tgt.x, "y": tgt.y})

    def _burst(self, x, y, color, n):
        for _ in range(n):
            a = self.rng.uniform(0, math.tau)
            s = self.rng.uniform(30, 90)
            self.particles.append([x, y, math.cos(a) * s, math.sin(a) * s - 40, self.rng.uniform(0.2, 0.45), color])

    def _ray_end(self, x, y, ex, ey):
        steps = int(math.hypot(ex - x, ey - y) // 6) + 1
        for i in range(1, steps + 1):
            px, py = x + (ex - x) * i / steps, y + (ey - y) * i / steps
            if self.map.solid(int(px // TILE), int(py // TILE)):
                return px, py
        return ex, ey

    def line_of_sight(self, a, b):
        ex, ey = self._ray_end(a.x, a.y - 8, b.x, b.y - 8)
        return math.hypot(ex - b.x, ey - (b.y - 8)) < 8

    # ================================================================ tokens (fairness: limited simultaneous attackers)
    def request_token(self, c, limit=2):
        if c.cid in self.tokens:
            return True
        if len(self.tokens) < limit:
            self.tokens.add(c.cid)
            return True
        return False


def _seg_dist(x1, y1, x2, y2, px, py):
    dx, dy = x2 - x1, y2 - y1
    L = dx * dx + dy * dy
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / L))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def enemy_look(e):
    col = list(e["color"])
    dark = [max(0, int(c * 0.55)) for c in col]
    return {"race": "human" if e["shape"] == "humanoid" else e["shape"], "shape": e["shape"],
            "skin": [190, 170, 150] if e["shape"] == "humanoid" else col, "hair": dark, "shirt": col, "pants": dark,
            "hair_style": 2, "hood": e.get("faction") == "hollow"}


def npc_fighter(data, npc):
    """An enemy-style combat definition built from a named NPC's character sheet (duels, Phase 6 foes)."""
    a = npc["attributes"]
    sk = npc["skills"]
    weapon, dmg = "fists", 4.0
    for item in npc["equipment"]:
        it = data.items.get(item)
        if it and it["type"] == "weapon" and data.weapons[it["weapon"]]["class"] == "melee":
            weapon, dmg = it["weapon"], it["damage"]
            break
    p = npc["personality"]
    if p["intelligence"] >= 8 and p["confidence"] >= 7:
        arch = "intelligent"
    elif p["aggression"] >= 7:
        arch = "aggressive"
    elif sk.get("blocking", 0) >= 35 or p["loyalty"] >= 9:
        arch = "defensive"
    elif a["speed"] >= 15:
        arch = "fast"
    elif a["strength"] >= 24:
        arch = "heavy"
    else:
        arch = "aggressive"
    skill = sk.get(data.weapons[weapon]["skill"], 0)
    return {"name": npc["name"], "archetype": arch, "faction": None, "hp": 40 + a["health"] * 3,
            "damage": round(dmg * (0.6 + a["strength"] / 30) * (1 + skill / 150), 1), "weapon": weapon,
            "speed": 55 + a["speed"] * 1.5, "armor": 2 + sk.get("blocking", 0) / 20,
            "attack_range": max(14, data.weapons[weapon]["reach"]), "aggro": 600, "flee_below": 0, "pack": [1, 1],
            "loot": {}, "xp": 30, "color": [120, 120, 120], "shape": "humanoid",
            "blocks": sk.get("blocking", 0) >= 20 or arch == "defensive", "npc": npc["id"]}
