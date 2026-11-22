# Development Log

Read this file first when resuming work in a new session. Then read GAME_DESIGN.md and ARCHITECTURE.md.

## Status

| Phase | Status |
|---|---|
| 0 Planning | ✅ Done |
| 1 Foundation | ✅ Done |
| 2 World | ✅ Done |
| 3 Combat | ✅ Done |
| 4 Items & Magic | ⏭ Next. All 16 weapons fight, the spell rules and runtime exist; crafting and the spell-creation UI are still to do |
| 5 NPCs & Local AI | Roster (47) + fallback dialogue built; model client not built |
| 6 Companions & Relationships | — |
| 7 World Simulation | Factions/reputation/shops partially built (used by Phase 2) |
| 8 Base Building | — |
| 9 Polish | — |

## Session 2 — Phase 3: Combat

### Built
- **Rules** (`set_system/combat.py`): attack profiles from weapon, ore, attributes and skill; wind-up,
  active and recovery phases; 3-hit combos with a finisher; kick; block arc with a guard meter and guard
  breaks; dodge with i-frames; backstab; armor and armor pierce; knockback vs mass; stagger vs poise;
  bleed and other statuses; training gains per hit.
- **Spells** (`set_system/spells.py`): sub-element × movement × stat × tier gives mana, power, range, area,
  duration and cooldown, with validity rules. 400+ valid combinations, all tested. Blood spells cost HP.
  Spell-book capacity is 2 + level/3. A starter book holds *Ash Dart* and *Mending Light*.
- **Runtime** (`gameplay/combat.py`): combatants (the player wraps the Character, so HP is shared with the
  Set System), all 12 melee and 4 ranged weapon types, ammo use (arrows, bolts, powder; thrown knives drop
  as pickups), all 9 spell movement classes (projectile, homing, beam, wave, area, ground, orbit, ward,
  aura) and all 10 stat payloads, buffs and shields, loot pickups, reputation effects on kills, hit-stop
  and screen shake.
- **Enemy AI** (`gameplay/enemy_ai.py`): 6 archetypes, attack tokens (at most 2 attacking at once),
  per-archetype pauses between attacks, reactions to the player's wind-up (block or dodge) and
  recovery (punish), flanking orders from the captain, ranged kiting with line of sight, obstacle
  avoidance, fleeing and escaping.
- **World integration:** wilderness enemy groups spawn from map spawn points, and pack size comes from
  the data. Defeated groups respawn after 4 days. Escapes either way are written to Set AI, and enemies
  that remember the player notice them from further away. Thornblood raiders are neutral until provoked.
  Defeat means being knocked out and robbed. Combat makes you thirsty faster.
- **Travel:** fight events let you choose a real-time arena fight (flee off the edges) or auto-resolve.
- **Presentation:** creature sprites (beast, bug, worm, brute, hooded outlaws), attack, block and dodge
  poses, swing arcs and trails, white hit flash, death fall and fade, damage numbers, health bars,
  status particles, spell visuals, a combat HUD (weapon, ammo, spell slots with cooldowns, guard), and
  mouse aiming.
- **Saves:** version 2, adding the spell book and weapon mode. A v1→v2 migration is included and tested.

### Decisions
- Dodge moved to Space, so interaction is E/Enter only.
- Fights never kill the player outright. A knockout is a meaningful setback and keeps the
  "begin with nothing" loop intact. NPC death and permanence come with Phases 5–7.
- Beasts don't steal marks; outlaws do.

### Testing
- 55 unit tests (`tests/test_systems.py`, `tests/test_combat.py`). Combat coverage: weapon
  distinctness, ore scaling, combos, block, guard break, backstab, i-frames, armor, bleed, every spell
  combination, every weapon hitting, ammo use, every movement class hitting, heal and buff, mana and
  cooldown, every enemy type engaging, a bot beating a wolf pack, the attack-token cap, fleeing,
  neutral-until-provoked, loot and reputation on kill.
- `tools/combat_demo.py` runs a bot through a Greywood fight and a road ambush (arena → victory →
  travel log) and saves screenshots.
- Performance: about 3.3 ms per frame headless with 6 archers.

### Next (Phase 4)
- Smelting (ore → bars) and crafting all 16 weapon types plus armor, tools, medicine and food at
  stations (anvil and furnace already exist in smithy interiors).
- Armor items in equipment slots (combatants already read `armor`).
- Spell creation UI: choose parts, preview the computed stats, test-cast against a dummy, inscribe in the
  spell book within capacity, replace a spell for a Mana Crystal.

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
- The "Would you travel with me?" option only explains requirements. Real recruitment is Phase 6.
- The bounty board is informational only. Bounty contracts come in Phase 7.
- Property for sale is shown but can't be bought yet (Phase 8).
- No sound yet (Phase 9).
