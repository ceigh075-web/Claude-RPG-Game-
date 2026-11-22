"""Kindred Roads - entry point.

    python main.py              play
    python main.py --headless   run without a window (for automated checks)
    python main.py --selftest   start headless, play a few seconds, save, load, exit (0 = OK)
"""
import sys


def selftest():
    import os
    import tempfile
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    os.environ["SDL_AUDIODRIVER"] = "dummy"
    from game.core.game import Game
    g = Game(headless=True, save_dir=tempfile.mkdtemp(prefix="kr_selftest_"))
    g.start()
    g.new_game("Selftest", "human", {"race": "human", "skin": [200, 160, 120], "hair": [40, 30, 20],
                                     "shirt": [60, 90, 150], "pants": [60, 50, 40], "hair_style": 0}, "they/them")
    for _ in range(180):
        g.step(1 / 60, [])
    assert g.save_game(1), "save failed"
    assert g.load_game(1), "load failed"
    for _ in range(60):
        g.step(1 / 60, [])
    from game.core.paths import USER_ROOT, DATA_DIR
    print(f"user folder: {USER_ROOT} | data: {DATA_DIR}")
    print(f"SELFTEST OK - {len(g.data.npcs)} NPCs, {len(g.data.locations)} locations, "
          f"{len(g.data.recipes)} recipes, scene {type(g.scenes.top).__name__}")
    return 0


def main():
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    from game.core.game import Game
    game = Game(headless="--headless" in sys.argv)
    game.run()


if __name__ == "__main__":
    main()
