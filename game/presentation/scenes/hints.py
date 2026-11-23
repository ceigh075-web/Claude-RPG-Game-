"""First-time contextual hints. Each is shown once per save (flag tip:<id>)."""
import math

HINTS = [
    ("move", lambda sc: True,
     "WASD moves, Shift sprints. Walk up to people and things and press E. Esc opens the menu (Controls are listed there)."),
    ("npc", lambda sc: any(sc.player.dist_to(a.x, a.y) < 60 for a in sc.npcs if a.npc),
     "Talk to people with E. Everyone can be recruited - ask them what it would take."),
    ("eat", lambda sc: sc.state.player.food < 35 or sc.state.player.water < 35,
     "You're getting hungry or thirsty: eat and drink from your Inventory (I). Wells and streams refill flasks."),
    ("wild", lambda sc: sc.map.kind == "wild",
     "The wilds: forage bushes, mine ore veins (needs a pickaxe), chop trees, search debris. Walk off a road at the "
     "map edge (or press M) to travel on."),
    ("combat", lambda sc: sc.combat.in_combat,
     "Fight! K / left mouse attacks (press again for a 3-hit combo), L / right mouse blocks, Space dodges, F kicks. "
     "Watch for wind-ups."),
    ("board", lambda sc: sc.map.kind == "town" and sc.state.clock.day_index >= 1,
     "Every town square has a job board: bounties, supply runs and caravan escorts pay well and build standing."),
    ("night", lambda sc: sc.state.clock.is_night and sc.map.kind != "interior",
     "It's getting dark. Inns rent beds; your own house (if you buy one) is free."),
    ("ore", lambda sc: any(i.endswith("_ore") for i in sc.state.player.inventory.items),
     "Ore sells best in Cinderdeep, or smelt it at a furnace and forge gear at an anvil (smithies, guild halls)."),
    ("company", lambda sc: bool(sc.state.companions),
     "You have company! P manages your squad (tasks, gear), R shows relationships. Companions eat from your packs."),
    ("spells", lambda sc: sc.state.player.level >= 3,
     "Spell book (B): design, edit and inscribe spells anywhere, any time. Test drafts in a practice yard. Mana refills "
     "on its own (faster out of combat) and every weapon hit you land restores some."),
    ("outpost", lambda sc: sc.state.gold >= 900,
     "With enough marks you could buy a house in town - or found your own outpost at Widow's Crossing."),
]


def next_hint(scene):
    st = scene.state
    if not scene.game.config.get("hints", True):
        return None
    for hid, cond, text in HINTS:
        key = f"tip:{hid}"
        if st.flags.get(key):
            continue
        try:
            ok = cond(scene)
        except Exception:
            ok = False
        if ok:
            st.flags[key] = True
            return text
    return None
