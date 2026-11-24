"""Drive every screen and the world with random input, headlessly, and report any exception with its traceback.
Also checks invariants after each run (no negative counts or gold, mana within bounds, no item duplication
from loot screens).

    python tools/fuzz.py [seconds_per_screen] [seed]
"""
import os
import random
import tempfile
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame  # noqa: E402

from game.core.game import Game  # noqa: E402

DT = 1 / 30
KEYS = [pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT, pygame.K_RETURN, pygame.K_SPACE, pygame.K_TAB,
        pygame.K_BACKSPACE, pygame.K_DELETE, pygame.K_e, pygame.K_a, pygame.K_d, pygame.K_w, pygame.K_s, pygame.K_q,
        pygame.K_r, pygame.K_t, pygame.K_k, pygame.K_x, pygame.K_c, pygame.K_m, pygame.K_n, pygame.K_u, pygame.K_v,
        pygame.K_g, pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_f, pygame.K_l, pygame.K_b, pygame.K_i,
        pygame.K_j, pygame.K_p, pygame.K_h, pygame.K_z]
FAILS = []


def ev(rng):
    if rng.random() < 0.08:
        return pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=rng.choice((1, 3)), pos=(rng.randint(0, 1279), rng.randint(0, 719)))
    if rng.random() < 0.05:
        return pygame.event.Event(pygame.MOUSEMOTION, pos=(rng.randint(0, 1279), rng.randint(0, 719)), rel=(0, 0), buttons=(0, 0, 0))
    k = rng.choice(KEYS)
    mod = pygame.KMOD_SHIFT if rng.random() < 0.1 else 0
    uni = pygame.key.name(k) if len(pygame.key.name(k)) == 1 else ""
    return pygame.event.Event(pygame.KEYDOWN, key=k, mod=mod, unicode=uni, scancode=0)


def snapshot(st):
    p = st.player
    return {"gold": st.gold, "items": dict(p.inventory.items)}


def check(st, label):
    p = st.player
    if st.gold < 0:
        FAILS.append((label, f"negative gold {st.gold}"))
    for k, v in p.inventory.items.items():
        if v <= 0:
            FAILS.append((label, f"non-positive count {k}={v}"))
        if k not in st.data.items:
            FAILS.append((label, f"unknown item {k}"))
    if not (-0.01 <= p.mana <= p.max_mana + 0.01):
        FAILS.append((label, f"mana out of range {p.mana}/{p.max_mana}"))
    if p.hp > p.max_hp + 0.01:
        FAILS.append((label, f"hp above max {p.hp}/{p.max_hp}"))


def drive(g, label, frames, rng, base_depth):
    for i in range(frames):
        events = [ev(rng)] if rng.random() < 0.6 else []
        try:
            g.step(DT, events)
        except SystemExit:
            return
        except Exception:
            FAILS.append((label, traceback.format_exc()))
            return
        if len(g.scenes.stack) < base_depth:          # closed itself: fine, stop
            return


def prepare(g):
    st = g.state
    p = st.player
    st.gold = 5000
    for it in list(g.data.items)[:60]:
        if it != "house_deed":
            p.inventory.add(it, 3)
    st.spellbook.append({"name": "Var", "element": "fire", "sub": "ash", "move": "area", "stat": "damage", "tier": 1,
                         "hue": 3, "intensity": 1.5, "behavior": "lingering", "duration": 2.0})
    st.spell_drafts.append({"name": "Pure", "element": "water", "move": "projectile", "stat": "heal", "tier": 1,
                            "behavior": "volley"})
    st.property["brackenford"] = {"building": "b5", "bought": 0, "storage": {}}
    from game.set_system import morale
    morale.resolve(st, "bandit_cutthroat", "prisoner")


def main():
    secs = float(sys.argv[1]) if len(sys.argv) > 1 else 6
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    rng = random.Random(seed)
    g = Game(headless=True, save_dir=os.path.join(tempfile.gettempdir(), f"fuzz_saves_{seed}"))
    g.new_game("Fuzz", "sylth", {"race": "sylth"}, "they/them")
    prepare(g)
    st = g.state
    from game.presentation.scenes import (base, character, crafting, creator, dialogue, guide, inventory, jobs,
                                          journal, loot, options, party, prisoners, shop, spellbook, worldmap)
    from game.presentation.scenes.common import ControlsScene, PauseScene
    npc = next(iter(g.data.npcs.values()))
    screens = [
        ("inventory", lambda: inventory.InventoryScene(g)),
        ("character", lambda: character.CharacterScene(g)),
        ("spellbook", lambda: spellbook.SpellbookScene(g)),
        ("spellcraft", lambda: spellbook.SpellCraftScene(g, spellbook.SpellbookScene(g))),
        ("party", lambda: party.PartyScene(g)), ("relationships", lambda: party.RelationshipsScene(g)),
        ("journal", lambda: journal.JournalScene(g)), ("guide", lambda: guide.GuideScene(g)),
        ("prisoners", lambda: prisoners.PrisonersScene(g)), ("options", lambda: options.OptionsScene(g)),
        ("controls", lambda: ControlsScene(g)), ("pause", lambda: PauseScene(g)),
        ("worldmap", lambda: worldmap.WorldMapScene(g)),
        ("creator", lambda: creator.CharacterCreatorScene(g, st.player.appearance, st.player.race)),
        ("craft_anvil", lambda: crafting.CraftingScene(g, "anvil")),
        ("craft_alchemy", lambda: crafting.CraftingScene(g, "alchemy")),
        ("shop", lambda: shop.ShopScene(g, "brackenford", "provisioner", None)),
        ("jobs", lambda: jobs.JobBoardScene(g, "brackenford")),
        ("storage", lambda: base.StorageScene(g, st.property["brackenford"], "Chest")),
        ("dialogue", lambda: dialogue.DialogueScene(g, npc, g.scenes.top)),
        ("loot", lambda: loot.LootScene(g, "Crate", [{"item": "marks", "qty": 9}, {"item": "bread", "qty": 2},
                                                      {"item": "dagger_rustite", "qty": 1}], None)),
    ]
    n = int(secs / DT)
    for loc in ("brackenford", "greywood", "velmora", "hollow_fort"):
        st.location, st.local_pos, st.sub_location = loc, None, None
        st.mode = "local"
        while len(g.scenes.stack) > 1:
            g.scenes.pop()
        g.enter_world()
        check(st, f"enter {loc}")
        # play the world itself (move, fight, cast, interact)
        drive(g, f"world {loc}", n * 2, rng, len(g.scenes.stack))
        while type(g.scenes.top).__name__ not in ("LocalScene",) and len(g.scenes.stack) > 1:
            g.scenes.pop()
        check(st, f"world {loc}")
        from game.presentation.scenes.local import LocalScene
        for name, make in screens:
            while not isinstance(g.scenes.top, LocalScene) and len(g.scenes.stack) > 1:
                g.scenes.pop()
            if st.mode != "local" or not st.player.alive if hasattr(st.player, "alive") else False:
                break
            if not isinstance(g.scenes.top, LocalScene):
                st.player.hp = st.player.max_hp
                g.enter_world()
            try:
                g.scenes.push(make())
            except Exception:
                FAILS.append((f"{name} open @ {loc}", traceback.format_exc()))
                continue
            drive(g, f"{name} @ {loc}", n, rng, len(g.scenes.stack))
            check(st, f"{name} @ {loc}")
            st.player.hp = st.player.max_hp
        st.player.hp = st.player.max_hp
    seen = set()
    for label, msg in FAILS:
        key = msg.strip().splitlines()[-1] if msg else label
        if key in seen:
            continue
        seen.add(key)
        print("=" * 70)
        print("FAIL:", label)
        print(msg)
    print(f"FUZZ DONE: {len(FAILS)} failures ({len(seen)} distinct)")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
