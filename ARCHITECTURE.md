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

## Module map (final)

| Layer | Modules |
|---|---|
| core | `game`, `scene`, `save` (versioned, autosave and backups), `state`, `clock`, `rng`, `events`, `data` |
| set_system (rules) | `aggression` (reactions & consequences of violence), `morale` (morale, surrender, prisoners, cells and beds, retainers), `loot` (body/container contents, taking, deposit), `bases` (starter house, bases, carter), `bosses` (lairs, boss stats, defeat and rewards), `crime` (bounties, guards, theft, seizing towns), `encounters` (group composition), `stats`, `needs`, `inventory`, `items`, `economy`, `factions`, `timeflow`, `daily`, `combat`, `skirmish`, `spells`, `crafting`, `relationships`, `favors`, `recruitment`, `companions`, `world_events`, `jobs`, `base` |
| set_ai (memory) | `memory` (append-only records and facts, prunable chatter) |
| local_ai (dialogue) | `client`, `context`, `personality`, `actions` (whitelist bridge), `dialogue` (engine: thread does HTTP only), `fallback` |
| world | `worldmap`, `mapgen`, `travel`, `effects`, `weather` |
| gameplay | `entity`, `interactions`, `npcs`, `combat` (runtime), `enemy_ai`, `companion_ai`, `bystander_ai`, `boss` (phases, summons, telegraphs) |
| presentation | `art` (procedural fallback), `assets` (pack sprite manifest), `charsprites` (humanoid rig compositor, enlarged chibi bodies), `chibi` (chibi heads), `wardrobe` (hair, clothes, hats, accessories, builds), `looks` (NPC identities, townsfolk and enemy variants), `weapons_art`, `animator`, `creatures`, `visuals` (gameplay → look/weapon glue), `vfx` (spell & combat effects), `env` (ground, water, buildings, props, decor), `knowledge` (read-only item sources/uses, money guide, job next steps), `icons` (item icons), `audio`, `combat_draw`, `ui/widgets`, `scenes/*` (menu, local, guide, travel, arena, duel, practice, worldmap, inventory, character, shop, crafting, spellbook, dialogue, party, jobs, base, journal, options, common, hints, loot, prisoners, creator, bases) |

**Daily tick order** (`set_system/daily.py`): companion bonds → relationship neglect → world events
(expiry, jobs, Hollow, territory, honours, festivals, a new event) → base (construction, research,
upkeep, production, raids).

**Threads:** only the local-AI HTTP call and music rendering run off the main thread. All game state,
including Set AI (SQLite), is touched only on the main thread.

## Hostility model (who may hurt whom)

`CombatWorld.hostile_between(a, b)`: teams give the default (party vs enemies; the neutral `npc` team is
nobody's enemy), and each combatant's `grudge` set overrides it in either direction. `foes_of` (AI
targeting) uses it; `strike_targets` / `can_hit` (what an attack connects with) add everyone when the
player's `intent` is on. The first blow on someone who wasn't a foe goes through
`_personal_violence`, which asks the Set System (`aggression.py`) for consequences and reactions and
hands the reaction to the victim's AI (`BystanderAI` for townsfolk, `CompanionAI` for companions).
Defeat sets `downed`; `execute` (finishing blow) sets `killed` and calls `aggression.on_kill`. Persistent
results are only Set System state and Set AI facts/records (`npc:<id>:alive`, `:grudge_until`,
`:injured_until`); the Local AI only reads them (`local_ai/context.violence_facts`).

## Presentation layer (visual overhaul)

Rendering only *reads* gameplay objects. The rules are:

- **No gameplay state is written from presentation code.** Animation is chosen from existing fields
  (`state`, `state_t`, `profile`, `moving`, `facing`, `flash`, `dead_t`, `blocking`, `charge`…).
- **One small hook in gameplay:** `CombatWorld.vfx_events`, a bounded list of hit/dodge notifications
  (`_vfx`) that the renderer drains. Gameplay never reads it. Spell hit profiles carry an extra `vfx_sub`
  key that the rules ignore. `tests/test_visuals.py` runs the same seeded battle with and without drawing
  and requires identical results.
- **Effects have their own RNG** (`vfx._rng`); they never consume the gameplay RNG.
- **Fallback:** if `assets/pixel_crawler` is missing, `visuals.enabled()` / `env.enabled()` are false and the
  original procedural art in `art.py` is used.

Pipeline per frame (LocalScene.draw): tiles (`env` textures, animated water) → ragged tile edges → ground
decor → building facades/roofs → `combat_draw.draw_under` (spell zones, telegraphs, rune circles,
shockwaves) → depth-sorted sprites (objects, `visuals.combatant_entries`, NPCs) → `combat_draw.draw_fx`
(projectiles, beams, waves, particles) → weather → lighting (spells add light sources) → damage numbers
and hurt flash in screen space.

Reusable pieces: `vfx.Style` per sub-element (palette, glyph, particle, beam style, ground pattern),
`vfx.glyph()` element shapes, a capped particle pool (`MAX_PARTICLES`), movement renderers shared by all
elements, and `charsprites.compose(look, anim, dir, frame)` for any humanoid. Sprite sources and licences
are recorded in `ASSETS.md`.

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
