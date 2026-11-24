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
| Visual overhaul (art, animation, VFX) | ✅ Done |
| Universal targeting & consequences | ✅ Done |
| NPC & enemy visual variety | ✅ Done |
| Quality of life update | ✅ Done |
| Major combat overhaul | ✅ Done |
| Major RPG overhaul (spells, creator, visuals, looting, prisons) | ✅ Done |
| Bug fixes & visual consistency | ✅ Done |
| Chibi characters | ✅ Done |
| Chibi bodies, map, travel, bases, bosses | ✅ Done |

## Session 12c — Back to the original heads

- Chibi mode is switched off (`charsprites.CHIBI = False`): characters use the rig's own heads and normal-size
  bodies again, pixel-identical to v1.0.6 (checked by hashing 52 looks x 4 animations against that commit).
  Portraits, the creator preview, overhead names, barks and health bars are back at their v1.0.6 positions.
  The chibi head code stays in `chibi.py` and is still tested, in case it's wanted later.

## Session 12b — Head size

- Heads read as bobble-heads. Now in between the original rig and the big chibi: the head is drawn at its
  native pixel grid (1.0x, keeping faces crisp; shrinking it smudged the eyes) on a fuller body (1.4x), so the
  head is about shoulder width. A test bounds the head-to-body ratio both ways.

## Session 12 — Chibi bodies, world map, travel, bases of operations, bosses

- Bodies: the rig is painted at its own size, then enlarged 1.3x about the feet (Scale2x, then sampled) and the
  chibi head 1.15x, so head and body match like the reference sprites (about two and a half tiles tall).
  Region detection runs on the original frames (enlarging first broke the neck detection and floated the head);
  weapon grips, smears and back-slung gear are mapped onto the enlarged frame (`charsprites.to_frame`,
  `frame_info`). Frames sit 8px lower (`FOOT_Y`) to leave room for hats.
- World map: a painted parchment map (watercolour regions, forests, mountains, marshes, dunes, ruins, sea,
  compass, cartouche) with inked roads, label plates, town houses, danger dots, job scrolls, home icons and boss
  skulls. Goals (jobs, homes, bases, any place) plot the whole multi-stop route in red with arrows, a flag at
  the end, distance, hours and the next stop; the next stop is preselected. Click a place to pick it.
- Travel: sky by time of day (sun and moon arcs, stars, clouds, dusk colours), three parallax layers per terrain
  using pack trees and rocks, the party walking (companions behind), a campfire at night when stopped, fog, and a
  route ribbon (from, you, to, goal). Status layout fixed (bars no longer under the menu).
- Starter house: a new character owns the for-sale house in the starting town (deed, a few supplies), so they
  have a bed, chest, workbench, scribing table and a prisoner cell from day one.
- Bases of operations (`set_system/bases.py`, `scenes/bases.py`, Tab menu): every house and the outpost with
  beds, cells, stored goods and facilities; a home base; route to any base on the map; a carter between bases
  (road time, safe, 3 marks per 10 km).
- Bosses (`data/bosses.json`, `set_system/bosses.py`, `gameplay/boss.py`): Varek the Hollow Warlord (Hollow Fort),
  the Bog Mother (Mirelight Bog) and the Ashen Colossus (Ashfall Crater). Phases by health (minions, faster
  attacks, enrage), telegraphed area attacks (a red ring fills before it strikes; the Bog Mother aims around
  you), a boss health bar with phase notches, large sprites, a defeat that lasts, guaranteed rewards on the
  body, reputation and Set AI history. Lairs show on the map; the guide explains them.
- Bug caught by the tests: a boss defeated on day 0 stored flag value 0 and still counted as alive.
- 228 tests (`tests/test_bases_bosses.py` added); the fuzzer now includes a boss lair.

## Session 11 — Chibi characters

- Every humanoid (player, companions, NPCs, townsfolk, humanoid enemies) now has a big chibi head drawn by
  `presentation/chibi.py`: a 16x14 face with 4x5 anime eyes (thick lash with a flick, three-tone iris, two
  catch-lights), nose, mouth by expression, soft skin shading, an outline, and voluminous hair for all 10 styles
  (fringe, side locks, glossy highlight, spikes, bun, ponytail, braids, long hair split into a layer in front of
  the shoulders and one behind the body). Beards, hats (all 10), helmets, hoods, glasses, eyepatches, earrings,
  face marks, face paint and race features (sylth ears, murrok furred ears and tusks, kethari stone flecks)
  are redrawn for the bigger head. Front, side and back views.
- Moods: squeezed `> <` eyes and an open mouth on the hit animation, closed eyes when knocked out, `^ ^` for
  grinning characters.
- The body rig is unchanged, so every animation, outfit, cape, weapon and the creator still work:
  `charsprites` removes the rig's small head each frame and places the chibi head at the same spot, so it bobs,
  leans and turns with the body, and rotates when the body lies down. Head-only wardrobe pieces are skipped in
  chibi mode (`wardrobe.apply(chibi=True)`). Heads are cached per look, view and mood.
- Reworked around the taller sprites: menu portraits (30x42 crop) and their scaling in dialogue, party,
  character and creator screens; overhead names, barks and enemy health bars moved up; main-menu party spacing.
- Tests: chibi heads for every hairstyle, hat, race, beard, helmet, hood, expression, accessory and mood in
  every view and animation, and a proportion check (head clearly wider than the body). 220 tests.

## Session 10 — Bug fixes and visual consistency

- **Spell book crash** (`KeyError: 'ash#0#1.5'`): `spells.compute()` stored the visual style key (sub-element or
  element id, plus `#hue#intensity` for colour variants) in the field called `sub`, and the spell book looked
  that up as a sub-element. Any variant spell, and any spell without a sub-element, crashed the detail view.
  Fixed at the source: `sub` is the real sub-element (or None), `style` is the VFX key; combat and VFX read
  `style`; display uses `spells.source_name()`.
- Saved spells from older rule sets are now repaired (`spells.repair`): mismatched sub-elements move to their
  element, invalid effects/behaviours/tiers reset, sliders clamp. Changes are shown after loading instead of the
  spell silently disappearing. `normalize` also fills missing movement/effect/tier.
- `tests/test_spell_matrix.py`: every valid element × sub-element × movement × effect × behaviour combination
  (thousands) computes and describes; every source with colour variants draws in the spell book and every
  designer field; every source saves, loads and casts; every movement casts; broken old spells are repaired.
- `tools/fuzz.py`: random keyboard and mouse input on every screen and in the world (town, wilds) with
  invariants (no negative counts or gold, mana and health in range). Runs in CI. Clean on several seeds;
  pyflakes clean; every asset reference resolves.
- Icons: one fantasy icon sheet for all interface icons (items with ore-tier recolouring, elements,
  sub-elements, effects, attributes and skills, actions). Shown in inventory, item cards, shops, crafting,
  storage, transfer, loot, spell book, designer, HUD (weapon and spells), the E prompt, dialogue choices,
  stranger and Tab menus, and job markers on the world map; towns get pixel-art house markers. Dropped loot
  uses the same icons reduced to world scale.
- Characters: anime-style fringe and side locks for every hairstyle, mouths with expressions (neutral, smile,
  grin, stern, sad) chosen from NPC personality and selectable in the creator, eye shine kept; cast pose now
  spans the whole cast.

## Session 9 — Major RPG overhaul: spell customization, character creator, visuals, looting, prisons

- Spell designer: duration, potency, speed and range sliders beside size; behaviours (Standard, Piercing,
  Volley, Lingering, Quickcast) limited by movement class; colour variants and effect intensity (visual, free).
  Every option feeds the mana formula and the designer shows a cost breakdown (each factor, more/less). Runtime:
  volleys fire 3 weaker missiles, piercing missiles pass through 2 more foes, lingering spells leave a short
  field, quickcast halves recast. VFX variants are generated per colour/intensity (`vfx._variant`). Spell book:
  copy (C), delete (X) with confirmation, rename by editing. Old spells load with neutral defaults.
- Attack from conversation: an Attack option in every NPC dialogue and a Chat/Trade/Attack menu for anonymous
  townsfolk and shopkeepers, with a warning that names the consequences. It uses the normal assault path
  (aggression, witnesses, bounty, guards) and a settlement alarm makes townsfolk nearby wary.
- Looting (`set_system/loot.py`, `scenes/loot.py`): coins and materials burst out of the fallen and bounce
  (pick up by walking over them); gear stays on the body (a bag marks it; E to search). Bodies and containers
  open a loot panel sorted by kind (money, equipment, food, materials, valuables) with take one / take all /
  money only. Contents are seeded and removed on taking (no duplication); container contents persist in the
  location save and refill after 3 days. Taking from townsfolk or their containers is reported if seen.
  Quick-deposit of materials (Q) at storage. Item icons (`presentation/icons.py`): pack weapon sprites plus
  hand-made 12 px pixel art replace the old coloured dots.
- Prisons: house cellar (1 cramped cell) and the new outpost Stockade (4 decent cells); retainer beds (1 per
  house, 2 at the outpost, 4 per bunkhouse). Capture and recruitment are blocked without room and say why.
  Conditions change loyalty/resentment daily; captives can be moved between cells. Old prisoners get a cell.
- Character creator (`scenes/creator.py`): skin tones per race (plus lighter/darker), build, height, eye colour
  and style, face marks (freckles, blush, scar, beauty mark, tattoo), face paint, facial hair, 10 hairstyles,
  hair colours incl. vivid ones, outfit and colours, trousers, boots, belt, cape, hats, 9 accessories, randomize,
  undo; live preview idle/walk/attack in four directions. Reachable from new game and the Tab menu.
- Visual pass: eye catch-lights and iris colours, hair sheen, NPC eye colours and occasional face details;
  buildings get type-specific architecture (pictogram shop signs, awnings, steeples, mage spire, battlements,
  flags, hipped roofs, forge glow and smoke, barn doors, hides, laundry, for-sale signs) and wealth cues (gilded
  trim, patched roofs); regional colour grading per biome and town; a pulsing outline on the current
  interactable; outpost buildings use the town textures.
- Tests: `tests/test_rpg_overhaul.py` (24) incl. old-save migration. 211 tests in total. Frame time in towns
  ~6.5 ms headless.

## Session 8 — Major combat overhaul

- Audit first: attack phases (32/14/54% of a cycle, slow-weapon "reloads" ~1.8 s), 0.6–6 s spell cooldowns plus a
  0.25 s cast lock, 16 fixed sub-elements with no element-only spells, one enemy type per spawn point (many
  dropped at map generation), five towns without gear shops.
- Faster combat: tempo ×1.3, shorter ranged recovery, recovery cancels, cast/attack chaining, wind-up/draw
  cancel into spells, movement while acting, quicker dodges.
- Mana: 80 + 2/Magic + 5/level, 5% / 2.5% regeneration per second, 40% hit recovery (cap 12).
- Magic rebuilt (data-driven): 5 elements with identities and affinities (Light added; Lightning to Air,
  Gravity to Earth, new Mending and Sanctuary), optional sub-elements, 5 new movement classes (burst, chain,
  trap, barrier, self), focuses, size slider, cost model by size × movement, per-caster limits. Old saved
  spells migrate automatically (`spells.normalize/migrate`). New designer UI with live cost and footprint; VFX
  for the new classes and element-only spells.
- Enemy AI: threat targeting, morale, missile dodging, spellcasting through the same framework, caster
  spacing, regrouping, calls for help. Five new caster enemies; data-driven encounter templates
  (`data/encounters.json`, `set_system/encounters.py`).
- Towns: outfitters in 6 towns, town-scaled and faction stock (`economy.stock_def`), coin loot by danger,
  guards, crime and bounties, theft and robbery, fines, seizing towns with taxes, discounts and retaking
  (`set_system/crime.py`).
- Morale, surrender, prisoners and retainers (`set_system/morale.py`, Prisoners screen in the Tab menu).
- Local AI context: bounties and seized towns as hard facts. The model still decides nothing.
- Bug caught in testing: the town-guard flag reused the name of the block-stamina meter (`guard`); renamed
  to `is_guard`.
- Performance: a 43-combatant fight with continuous spells averages 13.6 ms/frame (p95 21 ms) headless.
- Tests: `tests/test_overhaul.py` (30). Old tests updated where rules changed intentionally (element and
  sub-element counts, short recasts, morale-based fleeing). 187 tests in total.

## Session 7 — Quality of life: mana, movement, UI and guidance

- Mana rework (Set System, `spells.py` / `stats.py`): larger pool (40 + 1.2/Magic + 3/level), real-time regeneration
  (3%/s calm, 1.2%/s in combat), mana from weapon hits (30% of damage, cap 8). Spell design, editing (new) and
  inscription work anywhere for free. The HUD shows the regeneration rate and per-spell cost ticks on the bar, and
  says why a spell can't be cast.
- UI: a wood/parchment theme in `ui/widgets.py` (planked panels, brass studs, title plaques, parchment
  cards/tooltips, keycaps, framed bars, selection markers), so every screen picked it up. Notifications are
  parchment slips colour-coded by kind, with sounds; duplicates refresh instead of stacking. Scalable window
  and F11 full screen (pygame SCALED). Text renders are cached; menus reuse a snapshot of the paused world
  (inventory frame 12.3 ms -> 7.4 ms).
- Movement: velocity with acceleration/deceleration, corner sliding, 15% faster walking for the player, smoothed
  camera with look-ahead, footsteps, page-turn/coin/save/warning sounds, floating gain pop-ups.
- Clarity: `knowledge.py` derives item sources and uses, crafting-station towns, money methods, job next steps
  and place summaries from the data. The Adventurer's Guide (H, 13 chapters). Inventory filters, sorting,
  comparison and item cards; crafting shows where missing ingredients come from; shops keep unaffordable and
  unsellable items visible with the reason; the world map describes resources and enemies; the Jobs tab has a
  "Next:" step; prompts show refusal reasons and action durations; relationship/faction standing changes
  are announced; quick-load asks first; save messages include the date.
- Tests: `tests/test_qol.py` (14) covers mana growth, regeneration, hit recovery, limits, failure messages,
  inscription anywhere, knowledge coverage for every item and station, guide chapters, the Tab menu, movement
  ramp and glide, and save/load. One old test that required a scribing table was updated to the new rule.
  157 tests in total.

## Session 6 — NPC and enemy visual variety

- `wardrobe.py`: modular hair (10 styles), beards (4), headwear (cap, wide hat, wizard hat, crown, bandana, horns,
  circlet, miner's lamp-helmet, feathered cap, hood), outfits (tunic, robe, dress, coat, vest, apron,
  tabard, bare), capes, belts, accessories (necklace, scarf, satchel, eyepatch, glasses, pauldrons, quiver,
  earring, fur) and body builds. Drawn from per-frame body regions, so every piece follows every
  animation in all four directions, with the pack's outline style.
- Fixed head segmentation on the rig: the head now runs to the chin (neck detection). Previously the lower
  face was painted with the shirt colour (it looked like a collar), and on hit frames most of the face was.
- `looks.py`: identities for all 47 named NPCs (occupation, faction, age, pronouns, personality, race build),
  role pools for townsfolk and per-spawn enemy variants. NPC data, dialogue, relationships and behaviour
  are untouched.
- Ambient town crowds (anonymous, daytime, profession and race mix per town).
- Enemies: three more pack skeleton variants imported for husks; creature marking variants, biome tints,
  golem hues, elite scaling, and proper death poses for brutes, lurkers and golems (rubble, mound, shards).
  Enemy stats, AI and behaviour are unchanged.
- Evaluated but not used: the pack's orcs (no orc enemy exists; adding one would change gameplay) and the
  Knight/Rogue/Wizard/Citizen NPC sheets (side view only, no attack or hit frames). See ASSETS.md.
- `tools/character_gallery.py` renders all NPCs, townsfolk, enemy variants, creatures and husks.
- Tests (+5): all named NPC looks unique; at least 6 headwear types, 6 outfits and 7 hairstyles in use; looks stable; every
  NPC has every combat animation in every direction; enemy variants differ; husk variants load. 142 total.

## Session 5 — Universal entity interaction and combat

- Every character is attackable. Townsfolk, shopkeepers and camp NPCs are now combatants on a neutral
  `npc` team (`gameplay/bystander_ai.py`), so they share the combat runtime, animations, hit feedback,
  knockback and defeat poses with everyone else.
- Hostility is a team default plus personal grudges (`CombatWorld.hostile_between`). Hostile intent (G)
  lets the player's attacks connect with anyone, including companions; without it only foes are hit, so
  nothing happens by accident.
- `set_system/aggression.py` (deterministic): reactions (fight / flee / call for help / cower / yield),
  bystander responses to cries for help, companion reactions (join / stand / object / defend / leave),
  and consequences: relationships, faction standing (victim's faction, plus the town's faction if
  witnessed), player profile, statistics, Set AI records and facts.
- Defeat vs death: 0 HP knocks a person down; named NPCs recover at home (1 day) and hold a grudge
  (3 days). A finishing blow with hostile intent kills permanently (`npc:<id>:alive` = False, which
  schedules, shops, recruitment and the Local AI already respected). Leaders' deaths trigger succession;
  Black Ren's breaks the Hollow. Bodies persist on the map, with a blood pool; downed people show
  dazed stars.
- Companions who come to blows with the player decide afterwards (or when you leave the map) whether to
  stay; a killing can make a disapproving companion leave for good.
- Local AI context gains hard facts: "the player attacked you", known violence nearby, the player's kill
  count. The model never decides any outcome.
- Hostile NPCs refuse to talk or trade; names turn red; hurt NPCs show health bars; `in_combat` covers
  hostile townsfolk and companions who turned on you (music, resting, map exits).
- Tests: `tests/test_aggression.py` (13): personality-driven, deterministic reactions; no protected
  characters by default; assault, defeat and kill consequences; shop handover; peaceful swings don't hurt
  bystanders; execution needs intent; enemies ignore townsfolk; companions attackable and reacting;
  falling-out settlement; identical replays. 137 tests total.

## Session 4 — Visual Overhaul (presentation only)

Goal: make characters, combat, spells and places look and feel better without touching gameplay.
Source art: the uploaded *Pixel Crawler – Free Pack* by Anokolisa (free incl. commercial, may be altered,
can't be resold as assets; not CC0). Only a 58-file subset was imported. See `ASSETS.md`.

### Phase 1 — Visual audit
- Old art: 16×24 procedural characters with 4-frame walk, a line for a weapon, creatures as single blobs,
  spells as coloured circles, flat-colour tiles. The pack matches our 16 px grid and outline style.

### Phase 2 — Character animation
- `charsprites`: the pack's Body_A rig (idle, walk, run, slice, pierce, crush, hit, death, collect in
  3 directions, mirrored for the 4th). Baked tools are stripped; skin/hair/shirt/armour/pants/boots regions
  are found by erosion and recoloured per character; race features drawn on (Sylth ears, Murrok tusks,
  Kethari freckles, war paint).
- `weapons_art`: every weapon type drawn from the pack's weapon sheet, head recoloured by ore, posed at the
  hand each frame; carried on the back while walking. Bows, crossbows and firelocks are distinct.
- `animator`: attack phases map to anticipation (frames 0–2), strike (3–4) and follow-through (5–7);
  smear arcs scale with weapon size. Casting raises the hands, blocking holds a guard pose, dodges leave
  after-images, stagger shakes, death plays the collapse and fades.
- `creatures`: wolves, ice wolves, skitterers, sand wurms, stone brutes, bog lurkers, crystal golems and
  dummies each have idle / move / windup / strike / hit / death frames; big enemies are drawn big. Husks use
  the pack skeleton. Humanoid enemies wear role outfits (hooded cutthroats and archers, armoured
  shieldbearers, a dark captain with a red smear, painted Murrok raiders).

### Phase 3 — Spell effects
- 16 sub-element styles, each with its own glyph, particle, beam and ground pattern (crystalline ice shards,
  branching lightning, molten rock with dripping embers, ash flakes, steam clouds, blood droplets, poison
  bubbles, spinning metal blades, faceted gems, sand swirls, leaves and vines, wind crescents, expanding sound
  arcs, gravity wells pulling particles inward, radiant stars).
- Movement classes look different: projectiles with trails, homing ribbons, beams, growing waves,
  telegraphed areas that gather then burst, bounded ground zones, orbiting motes, ward totems, auras.
- Cast flourish (rune circle + sparks), hand glow while casting, element impacts, spell light at night.

### Phase 4 — Combat presentation
- Per-attack-type impacts: cut lines and blood for blades, dust rings, debris and stars for blunt weapons,
  splinters for arrows, smoke for firelocks, blue sparks for blocks, shattering for guard breaks, dust for
  dodges, knockback dust trails, stagger stars, status particles (burn, bleed, poison, chill, roots…).
- Damage numbers pop, rise and scale with damage; a red edge flashes when the player is hurt.

### Phase 5 — Environment
- Ground textures from the pack tinted to each biome's existing palette, ragged transitions between tile
  types, animated water with shoreline foam.
- Trees, rocks, bushes, crystals and ore veins (ore-coloured specks; greyed when depleted) chosen per biome.
- Ground clutter (flowers, mushrooms, pebbles, reeds…) per biome; non-colliding.
- Towns: textured facades and roofs with a style per town (log/thatch Brackenford, plaster-brick/slate
  Velmora, dark planks Cinderdeep, plaster Saltmarket…), windows lit at night, chimneys, flower boxes,
  banners. Interiors use pack furniture and stations; campfires animate.
- Character previews in menus, dialogue, party and travel use the new sprites.

### Phase 6 — Polish & testing
- `tests/test_visuals.py` (7 tests): rendering doesn't change a seeded battle; event queue is bounded;
  all 16 sub-elements have unique looks; every enemy/race/direction has frames; ground tiles are opaque;
  the game still draws with the art folder missing. Total: 124 tests pass.
- `tools/vfx_gallery.py` (every sub-element × movement), `tools/env_tour.py` (screenshot any location or
  interior), `tools/preview_assets.py`.
- Performance: ~7.5 ms per frame with 8 enemies and continuous spells in a headless run; particles capped
  at 450; sprite frames cached on first use (~2 ms each).

### Unchanged by design
Combat maths, stats, speeds, spells, weapons, AI, NPC behaviour, saves, world structure, controls.
Collision still uses tiles; big trees only change how things look.

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
