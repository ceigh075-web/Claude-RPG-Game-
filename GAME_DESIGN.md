# Kindred Roads — Game Design

A small, interconnected 2D open-world RPG. The player starts with almost nothing in a
farming village and grows into a figure who shapes the politics of a nine-town region.

Inspirations (philosophy only, nothing copied): open-ended squad survival, Oregon-Trail-style
text travel, life-sim world events, and companion friendships/romance.

## Pillars

1. **Small world, deep links.** 9 towns, 20 wilderness areas, 47 named NPCs. Every system feeds others.
2. **The world remembers.** An append-only history (Set AI) that dialogue must respect.
3. **Conversation is AI, reality is code.** The local model talks; the Set System decides.
4. **Everyone can join you.** All 47 named NPCs have a recruitment path.
5. **Playable at every stage.** No menus that do nothing.

## Hard scope limits

| Thing | Count |
|---|---|
| Towns | 9 |
| Wilderness areas | 20 |
| Named NPCs | 47 (target range 40–50) |
| Weapon types | 16 (12 melee, 4 ranged) |
| Ores | 4 |
| Primary elements / sub-elements | 4 / 16 |
| Races | 4 |
| Factions | 6 |
| Enemy archetypes | 12 |

## Races (data/races.json)

| Race | Look | Strengths | Weaknesses |
|---|---|---|---|
| **Human** | Varied skin, hair | Balanced; +trading, +learning speed | No standout attribute |
| **Kethari** | Grey/ochre stone-flecked skin, stocky | +Strength, +Health, mining | −Speed, slow magic learning |
| **Sylth** | Tall, pale-blue/lilac, long ears | +Dexterity, +Speed, magic affinity | −Health, eat less but need more water |
| **Murrok** | Furred, tusked, broad | +Health, +Strength, foraging/hunting | −Dexterity with fine crafting, mistrusted in Crown towns |

## Factions (data/factions.json)

| Faction | Leader | Seat | Goal |
|---|---|---|---|
| **Crown of Velmora** | Queen Aldra Venn | Velmora | Order; tax the roads; contain the Hollow |
| **Ironhold Guild** | Guildmaster Borun Kett | Hammerlee | Control ore and smithing |
| **Free Caravan League** | Sela Marrow | Saltmarket | Open trade routes, low tolls |
| **Ashen Circle** | Archmage Ivo Thale | Glimmerfen | Study and regulate magic |
| **Thornblood Clans** | Warchief Gruka | Thornhollow | Murrok sovereignty over the Thornwild |
| **The Hollow** | Black Ren | Hollow Fort | Outlaw brotherhood; raid the roads |

Reputation runs −100…+100 per faction. Faction-to-faction relations shift through world
events (wars, trade pacts). Hurting a member lowers rep; trading, jobs and gifts raise it.
Helping one side of a conflict lowers rep with the other.

## World map (data/locations.json)

A node graph. Towns and wilderness areas are nodes with map coordinates. Routes are edges with
a distance (km) and terrain. Travel is only along routes.

### Towns

| Town | Specialty | Faction | Notes |
|---|---|---|---|
| **Brackenford** | Farming (start) | Crown (loose) | Cheap food, starter jobs, cheapest house |
| **Velmora** | Military / capital | Crown | Barracks, bounty board, armor |
| **Cinderdeep** | Mining | Ironhold | Mine jobs, ore buyers |
| **Hammerlee** | Crafting / smithing | Ironhold | Best forges, weapon recipes |
| **Saltmarket** | Trading port | Free Caravans | Best prices, exotic goods, caravan contracts |
| **Glimmerfen** | Magic | Ashen Circle | Spell tutoring, mana items, enchanting |
| **Redwater** | Mercenaries | Independent | Hire swords, fighting pit, bounties |
| **Thornhollow** | Murrok clan seat | Thornblood | Hunting, hide, shamanism |
| **Duskreach** | Frontier outpost | Crown garrison | Gateway to the dangerous east, scavenging |

### Wilderness areas (danger 1–5)

| # | Area | Biome | Danger | Reason to visit |
|---|---|---|---|---|
| 1 | Meadowrun Fields | Grassland | 1 | Forage, easy hunting |
| 2 | Old Mill Woods | Forest | 1 | Wood, herbs, ruined mill scavenging |
| 3 | Rustback Hills | Hills | 1 | Surface Rustite veins |
| 4 | Cinder Pass | Mountain | 2 | Rustite + Greyvein, rockfalls |
| 5 | The Deep Galleries | Mine/cave | 3 | Greyvein and Sunsilver deep veins |
| 6 | Frostfang Ridge | Snow mountain | 3 | Sunsilver veins, ice wolves, hunter Ysolde |
| 7 | Kingsroad Verge | Grassland road | 1 | Caravans, toll patrols |
| 8 | Saltwind Dunes | Desert coast | 2 | Salt, scavenging, sand-wurms |
| 9 | Wrecker's Cove | Coast ruins | 2 | Shipwreck loot, smugglers |
| 10 | Mirelight Bog | Swamp | 2 | Rare herbs, poison reagents, hermit Margit |
| 11 | Sunken Abbey | Ruins | 3 | Magic relics, husks |
| 12 | Greywood | Forest | 2 | Hardwood, bandit scouts |
| 13 | Redrock Canyon | Canyon | 3 | Bandit camp, captive Nix |
| 14 | Thornwild | Dense forest | 3 | Thornblood territory, hides |
| 15 | Ashfall Crater | Volcanic | 4 | Voidglass deposits |
| 16 | Duskmoor | Moorland | 3 | Husks at night, lost caravans |
| 17 | The Shattered Spire | Ancient ruins | 5 | Endgame relics, legendary gear, Voidglass |
| 18 | Hollow Fort | Bandit stronghold | 4 | The Hollow's base, Black Ren |
| 19 | Widow's Crossing | Abandoned village | 2 | Central crossroads, knight Corin, **outpost site** |
| 20 | Starfall Basin | Crystal valley | 4 | Crystal golems, Voidglass, mana crystals |

## Ores (data/ores.json)

| Ore | Rarity | Value (raw) | Character |
|---|---|---|---|
| **Rustite** | Common | 6 | Heavy, cheap, low durability. Starter gear. |
| **Greyvein Iron** | Uncommon | 16 | Balanced, durable, best armor per cost. |
| **Sunsilver** | Rare | 40 | Light: +attack speed, mild mana conduction. |
| **Voidglass** | Very rare | 100 | Highest damage, strong mana conduction, brittle. Requires knowledge (smith's notes or research). |

Ore → bar at a forge (2 ore = 1 bar). Every metal weapon/armor = bars + common materials.
Weapon items are generated as `weapon type × ore` (e.g. `longsword_greyvein`).

## Weapons (data/weapons.json) — 16 types

Melee: Fists, Knuckles, Dagger, Short Sword, Long Sword, Greatsword, Axe, Battle Axe, Spear,
Polearm, Hammer, Mace. Ranged: Bow, Crossbow, Throwing weapons, **Firelock** (hand cannon:
short spread blast, huge knockback, very slow reload, uses powder).

Each has damage, attack speed, reach, arc, knockback, stagger, stat scaling, two-handedness and a
special trait (dagger backstab, spear thrust reach, mace armor-break, etc.).

## Combat (Phase 3)

Real-time, top-down. Every attack has **wind-up → active → recovery** phases whose lengths come from the
weapon's speed and the attacker's Dexterity and skill. Hits are tested against the weapon's **reach and arc**.

| Action | Notes |
|---|---|
| Attack (K / left mouse) | Melee chains into a 3-hit combo; the 3rd hit is a finisher (+40% damage, more knockback and stagger). Bows are held to draw (up to +80%). |
| Kick (F) | Short reach, big knockback, damages an enemy's guard. 1 s cooldown. |
| Block (L / right mouse, hold) | Covers a 150° front arc. Reduces damage to 8–30% (better with Blocking skill) and costs **guard**. When guard runs out, or a hammer or battle axe hits, the block breaks and the blocker is staggered. Moving at 45% speed. |
| Dodge (Space) | 0.32 s roll with 0.24 s of invulnerability. 0.65 s cooldown. |
| Spells (1–4) | Cast from the spell book (see Magic). Starter spells: *Ash Dart* (projectile damage) and *Mending Light* (heal aura). |
| Switch (Q) | Toggle between the melee and ranged weapon. |

- **Knockback** depends on the weapon, Strength and the target's mass. **Stagger** interrupts a target
  whose poise is lower than the hit's stagger value. Heavy enemies have high poise.
- **Weapon traits:** dagger backstab ×3, axe/battle-axe bleed, mace ignores half of armor,
  hammer/battle-axe break guards, longsword/greatsword/polearm sweep several targets, spear has the
  longest reach, crossbow bolts pierce, firelock fires a 5-pellet spread, thrown knives can be picked up again.
- **Status effects:** bleed, burn, poison and scald (damage over time); chill (slow); root and entangle;
  shock and stagger; blind (attacks miss 50%); pull; pierce (armor broken).
- **Learning by doing:** landing hits trains the weapon skill and the attributes that weapon scales with.
  Taking damage trains Health. Blocking and dodging train their skills.
- **Defeat is not death:** you are knocked out. Outlaws rob you; beasts eat your food. You wake up weak.

### Enemy AI (deterministic)
Enemies read distance, both sides' reach, the player's attack phase (a wind-up is a threat; recovery is an
opening), their own health, nearby allies and line of sight.

- **Aggressive:** presses in and punishes the player's recovery.
- **Defensive:** advances behind a raised guard, blocks telegraphed hits, then counterattacks.
- **Fast:** hit-and-run in packs, circling and lunging.
- **Heavy:** slow, high poise, long telegraphed swings that break guards.
- **Ranged:** keeps 90–200 px away, strafes, needs line of sight.
- **Intelligent:** waits at the edge of its reach, dodges or blocks, and its group flanks from different sides.

Only **two attackers** may swing at once (attack tokens), and every archetype pauses between attacks, so
fights stay fair and readable. Wounded enemies flee. Enemies that escape, or groups the player runs from,
**remember** the player: this is recorded in Set AI, and next time they notice the player from 50% farther away.
Defeated groups respawn after 4 days. Faction members (Thornblood raiders) are neutral unless provoked or
your standing is low, and attacking them costs reputation.

**Road fights:** a travel event that becomes a fight lets you choose: *fight it out* in a real-time arena
(walk off either side to flee) or *let it play out* (resolved by the Set System).

## Character looks

- **Named NPCs** each have an identity built from their occupation (smith's apron, miner's lamp-helmet,
  queen's crown and cape, archmage's pointed hat and long beard, warchief's horned helm and furs...), faction
  colours (tabards, capes, clothes), age (greying hair, balding), personality (the greedy wear jewellery, the
  sociable bright colours, the shifty hide behind scarves and hoods) and race build (broad Murrok,
  willowy Sylth, compact Kethari). Looks are deterministic per NPC and only affect appearance.
- **Townsfolk**: towns have an anonymous daytime crowd (3-7 people) dressed for the local trade - farmers in
  Brackenford, miners in Cinderdeep, smiths in Hammerlee, traders and dockhands in Saltmarket, mages in
  Glimmerfen, clan warriors in Thornhollow - with each town's racial mix. They can be greeted and, like
  everyone, attacked.
- **Building blocks** (`wardrobe.py`): 10 hairstyles, 4 beards, 9 kinds of headwear, 8 outfits, capes,
  belts, 9 accessories, stout/slim builds and tall/short heights. All are drawn per animation frame,
  so every combination has the full set of animations: walk, run, three attack styles, hit, death and cast.
- **Enemies**: humanoid enemies get a fresh variant for each spawn within their role (hooded or bandana'd
  cutthroats, feather-capped archers with quivers, Hollow soldiers in grey tabards, caped captains, painted
  Murrok raiders in furs and horns). Husks are one of four pack skeletons (plain, hooded rogue, armoured
  warrior, robed mage). Creatures get marking variants (saddle-backed or pale wolves, spined or spotted
  skitterers, striped or spiked wurms, mossy or crystal-studded brutes, mushroom-capped bog lurkers),
  natural creatures take on a little of their region's colours, golems come in three mineral hues, and
  elite/named monsters are drawn half again as large with capes and horns.

## Violence against anyone (universal targeting)

Every living character can be attacked: enemies, wildlife, townsfolk, shopkeepers, faction leaders,
recruitable NPCs and your own companions. Nobody is invulnerable by default.

- **Targeting.** Normal attacks only connect with enemies, so a swing in a crowded square can't hurt
  anyone by accident. Press **G** for *hostile intent*: with it on, melee, arrows and spells connect with
  whoever they touch. Anyone who is fighting you is a normal foe and can be hit without intent.
- **Reactions** (Set System, `set_system/aggression.py`, from personality and fighting skill):
  fight back, flee, call for help (nearby people may join in, flee or just watch, depending on their own
  courage, ties to the victim and how much they like you), cower when cornered indoors, or yield when badly
  hurt. Anyone you attack holds a grudge for 3 days: they won't talk or trade, and they may attack or run
  when they see you again.
- **Companions** react by personality, loyalty, their relationship with you and their ties to the victim
  (same faction, same home, friendship). They may join you, stand aside, object, or turn on you to
  defend the victim. Seeing a killing can make a companion leave for good. A companion you fought
  decides once things calm down whether to stay.
- **Defeat and death.** At 0 HP a person is *defeated*: knocked down, not killed. Named NPCs then stay home
  injured for a day. Only a deliberate finishing blow (hostile intent on) on someone lying defeated kills
  them, and death is permanent: they leave every schedule, shop and recruitment list, and the Local AI is
  told they are dead. Killing a faction leader triggers a succession (killing Black Ren breaks the
  Hollow). Bodies stay where they fell for the rest of the visit.
- **Consequences.** Assault: the victim's friendship and trust drop sharply and conflict rises; you lose
  standing with the victim's faction and with the faction that runs the town, if anyone saw it. Killing
  costs much more, hurts your standing with everyone who knew the victim, and counts on your record.
  All of it is written into the Set AI's history (`assault`, `defeated`, `death`, `witnessed`,
  `political`) so NPCs, the journal and the Local AI can refer to it later.
- **Exceptions** belong in data: an NPC with `"protected": true` (or listed in
  `aggression.PROTECTED`) can still be attacked and defeated but not killed. The list ships empty.

## Magic (data/magic.json)

4 elements × 4 sub-elements:

- Fire: Lightning, Plasma, Magma, Ash
- Water: Ice, Steam, Blood, Poison
- Earth: Metal, Crystal, Sand, Nature
- Air: Wind, Sound, Gravity, Light

A spell = **Sub-element + Movement class + Stat class** (+ power tier 1–3).
Movement: Projectile, Homing, Beam, Wave, Area, Ground, Orbit, Ward (stationary), Aura (self).
Stat: Damage, Heal, Strength, Speed, Dexterity, Vitality, Defense, Knockback, Root, Affliction (status).

The Set System computes mana cost, damage, range, duration, speed, area and cooldown from part
multipliers. Each sub-element allows only some stat classes (e.g. Blood can Heal, Light can't Root),
which keeps combinations balanced. Creating a spell (drafting/testing) is free; *inscribing* it in the
spell book is permanent-ish (replacing costs mana crystals). Capacity: 2 + level/3, max 12.

## Characters

**Attributes** (1–100): Strength, Speed, Health, Dexterity. **Skills** (0–100): Unarmed, Melee,
Ranged, Blocking, Dodging, Athletics, Mining, Gathering, Crafting, Magic, Trading.
Using a stat trains it with diminishing returns (`gain = base / (1 + value/20)`).
Level = derived from total experience; drives spell-book capacity.

**Needs**: Food and Water (0–100) drain per game hour; below 25 you suffer penalties, at 0 you lose HP.
Mana regenerates over time, faster when resting.

## NPCs (data/npcs.json) — 47 named

Each has race, pronouns, age, occupation, home, faction, 8 personality traits (0–10: friendliness,
aggression, confidence, intelligence, honesty, greed, loyalty, sociability), attributes, skills,
equipment, background, likes/dislikes, schedule template, romanceable flag and **recruitment
requirements** (gold, friendship, trust, respect, faction rep, skill, favor). Faction leaders are
recruitable late-game; their faction appoints a successor, which becomes world history.

## Travel (Oregon-Trail mode)

Choose a route from the world map. The journey runs in one-hour steps:
progress = base speed × pace × terrain × weather × party condition × encumbrance.
Each hour consumes food/water per party member according to **ration** setting (meager / normal /
generous); grueling pace speeds travel but injures and tires. Events roll per hour based on
route danger, weather, time of day and faction standings. Events offer choices whose effects are
applied by the Set System (items, gold, HP, time, reputation, memory records, combat).

## Calendar

60 min/h, 24 h/day, 7-day weeks, 4 weeks/month (28 days), 12 months/year.
Months: Thawmoon, Seedmoon, Bloomtide, Highsun, Embertide, Harvestmoon, Leaffall, Mistmoon,
Frostfall, Deepwinter, Ironfrost, Lastlight. Year starts at 412 A.R.
In local exploration 1 real second = 1 game minute.

## Economy

Currency: **marks**. Merchants have stock limits, cash limits and restock weekly. Sell price ≈ 50%
of value, modified by Trading skill and faction rep. Early income: foraging, Rustite (4 each),
scavenging, odd jobs. Milestones: town house (≈600 marks), outpost charter at Widow's Crossing
(≈2500 marks + materials).

## Systems added in Phases 4–9 (summary)
- **Crafting:** 98 recipes at furnace, anvil, workbench, stove, alchemy table and campfire. Crafting
  skill gates ore tiers. Head and body armor.
- **Favors:** 21 personal requests (deliver, pay, duel, clear an area, world flag) that gate many
  recruitment paths.
- **Legendary gear:** the Starfall Blade, the Skyglass Bow and the Emberheart Hammer, plus the Spire
  Core, found at guarded landmarks.
- **Companions:** a squad of 4, tasks, shared supplies, an ally AI, being downed rather than killed,
  bonds, couples and rivalries.
- **World simulation:** daily events, Hollow strength and territory, honours, regional prices, job boards.
- **Base:** a house in 6 towns, and an outpost at Widow's Crossing with 10 building types, workers,
  farming, research and raids.
- **Starting kit:** 25 marks, 3 rations, 4 water, 2 bandages, bread and an old Rustite dagger.

## Progression

- **Early — Survival**: forage, mine Rustite, scavenge, buy provisions, first recruit, buy a house.
- **Mid — Independence**: squad of 3–5, Greyvein/Sunsilver gear, outpost, farming, caravans, bounties.
- **Late — Influence**: faction politics, recruiting leaders, Voidglass gear, the Shattered Spire,
  custom high-tier spells, territory.

## Phase plan

1 Foundation · 2 World · 3 Combat · 4 Items & Magic · 5 NPCs & Local AI · 6 Companions & Relationships ·
7 World Simulation · 8 Base Building · 9 Polish. See DEVELOPMENT_LOG.md for status.
