"""Open, drive and draw every screen headlessly; any exception fails. Optionally saves screenshots.

    python tools/ui_smoke.py [OUT_DIR]
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame  # noqa: E402

from game.core.game import Game  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else None
DT = 1 / 60


def key(g, k, uni=""):
    g.step(DT, [pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode=uni, scancode=0)])
    g.step(DT, [])


def shot(g, name):
    g.step(DT, [])
    if OUT:
        os.makedirs(OUT, exist_ok=True)
        pygame.image.save(g.screen, os.path.join(OUT, name + ".png"))
    print("ok", name)


def push(g, scene, name, keys=()):
    g.scenes.push(scene)
    for k in keys:
        key(g, k)
    shot(g, name)
    while g.scenes.top is not scene and len(g.scenes.stack) > 1:
        g.scenes.pop()
    g.scenes.pop(scene)


def main():
    g = Game(headless=True, save_dir=os.path.join(OUT or "/tmp", "ui_smoke_saves"))
    g.new_game("Smoke", "sylth", {"race": "sylth", "skin": [170, 190, 230], "hair": [230, 230, 240],
                                  "shirt": [90, 60, 120], "pants": [50, 40, 40], "hair_style": 1}, "she/her")
    st = g.state
    p = st.player
    for it, n in (("rustite_ore", 6), ("leather", 4), ("meat", 2), ("herbs", 6), ("mirelight_herb", 2), ("water", 2),
                  ("arcane_dust", 2), ("enchanted_ink", 2), ("mail_rustite", 1), ("bow_rustite", 1), ("arrow", 20)):
        p.inventory.add(it, n)
    p.equipment["body"] = "mail_rustite"
    p.equipment["ranged"] = "bow_rustite"
    from game.presentation.scenes import crafting, spellbook, practice, inventory, character, journal
    push(g, crafting.CraftingScene(g, "furnace"), "p4_craft_furnace", [pygame.K_RETURN])
    push(g, crafting.CraftingScene(g, "alchemy"), "p4_craft_alchemy", [pygame.K_DOWN])
    push(g, crafting.CraftingScene(g, "campfire"), "p4_craft_campfire", [pygame.K_DOWN, pygame.K_RETURN])
    book = spellbook.SpellbookScene(g, at_table=True)
    g.scenes.push(book)
    key(g, pygame.K_n)
    for k in (pygame.K_RIGHT, pygame.K_DOWN, pygame.K_RIGHT, pygame.K_DOWN, pygame.K_RIGHT, pygame.K_RIGHT):
        key(g, k)
    shot(g, "p4_spell_design")
    for _ in range(4):
        key(g, pygame.K_DOWN)
    key(g, pygame.K_RETURN)
    assert st.spell_drafts, "draft not saved"
    shot(g, "p4_spellbook")
    key(g, pygame.K_t)
    assert type(g.scenes.top).__name__ == "PracticeScene"
    sc = g.scenes.top
    sc.player.aim = (1.0, 0.0)
    key(g, pygame.K_1)
    for _ in range(40):
        g.step(DT, [])
    shot(g, "p4_practice")
    key(g, pygame.K_ESCAPE)
    assert type(g.scenes.top).__name__ == "LocalScene"
    push(g, inventory.InventoryScene(g), "inventory")
    push(g, character.CharacterScene(g), "character")
    push(g, journal.JournalScene(g), "journal")
    # Phase 5: dialogue (offline fallback), free text, gift, requirements, duel
    from game.presentation.scenes.dialogue import DialogueScene
    g.config.setdefault("ai", {})["enabled"] = False
    npc = g.data.npcs["garrow"]
    d = DialogueScene(g, npc)
    g.scenes.push(d)
    key(g, pygame.K_RETURN)                    # say something...
    for ch in "hello friend":
        key(g, ord(ch) if ch != " " else pygame.K_SPACE, ch)
    key(g, pygame.K_RETURN)
    for _ in range(30):
        g.step(DT, [])
    assert not d.waiting and len(d.log) >= 3, d.log
    d.menu.index = [e[1] for e in d.menu.entries].index("favor")
    key(g, pygame.K_RETURN)
    for _ in range(30):
        g.step(DT, [])
    assert st.favors.get("garrow_spar"), "favor not started"
    shot(g, "p5_dialogue")
    d.build()
    d.menu.index = [e[1] for e in d.menu.entries].index("duel")
    key(g, pygame.K_RETURN)
    assert type(g.scenes.top).__name__ == "DuelScene", g.scenes.top
    duel = g.scenes.top
    for _ in range(90):
        g.step(DT, [])
    shot(g, "p5_duel")
    duel.foe.hp = 1
    g.step(DT, [])
    key(g, pygame.K_RETURN)
    assert st.flags.get("duel_won:garrow")
    assert type(g.scenes.top).__name__ == "LocalScene"
    # Phase 6: recruit via dialogue, party screen, transfer, relationships, companion in the world
    from game.set_system import relationships as rel
    st.gold = 500
    rel.change(st, "tobin", friendship=30)
    d = DialogueScene(g, g.data.npcs["tobin"], g.scenes.top)
    g.scenes.push(d)
    d.menu.index = [e[1] for e in d.menu.entries].index("join")
    key(g, pygame.K_RETURN)
    for _ in range(30):
        g.step(DT, [])
    assert type(g.scenes.top).__name__ == "ConfirmScene", g.scenes.top
    key(g, pygame.K_RETURN)
    assert "tobin" in st.companions, "recruit failed"
    while type(g.scenes.top).__name__ != "LocalScene":
        g.scenes.pop()
    local = g.scenes.top
    assert local.combat.companions(), "companion not spawned"
    for _ in range(60):
        g.step(DT, [])
    shot(g, "p6_companion_in_world")
    from game.presentation.scenes import party
    push(g, party.PartyScene(g), "p6_party")
    push(g, party.TransferScene(g, "tobin"), "p6_transfer", [pygame.K_RETURN])
    push(g, party.RelationshipsScene(g), "p6_relationships")
    # Phase 7: job board, news journal, event-spawned named monster
    from game.presentation.scenes.jobs import JobBoardScene
    from game.set_system import world_events
    import random as _r
    for _ in range(12):
        from game.set_system import timeflow
        timeflow.advance(st, 1440)
    jb = JobBoardScene(g, st.location)
    g.scenes.push(jb)
    key(g, pygame.K_RETURN)
    assert any(j["status"] == "active" for j in st.jobs), "job not accepted"
    shot(g, "p7_job_board")
    g.scenes.pop(jb)
    j = journal.JournalScene(g)
    g.scenes.push(j)
    key(g, pygame.K_TAB)
    shot(g, "p7_news")
    g.scenes.pop(j)
    ev = world_events.ev_creature(st, _r.Random(4))
    st.location, st.local_pos, st.sub_location = ev["location"], None, None
    st.discovered.add(ev["location"])
    st.clock.minutes = st.clock.day_index * 1440 + 12 * 60
    g.enter_world()
    loc = g.scenes.top
    elite = [c for c in loc.combat.enemies() if c.enemy.get("elite_event")]
    assert elite, "elite not spawned"
    loc.player.x, loc.player.y = elite[0].x - 70, elite[0].y
    for _ in range(90):
        g.step(DT, [])
    shot(g, "p7_named_monster")
    extra = globals().get("EXTRA")
    if extra:
        extra(g, push, key, shot)
    print("UI SMOKE OK")


if __name__ == "__main__":
    main()
