# Kindred Roads — Architecture

## Stack

- **Python 3.11+** with **pygame-ce** (2D rendering, input, audio). Pure Python, no build step,
  easy for one developer to extend; runs on ordinary desktops.
- **Content as JSON** in `data/`, validated at load time (`game/core/data.py`).
- **Set AI memory**: **SQLite** (stdlib `sqlite3`) with append-only triggers.
- **Saves**: versioned JSON + a SQLite file per slot.
- **Local AI**: HTTP to a local inference server — **Ollama** (`/api/chat`) or any
  **OpenAI-compatible** server (llama.cpp `llama-server`, LM Studio, KoboldCpp). Configured in
  `config.json`. Small models (3–8B, e.g. `llama3.2:3b`, `qwen2.5:7b`) are enough. Optional: the game
  is fully playable with fallback template dialogue.
- **Art**: procedurally drawn pixel art at startup (`game/presentation/art.py`), no external asset
  files. 16×16 tiles, 16×24 characters, rendered to a 640×360 canvas scaled 2× with nearest-neighbour.
  The UI draws at full 1280×720 for readable text.

## Folder structure

```
kindred_roads/
  main.py                 entry point (python main.py [--headless] )
  config.json             AI endpoint/model, window scale, etc.
  data/                   all content (JSON)
  game/
    core/                 Game manager, scene manager, save manager, clock, event bus, data loader, RNG
    set_system/           AUTHORITATIVE rules: stats, needs, inventory, equipment, items, economy,
                          factions, relationships, combat math, spells, crafting, recruitment
    set_ai/               append-only structured memory (SQLite)
    local_ai/             model client, prompt/context builder, personality, response parsing,
                          action-request validation bridge, fallback dialogue
    world/                world graph, travel simulation, travel events, location state, map generation
    gameplay/             entities, collision, interactions, NPC presence, real-time combat runtime
                          (combat.py) and deterministic enemy AI (enemy_ai.py); companions later
    presentation/         art generation, camera, UI widgets, HUD, scenes (menus, travel, local)
  tests/                  unittest suite (python -m unittest)
  tools/                  dev scripts (data validation, screenshots)
```

## The three systems

```
 Player input ─► Scene ─► Set System (rules, state) ◄──── validated requests ──┐
                              │  writes events                                  │
                              ▼                                                 │
                          Set AI (append-only memory) ── relevant records ──► Local AI (dialogue)
```

### Set System (authoritative)
Plain deterministic Python operating on `GameState`. Every state change goes through a Set
System function (`inventory.add`, `economy.buy`, `needs.tick`, …). Randomness comes from a seeded
`random.Random` stored in the save (`core/rng.py`), so outcomes are reproducible.

### Set AI (memory, not a model)
`set_ai/memory.py`. Table `records(id, subject, location, event_type, description, day, minute,
importance, related JSON, source)`. SQLite triggers abort any UPDATE or DELETE → history is
immutable. Low-value chatter goes to `chatter` (a bounded rolling table that *may* be pruned and is
never treated as history). Retrieval: by subject/related, ordered by importance then recency,
limited to a token budget. Facts such as deaths are also kept as **world facts** (`facts` table,
append-only, latest value wins) that the dialogue layer injects as hard constraints.

### Local AI (dialogue only)
`local_ai/client.py` speaks Ollama or OpenAI-compatible HTTP with a timeout and is only invoked when
the player opens a conversation or asks something. The model must answer in JSON:

```json
{"say": "text the NPC speaks", "mood": "friendly", "requests": [{"action": "sell_item", "item": "ration", "qty": 2}]}
```

`requests` may only name actions from a fixed whitelist (`local_ai/actions.py`): sell_item,
buy_item, offer_recruit, give_gift_ack, share_rumor, start_favor, end_conversation… The
**ActionBridge** passes each request to the Set System, which checks preconditions (stock, money,
requirements) and executes or rejects. The result is fed back so the NPC's next line matches reality.
The model never touches stats, items, money, relationships or history directly. If the model is
unreachable, malformed, or slow, `local_ai/fallback.py` builds dialogue from personality templates.

## Combat split

- `set_system/combat.py` holds the rules: attack profiles, phase timings, hit resolution (block, guard
  break, backstab, armor, stagger, statuses) and training gains. These are pure functions and are unit-tested.
- `set_system/spells.py` computes every number for a spell from its four parts and validates allowed
  combinations.
- `gameplay/combat.py` is the runtime: combatants, attack state machine, projectiles, spell shapes,
  pickups, attack tokens. It decides *when* things touch; the rules decide *what happens*.
- `gameplay/enemy_ai.py` contains the archetype behaviours. They are deterministic given the seeded RNG.
- `presentation/combat_draw.py` draws poses, swings, effects and the HUD.
- `set_system/skirmish.py` auto-resolves fights for travel events the player chooses not to fight in real time.

## Core loop

`Game.run()` → fixed-timestep update (60 Hz) → `SceneManager` (stack of scenes: menu, local
exploration, travel, overlay screens). Scenes receive input, call the Set System, and render.
`EventBus` publishes gameplay events (e.g. `item_gained`, `npc_died`) that Set AI and UI listen to.

## Save format

`saves/slot_N/state.json`:
```json
{"version": 1, "saved_at": "...", "state": { ...GameState.to_dict()... }}
```
plus `saves/slot_N/memory.sqlite`. Loading runs `MIGRATIONS[v]` functions to upgrade old saves.
Writes go to a temp file then `os.replace` for atomic saves.

## Data flow for a location visit

1. Travel arrives → `world.locations.enter(location_id)`.
2. `world.mapgen.generate(location, seed)` builds a deterministic tile map (same every visit).
3. Persistent changes (harvested nodes, mined veins, opened chests) live in
   `GameState.location_states[location_id]` and are reapplied on load.
4. Distant locations are not simulated tile-by-tile; they update abstractly via world events.

## Performance rules
- Art generated once and cached. Only the visible tile window is drawn.
- AI calls happen on a worker thread only during conversations; the game never blocks on them.
- No per-frame simulation of off-screen locations.
