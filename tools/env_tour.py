"""Visits locations headlessly and saves a screenshot of each (visual regression aid).

    python tools/env_tour.py OUT_DIR [location_id ...]
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame  # noqa: E402

from game.core.game import Game  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else "env_shots"
os.makedirs(OUT, exist_ok=True)


def main():
    g = Game(headless=True, save_dir=os.path.join(OUT, "saves"))
    g.new_game("Rook", "human", {"race": "human", "skin": [198, 146, 104], "hair": [40, 30, 20],
                                 "shirt": [60, 90, 150], "pants": [60, 50, 40], "hair_style": 0}, "they/them")
    st = g.state
    ids = sys.argv[2:] or [l["id"] for l in g.data.locations["towns"]] + [l["id"] for l in g.data.locations["wilderness"]]
    for lid in ids:
        while len(g.scenes.stack) > 1:
            g.scenes.pop()
        sub = None
        if ":" in lid:
            lid, sub = lid.split(":")
        st.sub_location = sub
        st.location = lid
        st.discovered.add(lid)
        st.clock.minutes = 12 * 60
        st.local_pos = None
        g.enter_world()
        for _ in range(20):
            g.step(1 / 60, [])
        pygame.image.save(g.screen, os.path.join(OUT, lid + ("_" + sub if sub else "") + ".png"))
        st.sub_location = None
        print("shot", lid, type(g.scenes.top).__name__)


if __name__ == "__main__":
    main()
