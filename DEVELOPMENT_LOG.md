# Development Log

Read this file first when resuming work in a new session. Then read GAME_DESIGN.md and ARCHITECTURE.md.

## Status

| Phase | Status |
|---|---|
| 0 Planning | ✅ Done |
| 1 Foundation | ✅ Done |
| 2 World | ✅ Done |
| 3 Combat | ⏭ Next |
| 4 Items & Magic | Data designed (ores, weapons, magic.json); systems not built |
| 5 NPCs & Local AI | Roster (47) + fallback dialogue built; model client not built |
| 6 Companions & Relationships | — |
| 7 World Simulation | Factions/reputation/shops partially built (used by Phase 2) |
| 8 Base Building | — |
| 9 Polish | — |

## Session 1 — Planning, Phase 1, Phase 2

### Decisions
- **Engine:** Python 3.11+ with pygame-ce. One dev, no build step, testable headless.
- **Art:** All pixel art is procedural (`game/presentation/art.py`), so there are no asset files.
  640×360 canvas scaled 2×; UI drawn at 1280×720.
- **Set AI:** SQLite with triggers that block UPDATE/DELETE, so history is append-only by construction.
  Small talk goes to a bounded `chatter` table and never counts as history.
- **Local AI:** Ollama or OpenAI-compatible HTTP, configured in `config.json` (Phase 5). The fallback
  dialogue in `local_ai/fallback.py` is already the working dialogue layer.
- **4th ranged weapon:** Firelock (hand cannon: spread shot, huge knockback, slow reload).
- **Ores:** Rustite → Greyvein Iron → Sunsilver → Voidglass.
- **Magic:** added a 10th stat class, *Vitality* (temporary max-HP boost); Nature uses it.
- **Leaders recruitable:** the 6 faction leaders are in the roster with late-game requirements; recruiting
  one will trigger a succession event (Phase 7).
- **Map scale:** 1 map unit = 1.5 km; base walking pace 4.5 km/h. Brackenford → Rustback Hills ≈ 21 km.
- **Abstract skirmishes:** travel-event fights auto-resolve with `set_system/skirmish.py`. Phase 3 should
  offer a real-time fight there and keep the resolver for off-screen battles.

### Phase 1 — Foundation (done)
- Project structure, `GameData` loader with scope validation (counts, references, graph connectivity).
- Main menu, character creation (name, 4 races, pronouns, randomized look).
- Save system: 3 slots, versioned JSON plus SQLite memory, atomic writes, migration hook. Quick save is F5 and quick load is F9.
- Player controller: 8-direction movement, sprint, tile collision, walk animation in 4 facings.
- Statistics: 4 attributes and 11 skills, learn-by-doing with diminishing returns, levels.
- Needs: food/water drain with hunger and thirst penalties, starvation damage, mana regen, natural healing.
- Inventory and equipment (melee and ranged slots), use/equip/drop, weight and encumbrance.
- Calendar: 7-day weeks, 4-week months, 12 named months, day/night lighting.

### Phase 2 — World (done)
- World graph: 9 towns, 20 wilderness areas, 37 routes with terrain and distance; world map screen.
- Deterministic local maps for all 29 locations: towns with buildings, paths, plaza, well and palisade;
  wilderness by biome with trees, rocks, forage bushes, ore veins, scavenge piles, crystals, landmarks,
  NPC camps and enemy spawn points (used in Phase 3). Walking to a road at the map edge opens travel.
- Building interiors: shops with counters, inns with beds, smithies, and a mine in Cinderdeep with ore veins.
- Text travel in 1-hour steps: pace, rations, auto-eating and drinking, weather by biome and season, night,
  injuries, encumbrance, resting/camping, turning back, auto-travel.
- 14 travel events with choices and consequences through a data-driven effect system (`world/effects.py`).
- Gathering: forage, mining (pickaxe; skill gates per ore), woodcutting, scavenging, crystals, water refills.
  Harvested nodes respawn after a set number of days and persist in saves.
- Shops: 12 shop types with stock, merchant cash, weekly restock, Trading-skill and reputation pricing.
  Named shopkeepers follow schedules; other shops have anonymous keepers during the day.
- NPCs: the 47 named NPCs appear at home following 10 schedule templates (work, tavern, wander, patrol,
  camp, sleep). You can talk to them using the fallback dialogue, which is shaped by personality, and the
  first meeting is recorded in Set AI.
- Inns: rent a bed and sleep until morning. Collapsing from needs costs marks and is recorded as history.
- HUD, inventory, character sheet (attributes, skills, factions), journal (log, Set AI history, places).

### Testing
- `python -m unittest` runs 32 tests: data scope, clock, RNG, stats, needs, items, economy, memory
  immutability, saves, world paths, map determinism, exit and door reachability, travel, every event
  choice, and skirmishes.
- `python tools/autoplay.py OUT_DIR` is a headless scripted playthrough: new game, walk, menus, enter
  shop, dialogue, buy pickaxe, world map, travel with events, arrive, mine, night, save, load. It writes
  screenshots.

### Known limitations / next steps
- **Phase 3 (next):** real-time combat in local maps. Use `LocalMap.spawns` for enemy placement and
  `data/enemies.json` archetypes. Add punch, kick, block, dodge, knockback and stagger. Let travel
  "Fight" choices open a combat arena.
- The "Would you travel with me?" option only explains requirements. Real recruitment is Phase 6.
- The bounty board is informational only. Bounty contracts come in Phase 7.
- Property for sale is shown but can't be bought yet (Phase 8).
- No sound yet (Phase 9).
