# Kindred Roads

A small, interconnected 2D open-world RPG. Travel between 9 towns and 20 wilderness areas in an
Oregon-Trail-style text journey, then explore, fight, gather and talk in real-time top-down maps.

- **47 named NPCs, all recruitable**, each with a personality, favors, relationships and memories.
  Optional local-AI dialogue.
- **Real-time combat** with 16 weapon types, combos, blocking, dodging, knockback and six enemy
  archetypes. Companions fight beside you.
- **Custom magic:** design spells from 4 elements, 16 sub-elements, 9 movement types and 10 effects,
  test them, and inscribe the best.
- **Crafting** from 4 ores (98 recipes), regional trade, job boards and bounties.
- **Friendships, rivalries and romance**, plus a squad of up to 4 companions.
- **A town house and an outpost** with farms, workshops, research, walls and raids.
- **A living world:** daily events (caravans, shortages, raids, wars, monsters, festivals), an outlaw
  faction that grows or breaks, faction honours and successions. Everything is written to an
  append-only history that NPCs remember.

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
| E / Enter | Interact / talk / confirm |
| K / left mouse | Attack (combos; hold to draw a bow) |
| L / right mouse | Block (hold) |
| F / Space | Kick / dodge roll |
| Q | Switch melee / ranged weapon |
| 1–4 | Cast spells |
| I / C / J | Inventory / character / journal |
| B / P / R | Spell book / your company / relationships |
| M | World map (choose a destination to travel) |
| Esc | Pause menu |
| F5 / F9 | Quick save / quick load (slot 1; there's also an autosave on arrival and after sleeping) |

## Develop

```bash
python -m unittest            # unit tests
python tools/autoplay.py out  # headless scripted playthrough + screenshots
python tools/combat_demo.py out  # headless bot fights (wilderness + road ambush) + screenshots
python tools/ui_smoke.py out   # opens and drives every screen headlessly
python tools/build_npcs.py    # regenerate data/npcs.json from the roster table
```

Docs: [GAME_DESIGN.md](GAME_DESIGN.md), [ARCHITECTURE.md](ARCHITECTURE.md), [DEVELOPMENT_LOG.md](DEVELOPMENT_LOG.md).

## Local AI (optional)

NPC dialogue uses a local model through [Ollama](https://ollama.com) or any OpenAI-compatible server
(llama.cpp `llama-server`, LM Studio, KoboldCpp). Set it up in `config.json`:

```json
"ai": {"enabled": true, "backend": "ollama", "endpoint": "http://localhost:11434", "model": "llama3.2:3b"}
```

To use Ollama:

```bash
ollama pull llama3.2:3b
```

For an OpenAI-compatible server, set `"backend": "openai"` and its endpoint (for example `http://localhost:8080`).
A 3–8B model is enough.

The model only writes dialogue. It can *request* whitelisted actions (trade, favors, recruiting,
promises, tone), and the game validates and runs them. It never changes stats, items, money or history.
If the model is off, missing or slow, NPCs use personality-driven template dialogue and everything
still works.
