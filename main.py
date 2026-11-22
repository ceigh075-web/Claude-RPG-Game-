"""Kindred Roads - entry point.

    python main.py              play
    python main.py --headless   run without a window (for automated checks)
"""
import sys

from game.core.game import Game


def main():
    game = Game(headless="--headless" in sys.argv)
    game.run()


if __name__ == "__main__":
    main()
