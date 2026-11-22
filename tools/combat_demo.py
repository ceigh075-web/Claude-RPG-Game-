"""Headless combat demo through the real scenes, with a simple bot player. Saves screenshots.

    python tools/combat_demo.py OUT_DIR
"""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame  # noqa: E402

from game.core.game import Game  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else "combat_shots"
os.makedirs(OUT, exist_ok=True)
DT = 1 / 60


def shot(game, name):
    pygame.image.save(game.screen, os.path.join(OUT, name + ".png"))
    print("screenshot", name)


def bot_step(scene, t):
    """Aim at the nearest foe; block telegraphed hits, otherwise attack, kick, cast."""
    w = scene.combat
    pc = scene.player
    foes = [c for c in w.enemies() if c.alive and c.hostile]
    if not foes:
        return
    f = min(foes, key=lambda c: math.hypot(c.x - pc.x, c.y - pc.y))
    d = math.hypot(f.x - pc.x, f.y - pc.y)
    pc.aim = ((f.x - pc.x) / d, (f.y - pc.y) / d) if d else (1, 0)
    from game.gameplay.combat import facing_from
    pc.facing = facing_from(pc.aim)
    threatened = any(c.state == "windup" and math.hypot(c.x - pc.x, c.y - pc.y) < 40 for c in foes)
    if threatened and pc.state == "idle":
        w.set_block(pc, True)
        return
    w.set_block(pc, False)
    if d < 30:
        if int(t * 10) % 17 == 0:
            w.kick(pc)
        else:
            w.attack(pc)
    elif d < 140 and int(t * 10) % 25 == 0:
        w.cast(pc, scene.state.spellbook[0])
    else:
        pc.move(scene.map, f.x - pc.x, f.y - pc.y, DT)


def fight(game, seconds, shots_at, prefix):
    scene = game.scenes.top
    t = 0.0
    taken = set()
    while t < seconds:
        if type(game.scenes.top).__name__ in ("LocalScene", "ArenaScene"):
            bot_step(game.scenes.top, t)
        game.step(DT, [])
        t += DT
        for s in shots_at:
            if t >= s and s not in taken:
                taken.add(s)
                shot(game, f"{prefix}_{s:04.1f}")
        if type(game.scenes.top).__name__ == "MessageScene":
            shot(game, f"{prefix}_result")
            return
    return scene


def main():
    g = Game(headless=True, save_dir=os.path.join(OUT, "saves"))
    g.new_game("Rook", "human", {"race": "human", "skin": [198, 146, 104], "hair": [40, 30, 20],
                                 "shirt": [60, 90, 150], "pants": [60, 50, 40], "hair_style": 0}, "they/them")
    st = g.state
    p = st.player
    p.inventory.add("longsword_greyvein")
    p.equipment["weapon"] = "longsword_greyvein"
    for a in ("strength", "dexterity", "health"):
        p.attributes[a] = 22
    p.skills["melee"] = 20
    p.hp = p.max_hp
    p.mana = p.max_mana
    # 1) wilderness fight in Greywood
    st.location = "greywood"
    st.discovered.add("greywood")
    st.clock.minutes = 13 * 60
    st.local_pos = None
    g.enter_world()
    scene = g.scenes.top
    sp = scene.map.spawns[0]
    scene.player.x, scene.player.y = sp["x"] * 16 - 70, sp["y"] * 16 + 8
    for _ in range(5):
        g.step(DT, [])
    fight(g, 14, [1.0, 2.5, 4.0, 6.0, 9.0], "greywood")
    print("kills:", st.stats.get("kills", 0), "hp:", round(p.hp), "melee:", round(p.skills["melee"], 2))
    # 2) road ambush: travel event -> real-time arena
    if g.scenes.top is not scene:
        g.scenes.pop()
    from game.world import travel
    st.location = "velmora"
    st.local_pos = None
    g.enter_world()
    travel.start(st, g.world, "widows_crossing")
    st.travel["pending_combat"] = {"enemy": "bandit_cutthroat", "count": 3}
    g.enter_world()
    g.step(DT, [])
    shot(g, "ambush_choice")
    ts = g.scenes.top
    ts.event_menu.index = 0
    g.step(DT, [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, mod=0, unicode="", scancode=0)])
    assert type(g.scenes.top).__name__ == "ArenaScene", g.scenes.top
    p.hp = p.max_hp
    fight(g, 25, [1.5, 4.0], "ambush")
    print("after ambush:", type(g.scenes.top).__name__, "hp:", round(p.hp), "gold:", st.gold)
    g.step(DT, [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, mod=0, unicode="", scancode=0)])
    print("returned to:", type(g.scenes.top).__name__, "| travel log:", st.travel["log"][-1] if st.travel else None)
    print("COMBAT DEMO OK")


if __name__ == "__main__":
    main()
