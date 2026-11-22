# Kindred Roads

A small, interconnected 2D open-world RPG: Oregon-Trail-style text travel between 9 towns and 20
wilderness areas, top-down exploration, 47 named and recruitable NPCs, and a world that remembers.

## Run

```bash
pip install -r requirements.txt
python main.py
```

Python 3.11+ is required. Saves go to `saves/` (override with `KINDRED_SAVE_DIR`).

## Controls

| Key | Action |
|---|---|
| WASD / arrows | Move (8 directions) |
| Shift | Sprint |
| E / Space | Interact / talk / confirm |
| I / C / J | Inventory / character / journal |
| M | World map (choose a destination to travel) |
| Esc | Pause menu |
| F5 / F9 | Quick save / quick load |

## Develop

```bash
python -m unittest            # unit tests
python tools/autoplay.py out  # headless scripted playthrough + screenshots
python tools/build_npcs.py    # regenerate data/npcs.json from the roster table
```

Docs: [GAME_DESIGN.md](GAME_DESIGN.md), [ARCHITECTURE.md](ARCHITECTURE.md), [DEVELOPMENT_LOG.md](DEVELOPMENT_LOG.md).

## Local AI (optional, Phase 5)

NPC dialogue will use a local model via [Ollama](https://ollama.com) or any OpenAI-compatible server,
configured in `config.json`. The game is fully playable without it: NPCs fall back to
personality-driven template dialogue.
