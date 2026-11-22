# Development Log

Read this file first when resuming work in a new session. Then read GAME_DESIGN.md and ARCHITECTURE.md.

**All nine phases are complete.** Future work is content, balance and polish on top of working systems
(see "Ideas beyond scope" at the end). Before changing anything, run the checks:

```bash
python -m unittest                    # 117 unit tests
python tools/autoplay.py out/ap       # scripted playthrough
python tools/combat_demo.py out/cd    # bot fights
python tools/ui_smoke.py out/ui       # opens and drives every screen
```

## Status

| Phase | Status |
|---|---|
| 0 Planning | ✅ Done |
| 1 Foundation | ✅ Done |
| 2 World | ✅ Done |
| 3 Combat | ✅ Done |
| 4 Items & Magic | ✅ Done |
| 5 NPCs & Local AI | ✅ Done |
| 6 Companions & Relationships | ✅ Done |
| 7 World Simulation | ✅ Done |
| 8 Base Building | ✅ Done |
| 9 Polish | ✅ Done |

## Session 3 — Phase 9: Polish & Testing
- **Audio** (`presentation/audio.py`): 20 procedurally synthesized effects (swings, hits, heavy hits,
  blocks, dodges, kicks, bow, firelock, spells, heals, pickups, coins, UI, mining, chopping, doors,
  level-up, alarm, death) and ambient music loops per mood (menu, town, wild, combat, travel), rendered on
  a worker thread. There are no asset files and no numpy, and the game is silent if no audio device
  exists. Gameplay code raises sounds through the EventBus (`sfx`), so the rules layer has no
  presentation imports.
- **Options** (Pause or Main menu): master, music and effects volume, tips on/off, local AI on/off,
  backend (Ollama or OpenAI-compatible), model name, and a live **AI connection test**. Saved to `config.json`.
- **First-time tips:** 11 contextual hints (movement, talking, hunger, wilderness, combat, job boards,
  night, ore, company, spells, property), each shown once per save.
- **Feedback:** level-up fanfare and toast (recorded in history), a low-health red vignette, toasts
  moved to the top of the screen.
- **Saves:** an autosave slot (on arrival after travel and after sleeping), a backup of each slot's
  previous save, and automatic fallback to it if the main file is damaged.
- **Balance pass** (measured with the auto-resolver, 60 seeds each):
  - Characters start with an old Rustite dagger. Bare fists lost every two-outlaw fight, which made the
    most common road event a coin-flip robbery.
  - Road ambush group size now scales with route danger (danger 1 roads send 1–2).
  - Starting win rates: 1 outlaw 100%, 2 wolves 97%, 2 bowmen 80%, 3 wolves 55%, 2 outlaws 22%
    (pay or run).
  - Ore values went up (Rustite 6, Greyvein 16, Sunsilver 40, Voidglass 100) and the assayer pays 80%.
    Cinderdeep now really is the best place to sell ore, and smelting adds value (2 ore at 4 → a bar at 12).
- **Performance:** about 6 ms per frame headless in the busiest scenes (a town at night with 4
  companions, the forest at night with enemies).
- **Bugs fixed this phase:** an EventBus keyword clash.

## Ideas beyond scope (not started)
- More hand-written travel events and per-NPC quest lines beyond the favors.
- Companion-to-companion conversations through the local model (the bond system already supplies context).
- Gamepad support, a minimap, key rebinding.

## Session 3 — Phase 8: Base Building
- **Town houses** (`set_system/base.py`, `data/base.json`): six towns have a house for sale (500–1200
  marks), bought at its door. Inside: your own bed (free sleep), a storage chest, a workbench, a stove, a
  desk (spell book or research) and a training dummy. Companions told to rest at home are fully restored
  each day.
- **Outpost at Widow's Crossing:** found it at the outpost site (1500 marks, or 1000 with Crown standing
  20 or more, plus wood and stone). You can't while the Hollow holds the crossing. It sets the
  `outpost_founded` flag, which completes Sir Corin's favor, and is importance-5 history. There are 8
  plots, chosen around the site and stored in the save.
- **Buildings** (10 types): storage shed, workshop (furnace, anvil and workbench; a worker smelts ore
  daily), farm (plant seeds, harvest after 3 days; a worker replants and harvests into storage), well,
  bunkhouse (4 beds each, needed for workers and guards; free sleep; heals workers), palisade and
  watchtower (defense), training yard (assigned companions train combat daily), trading post (a worker
  earns marks from Trading skill and Caravan standing), research hall.
  Construction costs marks plus materials from your pack or outpost storage and takes in-game hours
  (faster with more workers). Buildings can be repaired after raids or torn down.
- **People:** companions with work or guard tasks live at the outpost, with food upkeep from storage.
  Hungry workers lose friendship; a well covers water. Workers stand by their building and guards by the
  centre, and they fight if raiders come.
- **Research** (hall or house desk): Voidglass Smithing (a second route to Voidglass besides the smith's
  notes), Crop Rotation (+50% harvests), Fortification (+50% walls), Caravan Logistics (+50% trade).
- **Raids:** a daily chance that grows with Hollow strength. If you're at the outpost, raiders spawn
  for a **real-time defense**. Winning helps Crown standing and weakens the Hollow; leaving or losing
  counts as a loss. If you're away, defense rating (walls, towers, guards' stats) is compared with raid
  strength. A loss means 30% of storage is stolen and a building is damaged. Every raid is in world
  history and the outpost log.
- **UI:** outpost management (plots, building with costs, assigning, planting and harvesting, repair,
  demolish, guards, log), storage transfer, research, a generic choice dialog, and base building sprites
  (including damaged and crop states).
- **Bugs fixed:** a following companion hijacked E over doors and objects (companions are now the last
  target); healing didn't clear the "down" flag; the treasure branch swallowed the outpost-site landmark.
- Tests: `tests/test_phase8.py`. The smoke tool buys a house through its door, opens the chest, founds
  the outpost, builds six buildings and defends a raid in real time.

## Session 3 — Phase 7: World Simulation
- **World events** (`set_system/world_events.py`): one deterministic roll per day, seeded by world seed
  and date. Each event's consequences are applied by the Set System and written to world history:
  - caravan arrivals restock a town and cut its prices;
  - food shortages raise food and drink prices and post a delivery job;
  - Hollow raids halve shop cash, strengthen the Hollow and post a bounty;
  - Crown–Thornblood skirmishes worsen relations and spawn raider patrols;
  - **wars** raise prices in both sides' towns and spawn patrols (peace by diplomacy prevents them);
  - **named monsters** are 4× HP elites with a bounty, and killing one is world history;
  - fever outbreaks need salves, and if ignored the deaths are recorded;
  - companion debts hurt the relationship if ignored;
  - **festivals** fall on fixed dates.
  Weights depend on season, Hollow strength, faction relations and whether you have a squad.
- **Hollow strength** (0–100) grows daily and drops with every outlaw killed. At 75 or more the Hollow
  **seizes Widow's Crossing** (it becomes an outlaw stronghold). Breaking the Hollow (beating Black Ren)
  scatters it, halves outlaw spawns, frees the crossing, and cuts road ambushes.
- **Honours:** standing 60 or more with a faction grants a title and a gift, recorded in history.
- **Economy:** regional supply and demand by item type (`data/economy.json`) is applied to buying and
  selling, on top of faction standing and event modifiers, so carrying goods between towns pays.
- **Jobs** (`set_system/jobs.py`): every town square now has a job board. Boards refresh weekly with
  bounties (kills are tracked per enemy type, including auto-resolved fights), supply runs for what the
  town lacks, deliveries, and caravan escorts (finished on arrival; they draw more ambushes). Events add
  hunts, food and medicine relief, and debts. At most 5 active jobs, with deadlines; failing one costs
  standing and honesty.
- **Travel encounters** are weighted by world state (Hollow strength, escorts, wars, caravans).
- **UI:** job board scene; journal **News** tab (Hollow strength, titles, current events, world
  history) and **Jobs** tab (jobs and favors with progress).
- Tests: `tests/test_phase7.py` (a deterministic 200-day simulation, each event's consequences, prices,
  territory, honours, all job types, failure).

## Session 3 — Phase 6: Companions & Relationships
- **Recruiting** (`set_system/companions.py`): an NPC who meets their path (main, alt, or a free rejoin
  after dismissal) can be recruited from dialogue. The game asks for confirmation and pays any cost. The
  companion gets a full Character built from their sheet and gear. A test verifies **all 47** can be
  recruited. Recruiting a faction leader records a succession in world history.
- **Squad:** up to 4 active companions. Tasks are follow, gather, wait (here), and guard or work (the
  last two need a home or base, Phase 8). The party screen (P) shows stats, equipment, relationship and
  bonds. The transfer screen moves items and equips a companion's weapons and armor. Dismissed
  companions go home, return shared supplies, and can rejoin for free.
- **Shared needs:** companions' food, water and health tick with time. They eat from their own pack,
  then yours.
- **Companion combat** (`gameplay/companion_ai.py`): follow; engage alerted hostiles near you; block
  telegraphed hits (based on Blocking skill); heal hurt allies with spell numbers computed by the Set
  System, paid with their own mana; retreat when low; use ranged weapons if they have ammo. They go
  *down* (never die in a fight) and get up after it ends. Enemies target companions too. Auto-resolved
  skirmishes include the party.
- **Buddy system:** each day, squad pairs bond or clash based on personality compatibility. Statuses are
  friends, rivals and couple (romanceable pairs), recorded in Set AI. Banter shows as messages.
- **Reactions and shared experiences:** victories and journeys raise friendship and are remembered.
  Killing a companion's own faction members angers them. Kind choices please the friendly ones.
- **Romance in dialogue:** ask out once they're *interested* (affection plus compatibility), spend
  evenings together (once a day), commit after a week of dating with high affection and trust, or break
  up. Jealousy hits current partners. Neglect cools things.
- **Relationships screen (R):** everyone you've met, their values, compatibility, tastes (once friends)
  and shared history from Set AI.
- **Daily hub** (`set_system/daily.py`): one ordered place for once-a-day systems. World events and the
  base hook in here.
- Tests: `tests/test_phase6.py`.

## Session 3 — Phase 5: NPCs & Local AI
- **Client** (`local_ai/client.py`): Ollama `/api/chat` (JSON format) or OpenAI-compatible
  `/v1/chat/completions` (`json_object`). Standard-library HTTP, timeouts, and a cached availability probe.
- **Context** (`local_ai/context.py`): the NPC sheet, personality in words with a speech style, likes,
  their favor, the relationship numbers and mood. It also adds **hard facts** (date, place, dead NPCs,
  world flags, news, faction standing) and **Set AI memories ranked by importance** plus recent small
  talk, the action whitelist and a JSON reply schema.
- **Action bridge** (`local_ai/actions.py`): the model may only request `open_trade`, `share_rumor`,
  `offer_favor`, `check_favor`, `consider_joining`, `note_promise` (recorded with source=local_ai),
  `set_tone` (bounded, once a day) and `end_conversation`. Anything else is rejected. Results go back to
  the model on the next turn.
- **Engine** (`local_ai/dialogue.py`): the worker thread does **only** the HTTP call. Validation,
  actions and memory run on the main thread, because SQLite can't be shared across threads (that bug was
  found in testing). It parses JSON robustly and runs a consistency guard (a reply that mentions a dead
  NPC as alive is rejected and retried, then falls back). Template fallback covers every topic and free text.
- **Set System additions:** `relationships.py` (friendship, trust, affection, respect, conflict;
  compatibility from NPC values vs. the player's behaviour profile; NPC–NPC compatibility; daily talk;
  gifts by likes and dislikes; romance stages interested → dating → partners, plus breakups, jealousy and
  neglect), `favors.py` (deliver, pay, duel, clear an area, world flag; all 21 favors referenced by
  recruitment paths) and `recruitment.py` (main or alt requirement checks).
- **Duels** (`scenes/duel.py`): non-lethal fights against a named NPC whose combat stats come from their
  sheet (`combat.npc_fighter`).
- **Treasures:** one-time loot at landmarks guarded by enemies: the Spire Core plus the Starfall Blade,
  the Skyglass Bow, the Emberheart Hammer, and smaller caches.
- **Peace diplomacy:** Gruka can broker Crown–Thornblood peace (sets a world flag, changes relations,
  and is recorded as importance-5 history).
- **New dialogue screen:** free-text input, topics, favor and duel options, gifts, a recruitment
  requirement checklist, trade, an "AI / offline" indicator and a "thinking..." state.
- **Bug fixed:** flags stored the day index, so anything set on day 0 read as false. Flags now store True.
- Tests: `tests/test_phase5.py` uses a **fake local model server** (both APIs) to cover whitelist
  enforcement, money safety, promise recording, the dead-NPC guard, unreachable-model fallback and the
  threaded path.

## Session 3 — Phase 4: Items & Magic
- **Crafting** (`set_system/crafting.py`, `data/recipes.json` plus recipes generated by the loader):
  98 recipes. Smelting (ore → bar; 3 scrap → Rustite bar), all 16 weapon types in all 4 ores, helms and
  mail in all 4 ores, leather armor, tools, ammo, leather and cloth, medicine, food, building materials
  (planks, nails, stone blocks), magical materials (arcane dust, enchanted ink) and seeds.
- **Stations:** furnace, anvil, workbench, stove, alchemy table, campfire (cook or rest). They are placed
  in building interiors by type. Crafting skill gates ore tiers (0/10/25/45). Voidglass work requires
  *Voidglass Smithing Notes*, sold by the smith or researched later. Crafting takes time and trains
  Crafting and Dexterity.
- **Armor:** head and body slots, with armor values feeding combat damage reduction.
- **Spells:** a design screen (element → sub-element → movement → effect → tier, with a live preview of
  every computed number; creating is free). A practice yard tests a draft on training dummies before
  committing. Inscribing needs a scribing table and Enchanted Ink. A full book forces a replacement,
  which also costs a Mana Crystal. Spells can be reordered for the 1–4 hotkeys. Training dummies in
  barracks and arenas train combat skills.
- Tests: `tests/test_phase4.py`. `tools/ui_smoke.py` opens and drives every screen headlessly.

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
