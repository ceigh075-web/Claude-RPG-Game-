"""Boss fight runtime: phases by health, summoned minions, enrage, and telegraphed area attacks.

The boss itself is a normal enemy combatant driven by EnemyAI; this controller adds the set pieces on top.
Telegraphs are warning rings on the ground that strike after a delay, so they can always be dodged."""
import math

BARK = (255, 220, 160)


class BossFight:
    def __init__(self, world, c, boss_id):
        self.world = world
        self.c = c
        self.id = boss_id
        self.d = world.data.bosses[boss_id]
        self.phase = 0
        self.timer = self.d["attack"]["every"] * 0.6
        self.every = self.d["attack"]["every"]
        self.engaged = False
        self.enraged = False
        self.done = False

    @property
    def name(self):
        return self.d["name"]

    def _bark(self, text):
        self.world.floaters.append([text, self.c.x, self.c.y - 60, 0.0, BARK])
        self.world.events.append(f"{self.name}: \"{text}\"" if not text.endswith("...") and "!" in text else text)

    def update(self, dt):
        w, c = self.world, self.c
        if self.done:
            return
        if not c.alive:
            self.done = True
            return
        p = w.player
        if not self.engaged:
            if c.alerted or (p is not None and math.hypot(p.x - c.x, p.y - c.y) < 190):
                self.engaged = True
                c.alerted = True
                w.shake = max(w.shake, 4.0)
                w.events.append(self.d["intro"])
            return
        # phases
        frac = c.hp / max(1.0, c.max_hp)
        while self.phase < len(self.d["phases"]) and frac <= self.d["phases"][self.phase]["at"]:
            self._enter_phase(self.d["phases"][self.phase])
            self.phase += 1
        # signature attack
        self.timer -= dt
        if self.timer <= 0 and c.state not in ("stagger", "dead"):
            self.timer = self.every
            self._telegraph()

    def _enter_phase(self, ph):
        w, c = self.world, self.c
        if ph.get("say"):
            self._bark(ph["say"])
        w.shake = max(w.shake, 3.0)
        for eid, n in ph.get("summon", []):
            for k in range(n):
                ang = (k + 1) * 2.1 + self.phase
                x, y = c.x + math.cos(ang) * 40, c.y + math.sin(ang) * 30
                tx, ty = int(x // 16), int(y // 16)
                if w.map is not None and w.map.solid(tx, ty):
                    x, y = c.x, c.y
                m = w.spawn_enemy(eid, x, y, group=c.group, hostile=True)
                m.alerted = True
                w._burst(x, y - 8, (200, 60, 60), 10)
        if ph.get("enrage"):
            k = ph["enrage"]
            c.enemy = dict(c.enemy, damage=round(c.enemy["damage"] * k, 1), speed=c.enemy["speed"] * min(1.25, k))
            self.enraged = True
        if ph.get("every"):
            self.every = ph["every"]

    def _telegraph(self):
        """Mark the ground; it erupts after the delay. Some bosses aim at the target, others slam around themselves."""
        w, c, a = self.world, self.c, self.d["attack"]
        p = w.player
        spots = []
        n = a.get("around_target", 0)
        if n and p is not None:
            spots.append((p.x, p.y - 4))
            for k in range(n):
                ang = k * math.tau / n + w.rng.uniform(0, 1)
                spots.append((p.x + math.cos(ang) * a["radius"] * 1.3, p.y - 4 + math.sin(ang) * a["radius"]))
        else:
            spots.append((c.x, c.y - 4))
        for x, y in spots:
            w.telegraphs.append({"x": x, "y": y, "r": a["radius"], "t": 0.0, "delay": a["telegraph"], "src": c,
                                 "damage": a["damage"] * (1.25 if self.enraged else 1.0), "status": a.get("status"),
                                 "name": a["name"], "color": (230, 70, 50)})
        self._bark(a["name"] + "!")


def update_telegraphs(world, dt):
    """Advance warning rings; when one completes it strikes everyone hostile to its source inside it."""
    keep = []
    for tg in world.telegraphs:
        tg["t"] += dt
        if tg["t"] < tg["delay"]:
            keep.append(tg)
            continue
        src = tg["src"]
        prof = {"damage": tg["damage"], "knockback": 170, "stagger": 0.45, "skill": "melee", "scaling": [],
                "weapon": "fists", "class": "melee", "arc": 360, "reach": tg["r"], "windup": 0.0, "active": 0.0,
                "recovery": 0.0, "statuses": [(tg["status"], 4.0, 3.0)] if tg.get("status") and tg["status"] != "stagger" else []}
        for o in world.combatants:
            if o is src or not o.alive or not world.hostile_between(src, o):
                continue
            if math.hypot(o.x - tg["x"], (o.y - 4) - tg["y"]) <= tg["r"]:
                world.hit(src, o, prof, (tg["x"], tg["y"]))
        world._burst(tg["x"], tg["y"], tg["color"], 22)
        world.shake = max(world.shake, 3.5)
    world.telegraphs = keep
