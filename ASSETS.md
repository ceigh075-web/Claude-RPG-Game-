# External assets

Kindred Roads' code, data and most effects are original. The only third-party art is listed here.

## Pixel Crawler – Free Pack (Exterior 0.1)

| | |
|---|---|
| Author | Anokolisa (credit appreciated, not required; contact AnomalyPixel@gmail.com) |
| Source | Supplied by the project owner as `Pixel_Crawler_-_Free_Pack_Exterior_0.1.zip` (also on itch.io / Patreon: https://www.patreon.com/Anokolisa) |
| Licence | Author's own terms, copied verbatim in `assets/pixel_crawler/Terms.txt`. Summary: free to use in commercial and non-commercial projects; may be altered in any way; **the assets themselves may not be sold or redistributed as a product on their own**. Not CC0. |
| Location | `assets/pixel_crawler/` (58 files, ~750 KB — a curated subset, not the whole pack) |

Because the licence forbids selling the art as a standalone product, keep it inside the game folder and don't
publish it as a separate asset download.

### What is used, and how

| Pack files | Used for | Changes made at runtime |
|---|---|---|
| `Entities/Characters/Body_A/Animations/*` (idle, walk, run, slice, pierce, crush, hit, death, collect × down/side/up) | Every humanoid: player, companions, NPCs, humanoid enemies | Baked tools removed; body regions (skin, hair, shirt, armour, legs, boots) recoloured per character; race features (ears, tusks, freckles, war paint) drawn on; equipped weapon posed at the hand; smear arcs kept as a tinted effect layer |
| `Entities/Mobs/Skeleton Crew/Skeleton - Base/{Idle,Run,Death}` | Husk enemies | Mirrored for left-facing |
| `Weapons/Wood/Wood.png` | Weapon silhouettes (sword, axe, spear, mallet, dagger, bow, pickaxe…) | Striking part recoloured to the ore (Rustite / Greyvein / Sunsilver / Voidglass); scaled per weapon type |
| `Environment/Tilesets/Floors_Tiles.png` | Ground, path, plaza and floor textures | Tinted to each biome's existing palette; ragged overhang edges generated between tile types |
| `Environment/Tilesets/Water_tiles.png` | Animated water (4 frames) | Tinted for swamp / cave / cold biomes; shoreline foam added |
| `Environment/Props/Static/Trees/*`, `Vegetation.png`, `Rocks.png` | Trees, bushes, flowers, mushrooms, rocks, ore veins, crystals, ground clutter | Picked per biome; rocks tinted for dark biomes; ore specks drawn onto rocks in the ore's colour |
| `Environment/Structures/Buildings/Walls.png` | Building facades (log, plank, plaster, brick strips) | Cropped to two tiles high, tinted to town palette; roofs, windows, chimneys and banners are drawn procedurally |
| `Environment/Props/Static/Furniture.png`, `Farm.png`, `Dungeon_Props.png`, `Structures/Buildings/Props.png`, `Interior/*` | Interior furniture, barrels, crates | none |
| `Environment/Structures/Stations/*` (Anvil, Furnace, Workbench, Cooker, Alchemy, Bonfire) | Crafting stations, animated campfires | none |

Sprite rectangles are listed in `game/presentation/assets.py` (`MANIFEST`); `tools/preview_assets.py` renders all
of them on one sheet for checking.

### Not from the pack (original, procedural)

Spell and combat effects (`vfx.py`), non-humanoid creatures (wolves, bugs, wurms, brutes, golems –
`creatures.py`), roofs, windows, UI, and the fallback art in `art.py` used if the asset folder is missing.
