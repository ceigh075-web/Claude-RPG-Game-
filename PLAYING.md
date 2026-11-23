# Playing Kindred Roads

**Windows:** unzip and double-click `KindredRoads.exe`.
Windows SmartScreen may warn about an unrecognized app (the build isn't code-signed). Choose
**More info → Run anyway**.

**Linux / macOS:** unzip, then run `./KindredRoads`. On macOS you may need to right-click → Open the
first time (the app is unsigned).

Your saves and settings are kept in a `KindredRoads_data` folder created next to the game. Back up that
folder to keep your progress.

## Controls

| Key | Action |
|---|---|
| WASD / arrows | Move (8 directions); Shift to sprint |
| E / Enter | Interact, talk, confirm |
| K / left mouse | Attack (repeat for combos; hold to draw a bow) |
| L / right mouse | Block (hold) |
| Space | Dodge roll |
| F | Kick |
| Q | Switch melee / ranged weapon |
| G | Hostile intent on/off: your attacks hit anyone (townsfolk, companions), and finish off the fallen |
| H | Adventurer's Guide: tutorials, where to find resources, how to earn money, your objectives |
| Tab | Quick menu (every screen in one place) |
| F11 | Full screen (the window can also be resized) |
| 1–4 | Cast spells |
| I / C / J | Inventory / character / journal |
| B / P / R | Spell book / your company / relationships |
| M | World map (travel) |
| Esc | Menu: save, load, options, controls |
| F5 / F9 | Quick save / quick load |

## Optional: AI dialogue

NPCs talk with built-in personality dialogue out of the box. For free-form conversations, install
[Ollama](https://ollama.com) and run:

```
ollama pull llama3.2:3b
```

Then in the game open **Esc → Options** and use **Test AI connection**. LM Studio, llama.cpp
`llama-server` and other OpenAI-compatible servers also work: switch "AI server" in Options.

## Credits

Character, environment and prop art: *Pixel Crawler – Free Pack* by Anokolisa (see ASSETS.md for details and terms). Everything else is original to Kindred Roads.
