"""Headless scripted playthrough that exercises the main flows and saves screenshots.

    python tools/autoplay.py OUT_DIR

Used as an integration smoke test: any exception fails the run.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame  # noqa: E402

from game.core.game import Game  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp()
os.makedirs(OUT, exist_ok=True)
DT = 1 / 60


class Driver:
    def __init__(self):
        self.game = Game(headless=True, save_dir=tempfile.mkdtemp(prefix="kr_saves_"))
        self.game.start()
        self.held = set()
        self._orig = pygame.key.get_pressed

        driver = self

        class Pressed:
            def __getitem__(self, k):
                return k in driver.held
        pygame.key.get_pressed = lambda: Pressed()

    def frames(self, n=1, events=()):
        for i in range(n):
            self.game.step(DT, events if i == 0 else ())

    def key(self, k, unicode=""):
        ev = pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode=unicode, scancode=0)
        self.frames(2, [ev])

    def type(self, s):
        for ch in s:
            self.key(ord(ch.lower()), ch)

    def hold(self, keys, seconds):
        self.held = set(keys)
        self.frames(int(seconds / DT))
        self.held = set()
        self.frames(1)

    def shot(self, name):
        path = os.path.join(OUT, f"{name}.png")
        pygame.image.save(self.game.screen, path)
        print("screenshot", path)

    @property
    def top(self):
        return self.game.scenes.top


def main():
    d = Driver()
    d.frames(30)
    d.shot("01_main_menu")
    # New game (menu has no Continue on a fresh save dir)
    d.key(pygame.K_RETURN)
    d.type("Ash")
    d.key(pygame.K_RETURN)          # -> race field
    d.key(pygame.K_RIGHT)           # kethari
    d.frames(20)
    d.shot("02_character_creation")
    d.key(pygame.K_DOWN)
    d.key(pygame.K_DOWN)
    d.key(pygame.K_DOWN)            # -> start
    d.key(pygame.K_RETURN)
    assert type(d.top).__name__ == "LocalScene", d.top
    st = d.game.state
    assert st.player.name == "Ash" and st.player.race == "kethari"
    d.frames(30)
    d.shot("03_brackenford")
    d.hold({pygame.K_d}, 1.0)
    d.hold({pygame.K_s, pygame.K_LSHIFT}, 0.8)
    d.shot("04_walking")
    for k, name in ((pygame.K_i, "05_inventory"), (pygame.K_c, "06_character"), (pygame.K_j, "07_journal")):
        d.key(k)
        d.frames(5)
        d.shot(name)
        d.key(pygame.K_ESCAPE)
    # enter a building with a shop: teleport next to the provisioner door
    scene = d.top
    lmap = scene.map
    b = next(b for b in lmap.buildings.values() if b["type"] == "provisioner")
    st.clock.minutes = st.clock.day_index * 1440 + 10 * 60  # 10:00, shops open
    scene.player.x, scene.player.y = b["door"][0] * 16 + 8, (b["door"][1] + 1) * 16 + 10
    scene.player.facing = "up"
    d.frames(2)
    d.key(pygame.K_e)
    assert st.sub_location == b["id"], "did not enter building"
    d.frames(20)
    d.shot("08_interior")
    # walk to the shopkeeper and trade
    scene = d.top
    keeper = next(a for a in scene.npcs if getattr(a, "stationary", False))
    scene.player.x, scene.player.y = keeper.x, keeper.y + 34
    scene.player.facing = "up"
    d.frames(2)
    d.key(pygame.K_e)
    assert type(d.top).__name__ == "DialogueScene", d.top
    d.shot("09_dialogue")
    d.key(pygame.K_DOWN)
    d.key(pygame.K_RETURN)  # tell me about this place
    d.frames(3)
    d.shot("09b_dialogue_place")
    d.key(pygame.K_ESCAPE)
    gold_before = st.gold
    from game.presentation.scenes.shop import ShopScene
    d.game.scenes.push(ShopScene(d.game, st.location, "provisioner", keeper.npc))
    d.frames(3)
    # buy a pickaxe if listed
    menu = d.top.buy_menu
    idx = next(i for i, e in enumerate(menu.entries) if e[1] == "pickaxe")
    menu.index = idx
    d.key(pygame.K_RETURN)
    d.shot("10_shop")
    assert st.player.inventory.has("pickaxe"), "pickaxe purchase failed"
    assert st.gold < gold_before
    d.key(pygame.K_ESCAPE)
    # leave building
    scene = d.top
    ex = next(o for o in scene.map.objects if o["kind"] == "exit_door")
    scene.player.x, scene.player.y = ex["x"] * 16 + 8, ex["y"] * 16 - 2
    scene.player.facing = "down"
    d.frames(2)
    d.key(pygame.K_e)
    assert st.sub_location is None
    # open the world map and travel to Rustback Hills
    d.key(pygame.K_m)
    d.frames(5)
    d.shot("11_world_map")
    wm = d.top
    wm.menu.index = wm.options.index("rustback_hills")
    d.key(pygame.K_RETURN)
    assert type(d.top).__name__ == "TravelScene", d.top
    d.frames(5)
    d.shot("12_travel_start")
    # auto-travel; resolve events by picking the last (safest) choice
    for _ in range(400):
        ts = d.top
        if type(ts).__name__ != "TravelScene":
            d.key(pygame.K_ESCAPE)
            continue
        if ts.event_menu:
            d.shot("13_travel_event")
            ts.event_menu.index = len(ts.event_menu.entries) - 1
            ts.event_menu._skip_disabled(-1)
            d.key(pygame.K_RETURN)
            continue
        if st.travel and st.travel["arrived"]:
            break
        ts.do_step()
        d.frames(1)
    d.shot("14_travel_arrived")
    assert st.travel["arrived"]
    d.top.action("enter")
    assert st.location == "rustback_hills" and type(d.top).__name__ == "LocalScene"
    d.frames(10)
    d.shot("15_rustback_hills")
    # mine a vein
    scene = d.top
    vein = next(o for o in scene.map.objects if o["kind"] == "ore_vein")
    scene.player.x, scene.player.y = vein["x"] * 16 + 8, (vein["y"] + 1) * 16 + 8
    scene.player.facing = "up"
    d.frames(2)
    d.key(pygame.K_e)
    d.frames(10)
    d.shot("16_mining")
    d.frames(240)
    print("ore:", st.player.inventory.count("rustite_ore"))
    assert st.player.inventory.count("rustite_ore") >= 1, "mining failed"
    # night lighting
    st.clock.minutes = st.clock.day_index * 1440 + 22 * 60
    d.frames(3)
    d.shot("17_night")
    # save + reload round trip
    d.game.save_game(1)
    d.game.load_game(1)
    assert d.game.state.player.inventory.count("rustite_ore") >= 1
    print("records in Set AI memory:", d.game.state.memory.count())
    d.frames(5)
    d.shot("18_after_load")
    print("AUTOPLAY OK")


if __name__ == "__main__":
    main()
